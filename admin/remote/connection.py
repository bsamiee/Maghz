"""The asyncssh connection lifecycle and credential projection for the `remote` domain.

`KnownHostsPolicy` closes the `None`-passes-silently host-key bug at the type level: the vocabulary
is `Literal["insecure"] | Path`, so there is no `None` arm to drop into `asyncssh` unnoticed. The
single boundary that turns the raw `RemoteConfig.known_hosts: str` into that vocabulary is
`RemoteTarget.from_config` — `"insecure"` is the one literal escape hatch, every other string is a
`Path`. `target_options` is the ONE site that constructs `asyncssh.SSHClientConnectionOptions`,
resolving the policy in a total `match` (no `**dict` keyword soup at the call site), and `connection`
is the ONE site that opens `asyncssh.connect`, wrapping it in `guard(RetryClass.HTTP)` so transient
SSH faults (`ConnectionLost`/`ChannelOpenError`) retry on the shared `runtime` timing band while
terminal faults (`PermissionDenied`/`HostKeyNotVerifiable`) surface immediately as `BoundaryFault.api`.
Which asyncssh faults retry, and which classify terminal, is owned entirely by the `runtime` policy
table (`POLICY[RetryClass.HTTP].target`) and classification table (`CLASSIFY`) — this file holds no
parallel retry vocabulary. There is no connection pool: each `exec`/`deploy` invocation owns one
scoped connection under the anyio task tree.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import assert_never, Literal

import asyncssh
import msgspec
import structlog

from admin.runtime import guard, RetryClass
from admin.settings import RemoteConfig


# --- [TYPES] ---------------------------------------------------------------------------

type KnownHostsPolicy = Literal["insecure"] | Path


# --- [SERVICES] ------------------------------------------------------------------------

_log = structlog.get_logger("admin.remote.connection")


# --- [MODELS] --------------------------------------------------------------------------


class RemoteTarget(msgspec.Struct, frozen=True, gc=False, kw_only=True):
    """The derived SSH target value object: host, port, user, host-key policy, and remote workroot.

    A post-admission value object with no construction-time validation and no cycles, so the frozen
    `msgspec.Struct` is the owner rather than a dataclass. The host-key policy is already narrowed to
    `KnownHostsPolicy` here — the `RemoteConfig.known_hosts: str` ingress is converted exactly once,
    in `from_config`, so every downstream `match` is total. No `connect_kwargs` dict and no `url`
    property: `target_options` projects the options object and log context uses an inline f-string.
    """

    host: str
    port: int
    user: str
    known_hosts: KnownHostsPolicy
    workroot: str

    @classmethod
    def from_config(cls, cfg: RemoteConfig) -> RemoteTarget:
        """Project a validated `RemoteConfig` into a `RemoteTarget`, narrowing `known_hosts` to policy.

        The raw `cfg.known_hosts: str` is the sole untyped ingress: the literal `"insecure"` maps to
        the `Literal["insecure"]` escape hatch (host-key verification disabled), and every other value
        becomes a `Path`. This is the one boundary where the string vocabulary collapses into the
        typed `KnownHostsPolicy`, so no `None` can reach `asyncssh`.

        Returns:
            A frozen `RemoteTarget` carrying the SSH facts and the narrowed host-key policy.
        """
        policy: KnownHostsPolicy = "insecure" if cfg.known_hosts == "insecure" else Path(cfg.known_hosts)
        return cls(host=cfg.host, port=cfg.port, user=cfg.user, known_hosts=policy, workroot=cfg.workroot)


# --- [OPERATIONS] ----------------------------------------------------------------------


def target_options(target: RemoteTarget, cfg: RemoteConfig) -> asyncssh.SSHClientConnectionOptions:
    """Build the one `SSHClientConnectionOptions` per connection, resolving `KnownHostsPolicy` totally.

    The `match` over `target.known_hosts` is exhaustive: `"insecure"` logs
    `ssh.host_key_verification_disabled` and passes `known_hosts=None` (the only sanctioned route to a
    disabled check); a `Path` passes `known_hosts=str(p)`. `assert_never` proves the vocabulary is
    closed. The connect/login/keepalive columns thread from `cfg`, so every connection carries the
    same typed timeout posture and no call site assembles a raw `**dict`.

    Args:
        target: The SSH target whose host-key policy selects the `known_hosts` argument.
        cfg: The remote configuration supplying the connect/login/keepalive timing columns.

    Returns:
        The single typed `SSHClientConnectionOptions` object `connection` passes to `asyncssh.connect`.
    """
    match target.known_hosts:
        case "insecure":
            _log.warning("ssh.host_key_verification_disabled", host=target.host, port=target.port)
            known_hosts: str | None = None
        case Path() as p:
            known_hosts = str(p)
        case _ as unreachable:  # pragma: no cover - exhaustive over the closed KnownHostsPolicy union
            assert_never(unreachable)
    return asyncssh.SSHClientConnectionOptions(
        known_hosts=known_hosts,
        connect_timeout=cfg.connect_timeout,
        login_timeout=cfg.connect_timeout,
        keepalive_interval=cfg.keepalive_interval,
        keepalive_count_max=cfg.keepalive_count_max,
    )


@asynccontextmanager
async def connection(target: RemoteTarget, cfg: RemoteConfig) -> AsyncIterator[asyncssh.SSHClientConnection]:
    """Open one scoped `asyncssh.connect` under `guard(RetryClass.HTTP)`, yielding the live connection.

    `asyncssh.connect` is invoked through `guard(RetryClass.HTTP)` so the transient SSH faults the
    `runtime` `POLICY[RetryClass.HTTP].target` admits retry on the same timing band as httpx
    transients, while terminal auth/host-key faults surface immediately (classified to
    `BoundaryFault.api` at the `async_boundary` that wraps the caller). The awaited connection is
    entered as an `async with` resource, so the connection's own `__aexit__` owns deterministic
    teardown on both the success and the cancellation path — there is no pool and no second client.

    Args:
        target: The SSH target whose host/port/user identify the connection.
        cfg: The remote configuration whose timing columns build the connection options.

    Yields:
        The live `SSHClientConnection` for the duration of one CLI operation.
    """
    options = target_options(target, cfg)
    conn = await guard(RetryClass.HTTP)(
        asyncssh.connect, target.host, port=target.port, username=target.user, options=options
    )
    async with conn:
        yield conn


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["KnownHostsPolicy", "RemoteTarget", "connection", "target_options"]
