from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, UTC
from enum import StrEnum
import signal
from typing import assert_never, Final, Literal, Self
import uuid

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
from admin.core import completed, Detail, Envelope, fault, Report, Status, tag_of, TagForm
from admin.db import QueryResult
from admin.rails import sync as sync_run, SyncDetail, SyncOp
from admin.runtime import Admit, BoundaryFault, drain, DrainReceipt, feed, LaneKey, LanePolicy, LaneSource, Redaction, RetryClass, RuntimeRail
from admin.settings import MaghzSettings, settings


# --- [TYPES] ---------------------------------------------------------------------------


class GateReason(StrEnum):
    status: Status

    SATURATED = ("saturated", Status.SKIP)
    OVER_CEILING = ("over_ceiling", Status.SKIP)

    def __new__(cls, value: str, status: Status) -> Self:

        member = str.__new__(cls, value)
        member._value_ = value
        member.status = status
        return member


type TriggerTag = Literal["watch", "schedule", "manual"]


type ActionTag = Literal["notify", "embed", "sync"]


# TypeForm-annotated targets: the alias reference coerces to the checkable form `tag_of` narrows into.
_TRIGGER_FORM: Final[TagForm[TriggerTag]] = TriggerTag
_ACTION_FORM: Final[TagForm[ActionTag]] = ActionTag


class Watch(msgspec.Struct, frozen=True, gc=False, tag="watch"):
    paths: tuple[str, ...]
    filter: Literal["default", "python", "none"] = "default"
    debounce: int = 1600
    recursive: bool = True


class Schedule(msgspec.Struct, frozen=True, gc=False, tag="schedule"):
    cron: str
    jitter: int = 0
    timezone: str = "UTC"


class Manual(msgspec.Struct, frozen=True, gc=False, tag="manual"):
    pass


class Notify(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="notify"):
    channel: Literal["stderr", "ndjson"]
    message: str


class Embed(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="embed"):
    concept: str | None = None


class Sync(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="sync"):
    op: Literal["diff", "generate"]
    concept: str | msgspec.UnsetType = msgspec.UNSET


type Trigger = Watch | Schedule | Manual


type Action = Notify | Embed | Sync


class AutomationSpec(msgspec.Struct, frozen=True, gc=False):
    trigger: Trigger
    action: Action
    lane: str = "default"
    id: str = msgspec.field(default_factory=lambda: str(uuid.uuid4()))


class AutomationReceipt(Detail, frozen=True, tag="automation"):
    spec_id: str
    trigger_tag: TriggerTag
    action_tag: ActionTag
    lane: str
    fired_at: str
    attempt: int
    elapsed_ms: float
    rows_affected: int | msgspec.UnsetType = msgspec.UNSET
    job_id: str | msgspec.UnsetType = msgspec.UNSET
    cpu_percent: float | msgspec.UnsetType = msgspec.UNSET
    memory_rss_mb: float | msgspec.UnsetType = msgspec.UNSET


class Gate(msgspec.Struct, frozen=True, gc=False):
    reason: GateReason
    spec_id: str
    detail: str

    def envelope(self) -> Envelope:

        context = {"reason": self.reason.value, "spec_id": self.spec_id, "detail": self.detail}
        return completed(self.reason.status, error=self.detail, error_context=context)


type _DispatchOutcome = RuntimeRail[AutomationReceipt] | Gate


type _Admission = Result[_Snapshot, Gate]


type _LaneBuilder = Callable[[AutomationSpec, MaghzSettings, LanePolicy, TaskGroup], Awaitable[_DispatchOutcome]]


class _Snapshot(msgspec.Struct, frozen=True, gc=False):
    cpu_percent: float
    memory_rss_mb: float
    started: float
    load1: Option[float] = Nothing


class _ActionEvidence(msgspec.Struct, frozen=True, gc=False):
    rows_affected: int | msgspec.UnsetType = msgspec.UNSET
    job_id: str | msgspec.UnsetType = msgspec.UNSET


_EMPTY_EVIDENCE = _ActionEvidence()


_LOGGER: Final = structlog.get_logger("maghz.automation")


_REDACTION: Final[Redaction] = Redaction.of(frozenset({"rss_bytes"}))


_PROCESS: Final[psutil.Process] = psutil.Process()


def _now() -> float:
    return anyio.current_time()


def decode_spec(type_: type[AutomationSpec], tokens: Sequence[Token]) -> AutomationSpec:  # noqa: ARG001 - `type_` is the cyclopts converter contract positional bound by the framework

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

    with _PROCESS.oneshot():
        cpu = _PROCESS.cpu_percent(interval=None)
        rss_mb = _PROCESS.memory_info().rss / (1024 * 1024)
    load1 = Option.of_optional(getattr(psutil, "getloadavg", None)).map(lambda fn: fn()[0])
    snapshot = _Snapshot(cpu_percent=cpu, memory_rss_mb=rss_mb, started=_now(), load1=load1)
    if cpu > cfg.automation.cpu_ceil or rss_mb > cfg.automation.rss_ceil_mb:
        return Error(Gate(reason=GateReason.OVER_CEILING, spec_id=spec.id, detail=f"cpu={cpu:.1f}% rss={rss_mb:.0f}MB"))
    if policy.available_tokens == 0:
        return Error(Gate(reason=GateReason.SATURATED, spec_id=spec.id, detail=f"lane {spec.lane!r} saturated"))
    return Ok(snapshot)


def _retry_of(action: Action) -> RetryClass:
    match action:
        case Notify():
            return RetryClass.HTTP
        case Embed() | Sync():
            return RetryClass.DB
        case _ as unreachable:
            assert_never(unreachable)


def _work_of(spec: AutomationSpec, cfg: MaghzSettings, snapshot: _Snapshot, facts: dict[str, object]) -> Admit:

    bound = (
        facts
        | {"spec_id": spec.id, "action": spec.action.__struct_config__.tag, "lane": spec.lane}
        | snapshot.load1.map(lambda load: {"load1": load}).default_value({})
    )

    async def work() -> RuntimeRail[AutomationReceipt]:
        with structlog.contextvars.bound_contextvars(**bound):
            return (await _exec(spec.action, cfg, snapshot)).map(lambda evidence: _receipt(spec, Some(snapshot), evidence=evidence))

    return Admit.guarded(_retry_of(spec.action), work)


def _govern(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, facts: dict[str, object], tg: TaskGroup) -> Block[Admit]:

    match _admit(spec, cfg, policy):
        case Result(tag="ok", ok=snapshot):
            return Block.singleton(_work_of(spec, cfg, snapshot, facts))
        case Result(error=gate):
            _ = tg.start_soon(_ledger_skip, spec, cfg, gate.detail)  # fire-and-forget: the group owns the lifetime, the handle is unused
            return Block.empty()


def _fold(spec: AutomationSpec, cfg: MaghzSettings, receipt: DrainReceipt[object]) -> _DispatchOutcome:

    fired: Option[RuntimeRail[AutomationReceipt]] = receipt.values.try_head().map(lambda value: Ok(_as_receipt(value)))
    failed = receipt.faults.try_head().map(Error)
    deadline: RuntimeRail[AutomationReceipt] = Error(BoundaryFault(deadline=(spec.id, cfg.automation.action_timeout_s)))
    return fired.default_with(lambda: failed.default_value(deadline))


def _as_receipt(value: object) -> AutomationReceipt:

    assert isinstance(value, AutomationReceipt)  # noqa: S101 - the drain value is an AutomationReceipt by construction; the lane erases the type to `object`
    return value


async def _exec(action: Action, cfg: MaghzSettings, snapshot: _Snapshot) -> RuntimeRail[_ActionEvidence]:

    match action:
        case Notify(channel=channel, message=message):
            await _LOGGER.ainfo("automation.notify", channel=channel, message=message)
            return Ok(_EMPTY_EVIDENCE)
        case Embed(concept=concept):
            return await _embed(cfg, snapshot, Option.of_optional(concept))
        case Sync() as sync_action:
            return await _sync(cfg, sync_action)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Action union
            assert_never(unreachable)


async def _embed(cfg: MaghzSettings, _snapshot: _Snapshot, concept: Option[str]) -> RuntimeRail[_ActionEvidence]:

    def _enqueued(result: QueryResult) -> int:
        head = result.rows[0] if result.rows else ()
        return int(head[0]) if head and head[0] is not None else 0

    match concept:
        case Option(tag="some", some=name):
            sql = "select maghz.embed_enqueue() as enqueued where exists (select 1 from concept where canonical_name = :name)"
            queried = await db.query(sql, cfg, name=name)
        case _:
            queried = await db.query("select maghz.embed_enqueue() + maghz.embed_drain() as enqueued", cfg)
    return queried.map(lambda result: _ActionEvidence(rows_affected=_enqueued(result)))


async def _sync(cfg: MaghzSettings, action: Sync) -> RuntimeRail[_ActionEvidence]:

    match _sync_concept(action):
        case Result(tag="ok", ok=concept):
            rail = await _sync_dispatch(cfg, concept)
        case Result(error=boundary_fault):
            return Error(boundary_fault)

    return _sync_evidence(rail)


def _sync_concept(action: Sync) -> RuntimeRail[str | None]:

    match action:
        case Sync(op="diff", concept=msgspec.UNSET):
            return Ok(None)
        case Sync(op="diff", concept=str() as concept):
            return Error(BoundaryFault(config=("automation.sync", f"diff does not accept concept {concept!r}")))
        case Sync(op="generate", concept=str() as concept):
            return Ok(concept)
        case Sync(op="generate", concept=msgspec.UNSET):
            return Error(BoundaryFault(config=("automation.sync", "generate requires concept")))
        case _:
            return Error(BoundaryFault(config=("automation.sync", "invalid sync action")))


async def _sync_dispatch(cfg: MaghzSettings, concept: str | None) -> RuntimeRail[Envelope]:

    return await sync_run(cfg) if concept is None else await sync_run(cfg, concept=concept)


def _sync_evidence(rail: RuntimeRail[Envelope]) -> RuntimeRail[_ActionEvidence]:

    match rail:
        case Result(tag="ok", ok=Envelope(report=Report(detail=SyncDetail(op=SyncOp.DIFF, drifted=int() as drifted, orphaned=int() as orphaned)))):
            return Ok(_ActionEvidence(rows_affected=drifted + orphaned))
        case Result(tag="ok", ok=Envelope(report=Report(detail=SyncDetail(op=SyncOp.GENERATE, card_id=str())))):
            return Ok(_ActionEvidence(rows_affected=1))
        case Result(tag="ok"):
            return Ok(_EMPTY_EVIDENCE)
        case Result(error=boundary_fault):
            return Error(boundary_fault)


def _receipt(spec: AutomationSpec, snapshot: Option[_Snapshot], *, evidence: _ActionEvidence = _EMPTY_EVIDENCE) -> AutomationReceipt:

    return AutomationReceipt(
        spec_id=spec.id,
        trigger_tag=tag_of(spec.trigger, _TRIGGER_FORM),
        action_tag=tag_of(spec.action, _ACTION_FORM),
        lane=spec.lane,
        fired_at=datetime.now(UTC).isoformat(),
        attempt=1 if snapshot.is_some() else 0,
        elapsed_ms=snapshot.map(lambda snap: (_now() - snap.started) * 1000.0).default_value(0.0),
        rows_affected=evidence.rows_affected,
        job_id=evidence.job_id,
        cpu_percent=snapshot.map(lambda snap: snap.cpu_percent).default_value(msgspec.UNSET),
        memory_rss_mb=snapshot.map(lambda snap: snap.memory_rss_mb).default_value(msgspec.UNSET),
    )


async def _record_ledger(values: Block[object], cfg: MaghzSettings) -> None:

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

    await _LOGGER.ainfo("automation.skip", spec_id=spec.id, detail=detail)
    await _record_ledger(Block.singleton(_receipt(spec, Nothing)), cfg)


_SPEC_DECODER: Final[msgspec.json.Decoder[AutomationSpec]] = msgspec.json.Decoder(type=AutomationSpec)


_WATCH_FILTER: Final[frozendict[Literal["default", "python", "none"], BaseFilter]] = frozendict({
    "default": DefaultFilter(),
    "python": PythonFilter(),
    "none": BaseFilter(),
})


async def _manual_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, _tg: TaskGroup) -> _DispatchOutcome:

    match _admit(spec, cfg, policy):
        case Result(tag="error", error=gate):
            await _ledger_skip(spec, cfg, gate.detail)
            return gate
        case Result(ok=snapshot):
            receipt = await drain(policy, Block.singleton(_work_of(spec, cfg, snapshot, {})))
            await _record_ledger(receipt.values, cfg)
            return _fold(spec, cfg, receipt)


async def _watch_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, tg: TaskGroup) -> _DispatchOutcome:

    watch = spec.trigger
    assert isinstance(watch, Watch)  # noqa: S101 - the watch lane is selected only for the Watch arm in drive
    for path in watch.paths:
        if not await anyio.Path(path).exists():
            return Error(BoundaryFault(resource=(spec.lane, f"path not found: {path}")))

    def _watch_build(batch: set[tuple[Change, str]]) -> Block[Admit]:
        facts: dict[str, object] = {"changes": tuple(f"{change.raw_str()}:{target}" for change, target in batch)}
        return _govern(spec, cfg, policy, facts, tg)

    source = LaneSource.on_change(
        watch.paths, _watch_build, watch_filter=_WATCH_FILTER[watch.filter], debounce=watch.debounce, recursive=watch.recursive
    )
    outcome: _DispatchOutcome = Error(BoundaryFault(resource=(spec.lane, "no change observed")))
    async for receipt in feed(policy, source, "automation", _REDACTION):
        if receipt.accepted == 0:  # a gated batch admitted no fire; its skip is already ledgered on the group
            continue
        await _record_ledger(receipt.values, cfg)
        outcome = _fold(spec, cfg, receipt)
    return outcome


async def _schedule_lane(spec: AutomationSpec, cfg: MaghzSettings, policy: LanePolicy, tg: TaskGroup) -> _DispatchOutcome:

    schedule = spec.trigger
    assert isinstance(schedule, Schedule)  # noqa: S101 - the schedule lane is selected only for the Schedule arm in drive

    def _schedule_build(event: JobReleased) -> Block[Admit]:
        if event.outcome is JobOutcome.missed_start_deadline:
            _ = tg.start_soon(_ledger_skip, spec, cfg, f"missed schedule tick at {event.scheduled_start}")  # fire-and-forget skip ledgering
            return Block.empty()
        return _govern(spec, cfg, policy, {"scheduled_start": str(event.scheduled_start)}, tg)

    trigger = CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone)
    source = LaneSource.on_schedule(trigger, _schedule_build, jitter=schedule.jitter or None)
    outcome: _DispatchOutcome = Error(BoundaryFault(resource=(spec.lane, "scheduler stopped")))
    async for receipt in feed(policy, source, "automation", _REDACTION):
        if receipt.accepted == 0:  # a gated/missed tick admitted no fire; its skip is already ledgered on the group
            continue
        await _record_ledger(receipt.values, cfg)
        outcome = _fold(spec, cfg, receipt)
    return outcome


async def _signal_lane(tg: TaskGroup) -> None:

    with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as receiver:
        async for _signum in receiver:
            tg.cancel_scope.cancel()
            return


_LANE: Final[frozendict[TriggerTag, _LaneBuilder]] = frozendict({"manual": _manual_lane, "watch": _watch_lane, "schedule": _schedule_lane})


async def drive(spec: AutomationSpec, cfg: MaghzSettings) -> Envelope:

    policy = LanePolicy(
        capacity=cfg.automation.max_concurrent, deadline=Some(cfg.automation.action_timeout_s), key=LaneKey(f"automation.{spec.lane}")
    )
    tag = tag_of(spec.trigger, _TRIGGER_FORM)
    outcome: _DispatchOutcome
    try:
        async with anyio.create_task_group() as tg:
            if tag != "manual":
                _ = tg.start_soon(_signal_lane, tg)  # fire-and-forget: the group owns the lifetime, the handle is unused
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


__all__ = [
    "Action",
    "AutomationReceipt",
    "AutomationSpec",
    "Embed",
    "Manual",
    "Notify",
    "Schedule",
    "Sync",
    "Trigger",
    "Watch",
    "decode_spec",
    "drive",
]
