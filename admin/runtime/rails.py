"""The one boundary-fault family and the typed rail every runtime owner returns through.

`BoundaryFault` is the single closed tagged union discriminating the eight ingress classes; every
rail mints it directly (carrier-free), so there is no parallel `DbFault`/`CloudFault`/`N8nFault`.
`RuntimeRail[T] = Result[T, BoundaryFault]` is the one carrier; absence rides the `expression`
`Option` directly. `_convert` is the one fault-lift core backing `boundary` (sync), `async_boundary`
(awaitable), and the `@trapped` decorator — it folds a caught exception through `BoundaryFault.of`
(the ordered `CLASSIFY` `choose`/`try_head`/`default_with` first-match `Option` fold), records it on
the active OTel span, and returns `Error(BoundaryFault)`. Domain logic returns the rail and never
raises; exceptions convert exactly once at the owning boundary.

`CLASSIFY` is the sole conversion authority — a caught exception family maps to its fault leaf by one
ordered row, so a `TimeoutError` lands as `deadline`, an `ImportError` as `import_`, a codec break as
the subject-carrying `boundary`, a contract violation as `api`, a reached-non-200 `httpx.HTTPStatusError`
as the status-code-carrying `wire`, and an unclassified raise as `boundary`. The asyncssh rows are
load-bearing in order: every `DisconnectError` subtype shares one
base, so the auth-denial (`SSH_DENIED`) and the deterministic negotiation/integrity (`SSH_PROTOCOL`)
families scan before the `SSH_TRANSIENT` base row, leaving only a true peer disconnect for the
retryable `resource` row. `SSH_TRANSIENT`/`SSH_TERMINAL` are the one partition the resilience policy
table also reads, so retry-admission and classification can never disagree on an SSH fault.

`spawn` is the one subprocess boundary: `anyio.run_process(check=False)` under `guard(retry_class)`,
lifting the exhausted-retry escape through `async_boundary` and returning the `CompletedProcess` for
the caller to grade — every subprocess site (cloud/n8n/schema/sync and the remote git pair) composes it
rather than re-deriving the spawn/retry/lift chain or minting a parallel subprocess fault carrier.
`traversed` folds a `Block` of rails
under one `Disposition` (abort/accumulate/partition), the `@overload` arms carrying the per-disposition
output shape. `railed` is the bound `effect.result` do-notation builder for interleaved-bind chains
past the nested-`bind` threshold. `lower` is the one CLI seam collapsing a `RuntimeRail[Envelope]` to
the `Envelope` wire.
"""

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from functools import wraps
import inspect
from os import PathLike
from subprocess import CompletedProcess  # noqa: S404
from typing import (
    Any,  # noqa: TID251 - the `railed` ResultBuilder source axis types both the per-yield bind and the return_ payload (rationale at the `railed` definition)
    assert_never,
    Final,
    Literal,
    overload,
    TYPE_CHECKING,
)

import anyio
import asyncssh
from beartype.roar import BeartypeCallHintViolation
from expression import case, effect, Error, Nothing, Ok, Result, Some, tag, tagged_union
from expression.collections import Block
from httpx import HTTPStatusError
import msgspec
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from admin.core import Envelope, fault


if TYPE_CHECKING:
    from admin.runtime.resilience import RetryClass


# --- [TYPES] ---------------------------------------------------------------------------

type FaultTag = Literal["config", "resource", "deadline", "api", "import_", "wire", "boundary", "aggregate"]
type ClassifyRow = tuple[type[Exception] | tuple[type[Exception], ...], Callable[[str, BaseException], BoundaryFault]]
type Catch = type[BaseException] | tuple[type[BaseException], ...]
type StrPath = str | PathLike[str]
type Trapped[**P, T] = Callable[P, RuntimeRail[T]] | Callable[P, Awaitable[RuntimeRail[T]]]


class Disposition(StrEnum):
    """How `traversed` reduces a block of rails: abort on first, accumulate all, or partition both."""

    ABORT = "abort"  # bind-short-circuit to the first fault (dependent steps)
    ACCUMULATE = "accumulate"  # combine-fold every fault into one aggregate (independent operands)
    PARTITION = "partition"  # split ok/err into two blocks (a census, never a gate)


# --- [MODELS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class BoundaryFault:
    """The one closed boundary-failure family; every rail mints it directly, no per-rail carrier.

    Eight cases discriminate the ingress classes — `config`/`resource`/`api`/`import_`/`boundary`
    carry `(subject, detail)`, `deadline` carries `(subject, budget)`, `wire` carries `(subject, code)`
    for a numeric protocol/status discriminant, and `aggregate` carries `tuple[BoundaryFault, ...]` so
    an accumulating boundary keeps every member structurally addressable. The seven leaf constructors
    are the `CLASSIFY` table's builders, not seven hand-written factories: `of` `choose`s the first
    matching row through the `Option` fold; `wire`/`deadline` also admit explicit keyword construction
    at a fence that owns the scalar the caught exception lacks.
    """

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
        """Classify a caught exception to its `BoundaryFault` leaf through the ordered `CLASSIFY` fold.

        `choose` keeps the first row whose family matches, `try_head` reads it as an `Option`, and
        `default_with` supplies the `boundary` catch-all — totality is the `Option` fold, never a
        falsy-`None` `or` resting on `tagged_union` truthiness nor a `next(...)` that raises
        `StopIteration` when the catch-all row is edited away. The catch-all `detail` is
        `str(cause) or type(cause).__name__`, so an unclassified domain exception carrying a
        discriminating message preserves it into the `detail` slot the `facts()` egress and the
        receipts `rejected` projection carry, falling back to the class name only for a bare raise.

        Returns:
            The leaf the first matching `CLASSIFY` row mints, or the `boundary` leaf for an
            unclassified escape (unreachable while the `(Exception,)` catch-all row stands).
        """
        matched = CLASSIFY.choose(lambda row: Some(row[1](subject, cause)) if isinstance(cause, row[0]) else Nothing)
        return matched.try_head().default_with(lambda: BoundaryFault(boundary=(subject, str(cause) or type(cause).__name__)))

    @staticmethod
    def combine(left: BoundaryFault, right: BoundaryFault) -> BoundaryFault:
        """Fold two faults into one flat `aggregate` leaf, splicing existing aggregates (associative).

        Each side spreads to its members (an aggregate's tuple, or itself as a singleton) and the two
        spreads concatenate, so a nested aggregate flattens and a leaf wraps without a per-arm branch.
        The accumulating `traversed` disposition reduces a fault stream through this monoid.

        Returns:
            A `BoundaryFault(aggregate=...)` whose members are the leaf faults of both operands.
        """
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
        """Whether this fault (or any aggregate member) is in the recovery set, keyed on `FaultTag`.

        The membership test folds over the aggregate spine against the closed `FaultTag` vocabulary,
        so the recovery set is `frozenset[FaultTag]` rather than stringly `frozenset[str]`, and the
        test keys on the fault's own tag, never a reconstructed message.

        Returns:
            `True` when this fault's tag — or any member's, for an aggregate — is in `codes`.
        """
        match self:
            case BoundaryFault(tag="aggregate", aggregate=members):
                return any(member.recoverable(codes) for member in members)
            case _:
                return self.tag in codes

    def facts(self) -> dict[str, object]:
        """Project this fault to the flat structured-log fact map the receipts `rejected` emit spreads.

        The map element is `object`, not `str`: the `deadline` `budget: float` and `wire` `code: int`
        ride as native scalars the receipts `EventDict` (`dict[str, object]`) and its
        `enc_hook=repr` renderer serialize without a `str()` coerce — a pre-stringified `f"{budget:g}"`
        here is the deleted form. Only `members` joins to a comma-string because it names member tags
        rather than carrying one scalar. Dispatch is the structural match over the closed union: the five
        `(subject, detail)` leaves collapse to one OR-pattern arm binding `(subject, detail)` positionally
        per case, never a `getattr(self, self.tag)` escape that defeats the closed family. The post-match
        `raise` is the unreachable marker: the eight-case structural match is exhaustive, but the binding
        `ty` gate cannot narrow the opaque `tagged_union` residual to `Never` (it infers `@Todo` and
        rejects `assert_never`), so the explicit raise carries the proven totality the union match owns.

        Returns:
            A transient `dict` of `tag` plus the case-specific slots, consumed immediately by the
            receipt log pipeline and the `lower` CLI seam; never stored.

        Raises:
            AssertionError: Unreachable while the match is exhaustive over the closed `FaultTag` union;
                the totality marker fires only if a new fault case is added without its `facts()` arm.
        """
        match self:
            case BoundaryFault(tag="aggregate", aggregate=members):
                return {"tag": "aggregate", "subject": "aggregate", "members": ",".join(member.tag for member in members)}
            case BoundaryFault(tag="deadline", deadline=(subject, budget)):
                return {"tag": "deadline", "subject": subject, "budget": budget}
            case BoundaryFault(tag="wire", wire=(subject, code)):
                return {"tag": "wire", "subject": subject, "code": code}
            case (
                BoundaryFault(tag=tag_value, config=(subject, detail))
                | BoundaryFault(tag=tag_value, resource=(subject, detail))
                | BoundaryFault(tag=tag_value, api=(subject, detail))
                | BoundaryFault(tag=tag_value, import_=(subject, detail))
                | BoundaryFault(tag=tag_value, boundary=(subject, detail))
            ):
                return {"tag": tag_value, "subject": subject, "detail": detail}
        raise AssertionError(self.tag)  # pragma: no cover - exhaustive over the closed FaultTag union

    def headline(self) -> str:
        """Name this fault's `subject: cause` line by DECODING `facts()`, never a parallel cause match.

        The single cause-naming mint: `facts()` is the one total projection over the closed union, and
        this decodes it — `subject` plus the lone discriminating scalar (the `detail`/`budget`/`code`/
        `members` slot every case carries exactly one of beside `tag`/`subject`). The CLI `lower` seam
        and every rail that self-lowers a surviving `Error(BoundaryFault)` read this one line rather than
        re-deriving `f"{subject}: {detail}"` off a `facts()` rescan; the `str`/f-string coercion is the
        CLI string edge, distinct from the native-scalar `facts()` the structured-log renderer consumes.

        Returns:
            The `f"{subject}: {cause}"` line naming this fault's discriminating cause.
        """
        slots = self.facts()
        return f"{slots['subject']}: {next(value for key, value in slots.items() if key not in {'tag', 'subject'})}"


# --- [CONSTANTS] -----------------------------------------------------------------------

# The anyio worker/stream-resource break family lifting to the retryable `resource` leaf: a broken
# subinterpreter/process worker (the `spawn`/offload cold-start crash) and a broken/closed/failed
# memory-stream resource. A `BrokenWorkerInterpreter` crossing here is the budget-exhausted offload
# retry — a fresh transient retries at the lane's `guard` before the conversion ever sees it.
_WORKER_EXC: Final = (
    anyio.BrokenWorkerProcess,
    anyio.BrokenWorkerInterpreter,
    anyio.BrokenResourceError,
    anyio.ClosedResourceError,
    anyio.ConnectionFailed,
)
# Auth-denial terminus: the three `DisconnectError` subtypes a credential/host-key/username rejection
# raises. They scan before `SSH_TRANSIENT` (which carries the `DisconnectError` base) so a denied auth
# never classifies as retryable `resource`.
_SSH_DENIED: Final = (asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable, asyncssh.IllegalUserName)
# Deterministic transport-negotiation/integrity faults (`<: DisconnectError`): a re-handshake fails
# identically and `MACError` signals tampering, so these are non-retryable `boundary`, never `resource`.
# They scan before `SSH_TRANSIENT` to escape the base-class capture.
_SSH_PROTOCOL: Final = (
    asyncssh.KeyExchangeFailed,
    asyncssh.MACError,
    asyncssh.CompressionError,
    asyncssh.ProtocolError,
    asyncssh.ProtocolNotSupported,
    asyncssh.ServiceNotAvailable,
)
# The ONE owner of "which asyncssh fault is retryable". `SSH_TRANSIENT`: an unexpected peer disconnect
# (`ConnectionLost`/the `DisconnectError` base) or a channel-open rejection, retryable once the terminal
# subtypes are peeled off the `DisconnectError` subtree. `SSH_TERMINAL`: every deterministic
# non-retryable subtype (auth-denial + protocol/integrity), all `<: DisconnectError`, so a retry
# predicate admitting the `DisconnectError` base subtracts `SSH_TERMINAL` to abort them on the first
# attempt. `resilience.POLICY` consumes both (never re-declaring the partition), so the retry boundary
# and the classification boundary can never disagree on a given fault.
SSH_TRANSIENT: Final[tuple[type[asyncssh.Error], ...]] = (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError)
SSH_TERMINAL: Final[tuple[type[asyncssh.Error], ...]] = (*_SSH_DENIED, *_SSH_PROTOCOL)


# --- [OPERATIONS] ----------------------------------------------------------------------

type RuntimeRail[T] = Result[T, BoundaryFault]


def _convert(subject: str, cause: BaseException) -> BoundaryFault:
    """The one conversion: classify the exception, record it on the active OTel span, return the fault.

    The fault is recorded on whatever span is currently recording (a no-op when none records), so a
    boundary breach is visible in the distributed trace without this owner ever minting, activating, or
    ending a span — span lifecycle stays with the measured operation.

    Returns:
        The `BoundaryFault` leaf, recorded on the active span when one is recording.
    """
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
    """Call `thunk`, lifting any caught escape to the `BoundaryFault` rail via the `CLASSIFY` fold.

    `catch` narrows the caught surface to a real multi-class engine fault tuple where a fence owns a
    disjoint backend root set, defaulting to `Exception` as the total classification catch-all.

    Args:
        subject: The boundary identity stamped into the minted fault's `subject` slot.
        thunk: The fallible synchronous unit of work whose escape is classified.
        catch: The exception class or tuple this fence catches; `Exception` by default.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the first `CLASSIFY` family match.
    """
    return _guard(subject, thunk, catch)


async def async_boundary[T](subject: str, thunk: Callable[[], Awaitable[T]], *, catch: Catch = Exception) -> RuntimeRail[T]:
    """Await `thunk`, lifting any caught escape to the `BoundaryFault` rail via the `CLASSIFY` fold.

    The awaitable sibling of `boundary`: a synchronous compute and a subprocess/offload seam share one
    `_convert` conversion rather than a second async rail.

    Args:
        subject: The boundary identity stamped into the minted fault's `subject` slot.
        thunk: The fallible awaitable-returning unit of work whose escape is classified.
        catch: The exception class or tuple this fence catches; `Exception` by default.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the first `CLASSIFY` family match.
    """
    try:
        return Ok(await thunk())
    except catch as cause:
        return Error(_convert(subject, cause))


def trapped[**P, T](subject: str, *, catch: Catch = Exception) -> Callable[[Callable[P, T]], Trapped[P, T]]:
    """Wrap a raising `def`/`async def` so any escape lifts to `BoundaryFault` through `CLASSIFY`.

    The decorator form of `boundary`/`async_boundary`, dispatching on `inspect.iscoroutinefunction` so
    one aspect covers both call shapes and collapses the inline `try`/`except` boundary fences a
    consumer otherwise repeats per op. `functools.wraps` preserves the name/parameter signature, but its
    copied `return` annotation is overwritten with `RuntimeRail` on the wrapper: the wrapper returns the
    rail, not the wrapped op's `T`, so under the `admin.*` package beartype claw the return check
    validates the honest rail contract instead of rejecting the lifted `Result` against the original
    `-> T`. The result is the `Trapped` union — a sync `fn` yields a `Callable[P, RuntimeRail[T]]` the
    caller invokes directly; an `async def fn` yields a `Callable[P, Awaitable[RuntimeRail[T]]]` the
    caller awaits — so the async branch's coroutine return is typed honestly rather than a uniform
    signature that erases the await.

    Args:
        subject: The boundary identity stamped into every minted fault's `subject` slot.
        catch: The exception class or tuple every minted fence catches; `Exception` by default.

    Returns:
        A decorator lifting the wrapped op's result to the rail; sync-direct or async-awaitable per `fn`.
    """

    def decorate(fn: Callable[P, T]) -> Trapped[P, T]:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def awaited(*args: P.args, **kwargs: P.kwargs) -> RuntimeRail[T]:
                return await async_boundary(subject, lambda: fn(*args, **kwargs), catch=catch)

            awaited.__annotations__["return"] = RuntimeRail
            return awaited

        @wraps(fn)
        def called(*args: P.args, **kwargs: P.kwargs) -> RuntimeRail[T]:
            return _guard(subject, lambda: fn(*args, **kwargs), catch)

        called.__annotations__["return"] = RuntimeRail
        return called

    return decorate


async def spawn(
    argv: tuple[str, ...],
    *,
    subject: str,
    retry_class: RetryClass | None = None,
    env: Mapping[str, str] | None = None,
    cwd: StrPath | None = None,
    stdin: bytes | None = None,
) -> RuntimeRail[CompletedProcess[bytes]]:
    """Run one subprocess under `check=False`, retried by `guard(retry_class)`, lifting escapes to the rail.

    The one subprocess boundary the rails compose: `anyio.run_process(check=False)` owns the spawn and
    never raises on a non-zero exit, so the returned `CompletedProcess` carries `returncode`/`stdout`/
    `stderr` for the caller to grade (an rclone `0`/`9` success, a `docker exec` non-zero fault) — the
    exit-to-fault mapping is the caller's domain logic, while the spawn-flap/retry/lift chain is owned
    here once. A missing binary or transient spawn fault raises `OSError`; `guard(retry_class)` replays
    it within the named policy budget before the exhausted escape crosses `async_boundary` to the
    `boundary`/`resource` leaf. A `None` retry class runs the bare spawn unguarded.

    Args:
        argv: The full command and its arguments.
        subject: The boundary identity stamped into a lifted fault's `subject` slot.
        retry_class: The `RetryClass` whose policy guards a transient spawn flap, or `None` to run bare.
        env: The process environment block, or `None` to inherit.
        cwd: The working directory, or `None` for the invocation cwd.
        stdin: The bytes piped to the process stdin, or `None`.

    Returns:
        `Ok(CompletedProcess)` carrying the graded exit (the caller inspects `returncode`), or
        `Error(BoundaryFault)` for an exhausted spawn flap lifted at this boundary.
    """

    async def run() -> CompletedProcess[bytes]:
        return await anyio.run_process(argv, input=stdin, env=env, cwd=cwd, check=False)

    if retry_class is None:
        return await async_boundary(subject, run)
    # deferred to break the resilience->rails edge (resilience imports SSH_TRANSIENT/SSH_TERMINAL here) and keep the bare-spawn path resilience-free
    from admin.runtime.resilience import guard  # noqa: PLC0415

    return await async_boundary(subject, lambda: guard(retry_class)(run))


@overload
def traversed[T](rails: Block[RuntimeRail[T]], *, by: Literal[Disposition.ABORT, Disposition.ACCUMULATE] = ...) -> RuntimeRail[Block[T]]: ...
@overload
def traversed[T](rails: Block[RuntimeRail[T]], *, by: Literal[Disposition.PARTITION]) -> RuntimeRail[tuple[Block[T], Block[BoundaryFault]]]: ...
def traversed[T](
    rails: Block[RuntimeRail[T]], *, by: Disposition = Disposition.ABORT
) -> RuntimeRail[Block[T]] | RuntimeRail[tuple[Block[T], Block[BoundaryFault]]]:
    """Fold a block of rails to one rail, the `Disposition` choosing abort/accumulate/partition.

    `ABORT` binds left-to-right and short-circuits the first `Error` (dependent steps where only the
    first failure matters). `ACCUMULATE` reduces every fault through `BoundaryFault.combine` into one
    `aggregate` leaf and keeps the ok values only when all succeed (independent operands). `PARTITION`
    always succeeds, splitting the ok values and the leaf faults into two blocks (a census, not a gate).
    `ACCUMULATE` and `PARTITION` share one match arm and one pair of `choose` projections — `to_option`
    drains the values, `swap().to_option()` drains the faults — folding the rails once rather than
    re-spelling two `partition` passes per arm. The `@overload` rows carry the per-disposition output
    shape so the caller narrows on the literal it passes, never on the runtime union.

    Args:
        rails: The block of independent or dependent rails to fold.
        by: The accumulation discipline; the correctness decision fixed at the boundary.

    Returns:
        `Ok(Block[T])` of the values (`ABORT`/`ACCUMULATE`), `Error(BoundaryFault)` of the first or
        aggregated fault, or `Ok((oks, faults))` for `PARTITION`.
    """
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


# --- [COMPOSITION] ---------------------------------------------------------------------

# Ordered first-match exception classification: each row pairs an exception family with the leaf
# builder it mints. `BoundaryFault.of` `choose`s the first row whose family `isinstance`-matches, so the
# order is load-bearing — the `(Exception,)` catch-all is last and the asyncssh rows sit immediately
# before `(OSError,)`. `TimeoutError` precedes the worker/`OSError` rows so a timeout lands `deadline`
# rather than coalescing into `resource`. `import_` is the dual-band gated-import failure leaf; the
# msgspec codec rows fold to the subject-carrying `boundary` (no numeric code in hand, so not `wire`),
# while a reached-but-non-200 `httpx.HTTPStatusError` (a `raise_for_status` on the n8n REST leg) lands
# `wire` carrying the native `response.status_code` int — the numeric protocol discriminant the egress
# fact preserves rather than stringifying into `boundary`; transport-transient `httpx.ConnectError`/
# `RemoteProtocolError` are disjoint (not `HTTPStatusError`) and ride the resilience `HTTP` retry then
# the `(Exception,)`/`(OSError,)` `boundary` floor past budget. The SSH denial/protocol families scan
# ahead of the transient base to escape its `DisconnectError` capture. This is the SOLE conversion
# authority: a new family is one new row, never a `catch` parameter or a parallel function. Builders read
# `type(cause).__name__` where the exception TYPE is the discriminant (a `DecodeError`/
# `BeartypeCallHintViolation` class name), since their message is noise; the `of` catch-all keeps the
# message where it discriminates an unclassified domain raise. The `wire` row's builder is the one
# typed-payload narrowing (every other row reads `BaseException`-total `str`/`__name__`): the `of` fold
# fires it only on an `HTTPStatusError`, the guard narrows for `ty` to read the native `status_code` int,
# and the unreachable `0` floor mirrors the bare-`TimeoutError` row's `0.0` budget floor.
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

# Bound do-notation builder for sequential `value = yield from rail` chains over the BoundaryFault rail;
# the one effect builder past the nested-`bind` threshold, reused across every decorated comprehension.
# The value axis is `Any`: the `ResultBuilder`'s single source parameter types both each `yield from`
# bind result and the `return_` payload, so a chain binding heterogeneous leaf values yet returning a
# distinct aggregate erases here and carries its precise per-step types at the consumer's own generator,
# rather than `object` forcing every bind site to re-narrow an unusable value.
railed = effect.result[Any, BoundaryFault]()


def lower(rail: RuntimeRail[Envelope]) -> Envelope:
    """Lower a domain `RuntimeRail[Envelope]` to the CLI `Envelope`, mapping a `BoundaryFault` to `fault`.

    The single CLI seam: an `Ok` carries its rail `Envelope`; an `Error(BoundaryFault)` projects the
    fault's `headline()` cause line into the `fault(...)` error slot and spreads its `facts()` map as the
    string-coerced context. The discriminant pick lives once on `BoundaryFault.headline()` (which decodes
    the one `facts()` projection), so this seam never re-spells `f"{subject}: {detail}"` — every command
    handler binds this and every self-lowering rail composes `headline()`/`facts()` rather than re-deriving
    the cause. The str-coerce is the CLI string-envelope edge (`error_context: Mapping[str, str]`),
    distinct from the receipts native-scalar `facts()` path.

    Args:
        rail: The domain rail whose success carries an `Envelope` and whose error is a `BoundaryFault`.

    Returns:
        The carried `Envelope` on success, or a `fault` envelope projected from the boundary fault.
    """
    match rail:
        case Result(tag="ok", ok=envelope):
            return envelope
        case Result(error=boundary_fault):
            return fault(boundary_fault.headline(), {key: str(value) for key, value in boundary_fault.facts().items()})
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed Result(Ok | Error) union
            assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "CLASSIFY",
    "SSH_TERMINAL",
    "SSH_TRANSIENT",
    "BoundaryFault",
    "Catch",
    "Disposition",
    "FaultTag",
    "RuntimeRail",
    "async_boundary",
    "boundary",
    "lower",
    "railed",
    "spawn",
    "trapped",
    "traversed",
]
