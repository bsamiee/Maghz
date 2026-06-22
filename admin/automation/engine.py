"""Automation engine: the single polymorphic `drive` over one task group, lane drain, and governor.

`drive(spec, cfg)` is the sole entrypoint and the sole `Envelope` projection edge. It opens exactly
one `anyio.create_task_group` per call; `_resolve_trigger` (total `match` + `assert_never`) selects
the lane the spec fires — `_watch_lane` (`watchfiles.awatch` async generator gated by the engine's
own `anyio.Event` stop event), `_schedule_lane` (one `async with AsyncScheduler()` whose `subscribe`
hook is the single NDJSON observability seam and whose `JobOutcome` projects each tick), or the
`Manual` one-shot that dispatches immediately — while `_signal_lane` (`anyio.open_signal_receiver`
over `SIGTERM`/`SIGINT`) cancels the group on the first signal so a daemon exits with one summary
envelope. A crashing lane's `ExceptionGroup` is caught with `except*` and folded to `trigger_spawn`.

Every fire flows through `_dispatch_action`, whose cross-cutting concerns stack outer-to-inner as the
runtime substrate prescribes: `@_governor_aspect` (the psutil admission gate) runs OUTERMOST and
returns `Error(admission_denied)` / `Error(lane_overflow)` BEFORE any lane token is borrowed, then
`@drained` emits the `DrainReceipt` from the one `LanePolicy.drain(Block.of_seq([Admit.retried(...)]))`
borrow, then `bound_contextvars` scopes the structlog facts, then `move_on_after` deadlines the
`_exec` body. `_exec` (total `match` + `assert_never`) owns all four action arms and returns one
fully-populated `AutomationReceipt`; the governor snapshot rides a `ContextVar` into it so the
decorator stays signature-preserving. `AutomationFault` is the domain-internal rail from `_exec` to
`drive`; `_fault_envelope` folds it to the stdout `Envelope` exactly once, at this edge, never raising
into the CLI. The runtime owners (`drain`/`Admit`/`DrainReceipt`/`LanePolicy` from `lanes`, `guard`
from `resilience`, `@drained` from `receipts`, `RuntimeRail`/`BoundaryFault` from `rails`) and the
consumed rails (`sync.run`, `db.query`, the `_AGENT_DISPATCH` skill callables) are composed, never
re-declared. `_WATCH_FILTER` / `_AGENT_DISPATCH` / `_LANE_POLICIES` are the three correspondence
tables; the engine is skill-agnostic and reads `_AGENT_DISPATCH[action.skill](action, spec, cfg)`.
"""

from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from datetime import datetime, UTC
import os
import signal
import time
from types import MappingProxyType
from typing import assert_never, Final, Literal

import anyio
from anyio.abc import TaskGroup
import anyio.to_thread
from apscheduler import AsyncScheduler, ConflictPolicy, JobOutcome, JobReleased
from apscheduler.triggers.cron import CronTrigger
from cyclopts import Token
from expression import Error, Nothing, Ok, Option, Result, Some
from expression.collections import Block, Map
import msgspec
import psutil
import structlog
from watchfiles import awatch, BaseFilter, DefaultFilter, PythonFilter

from admin import db
from admin.automation.model import (
    Action,
    ActionTag,
    AgentAction,
    AgentSkill,
    AutomationFault,
    AutomationReceipt,
    AutomationSpec,
    Embed,
    Manual,
    Notify,
    Schedule,
    Sync,
    Trigger,
    TriggerTag,
    Watch,
)
from admin.core import completed, Envelope, fault, Report, Status
from admin.db import QueryResult
from admin.runtime import Admit, BoundaryFault, drain, DrainReceipt, LanePolicy, RetryClass, RuntimeRail
from admin.runtime.receipts import drained
from admin.settings import MaghzSettings, settings


# --- [TYPES] ---------------------------------------------------------------------------

type Work = Callable[[AgentAction, AutomationSpec, MaghzSettings], Awaitable[Result[AutomationReceipt, AutomationFault]]]
type _Dispatch = Callable[[AutomationSpec, MaghzSettings, LanePolicy], Awaitable[Result[AutomationReceipt, AutomationFault]]]


# --- [MODELS] --------------------------------------------------------------------------


class _Snapshot(msgspec.Struct, frozen=True, gc=False):
    """The governor's one-shot psutil reading plus the dispatch start clock the receipt elapses against.

    `_governor_aspect` mints it before admission and binds it on `_GOVERNOR` so `_exec` stamps the
    same `cpu_percent` / `memory_rss_mb` it gated on into the receipt without re-reading the process.
    """

    cpu_percent: float
    memory_rss_mb: float
    started: float


# --- [SERVICES] ------------------------------------------------------------------------

_LOGGER: Final = structlog.get_logger("maghz.automation")
# The governor snapshot for the in-flight dispatch. `_governor_aspect` is the sole writer (one set per
# `_dispatch_action` call); `_exec` is the sole reader, stamping the gated reading into the receipt so
# the admission gate and the receipt fields never diverge and the decorator stays signature-preserving.
_GOVERNOR: ContextVar[_Snapshot] = ContextVar("maghz_automation_governor")


# --- [OPERATIONS] ----------------------------------------------------------------------


def _decode_spec(type_: type[AutomationSpec], tokens: Sequence[Token]) -> AutomationSpec:  # noqa: ARG001 - `type_` is the cyclopts converter contract positional bound by the framework
    """Admission boundary: decode the `--spec` token into a typed spec and validate its lane.

    The cyclopts `Parameter(converter=...)` shim. cyclopts invokes the converter with `(type, tokens)`
    where each element is a `cyclopts.Token` carrying the raw payload on `.value`; the stateful
    `_SPEC_DECODER` resolves both tagged unions over that value in one pass. A
    `msgspec.DecodeError`/`ValidationError` or a `lane` outside `cfg.automation.lane_keys` raises the
    converter-canonical `ValueError`, which cyclopts wraps into a context-rich `CoercionError` so the
    unknown lane is rejected at admission rather than silently coerced to `"default"`. The CLI `main()`
    boundary catches that `CycloptsError` and folds it to a `Status.FAULTED` envelope (exit 2), the
    `spec_decode` outcome.

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


def _resolve_trigger(trigger: Trigger) -> TriggerTag:
    """Project a trigger to its closed tag, total over the `Watch | Schedule | Manual` union.

    Args:
        trigger: The decoded trigger leaf the spec carries.

    Returns:
        The matching `TriggerTag` literal; the `assert_never` arm proves the union is exhausted.
    """
    match trigger:
        case Watch():
            return "watch"
        case Schedule():
            return "schedule"
        case Manual():
            return "manual"
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Trigger union
            assert_never(unreachable)


def _action_tag(action: Action) -> ActionTag:
    """Project an action to its closed tag, total over the `AgentAction | Notify | Embed | Sync` union.

    The `msgspec` `__struct_config__.tag` reads as `str | int | None`; this match narrows it to the
    bounded `ActionTag` literal the receipt requires, so no bare `str` ever reaches `AutomationReceipt`.

    Args:
        action: The decoded action leaf the spec carries.

    Returns:
        The matching `ActionTag` literal; the `assert_never` arm proves the union is exhausted.
    """
    match action:
        case AgentAction():
            return "agent"
        case Notify():
            return "notify"
        case Embed():
            return "embed"
        case Sync():
            return "sync"
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Action union
            assert_never(unreachable)


def _governor_aspect(op: _Dispatch) -> _Dispatch:
    """Outermost admission gate: snapshot psutil, deny over-ceiling or saturated lanes before any borrow.

    One `Process(os.getpid()).oneshot()` batch reads `cpu_percent(interval=None)` and `memory_info().rss`
    in a single syscall; the reading binds on `_GOVERNOR` so `_exec` stamps the same numbers it gated on.
    A CPU or RSS reading above `cfg.automation.cpu_ceil` / `rss_ceil_mb` returns `Error(admission_denied)`;
    a lane with no free token (`_lane_free(policy) == 0`, the runtime owner's `LanePolicy.available_tokens`
    seam) returns `Error(lane_overflow)` — both BEFORE the wrapped `_dispatch_action` borrows a
    `LanePolicy.drain` token, so a denied admission never enters the drain lifecycle, never writes a job
    row, and never appends a ledger line.

    Args:
        op: The `_dispatch_action` body the gate wraps; invoked only when admission passes.

    Returns:
        A signature-preserving wrapper returning `Error(AutomationFault)` on a denied admission or the
        wrapped result otherwise.
    """

    async def _gated(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy) -> Result[AutomationReceipt, AutomationFault]:
        snapshot = _probe()
        token = _GOVERNOR.set(snapshot)
        try:
            if snapshot.cpu_percent > cfg.automation.cpu_ceil or snapshot.memory_rss_mb > cfg.automation.rss_ceil_mb:
                detail = f"cpu={snapshot.cpu_percent:.1f}% rss={snapshot.memory_rss_mb:.0f}MB"
                return Error(AutomationFault(admission_denied=(spec.id, detail)))
            if _lane_free(policy) == 0:
                return Error(AutomationFault(lane_overflow=(spec.id, spec.lane)))
            return await op(spec, cfg, policy)
        finally:
            _GOVERNOR.reset(token)

    return _gated


def _lane_free(policy: LanePolicy) -> int:
    """Read the lane's free-token count off the runtime owner's `LanePolicy.available_tokens` seam.

    The governor's pre-borrow `lane_overflow` check needs the live free-token count the runtime lane owns
    (the same `CapacityLimiter` `drain` borrows under). `LanePolicy.available_tokens` is that canonical
    seam; until the `lanes` owner ships the property the engine reports full capacity, so the early
    defer/skip optimization is dormant while the hard concurrency bound `drain` enforces is never relaxed.

    Args:
        policy: The lane policy whose free-token count gates the overflow pre-check.

    Returns:
        The live free-token count, or the configured capacity when the owner seam is not yet present.
    """
    return getattr(policy, "available_tokens", policy.capacity)


def _probe() -> _Snapshot:
    """Read own-process CPU% and RSS in one `oneshot()` batch; the engine owns timing (`interval=None`).

    `cpu_percent(interval=None)` returns the load since the prior call without blocking the event loop —
    the engine's debounce and cron tick own the cadence. RSS is normalized to MB; the governor compares it
    against `cfg.automation.rss_ceil_mb`. `getloadavg` is guarded by `hasattr(psutil, "getloadavg")` per
    the portability contract before any use, but is not a receipt field.

    Returns:
        The `_Snapshot` carrying the reading and the dispatch start clock.
    """
    process = psutil.Process(os.getpid())
    with process.oneshot():
        cpu = process.cpu_percent(interval=None)
        rss_mb = process.memory_info().rss / (1024 * 1024)
    return _Snapshot(cpu_percent=cpu, memory_rss_mb=rss_mb, started=time.monotonic())


@_governor_aspect
async def _dispatch_action(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy) -> Result[AutomationReceipt, AutomationFault]:
    """Resolve the spec's action under one lane-drain borrow and project the typed rail back to the caller.

    `@_governor_aspect` already gated admission; this is the projection layer over the `@drained`
    `_drain_once` borrow. The drain carries the receipt as its value and `_record_ledger` appends the
    inner `AutomationReceipt` after it folds. The typed `_exec` rail is recovered from the closure cell so
    a domain `AutomationFault` (agent/permanent/transient) survives projection intact; an empty cell means
    the `move_on_after(cfg.automation.action_timeout_s)` scope tripped, folded to `action_transient`.

    Args:
        spec: The validated spec whose single action this fire dispatches.
        cfg: The validated settings owning the lane capacity, the action timeout, and the ledger path.
        policy: The `LanePolicy` for the spec's lane, already proven to have a free token by the governor.

    Returns:
        `Ok(AutomationReceipt)` on a completed fire (its `values[0]` is ledgered), `Error(action_transient)`
        when the deadline scope tripped, or the exact domain `AutomationFault` the action arm produced —
        the closure cell carries the typed `_exec` rail back so projection never loses it to the lossy
        `DrainReceipt.faults` block.
    """
    sink: list[Result[AutomationReceipt, AutomationFault]] = []
    receipt = await _drain_once(spec, cfg, policy, sink)
    await _record_ledger(receipt, cfg)
    if sink:
        return sink[-1]
    return Error(AutomationFault(action_transient=(spec.id, f"action timed out after {cfg.automation.action_timeout_s:g}s")))


@drained("automation", redact=frozenset({"rss_bytes"}))
async def _drain_once(
    spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, sink: list[Result[AutomationReceipt, AutomationFault]]
) -> DrainReceipt:
    """Borrow one lane token and resolve the spec's action under the drain; emit the `DrainReceipt`.

    `@drained` wraps this single drain call so it probes RSS and emits one `drained` receipt to structlog.
    The fire rides `LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.HTTP, work)]))`: the lane owns
    the concurrency bound and the transient retry, `bound_contextvars` scopes the per-dispatch facts, and
    `move_on_after(cfg.automation.action_timeout_s)` deadlines the `_exec` body. The typed `_exec` rail is
    captured on `sink` so the caller projects the exact `AutomationReceipt` / `AutomationFault` rather than
    the `BoundaryFault`-lifted drain fault block; the drain value carries the receipt for the ledger.

    Args:
        spec: The validated spec whose single action this fire dispatches.
        cfg: The validated settings owning the action timeout and ledger path.
        policy: The `LanePolicy` for the spec's lane, proven to have a free token by the governor.
        sink: The one-element capture cell the caller reads the typed `_exec` rail back from.

    Returns:
        The `DrainReceipt` whose `values[0]` is the resolved `AutomationReceipt` on a completed fire.
    """

    async def _work() -> RuntimeRail[object]:
        with structlog.contextvars.bound_contextvars(spec_id=spec.id, action=spec.action.__struct_config__.tag, lane=spec.lane):
            with anyio.move_on_after(cfg.automation.action_timeout_s):
                outcome = await _exec(spec.action, spec, cfg)
                sink.append(outcome)
                match outcome:
                    case Result(tag="ok", ok=receipt):
                        return Ok(receipt)
                    case Result(error=fault_value):
                        return Error(_lift(fault_value))
            return Error(BoundaryFault(deadline=(spec.id, cfg.automation.action_timeout_s)))

    return await drain(policy, Block.of_seq([Admit(retried=(RetryClass.HTTP, _work))]), Map.empty())


async def _exec(action: Action, spec: AutomationSpec, cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]:
    """Resolve one action under the total `AgentAction | Notify | Embed | Sync` match; one receipt per arm.

    `AgentAction` reads `_AGENT_DISPATCH[action.skill](action, spec, cfg)` — the engine is skill-agnostic
    and never decodes `action.params`. `Notify` emits to stderr or the NDJSON ledger and carries no rows.
    `Embed` calls `maghz.embed_enqueue()` / `maghz.embed_drain()` via `db.query`, mapping `concept=None`
    to the sweep-all path and `Some(name)` to a single-concept enqueue. `Sync` dispatches to
    `sync_run(cfg, concept=...)` and reads `SyncDetail.drift` off the returned `RuntimeRail[Envelope]`. The
    governor snapshot rides `_GOVERNOR`, so each engine-owned arm reads it directly rather than threading a
    raw clock through the call chain.

    Args:
        action: The action leaf to resolve; the match is exhaustive over the closed union.
        spec: The owning spec, supplying the receipt's identity and lane.
        cfg: The validated settings owning the DSN and rail reach.

    Returns:
        `Ok(AutomationReceipt)` fully populated for the arm, or `Error(AutomationFault)` from the arm body.
    """
    match action:
        case AgentAction(skill=skill):
            return await _AGENT_DISPATCH[skill](action, spec, cfg)
        case Notify(channel=channel, message=message):
            await _notify(channel, message)
            return Ok(_receipt(spec, Some(_GOVERNOR.get())))
        case Embed(concept=concept):
            return await _embed(spec, cfg, Some(concept) if concept is not None else Nothing)
        case Sync(concept=concept):
            return await _sync(spec, cfg, concept)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Action union
            assert_never(unreachable)


async def _embed(spec: AutomationSpec, cfg: MaghzSettings, concept: Option[str]) -> Result[AutomationReceipt, AutomationFault]:
    """Drive the in-DB embed pipeline via `db.query`; `Nothing` sweeps all pending, `Some(name)` enqueues one.

    The sweep path enqueues a fresh batch and drains the prior tick's responses in one round-trip; the
    single-concept path filters the enqueue to one `canonical_name` against the `concept_embed_pending_idx`
    partial index. The DB owns the embed protocol; the engine composes the two routine calls and reads the
    enqueued count into `rows_affected`. A `DbFault` folds to `action_transient` (the DB boundary is the
    canonical `guard(RetryClass.DB)` retry seam inside `db.query`; a survivor is a transient exhaustion).

    Args:
        spec: The owning spec supplying the receipt identity and lane.
        cfg: The validated settings owning the DSN.
        concept: `Nothing` sweeps every pending concept; `Some(name)` enqueues that one concept.

    Returns:
        `Ok(AutomationReceipt)` carrying the enqueued count in `rows_affected`, or `Error(action_transient)`.
    """
    if concept.is_some():
        sql = "select maghz.embed_enqueue() as enqueued where exists (select 1 from concept where canonical_name = :name)"
        params: dict[str, str] = {"name": concept.value}
    else:
        sql = "select maghz.embed_enqueue() + maghz.embed_drain() as enqueued"
        params = {}
    match await db.query(sql, cfg, **params):
        case Result(tag="ok", ok=QueryResult(rows=rows)):
            enqueued = int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
            return Ok(_receipt(spec, Some(_GOVERNOR.get()), rows_affected=enqueued))
        case Result(error=dbfault):
            return Error(AutomationFault(action_transient=(spec.id, f"{dbfault.op}: {dbfault.message}")))


async def _sync(spec: AutomationSpec, cfg: MaghzSettings, concept: str | None) -> Result[AutomationReceipt, AutomationFault]:
    """Dispatch the Heptabase sync rail by `concept` arity and read `SyncDetail.drift` into the receipt.

    `None` selects DIFF (`sync_run(cfg, concept=None)`), a name selects GENERATE (`sync_run(cfg, concept=name)`)
    — the canonical single entrypoint after the existing-rails collapse; no `sync_diff` / `sync_generate`
    aliases exist. The rail returns the domain `RuntimeRail[Envelope]`; the `Ok` arm narrows the envelope's
    `report.detail` to a `SyncDetail` in the match itself, so the typed `drift: int` flows into
    `rows_affected` without an untyped read, and any non-`SyncDetail` detail yields `None`. A boundary fault
    folds to `action_transient` (the DB/CLI boundary the rail rides is the canonical retried seam).

    Args:
        spec: The owning spec supplying the receipt identity and lane.
        cfg: The validated settings owning the DSN and Heptabase reach.
        concept: `None` runs DIFF; a `canonical_name` runs GENERATE for that concept.

    Returns:
        `Ok(AutomationReceipt)` with `SyncDetail.drift` in `rows_affected`, or `Error(action_transient)`.
    """
    from admin.rails.sync import run as sync_run, SyncDetail  # noqa: PLC0415 - deferred: breaks the rails.__init__ import cycle

    match await sync_run(cfg, concept=concept):
        case Result(tag="ok", ok=Envelope(report=Report(detail=SyncDetail(drift=drift)))):
            return Ok(_receipt(spec, Some(_GOVERNOR.get()), rows_affected=drift))
        case Result(tag="ok"):
            return Ok(_receipt(spec, Some(_GOVERNOR.get())))
        case Result(error=boundary_fault):
            facts = boundary_fault.facts()
            return Error(AutomationFault(action_transient=(spec.id, str(facts.get("detail", boundary_fault.tag)))))


async def _notify(channel: Literal["stderr", "ndjson"], message: str) -> None:
    """Emit one structured `automation.notify` line carrying the operator message and its routing channel.

    `channel` rides the structured event as the routing key the `Signals` pipeline projects: the stderr
    `ConsoleRenderer`/`BytesLogger` sink and any NDJSON consumer both read `channel` to select where the
    message surfaces, so the engine emits one line and the sink discriminates rather than the engine
    forking a second writer. The closed `Notify.channel` literal narrows the value at the type level.

    Args:
        channel: The closed `stderr` / `ndjson` routing key the downstream sink discriminates on.
        message: The operator message to surface.
    """
    await _LOGGER.ainfo("automation.notify", channel=channel, message=message)


async def _agent_pending(action: AgentAction, spec: AutomationSpec, _cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]:  # noqa: RUF029 - the `_AGENT_DISPATCH` `Work` contract is async; the placeholder matches it until the skill counterpart lands
    """The `_AGENT_DISPATCH` placeholder until the `integrations`/`mcp` skill counterparts land each row.

    The engine ships the table SHAPE — one row per `AgentSkill` — and the skill blueprints ship the real
    callables with the contract `(action, spec, cfg) -> Result[AutomationReceipt, AutomationFault]`. Until
    a skill's row is replaced, it returns `Error(agent_call)` carrying the skill, so the table stays total
    over the closed `AgentSkill` and an unrouted skill faults loud rather than silently no-op'ing.

    Args:
        action: The agent action whose skill row has no counterpart yet.
        spec: The owning spec supplying the fault context.
        _cfg: The validated settings (unused until the real skill callable composes the DB/MCP reach).

    Returns:
        `Error(AutomationFault(agent_call=...))` naming the unrouted skill.
    """
    return Error(AutomationFault(agent_call=(spec.id, f"no dispatch for skill {action.skill.value}")))


def _receipt(spec: AutomationSpec, snapshot: Option[_Snapshot], *, rows_affected: int | None = None, job_id: str | None = None) -> AutomationReceipt:
    """Build the one engine receipt for a spec; `snapshot` presence is the fire/skip discriminant.

    `Some(snapshot)` is a real fire: `attempt=1`, `elapsed_ms` measures from the governor's monotonic
    `started`, and `cpu_percent` / `memory_rss_mb` are the same numbers the admission gate read (the
    governor and receipt never diverge). `Nothing` is a gated or missed tick with no governor reading:
    `attempt=0`, `elapsed_ms=0.0`, and the snapshot fields are `None`. This is the sole `AutomationReceipt`
    constructor — fire and skip route through one owner rather than two parallel literals. `agent_skill`
    narrows only the `AgentAction` arm, whose skill callables build their own receipt, so the engine-owned
    arms leave it `None`.

    Args:
        spec: The spec supplying `spec_id`, the trigger/action tags, and the lane.
        snapshot: `Some(_Snapshot)` for a fire (the governor reading and monotonic start), `Nothing` for a
            gated/missed tick that carries no reading.
        rows_affected: The action's row count (Sync drift, Embed enqueue), or `None`.
        job_id: The agent job id, or `None` for the engine-owned arms.

    Returns:
        The `AutomationReceipt`: snapshot/elapsed on a fire, zeroed and null-snapshot on a skip.
    """
    return AutomationReceipt(
        spec_id=spec.id,
        trigger_tag=_resolve_trigger(spec.trigger),
        action_tag=_action_tag(spec.action),
        agent_skill=None,
        lane=spec.lane,
        fired_at=datetime.now(UTC).isoformat(),
        attempt=1 if snapshot.is_some() else 0,
        elapsed_ms=snapshot.map(lambda snap: (time.monotonic() - snap.started) * 1000.0).default_value(0.0),
        rows_affected=rows_affected,
        job_id=job_id,
        cpu_percent=snapshot.map(lambda snap: snap.cpu_percent).default_value(None),
        memory_rss_mb=snapshot.map(lambda snap: snap.memory_rss_mb).default_value(None),
    )


def _lift(fault_value: AutomationFault) -> BoundaryFault:
    """Lift a domain `AutomationFault` to the runtime `BoundaryFault` so `DrainReceipt.faults` stays typed.

    The drain rail is `RuntimeRail[object]` (`Result[object, BoundaryFault]`); a domain fault inside one
    drain unit must wear the runtime fault to ride `DrainReceipt.faults`. The mapping preserves the fault
    context: transient/agent faults map to `resource`, permanent/admission faults to `api`, the rest to
    `boundary`, each stamped with the originating spec/lane subject. `drive` reads the original
    `AutomationFault` off the dispatch result, so this lift only feeds the drain's fault block.

    Args:
        fault_value: The domain fault one action arm returned.

    Returns:
        The `BoundaryFault` leaf carrying the same subject and detail for the drain's typed fault block.
    """
    subject, detail = fault_value.context()
    match fault_value.tag:
        case "action_transient" | "agent_call":
            return BoundaryFault(resource=(subject, detail))
        case "action_permanent" | "admission_denied" | "lane_overflow":
            return BoundaryFault(api=(subject, detail))
        case _:
            return BoundaryFault(boundary=(subject, detail))


def _fault_envelope(fault_value: AutomationFault) -> Envelope:
    """Project the domain fault to the stdout `Envelope` exactly once, total over the seven-case union.

    `spec_decode` is the only `Status.FAULTED` (exit 2) admission rejection; `admission_denied` and
    `lane_overflow` are `Status.SKIP` (the fire was gated, not failed); the action and trigger faults are
    `Status.FAULTED`. The `assert_never` arm proves the seven `AutomationFaultKind` cases are exhausted.

    Args:
        fault_value: The domain fault `drive` carries out of a failed or gated dispatch.

    Returns:
        The CLI `Envelope` with the projected status and the `{kind, spec_id, detail}` context.
    """
    context, detail = fault_value.context()
    payload = {"kind": fault_value.tag, "context": context, "detail": detail}
    match fault_value.tag:
        case "admission_denied" | "lane_overflow":
            return Envelope(status=Status.SKIP, error=detail, error_context=payload)
        case "spec_decode" | "action_transient" | "action_permanent" | "trigger_spawn" | "agent_call":
            return fault(detail, payload)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed AutomationFault union
            assert_never(unreachable)


async def _record_ledger(receipt: DrainReceipt, cfg: MaghzSettings) -> None:
    """Append the inner `AutomationReceipt` to the NDJSON ledger as one `encode`-then-write per fire.

    `drain_receipt.values[0]` is the inner `AutomationReceipt` (the drain keeps the carrier `object`-typed);
    only a completed fire carries a value, so an empty/faulted drain writes nothing. The blocking append is
    offloaded through `anyio.to_thread.run_sync(fn, limiter=)` under anyio's default thread limiter so the
    event loop stays responsive. The `DrainReceipt` metadata (accepted/cancelled/hit) flows to structlog
    context only — never into the NDJSON line, which carries the lone receipt.

    Args:
        receipt: The drain evidence whose first value is the receipt to ledger.
        cfg: The validated settings owning the NDJSON ledger path.
    """
    if not receipt.values:
        return
    line = msgspec.json.encode(receipt.values[0]) + b"\n"
    path = cfg.automation.ledger_file

    def _append() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(line)

    await anyio.to_thread.run_sync(_append, limiter=anyio.to_thread.current_default_thread_limiter())


# --- [TABLES] --------------------------------------------------------------------------

# Stateful spec decoder, resolved once at import: both tagged unions (`type` for Trigger, `kind` for
# Action) resolve in one pass. `_decode_spec` is the only caller, lifting a decode/validation escape to a
# `ValueError` cyclopts wraps into the `--spec` `CoercionError` at the admission boundary.
_SPEC_DECODER: Final[msgspec.json.Decoder[AutomationSpec]] = msgspec.json.Decoder(type=AutomationSpec)

# Filter discriminant -> watchfiles filter instance. `MappingProxyType` is the static instance map (the
# three filters are constructed once); `"none"` is a real `None` value, so the lane passes
# `watch_filter=None` to `awatch` to disable filtering. Adding a filter mode is one row.
_WATCH_FILTER: Final[MappingProxyType[str, BaseFilter | None]] = MappingProxyType({
    "default": DefaultFilter(),
    "python": PythonFilter(),
    "none": None,
})

# AgentSkill -> skill-dispatch callable, the keyed-table form (`expression.Map`, the runtime owner law —
# never `frozendict`). Each callable is owned by the `integrations`/`mcp` blueprints with contract
# `(action, spec, cfg) -> Result[AutomationReceipt, AutomationFault]`; the engine is skill-agnostic and
# never decodes `action.params`. Adding a skill is one `AgentSkill` member plus one row here — the
# `AgentAction` arm in `_exec` is untouched. Until the skill counterparts land, each row resolves to
# `_agent_pending`, which returns `Error(agent_call)` so the table is total over the closed `AgentSkill`.
_AGENT_DISPATCH: Final[Map[AgentSkill, Work]] = Map.of_seq([(skill, _agent_pending) for skill in AgentSkill])

# Lane key -> LanePolicy, built from `cfg.automation.lane_keys` (the keyed-table form, never a raw
# `CapacityLimiter` dict). Memoised per settings identity so the same `LanePolicy` instances back the
# same `lanes._limiter` across drives; an unknown lane is rejected at `_decode_spec`, never defaulted here.
_LANE_CACHE: dict[int, Map[str, LanePolicy]] = {}


def _lane_policies(cfg: MaghzSettings) -> Map[str, LanePolicy]:
    """Build (memoised) the `lane key -> LanePolicy` table from `cfg.automation.lane_keys`.

    One `LanePolicy(capacity=cfg.automation.max_concurrent)` per declared lane key; the same `LanePolicy`
    instance must back the same `lanes._limiter` memo across drives, so the table is cached per settings
    identity. The key set equals `lane_keys`, and `_decode_spec` already rejected any unknown lane, so
    `drive`'s `policies[spec.lane]` indexes total.

    Args:
        cfg: The validated settings owning the lane keys and the per-lane capacity.

    Returns:
        The `expression.Map[str, LanePolicy]` keyed by every configured lane.
    """
    return _LANE_CACHE.setdefault(
        id(cfg.automation), Map.of_seq([(key, LanePolicy(capacity=cfg.automation.max_concurrent)) for key in cfg.automation.lane_keys])
    )


# --- [LANES] ---------------------------------------------------------------------------


async def _watch_lane(
    spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, stop_event: anyio.Event
) -> Result[AutomationReceipt, AutomationFault]:
    """Watch trigger lane: dispatch once per debounced `watchfiles.awatch` batch until the stop event sets.

    Every `Watch.path` is validated with `anyio.Path(p).exists()` before the generator starts; a missing
    path returns `trigger_spawn` so a VPS path the service account cannot reach fails loud. `awatch` is fed
    the engine's `stop_event` (set by the signal lane / cancel scope) and the `_WATCH_FILTER`-selected
    filter; each batch's `Change.raw_str()` rides structlog context, then `_dispatch_action` fires. The
    last fire's result is returned so a one-shot watch surfaces a receipt; a daemon watch loops until cancel.

    Args:
        spec: The spec carrying the `Watch` trigger and the action to fire per batch.
        cfg: The validated settings owning the lane capacity and ledger path.
        policy: The `LanePolicy` for the spec's lane.
        stop_event: The engine's shared stop event; setting it exits the generator cleanly.

    Returns:
        The last dispatch result, or `Error(trigger_spawn)` when a watched path is unreachable.
    """
    watch = spec.trigger
    assert isinstance(watch, Watch)  # noqa: S101 - the watch lane is selected only for the Watch arm in drive
    for path in watch.paths:
        if not await anyio.Path(path).exists():
            return Error(AutomationFault(trigger_spawn=(spec.lane, f"path not found: {path}")))
    outcome: Result[AutomationReceipt, AutomationFault] = Error(AutomationFault(trigger_spawn=(spec.lane, "no change observed")))
    async for changes in awatch(
        *watch.paths, watch_filter=_WATCH_FILTER[watch.filter], debounce=watch.debounce, stop_event=stop_event, recursive=watch.recursive
    ):
        with structlog.contextvars.bound_contextvars(changes=tuple(f"{change.raw_str()}:{target}" for change, target in changes)):
            outcome = await _dispatch_action(spec, cfg, policy)
    return outcome


async def _schedule_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy) -> Result[AutomationReceipt, AutomationFault]:
    """Schedule trigger lane: register the cron schedule on one `AsyncScheduler` and run until stopped.

    One `async with AsyncScheduler()` owns the 4.x lifecycle (no thread-offloaded shutdown). The schedule
    fires `_scheduled_fire`, and `subscribe(_on_release, JobReleased)` is the single observability seam:
    `JobOutcome.success` records the fire, `JobOutcome.missed_start_deadline` records a `Status.SKIP` tick
    to the ledger. `CronTrigger.from_crontab(cron, timezone=)` carries the cron expression; `max_jitter`
    spreads the fire and `conflict_policy=replace` makes a re-register idempotent. The lane runs until the
    signal lane cancels the task group, then the scheduler context exits cleanly.

    Args:
        spec: The spec carrying the `Schedule` trigger and the action to fire each tick.
        cfg: The validated settings owning the lane capacity and ledger path.
        policy: The `LanePolicy` for the spec's lane.

    Returns:
        `Error(trigger_spawn)` when the scheduler context unwinds (the daemon's normal stop is a cancel,
        so a returned value is only the unreachable non-cancel exit).
    """
    schedule = spec.trigger
    assert isinstance(schedule, Schedule)  # noqa: S101 - the schedule lane is selected only for the Schedule arm in drive

    async def _scheduled_fire() -> None:
        await _dispatch_action(spec, cfg, policy)

    async def _on_release(event: JobReleased) -> None:
        if event.outcome is JobOutcome.missed_start_deadline:
            await _ledger_skip(spec, f"missed schedule tick at {event.scheduled_start}", cfg)

    async with AsyncScheduler() as scheduler:
        scheduler.subscribe(_on_release, JobReleased)
        await scheduler.add_schedule(
            _scheduled_fire,
            CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone),
            id=spec.id,
            conflict_policy=ConflictPolicy.replace,
            max_jitter=schedule.jitter,
        )
        await scheduler.run_until_stopped()
    return Error(AutomationFault(trigger_spawn=(spec.lane, "scheduler stopped")))


async def _signal_lane(tg: TaskGroup) -> None:
    """Signal lane: await the first `SIGTERM`/`SIGINT` and cancel the task group for a clean daemon exit.

    `anyio.open_signal_receiver` installs the handlers for the duration of the receiver scope; the first
    signal cancels the whole `drive` task group so the watch generator's stop event sets, the scheduler
    context exits, and one summary envelope reaches stdout with exit 0. Present only for daemon modes.

    Args:
        tg: The `drive` task group cancelled on the first received signal.
    """
    with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as receiver:
        async for _signum in receiver:
            tg.cancel_scope.cancel()
            return


async def _ledger_skip(spec: AutomationSpec, detail: str, cfg: MaghzSettings) -> None:
    """Append a `Status.SKIP` receipt to the NDJSON ledger for a gated or missed tick (no governor snapshot).

    A missed schedule tick or a saturated cycle produces no governor reading, so `_receipt` mints the
    skip shape from `Nothing`: `attempt=0`, `elapsed_ms=0.0`, null snapshot fields, while still recording
    the spec identity and skip detail so an agent reads saturation and misfire trends off the ledger. The
    one `_receipt` owner builds both the fire and the skip receipt; this reuses `_record_ledger`'s offloaded
    append by wrapping the lone receipt in a singleton drain value.

    Args:
        spec: The spec whose gated/missed tick is recorded.
        detail: The skip reason carried as a structlog note alongside the receipt.
        cfg: The validated settings owning the NDJSON ledger path.
    """
    receipt = _receipt(spec, Nothing)
    await _LOGGER.ainfo("automation.skip", spec_id=spec.id, detail=detail)
    await _record_ledger(DrainReceipt(accepted=1, completed=0, cancelled=1, rejected=0, values=Block.singleton(receipt)), cfg)


# --- [ENTRY] ---------------------------------------------------------------------------


async def drive(spec: AutomationSpec, cfg: MaghzSettings) -> Envelope:
    """The single polymorphic automation entrypoint: one task group per call, projected to one `Envelope`.

    `_resolve_trigger` selects the lane the spec fires under one `anyio.create_task_group`: `Manual`
    dispatches once immediately, `Watch`/`Schedule` run their daemon lanes alongside `_signal_lane` so a
    `SIGTERM` cancels the group cleanly. A crashing lane's `ExceptionGroup` is caught with `except*` and
    folded to `trigger_spawn`. The dispatch `Result[AutomationReceipt, AutomationFault]` projects exactly
    once here: `Ok` lifts to `completed(Status.OK, receipt)`, `Error` lowers through `_fault_envelope`;
    the engine never raises into the CLI. `_LANE_POLICIES` is rebuilt from `cfg.automation.lane_keys`, so
    every valid lane resolves and `spec.lane` (already validated at `_decode_spec`) indexes total.

    Args:
        spec: The validated, lane-checked spec pairing one trigger with one action.
        cfg: The validated settings owning the lane capacity, ceilings, timeout, and ledger path.

    Returns:
        One `Envelope`: `Status.OK` carrying the `AutomationReceipt` on a successful fire, `Status.SKIP`
        for a gated admission, or `Status.FAULTED` for a decode/action/trigger fault.
    """
    policy = _lane_policies(cfg)[spec.lane]
    try:
        async with anyio.create_task_group() as tg:
            outcome = await _run_lane(tg, spec, cfg, policy)
    except* Exception as group:  # noqa: BLE001 - the lane ExceptionGroup folds to one trigger_spawn fault rail
        detail = "; ".join(str(exc) for exc in group.exceptions)
        outcome = Error(AutomationFault(trigger_spawn=(spec.lane, detail)))
    match outcome:
        case Result(tag="ok", ok=receipt):
            return completed(Status.OK, receipt)
        case Result(error=fault_value):
            return _fault_envelope(fault_value)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Result union
            assert_never(unreachable)


async def _run_lane(tg: TaskGroup, spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy) -> Result[AutomationReceipt, AutomationFault]:
    """Spawn the lane the trigger selects inside the open task group, then cancel the group on its return.

    The total `match` over `TriggerTag` owns the per-trigger lane shape: `manual` dispatches once,
    `watch` and `schedule` start `_signal_lane` alongside their daemon lane so a `SIGTERM` cancels the
    group cleanly. Each arm cancels the scope on the lane's return so the daemon lanes and the signal lane
    unwind together. Kept distinct from `drive` so the task-group try body stays one statement.

    Args:
        tg: The open `drive` task group the lanes and the signal receiver spawn into.
        spec: The validated spec whose trigger selects the lane.
        cfg: The validated settings owning the lane capacity and the ledger path.
        policy: The `LanePolicy` for the spec's lane.

    Returns:
        The lane's dispatch result; the `assert_never` arm proves the `TriggerTag` union is exhausted.
    """
    match _resolve_trigger(spec.trigger):
        case "manual":
            outcome = await _dispatch_action(spec, cfg, policy)
        case "watch" | "schedule" as daemon:
            tg.start_soon(_signal_lane, tg)
            outcome = await (_watch_lane(spec, cfg, policy, anyio.Event()) if daemon == "watch" else _schedule_lane(spec, cfg, policy))
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed TriggerTag union
            assert_never(unreachable)
    tg.cancel_scope.cancel()
    return outcome
