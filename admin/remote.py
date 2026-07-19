"""The `remote` domain: VPS `exec` over one scoped asyncssh connection, git via `runtime.spawn`.

One file owning the connection lifecycle and the VPS-facing entrypoint. `RemoteTarget.from_config` is the
sole boundary narrowing the raw `RemoteConfig.known_hosts: str` to the typed `KnownHostsPolicy`
(`Literal["insecure"] | Path`), so no `None` reaches `asyncssh` and every downstream `match` is total.
`RemoteOp` is the closed verb vocabulary the CLI mounts; each member carries only its `.subject`, and each
entrypoint supplies one connection `body` over the shared `(session) -> Awaitable[Detail]` signature to the
one `_drive` spine. Service-plane lifecycle is NOT a remote verb: `maghz up`/`down`/`status` at
`stage=prd` converge the VPS daemon directly over the stage-resolved `ssh://` docker endpoint, so this
domain carries agent shell work only — a new remote verb is one `RemoteOp` member plus one body, with the
prelude and the CLI lowering untouched.

Two subprocess/SSH boundary families, each on the canonical rail and never re-deriving its own
spawn/grade/lift chain. The LOCAL git probes (`ls-files`, `check-attr`, `rev-parse`) compose the one
`runtime.spawn` boundary under `RetryClass.PROC` and grade the exit inline against the `remote.git`
subject; the dependent manifest/commit prelude short-circuits on the rail, so a probe fault returns before
any connection opens. The remote command, the working-tree push, and the artifact pull all ride one
`_Session` opened under `guard(RetryClass.HTTP)` and fenced by one `async_boundary(op.subject, ...)`: a
non-zero `conn.run(check=True)` raises `ProcessError` (lifted to `BoundaryFault.boundary`), an SSH
disconnect lands `resource`, an auth/host-key denial `api`, and a codec break `boundary` — `BoundaryFault`
already spans that space, so the domain mints no parallel `RemoteFault`. The verb returns the
domain-internal `RuntimeRail[Envelope]`, so the one CLI `runtime.lower` seam lowers a surviving
`Error(BoundaryFault)` once, at the edge.

The push is never a fresh `anyio.CapacityLimiter` per call (which bounds nothing): each parent directory is
one `drain` unit over `LanePolicy(capacity=cfg.remote.sftp_push_concurrency)`, whose substrate-memoised
limiter bounds every concurrent SFTP session across the process, and the lossless `DrainReceipt` folds the
pushed count and per-directory faults into the receipt notes — no mutable accumulator, no raw task group.
git-lfs pointer paths are held out of the transfer by the `check-attr` pass and noted rather than pushed as
stubs. Every remote token is `shlex.quote`-d behind the `_REMOTE_ENV` projection, so no shell metacharacter
escapes. Every receipt carries the pushed commit sha minted once by `rev-parse` and threaded outward,
never re-derived per leg.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from enum import StrEnum
import itertools
import operator
from pathlib import Path, PurePosixPath
import shlex
from typing import assert_never, Literal, Self

import asyncssh
from expression import Error, Ok, Result
from expression.collections import Block
from frozendict import frozendict
import msgspec
from pydantic import SecretStr
import structlog

from admin.core import completed, Detail, Envelope, Status
from admin.runtime import Admit, async_boundary, BoundaryFault, DrainReceipt, guard, LaneKey, LanePolicy, RetryClass, RuntimeRail, spawn
from admin.settings import MaghzSettings, RemoteConfig, REPO_ROOT


# --- [TYPES] ---------------------------------------------------------------------------

type KnownHostsPolicy = Literal["insecure"] | Path
type Manifest = Worktree


class RemoteOp(StrEnum):
    """The closed remote verb vocabulary the CLI mounts; each member carries its `.subject` fence identity.

    One case: `EXEC` runs a free command under the pushed working tree and pulls artifacts back. The
    working-tree push and the artifact pull are implicit, never standalone user-facing verbs; stack
    lifecycle belongs to the stage-discriminated `infra` rail, not to a remote verb.
    """

    EXEC = "exec"

    @property
    def subject(self) -> str:
        """The `remote.<op>` boundary subject stamped into the `async_boundary` fence and every fault."""
        return f"remote.{self.value}"


# --- [SERVICES] ------------------------------------------------------------------------

_log = structlog.get_logger("admin.remote")


# --- [MODELS] --------------------------------------------------------------------------


class RemoteTarget(msgspec.Struct, frozen=True, gc=False, kw_only=True):
    """The derived SSH target value object: host, port, user, host-key policy, workroot.

    A post-admission value object with no construction-time validation and no cycles, so the frozen
    `msgspec.Struct` is the owner rather than a dataclass. `known_hosts` is already narrowed to
    `KnownHostsPolicy` here — `from_config` converts the `RemoteConfig.known_hosts: str` ingress exactly
    once, so every downstream `match` is total. `options` projects the one `SSHClientConnectionOptions`;
    `label` mints the receipt identity once.
    """

    host: str
    port: int
    user: str
    known_hosts: KnownHostsPolicy
    workroot: str

    @classmethod
    def from_config(cls, cfg: RemoteConfig) -> RuntimeRail[Self]:
        """Project a validated `RemoteConfig` into a `RemoteTarget`, narrowing `known_hosts` to policy.

        The raw `cfg.known_hosts: str` is the sole untyped ingress: `"insecure"` maps to the literal
        escape hatch (host-key verification disabled), every other value becomes a `Path`. This is the
        one boundary where the string vocabulary collapses into the typed `KnownHostsPolicy`, so no
        `None` reaches `asyncssh`.

        Returns:
            A frozen `RemoteTarget` carrying the SSH facts and the narrowed host-key policy.
        """
        if not cfg.host or not cfg.user:
            return Error(BoundaryFault(config=("remote.target", "remote host/user not configured: set MAGHZ_REMOTE_HOST and MAGHZ_REMOTE_USER")))
        policy: KnownHostsPolicy = "insecure" if cfg.known_hosts == "insecure" else Path(cfg.known_hosts)
        return Ok(cls(host=cfg.host, port=cfg.port, user=cfg.user, known_hosts=policy, workroot=cfg.workroot))

    @property
    def label(self) -> str:
        """The `user@host:port` identity stamped into every receipt; minted here, never re-spelled per leg."""
        return f"{self.user}@{self.host}:{self.port}"

    def options(self, cfg: RemoteConfig) -> asyncssh.SSHClientConnectionOptions:
        """Build the one `SSHClientConnectionOptions` per connection, resolving `KnownHostsPolicy` totally.

        The `match` over `known_hosts` is exhaustive: `"insecure"` logs the disabled-verification warning
        and passes `known_hosts=None` (the only sanctioned route to a disabled check); a `Path` passes
        `known_hosts=str(p)`; `assert_never` proves the vocabulary closed. `client_keys` is threaded only
        when `cfg.key_file` is set — an explicit private key; when absent the option is omitted so
        `asyncssh` falls back to the running agent (the Forge 1Password SSH agent via `SSH_AUTH_SOCK`) plus
        the default key locations, never the empty `client_keys=()` that would disable key auth outright.
        The connect/login/keepalive columns thread from `cfg`, so every connection carries the same typed
        timeout posture and no call site assembles a raw `**dict`.

        Args:
            cfg: The remote configuration supplying the key file, host-key policy, and timing columns.

        Returns:
            The single typed `SSHClientConnectionOptions` `_session` passes to `asyncssh.connect`.
        """
        match self.known_hosts:
            case "insecure":
                _log.warning("ssh.host_key_verification_disabled", host=self.host, port=self.port)
                known_hosts: str | None = None
            case Path() as path:
                known_hosts = str(path)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed KnownHostsPolicy union
                assert_never(unreachable)
        keys = {"client_keys": [str(cfg.key_file)]} if cfg.key_file is not None else {}
        return asyncssh.SSHClientConnectionOptions(
            known_hosts=known_hosts,
            connect_timeout=cfg.connect_timeout,
            login_timeout=cfg.connect_timeout,
            keepalive_interval=cfg.keepalive_interval,
            keepalive_count_max=cfg.keepalive_count_max,
            **keys,
        )


class RemoteExec(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="exec"):
    argv: tuple[str, ...]


type RemoteRequest = RemoteExec


class PushGroup(msgspec.Struct, frozen=True, gc=False):
    relative: str
    paths: tuple[str, ...]


class Worktree(msgspec.Struct, frozen=True, gc=False):
    root: Path
    pushable: tuple[str, ...]
    skipped_lfs: tuple[str, ...]

    def groups(self) -> tuple[PushGroup, ...]:
        keyed = sorted((str(PurePosixPath(path).parent), path) for path in self.pushable)
        return tuple(
            PushGroup(relative=relative, paths=tuple(path for _, path in group))
            for relative, group in itertools.groupby(keyed, key=operator.itemgetter(0))
        )


class RemoteEnv(msgspec.Struct, frozen=True, gc=False):
    rows: frozendict[str, str]

    @staticmethod
    def of(cfg: MaghzSettings) -> RuntimeRail[RemoteEnv]:
        try:
            return Ok(RemoteEnv(frozendict((key, project(cfg)) for key, project in _REMOTE_ENV.items())))
        except ValueError as exc:
            return Error(BoundaryFault(config=("remote.env", str(exc))))

    def shell(self) -> str:
        return " ".join(f"{key}={shlex.quote(value)}" for key, value in self.rows.items())


class ExecReceipt(Detail, frozen=True, gc=False, tag="remote_exec"):
    """One remote `exec` receipt: target identity, the deployed commit, completed-process outcome, transfer counts.

    `exit_status`/`exit_signal` mirror `asyncssh.SSHCompletedProcess` exactly, read off a clean completion
    — a non-zero exit raises `ProcessError` (lifted to `BoundaryFault.boundary`) and never reaches this
    projection. `commit` is the pushed working-tree sha minted once by the `git rev-parse` probe.
    """

    target: str
    host: str
    commit: str
    exit_status: int | None
    exit_signal: str | None
    pushed: int
    pulled: int
    notes: tuple[str, ...]


class _Session(msgspec.Struct, frozen=True, gc=False):
    """The live connection-scoped handle threaded into each `_drive` body: connection, SFTP, target, settings, commit.

    Opened once by `_drive` under `guard(RetryClass.HTTP)` and entered as an `async with` resource, so its
    own `__aexit__` owns deterministic teardown on both the success and the cancellation path — there is no
    pool and no second client. `push` and `run` are the two SSH operations every body composes; `commit` is
    the pushed sha minted by the git prelude and carried into every receipt.
    """

    conn: asyncssh.SSHClientConnection
    sftp: asyncssh.SFTPClient
    target: RemoteTarget
    cfg: MaghzSettings
    manifest: Manifest
    env: RemoteEnv
    commit: str

    async def run(self, *argv: str) -> asyncssh.SSHCompletedProcess:
        """Run one quoted command on the VPS with `check=True`, returning the clean completed process.

        Every token routes through `shlex.quote` behind the `_REMOTE_ENV` export projection, so a
        workroot, env value, or argument carrying shell metacharacters cannot escape. `check=True` raises
        `ProcessError` on a non-zero exit — lifted to `BoundaryFault.boundary` at the `_drive` fence, never
        inspected by hand — so this returns only a clean `SSHCompletedProcess`.

        Returns:
            The clean `SSHCompletedProcess`; `encoding=None` keeps `stdout`/`stderr` as raw bytes.
        """
        body = " ".join(shlex.quote(token) for token in argv)
        return await self.conn.run(f"cd {shlex.quote(self.target.workroot)} && {self.env.shell()} {body}", check=True, encoding=None)

    async def push(self) -> tuple[int, tuple[str, ...]]:
        """Push the tracked working tree to the remote workroot, drained per directory under the memoised lane limiter.

        The `manifest` (lfs pointers already held out by `_manifest`) groups by parent directory; each
        directory is one `drain` unit over `LanePolicy(capacity=cfg.remote.sftp_push_concurrency)`, whose
        substrate-memoised `CapacityLimiter` bounds every concurrent SFTP session across the process — never
        a fresh per-call limiter that bounds nothing. The lossless `DrainReceipt` folds the per-directory
        pushed counts into the total and the per-directory boundary faults into the notes; the held-out lfs
        paths are noted too. A per-file `SFTPError` folds through `put`'s `error_handler` into its
        directory's count, so one bad file never aborts the whole transfer.

        Returns:
            A `(pushed_count, notes)` pair: the files transferred and the per-directory failure plus
            held-out-lfs notes folded from the drain receipt.
        """
        pushable = self.manifest.pushable
        notes = tuple(f"lfs-skipped {path}" for path in self.manifest.skipped_lfs)
        if not pushable:
            return 0, notes
        workroot = PurePosixPath(self.target.workroot)
        await self.sftp.makedirs(self.target.workroot, exist_ok=True)
        policy = LanePolicy(capacity=self.cfg.remote.sftp_push_concurrency, key=LaneKey("remote.sftp.push"))
        units = Block.of_seq(Admit.of(self._dir(workroot, group.relative, group.paths)) for group in self.manifest.groups())
        receipt: DrainReceipt[object] = await policy.drain(units)
        pushed = sum(int(value) for value in receipt.values if isinstance(value, int))
        return pushed, (*notes, *(fault.headline() for fault in receipt.faults))

    def _dir(self, workroot: PurePosixPath, relative: str, files: tuple[str, ...]) -> Callable[[], Awaitable[RuntimeRail[object]]]:
        """Build one per-directory push `Work` unit: ensure the remote dir, then `put` the files under the lane bound.

        The unit returns `Ok(pushed_int)` — the file count minus the per-file `error_handler` failures — so
        the drain folds counts and faults losslessly; a directory-level `SFTPError` (the `makedirs`/`put`
        setup) rides the substrate `CLASSIFY` fold to a `boundary` leaf on the `Error` leg, which the receipt
        notes name. The per-file error sink is the one sanctioned mutable boundary adapter: asyncssh invokes
        `error_handler` per failed file, so a list-backed collector counts them inside the unit.

        Returns:
            An async `Work` callable returning `Ok(pushed_count)` for the directory, or `Error(BoundaryFault)`
            when the directory-level `makedirs`/`put` raises `SFTPError`.
        """
        remotedir = str(workroot / relative) if relative != "." else self.target.workroot

        async def put() -> int:
            failures: list[str] = []
            await self.sftp.makedirs(remotedir, exist_ok=True)
            local = [str(self.manifest.root / path) for path in files]
            await self.sftp.put(local, remotedir, max_requests=self.cfg.remote.sftp_max_requests, error_handler=lambda exc: failures.append(str(exc)))
            return len(files) - len(failures)

        return lambda: async_boundary("remote.sftp", put, catch=asyncssh.SFTPError)


# --- [TABLES] --------------------------------------------------------------------------


# The minimal environment projection forwarded into the remote `maghz` process, declared once and shared
# by every `_Session.run`. Each row pairs the canonical env key with the projection that mints its value
# from the validated settings, so `MAGHZ_DATABASE_DSN` tracks `cfg.database.dsn` by construction and
# `MAGHZ_LOG__FORMAT` is pinned to the machine-readable renderer; `run` folds each row into a
# `KEY=<shlex.quote(value)>` export ahead of the remote argv.
def _required(value: SecretStr | str | None, key: str) -> str:
    raw = value.get_secret_value() if isinstance(value, SecretStr) else (value or "")
    if not raw:
        raise ValueError(f"missing required remote environment variable: {key}")
    return raw


_REMOTE_ENV: frozendict[str, Callable[[MaghzSettings], str]] = frozendict({
    "MAGHZ_DATABASE_DSN": lambda cfg: str(cfg.database.dsn),
    "MAGHZ_LOG__FORMAT": lambda _cfg: "json",
    "CODERABBIT_API_KEY": lambda cfg: _required(cfg.integrations.coderabbit_api_key, "CODERABBIT_API_KEY"),
    "OP_SERVICE_ACCOUNT_TOKEN": lambda cfg: _required(cfg.integrations.op_service_account_token, "OP_SERVICE_ACCOUNT_TOKEN"),
    "GOOGLE_OAUTH_CLIENT_ID": lambda cfg: _required(cfg.integrations.google_oauth_client_id, "GOOGLE_OAUTH_CLIENT_ID"),
    "GOOGLE_OAUTH_CLIENT_SECRET": lambda cfg: _required(cfg.integrations.google_oauth_client_secret, "GOOGLE_OAUTH_CLIENT_SECRET"),
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": lambda cfg: f"/home/{cfg.remote.user}/.config/gws",
    "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE": lambda cfg: f"/home/{cfg.remote.user}/.config/gws/credentials.json",
    "GOOGLE_WORKSPACE_PROJECT_ID": lambda cfg: _required(cfg.integrations.google_workspace_project_id, "GOOGLE_WORKSPACE_PROJECT_ID"),
    "GREPTILE_API_KEY": lambda cfg: _required(cfg.integrations.greptile_api_key, "GREPTILE_API_KEY"),
    "GH_TOKEN": lambda cfg: _required(cfg.integrations.gh_token, "GH_TOKEN"),
    "GITHUB_TOKEN": lambda cfg: _required(cfg.integrations.github_token, "GITHUB_TOKEN"),
    "GH_PROJECTS_TOKEN": lambda cfg: _required(cfg.integrations.gh_projects_token, "GH_PROJECTS_TOKEN"),
    "HOSTINGER_API_TOKEN": lambda cfg: _required(cfg.integrations.hostinger_api_token, "HOSTINGER_API_TOKEN"),
    "CONTEXT7_API_KEY": lambda cfg: _required(cfg.integrations.context7_api_key, "CONTEXT7_API_KEY"),
    "EXA_API_KEY": lambda cfg: _required(cfg.integrations.exa_api_key, "EXA_API_KEY"),
    "PERPLEXITY_API_KEY": lambda cfg: _required(cfg.integrations.perplexity_api_key, "PERPLEXITY_API_KEY"),
    "TAVILY_API_KEY": lambda cfg: _required(cfg.integrations.tavily_api_key, "TAVILY_API_KEY"),
})


# --- [OPERATIONS] ----------------------------------------------------------------------

# --- [GIT_PROBE]


async def _git(*argv: str, stdin: bytes | None = None) -> RuntimeRail[bytes]:
    """Run one local `git` probe through the canonical `runtime.spawn` boundary, grading the exit to stdout.

    The one local-git boundary the prelude composes: `runtime.spawn` owns the `anyio.run_process(check=
    False)` spawn, the `guard(RetryClass.PROC)` retry of a transient spawn flap, and the `async_boundary`
    lift of an exhausted-spawn escape — so the three git invocations (`ls-files`, `check-attr`, `rev-parse`)
    share one spawn/retry/lift chain. A zero exit yields the raw stdout bytes; a non-zero exit grades to
    `BoundaryFault.boundary` against the `remote.git` subject (the deterministic-failure leaf distinct from
    the retryable spawn flap the lane already replays), minting the fault directly — carrier-free, no
    per-rail wrapper. The exit-to-rail mapping the `spawn` contract leaves to the caller lives here, once.

    Args:
        argv: The `git` subcommand and its arguments, run with `cwd` at the repo root.
        stdin: The bytes piped to git stdin (the NUL-joined manifest for `check-attr`), or `None`.

    Returns:
        `Ok(stdout_bytes)` on a zero exit, or `Error(BoundaryFault)` for a non-zero git exit or an
        exhausted spawn flap lifted at the `runtime.spawn` boundary.
    """
    return (await spawn(("git", *argv), subject="remote.git", retry_class=RetryClass.PROC, cwd=REPO_ROOT, stdin=stdin)).bind(
        lambda run: (
            Ok(run.stdout)
            if run.returncode == 0
            else Error(BoundaryFault(boundary=("remote.git", run.stderr.decode(errors="replace").strip() or f"git exit {run.returncode}")))
        )
    )


async def _manifest() -> RuntimeRail[Manifest]:
    """Enumerate the tracked working tree on the rail, partitioning git-lfs pointer paths out of the push set.

    `git ls-files --cached --exclude-standard -z` yields the NUL-delimited tracked manifest; a second
    `git check-attr filter -z --stdin` pass over that manifest reads each path's `filter` attribute, so
    `filter=lfs` paths (which `ls-files` reports as a few-hundred-byte pointer, not the binary object) are
    excluded from the transfer and folded into the skip notes rather than pushed as stubs. Both probes ride
    the `_git` boundary, so a git failure short-circuits the push to the rail rather than transferring a
    partial tree; the dependent second probe binds the first only when the manifest is non-empty.

    Returns:
        `Ok((pushable, skipped))` — `pushable` the non-lfs tracked POSIX-relative paths to transfer,
        `skipped` the lfs-tracked pointer paths held out — or `Error(BoundaryFault)` from either probe.
    """

    def _split(tracked: tuple[str, ...], attrs: bytes) -> Manifest:
        fields = attrs.decode().split("\0")
        lfs = {fields[index] for index in range(0, len(fields) - 2, 3) if fields[index + 2] == "lfs"}
        return Worktree(root=REPO_ROOT, pushable=tuple(path for path in tracked if path not in lfs), skipped_lfs=tuple(sorted(lfs)))

    match await _git("ls-files", "--cached", "--exclude-standard", "-z"):
        case Result(tag="ok", ok=listed):
            tracked = tuple(path for path in listed.decode().split("\0") if path)
            if not tracked:
                return Ok(Worktree(root=REPO_ROOT, pushable=(), skipped_lfs=()))
            attrs = await _git("check-attr", "filter", "-z", "--stdin", stdin="\0".join(tracked).encode())
            return attrs.map(lambda raw: _split(tracked, raw))
        case Result(error=manifest_fault):
            return Error(manifest_fault)


async def _commit() -> RuntimeRail[str]:
    """Resolve the working-tree HEAD sha through the `_git` boundary, the deployed-commit receipt source.

    The one mint of the commit identity threaded into every `ExecReceipt`, so a consumer
    correlating a remote run with the local tree reads the sha off the canonical receipt rather than the
    push re-deriving it per leg. `--short` keeps the abbreviated form the receipt carries.

    Returns:
        `Ok(short_sha)` on a clean repo, or `Error(BoundaryFault)` when `git rev-parse` fails.
    """
    return (await _git("rev-parse", "--short", "HEAD")).map(lambda raw: raw.decode().strip())


# --- [SSH_OPS]


@asynccontextmanager
async def _open(target: RemoteTarget, cfg: MaghzSettings, manifest: Manifest, env: RemoteEnv, commit: str) -> AsyncIterator[_Session]:
    """Open one scoped connection under `guard(RetryClass.HTTP)` plus its SFTP client, yielding the `_Session`.

    `asyncssh.connect` is driven through the member-cached `guard(RetryClass.HTTP)` caller so the transient
    SSH faults the `runtime` `POLICY[RetryClass.HTTP].target` admits retry on the same band as httpx
    transients, while terminal auth/host-key faults surface immediately (classified to `BoundaryFault.api`
    at the `_drive` fence wrapping this). The connection and its SFTP client are entered as `async with`
    resources, so their own `__aexit__` owns deterministic teardown on both the success and the
    cancellation path — there is no pool and no second client.

    Yields:
        The live `_Session` threading the connection, SFTP client, target, settings, manifest, and commit.
    """
    conn = await guard(RetryClass.HTTP)(asyncssh.connect, target.host, port=target.port, username=target.user, options=target.options(cfg.remote))
    async with conn, conn.start_sftp_client() as sftp:
        yield _Session(conn=conn, sftp=sftp, target=target, cfg=cfg, manifest=manifest, env=env, commit=commit)


async def _exec(session: _Session, argv: tuple[str, ...]) -> RuntimeRail[Detail]:
    """`EXEC` body: push the tree, run the command, pull the workroot back, project the `ExecReceipt`.

    The clean `SSHCompletedProcess` projects into the receipt; the pull rides `sftp.mget(..., recurse=True)`
    with the per-file completion folded into a count and the per-file error folded into a note. A non-zero
    command exit raised `ProcessError` inside `session.run` and never reaches this projection.

    Returns:
        The `ExecReceipt` carrying the target identity, commit, completed-process outcome, and counts.
    """
    pushed, push_notes = await session.push()
    process = await session.run(*argv)
    pull_notes: list[str] = []
    pulled: set[bytes] = set()
    await session.sftp.mget(
        session.target.workroot,
        localpath=str(session.cfg.artifacts_dir),
        recurse=True,
        progress_handler=lambda _src, dst, copied, total: pulled.add(dst) if copied >= total else None,
        error_handler=lambda exc: pull_notes.append(f"pull-error {exc}"),
    )
    signal = process.exit_signal
    return Ok(
        ExecReceipt(
            target=session.target.label,
            host=session.target.host,
            commit=session.commit,
            exit_status=process.exit_status,
            exit_signal=signal[0] if isinstance(signal, tuple) else signal,
            pushed=pushed,
            pulled=len(pulled),
            notes=(*push_notes, *pull_notes),
        )
    )


async def _prelude() -> RuntimeRail[tuple[Manifest, str]]:
    """Resolve the git manifest and HEAD sha on the rail as one dependent pair, short-circuiting the first fault.

    The two git facts are dependent on a clean repo, so the manifest binds the sha through `bind`
    short-circuit (the RAILS abort discipline for dependent steps): a probe `Error(BoundaryFault)` returns
    before any connection opens, and only a clean pair reaches the caller. The pair is then threaded into
    the connection-scoped body without re-derivation.

    Returns:
        `Ok((manifest, commit))` when both probes succeed, or the first `Error(BoundaryFault)` either minted.
    """
    match await _manifest():
        case Result(tag="ok", ok=manifest):
            return (await _commit()).map(lambda commit: (manifest, commit))
        case Result(error=manifest_fault):
            return Error(manifest_fault)


async def _drive(
    op: RemoteOp, target: RemoteTarget, cfg: MaghzSettings, body: Callable[[_Session], Awaitable[RuntimeRail[Detail]]]
) -> RuntimeRail[Envelope]:
    """The one connection-scoped spine: bind context, resolve the git prelude, open the session, fence the body.

    Both verbs share this spine — only `body` differs. `structlog` binds the rail/op facts once; the
    dependent `_prelude` resolves the manifest and commit on the rail (a probe `Error(BoundaryFault)`
    short-circuits before any connection opens); the clean pair opens one `_Session` under
    `guard(RetryClass.HTTP)`; and the whole connection body runs inside `async_boundary(op.subject, ...)`,
    so the git boundary's `resource`/`deadline`/`boundary` discrimination and the SSH boundary's
    `ProcessError`/`SFTPError`/disconnect faults ride the one rail to the CLI projection. The body's `Detail`
    folds into a `completed(OK, detail)` envelope; a surviving `Error(BoundaryFault)` lowers once at the CLI
    `runtime.lower` edge.

    Args:
        op: The remote verb whose `subject` fences the boundary and binds the structlog context.
        target: The resolved remote target (host, port, user, known-hosts policy, workroot).
        cfg: The validated settings owning the connection, env projection, SFTP bounds, and git prelude.
        body: The connection-scoped body producing the verb's `Detail` over the open `_Session`.

    Returns:
        `Ok(completed(...))` carrying the verb receipt, or `Error(BoundaryFault)` the CLI seam lowers.
    """
    match RemoteEnv.of(cfg):
        case Result(tag="error", error=env_fault):
            return Error(env_fault)
        case Result(ok=remote_env):
            env = remote_env

    async def _connected(staged: tuple[Manifest, str]) -> RuntimeRail[Envelope]:
        manifest, commit = staged

        async def _session() -> RuntimeRail[Envelope]:
            async with _open(target, cfg, manifest, env, commit) as session:
                return (await body(session)).map(lambda detail: completed(Status.OK, detail))

        return (await async_boundary(op.subject, _session)).bind(lambda rail: rail)

    with structlog.contextvars.bound_contextvars(rail="remote", op=op.value):
        match await _prelude():
            case Result(tag="ok", ok=staged):
                return await _connected(staged)
            case Result(error=prelude_fault):
                return Error(prelude_fault)


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(request: RemoteRequest, cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    match RemoteTarget.from_config(cfg.remote):
        case Result(tag="error", error=target_fault):
            return Error(target_fault)
        case Result(ok=target):
            match request:
                case RemoteExec(argv=argv):
                    return await _drive(RemoteOp.EXEC, target, cfg, lambda session: _exec(session, argv))
                case _ as unreachable:
                    assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["ExecReceipt", "KnownHostsPolicy", "Manifest", "RemoteExec", "RemoteOp", "RemoteRequest", "RemoteTarget", "run"]
