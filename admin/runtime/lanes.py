"""Lane owner: one bounded `drain` over a closed `Admit` family, PEP-734 `offload`, and a fed source.

`LanePolicy.drain` is the bounded drain: one `anyio.create_task_group` under one `functools.cache`-memoised
`CapacityLimiter` per lane identity and one `move_on_after` deadline scope. A `Block[Admit]` admits three
cases through one `ADMIT_TABLE` row each — a bare `Work`, a content-`keyed` cache unit, a `retried`
resilience-guarded unit — resolving into one `DrainReceipt[object]` carrying the recovered values, the
threaded session `Map`, the typed `Block[BoundaryFault]`, and the five-column outcome tally; the lane is
concept-agnostic and the consumer narrows the `object` value at its boundary. `LanePolicy.offload` routes a
CPU kernel through `anyio.to_interpreter.run_sync` under the same limiter and deadline, forwarding an injected
W3C `Carrier` as the kernel's leading positional so a caller's clean `traced_kernel` applicator attaches it
worker-side, lifting a deadline/cold-start crash through `async_boundary`. The module-level
`drain(policy, units, cache)` is the consumer seam delegating to `policy.drain`.

`StagePlan.execute` drives a `graphlib` DAG, each dependency front draining concurrently and threading its
cache forward. `LaneSource` is the closed `scheduled`/`watched` feeder union projected by one `_events`
`match`; `feed` threads the receipts `@drained` aspect over it. Cancellation rides `move_on_after`, cron rides
apscheduler 4.x `AsyncScheduler`, and bare `asyncio` is never imported.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
import functools
from graphlib import TopologicalSorter
import math
from os import fspath, PathLike
from typing import Final, get_args, Literal, NewType, TYPE_CHECKING

import anyio
from anyio import CapacityLimiter, move_on_after, WouldBlock
from anyio.streams.memory import MemoryObjectSendStream
from anyio.to_interpreter import run_sync as interpreter_run_sync
from apscheduler import AsyncScheduler, JobReleased
from apscheduler.abc import Trigger
from expression import case, Nothing, Ok, Option, Some, tag, tagged_union
from expression.collections import Block, Map
import msgspec
from opentelemetry import context, propagate
from watchfiles import awatch, BaseFilter, Change, PythonFilter

from admin.runtime.rails import async_boundary, BoundaryFault, RuntimeRail
from admin.runtime.resilience import guard, RetryClass


# `receipts` consumes this module's `DRAIN_COLUMNS`/`DrainReceipt`, so the receipts dependency runs the
# other way: `Redaction` is referenced structurally here and the `@drained` aspect is imported
# function-locally inside `feed`, never module-top (it would close a lanes->receipts->lanes cycle).
if TYPE_CHECKING:
    from admin.runtime.receipts import Redaction


# --- [TYPES] ---------------------------------------------------------------------------

ContentKey = NewType("ContentKey", str)

# The lane is concept-agnostic: a `Work` rail yields `object` and the consumer narrows at its own
# boundary. `Work`/`Admit` are non-generic so a concrete `Work[_T]` a caller builds is admitted by
# return-covariance (a `…RuntimeRail[_T]` callable IS-A `…RuntimeRail[object]` callable) without fighting
# the invariant `Block`/`Map` — the receipts owner's `DrainReceipt[object]` spelling is the one place the
# value type surfaces, carried by the generic `DrainReceipt[T]` struct alone.
type Work = Callable[[], Awaitable[RuntimeRail[object]]]
type Kernel[T] = Callable[..., T]
# The carrier-first applicator `offload` forwards the injected `Carrier` into: a clean-module callable a
# caller composes by binding `traced_kernel` to its inner `Kernel[T]`, so the worker attaches the W3C
# parent off the forwarded carrier before running the inner kernel. `offload` types its `kernel` param to
# this, not bare `Kernel[T]`, so the carrier-leading hop contract is checked rather than implicit.
type TracedKernel[T] = Callable[..., T]
type Carrier = dict[str, str]
type AdmitTag = Literal["bare", "keyed", "retried"]
type DrainOutcome = Literal["accepted", "completed", "cancelled", "rejected", "hit"]
type _Resolved = tuple[Option[ContentKey], RuntimeRail[object]]
type _Probed = tuple[Option[ContentKey], Option[object], Work]
type _StageWork = Callable[[str, RetryClass], Sequence[Work]]


@tagged_union(frozen=True)
class Admit:
    """The closed admission family `drain` discriminates on, one `ADMIT_TABLE` row per case.

    `bare` runs a plain rail coroutine, `keyed` short-circuits its `ContentKey` against the session
    cache, `retried` binds `guard(cls)` so a transient fault retries under one stamina policy row. The
    CPU-kernel `offload` is a distinct `LanePolicy` method sharing the lane budget, never a fourth case.
    """

    tag: AdmitTag = tag()
    bare: Work = case()
    keyed: tuple[ContentKey, Work] = case()
    retried: tuple[RetryClass, Work] = case()

    @staticmethod
    def of(work: Work) -> Admit:
        """A `bare` admission: a plain rail coroutine the lane runs directly, no key, no guard."""
        return Admit(bare=work)

    @staticmethod
    def cached(key: ContentKey, work: Work) -> Admit:
        """A `keyed` admission: short-circuit `work` against the session cache on a `key` hit."""
        return Admit(keyed=(key, work))

    @staticmethod
    def guarded(retry: RetryClass, work: Work) -> Admit:
        """A `retried` admission: bind `guard(cls)` so a transient fault retries under one stamina row."""
        return Admit(retried=(retry, work))


@tagged_union(frozen=True)
class LaneSource:
    """The closed feeder union `feed` drains: a cron/interval/one-off fire or a filtered file-change batch.

    `scheduled` carries an apscheduler 4.x `Trigger` and the projector folding each `JobReleased` fire
    into admission units; `watched` carries the watch roots, an optional `BaseFilter`, and the projector
    folding each `awatch` `Change` batch into units. A new source modality is one case plus one `_events`
    arm; the shared `feed` tail owns the single observed drain.
    """

    tag: Literal["scheduled", "watched"] = tag()
    scheduled: tuple[Trigger, Callable[[JobReleased], Block[Admit]]] = case()
    watched: tuple[tuple[str | PathLike[str], ...], BaseFilter | None, Callable[[set[tuple[Change, str]]], Block[Admit]]] = case()

    @staticmethod
    def on_schedule(trigger: Trigger, build: Callable[[JobReleased], Block[Admit]]) -> LaneSource:
        """A `scheduled` feeder: `trigger` fires on the one `AsyncScheduler`, `build` projects each fire."""
        return LaneSource(scheduled=(trigger, build))

    @staticmethod
    def on_change(
        paths: Sequence[str | PathLike[str]], build: Callable[[set[tuple[Change, str]]], Block[Admit]], *, watch_filter: BaseFilter | None = None
    ) -> LaneSource:
        """A `watched` feeder: freeze the watch roots to a tuple at the edge, `build` projects each batch."""
        return LaneSource(watched=(tuple(paths), watch_filter, build))


# --- [CONSTANTS] -----------------------------------------------------------------------

_INF: Final = math.inf
# Derived from the `DrainOutcome` vocabulary, never re-enumerated: the Literal IS the column set, so the
# `receipts` `drained` egress and any counter dimension read this one ordered fact and can never drift.
DRAIN_COLUMNS: Final[tuple[DrainOutcome, ...]] = get_args(DrainOutcome.__value__)
# Bounded fire-seam buffer: a slow consumer backpressures the apscheduler `subscribe` callback, whose
# `send_nowait` then raises `WouldBlock`; the seam drops the overflow as the scheduler's own
# coalesce/misfire policy rather than a raise breaking the subscription.
_FIRE_BUFFER: Final = 64


# --- [MODELS] --------------------------------------------------------------------------


class DrainReceipt[T](msgspec.Struct, frozen=True):
    """Lossless drain evidence: the five outcome counts plus the recovered values, cache, and faults.

    `values` carries both replayed cache hits and resolved oks; `faults` carries the typed boundary
    faults rejected units minted, so a drained lane surfaces which units failed *and* the values that
    succeeded — never a count-only return that discards the computed work. `cache` threads the session
    `Map` forward so a downstream `StagePlan` front replays an upstream `Ok`. The generic parameter
    defaults to `object` at the concept-agnostic consumer call sites that build the receipt directly.
    """

    accepted: int
    completed: int
    cancelled: int
    rejected: int
    values: Block[T] = Block.empty()
    cache: Map[ContentKey, T] = Map.empty()
    faults: Block[BoundaryFault] = Block.empty()
    hit: int = 0

    @staticmethod
    def of(
        accepted: int, hit: int, resolved: Block[_Resolved], replayed: Block[tuple[ContentKey, object]], cache: Map[ContentKey, object]
    ) -> DrainReceipt[object]:
        """Fold the resolved rails and replayed cache hits into one lossless receipt.

        `completed`/`faults` split the resolved rails by `Result` tag via `to_option`/`swap().to_option`
        (mirroring `rails.traversed`'s accumulate fold); `cancelled` is the went-live cardinality minus
        the cardinality that reached the stream, so a deadline trip reports its partial losses with the
        values intact. Only a unit that both carried a `ContentKey` and resolved `Ok` folds back into the
        threaded cache. `values` carries the replayed hits ahead of the resolved oks.

        Args:
            accepted: The admitted cardinality (every unit, hits included).
            hit: The cardinality that short-circuited on a cache hit without going live.
            resolved: The `(key, rail)` outcomes that reached the stream live.
            replayed: The `(key, value)` cache hits reproduced without invoking the coroutine.
            cache: The prior session cache the survivors thread out of.

        Returns:
            The folded `DrainReceipt[U]` carrying values, threaded cache, typed faults, and the tally.
        """
        merged = replayed.map(lambda pair: (Some(pair[0]), Ok(pair[1]))).append(resolved)
        completed = resolved.choose(lambda pair: pair[1].to_option())
        faults = resolved.choose(lambda pair: pair[1].swap().to_option())

        def thread(acc: Map[ContentKey, object], pair: _Resolved) -> Map[ContentKey, object]:
            return pair[0].bind(lambda key: pair[1].to_option().map(lambda value: acc.add(key, value))).default_value(acc)

        threaded = merged.fold(thread, cache)
        return DrainReceipt(
            accepted=accepted,
            completed=len(completed),
            cancelled=accepted - hit - len(resolved),
            rejected=len(faults),
            values=merged.choose(lambda pair: pair[1].to_option()),
            cache=threaded,
            faults=faults,
            hit=hit,
        )


class AdmitRow(msgspec.Struct, frozen=True):
    """One admission behavior row: the `Option[ContentKey]` cache probe and the `Work` builder."""

    key: Callable[[Admit], Option[ContentKey]]
    make: Callable[[Admit], Work]


# --- [SERVICES] ------------------------------------------------------------------------


@functools.cache
def _limiter(policy: LanePolicy) -> CapacityLimiter:
    """The one bounded slot allocator per lane identity; minted once and shared across drain and offload.

    The frozen `LanePolicy` is hashable, so the policy is the memo key and one `CapacityLimiter` bounds the
    lane across its lifetime; two policies with identical `capacity`/`deadline` share one bound, capping both
    their concurrent drain units and their offload subinterpreter hops on one allocator.

    Returns:
        The memoised `CapacityLimiter` bounding every drain and offload on this policy identity.
    """
    return CapacityLimiter(policy.capacity)


class LanePolicy(msgspec.Struct, frozen=True):
    """Frozen lane value object: the concurrency capacity and an optional deadline budget.

    `drain` and `offload` are the two bounded entrypoints sharing the memoised per-identity limiter and
    the `move_on_after` deadline; `available_tokens` exposes the live free-token count the admission
    governor pre-checks. The module-level `drain` delegates here for the locked consumer call shape.
    """

    capacity: int
    deadline: Option[float] = Nothing

    @property
    def limiter(self) -> CapacityLimiter:
        """The memoised `CapacityLimiter` shared across this policy's every drain and offload."""
        return _limiter(self)

    @property
    def available_tokens(self) -> int:
        """The live free-token count off the shared limiter; the admission governor's overflow seam."""
        return math.floor(self.limiter.available_tokens)

    async def drain(self, units: Block[Admit], cache: Map[ContentKey, object] = Map.empty()) -> DrainReceipt[object]:  # noqa: B008 - `Map.empty()` is the immutable persistent-collection factory, no shared-mutable-default hazard
        """Admit and resolve every unit under one bounded task group, folding to a lossless receipt.

        Each unit's `ADMIT_TABLE` row is resolved once by `probe` into a `(key, cached, work)` triple; a
        single `Block.partition` splits the cache hits (replayed without invoking the coroutine) from the
        live units. The live units run under one `CapacityLimiter` slot each inside one
        `move_on_after(deadline)` scope, each sending its full `RuntimeRail` over one memory stream so the
        typed fault survives. A tripped deadline cancels the in-flight units and the receipt reports them as
        `cancelled` with the partial values/faults intact — never a raw `TimeoutError` escaping the lane
        without a receipt.

        Args:
            units: The admission units, each discriminated by case through `ADMIT_TABLE`.
            cache: The session cache `keyed` units short-circuit against; survivors thread out.

        Returns:
            One `DrainReceipt[object]` carrying the values, threaded cache, typed faults, and outcome tally.
        """
        limiter = self.limiter
        budget = self.deadline.default_value(_INF)
        send, receive = anyio.create_memory_object_stream[_Resolved](max(len(units), 1))
        probed = units.map(lambda unit: probe(ADMIT_TABLE[unit.tag], unit, cache))
        hits, live = probed.partition(lambda triple: triple[1].is_some())
        replayed = hits.choose(lambda triple: triple[0].map2(lambda key, value: (key, value), triple[1]))

        async def lane(key: Option[ContentKey], fn: Work, sink: MemoryObjectSendStream[_Resolved]) -> None:
            async with sink, limiter:
                await sink.send((key, await fn()))

        with move_on_after(budget):
            async with anyio.create_task_group() as group, send:
                for key, _, fn in live:
                    group.start_soon(lane, key, fn, send.clone())
        resolved = Block.of_seq([item async for item in receive])
        return DrainReceipt.of(len(units), len(replayed), resolved, replayed, cache)

    async def offload[T](self, kernel: TracedKernel[T], *args: object, retry: RetryClass | None = None) -> RuntimeRail[T]:
        """Route a carrier-seeded CPU kernel through per-subinterpreter execution under the shared lane budget.

        The kernel runs via `anyio.to_interpreter.run_sync` (PEP 734 per-subinterpreter GIL, no pickle hop)
        under the same memoised limiter and `move_on_after` deadline `drain` bounds with. The active OTel
        context injects into a `Carrier` once and forwards as the kernel's leading positional, so `kernel` is
        a subinterpreter-clean module-level `(carrier, *args) -> T` applicator (a caller's `traced_kernel`
        bound around its inner kernel) that runs `propagate.extract`+`context.attach` worker-side — this
        module's `msgspec`/`watchfiles` C-extensions bar it from subinterpreter load, so the attach applicator
        lives in the caller's clean module and the lane forwards the carrier rather than the shim. An optional
        `retry` wraps the leg in `guard(cls)` so a transient `BrokenWorkerInterpreter` cold-start retries
        before the lift. The kernel is received, never imported.

        Args:
            kernel: The subinterpreter-clean `(carrier, *args) -> T` applicator run in a fresh subinterpreter.
            args: The cross-interpreter-shareable positional arguments forwarded after the carrier.
            retry: An optional retry class wrapping the offload leg against transient worker crashes.

        Returns:
            `Ok(value)` on a clean hop, or `Error(BoundaryFault)` for a deadline trip or terminal crash.
        """
        carrier: Carrier = {}
        propagate.inject(carrier)

        async def run() -> T:
            return await interpreter_run_sync(kernel, carrier, *args, limiter=self.limiter)

        async def hop() -> T:
            with move_on_after(self.deadline.default_value(_INF)):
                return await (guard(retry)(run) if retry is not None else run())
            raise TimeoutError("offload deadline elapsed")

        return await async_boundary("offload", hop)


class StagePlan(msgspec.Struct, frozen=True):
    """A multi-stage DAG over one `LanePolicy.drain`, each dependency-level front draining concurrently.

    `execute` drives a `graphlib.TopologicalSorter` in active `prepare`/`get_ready`/`done` mode so every
    same-level stage's flattened work runs concurrently under one drain (units entering as `retried` cases
    carrying the stage's `RetryClass`), and threads each front's `DrainReceipt.cache` forward so a `keyed`
    unit a downstream stage re-admits replays the upstream `Ok` rather than recomputing. A new stage is
    one edge; the front-internal capacity stays bounded by the lane's one limiter.
    """

    lane: LanePolicy
    stages: tuple[tuple[str, RetryClass], ...]
    edges: tuple[tuple[str, str], ...]

    async def execute(self, work: _StageWork) -> tuple[DrainReceipt[object], ...]:
        """Drive the stage DAG, one concurrent drain per dependency front, cache threaded across fronts.

        Args:
            work: The per-stage work projector yielding the `Work` units a stage admits as `retried`.

        Returns:
            One `DrainReceipt[object]` per dependency-level front, in topological-front order.
        """
        classes = dict(self.stages)
        order: TopologicalSorter[str] = TopologicalSorter(dict.fromkeys(classes, ()))
        for parent, child in self.edges:
            order.add(child, parent)
        order.prepare()
        carried: Map[ContentKey, object] = Map.empty()
        collected: Block[DrainReceipt[object]] = Block.empty()
        while order.is_active():
            front = order.get_ready()
            units = Block.of_seq([Admit.guarded(classes[stage], fn) for stage in front for fn in work(stage, classes[stage])])
            receipt = await self.lane.drain(units, carried)
            order.done(*front)
            carried, collected = receipt.cache, collected.append(Block.singleton(receipt))
        return tuple(collected)


# --- [OPERATIONS] ----------------------------------------------------------------------


def probe(row: AdmitRow, unit: Admit, cache: Map[ContentKey, object]) -> _Probed:
    """Resolve one admission row into the `(key, cached, work)` triple `drain` partitions in one pass.

    The row's `key` projection yields the `Option[ContentKey]` the unit probes the cache with (`Nothing`
    for the un-keyed `bare`/`retried` cases); `key.bind(cache.try_find)` folds the cache hit; `make`
    builds the `Work`. One pass per unit — never a double row lookup or a double `try_find`.

    Returns:
        The `(Option[ContentKey], Option[object], Work)` triple: the probe key, the cache hit, the work.
    """
    key = row.key(unit)
    return key, key.bind(cache.try_find), row.make(unit)


def traced_kernel[T](carrier: Carrier, kernel: Kernel[T], *args: object) -> T:
    """The W3C trace-stitch applicator a subinterpreter-clean kernel module composes as its offload entry.

    `LanePolicy.offload` forwards the injected `Carrier` as the leading positional, so a clean kernel module
    binds this applicator around its inner `Kernel[T]`: the worker runs `propagate.extract`+`context.attach`
    before invoking the kernel, parenting the offloaded work under the calling span where the worker carries
    the installed composite propagator (a worker without the install resolves an empty `Context` and runs
    unparented while the `traceparent` survives on the carrier). Pure-`opentelemetry`/stdlib so it resolves by
    `__qualname__` re-import in the PEP-734 worker this module's `msgspec`/`watchfiles` C-extensions cannot
    enter — the reference shape the caller's clean module mirrors.

    Returns:
        The kernel's result; the attached context token is detached on success, fault, or cancellation.
    """
    token = context.attach(propagate.extract(carrier))
    try:
        return kernel(*args)
    finally:
        context.detach(token)


def _fire_seam(send: MemoryObjectSendStream[JobReleased]) -> Callable[[JobReleased], None]:
    """Build the apscheduler `subscribe` callback pushing each `JobReleased` fire over the bounded stream.

    The sync callback's (`subscribe(..., is_async=False)`) non-blocking `send_nowait` raises `WouldBlock` once
    a slow consumer fills the buffer; the marked `except WouldBlock` drops that overflow as the scheduler's own
    coalesce/misfire policy, never a raise breaking the subscription (`contextlib.suppress` is TID251-banned).

    Returns:
        A sync callback registered against `JobReleased` on the one `AsyncScheduler`.
    """

    def on_fire(event: JobReleased) -> None:
        try:  # noqa: SIM105 - `contextlib.suppress` is banned by repo TID251; the explicit except is the marked drop
            send.send_nowait(event)
        except WouldBlock:  # noqa: S110 - the deliberate coalesce drop: a backpressured redundant fire is the scheduler's missed-fire policy
            pass

    return on_fire


async def drain(policy: LanePolicy, units: Block[Admit], cache: Map[ContentKey, object] = Map.empty()) -> DrainReceipt[object]:  # noqa: B008 - `Map.empty()` is the immutable persistent-collection factory, no shared-mutable-default hazard
    """Drain `units` under `policy` — the locked module seam delegating to `LanePolicy.drain`.

    The consumer-facing call shape (`await drain(policy, units, cache)`); the bounded task group, limiter,
    deadline scope, and lossless fold all live on `LanePolicy.drain`.

    Returns:
        The lossless `DrainReceipt[object]` for the admitted units.
    """
    return await policy.drain(units, cache)


async def _events(source: LaneSource) -> AsyncIterator[Block[Admit]]:
    """Project a `LaneSource` into the `Block[Admit[T]]` batches `feed` drains, one `match` arm per case.

    `watched` iterates the `PythonFilter`-narrowed `awatch` change stream (a `None` filter lifting to
    `PythonFilter()`), projecting each `Change` batch through the case's builder. `scheduled` registers
    its `Trigger` on one apscheduler 4.x `AsyncScheduler` (async CM, anyio-native), whose `subscribe`
    against `JobReleased` is the single fire seam pushing each fire over a bounded stream the loop
    projects. The arm set is total over the closed union; cron rides apscheduler alone — no `croniter`,
    no `aiocron`, no hand-rolled `anyio.sleep` loop.

    Yields:
        One `Block[Admit[T]]` per source event (a watch batch or a scheduler fire), projected by the case.

    Raises:
        AssertionError: Unreachable while the match is exhaustive over the closed `LaneSource` union; the
            explicit raise stands in for `assert_never`, which the `ty` gate rejects on the opaque residual.
    """
    match source:
        case LaneSource(tag="watched", watched=(paths, watch_filter, build)):
            async for batch in awatch(*(fspath(path) for path in paths), watch_filter=Option.of_optional(watch_filter).default_value(PythonFilter())):
                yield build(batch)
        case LaneSource(tag="scheduled", scheduled=(trigger, build)):
            send, receive = anyio.create_memory_object_stream[JobReleased](_FIRE_BUFFER)
            # the `AsyncScheduler` async-CM owns the 4.x lifecycle; `feed` fully drives this generator so
            # the scheduler shuts down when the `receive` stream closes or the enclosing task group cancels.
            async with AsyncScheduler() as scheduler, send:
                scheduler.subscribe(_fire_seam(send), JobReleased, is_async=False)
                await scheduler.add_schedule(_noop, trigger)
                await scheduler.start_in_background()
                async for event in receive:
                    yield build(event)  # noqa: ASYNC119 - the scheduler async-CM is the lifecycle owner; `feed` drains this to completion
        case _:  # pragma: no cover - exhaustive over the closed LaneSource union
            # the `ty` gate rejects `assert_never` on the opaque `tagged_union` residual, so the explicit raise carries the proven totality.
            raise AssertionError(source.tag)


async def feed(policy: LanePolicy, source: LaneSource, owner: str, redaction: Redaction) -> AsyncIterator[DrainReceipt[object]]:
    """Drain a `LaneSource` under one `@drained`-observed `policy.drain`, yielding one receipt per batch.

    The receipts `@drained` aspect wraps `policy.drain` once and threads it over the `_events` projector, so a
    `scheduled`/`watched` source is observed by composition — RSS probed and one `drained` receipt emitted per
    batch — rather than each source re-implementing the receipt egress.

    Args:
        policy: The lane the projected batches drain under.
        source: The closed feeder union `_events` projects.
        owner: The owning subject stamped into each emitted `drained` receipt.
        redaction: The receipt field keys dropped before emission.

    Yields:
        One observed `DrainReceipt[object]` per source batch.
    """
    from admin.runtime.receipts import drained  # noqa: PLC0415 - deferred to break the lanes->receipts->lanes import cycle

    observed = drained(owner, redaction=redaction)(policy.drain)
    async for batch in _events(source):
        yield await observed(batch)


def _noop() -> None:
    """The empty schedule target: the fire seam reads `JobReleased`, never a wrapped job body."""


# --- [TABLES] --------------------------------------------------------------------------

# One admission row per Admit case: (key projection, Work builder). `bare`/`retried` carry no content
# key; `keyed` projects its `ContentKey` so `drain` short-circuits on a cache hit. The `retried` builder
# wraps the inner coroutine in `guard(cls)` so retry is one admission case rather than caller boilerplate.
ADMIT_TABLE: Final[Map[AdmitTag, AdmitRow]] = Map.of_seq([
    ("bare", AdmitRow(key=lambda _unit: Nothing, make=lambda unit: unit.bare)),
    ("keyed", AdmitRow(key=lambda unit: Some(unit.keyed[0]), make=lambda unit: unit.keyed[1])),
    ("retried", AdmitRow(key=lambda _unit: Nothing, make=lambda unit: lambda: guard(unit.retried[0])(unit.retried[1]))),
])


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "ADMIT_TABLE",
    "DRAIN_COLUMNS",
    "Admit",
    "AdmitRow",
    "AdmitTag",
    "Carrier",
    "ContentKey",
    "DrainOutcome",
    "DrainReceipt",
    "Kernel",
    "LanePolicy",
    "LaneSource",
    "StagePlan",
    "TracedKernel",
    "Work",
    "drain",
    "feed",
    "probe",
    "traced_kernel",
]
