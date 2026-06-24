"""Automation engine: the single polymorphic `drive` composing the substrate `feed`/`drain` lane owner.

`drive(spec, cfg)` is the sole entrypoint and the sole `Envelope` projection edge. It opens one
`anyio.create_task_group` per call, reads `tag_of(spec.trigger, TriggerTag)`, and keys the `_LANE` table:
`manual` drains one governed batch directly off the substrate `drain`; `watch`/`schedule` compose the
substrate `feed(policy, LaneSource.on_change/on_schedule, "automation", redaction)` so the lane owner — not
the engine — owns the `watchfiles.awatch` stream, the apscheduler 4.x `AsyncScheduler` fire-seam, the
`@drained` receipt egress, and the lossless `DrainReceipt` fold. The engine never re-implements the watch
loop or the scheduler lifecycle; it supplies one `build` projector per source that governs admission and
emits the `Block[Admit]` the shared `feed` tail drains. The caller-spawned `_signal_lane` cancels the group
on `SIGTERM`/`SIGINT`, which closes the `feed` generator and exits the daemon with one summary envelope.

Admission is one pure `_admit(spec, cfg, policy) -> Result[_Snapshot, Gate]` rail read BEFORE any lane token
is borrowed: `Ok(snapshot)` carries the psutil reading the receipt stamps (so the gate and the receipt never
diverge); `Error(gate)` is a deliberate `Status.SKIP` over-ceiling or saturated outcome that never enters the
boundary rail. The governed batch rides one `LanePolicy.drain` borrow whose `deadline=Some(action_timeout_s)`
contains a tripped deadline as a `cancelled` count rather than a raised `TimeoutError`; an empty governed
batch (a gated tick) borrows nothing, so a gated fire never enters the drain lifecycle. `_fold` reads the
substrate `DrainReceipt` once: a completed fire's `values[0]` is the `AutomationReceipt`, a surviving
`BoundaryFault` rides `faults[0]`, and an empty-but-cancelled receipt is the deadline trip folded to one
`BoundaryFault.deadline` leaf naming the spec and budget.

Every action arm rides the substrate `RuntimeRail[AutomationReceipt]` (`Result[_, BoundaryFault]`) — the SAME
`BoundaryFault` the drain's typed `faults` block carries — so the drain is lossless for the engine with no
sink cell, no `_project` cast, and no fault re-lift. `_exec` (total `match` + `assert_never`) owns the four
action arms and takes the governor snapshot on its signature, so no process-global cell threads it. `drive`
projects the union to stdout exactly once: `Ok(receipt)` lifts to `completed(Status.OK, …)`, a `Gate` projects
through `gate.envelope()` (`Status.SKIP`), and an `Error(BoundaryFault)` lowers through the substrate
`BoundaryFault.headline()`/`facts()` cause-naming — the engine never raises into the CLI and mints no parallel
fault carrier. The action arms compose the locked substrate rails (`sync.run`, `db.query`, the
`_AGENT_DISPATCH` skill callables); `_WATCH_FILTER`, `_AGENT_DISPATCH`, and `_LANE` are the three
correspondence tables, and the engine is skill-agnostic — it reads `_AGENT_DISPATCH[action.skill](action, spec, cfg)`.
"""

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, UTC
import os
import signal
import time
from typing import assert_never, Final, Literal

import anyio
from anyio.abc import TaskGroup
import anyio.to_thread
from apscheduler import JobOutcome, JobReleased
from apscheduler.triggers.cron import CronTrigger
from cyclopts import Token
from expression import Error, Nothing, Ok, Option, Result, Some
from expression.collections import Block
from frozendict import frozendict
import msgspec
import psutil
import structlog
from watchfiles import BaseFilter, Change, DefaultFilter, PythonFilter

from admin import db
from admin.automation.model import (
    Action,
    ActionTag,
    AgentAction,
    AgentSkill,
    AutomationReceipt,
    AutomationSpec,
    Embed,
    Gate,
    GateReason,
    Notify,
    Schedule,
    Sync,
    TriggerTag,
    Watch,
)
from admin.core import completed, Envelope, fault, Report, Status, tag_of
from admin.db import QueryResult
from admin.runtime import Admit, BoundaryFault, drain, DrainReceipt, LanePolicy, RetryClass, RuntimeRail
from admin.runtime.lanes import feed, LaneSource
from admin.runtime.receipts import Redaction
from admin.settings import MaghzSettings, settings


# --- [TYPES] ---------------------------------------------------------------------------

# The skill-dispatch contract `_AGENT_DISPATCH` rows carry, owned by the `integrations`/`mcp` blueprints:
# one polymorphic `(action, spec, cfg) -> RuntimeRail[AutomationReceipt]` over the substrate rail, so a
# skill fault is a `BoundaryFault` leaf the drain carries losslessly rather than a per-domain carrier.
type Work = Callable[[AgentAction, AutomationSpec, MaghzSettings], Awaitable[RuntimeRail[AutomationReceipt]]]
# The fire result: the substrate rail on a real fire (`Ok` receipt / `Error(BoundaryFault)`) OR a `Gate`
# value for a gated admission — a non-failure that never enters the boundary rail. `drive` folds the union
# once at the edge; `_admit` mints the `Gate`, every action arm the rail.
type _DispatchOutcome = RuntimeRail[AutomationReceipt] | Gate
# The admission rail: `Ok(_Snapshot)` is the governor reading a real fire stamps into its receipt, `Error(Gate)`
# the deliberate over-ceiling/saturated skip. `Gate` is the typed denied-admission outcome modeled as the
# `Error` arm of this local rail (distinct from the boundary `RuntimeRail`), read once before any token borrow.
type _Admission = Result[_Snapshot, Gate]
# The lane-builder a `TriggerTag` selects: `manual` drains once, `watch`/`schedule` compose the substrate
# `feed` daemon alongside the caller-spawned signal lane. The `drive` task group rides the signature so a
# daemon's `build` projector schedules a gated-tick skip-ledger onto the running group without blocking the
# sync projector. One row per tag in `_LANE`, so `drive` never re-derives the per-trigger shape with a
# `match`/`assert_never` over an already-exhaustive table.
type _LaneBuilder = Callable[[AutomationSpec, MaghzSettings, LanePolicy, TaskGroup], Awaitable[_DispatchOutcome]]


# --- [MODELS] --------------------------------------------------------------------------


class _Snapshot(msgspec.Struct, frozen=True, gc=False):
    """The governor's one-shot psutil reading plus the dispatch start clock the receipt elapses against.

    `_admit` mints it before admission and `_exec` stamps the same `cpu_percent` / `memory_rss_mb` it gated
    on into the receipt without re-reading the process. `load1` rides the one-minute load average where the
    platform exposes `psutil.getloadavg` (absent on a load-average-free host); it is a structlog fact the
    fire emits, never a receipt slot.
    """

    cpu_percent: float
    memory_rss_mb: float
    started: float
    load1: Option[float] = Nothing


# --- [SERVICES] ------------------------------------------------------------------------

_LOGGER: Final = structlog.get_logger("maghz.automation")
# The one `drained`-egress redaction the daemon `feed` legs share: drop the RSS byte slot the `@drained`
# aspect probes so it never reaches the line. Minted once (`feed` types its `redaction` as the normalized
# `Redaction`, not the bare drop-set the `@drained` decorator admits), so the two daemon lanes name the
# dropped field one way.
_REDACTION: Final[Redaction] = Redaction.of(frozenset({"rss_bytes"}))


# --- [OPERATIONS] ----------------------------------------------------------------------


def decode_spec(type_: type[AutomationSpec], tokens: Sequence[Token]) -> AutomationSpec:  # noqa: ARG001 - `type_` is the cyclopts converter contract positional bound by the framework
    """Admission boundary: decode the `--spec` token into a typed spec and validate its lane.

    The cyclopts `Parameter(converter=...)` shim and the engine's one public symbol the CLI binds. cyclopts
    invokes the converter with `(type, tokens)` where each element is a `cyclopts.Token` carrying the raw
    payload on `.value`; the stateful `_SPEC_DECODER` resolves both tagged unions over that value in one pass.
    A `msgspec.DecodeError` / `ValidationError` or a `lane` outside `cfg.automation.lane_keys` raises the
    converter-canonical `ValueError`, which cyclopts wraps into a context-rich `CoercionError` so the unknown
    lane is rejected at admission rather than silently coerced to `"default"`. The CLI `main()` boundary
    catches that `CycloptsError` and folds it to a `Status.FAULTED` envelope (exit 2).

    Args:
        type_: The annotated target type cyclopts passes; always `AutomationSpec`.
        tokens: The `--spec` argument tokens cyclopts binds; exactly one `Token` whose `.value` is the
            JSON payload.

    Returns:
        The decoded, lane-validated `AutomationSpec`.

    Raises:
        ValueError: The payload is malformed JSON, fails struct validation, or names a lane outside the
            configured `lane_keys`; cyclopts wraps it into the `--spec` `CoercionError` at the CLI edge.
    """
    raw = tokens[-1].value
    try:
        spec = _SPEC_DECODER.decode(raw.encode())
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        msg = f"spec decode: {exc}"
        raise ValueError(msg) from exc
    if spec.lane not in settings().automation.lane_keys:
        msg = f"unknown lane: {spec.lane}"
        raise ValueError(msg)
    return spec


def _admit(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy) -> _Admission:
    """The pre-borrow governor rail: snapshot psutil, return `Error(Gate)` over-ceiling or saturated, else `Ok`.

    One `Process(os.getpid()).oneshot()` batch reads `cpu_percent(interval=None)` (the load since the prior
    call, non-blocking — the engine's debounce and cron tick own the cadence) and `memory_info().rss` in one
    syscall; `getloadavg` rides `Option.of_optional(getattr(...))` so a load-average-free host yields `Nothing`
    rather than a branch. A CPU or RSS reading above `cfg.automation.cpu_ceil` / `rss_ceil_mb` returns
    `Error(Gate(OVER_CEILING))`; a lane shedding load with no free token (`available_tokens == 0`) returns
    `Error(Gate(SATURATED))` — both BEFORE the caller borrows a `LanePolicy.drain` token, so a gated admission
    never enters the drain lifecycle, never writes a job row, and never appends a ledger line. `Ok(snapshot)`
    carries the reading `_exec` stamps into the receipt, so the admission gate and the receipt fields never
    diverge. A `Gate` is a deliberate non-failure distinct from a `BoundaryFault` operational breach: it never
    enters the boundary rail.

    Args:
        spec: The validated spec whose fire this gates; supplies the gate's `spec_id`.
        cfg: The validated settings owning the CPU/RSS ceilings.
        policy: The `LanePolicy` whose free-token count the saturation shed reads.

    Returns:
        `Ok(_Snapshot)` admitting the fire with the gated reading, or `Error(Gate)` for a denied admission.
    """
    process = psutil.Process(os.getpid())
    with process.oneshot():
        cpu = process.cpu_percent(interval=None)
        rss_mb = process.memory_info().rss / (1024 * 1024)
    load1 = Option.of_optional(getattr(psutil, "getloadavg", None)).map(lambda fn: fn()[0])
    snapshot = _Snapshot(cpu_percent=cpu, memory_rss_mb=rss_mb, started=time.monotonic(), load1=load1)
    if cpu > cfg.automation.cpu_ceil or rss_mb > cfg.automation.rss_ceil_mb:
        return Error(Gate(reason=GateReason.OVER_CEILING, spec_id=spec.id, detail=f"cpu={cpu:.1f}% rss={rss_mb:.0f}MB"))
    if policy.available_tokens == 0:
        return Error(Gate(reason=GateReason.SATURATED, spec_id=spec.id, detail=f"lane {spec.lane!r} saturated"))
    return Ok(snapshot)


def _work_of(spec: AutomationSpec, cfg: MaghzSettings, snapshot: _Snapshot, facts: dict[str, object]) -> Admit:
    """Build one governed `Admit.guarded` unit: a transient-retried fire scoping its per-fire structlog facts.

    `Admit.guarded(RetryClass.HTTP, work)` so a transient retries under the canonical stamina row; the `work`
    thunk closes over the gated `snapshot` (which `_exec` stamps into the receipt) and the `facts` the lane
    contributed (the change set, the cron tick, or empty for the manual one-shot), binding them on the structlog
    contextvars for the fire's duration. The one unit constructor both the daemon `build` projector and the
    manual one-shot drain admit, so the governed fire shape lives once.

    Returns:
        The `Admit.guarded` unit the lane drains.
    """
    bound = facts | {"spec_id": spec.id, "action": spec.action.__struct_config__.tag, "lane": spec.lane} | snapshot.load1.map(
        lambda load: {"load1": load}
    ).default_value({})

    async def work() -> RuntimeRail[AutomationReceipt]:
        with structlog.contextvars.bound_contextvars(**bound):
            return await _exec(spec.action, spec, cfg, snapshot)

    return Admit.guarded(RetryClass.HTTP, work)


def _govern(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, facts: dict[str, object], tg: TaskGroup) -> Block[Admit]:
    """The pure `build` projector both daemon sources share: govern admission, emit the governed `Block[Admit]`.

    One `_admit` rail per fire: `Ok(snapshot)` builds the governed singleton through `_work_of`; `Error(gate)`
    schedules the skip-ledger onto the running `drive` task group (the sync projector runs on the loop thread
    inside `feed`'s generator, so it cannot await — `tg.start_soon` defers the async append without blocking)
    and returns `Block.empty()` so the shared `feed` tail's `policy.drain` borrows no token for a gated tick. A
    `Gate` cannot ride `feed`'s `DrainReceipt` channel, so the daemon's gated tick is a logged and ledgered skip
    the running summary absorbs rather than a per-tick envelope; the watch and schedule daemons differ only by
    the `facts` the source event carries, never a duplicated drain or receipt egress.

    Args:
        spec: The spec whose single action each governed fire dispatches.
        cfg: The validated settings owning the ceilings, timeout, and ledger path.
        policy: The `LanePolicy` whose token the governed fire borrows.
        facts: The per-fire structlog facts the daemon source event contributed (the change set or the cron tick).
        tg: The `drive` task group a gated tick's skip-ledger is scheduled onto.

    Returns:
        A governed singleton `Block[Admit]` on admission, or `Block.empty()` on a gated tick (skip scheduled).
    """
    match _admit(spec, cfg, policy):
        case Result(tag="ok", ok=snapshot):
            return Block.singleton(_work_of(spec, cfg, snapshot, facts))
        case Result(error=gate):
            tg.start_soon(_ledger_skip, spec, cfg, gate.detail)
            return Block.empty()


def _fold(spec: AutomationSpec, cfg: MaghzSettings, receipt: DrainReceipt[object]) -> _DispatchOutcome:
    """Project one live-fire substrate `DrainReceipt` to the outcome — value, fault, or contained-deadline leaf.

    Because every action arm rides `RuntimeRail[AutomationReceipt]` (the SAME `BoundaryFault` the drain's typed
    `faults` block carries), the drain is lossless: a completed fire's `values[0]` narrows to the receipt, a
    surviving `BoundaryFault` rides `faults[0]`, read straight off the drain with no sink cell, no cast, and no
    fault re-lift. An empty drain (no value, no fault) on a unit that went live is the `LanePolicy.deadline` trip
    the substrate contains as a `cancelled` count; the engine folds it to the one `BoundaryFault.deadline` leaf
    naming the spec and the elapsed budget. Only called on a receipt that admitted a fire (`accepted > 0`) — a
    gated daemon tick's empty batch is filtered at the lane loop, already ledgered as a skip, and never folds to
    a spurious deadline.

    Args:
        spec: The fired spec supplying the deadline leaf's subject.
        cfg: The validated settings owning the action timeout the deadline leaf names.
        receipt: The substrate drain receipt whose `values`/`faults` this folds (one admitted fire).

    Returns:
        `Ok(AutomationReceipt)` on a completed fire, or `Error(BoundaryFault)` carrying the action arm's fault
        or the contained-deadline leaf.
    """
    fired: Option[RuntimeRail[AutomationReceipt]] = receipt.values.try_head().map(lambda value: Ok(_as_receipt(value)))
    failed = receipt.faults.try_head().map(Error)
    deadline: RuntimeRail[AutomationReceipt] = Error(BoundaryFault(deadline=(spec.id, cfg.automation.action_timeout_s)))
    return fired.default_with(lambda: failed.default_value(deadline))


def _as_receipt(value: object) -> AutomationReceipt:
    """Narrow one concept-agnostic drain value to the engine's receipt at the `object`-rail boundary.

    The lane carries `Block[object]` by design (`drain` is concept-agnostic, `Work`/`Admit` erase the value
    type to admit any concrete `Work[_T]` by return-covariance, so the consumer narrows at its own boundary);
    every value the engine's `work` admits is an `AutomationReceipt` by construction, so this is the single
    narrowing seam the fold reads the typed receipt back through.

    Returns:
        The value typed as `AutomationReceipt`.
    """
    assert isinstance(value, AutomationReceipt)  # noqa: S101 - the drain value is an AutomationReceipt by construction; the lane erases the type to `object`
    return value


async def _exec(action: Action, spec: AutomationSpec, cfg: MaghzSettings, snapshot: _Snapshot) -> RuntimeRail[AutomationReceipt]:
    """Resolve one action under the total `AgentAction | Notify | Embed | Sync` match; one receipt per arm.

    `AgentAction` reads `_AGENT_DISPATCH[action.skill](action, spec, cfg)` — the engine is skill-agnostic and
    never decodes `action.params`. `Notify` emits to structlog and carries no rows. `Embed` calls
    `maghz.embed_enqueue()` / `maghz.embed_drain()` via `db.query`, mapping `concept=None` to the sweep-all
    path and `Some(name)` to a single-concept enqueue. `Sync` dispatches to `sync.run(cfg, concept=...)` and
    reads `SyncDetail.drift` off the returned `RuntimeRail[Envelope]`. Each arm rides the substrate
    `RuntimeRail[AutomationReceipt]`, so a boundary fault is a `BoundaryFault` leaf the drain carries
    losslessly. The governor `snapshot` rides the signature, so each engine-owned arm stamps the gated reading
    into its receipt directly rather than threading a process-global cell.

    Args:
        action: The action leaf to resolve; the match is exhaustive over the closed union.
        spec: The owning spec, supplying the receipt's identity and lane.
        cfg: The validated settings owning the DSN and rail reach.
        snapshot: The governor reading the receipt stamps so the gate and the receipt never diverge.

    Returns:
        `Ok(AutomationReceipt)` fully populated for the arm, or `Error(BoundaryFault)` from the arm body.
    """
    match action:
        case AgentAction(skill=skill):
            return await _AGENT_DISPATCH[skill](action, spec, cfg)
        case Notify(channel=channel, message=message):
            await _LOGGER.ainfo("automation.notify", channel=channel, message=message)
            return Ok(_receipt(spec, Some(snapshot)))
        case Embed(concept=concept):
            return await _embed(spec, cfg, snapshot, Option.of_optional(concept))
        case Sync(concept=concept):
            return await _sync(spec, cfg, snapshot, concept)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Action union
            assert_never(unreachable)


async def _embed(spec: AutomationSpec, cfg: MaghzSettings, snapshot: _Snapshot, concept: Option[str]) -> RuntimeRail[AutomationReceipt]:
    """Drive the in-DB embed pipeline via `db.query`; `Nothing` sweeps all pending, `Some(name)` enqueues one.

    The sweep path enqueues a fresh batch and drains the prior tick's responses in one round-trip; the
    single-concept path filters the enqueue to one `canonical_name` against the `concept_embed_pending_idx`
    partial index. `concept` arity discriminates the one `db.query` call — `Some(name)` binds the named `:name`
    placeholder directly (the canonical keyword form, never a `**dict` spread that races the `exec` keyword),
    `Nothing` runs the parameter-free sweep — so the DB owns the embed protocol and the engine composes the two
    routine calls, reading the enqueued count into `rows_affected`. `db.query` returns `RuntimeRail[QueryResult]`
    directly — the `BoundaryFault` lift already happened once inside `db.py` — so a DB fault propagates in place
    on the `Error` arm with no re-lift, the canonical `guard(RetryClass.DB)` retry seam having already replayed
    any transient.

    Args:
        spec: The owning spec supplying the receipt identity and lane.
        cfg: The validated settings owning the DSN.
        snapshot: The governor reading the receipt stamps.
        concept: `Nothing` sweeps every pending concept; `Some(name)` enqueues that one concept.

    Returns:
        `Ok(AutomationReceipt)` carrying the enqueued count in `rows_affected`, or the `db.query`
        `Error(BoundaryFault)` propagated unchanged.
    """

    def _enqueued(result: QueryResult) -> int:
        head = result.rows[0] if result.rows else ()
        return int(head[0]) if head and head[0] is not None else 0

    match concept:
        case Option(tag="some", some=name):
            sql = "select maghz.embed_enqueue() as enqueued where exists (select 1 from concept where canonical_name = :name)"
            queried = await db.query(sql, cfg, name=name)
        case _:
            queried = await db.query("select maghz.embed_enqueue() + maghz.embed_drain() as enqueued", cfg)
    return queried.map(lambda result: _receipt(spec, Some(snapshot), rows_affected=_enqueued(result)))


async def _sync(spec: AutomationSpec, cfg: MaghzSettings, snapshot: _Snapshot, concept: str | None) -> RuntimeRail[AutomationReceipt]:
    """Dispatch the Heptabase sync rail by `concept` arity and read `SyncDetail.drift` into the receipt.

    `None` selects DIFF (`sync.run(cfg, concept=None)`), a name selects GENERATE (`sync.run(cfg, concept=name)`)
    — the canonical single entrypoint; no `sync_diff` / `sync_generate` aliases exist. The rail returns the
    domain `RuntimeRail[Envelope]`; the `Ok` arm narrows the envelope's `report.detail` to a `SyncDetail` in the
    match itself, so the typed `drift: int` flows into `rows_affected` without an untyped read, and any
    non-`SyncDetail` detail yields no count. A boundary fault propagates in place — `sync.run` already mints its
    `BoundaryFault` carrier-free (its DB and `runtime.spawn` legs lift once), so the engine re-lifts nothing.

    Args:
        spec: The owning spec supplying the receipt identity and lane.
        cfg: The validated settings owning the DSN and Heptabase reach.
        snapshot: The governor reading the receipt stamps.
        concept: `None` runs DIFF; a `canonical_name` runs GENERATE for that concept.

    Returns:
        `Ok(AutomationReceipt)` with `SyncDetail.drift` in `rows_affected`, or the `sync.run`
        `Error(BoundaryFault)` propagated unchanged.
    """
    from admin.rails.sync import run as sync_run, SyncDetail  # noqa: PLC0415 - deferred: breaks the rails.__init__ import cycle

    match await sync_run(cfg, concept=concept):
        case Result(tag="ok", ok=Envelope(report=Report(detail=SyncDetail(drift=drift)))):
            return Ok(_receipt(spec, Some(snapshot), rows_affected=drift))
        case Result(tag="ok"):
            return Ok(_receipt(spec, Some(snapshot)))
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _agent_pending(action: AgentAction, spec: AutomationSpec, _cfg: MaghzSettings) -> RuntimeRail[AutomationReceipt]:  # noqa: RUF029 - the `_AGENT_DISPATCH` `Work` contract is async; the placeholder matches it until the skill counterpart lands
    """The `_AGENT_DISPATCH` placeholder until the `integrations`/`mcp` skill counterparts land each row.

    The engine ships the table SHAPE — one row per `AgentSkill` — and the skill blueprints ship the real
    callables with the contract `(action, spec, cfg) -> RuntimeRail[AutomationReceipt]`. Until a skill's row is
    replaced, it returns `Error(BoundaryFault(api=...))` naming the unrouted skill — the deterministic `api`
    leaf (a contract gap, not a retryable resource), so the table stays total over the closed `AgentSkill` and
    an unrouted skill faults loud rather than silently no-op'ing.

    Args:
        action: The agent action whose skill row has no counterpart yet.
        spec: The owning spec supplying the fault subject.
        _cfg: The validated settings (unused until the real skill callable composes the DB/MCP reach).

    Returns:
        `Error(BoundaryFault(api=(spec.id, …)))` naming the unrouted skill.
    """
    return Error(BoundaryFault(api=(spec.id, f"no dispatch for skill {action.skill.value}")))


def _receipt(
    spec: AutomationSpec,
    snapshot: Option[_Snapshot],
    *,
    rows_affected: int | msgspec.UnsetType = msgspec.UNSET,
    job_id: str | msgspec.UnsetType = msgspec.UNSET,
) -> AutomationReceipt:
    """Build the one engine receipt for a spec; `snapshot` presence is the fire/skip discriminant.

    `Some(snapshot)` is a real fire: `attempt=1`, `elapsed_ms` measures from the governor's monotonic
    `started`, and `cpu_percent` / `memory_rss_mb` are the same numbers the admission gate read (the governor
    and receipt never diverge). `Nothing` is a gated or missed tick with no governor reading: `attempt=0`,
    `elapsed_ms=0.0`, and the snapshot slots ride `msgspec.UNSET` so they encode ABSENT on the ledger wire
    rather than `null`. This is the sole `AutomationReceipt` constructor — fire and skip route through one owner
    rather than two parallel literals — and the mode-divergent slots default to `UNSET` at the model, so the
    engine-owned arms simply omit `agent_skill` and the skip path omits the snapshot rather than threading a
    `None` the wire would render.

    Args:
        spec: The spec supplying `spec_id`, the trigger/action tags, and the lane.
        snapshot: `Some(_Snapshot)` for a fire (the governor reading and monotonic start), `Nothing` for a
            gated/missed tick that carries no reading.
        rows_affected: The action's row count (Sync drift, Embed enqueue), or `UNSET` when the arm carries none.
        job_id: The agent job id, or `UNSET` for the engine-owned arms.

    Returns:
        The `AutomationReceipt`: snapshot/elapsed on a fire, zeroed with absent snapshot slots on a skip.
    """
    return AutomationReceipt(
        spec_id=spec.id,
        trigger_tag=tag_of(spec.trigger, TriggerTag),
        action_tag=tag_of(spec.action, ActionTag),
        lane=spec.lane,
        fired_at=datetime.now(UTC).isoformat(),
        attempt=1 if snapshot.is_some() else 0,
        elapsed_ms=snapshot.map(lambda snap: (time.monotonic() - snap.started) * 1000.0).default_value(0.0),
        rows_affected=rows_affected,
        job_id=job_id,
        cpu_percent=snapshot.map(lambda snap: snap.cpu_percent).default_value(msgspec.UNSET),
        memory_rss_mb=snapshot.map(lambda snap: snap.memory_rss_mb).default_value(msgspec.UNSET),
    )


async def _record_ledger(values: Block[object], cfg: MaghzSettings) -> None:
    """Append the head `AutomationReceipt` to the NDJSON ledger as one `encode`-then-write per fire.

    `values.try_head()` is the inner receipt; only a completed fire (or a deliberately-ledgered skip) carries
    one, so an empty/faulted drain writes nothing. The block is the concept-agnostic drain `values`
    (`Block[object]`); its head is an `AutomationReceipt` by construction and `msgspec.json.encode` projects any
    struct, so no narrow is needed for the byte sink. The blocking append is offloaded through
    `anyio.to_thread.run_sync(fn, limiter=)` under anyio's default thread limiter so the event loop stays
    responsive. This is the one ledger sink: a fire's receipt rides the drain's `values`, and a missed-tick skip
    wraps its lone `_receipt` in a singleton `Block` so both fire and skip share one offloaded append.

    Args:
        values: The value block whose head is appended; the drain's `values` on a fire, a singleton skip
            receipt on a missed tick.
        cfg: The validated settings owning the NDJSON ledger path.
    """
    head = values.try_head()
    if head.is_none():
        return
    line = msgspec.json.encode(head.value) + b"\n"
    path = cfg.automation.ledger_file

    def _append() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(line)

    await anyio.to_thread.run_sync(_append, limiter=anyio.to_thread.current_default_thread_limiter())


async def _ledger_skip(spec: AutomationSpec, cfg: MaghzSettings, detail: str) -> None:
    """Append a `Status.SKIP` receipt to the NDJSON ledger for a gated or missed tick (no governor snapshot).

    A missed schedule tick or a saturated cycle produces no governor reading, so `_receipt` mints the skip shape
    from `Nothing`: `attempt=0`, `elapsed_ms=0.0`, absent snapshot fields, while still recording the spec
    identity and skip detail so an agent reads saturation and misfire trends off the ledger. Reuses
    `_record_ledger`'s offloaded append by wrapping the lone receipt in a singleton `Block`.

    Args:
        spec: The spec whose gated/missed tick is recorded.
        cfg: The validated settings owning the NDJSON ledger path.
        detail: The skip reason carried as a structlog note alongside the receipt.
    """
    await _LOGGER.ainfo("automation.skip", spec_id=spec.id, detail=detail)
    await _record_ledger(Block.singleton(_receipt(spec, Nothing)), cfg)


# --- [TABLES] --------------------------------------------------------------------------

# Stateful spec decoder, resolved once at import: both tagged unions (`type` for Trigger, `kind` for Action)
# resolve in one pass. `decode_spec` is the only caller, lifting a decode/validation escape to a `ValueError`
# cyclopts wraps into the `--spec` `CoercionError` at the admission boundary.
_SPEC_DECODER: Final[msgspec.json.Decoder[AutomationSpec]] = msgspec.json.Decoder(type=AutomationSpec)

# The `watch.filter` literal -> its `watchfiles` `BaseFilter`. `default` ships the dotfile/VCS/build ignore
# set, `python` narrows to Python-source changes, `none` keeps every change (a raw keep-all `BaseFilter`). A
# data row per literal, total over the closed `Watch.filter` set, so the watch `build` projector reads one
# filter off `_WATCH_FILTER[watch.filter]` rather than an `if`-ladder over the three modalities.
_WATCH_FILTER: Final[frozendict[Literal["default", "python", "none"], BaseFilter]] = frozendict({
    "default": DefaultFilter(),
    "python": PythonFilter(),
    "none": BaseFilter(),
})

# AgentSkill -> skill-dispatch callable, the keyed correspondence table. Each callable is owned by the
# `integrations`/`mcp` blueprints with contract `(action, spec, cfg) -> RuntimeRail[AutomationReceipt]`; the
# engine is skill-agnostic and never decodes `action.params`. Adding a skill is one `AgentSkill` member plus
# one row here — the `AgentAction` arm in `_exec` is untouched. Until the skill counterparts land, each row
# resolves to `_agent_pending`, which returns `Error(BoundaryFault(api=...))` so the table is total over the
# closed `AgentSkill`.
_AGENT_DISPATCH: Final[frozendict[AgentSkill, Work]] = frozendict(dict.fromkeys(AgentSkill, _agent_pending))


# --- [LANES] ---------------------------------------------------------------------------


async def _manual_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, _tg: TaskGroup) -> _DispatchOutcome:
    """Manual trigger lane: govern admission, drain one governed batch, and fold the receipt to the outcome.

    The one-shot path — no daemon source, no `feed`, no signal lane (`drive` spawns the signal lane only for
    the `watch`/`schedule` daemon tags), so it awaits its own skip-ledger directly rather than scheduling it on
    the group. `_admit` gates the fire; `Error(gate)` ledgers the skip and surfaces the `Gate` so the CLI shows
    the gating reason at `Status.SKIP`. `Ok(snapshot)` drains the one governed `Admit.guarded` batch (the same
    `_work_of` unit the daemon projector builds) off the substrate `drain` under the lane's
    `deadline=Some(action_timeout_s)`, then `_fold` reads the `DrainReceipt` (value / fault / contained-deadline)
    and the inner receipt is ledgered.

    Args:
        spec: The spec carrying the `Manual` trigger and the action to fire once.
        cfg: The validated settings owning the lane capacity, the action timeout, and the ledger path.
        policy: The `LanePolicy` for the spec's lane (deadline-bounded by `drive`).
        _tg: The `drive` task group (unused — the one-shot awaits its own skip-ledger directly).

    Returns:
        The single dispatch outcome — `Ok(receipt)` / `Error(BoundaryFault)` for the fire, or the `Gate` skip.
    """
    match _admit(spec, cfg, policy):
        case Result(error=gate):
            await _ledger_skip(spec, cfg, gate.detail)
            return gate
        case Result(ok=snapshot):
            receipt = await drain(policy, Block.singleton(_work_of(spec, cfg, snapshot, {})))
            await _record_ledger(receipt.values, cfg)
            return _fold(spec, cfg, receipt)


async def _watch_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, tg: TaskGroup) -> _DispatchOutcome:
    """Watch trigger lane: compose the substrate `feed` over a `LaneSource.on_change` watched source.

    Every `Watch.path` is validated with `anyio.Path(p).exists()` before the feed starts; a missing path
    returns `Error(BoundaryFault(resource=...))` so a VPS path the service account cannot reach fails loud (a
    re-reachable mount is the retryable `resource` leaf). `feed` owns the `watchfiles.awatch` stream (filtered
    by `_WATCH_FILTER[watch.filter]`), the `@drained` receipt egress, and the per-batch `policy.drain`; the
    `_watch_build` projector governs admission and emits the governed `Block[Admit]` carrying the change set as
    structlog facts. The lane consumes every observed `DrainReceipt` to drive the per-batch fire and ledger,
    folding the last batch's outcome so a one-shot watch surfaces a receipt; a daemon watch loops until the
    signal lane cancels the group, which closes the `feed` generator.

    Args:
        spec: The spec carrying the `Watch` trigger and the action to fire per batch.
        cfg: The validated settings owning the lane capacity and ledger path.
        policy: The `LanePolicy` for the spec's lane (deadline-bounded by `drive`).
        tg: The `drive` task group a gated tick's skip-ledger is scheduled onto.

    Returns:
        The last batch's folded outcome, or `Error(BoundaryFault)` when a watched path is unreachable.
    """
    watch = spec.trigger
    assert isinstance(watch, Watch)  # noqa: S101 - the watch lane is selected only for the Watch arm in drive
    for path in watch.paths:
        if not await anyio.Path(path).exists():
            return Error(BoundaryFault(resource=(spec.lane, f"path not found: {path}")))

    def _watch_build(batch: set[tuple[Change, str]]) -> Block[Admit]:
        facts: dict[str, object] = {"changes": tuple(f"{change.raw_str()}:{target}" for change, target in batch)}
        return _govern(spec, cfg, policy, facts, tg)

    source = LaneSource.on_change(watch.paths, _watch_build, watch_filter=_WATCH_FILTER[watch.filter])
    outcome: _DispatchOutcome = Error(BoundaryFault(resource=(spec.lane, "no change observed")))
    async for receipt in feed(policy, source, "automation", _REDACTION):
        if receipt.accepted == 0:  # a gated batch admitted no fire; its skip is already ledgered on the group
            continue
        await _record_ledger(receipt.values, cfg)
        outcome = _fold(spec, cfg, receipt)
    return outcome


async def _schedule_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, tg: TaskGroup) -> _DispatchOutcome:
    """Schedule trigger lane: compose the substrate `feed` over a `LaneSource.on_schedule` cron source.

    `feed` owns the one apscheduler 4.x `AsyncScheduler` lifecycle, the `subscribe(JobReleased)` fire-seam over
    a bounded stream, the `@drained` egress, and the per-fire `policy.drain`; the `_schedule_build` projector
    grades each `JobReleased` and either governs a real fire or schedules a `missed_start_deadline` skip-ledger
    onto the group, emitting the governed `Block[Admit]` (empty on a missed tick). `CronTrigger.from_crontab(cron, timezone=)`
    carries the cron expression. The lane runs until the signal lane cancels the group, which closes the `feed`
    generator and exits the scheduler context; the returned `Error(BoundaryFault)` names only the unreachable
    no-fire exit.

    Args:
        spec: The spec carrying the `Schedule` trigger and the action to fire each tick.
        cfg: The validated settings owning the lane capacity and ledger path.
        policy: The `LanePolicy` for the spec's lane (deadline-bounded by `drive`).
        tg: The `drive` task group a missed/gated tick's skip-ledger is scheduled onto.

    Returns:
        The last tick's folded outcome, or `Error(BoundaryFault(resource=...))` when the feed unwinds with no fire.
    """
    schedule = spec.trigger
    assert isinstance(schedule, Schedule)  # noqa: S101 - the schedule lane is selected only for the Schedule arm in drive

    def _schedule_build(event: JobReleased) -> Block[Admit]:
        if event.outcome is JobOutcome.missed_start_deadline:
            tg.start_soon(_ledger_skip, spec, cfg, f"missed schedule tick at {event.scheduled_start}")
            return Block.empty()
        return _govern(spec, cfg, policy, {"scheduled_start": str(event.scheduled_start)}, tg)

    trigger = CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone)
    source = LaneSource.on_schedule(trigger, _schedule_build)
    outcome: _DispatchOutcome = Error(BoundaryFault(resource=(spec.lane, "scheduler stopped")))
    async for receipt in feed(policy, source, "automation", _REDACTION):
        if receipt.accepted == 0:  # a gated/missed tick admitted no fire; its skip is already ledgered on the group
            continue
        await _record_ledger(receipt.values, cfg)
        outcome = _fold(spec, cfg, receipt)
    return outcome


async def _signal_lane(tg: TaskGroup) -> None:
    """Signal lane: await the first `SIGTERM`/`SIGINT` and cancel the task group for a clean daemon exit.

    `anyio.open_signal_receiver` installs the handlers for the duration of the receiver scope; the first signal
    cancels the whole `drive` task group so the `feed` generator closes (its `awatch`/`AsyncScheduler` context
    exits) and one summary envelope reaches stdout with exit 0. Present only for daemon modes.

    Args:
        tg: The `drive` task group cancelled on the first received signal.
    """
    with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as receiver:
        async for _signum in receiver:
            tg.cancel_scope.cancel()
            return


# --- [TABLES] --------------------------------------------------------------------------

# TriggerTag -> its lane builder. `manual` drains one governed batch directly; `watch`/`schedule` compose the
# substrate `feed` daemon alongside the caller-spawned signal lane. The key set equals `TriggerTag` exactly, so
# `drive`'s `_LANE[tag]` subscription is total — a new trigger modality is one `TriggerTag` member plus one row
# here, never a `match`/`assert_never` ladder over an already-exhaustive table.
_LANE: Final[frozendict[TriggerTag, _LaneBuilder]] = frozendict({
    "manual": _manual_lane,
    "watch": _watch_lane,
    "schedule": _schedule_lane,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def drive(spec: AutomationSpec, cfg: MaghzSettings) -> Envelope:
    """The single polymorphic automation entrypoint: one task group per call, projected to one `Envelope`.

    `tag_of(spec.trigger, TriggerTag)` keys the `_LANE` table the spec fires under one
    `anyio.create_task_group`: `manual` drains once immediately, `watch`/`schedule` start `_signal_lane` into
    the group and compose the substrate `feed` daemon so a `SIGTERM` cancels the group cleanly. A crashing lane's
    `ExceptionGroup` is caught with `except*` and folded to one `BoundaryFault.of` leaf naming the lane. The
    dispatch `_DispatchOutcome` projects exactly once here: `Ok(receipt)` lifts to `completed(Status.OK, …)`, a
    `Gate` projects through `gate.envelope()` (`Status.SKIP`), and an `Error(BoundaryFault)` lowers through the
    substrate `BoundaryFault.headline()`/`facts()` cause-naming — the engine never raises into the CLI and mints
    no parallel fault carrier. The per-lane `LanePolicy(capacity=max_concurrent, deadline=Some(action_timeout_s))`
    shares the substrate-memoised `CapacityLimiter` keyed on its frozen identity and pushes the per-fire deadline
    onto the lane so the drain contains a deadline trip as a `cancelled` count; `spec.lane` (already validated at
    `decode_spec`) selects the canonical lane the table indexes total.

    Args:
        spec: The validated, lane-checked spec pairing one trigger with one action.
        cfg: The validated settings owning the lane capacity, ceilings, timeout, and ledger path.

    Returns:
        One `Envelope`: `Status.OK` carrying the `AutomationReceipt` on a successful fire, `Status.SKIP` for a
        gated admission or missed tick, or `Status.FAULTED` for a boundary breach.
    """
    policy = LanePolicy(capacity=cfg.automation.max_concurrent, deadline=Some(cfg.automation.action_timeout_s))
    tag = tag_of(spec.trigger, TriggerTag)
    outcome: _DispatchOutcome
    try:
        async with anyio.create_task_group() as tg:
            if tag != "manual":
                tg.start_soon(_signal_lane, tg)
            outcome = await _LANE[tag](spec, cfg, policy, tg)
            tg.cancel_scope.cancel()
    except* Exception as group:  # noqa: BLE001 - the lane ExceptionGroup folds to one BoundaryFault rail
        detail = BaseException("; ".join(str(exc) for exc in group.exceptions))
        outcome = Error(BoundaryFault.of(spec.lane, detail))
    match outcome:
        case Gate() as gate:
            return gate.envelope()
        case Result(tag="ok", ok=receipt):
            return completed(Status.OK, receipt)
        case Result(error=boundary_fault):
            return fault(boundary_fault.headline(), {key: str(value) for key, value in boundary_fault.facts().items()})
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed _DispatchOutcome union
            assert_never(unreachable)
