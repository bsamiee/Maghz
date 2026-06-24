"""Resilience owner: one retry-class `StrEnum` over a structurally-total `stamina` policy table.

`RetryClass` keys every transient-boundary policy; `POLICY` carries exactly one `Policy` row per
member, so totality is structural rather than defensive — a `Map` miss can only mean a member was
added without its row. Each member binds one frozen `Policy` (`attempts`, `timeout`, the `_Target`
exception/backoff discriminator, and four `UNSET`-defaulting `wait_*` backoff columns) resolved
through `.policy`. `Policy.schedule` is the one projection folding the present (non-`UNSET`) `wait_*`
columns onto `attempts`/`timeout` into the `**`-passable `Schedule` TypedDict, so the bound-caller
build and the inline `retry_context` read one source and never re-spell `attempts=…, timeout=…,
wait_*=…` twice. The named-key `TypedDict` is load-bearing: only it makes the `**`-spread type-check
against `stamina`'s typed keyword signature, where a `dict[str, object]` projection spreads values the
caller rejects. `target` stays off the schedule — the callers apply it through `.on(...)`, the iterator
through `on=`.

`target` is the full `stamina` discriminator over one axis: a bare exception tuple, or a `_Target`
backoff hook a class whose transient needs a predicate binds. `_retry_after(*transient, exclude=...)`
is the one reusable hook factory — it honours a server-directed `Retry-After` delay (an exception
satisfying the host-neutral `RetryAfter` structural protocol the transport boundary populates from a
`429`/`503` header) by returning the delay seconds so `stamina` waits exactly that long before falling
through to the exponential schedule on its `bool` transient match, and subtracts an `exclude` subtree
(the terminal asyncssh family) so a deterministic auth/negotiation fault aborts on the first attempt.
A class needing distinct backoff geometry sets its own `wait_*` column on its row, never a tuning
parameter threaded through `guarded`/`retrying`.

The triad is three `stamina` application shapes over the one row, with `guarded` the primary consumer
envelope: `guarded(cls, fn, *args, subject)` fuses the member-cached bound caller around `fn` and lifts
the terminal raise through the `rails` `async_boundary` exactly once into a `RuntimeRail[T]`, so every
fetch-shaped leg delegates the retry+lift pair rather than re-spelling `async_boundary(subject, lambda:
guard(cls)(...))` inline. `guard(cls)` is the lower bare `BoundAsyncRetryingCaller` `guarded` builds on,
memoised per member — the public entry for the one consumer that owns its own rail (the lanes `retried`
admission row binds it as a per-unit aspect inside its own railed drain, where a second `guarded`
boundary would double the lane's rail). `retrying(cls)` rebuilds the one-shot `retry_context` per call
for inline blocks the caller cannot pre-shape as a coroutine; `guarded_sync`/`guard_sync` are the
synchronous mirror over `boundary`, one row's two runtime arms — never a hand-rolled `sleep` loop.

`install(mode)` owns the one process-global `set_on_retry_hooks` registration: `RETRY_HOOKS` weaves
the `retry`-phase receipt fact (carrying a child span that wraps the scheduled wait) and the structlog
warning from one `RetryDetails` payload, so the receipt, the span status, and the warning mint once
from one source. It is total over `RetryMode` — `EMIT` registers the stack, `SILENT` the empty
iterable, `TEST` collapses backoff through `set_testing(True)` *and* registers `()` so a deterministic
spec is both fast and quiet rather than inheriting whatever a prior install last left in the
process-global hook table.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from enum import StrEnum
import functools
from typing import assert_never, Final, NotRequired, Protocol, runtime_checkable, TypedDict

from expression.collections import Map
import httpx
from msgspec import Struct, UNSET, UnsetType
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import pg8000
import stamina
import stamina.instrumentation
from stamina.typing import RetryDetails

from admin.runtime.rails import async_boundary, boundary, RuntimeRail, SSH_TERMINAL, SSH_TRANSIENT


# --- [TYPES] ---------------------------------------------------------------------------

# `stamina`'s `on=` discriminator (an exception class, a tuple of classes, or a backoff hook returning
# `bool`/`float`/`timedelta` for the Retry-After pattern) is `stamina._core.ExcOrBackoffHook`, and
# neither it nor `stamina._core.BackoffHook` is re-exported off `stamina`/`stamina.typing`, so this
# local alias is the canonical owner of `Policy.target` and the `_retry_after` hook return.
type _Target = type[Exception] | tuple[type[Exception], ...] | Callable[[Exception], bool | float | timedelta]


@runtime_checkable
class RetryAfter(Protocol):
    """The host-neutral server-rate-limit slot a transport boundary populates from a `429`/`503` header.

    `_retry_after` reads this typed slot rather than introspecting a provider response shape: the
    transport owner maps the `Retry-After` header onto `retry_after` once at the edge, and resilience
    matches the protocol structurally to honour the server-directed delay. `@runtime_checkable` so the
    `_retry_after` backoff hook's `case RetryAfter(...)` narrowing works and the package beartype claw
    can admit the protocol in any annotation position.
    """

    retry_after: float | None


@runtime_checkable
class OnRetry(Protocol):
    """The on-retry hook contract: a sync callable that may return a context manager spanning the wait.

    Structurally identical to `stamina.typing.RetryHook` but `@runtime_checkable`, so the package
    beartype claw can check a hook-returning factory — the stamina `Protocol` is not runtime-checkable
    and is uncheckable in any claw-decorated annotation position (a def return or a module global).
    """

    def __call__(self, details: RetryDetails) -> AbstractContextManager[None] | None:
        """Record one scheduled retry from its `RetryDetails`, optionally spanning the wait."""
        ...


class RetryClass(StrEnum):
    """The closed set of transient-boundary retry classes, one `POLICY` row each, resolved via `.policy`."""

    DB = "db"
    HTTP = "http"
    PROC = "proc"

    @property
    def policy(self) -> "Policy":  # noqa: UP037 - `Policy` is declared below in `[MODELS]`; the forward-ref quote is load-bearing
        """Resolve this member's one structurally-total `POLICY` row."""
        return POLICY[self]


class RetryMode(StrEnum):
    """The closed set of retry-instrumentation install modes `install` dispatches over with `assert_never`."""

    EMIT = "emit"
    SILENT = "silent"
    TEST = "test"


class Schedule(TypedDict):
    """The `**`-passable `stamina` schedule columns `Policy.schedule` projects; `wait_*` optional.

    Mirrors the `stamina` caller/`retry_context` keyword schema so the `**`-spread type-checks each
    column against the target signature statically — a `dict[str, object]` projection spreads as
    `object`-typed values the typed `stamina` `__init__`/`retry_context` reject, so the named-key
    `TypedDict` is the one `**`-spreadable carrier the gate admits. `target` is bound separately through
    `.on(...)`/`on=` and is not a member. Each `wait_*` is `NotRequired`: an absent column defers to the
    `stamina` default rather than overriding it.
    """

    attempts: int
    timeout: float
    wait_initial: NotRequired[float]
    wait_max: NotRequired[float]
    wait_jitter: NotRequired[float]
    wait_exp_base: NotRequired[float]


# --- [MODELS] --------------------------------------------------------------------------


class Policy(Struct, frozen=True):
    """One frozen retry row: the bound `target` plus the `stamina` schedule columns.

    `target` carries exception types and backoff callables; the row is never wire-serialized, so the
    `msgspec.Struct` only ever holds them. Absent (`UNSET`) `wait_*` columns defer to the `stamina`
    default, distinct from a column the row explicitly sets — the `UNSET` sentinel is dropped from the
    `schedule` projection so "use the default" and "set to a value" never collapse.
    """

    attempts: int
    timeout: float
    target: _Target
    wait_initial: float | UnsetType = UNSET
    wait_max: float | UnsetType = UNSET
    wait_jitter: float | UnsetType = UNSET
    wait_exp_base: float | UnsetType = UNSET

    @property
    def schedule(self) -> Schedule:
        """Project `attempts`/`timeout` and the set `wait_*` columns to one `**`-passable `Schedule`.

        `attempts`/`timeout` seed the `Schedule` and each set `wait_*` column lands under its own named
        key — the per-key form is load-bearing, not the deleted `_WAIT_COLUMNS` comprehension: only a
        `TypedDict` whose keys statically match makes the `**`-spread type-check against `stamina`'s
        signature, where a `dict[str, object]`/`dict[str, float | int]` projection spreads `object`-typed
        values the typed `stamina` `__init__`/`retry_context` reject. `target` is the binding axis, not a
        schedule column — `guard`/`guard_sync` apply it through `.on(...)` and `retrying` through `on=`,
        so it stays off this dict, which all three spread once. An `UNSET` column is omitted so the
        `stamina` default stands, distinct from a column the row sets.

        Returns:
            A `Schedule` carrying `attempts`/`timeout` plus every set (`float`, non-`UNSET`) `wait_*`
            column; absent columns defer to the `stamina` default.
        """
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


# --- [SERVICES] ------------------------------------------------------------------------

# The one tracer handle, resolved once off the proxy-until-install provider (a `ProxyTracer` until an
# observability SDK installs a real provider, so the import and every span are no-ops until then). The
# retry child span the on-retry hook opens around each scheduled wait is minted here, so a retry is a
# child of the measured span the guarded call already opened — the span the `rails` `_convert` records
# the terminal raise on when the budget exhausts.
_TRACER: Final = trace.get_tracer("maghz.runtime.resilience")


# --- [OPERATIONS] ----------------------------------------------------------------------


def _retry_after(*transient: type[Exception], exclude: tuple[type[Exception], ...] = ()) -> _Target:
    """Build a `Retry-After`-honouring backoff hook over a transient set minus an excluded subtree.

    The one reusable `_Target` factory for a class whose transient needs a predicate. The returned hook
    is total over the caught exception: a `RetryAfter`-satisfying fault (the transport boundary mapped a
    `429`/`503` `Retry-After` header onto its typed `retry_after` slot) returns the server-directed delay
    in seconds so `stamina` waits exactly that long; any other fault returns a `bool` transient match so
    the `stamina` exponential schedule owns the wait — exactly bare-tuple semantics for the non-rate-
    limited path. `exclude` subtracts a terminal subtree captured through a transient base class: the
    fused HTTP/SSH `target` admits the `DisconnectError` base through `SSH_TRANSIENT`, so excluding
    `SSH_TERMINAL` aborts a denied auth / negotiation / integrity fault on the first attempt rather than
    retrying a fault a re-handshake cannot clear. The retry-admission set and the `rails.CLASSIFY` set
    read the one `SSH_TRANSIENT`/`SSH_TERMINAL` partition, so this hook and the classifier agree on every
    SSH fault by construction. A `None` `retry_after` slot falls through to the transient `bool`.

    Args:
        transient: The transient exception families a non-rate-limited match admits for retry.
        exclude: A terminal subtree to subtract — a class captured through a `transient` base whose
            deterministic faults must abort on the first attempt.

    Returns:
        A backoff hook returning the server-directed delay for a `RetryAfter` fault, else the `bool`
        transient match with the excluded subtree removed.
    """

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
    """Build the `stamina` on-retry hook weaving one `retry`-phase receipt and a child span per retry.

    The `RetryHook` is a synchronous callable even on the async retry path, so the receipt mints through
    the sync `Signals.emit`, never the loop-only `emit_async` mirror. The native `retry_num: int` and
    `wait_for`/`waited_so_far: float` land straight on the `dict[str, object]` facts map — the receipts
    `enc_hook=repr`/`order="deterministic"` renderer owns the JSON coercion, so a numeric fact reaches
    the line as a number rather than a pre-`str()`-formatted string; `caused_by` is the single cause
    render both the fact and the span status read, named once by `__qualname__`. The hook returns the
    `trace.use_span` context manager wrapping the scheduled wait, so each retry is an `ERROR`-status
    child span entered when scheduled and exited before the retry runs — a no-op span until an
    observability SDK installs a real provider, lit by the same proxy the receipts injector reads.

    Returns:
        The on-retry hook the `RetryReceiptHook` factory builds lazily on the first scheduled retry.
    """
    from admin.runtime.receipts import Receipt, Signals  # noqa: PLC0415 - deferred to break the resilience->receipts->lanes->resilience import cycle

    @contextmanager
    def hook(details: RetryDetails) -> Iterator[None]:
        cause = type(details.caused_by).__qualname__
        facts: dict[str, object] = {
            "retry_num": details.retry_num,
            "wait_for": details.wait_for,
            "waited_so_far": details.waited_so_far,
            "caused_by": cause,
        }
        Signals.emit(Receipt.of("resilience", ("retry", details.name, facts)))
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


# The lower bare bound caller, memoised per member off the row's keyword schedule (each `__call__` opens
# a fresh internal `retry_context`, so the binding is paid once and reused). `guarded` is the primary
# fetch-leg entry built on it; the lanes `retried` admission row binds this bare caller as a per-unit
# retry aspect inside its own already-railed drain, where a second `guarded` boundary would double the
# rail. The inline `retry_context` iterator is one-shot and rebuilt per call in `retrying` — never cached.
@functools.cache
def guard(cls: RetryClass) -> stamina.BoundAsyncRetryingCaller:
    """The memoised bound async retrying caller for one retry class; its policy is frozen at build.

    Args:
        cls: The retry class whose `POLICY` row binds the caller's schedule and exception target.

    Returns:
        A reusable `BoundAsyncRetryingCaller`; call it as `await guard(cls)(afn, *args, **kwargs)`.
        Repeated calls for the same class return the same cached instance.
    """
    row = cls.policy
    return stamina.AsyncRetryingCaller(**row.schedule).on(row.target)


# The sync mirror of `guard`, memoised per member off the same `Policy.schedule` source, so the sync and
# async callers are one row's two runtime arms rather than two policy tables. The one entry a synchronous
# transient-failure boundary that cannot be shaped as a coroutine delegates to (through `guarded_sync`).
@functools.cache
def guard_sync(cls: RetryClass) -> stamina.BoundRetryingCaller:
    """The memoised bound sync retrying caller for one retry class; its policy is frozen at build.

    Args:
        cls: The retry class whose `POLICY` row binds the caller's schedule and exception target.

    Returns:
        A reusable `BoundRetryingCaller`; call it as `guard_sync(cls)(fn, *args, **kwargs)`.
    """
    row = cls.policy
    return stamina.RetryingCaller(**row.schedule).on(row.target)


def retrying(cls: RetryClass) -> AsyncIterator[stamina.Attempt]:
    """Build one fresh `retry_context` iterator for an inline retry block over a retry class.

    Args:
        cls: The retry class whose `POLICY` row supplies the context schedule and target.

    Returns:
        A fresh single-use `stamina.retry_context`; consume it once with `async for attempt in ...`,
        reading `attempt.num`/`attempt.next_wait` natively. A one-shot iterator silently exhausts on a
        second drive, which is why it is rebuilt per call rather than cached like `guard`.
    """
    row = cls.policy
    return stamina.retry_context(on=row.target, **row.schedule)


async def guarded[T](cls: RetryClass, fn: Callable[..., Awaitable[T]], *args: object, subject: str, **kwargs: object) -> RuntimeRail[T]:
    """Drive `fn` under the member-cached caller and lift the terminal raise to `RuntimeRail[T]` once.

    The one fused consumer envelope, parameterized over the `(fn, *args, **kwargs)` input and the
    `RuntimeRail[T]` output: a budget-exhausted transient class surfaces as the `CLASSIFY`-classified
    `BoundaryFault` naming the final cause, and a non-transient raise the row never named surfaces
    immediately, the call site deciding recovery against its own code set. Every fetch-shaped leg
    delegates the retry+lift pair here rather than composing a bare `guard(cls)` caller inside its own
    `async_boundary` fence (the doubled-lift form); the lanes `retried` admission row is the sole
    legitimate bare-`guard` consumer, already railed by its own drain.

    Args:
        cls: The retry class whose `POLICY` row binds the caller.
        fn: The fallible async unit of work driven under the caller.
        args: Positional arguments forwarded to `fn`.
        subject: The boundary identity stamped into a minted fault's `subject` slot.
        kwargs: Keyword arguments forwarded to `fn`.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the terminal raise the retry budget
        could not clear, classified through the `rails` `CLASSIFY` table.
    """
    with _TRACER.start_as_current_span("resilience.guarded", attributes={"maghz.retry_class": cls.value}):
        return await async_boundary(subject, lambda: guard(cls)(fn, *args, **kwargs))


def guarded_sync[T](cls: RetryClass, fn: Callable[..., T], *args: object, subject: str, **kwargs: object) -> RuntimeRail[T]:
    """The synchronous mirror of `guarded`: the same retry+terminal-lift pair over `guard_sync`/`boundary`.

    The one entry a synchronous transient-failure boundary delegates to, never a hand-opened
    `stamina.retry_context` block at the call site (the single-policy-table deleted form).

    Args:
        cls: The retry class whose `POLICY` row binds the caller.
        fn: The fallible synchronous unit of work driven under the caller.
        args: Positional arguments forwarded to `fn`.
        subject: The boundary identity stamped into a minted fault's `subject` slot.
        kwargs: Keyword arguments forwarded to `fn`.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the terminal raise the retry budget
        could not clear, classified through the `rails` `CLASSIFY` table.
    """
    with _TRACER.start_as_current_span("resilience.guarded", attributes={"maghz.retry_class": cls.value}):
        return boundary(subject, lambda: guard_sync(cls)(fn, *args, **kwargs))


def install(mode: RetryMode = RetryMode.EMIT) -> None:
    """Flip the one process-global retry instrumentation to a closed `RetryMode`, total over the enum.

    `EMIT` registers the composed `RETRY_HOOKS` stack (the receipt fact plus the structlog warning) in
    one `set_on_retry_hooks`; `SILENT` passes the empty iterable to deactivate instrumentation; `TEST`
    calls `set_testing(True)` to collapse backoff and cap attempts *and* registers `()` so a
    deterministic spec runs fast and silent rather than inheriting a prior install's hook table.
    Production code branches on neither `is_active` nor `is_testing`.

    Args:
        mode: The install mode whose action runs against the process-global hook table.
    """
    match mode:
        case RetryMode.EMIT:
            stamina.instrumentation.set_on_retry_hooks(RETRY_HOOKS)
        case RetryMode.SILENT:
            stamina.instrumentation.set_on_retry_hooks(())
        case RetryMode.TEST:
            stamina.set_testing(True)
            stamina.instrumentation.set_on_retry_hooks(())
        case _ as unreachable:
            assert_never(unreachable)


# --- [TABLES] --------------------------------------------------------------------------

# One structurally-total policy row per `RetryClass` member. `DB` retries a transient `pg8000.Error`
# connection-loss / `OSError` re-dial (an in-flight query fault is tagged non-retryably in `db.py` and
# never reaches `guard`); `PROC` the transient subprocess-spawn `OSError`. A class needing distinct backoff
# geometry sets its own `wait_*` column on its row, never a tuning parameter threaded through
# `guarded`/`retrying`. There is no secret-unlock retry class: secrets resolve from the op-injected
# environment alone, never a macOS keychain handshake, so no `keyring` unlock leg exists to retry.
#
# `HTTP` is the one fused-transport band — Ollama-pull streams, n8n REST, and VPS SSH/SFTP reconnects
# share it — so its `target` is the `_retry_after` backoff hook, not a bare tuple, for two reasons. (1)
# It honours a server-directed `Retry-After` (a rate-limited n8n/Ollama `429`/`503`) over the exponential
# schedule once the transport boundary populates the `RetryAfter` slot. (2) `httpx.ConnectError`/
# `RemoteProtocolError` and the asyncssh transients are NOT `OSError` subclasses (`asyncssh.Error` derives
# straight from `Exception`, the httpx transients from `httpx.HTTPError`), so they are named explicitly
# beside `OSError` (which subsumes the `ConnectionError`/`TimeoutError`/socket re-dial surface); and every
# terminal asyncssh fault derives from `DisconnectError`, admitted through `SSH_TRANSIENT`'s base, so the
# hook subtracts `SSH_TERMINAL` to abort a denied auth / negotiation / integrity fault on the first
# attempt. The retry-admission set and `rails.CLASSIFY` read the ONE `SSH_TRANSIENT`/`SSH_TERMINAL`
# partition, so a fault can never be "retry" here and "terminal" there.
_HTTP_TARGET: Final[_Target] = _retry_after(httpx.ConnectError, httpx.RemoteProtocolError, *SSH_TRANSIENT, OSError, exclude=SSH_TERMINAL)

POLICY: Final[Map[RetryClass, Policy]] = Map.of_seq([
    (RetryClass.DB, Policy(attempts=4, timeout=30.0, target=(pg8000.Error, OSError), wait_initial=0.1, wait_max=3.0)),
    (RetryClass.HTTP, Policy(attempts=5, timeout=60.0, target=_HTTP_TARGET, wait_initial=0.2, wait_max=5.0)),
    (RetryClass.PROC, Policy(attempts=3, timeout=45.0, target=(OSError,), wait_initial=0.1, wait_max=4.0)),
])


# --- [COMPOSITION] ---------------------------------------------------------------------

# The one on-retry signal: a RetryHookFactory whose built hook mints the receipt fact and the child
# span from one RetryDetails payload (lazy build per the factory contract, so the receipts import is
# deferred to the first scheduled retry and the resilience->receipts->lanes->resilience cycle stays
# unbroken). The hook returns the span context manager wrapping the wait, so each retry is a child span.
RetryReceiptHook: Final[stamina.instrumentation.RetryHookFactory] = stamina.instrumentation.RetryHookFactory(_retry_receipt)

# The one stacked hook set EMIT registers — the receipt+span fact and the structlog warning, both woven
# from one RetryDetails payload in one set_on_retry_hooks call. Both members are RetryHookFactory
# instances (lazy-built on the first scheduled retry). A second set_on_retry_hooks anywhere clobbers
# this stack because the hook table is process-global and the last write wins.
RETRY_HOOKS: Final[tuple[stamina.instrumentation.RetryHookFactory, ...]] = (RetryReceiptHook, stamina.instrumentation.StructlogOnRetryHook)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "POLICY",
    "RETRY_HOOKS",
    "OnRetry",
    "Policy",
    "RetryAfter",
    "RetryClass",
    "RetryMode",
    "RetryReceiptHook",
    "guard",
    "guard_sync",
    "guarded",
    "guarded_sync",
    "install",
    "retrying",
]
