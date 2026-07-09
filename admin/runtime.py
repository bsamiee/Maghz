from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from enum import StrEnum
from functools import cache, wraps
from hashlib import blake2b
import math
import os
from os import fspath, PathLike
from subprocess import CompletedProcess  # noqa: S404
import sys
from typing import assert_never, Final, final, Literal, NewType, NotRequired, overload, Protocol, runtime_checkable, TypedDict

import anyio
from anyio import CapacityLimiter, move_on_after, WouldBlock
from anyio.streams.memory import MemoryObjectSendStream
from apscheduler import AsyncScheduler, JobReleased
from apscheduler.abc import Trigger as ScheduleTrigger
import asyncssh
from beartype.roar import BeartypeCallHintViolation
from expression import case, Error, Nothing, Ok, Option, Result, Some, tag, tagged_union
from expression.collections import Block, Map
import httpx
from httpx import HTTPStatusError
import msgspec
from msgspec import Struct, UNSET, UnsetType
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import pg8000
import psutil
import stamina
import stamina.instrumentation
from stamina.typing import RetryDetails
import structlog
from watchfiles import awatch, BaseFilter, Change, PythonFilter

from admin.core import Envelope, fault


# --- [TYPES] ---------------------------------------------------------------------------

type FaultTag = Literal["config", "resource", "deadline", "api", "import_", "wire", "boundary", "aggregate"]
type ClassifyRow = tuple[type[Exception] | tuple[type[Exception], ...], Callable[[str, BaseException], BoundaryFault]]
type Catch = type[BaseException] | tuple[type[BaseException], ...]
type StrPath = str | PathLike[str]


class Disposition(StrEnum):
    ABORT = "abort"  # bind-short-circuit to the first fault (dependent steps)
    ACCUMULATE = "accumulate"  # combine-fold every fault into one aggregate (independent operands)
    PARTITION = "partition"


@tagged_union(frozen=True)
class BoundaryFault:
    tag: FaultTag = tag()
    config: tuple[str, str] = case()
    resource: tuple[str, str] = case()
    deadline: tuple[str, float] = case()
    api: tuple[str, str] = case()
    import_: tuple[str, str] = case()
    wire: tuple[str, int] = case()
    boundary: tuple[str, str] = case()
    aggregate: tuple[BoundaryFault, ...] = case()

    @staticmethod
    def of(subject: str, cause: BaseException) -> BoundaryFault:

        matched = CLASSIFY.choose(lambda row: Some(row[1](subject, cause)) if isinstance(cause, row[0]) else Nothing)
        return matched.try_head().default_with(lambda: BoundaryFault(boundary=(subject, str(cause) or type(cause).__name__)))

    @staticmethod
    def combine(left: BoundaryFault, right: BoundaryFault) -> BoundaryFault:

        match (left, right):
            case (BoundaryFault(tag="aggregate"), BoundaryFault(tag="aggregate")):
                return BoundaryFault(aggregate=(*left.aggregate, *right.aggregate))
            case (BoundaryFault(tag="aggregate"), _):
                return BoundaryFault(aggregate=(*left.aggregate, right))
            case (_, BoundaryFault(tag="aggregate")):
                return BoundaryFault(aggregate=(left, *right.aggregate))
            case _:
                return BoundaryFault(aggregate=(left, right))

    def recoverable(self, codes: frozenset[FaultTag]) -> bool:

        match self:
            case BoundaryFault(tag="aggregate", aggregate=members):
                return any(member.recoverable(codes) for member in members)
            case _:
                return self.tag in codes

    def facts(self) -> dict[str, object]:

        match self.tag:
            case "aggregate":
                return {"tag": "aggregate", "subject": "aggregate", "members": ",".join(member.tag for member in self.aggregate)}
            case "deadline":
                subject, budget = self.deadline
                return {"tag": "deadline", "subject": subject, "budget": budget}
            case "wire":
                subject, code = self.wire
                return {"tag": "wire", "subject": subject, "code": code}
            case "config" | "resource" | "api" | "import_" | "boundary" as tag_value:
                # the tagged-union law pins each case attribute to its tag name, so the narrowed tag IS the payload key
                subject, detail = getattr(self, tag_value)
                return {"tag": tag_value, "subject": subject, "detail": detail}
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed FaultTag literal
                assert_never(unreachable)

    def headline(self) -> str:

        slots = self.facts()
        return f"{slots['subject']}: {next(value for key, value in slots.items() if key not in {'tag', 'subject'})}"


_WORKER_EXC: Final = (
    anyio.BrokenWorkerProcess,
    anyio.BrokenWorkerInterpreter,
    anyio.BrokenResourceError,
    anyio.ClosedResourceError,
    anyio.ConnectionFailed,
)
_SSH_PROTOCOL: Final = (
    asyncssh.KeyExchangeFailed,
    asyncssh.MACError,
    asyncssh.CompressionError,
    asyncssh.ProtocolError,
    asyncssh.ProtocolNotSupported,
    asyncssh.ServiceNotAvailable,
)
_SSH_DENIED: Final = (asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable, asyncssh.IllegalUserName)
SSH_TRANSIENT: Final[tuple[type[asyncssh.Error], ...]] = (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError)
SSH_TERMINAL: Final[tuple[type[asyncssh.Error], ...]] = (*_SSH_DENIED, *_SSH_PROTOCOL)


type RuntimeRail[T] = Result[T, BoundaryFault]
type AsyncWork[T] = Callable[[], Awaitable[T]]
type Work = Callable[[], Awaitable[RuntimeRail[object]]]


def _convert(subject: str, cause: BaseException) -> BoundaryFault:

    fault_value = BoundaryFault.of(subject, cause)
    span = trace.get_current_span()
    if span.is_recording():
        # `escaped` stays the default `False`: the exception is converted to `Error(fault)` at this
        # fence, so per OTel semantics it does NOT escape the span scope.
        span.record_exception(cause, attributes={"maghz.fault.tag": fault_value.tag, "maghz.fault.subject": subject})
        span.set_status(Status(StatusCode.ERROR, fault_value.tag))
    return fault_value


def _guard[T](subject: str, thunk: Callable[[], T], catch: Catch) -> RuntimeRail[T]:
    try:
        return Ok(thunk())
    except catch as cause:
        return Error(_convert(subject, cause))


def boundary[T](subject: str, thunk: Callable[[], T], *, catch: Catch = Exception) -> RuntimeRail[T]:

    return _guard(subject, thunk, catch)


async def async_boundary[T](subject: str, thunk: Callable[[], Awaitable[T]], *, catch: Catch = Exception) -> RuntimeRail[T]:

    try:
        return Ok(await thunk())
    except catch as cause:
        return Error(_convert(subject, cause))


@overload
def traversed[T](rails: Block[RuntimeRail[T]], *, by: Literal[Disposition.ABORT, Disposition.ACCUMULATE] = ...) -> RuntimeRail[Block[T]]: ...


@overload
def traversed[T](rails: Block[RuntimeRail[T]], *, by: Literal[Disposition.PARTITION]) -> RuntimeRail[tuple[Block[T], Block[BoundaryFault]]]: ...


def traversed[T](
    rails: Block[RuntimeRail[T]], *, by: Disposition = Disposition.ABORT
) -> RuntimeRail[Block[T]] | RuntimeRail[tuple[Block[T], Block[BoundaryFault]]]:

    match by:
        case Disposition.ABORT:
            seed: RuntimeRail[Block[T]] = Ok(Block.empty())
            return rails.fold(lambda acc, rail: acc.bind(lambda done: rail.map(lambda value: done.append(Block.singleton(value)))), seed)
        case Disposition.ACCUMULATE | Disposition.PARTITION:
            values, faults = rails.choose(lambda rail: rail.to_option()), rails.choose(lambda rail: rail.swap().to_option())
            if by is Disposition.PARTITION:
                return Ok((values, faults))
            return Ok(values) if faults.try_head().is_none() else Error(faults.reduce(BoundaryFault.combine))
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Disposition enum
            assert_never(unreachable)


def _wire(subject: str, cause: BaseException) -> BoundaryFault:
    return BoundaryFault(wire=(subject, cause.response.status_code if isinstance(cause, HTTPStatusError) else 0))


CLASSIFY: Final[Block[ClassifyRow]] = Block.of_seq([
    ((TimeoutError,), lambda subject, _cause: BoundaryFault(deadline=(subject, 0.0))),
    (_WORKER_EXC, lambda subject, cause: BoundaryFault(resource=(subject, type(cause).__name__))),
    ((msgspec.DecodeError, msgspec.ValidationError), lambda subject, cause: BoundaryFault(boundary=(subject, type(cause).__name__))),
    ((BeartypeCallHintViolation,), lambda subject, cause: BoundaryFault(api=(subject, type(cause).__name__))),
    ((ImportError,), lambda subject, cause: BoundaryFault(import_=(subject, type(cause).__name__))),
    ((HTTPStatusError,), _wire),
    ((asyncssh.ProcessError, asyncssh.SFTPError), lambda subject, cause: BoundaryFault(boundary=(subject, str(cause)))),
    (_SSH_DENIED, lambda subject, cause: BoundaryFault(api=(subject, str(cause)))),
    (_SSH_PROTOCOL, lambda subject, cause: BoundaryFault(boundary=(subject, str(cause)))),
    (SSH_TRANSIENT, lambda subject, cause: BoundaryFault(resource=(subject, str(cause)))),
    ((OSError,), lambda subject, cause: BoundaryFault(boundary=(subject, str(cause)))),
    ((Exception,), lambda subject, cause: BoundaryFault(boundary=(subject, str(cause)))),
])


def lower(rail: RuntimeRail[Envelope]) -> Envelope:

    match rail:
        case Result(tag="ok", ok=envelope):
            return envelope
        case Result(error=boundary_fault):
            return fault(boundary_fault.headline(), {key: str(value) for key, value in boundary_fault.facts().items()})
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Result(Ok | Error) union
            assert_never(unreachable)


type _Target = type[Exception] | tuple[type[Exception], ...] | Callable[[Exception], bool | float | timedelta]


@runtime_checkable
class RetryAfter(Protocol):
    retry_after: float | None


# `stamina.typing.RetryHook` re-stated runtime-checkable: the claw cannot decorate against the
# upstream non-checkable protocol, so this local form is the claw-admissible return contract.
@runtime_checkable
class OnRetry(Protocol):
    def __call__(self, details: RetryDetails) -> AbstractContextManager[None] | None: ...


class RetryClass(StrEnum):
    DB = "db"
    HTTP = "http"
    PROC = "proc"

    @property
    def policy(self) -> "Policy":  # noqa: UP037 - `Policy` is declared below in `[MODELS]`; the forward-ref quote is load-bearing

        return POLICY[self]


class RetryMode(StrEnum):
    EMIT = "emit"
    SILENT = "silent"
    TEST = "test"


class Schedule(TypedDict):
    attempts: int
    timeout: float
    wait_initial: NotRequired[float]
    wait_max: NotRequired[float]
    wait_jitter: NotRequired[float]
    wait_exp_base: NotRequired[float]


class Policy(Struct, frozen=True):
    attempts: int
    timeout: float
    target: _Target
    wait_initial: float | UnsetType = UNSET
    wait_max: float | UnsetType = UNSET
    wait_jitter: float | UnsetType = UNSET
    wait_exp_base: float | UnsetType = UNSET

    @property
    def schedule(self) -> Schedule:

        schedule: Schedule = {"attempts": self.attempts, "timeout": self.timeout}
        if isinstance(self.wait_initial, float):
            schedule["wait_initial"] = self.wait_initial
        if isinstance(self.wait_max, float):
            schedule["wait_max"] = self.wait_max
        if isinstance(self.wait_jitter, float):
            schedule["wait_jitter"] = self.wait_jitter
        if isinstance(self.wait_exp_base, float):
            schedule["wait_exp_base"] = self.wait_exp_base
        return schedule


class _RailRetryError(Exception):
    fault: BoundaryFault

    def __init__(self, fault_value: BoundaryFault) -> None:
        super().__init__(fault_value.headline())
        self.fault = fault_value


_TRACER: Final = trace.get_tracer("maghz.runtime.resilience")


def _retry_after(*transient: type[Exception], exclude: tuple[type[Exception], ...] = ()) -> _Target:

    def backoff(exc: Exception) -> bool | float | timedelta:
        match exc:
            case _ if isinstance(exc, exclude):
                return False
            case RetryAfter(retry_after=float() as seconds):
                return seconds
            case _:
                return isinstance(exc, transient)

    return backoff


def _retry_receipt() -> OnRetry:

    @contextmanager
    def hook(details: RetryDetails) -> Iterator[None]:
        cause = type(details.caused_by).__qualname__
        facts: dict[str, object] = {
            "retry_num": details.retry_num,
            "wait_for": details.wait_for,
            "waited_so_far": details.waited_so_far,
            "caused_by": cause,
        }
        Signals.emit(Receipt.of("resilience", Fact("retry", details.name, facts)))
        span = _TRACER.start_span(
            "resilience.retry", attributes={"maghz.retry_num": details.retry_num, "maghz.wait_for": details.wait_for, "maghz.caused_by": cause}
        )
        span.set_status(Status(StatusCode.ERROR, cause))
        # `trace.use_span` yields the `Span`; this generator re-yields `None` so the returned CM is the
        # `AbstractContextManager[None]` the `stamina` `RetryHook` contract requires, the span entered for
        # the scheduled wait and ended on exit. `Signals.emit` mints the fact before the wait.
        with trace.use_span(span, end_on_exit=True):
            yield

    return hook


@cache
def guard(cls: RetryClass) -> stamina.BoundAsyncRetryingCaller:

    row = cls.policy
    return stamina.AsyncRetryingCaller(**row.schedule).on(row.target)


# Declared below `RetryClass` so the claw resolves the `RetryClass | None` hint at decoration time.
async def spawn(
    argv: tuple[str, ...],
    *,
    subject: str,
    retry_class: RetryClass | None = None,
    env: Mapping[str, str] | None = None,
    cwd: StrPath | None = None,
    stdin: bytes | None = None,
) -> RuntimeRail[CompletedProcess[bytes]]:

    async def run() -> CompletedProcess[bytes]:
        # anyio `env` REPLACES the child environment; the spawn contract is overlay — supplied rows
        # extend the inherited environment so PATH/HOME survive under injected DOCKER_HOST/RCLONE_* rows.
        overlay = {**os.environ, **env} if env is not None else None  # noqa: TID251 - subprocess overlay at the one spawn boundary, not config ingress
        return await anyio.run_process(argv, input=stdin, env=overlay, cwd=cwd, check=False)

    if retry_class is None:
        return await async_boundary(subject, run)
    return await async_boundary(subject, lambda: guard(retry_class)(run))


def _targeted(cls: RetryClass) -> _Target:

    base = cls.policy.target
    recoverable = RAIL_RETRY_TAGS[cls]

    def target(cause: Exception) -> bool | float | timedelta:
        if isinstance(cause, _RailRetryError):
            return cause.fault.recoverable(recoverable)
        if isinstance(base, (type, tuple)):
            return isinstance(cause, base)
        return base(cause)

    return target


async def _retry_rail(cls: RetryClass, work: Work) -> RuntimeRail[object]:

    # `_graded` raises `_RailRetryError` for a recoverable fault; stamina suppresses it inside
    # `with attempt` to schedule the next try, and exhaustion re-raises it into the except arms.
    try:
        async for attempt in stamina.retry_context(on=_targeted(cls), **cls.policy.schedule):
            with attempt:
                return _graded(cls, await work())
    except _RailRetryError as cause:
        return Error(cause.fault)
    except Exception as cause:  # noqa: BLE001 - lane retry boundary converts terminal escapes to the rail
        return Error(_convert(f"lane.{cls.value}", cause))
    return Error(BoundaryFault(boundary=(f"lane.{cls.value}", "retry exhausted without result")))


def _graded(cls: RetryClass, rail: RuntimeRail[object]) -> RuntimeRail[object]:

    match rail:
        case Result(tag="ok") as ok:
            return ok
        case Result(error=fault_value) if fault_value.recoverable(RAIL_RETRY_TAGS[cls]):
            raise _RailRetryError(fault_value)
        case Result(error=fault_value):
            return Error(fault_value)


async def guarded[T](cls: RetryClass, work: AsyncWork[T], *, subject: str) -> RuntimeRail[T]:

    with _TRACER.start_as_current_span("resilience.guarded", attributes={"maghz.retry_class": cls.value}):
        return await async_boundary(subject, lambda: guard(cls)(work))


def install(mode: RetryMode = RetryMode.EMIT) -> None:

    stamina.set_testing(mode is RetryMode.TEST)
    stamina.instrumentation.set_on_retry_hooks(RETRY_HOOKS if mode is RetryMode.EMIT else ())


_HTTP_TARGET: Final[_Target] = _retry_after(httpx.ConnectError, httpx.RemoteProtocolError, *SSH_TRANSIENT, OSError, exclude=SSH_TERMINAL)
POLICY: Final[Map[RetryClass, Policy]] = Map.of_seq([
    (RetryClass.DB, Policy(attempts=4, timeout=30.0, target=(pg8000.Error, OSError), wait_initial=0.1, wait_max=3.0)),
    (RetryClass.HTTP, Policy(attempts=5, timeout=60.0, target=_HTTP_TARGET, wait_initial=0.2, wait_max=5.0)),
    (RetryClass.PROC, Policy(attempts=3, timeout=45.0, target=(OSError,), wait_initial=0.1, wait_max=4.0)),
])
RAIL_RETRY_TAGS: Final[Map[RetryClass, frozenset[FaultTag]]] = Map.of_seq([
    (RetryClass.DB, frozenset({"resource", "deadline"})),
    (RetryClass.HTTP, frozenset({"resource", "deadline", "wire"})),
    (RetryClass.PROC, frozenset({"resource", "deadline"})),
])
RetryReceiptHook: Final[stamina.instrumentation.RetryHookFactory] = stamina.instrumentation.RetryHookFactory(_retry_receipt)
RETRY_HOOKS: Final[tuple[stamina.instrumentation.RetryHookFactory, ...]] = (RetryReceiptHook, stamina.instrumentation.StructlogOnRetryHook)
LaneKey = NewType("LaneKey", str)

type AdmitTag = Literal["bare", "retried"]


@tagged_union(frozen=True)
class Admit:
    tag: AdmitTag = tag()
    bare: Work = case()
    retried: tuple[RetryClass, Work] = case()

    @staticmethod
    def of(work: Work) -> Admit:

        return Admit(bare=work)

    @staticmethod
    def guarded(retry: RetryClass, work: Work) -> Admit:

        return Admit(retried=(retry, work))

    def resolved(self) -> Work:

        match self.tag:
            case "bare":
                return self.bare
            case "retried":
                retry, work = self.retried
                return lambda: _retry_rail(retry, work)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed AdmitTag literal
                assert_never(unreachable)


@tagged_union(frozen=True)
class LaneSource:
    tag: Literal["scheduled", "watched"] = tag()
    scheduled: tuple[ScheduleTrigger, float | timedelta | None, Callable[[JobReleased], Block[Admit]]] = case()
    watched: tuple[tuple[str | PathLike[str], ...], BaseFilter | None, int, bool, Callable[[set[tuple[Change, str]]], Block[Admit]]] = case()

    @staticmethod
    def on_schedule(trigger: ScheduleTrigger, build: Callable[[JobReleased], Block[Admit]], *, jitter: float | timedelta | None = None) -> LaneSource:

        return LaneSource(scheduled=(trigger, jitter, build))

    @staticmethod
    def on_change(
        paths: Sequence[str | PathLike[str]],
        build: Callable[[set[tuple[Change, str]]], Block[Admit]],
        *,
        watch_filter: BaseFilter | None = None,
        debounce: int = 1600,
        recursive: bool = True,
    ) -> LaneSource:

        return LaneSource(watched=(tuple(paths), watch_filter, debounce, recursive, build))


_INF: Final = math.inf
_FIRE_BUFFER: Final = 64


class DrainReceipt[T](msgspec.Struct, frozen=True):
    accepted: int
    completed: int
    cancelled: int
    rejected: int
    values: Block[T] = Block.empty()
    faults: Block[BoundaryFault] = Block.empty()

    def counts(self) -> dict[str, int]:
        return {"accepted": self.accepted, "completed": self.completed, "cancelled": self.cancelled, "rejected": self.rejected}


@cache
def _limiter(policy: LanePolicy) -> CapacityLimiter:

    return CapacityLimiter(policy.capacity)


class LanePolicy(msgspec.Struct, frozen=True):
    capacity: int
    deadline: Option[float] = Nothing
    key: LaneKey = LaneKey("default")

    @property
    def limiter(self) -> CapacityLimiter:

        return _limiter(self)

    @property
    def available_tokens(self) -> int:

        return math.floor(self.limiter.available_tokens)

    async def drain(self, units: Block[Admit]) -> DrainReceipt[object]:

        limiter = self.limiter
        budget = self.deadline.default_value(_INF)
        send, receive = anyio.create_memory_object_stream[RuntimeRail[object]](max(len(units), 1))

        async def lane(fn: Work, sink: MemoryObjectSendStream[RuntimeRail[object]]) -> None:
            async with sink, limiter:
                try:
                    rail = await fn()
                except Exception as cause:  # noqa: BLE001 - lane boundary converts all work escapes to rejected rail faults
                    rail = Error(_convert(str(self.key), cause))
                await sink.send(rail)

        with move_on_after(budget):
            async with anyio.create_task_group() as group, send:
                for unit in units:
                    _ = group.start_soon(lane, unit.resolved(), send.clone())  # fire-and-forget: the group owns the lifetime, the handle is unused
        resolved = Block.of_seq([item async for item in receive])
        values = resolved.choose(lambda rail: rail.to_option())
        faults = resolved.choose(lambda rail: rail.swap().to_option())
        return DrainReceipt(
            accepted=len(units), completed=len(values), cancelled=len(units) - len(resolved), rejected=len(faults), values=values, faults=faults
        )


def _fire_seam(send: MemoryObjectSendStream[JobReleased]) -> Callable[[JobReleased], None]:

    def on_fire(event: JobReleased) -> None:
        try:
            send.send_nowait(event)
        except WouldBlock:
            Signals.emit(Receipt.of("lane", Fact("admitted", "schedule.drop", {"job_id": event.job_id})))
        except anyio.BrokenResourceError:
            Signals.emit(Receipt.of("lane", Fact("admitted", "schedule.closed", {"job_id": event.job_id})))

    return on_fire


async def _events(source: LaneSource) -> AsyncIterator[Block[Admit]]:

    match source:
        case LaneSource(tag="watched", watched=(paths, watch_filter, debounce, recursive, build)):
            async for batch in awatch(
                *(fspath(path) for path in paths),
                watch_filter=Option.of_optional(watch_filter).default_value(PythonFilter()),
                debounce=debounce,
                recursive=recursive,
            ):
                yield build(batch)
        case LaneSource(tag="scheduled", scheduled=(trigger, jitter, build)):
            send, receive = anyio.create_memory_object_stream[JobReleased](_FIRE_BUFFER)
            # the `AsyncScheduler` async-CM owns the 4.x lifecycle; `feed` fully drives this generator so
            # the scheduler shuts down when the `receive` stream closes or the enclosing task group cancels.
            async with AsyncScheduler() as scheduler, send:
                scheduler.subscribe(_fire_seam(send), JobReleased, is_async=False)
                await scheduler.add_schedule(_noop, trigger, max_jitter=jitter)
                await scheduler.start_in_background()
                async for event in receive:
                    yield build(event)  # noqa: ASYNC119 - the scheduler async-CM is the lifecycle owner; `feed` drains this to completion
        case _:  # pragma: no cover - exhaustive over the closed LaneSource union
            # the `ty` gate rejects `assert_never` on the opaque `tagged_union` residual, so the explicit raise carries the proven totality.
            raise AssertionError(source.tag)


def _noop() -> None:
    pass


type Phase = Literal["admitted", "retry", "emitted"]
type ReceiptTag = Literal["fact", "rejected", "drained"]
type LogLevel = Literal["debug", "info", "warning", "error"]
type Format = Literal["json", "console"]
type Classification = Literal["drop", "mask", "hash"]
type EventDict = dict[str, object]


@final
class Fact(msgspec.Struct, frozen=True, gc=False):
    phase: Phase
    subject: str
    values: dict[str, object]


type Evidence = Fact | BoundaryFault | DrainReceipt[object]
type RedactionSpec = Redaction | Map[str, Classification] | frozenset[str]
type Streamable = Receipt | Iterable[Receipt]
type Draining[**P] = Callable[P, Awaitable[DrainReceipt[object]]]
type ProcessorEvent = structlog.typing.EventDict
type Processor = structlog.typing.Processor
type WrappedLogger = structlog.typing.WrappedLogger
type BoundLogger = structlog.typing.FilteringBoundLogger


@runtime_checkable
class LevelEmit[R](Protocol):
    def __call__(self, event: str, **kwargs: object) -> R: ...


@runtime_checkable
class LoggerFactory(Protocol):
    def __call__(self, *args: object) -> WrappedLogger: ...


type LevelSelector[R] = Callable[[BoundLogger], LevelEmit[R]]
type LevelBinding = tuple[LevelSelector[object], LevelSelector[Awaitable[object]]]
type FormatBinding = tuple[tuple[Processor, ...], Callable[[], LoggerFactory]]


_LOGGER_NAME: Final = "maghz.runtime"
REDACTED: Final[str] = "***"
_REDACTION: Final[str] = "_redaction"
_ENCODE: Final[Callable[[object], bytes]] = msgspec.json.Encoder(enc_hook=repr, order="deterministic").encode
_PROCESS: Final[psutil.Process] = psutil.Process()
_PROCESS_FAULTS: Final[tuple[type[psutil.Error], ...]] = (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied)


@tagged_union(frozen=True)
class Receipt:
    tag: ReceiptTag = tag()
    fact: tuple[Phase, str, str, dict[str, object]] = case()
    rejected: tuple[str, BoundaryFault] = case()
    drained: tuple[str, DrainReceipt[object]] = case()

    @staticmethod
    def of(owner: str, evidence: Evidence) -> Receipt:

        match evidence:
            case Fact(phase=phase, subject=subject, values=facts):
                return Receipt(fact=(phase, owner, subject, facts))
            case BoundaryFault() as fault:
                return Receipt(rejected=(owner, fault))
            case DrainReceipt() as drain:
                return Receipt(drained=(owner, drain))
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed Evidence alias
                assert_never(unreachable)

    def project(self) -> tuple[LogLevel, EventDict]:

        match self.tag:
            case "fact":
                phase, owner, subject, facts = self.fact
                return PHASE_LEVEL[phase], {"event": phase, "owner": owner, "subject": subject, **facts}
            case "rejected":
                owner, fault = self.rejected
                return "warning", {"event": "rejected", "owner": owner, **fault.facts()}
            case "drained":
                owner, drain = self.drained
                return "info", {"event": "drained", "owner": owner, **_rss(), **drain.counts()}
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed ReceiptTag literal
                assert_never(unreachable)


class Redaction(msgspec.Struct, frozen=True):
    classified: Map[str, Classification]
    salt: bytes = b"maghz"

    @staticmethod
    def of(spec: RedactionSpec) -> Redaction:

        match spec:
            case Redaction():
                return spec
            case frozenset():
                return Redaction(classified=Map.of_seq([(str(key), "drop") for key in spec]))
            case Map():
                return Redaction(classified=spec)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed RedactionSpec union
                assert_never(unreachable)

    def apply(self, facts: Mapping[str, object]) -> EventDict:

        return {key: redacted for key, value in facts.items() if key != _REDACTION for redacted in self._classify(key, value)}

    def _classify(self, key: str, value: object) -> tuple[object, ...]:
        return self.classified.try_find(key).map(lambda cls: self._reduce(cls, value)).default_value((value,))

    def _reduce(self, classification: Classification, value: object) -> tuple[object, ...]:
        match classification:
            case "drop":
                return ()
            case "mask":
                return (REDACTED,)
            case "hash":
                return (blake2b(_ENCODE(value), key=self.salt, digest_size=8).hexdigest(),)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed Classification set
                assert_never(unreachable)


_OPEN: Final[Redaction] = Redaction(classified=Map.empty())


def _rss() -> EventDict:

    try:
        return {"rss_bytes": _PROCESS.memory_info().rss}
    except _PROCESS_FAULTS:
        return {}


def _stream(source: Streamable) -> Iterable[Receipt]:

    match source:
        case Receipt():
            return (source,)
        case _:
            return source


def _render(source: Streamable, spec: RedactionSpec) -> Iterator[tuple[LevelBinding, str, EventDict]]:

    redaction = Redaction.of(spec)
    for receipt in _stream(source):
        level, event = receipt.project()
        yield LEVEL_METHOD[level], str(event.pop("event")), event | {_REDACTION: redaction}


def _serialize(event: ProcessorEvent, **_: object) -> bytes:

    return _ENCODE(event)


def redact(_: object, __: str, event: ProcessorEvent) -> ProcessorEvent:

    return Option.of_optional(event.get(_REDACTION)).default_value(_OPEN).apply(event)


def trace_context(_: object, __: str, event: ProcessorEvent) -> ProcessorEvent:

    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event.update(trace_id=trace.format_trace_id(ctx.trace_id), span_id=trace.format_span_id(ctx.span_id), trace_flags=int(ctx.trace_flags))
    return event


class Signals:
    @staticmethod
    def configure(fmt: Format = "json", *, level: LogLevel = "info") -> None:

        render, factory = _FORMAT[fmt]
        structlog.configure(
            processors=[*_CHAIN, *render],
            wrapper_class=structlog.make_filtering_bound_logger(_LEVEL_NUMBER[level]),
            logger_factory=factory(),
            cache_logger_on_first_use=True,
        )

    @staticmethod
    def emit(source: Streamable, redaction: RedactionSpec = _OPEN, *, sink: BoundLogger | None = None) -> None:

        log = _sink(sink)
        for (sync, _), name, fields in _render(source, redaction):
            sync(log)(name, **fields)

    @staticmethod
    async def emit_async(source: Streamable, redaction: RedactionSpec = _OPEN, *, sink: BoundLogger | None = None) -> None:

        log = _sink(sink)
        for (_, amirror), name, fields in _render(source, redaction):
            await amirror(log)(name, **fields)


def _sink(sink: BoundLogger | None) -> BoundLogger:

    return Option.of_optional(sink).default_with(lambda: structlog.get_logger(_LOGGER_NAME).bind())


def drained[**P](owner: str, *, redaction: RedactionSpec = _OPEN) -> Callable[[Draining[P]], Draining[P]]:

    def _decorate(operation: Draining[P]) -> Draining[P]:
        @wraps(operation)
        async def _async(*args: P.args, **kwargs: P.kwargs) -> DrainReceipt[object]:
            drain = await operation(*args, **kwargs)
            await Signals.emit_async(Receipt.of(owner, drain), redaction)
            return drain

        return _async

    return _decorate


# Declared below `Redaction`/`drained` so the claw resolves both hints at decoration time.
async def feed(policy: LanePolicy, source: LaneSource, owner: str, redaction: Redaction) -> AsyncIterator[DrainReceipt[object]]:

    observed = drained(owner, redaction=redaction)(policy.drain)
    async for batch in _events(source):
        yield await observed(batch)


PHASE_LEVEL: Final[Map[Phase, LogLevel]] = Map.of_seq([("admitted", "debug"), ("retry", "warning"), ("emitted", "info")])
_LEVEL_NUMBER: Final[Map[LogLevel, int]] = Map.of_seq([("debug", 10), ("info", 20), ("warning", 30), ("error", 40)])
_CHAIN: Final[tuple[Processor, ...]] = (
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    trace_context,
    redact,
    structlog.processors.CallsiteParameterAdder(),
    structlog.processors.dict_tracebacks,
    structlog.processors.TimeStamper(fmt="iso"),
)
_FORMAT: Final[Map[Format, FormatBinding]] = Map.of_seq([
    (
        "json",
        (
            (structlog.processors.EventRenamer(to="body"), structlog.processors.JSONRenderer(serializer=_serialize)),
            lambda: structlog.BytesLoggerFactory(file=sys.stderr.buffer),
        ),
    ),
    ("console", ((structlog.dev.ConsoleRenderer(colors=False),), lambda: structlog.PrintLoggerFactory(file=sys.stderr))),
])
LEVEL_METHOD: Final[Map[LogLevel, LevelBinding]] = Map.of_seq([
    ("debug", (lambda log: log.debug, lambda log: log.adebug)),
    ("info", (lambda log: log.info, lambda log: log.ainfo)),
    ("warning", (lambda log: log.warning, lambda log: log.awarning)),
    ("error", (lambda log: log.error, lambda log: log.aerror)),
])


__all__ = [
    "Admit",
    "BoundaryFault",
    "Disposition",
    "DrainReceipt",
    "Fact",
    "LaneKey",
    "LanePolicy",
    "LaneSource",
    "Receipt",
    "Redaction",
    "RetryClass",
    "RetryMode",
    "RuntimeRail",
    "Signals",
    "async_boundary",
    "boundary",
    "feed",
    "guard",
    "guarded",
    "install",
    "lower",
    "spawn",
    "traversed",
]
