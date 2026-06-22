"""Resilience owner: one retry-class StrEnum over a structurally-total `stamina` policy table.

`RetryClass` keys every transient-boundary policy; `POLICY` carries exactly one `Policy` row per
member, so totality is structural, not defensive. `Policy.schedule()` is the one `**`-passable projection of the schedule columns (`attempts`,
`timeout`, set `wait_*`), shared by both call shapes so the construction is built once; `target` is
the exception-binding axis, applied via `.on(...)` for the caller and `on=` for the iterator.
`guard(cls)` is the `functools.cache`-memoised builder of one reusable
`BoundAsyncRetryingCaller` per class — the call-site form `await guard(RetryClass.DB)(afn, *args)`, never a
`@guard(...)` decorator. `retrying(cls)` is the single-use `async for` sibling that rebuilds a fresh
`retry_context` each call; the two are not collapsible (reusable bound caller vs fresh iterator).
`install(mode)` flips the process-global retry instrumentation through `INSTALL_TABLE`, and
`RetryReceiptHook` mints a `fact`-phase `retry` receipt from each `RetryDetails` payload.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
import functools
from typing import Final, NotRequired, TypedDict

import asyncssh
from expression.collections import Map
import httpx
import keyring.errors
import pg8000
import stamina
import stamina.instrumentation


# --- [TYPES] ---------------------------------------------------------------------------


class RetryClass(StrEnum):
    """The closed set of transient-boundary retry classes, one `POLICY` row each."""

    DB = "db"
    HTTP = "http"
    PROC = "proc"
    SECRET = "secret"  # noqa: S105 - StrEnum member value, not a credential literal


class RetryMode(StrEnum):
    """The closed set of retry-instrumentation install modes dispatched by `install`."""

    EMIT = "emit"
    SILENT = "silent"
    TEST = "test"


# `stamina`'s `on=` discriminator (an exception class, a tuple of classes, or a backoff hook
# returning bool/float/timedelta for the Retry-After pattern) is defined only at `stamina._core`
# and never publicly exported, so the local alias is the canonical owner of the `Policy.target` shape.
type _Target = type[Exception] | tuple[type[Exception], ...] | Callable[[Exception], bool | float | timedelta]


class Schedule(TypedDict):
    """The `**`-passable `stamina` schedule columns `Policy.schedule()` projects; `wait_*` optional.

    Mirrors the `stamina` caller/`retry_context` keyword schema so a `**`-spread type-checks each
    column against the target signature; `target` is bound separately and is not a member here.
    """

    attempts: int
    timeout: float
    wait_initial: NotRequired[float]
    wait_max: NotRequired[float]
    wait_jitter: NotRequired[float]
    wait_exp_base: NotRequired[float]


# --- [MODELS] --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    """One frozen retry policy: the bound target plus the `stamina` schedule columns.

    Not a `msgspec.Struct`: `target` carries exception types and callables msgspec cannot encode,
    and the policy is never wire-serialized. Absent `wait_*` columns defer to the `stamina` default.
    """

    attempts: int
    timeout: float
    target: _Target
    wait_initial: float | None = None
    wait_max: float | None = None
    wait_jitter: float | None = None
    wait_exp_base: float | None = None

    def schedule(self) -> Schedule:
        """Project `attempts`, `timeout`, and the set `wait_*` columns to one `**`-passable schedule.

        `target` is the binding axis, not a schedule column: the caller applies it through `.on(...)`
        and the iterator through `on=`, so it stays off this dict.

        Returns:
            A `Schedule` carrying `attempts`/`timeout` plus every non-`None` `wait_*` column;
            absent `wait_*` columns defer to the `stamina` default.
        """
        waits: dict[str, float] = {
            key: value
            for key, value in (
                ("wait_initial", self.wait_initial),
                ("wait_max", self.wait_max),
                ("wait_jitter", self.wait_jitter),
                ("wait_exp_base", self.wait_exp_base),
            )
            if value is not None
        }
        return Schedule(attempts=self.attempts, timeout=self.timeout, **waits)


# --- [OPERATIONS] ----------------------------------------------------------------------


@functools.cache
def guard(cls: RetryClass) -> stamina.BoundAsyncRetryingCaller:
    """The memoised bound async retrying caller for one retry class; its policy is frozen at build.

    Args:
        cls: The retry class whose `POLICY` row binds the caller's schedule and exception target.

    Returns:
        A reusable `BoundAsyncRetryingCaller`; call it as `await guard(cls)(afn, *args, **kwargs)`.
        Repeated calls for the same class return the same cached instance.
    """
    policy = POLICY[cls]
    return stamina.AsyncRetryingCaller(**policy.schedule()).on(policy.target)


def retrying(cls: RetryClass) -> AsyncIterator[stamina.Attempt]:
    """Build one fresh `retry_context` iterator for an inline retry block over a retry class.

    Args:
        cls: The retry class whose `POLICY` row supplies the context schedule and target.

    Returns:
        A fresh single-use `stamina.retry_context`; consume it once with `async for attempt in ...`.
    """
    policy = POLICY[cls]
    return stamina.retry_context(on=policy.target, **policy.schedule())


def install(mode: RetryMode) -> None:
    """Flip the process-global retry instrumentation to one closed `RetryMode` via `INSTALL_TABLE`.

    Args:
        mode: The install mode whose `INSTALL_TABLE` action runs (hook stack or test toggle).
    """
    INSTALL_TABLE.try_find(mode).default_with(lambda: lambda: None)()


def _retry_receipt(details: stamina.instrumentation.RetryDetails) -> None:
    """Mint a `fact`-phase `retry` receipt from one `RetryDetails` payload via the receipt service.

    Args:
        details: The per-retry fact carrier `stamina` passes to every on-retry hook.
    """
    from admin.runtime.receipts import Receipt, Signals  # noqa: PLC0415 - deferred to break the resilience->receipts->lanes->resilience import cycle

    facts: dict[str, object] = {
        "name": details.name,
        "retry_num": details.retry_num,
        "wait_for": details.wait_for,
        "waited_so_far": details.waited_so_far,
        "caused_by": repr(details.caused_by),
    }
    Signals.emit(Receipt.of(details.name, ("retry", details.name, facts)))


# --- [TABLES] --------------------------------------------------------------------------

# One structurally-total policy row per RetryClass member, keyed on the member (not `.value`). The
# HTTP row's target spans every transient network seam at one timing band — Ollama-pull streams and
# VPS SSH/SFTP reconnects share `RetryClass.HTTP`; SECRET guards the keyring unlock handshake with a
# widened initial wait.
# `httpx.ConnectError`/`RemoteProtocolError` and the asyncssh transients are NOT `OSError`/`ConnectionError`
# subclasses (asyncssh.Error derives straight from Exception), so the bare `OSError` row would never
# catch a dropped Ollama-pull stream or a remote disconnect — each transient family is named explicitly
# so the HTTP retry fires.
# The HTTP target is a `stamina` backoff PREDICATE, not a bare tuple, because the two terminal asyncssh
# faults derive from `DisconnectError`: `PermissionDenied`/`HostKeyNotVerifiable` <: `DisconnectError` <:
# `Error`. A tuple admitting `DisconnectError` therefore `isinstance`-matches a denied auth or unverified
# host key and would retry it (`CLASSIFY` still routes it to `api`, but only after exhausting the schedule).
# `_http_retryable` returns True for the transient families and False for the terminal subclasses, so a
# denied auth or unverified host key aborts on the first attempt; a new terminal SSH fault is one
# `_SSH_TERMINAL` entry, not a re-tupled target.
_SSH_RETRYABLE: Final[tuple[type[asyncssh.Error], ...]] = (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError)
_SSH_TERMINAL: Final[tuple[type[asyncssh.Error], ...]] = (asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable)
_HTTP_RETRYABLE: Final[tuple[type[Exception], ...]] = (
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    *_SSH_RETRYABLE,
    ConnectionError,
    OSError,
    TimeoutError,
)


def _http_retryable(exc: Exception) -> bool:
    """Admit retry for every HTTP/SSH transient family while excluding the terminal asyncssh faults.

    The terminal `asyncssh.PermissionDenied`/`HostKeyNotVerifiable` derive from `DisconnectError`, which
    `_HTTP_RETRYABLE` admits; the explicit `_SSH_TERMINAL` exclusion is what stops `stamina` from
    `isinstance`-matching them through that superclass and retrying a denied auth or unverified host key.

    Args:
        exc: The exception `stamina` raises out of the guarded HTTP/SSH call.

    Returns:
        `True` when `exc` is a transient family member and not a terminal asyncssh fault, else `False`.
    """
    return isinstance(exc, _HTTP_RETRYABLE) and not isinstance(exc, _SSH_TERMINAL)


POLICY: Final[Map[RetryClass, Policy]] = Map.of_seq([
    (RetryClass.DB, Policy(attempts=4, timeout=30.0, target=(pg8000.Error, OSError), wait_initial=0.1, wait_max=3.0)),
    (RetryClass.HTTP, Policy(attempts=5, timeout=60.0, target=_http_retryable, wait_initial=0.2, wait_max=5.0)),
    (RetryClass.PROC, Policy(attempts=3, timeout=45.0, target=(OSError,), wait_initial=0.1, wait_max=4.0)),
    (RetryClass.SECRET, Policy(attempts=4, timeout=20.0, target=(keyring.errors.KeyringLocked, OSError), wait_initial=0.5, wait_max=5.0)),
])

# RetryReceiptHook lazily constructs the `_retry_receipt` hook on the first scheduled retry; the
# EMIT mode stacks it with the structlog warning emitter, SILENT clears all hooks, TEST collapses
# backoff for deterministic specs.
RetryReceiptHook: Final[stamina.instrumentation.RetryHookFactory] = stamina.instrumentation.RetryHookFactory(lambda: _retry_receipt)
INSTALL_TABLE: Final[Map[RetryMode, Callable[[], object]]] = Map.of_seq([
    (RetryMode.EMIT, lambda: stamina.instrumentation.set_on_retry_hooks([RetryReceiptHook, stamina.instrumentation.StructlogOnRetryHook])),
    (RetryMode.SILENT, lambda: stamina.instrumentation.set_on_retry_hooks([])),
    (RetryMode.TEST, lambda: stamina.set_testing(True)),
])


# --- [COMPOSITION] ---------------------------------------------------------------------

__all__ = ["INSTALL_TABLE", "POLICY", "Policy", "RetryClass", "RetryMode", "RetryReceiptHook", "guard", "install", "retrying"]
