"""Remote VPS operations: one file owning `exec` and `deploy` plus the shared working-tree push.

`exec` and `deploy` are the two VPS-facing entrypoints; `_push_tree` is the working-tree transfer
both compose (shared, never inlined twice). Both return the domain-internal `RuntimeRail[Envelope]`
exactly like the `stack`/`schema`/`sync` rails, so the one CLI `project` seam in `admin.__main__`
lowers a surviving `Error(BoundaryFault)` to a `fault(...)` envelope once, at the edge — this file
holds no parallel lowering. Every SSH/SFTP boundary lifts through the canonical
`async_boundary("remote.exec" | "remote.deploy", ...)` fault rail from `admin.runtime`; there is no
inline `try/except` and no parallel `RemoteFault` — `BoundaryFault` already spans the fault space
(`resource` for connection loss, `api` for auth/host-key denial, `boundary` for command failure and
remote-stdout decode error). `conn.run(..., check=True)` raises `ProcessError` on non-zero exit, so
the receipt is only ever projected from a clean `SSHCompletedProcess`; a failed run rides the rail.
`deploy` discriminates totally on the relocated `StackOp` owner (`admin.infra.runner`) and decodes
each remote `maghz` stdout into the shared `Envelope`, narrowing `report.detail` to the read-only
`StackDetail`/`SchemaDetail` receipts — never the outer wire `Envelope`. The remote `maghz`
invocation runs `uv run --project <workroot> python -m admin <sub>`, every argument `shlex.quote`-d
and prefixed with the `_REMOTE_ENV` projection, so no shell metacharacter escapes the command.
"""

from collections.abc import Callable
from enum import StrEnum
from pathlib import PurePosixPath
import shlex
from typing import assert_never

import anyio
import asyncssh
from frozendict import frozendict
import msgspec
import structlog

from admin.core import completed, Detail, Envelope, Status
from admin.infra.runner import StackDetail, StackOp
from admin.rails.schema import SchemaDetail
from admin.remote.connection import connection, RemoteTarget
from admin.runtime import async_boundary, RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class RemoteOp(StrEnum):
    """The closed remote verb vocabulary the CLI mounts as commands.

    Two cases only: `PUSH`/`PULL` are excluded because the working-tree push and artifact pull are
    always implicit in `EXEC` and `DEPLOY`, never standalone user-facing verbs.
    """

    EXEC = "exec"
    DEPLOY = "deploy"


# --- [MODELS] --------------------------------------------------------------------------


class ExecReceipt(Detail, frozen=True, gc=False, tag="remote_exec"):
    """One remote `exec` receipt: target identity, the completed-process outcome, and transfer counts.

    `exit_status` / `exit_signal` mirror `asyncssh.SSHCompletedProcess` exactly; both are read off a
    clean completion, because a non-zero exit raises `ProcessError` (lifted to `BoundaryFault.boundary`
    by `async_boundary`) and never reaches this projection.
    """

    target: str
    host: str
    exit_status: int | None
    exit_signal: str | None
    pushed: int
    pulled: int
    notes: tuple[str, ...]


class DeployReceipt(Detail, frozen=True, gc=False, tag="remote_deploy"):
    """One remote `deploy` receipt: the stack verb, push counts, and the decoded remote receipts.

    `up_detail` / `schema_detail` carry the read-only `StackDetail` / `SchemaDetail` decoded from the
    remote `maghz up` and `maghz schema apply` stdout — the typed inner receipts, never the outer wire
    `Envelope`. Both are populated for `UP`; both are `None` for `DOWN` and `STATUS`.
    """

    op: StackOp
    pushed: int
    push_notes: tuple[str, ...]
    up_detail: StackDetail | None
    schema_detail: SchemaDetail | None


# --- [TABLES] --------------------------------------------------------------------------

# The minimal environment projection forwarded into the remote `maghz` process, declared once and
# shared by `exec` and `deploy`. Each row pairs the canonical env key with the projection that mints
# its value from the validated settings, so `MAGHZ_DATABASE_DSN` tracks `cfg.database.dsn` by
# construction and `MAGHZ_LOG__FORMAT` is pinned to the machine-readable renderer; the command builder
# folds each row into a `KEY=<shlex.quote(value)>` export ahead of the remote argv.
_REMOTE_ENV: frozendict[str, Callable[[MaghzSettings], str]] = frozendict({
    "MAGHZ_DATABASE_DSN": lambda cfg: str(cfg.database.dsn),
    "MAGHZ_LOG__FORMAT": lambda _cfg: "json",
})


# --- [OPERATIONS] ----------------------------------------------------------------------


def _command(target: RemoteTarget, cfg: MaghzSettings, argv: tuple[str, ...]) -> str:
    """Compose one quoted remote command: `cd <workroot> && <env exports> <argv>`.

    Every token routes through `shlex.quote`, so a workroot, env value, or argument carrying shell
    metacharacters cannot escape the command. The `_REMOTE_ENV` projection mints the forwarded env
    pairs (`MAGHZ_DATABASE_DSN` from the settings DSN, `MAGHZ_LOG__FORMAT` pinned to `json`).

    Args:
        target: The remote target whose `workroot` anchors the working directory.
        cfg: The validated settings supplying the forwarded env projection.
        argv: The remote command and its arguments, quoted token by token.

    Returns:
        A single shell-safe command string ready for `conn.run(command, check=True)`.
    """
    exports = " ".join(f"{key}={shlex.quote(project(cfg))}" for key, project in _REMOTE_ENV.items())
    body = " ".join(shlex.quote(token) for token in argv)
    return f"cd {shlex.quote(target.workroot)} && {exports} {body}"


def _maghz(target: RemoteTarget, *subcommand: str) -> tuple[str, ...]:
    """Build the remote `maghz` argv: `uv run --project <workroot> python -m admin <subcommand>`.

    `uv` is pre-installed on the VPS by bootstrap; the pushed `pyproject.toml` drives the project run.

    Args:
        target: The remote target whose `workroot` is the `uv` project directory.
        subcommand: The `admin` subcommand tokens (`("up",)`, `("schema", "apply")`, `("down",)`, ...).

    Returns:
        The argv tuple invoking the remote `maghz` subcommand under `uv run`.
    """
    return ("uv", "run", "--project", target.workroot, "python", "-m", "admin", *subcommand)


async def _manifest(cfg: MaghzSettings) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Enumerate the tracked working tree, partitioning git-lfs pointer paths out of the push set.

    `git ls-files --cached --exclude-standard -z` yields the NUL-delimited tracked manifest; a second
    `git check-attr filter -z --stdin` pass over that manifest reads each path's `filter` attribute, so
    `filter=lfs` paths (which `ls-files` reports as a few-hundred-byte pointer, not the binary object)
    are excluded from the transfer and folded into the returned skip notes rather than pushed as stubs.

    Args:
        cfg: The validated settings; the manifest enumerates the repo tree from the invocation cwd.

    Returns:
        A `(pushable, skipped)` pair of POSIX-relative path tuples — `pushable` are the non-lfs tracked
        files to transfer, `skipped` are the lfs-tracked pointer paths held out of the push.
    """
    root = cfg.artifacts_dir.parent  # the repo root anchoring `maghz` (artifacts_dir is `<root>/.artifacts`)
    listed = await anyio.run_process(("git", "ls-files", "--cached", "--exclude-standard", "-z"), cwd=root)
    tracked = tuple(path for path in listed.stdout.decode().split("\0") if path)
    if not tracked:
        return (), ()
    attrs = await anyio.run_process(("git", "check-attr", "filter", "-z", "--stdin"), cwd=root, input="\0".join(tracked).encode())
    fields = attrs.stdout.decode().split("\0")
    lfs = {fields[index] for index in range(0, len(fields) - 2, 3) if fields[index + 2] == "lfs"}
    return tuple(path for path in tracked if path not in lfs), tuple(sorted(lfs))


async def _push_tree(sftp: asyncssh.SFTPClient, target: RemoteTarget, cfg: MaghzSettings) -> tuple[int, tuple[str, ...]]:
    """Push the tracked working tree to the remote workroot, fanned out per directory under a capacity bound.

    Composed by both `exec` and `deploy`. The tracked manifest (lfs pointers held out by `_manifest`)
    is grouped by parent directory; each directory's files transfer through one
    `sftp.put(..., max_requests=cfg.remote.sftp_max_requests, error_handler=...)`, all fanned out
    inside one `anyio.create_task_group` and gated by `anyio.CapacityLimiter(cfg.remote.sftp_push_concurrency)`
    so the VPS sees a bounded number of concurrent SFTP sessions. A per-file `SFTPError` folds into the
    notes through `error_handler` instead of aborting the whole transfer; held-out lfs paths are noted too.

    Args:
        sftp: The open SFTP session scoped to the remote connection.
        target: The remote target whose `workroot` is the transfer root.
        cfg: The validated settings owning the content root and the SFTP concurrency/request bounds.

    Returns:
        A `(pushed_count, notes)` pair: the number of files transferred and the per-file failure plus
        held-out-lfs notes accumulated during the fan-out.
    """
    pushable, skipped = await _manifest(cfg)
    notes: list[str] = [f"lfs-skipped {path}" for path in skipped]
    if not pushable:
        return 0, tuple(notes)
    workroot = PurePosixPath(target.workroot)
    grouped: dict[str, list[str]] = {}
    for path in pushable:
        grouped.setdefault(str(PurePosixPath(path).parent), []).append(path)
    await sftp.makedirs(target.workroot, exist_ok=True)
    limiter = anyio.CapacityLimiter(cfg.remote.sftp_push_concurrency)

    def _on_error(exc: Exception) -> None:
        notes.append(f"sftp-error {exc}")

    async def _put(relative: str, files: list[str]) -> None:
        async with limiter:
            remotedir = str(workroot / relative) if relative != "." else target.workroot
            await sftp.makedirs(remotedir, exist_ok=True)
            await sftp.put(files, remotedir, max_requests=cfg.remote.sftp_max_requests, error_handler=_on_error)

    async with anyio.create_task_group() as group:
        for relative, files in grouped.items():
            group.start_soon(_put, relative, files)
    return len(pushable) - sum(note.startswith("sftp-error") for note in notes), tuple(notes)


def _narrow[T: Detail](detail: Detail | None, kind: type[T]) -> T | None:
    """Narrow a decoded remote `Envelope.report.detail` to one expected `Detail` subclass, else `None`."""
    return detail if isinstance(detail, kind) else None


async def exec(target: RemoteTarget, argv: tuple[str, ...], *, cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Run one command on the VPS over a scoped connection: push the tree, execute, pull artifacts.

    The single modal entrypoint for remote execution. Under `async_boundary("remote.exec", ...)` it
    opens one scoped connection (`guard(RetryClass.HTTP)`-retried inside `connection`), opens SFTP,
    transfers the working tree through the shared `_push_tree`, runs the command with `check=True`
    (a non-zero exit raises `ProcessError`, lifted to `BoundaryFault.boundary` — never inspected by
    hand), then pulls the workroot back with `sftp.mget(..., recurse=True)`. The clean
    `SSHCompletedProcess` projects into an `ExecReceipt`; any SSH/SFTP/decode escape rides the rail to
    the one CLI `project` lowering.

    Args:
        target: The resolved remote target (host, port, user, known-hosts policy, workroot).
        argv: The remote command and its arguments, quoted into one shell-safe command.
        cfg: The validated settings owning the connection, env projection, and SFTP bounds.

    Returns:
        The domain rail — `Ok(completed(...))` carrying the `ExecReceipt`, or `Error(BoundaryFault)`
        that the CLI `project` seam lowers to a `fault` envelope at the edge.
    """
    structlog.contextvars.bind_contextvars(rail="remote", op=RemoteOp.EXEC.value)

    async def _run() -> Envelope:
        async with connection(target, cfg.remote) as conn, conn.start_sftp_client() as sftp:
            pushed, push_notes = await _push_tree(sftp, target, cfg)
            completed_process = await conn.run(_command(target, cfg, argv), check=True, encoding=None)
            pull_notes: list[str] = []
            pulled: set[bytes] = set()

            def _on_pull(_src: bytes, dst: bytes, copied: int, total: int) -> None:
                if copied >= total:
                    pulled.add(dst)

            await sftp.mget(
                target.workroot,
                localpath=str(cfg.artifacts_dir),
                recurse=True,
                progress_handler=_on_pull,
                error_handler=lambda exc: pull_notes.append(f"pull-error {exc}"),
            )
            signal = completed_process.exit_signal
            receipt = ExecReceipt(
                target=f"{target.user}@{target.host}:{target.port}",
                host=target.host,
                exit_status=completed_process.exit_status,
                exit_signal=signal[0] if isinstance(signal, tuple) else signal,
                pushed=pushed,
                pulled=len(pulled),
                notes=(*push_notes, *pull_notes),
            )
            return completed(Status.OK, receipt)

    return await async_boundary("remote.exec", _run)


async def deploy(target: RemoteTarget, op: StackOp, cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Deploy the stack on the VPS: total `match` over `StackOp`, pushing then running remote `maghz`.

    The single modal entrypoint for remote deployment, discriminating exhaustively on the relocated
    `StackOp` owner. `UP` transfers the working tree through `_push_tree`, runs `maghz up` then
    `maghz schema apply` over SSH, decodes each remote stdout into the shared `Envelope`, and narrows
    `report.detail` to the read-only `StackDetail` / `SchemaDetail`. `DOWN` / `STATUS` run the matching
    `maghz` verb without a push; both decoded details stay `None`. Every SSH/decode escape lifts through
    `async_boundary("remote.deploy", ...)` to the one CLI `project` lowering; a `RESTART`-class new
    `StackOp` case is caught by `assert_never` at static-analysis time.

    Args:
        target: The resolved remote target (host, port, user, known-hosts policy, workroot).
        op: The stack verb to run remotely; selects the push-and-decode arm.
        cfg: The validated settings owning the connection, env projection, and SFTP bounds.

    Returns:
        The domain rail — `Ok(completed(...))` carrying the `DeployReceipt`, or `Error(BoundaryFault)`
        that the CLI `project` seam lowers to a `fault` envelope at the edge.
    """
    structlog.contextvars.bind_contextvars(rail="remote", op=RemoteOp.DEPLOY.value)

    async def _decode(conn: asyncssh.SSHClientConnection, *subcommand: str) -> Envelope:
        run = await conn.run(_command(target, cfg, _maghz(target, *subcommand)), check=True, encoding=None)
        return msgspec.json.decode(run.stdout or b"", type=Envelope)

    async def _up(conn: asyncssh.SSHClientConnection, sftp: asyncssh.SFTPClient) -> DeployReceipt:
        pushed, push_notes = await _push_tree(sftp, target, cfg)
        up_env = await _decode(conn, "up")
        schema_env = await _decode(conn, "schema", "apply")
        up_detail = _narrow(up_env.report.detail if up_env.report else None, StackDetail)
        schema_detail = _narrow(schema_env.report.detail if schema_env.report else None, SchemaDetail)
        return DeployReceipt(op=StackOp.UP, pushed=pushed, push_notes=push_notes, up_detail=up_detail, schema_detail=schema_detail)

    async def _single(conn: asyncssh.SSHClientConnection, verb: StackOp) -> DeployReceipt:
        await _decode(conn, verb.value)
        return DeployReceipt(op=verb, pushed=0, push_notes=(), up_detail=None, schema_detail=None)

    async def _run() -> Envelope:
        async with connection(target, cfg.remote) as conn, conn.start_sftp_client() as sftp:
            match op:
                case StackOp.UP:
                    receipt = await _up(conn, sftp)
                case StackOp.DOWN | StackOp.STATUS:
                    receipt = await _single(conn, op)
                case _ as unreachable:
                    assert_never(unreachable)
            return completed(Status.OK, receipt)

    return await async_boundary("remote.deploy", _run)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["DeployReceipt", "ExecReceipt", "RemoteOp", "deploy", "exec"]
