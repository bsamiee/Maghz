"""Lane owner: one bounded `drain` over a closed `Admit` admission family with thread-offload.

`drain` is the sole polymorphic entrypoint: one `anyio.create_task_group` per call and one
`functools.cache`-memoised `CapacityLimiter` per `LanePolicy` that gates every working unit — each
admitted unit acquires a lane token (`async with limiter`) so `LanePolicy.capacity` is the true
concurrency bound, while a cache hit skips the gate entirely. The token-held body runs under a
per-unit `anyio.move_on_after` deadline scope (a tripped scope increments `cancelled`, never raises);
the deadline covers only working time, never the queue wait for a token. `offload` cases run through
`anyio.to_thread.run_sync(fn, limiter=)` under a *distinct* thread limiter (the per-unit override, or
anyio's default thread limiter on `Nothing`) because re-acquiring the lane token on the same task
raises. Every unit's outcome arrives over one `create_memory_object_stream` channel; `keyed` units
short-circuit on a cache hit. `_fold` folds the outcomes into a frozen `DrainReceipt` via `Block`
combinators, splitting ok/error rails by `Result` tag and threading the content cache through
`Map.add`. `ADMIT_TABLE` discriminates admission by case.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
import functools
import math
from typing import Final, Literal, NewType

import anyio
from anyio.streams.memory import MemoryObjectSendStream
import anyio.to_thread
from expression import case, Error, Nothing, Ok, Option, Result, Some, tag, tagged_union
from expression.collections import Block, Map

from admin.runtime.rails import async_boundary, BoundaryFault, RuntimeRail
from admin.runtime.resilience import guard, RetryClass


# --- [TYPES] ---------------------------------------------------------------------------

ContentKey = NewType("ContentKey", str)

type AdmitTag = Literal["bare", "keyed", "retried", "offload"]
type Work = Callable[[], Awaitable[RuntimeRail[object]]]
type _Outcome = tuple[Literal["done", "cancelled", "hit"], Option[ContentKey], RuntimeRail[object]]
type _KeyFn = Callable[[Admit], Option[ContentKey]]
type _MakeFn = Callable[[Admit], Work]


# --- [CONSTANTS] -----------------------------------------------------------------------

_INF: Final = math.inf
# Resolution phase -> the DrainReceipt counter it bumps, split by ok/error rail: an ok `hit` grows
# `hit`, an ok `done` grows `completed`; an error `cancelled` grows `cancelled`, any other error
# (a `done` carrying an `Error` rail) grows `rejected`.
_OK_SLOT: Final[dict[str, str]] = {"hit": "hit", "done": "completed"}
_ERR_SLOT: Final[dict[str, str]] = {"cancelled": "cancelled", "done": "rejected"}


# --- [MODELS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class Admit:
    """The closed admission family `drain` discriminates on, one row per case in `ADMIT_TABLE`."""

    tag: AdmitTag = tag()
    bare: Work = case()
    keyed: tuple[ContentKey, Work] = case()
    retried: tuple[RetryClass, Work] = case()
    offload: tuple[Callable[[], object], Option[anyio.CapacityLimiter]] = case()


@dataclass(frozen=True, slots=True, kw_only=True)
class LanePolicy:
    """Frozen lane value object: the concurrency capacity and an optional per-unit deadline budget."""

    capacity: int
    deadline: Option[float] = field(default=Nothing)


@dataclass(frozen=True, slots=True)
class DrainReceipt:
    """Frozen drain evidence: admission counters plus the collected values, cache, and faults."""

    accepted: int
    completed: int
    cancelled: int
    rejected: int
    values: Block[object] = field(default_factory=Block.empty)
    cache: Map[ContentKey, object] = field(default_factory=Map.empty)
    faults: Block[BoundaryFault] = field(default_factory=Block.empty)
    hit: int = 0


# --- [OPERATIONS] ----------------------------------------------------------------------


@functools.cache
def _limiter(policy: LanePolicy) -> anyio.CapacityLimiter:
    """The memoised `CapacityLimiter` for one `LanePolicy`; shared across that policy's drains."""
    return anyio.CapacityLimiter(policy.capacity)


def _flat(subject: str, inner: Work) -> Work:
    """Run a rail-returning thunk through `async_boundary` and flatten the doubly-lifted result.

    The thunk already yields a `RuntimeRail[object]`; `async_boundary` lifts any escape it raises
    before producing that rail, and the `bind` collapses the `Ok(inner_rail)` back to one level so a
    thunk-internal `Error` is preserved rather than re-wrapped.

    Returns:
        A `Work` whose awaited result is the single-level rail with thunk-internal faults preserved.
    """

    async def _run() -> RuntimeRail[object]:
        lifted = await async_boundary(subject, inner)
        return lifted.bind(lambda rail: rail)

    return _run


def _offload_work(unit: Admit) -> Work:
    """Build the thread-offload `Work` for an `offload` unit, honoring its per-unit limiter override.

    The lane `CapacityLimiter` already gates this unit's async slot inside `_admit`, so the thread
    fence must run under a *different* limiter — the same task acquiring one limiter twice raises
    `RuntimeError`. An absent override (`Nothing`) therefore defers to anyio's default thread limiter;
    an explicit override is a distinct token pool the caller owns.

    Returns:
        A `Work` that threads the worker call through `async_boundary` under the resolved limiter.
    """
    fn, override = unit.offload
    limiter = override.default_value(anyio.to_thread.current_default_thread_limiter())
    return lambda: async_boundary("offload", lambda: anyio.to_thread.run_sync(fn, limiter=limiter))


def _retried_work(unit: Admit) -> Work:
    """Build the guarded `Work` for a `retried` unit, threading the inner thunk through `guard`."""
    cls, inner = unit.retried
    return _flat("retried", lambda: guard(cls)(inner))


async def drain(policy: LanePolicy, units: Block[Admit], cache: Map[ContentKey, object]) -> DrainReceipt:
    """Admit and resolve every unit under one bounded task group, folding outcomes to a `DrainReceipt`.

    Args:
        policy: The lane value object owning the concurrency capacity and per-unit deadline budget.
        units: The admission units; each is discriminated by case through `ADMIT_TABLE`.
        cache: The content cache `keyed` units short-circuit against; surviving entries thread out.

    Returns:
        A frozen `DrainReceipt` whose counters and `values`/`cache`/`faults` fold the unit outcomes.
    """
    limiter = _limiter(policy)
    budget = policy.deadline.default_value(_INF)
    tripped: RuntimeRail[object] = Error(BoundaryFault(deadline=("drain", budget)))
    send, receive = anyio.create_memory_object_stream[_Outcome](max(len(units), 1))

    async def _admit(unit: Admit, channel: MemoryObjectSendStream[_Outcome]) -> None:
        key_fn, make_fn = ADMIT_TABLE[unit.tag]
        async with channel:
            key = key_fn(unit)
            cached = key.bind(cache.try_find)
            if cached.is_some():
                await channel.send(("hit", key, Ok(cached.value)))
                return
            async with limiter:
                work = make_fn(unit)
                with anyio.move_on_after(budget) as scope:
                    outcome = await work()
            await channel.send(("cancelled", key, tripped) if scope.cancelled_caught else ("done", key, outcome))

    async with anyio.create_task_group() as tg:
        async with send:
            for unit in units:
                tg.start_soon(_admit, unit, send.clone())
        async with receive:
            collected = [item async for item in receive]
    return _fold(Block.of_seq(collected), cache)


def _fold(outcomes: Block[_Outcome], cache: Map[ContentKey, object]) -> DrainReceipt:
    """Fold the resolved unit outcomes into one frozen `DrainReceipt` via collection combinators.

    The two ok phases (`hit`/`done`) grow `values`/`cache` and bump `hit`/`completed` via `_OK_SLOT`;
    the two error phases (`cancelled`/`done`) grow `faults` and bump `cancelled`/`rejected` via
    `_ERR_SLOT`. `accepted` always bumps, so the four outcome arms collapse to two growers.

    Returns:
        The folded `DrainReceipt` seeded with the prior content `cache` and zeroed counters.
    """

    def _ok(receipt: DrainReceipt, key: Option[ContentKey], value: object, slot: str) -> DrainReceipt:
        cached = key.map(lambda content: receipt.cache.add(content, value)).default_value(receipt.cache)
        bumped = {"accepted": receipt.accepted + 1, slot: getattr(receipt, slot) + 1}
        return replace(receipt, values=receipt.values.append(Block.singleton(value)), cache=cached, **bumped)

    def _err(receipt: DrainReceipt, fault: BoundaryFault, slot: str) -> DrainReceipt:
        bumped = {"accepted": receipt.accepted + 1, slot: getattr(receipt, slot) + 1}
        return replace(receipt, faults=receipt.faults.append(Block.singleton(fault)), **bumped)

    def _step(receipt: DrainReceipt, outcome: _Outcome) -> DrainReceipt:
        phase, key, rail = outcome
        match rail:
            case Result(tag="ok", ok=value):
                return _ok(receipt, key, value, _OK_SLOT[phase])
            case Result(tag="error", error=fault):
                return _err(receipt, fault, _ERR_SLOT[phase])
            case _:  # pragma: no cover - Result is a closed ok/error union
                return receipt

    return outcomes.fold(_step, DrainReceipt(accepted=0, completed=0, cancelled=0, rejected=0, cache=cache))


# --- [TABLES] --------------------------------------------------------------------------

# One admission row per Admit case: (key extractor, Work builder). `bare`/`retried`/`offload` carry
# no content key; `keyed` projects its ContentKey so `drain` short-circuits on a cache hit. The
# builder lifts each case's thunk to a uniform `Work` (offload threads to a worker, retried wraps
# in `guard`, bare/keyed run the inner coroutine directly through `async_boundary`).
ADMIT_TABLE: Final[Map[AdmitTag, tuple[_KeyFn, _MakeFn]]] = Map.of_seq([
    ("bare", (lambda _unit: Nothing, lambda unit: _flat("bare", unit.bare))),
    ("keyed", (lambda unit: Some(unit.keyed[0]), lambda unit: _flat("keyed", unit.keyed[1]))),
    ("retried", (lambda _unit: Nothing, _retried_work)),
    ("offload", (lambda _unit: Nothing, _offload_work)),
])


# --- [COMPOSITION] ---------------------------------------------------------------------

__all__ = ["ADMIT_TABLE", "Admit", "AdmitTag", "ContentKey", "DrainReceipt", "LanePolicy", "Work", "drain"]
