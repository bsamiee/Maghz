"""Typed boundary rail: the closed `BoundaryFault` family and the one exception-to-fault conversion.

`RuntimeRail[T] = Result[T, BoundaryFault]` is the domain-internal rail every runtime owner
returns; it never collapses into the CLI `Envelope` (that projection lives at the command edge).
`async_boundary`/`boundary` are the sole fallible-boundary conversions: each awaits (or calls) a
thunk and, on any escape, walks the ordered `CLASSIFY` table for the first `isinstance` match,
returning `Error(builder(subject, str(exc)))`. There is no `catch` parameter on either function —
`CLASSIFY` is the one extension contract, so a new exception family is one row, never a knob. The
asyncssh rows sit ahead of the `(OSError,)` row. Because every `DisconnectError` subtype shares one
base, the `_SSH_TRANSIENT_EXC` row (which carries that base) would capture the whole subtree as
retryable `resource`; the auth-denial row (`_SSH_DENIED_EXC`) and the deterministic
negotiation/integrity row (`_SSH_PROTOCOL_EXC`) therefore scan first so denial classifies as `api`
and a futile re-handshake as `boundary`, leaving only a true peer disconnect for the transient
`resource` row. The `(Exception,)` catch-all stays last so every escape is classified.
"""

from collections.abc import Awaitable, Callable
import math
from typing import assert_never, Final, Literal

import anyio
import asyncssh
from beartype.roar import BeartypeCallHintViolation
from expression import case, Error, Ok, Result, tag, tagged_union
import msgspec


# --- [TYPES] ---------------------------------------------------------------------------

type FaultTag = Literal["config", "resource", "deadline", "api", "boundary", "aggregate"]
type RuntimeRail[T] = Result[T, BoundaryFault]


# --- [MODELS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class BoundaryFault:
    """The one closed boundary-failure family; every leaf projects to a structured-log fact dict."""

    tag: FaultTag = tag()
    config: tuple[str, str] = case()
    resource: tuple[str, str] = case()
    deadline: tuple[str, float] = case()
    api: tuple[str, str] = case()
    boundary: tuple[str, str] = case()
    aggregate: tuple[BoundaryFault, ...] = case()

    def facts(self) -> dict[str, object]:
        """Project this fault to a transient `dict` of `subject`/`detail`/`budget`/`members` keys.

        Returns:
            A read-only view consumed immediately by the receipt log pipeline; never stored.
            `aggregate` carries its members' own fact views without flattening the leaves.
        """
        match self:
            case (
                BoundaryFault(config=(subject, detail))
                | BoundaryFault(resource=(subject, detail))
                | BoundaryFault(api=(subject, detail))
                | BoundaryFault(boundary=(subject, detail))
            ):
                return {"subject": subject, "detail": detail}
            case BoundaryFault(deadline=(subject, budget)):
                detail = f"exceeded {budget:g}s budget" if budget > 0.0 and math.isfinite(budget) else "deadline exceeded"
                return {"subject": subject, "detail": detail, "budget": budget}
            case BoundaryFault(aggregate=members):
                return {"members": tuple(member.facts() for member in members)}
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed BoundaryFault union
                assert_never(unreachable)


# --- [CONSTANTS] -----------------------------------------------------------------------

# Ordered first-match exception classification: each row pairs an exception-family tuple with the
# `BoundaryFault` leaf builder it mints. `async_boundary`/`boundary` linear-scan this with
# `isinstance`, so the order is load-bearing — the `(Exception,)` catch-all is last and the asyncssh
# rows sit immediately before `(OSError,)`. Every asyncssh `DisconnectError` subtype shares one base
# (`PermissionDenied`/`HostKeyNotVerifiable`/`IllegalUserName`/`KeyExchangeFailed`/`MACError`/... <:
# `DisconnectError` <: `Error`), so the bare-base `_SSH_TRANSIENT_EXC` row over-captures the whole
# subtree as retryable `resource`; the terminal auth-denial and the deterministic negotiation/integrity
# families therefore scan FIRST so only a true peer disconnect reaches the transient row. `ChannelOpenError`
# is `<: Error` directly (not `<: DisconnectError`) and is the one channel-open transient folded in
# beside the disconnect pair. This is the SOLE conversion authority: a new family is a new row, never a
# `catch` parameter or a parallel function.
_RESOURCE_EXC: Final = (anyio.BrokenWorkerProcess, anyio.BrokenResourceError, anyio.ClosedResourceError)
# Auth-denial terminus: the three `DisconnectError` subtypes a credential/host-key/username rejection
# raises. They scan before `_SSH_TRANSIENT_EXC` (which carries the `DisconnectError` base) so a denied
# auth never classifies as retryable `resource`.
_SSH_DENIED_EXC: Final = (asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable, asyncssh.IllegalUserName)
# Deterministic transport-negotiation/integrity faults (`<: DisconnectError`): a re-handshake fails
# identically and `MACError` signals tampering, so these are non-retryable `boundary`, never `resource`.
# They scan before `_SSH_TRANSIENT_EXC` to escape the base-class capture.
_SSH_PROTOCOL_EXC: Final = (
    asyncssh.KeyExchangeFailed,
    asyncssh.MACError,
    asyncssh.CompressionError,
    asyncssh.ProtocolError,
    asyncssh.ProtocolNotSupported,
    asyncssh.ServiceNotAvailable,
)
# The genuine transient family `connection.py`'s `_RETRY_ON` mirrors: an unexpected peer disconnect
# (`ConnectionLost`/the `DisconnectError` base) or a channel-open rejection, all retryable once the
# denied/protocol subtypes above have been peeled off the `DisconnectError` subtree.
_SSH_TRANSIENT_EXC: Final = (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError)
CLASSIFY: Final[tuple[tuple[tuple[type[Exception], ...], Callable[[str, str], BoundaryFault]], ...]] = (
    (_RESOURCE_EXC, lambda subject, detail: BoundaryFault(resource=(subject, detail))),
    ((TimeoutError,), lambda subject, _detail: BoundaryFault(deadline=(subject, 0.0))),
    ((msgspec.DecodeError, msgspec.ValidationError), lambda subject, detail: BoundaryFault(boundary=(subject, detail))),
    ((asyncssh.ProcessError, asyncssh.SFTPError), lambda subject, detail: BoundaryFault(boundary=(subject, detail))),
    (_SSH_DENIED_EXC, lambda subject, detail: BoundaryFault(api=(subject, detail))),
    (_SSH_PROTOCOL_EXC, lambda subject, detail: BoundaryFault(boundary=(subject, detail))),
    (_SSH_TRANSIENT_EXC, lambda subject, detail: BoundaryFault(resource=(subject, detail))),
    ((OSError,), lambda subject, detail: BoundaryFault(boundary=(subject, detail))),
    ((BeartypeCallHintViolation,), lambda subject, detail: BoundaryFault(api=(subject, detail))),
    ((Exception,), lambda subject, detail: BoundaryFault(boundary=(subject, detail))),
)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _classify(subject: str, exc: Exception) -> BoundaryFault:
    """Walk `CLASSIFY` for the first matching exception family and mint its `BoundaryFault` leaf.

    The walk is structurally total: the `(Exception,)` catch-all row is the last family, so the
    `next` default never fires for a live escape. It pins the `boundary` leaf regardless, so an
    edit that removes the catch-all still lands on the rail instead of leaking `StopIteration`.

    Returns:
        The `BoundaryFault` leaf the first matching `CLASSIFY` row mints, or the `boundary` leaf
        when no row matches (unreachable while the catch-all row stands).
    """
    detail = str(exc)
    matched = (builder(subject, detail) for family, builder in CLASSIFY if isinstance(exc, family))
    return next(matched, BoundaryFault(boundary=(subject, detail)))


async def async_boundary[T](subject: str, thunk: Callable[[], Awaitable[T]]) -> RuntimeRail[T]:
    """Await `thunk`, lifting any escape to the `BoundaryFault` rail via the `CLASSIFY` table.

    Args:
        subject: The boundary identity stamped into the minted fault's `subject` slot.
        thunk: The fallible async unit of work whose escape is classified.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the first `CLASSIFY` family match.
    """
    try:
        return Ok(await thunk())
    except Exception as exc:  # noqa: BLE001 - CLASSIFY is the total classification authority over every escape
        return Error(_classify(subject, exc))


def boundary[T](subject: str, thunk: Callable[[], T]) -> RuntimeRail[T]:
    """Call `thunk`, lifting any escape to the `BoundaryFault` rail via the `CLASSIFY` table.

    Args:
        subject: The boundary identity stamped into the minted fault's `subject` slot.
        thunk: The fallible synchronous unit of work whose escape is classified.

    Returns:
        `Ok(value)` on success, or `Error(BoundaryFault)` for the first `CLASSIFY` family match.
    """
    try:
        return Ok(thunk())
    except Exception as exc:  # noqa: BLE001 - CLASSIFY is the total classification authority over every escape
        return Error(_classify(subject, exc))


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["CLASSIFY", "BoundaryFault", "FaultTag", "RuntimeRail", "async_boundary", "boundary"]
