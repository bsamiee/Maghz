"""Cloud-sync rail: one polymorphic verb driving `rclone` to back up and restore the maghz system.

A single `run` entrypoint discriminates on a closed `CloudOp` and lowers to the stdout `Envelope`
itself (it owns the `completed`/`fault` lift, so the CLI binds it with no `project` seam): `SYNC`
dumps the ledger and bisyncs the content tree to both remotes, `RESTORE` pulls the latest dump and
bisyncs back. `_BUILD` is the verb table, one row per `CloudOp`; `assert_never` guards the
fallthrough. The remote fan-out is never a raw `anyio.create_task_group` — it is one
`drain` over `Block.of_seq([Admit(retried=(RetryClass.PROC, work)) for remote in Remote])`, so
the concurrency bound, per-unit deadline, and spawn-flap retry are the runtime lane's, not this
rail's. `_spawn` is the sole subprocess boundary and the ONLY `@stamina.retry` in the file: it owns
`rclone`'s exit map (`0`/`9` success, `5`/`7` retriable, `1`/`8` and every other non-zero fatal) and
raises `_RcloneTransient` for both retriable exits so `_rclone_transient_hook` drives the backoff
(both `5` and `7` take the same 60 s wait override) — the one case that forces a raised exception,
because `stamina`'s `BackoffHook` inspects an `Exception`, never a `Result.Error`. A returncode is not
an exception, so neither exit is retriable through `RetryClass.PROC` (which targets `OSError` only);
the `@stamina.retry` decoration owns the exit-driven retry. `_rclone` wraps `_spawn` and lowers an exhausted-retry escape
to the typed `CloudFault` rail, so interior code never sees a raised exit. The per-remote `CloudFault`
lifts to the runtime `BoundaryFault` at the drain admission so `DrainReceipt.faults` stays typed;
`run` folds `DrainReceipt.values` into the `CloudSyncDetail` receipt and projects a partial remote
failure to `Status.FAILED` with a `Row` per remote that never materialized. The whole operation is
bounded by `anyio.fail_after(cfg.cloud.op_timeout_s)` at this CLI edge — a deadline trip is a
process-level failure that propagates, not a `CloudFault`. The dump staging dir is staged through
`contextlib.AsyncExitStack` with a `anyio.CancelScope(shield=True)` cleanup callback; no `asyncio` is
imported anywhere.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
import contextlib
from datetime import datetime, UTC
from enum import StrEnum
import shutil
import tempfile
from typing import assert_never, Literal

import anyio
import anyio.to_thread
from expression import Error, Ok, Result
from expression.collections import Block, Map
from frozendict import frozendict
import keyring
import msgspec
import stamina
import structlog

from admin.core import completed, Detail, Envelope, fault, Row, Status
from admin.runtime import Admit, BoundaryFault, drain, DrainReceipt, LanePolicy, RetryClass
from admin.settings import MaghzSettings
from admin.settings.config import CloudConfig, Remote


# --- [TYPES] ---------------------------------------------------------------------------


class CloudOp(StrEnum):
    """The closed verb vocabulary `run` discriminates on; one `_BUILD` row per member."""

    SYNC = "sync"  # pg_dump + content bisync to both remotes
    RESTORE = "restore"  # pg_restore from a remote dump + content bisync back


# rclone/pg-tool boundary cases. Own alias in this file: it does NOT extend `admin.db.Boundary`;
# `"spawn"` carries the `OSError` (missing binary / path) seam, the other three the tool exits.
type CloudBoundary = Literal["rclone", "pg_dump", "pg_restore", "spawn"]


class _RcloneTransient(Exception):  # noqa: N818 - the platform-forced retry seam carries a CloudFault, not an Error-suffixed alias
    """The named platform-forced retry seam: raised only for a retriable rclone exit (`5`/`7`).

    `stamina`'s `BackoffHook` receives an `Exception` instance and cannot inspect a `Result.Error`
    value, so the retriable-exit case raises this carrier rather than returning a rail. It wraps the
    `CloudFault` so the `_rclone` boundary projects the exhausted-retry escape without rebuilding it.
    No parallel `_RcloneRateLimit`/`_CloudError` wrapper exists; this is the one such class.
    """

    def __init__(self, fault: CloudFault) -> None:
        self.fault = fault
        super().__init__(str(fault))


# --- [MODELS] --------------------------------------------------------------------------


class CloudSyncDetail(Detail, frozen=True, tag="cloud"):
    """The typed cloud-sync receipt: which verb ran, the remotes reached, and the folded transfer tally."""

    op: CloudOp
    remotes: tuple[Remote, ...]
    transferred: int = 0
    errors: int = 0
    checks: int = 0
    elapsed_s: float = 0.0
    dump_path: str | msgspec.UnsetType = msgspec.UNSET
    restored_from: str | msgspec.UnsetType = msgspec.UNSET


class _RcloneStats(msgspec.Struct, frozen=True, gc=False):
    """The inner `stats` object rclone nests under each `--use-json-log` summary line (camelCase wire).

    The transfer-count field decodes from the rclone wire key `transfers` (`transferred` is never a
    key rclone emits, so a field literally named `transferred` would decode to its `0` default on
    every line); `msgspec.field(name="transfers")` binds the wire key while the receipt fold and the
    `CloudSyncDetail.transferred` slot keep the domain name. `forbid_unknown_fields` stays default so
    the unmodelled `bytes`/`speed`/`totalTransfers` keys are ignored.
    """

    transferred: int = msgspec.field(default=0, name="transfers")
    errors: int = 0
    checks: int = 0
    elapsedTime: float = 0.0  # noqa: N815 - rclone JSON field name, decoded verbatim


class _RcloneLogLine(msgspec.Struct, frozen=True, gc=False):
    """The outer `--use-json-log` line wrapper; a non-stats line decodes with `stats is None`, skipped."""

    level: str = ""
    msg: str = ""
    stats: _RcloneStats | None = None


class _RemoteResult(msgspec.Struct, frozen=True, gc=False):
    """One drain child's per-remote outcome: the remote, its summed stats, and the dump path on sync."""

    remote: Remote
    stats: _RcloneStats
    dump_path: str | msgspec.UnsetType = msgspec.UNSET


# --- [ERRORS] --------------------------------------------------------------------------


class CloudFault(msgspec.Struct, frozen=True, gc=False):
    """A cloud-sync boundary failure tagged by the tool that raised it, projecting to one fault envelope."""

    op: CloudBoundary
    message: str
    remote: Remote | None = None
    exit_code: int | None = None

    def lift(self) -> BoundaryFault:
        """Lift this typed cloud fault to the runtime `BoundaryFault` rail the drain receipt carries.

        The failing remote (or the tool name on a pg/spawn fault) is the boundary subject so the
        `run` fold can name which remote never materialized from the drain receipt alone.

        Returns:
            A `BoundaryFault(boundary=(subject, detail))` whose subject is the remote value when a
            remote is bound, else the tool `op`, and whose detail carries the message and exit code.
        """
        subject = self.remote.value if self.remote is not None else self.op
        detail = self.message if self.exit_code is None else f"{self.message} (exit {self.exit_code})"
        return BoundaryFault(boundary=(subject, detail))

    def envelope(self) -> Envelope:
        """Project this boundary failure to a `fault` envelope, carrying the tool, remote, and exit context."""
        remote = {"remote": self.remote.value} if self.remote is not None else {}
        exit_code = {"exit_code": str(self.exit_code)} if self.exit_code is not None else {}
        return fault(self.message, {"op": self.op, **remote, **exit_code})


# --- [SERVICES] ------------------------------------------------------------------------

# One decoder for the rclone `--use-json-log` line shape, resolved once at import rather than per
# stderr line; `_rclone_stats` scans every line through it inside a `try/except msgspec.DecodeError`.
_LOG_DECODER = msgspec.json.Decoder(type=_RcloneLogLine)


# --- [TABLES] --------------------------------------------------------------------------


def _rclone_transient_hook(exc: Exception, /) -> bool | float:
    """The sole `stamina` backoff hook on `_spawn`: a 60 s override for a transient rclone exit, exponential for a spawn flap.

    Args:
        exc: The exception `stamina` caught on the last attempt, the retry-strategy discriminant.

    Returns:
        `60.0` for `_RcloneTransient` (rclone exit `5` temporary or `7` rate-limit/quota, both taking
        the same wait override), `True` for `OSError` (a spawn flap retried with the default
        exponential backoff), `False` for every other escape (non-retriable).
    """
    match exc:
        case _RcloneTransient():
            return 60.0
        case OSError():
            return True
        case _:
            return False


# --- [OPERATIONS] ----------------------------------------------------------------------


def _env_for(remote: Remote, cfg: CloudConfig) -> Mapping[str, str]:
    """Assemble the immutable `RCLONE_CONFIG_<REMOTE>_*` env block for one remote, total over `Remote`.

    The token is resolved at call time — `keyring.get_password(cfg.keyring_service, remote.value)`
    first, falling back to the `RemoteCredentials.token` VPS env path when the keyring returns `None`
    — never at import. Drive carries the service-account credential strategy (`SCOPE`,
    `SERVICE_ACCOUNT_CREDENTIALS` passed as the raw service-account JSON blob rclone parses verbatim —
    never a base64 wrapper, which rclone cannot decode); OneDrive carries the client-credentials
    strategy (`DRIVE_ID`). The two arms add disjoint strategy keys on top of the shared `common` block;
    `match remote` is total with `assert_never`.

    Args:
        remote: The remote whose `RCLONE_CONFIG_<REMOTE.value.upper()>_*` block is built.
        cfg: The cloud settings owning the per-remote credentials and the keyring service name.

    Returns:
        A frozen `frozendict[str, str]` of the remote's rclone env config, ready as `env=` for
        `anyio.run_process`; never stored or mutated after construction.
    """
    conf = cfg.remotes[remote]
    prefix = f"RCLONE_CONFIG_{remote.value.upper()}"
    token = keyring.get_password(cfg.keyring_service, remote.value) or conf.token
    common = {
        f"{prefix}_TYPE": remote.value,
        f"{prefix}_CLIENT_ID": conf.client_id,
        f"{prefix}_CLIENT_SECRET": conf.client_secret,
        f"{prefix}_TOKEN": token,
    }
    match remote:
        case Remote.DRIVE:
            return frozendict({**common, f"{prefix}_SCOPE": "drive", f"{prefix}_SERVICE_ACCOUNT_CREDENTIALS": conf.service_account_credentials})
        case Remote.ONEDRIVE:
            return frozendict({**common, f"{prefix}_DRIVE_ID": conf.drive_id})
        case unreachable:
            assert_never(unreachable)


def _rclone_stats(stderr: bytes) -> _RcloneStats:
    """Fold the rclone `--use-json-log` stderr into one summed `_RcloneStats`, skipping non-JSON lines.

    Each line is decoded through the shared `_LOG_DECODER`; a `msgspec.DecodeError` (banner/progress
    noise) is skipped, and only lines carrying a nested `stats` object contribute. `transferred`
    (the rclone wire key `transfers`), `errors`, and `checks` sum across every stats line; `elapsedTime`
    takes the run maximum (it is monotone within a run, so the max is the final wall figure).

    Args:
        stderr: The raw rclone stderr from one `--use-json-log --stats <interval>` invocation, where the
            interval exceeds the op (`--stats 1m`) so the single end-of-run summary line fires while the
            periodic ticks stay suppressed — `--stats 0` would suppress the summary too and zero the tally.

    Returns:
        The folded `_RcloneStats`; a zero-sentinel `_RcloneStats()` when no stats line decodes.
    """

    def _decode(line: bytes) -> _RcloneStats | None:
        try:
            return _LOG_DECODER.decode(line).stats
        except msgspec.DecodeError:
            return None

    parsed = Block.of_seq(stats for line in stderr.splitlines() if line.strip() and (stats := _decode(line)) is not None)
    return parsed.fold(
        lambda acc, s: _RcloneStats(
            transferred=acc.transferred + s.transferred,
            errors=acc.errors + s.errors,
            checks=acc.checks + s.checks,
            elapsedTime=max(acc.elapsedTime, s.elapsedTime),
        ),
        _RcloneStats(),
    )


@stamina.retry(on=_rclone_transient_hook, attempts=3, wait_initial=2.0, wait_max=30.0, wait_jitter=1.0)
async def _spawn(argv: tuple[str, ...], env: Mapping[str, str], op: CloudBoundary, remote: Remote | None) -> Result[_RcloneStats, CloudFault]:
    """Drive one subprocess and grade its exit; the sole retried boundary over the `rclone`/`pg` map.

    `anyio.run_process(check=False)` so this owns exit interpretation. Exit `0`/`9` are success
    (9 = no files transferred); `5` (temporary) and `7` (rate-limit/quota) both raise `_RcloneTransient`
    so the hook drives the retry with the same 60 s wait override; every other non-zero exit returns a
    non-retriable `Error(CloudFault)`. A missing binary raises `OSError`, retried by the hook's `OSError`
    arm and re-raised on exhaustion for `_rclone` to lower to `Error(CloudFault(op="spawn"))`.

    Args:
        argv: The full `rclone`/`pg_dump`/`pg_restore` command and its arguments.
        env: The per-remote `RCLONE_CONFIG_*` block (empty for pg tools), passed verbatim as `env=`.
        op: The `CloudBoundary` case stamped into a lifted fault (`rclone`/`pg_dump`/`pg_restore`).
        remote: The remote bound to a fault, or `None` for the pg tools and the spawn seam.

    Returns:
        `Ok(_RcloneStats)` on a success exit (stats folded from stderr for rclone, zero-sentinel for
        pg tools), or `Error(CloudFault)` for a fatal exit.

    Raises:
        _RcloneTransient: On a retriable rclone exit (`5`/`7`), carrying the `CloudFault` for the hook.
        OSError: On a spawn failure, raised so the retry aspect replays it within the budget.
    """
    run = await anyio.run_process(list(argv), env=dict(env), check=False)
    code = run.returncode
    if code in {0, 9}:
        return Ok(_rclone_stats(run.stderr) if op == "rclone" else _RcloneStats())
    message = run.stderr.decode(errors="replace").strip() or f"{op} exited {code}"
    fault_value = CloudFault(op=op, message=message, remote=remote, exit_code=code)
    if code in {5, 7}:
        raise _RcloneTransient(fault_value)
    return Error(fault_value)


async def _rclone(*argv: str, env: Mapping[str, str], op: CloudBoundary, remote: Remote | None) -> Result[_RcloneStats, CloudFault]:
    """Run one subprocess through the retried `_spawn`, lowering an exhausted-retry escape to the rail.

    `_spawn` owns the exit grading and the `@stamina.retry`; this boundary lowers the two escapes
    that survive the retry budget — a `_RcloneTransient` (the exhausted rate-limit, carrying its
    `CloudFault`) and an `OSError` (the exhausted spawn flap, the `"spawn"` case) — so interior code
    only ever sees the typed `Result` rail, never a raised exit.

    Args:
        argv: The full `rclone`/`pg_dump`/`pg_restore` command and its arguments.
        env: The per-remote `RCLONE_CONFIG_*` block (empty for pg tools), passed verbatim as `env=`.
        op: The `CloudBoundary` case stamped into a lifted fault (`rclone`/`pg_dump`/`pg_restore`).
        remote: The remote bound to a fault, or `None` for the pg tools and the spawn seam.

    Returns:
        `Ok(_RcloneStats)` on success, or `Error(CloudFault)` for a fatal exit, an exhausted
        rate-limit (the carried fault), or an exhausted spawn flap (`op="spawn"`).
    """
    try:
        return await _spawn(tuple(argv), env, op, remote)
    except _RcloneTransient as exc:
        return Error(exc.fault)
    except OSError as exc:
        return Error(CloudFault(op="spawn", message=str(exc), remote=remote))


def _work(
    remote: Remote, cfg: MaghzSettings, dump: str, *, resync: bool, upload: str | None
) -> Callable[[], Awaitable[Result[_RemoteResult, BoundaryFault]]]:
    """Build the per-remote drain child: bind the structlog context, copy the dump, then bisync the tree.

    `upload` set (sync) runs `rclone copy <dump> <remote>:<remote_dump_path>` before the bisync and
    records its path on the `_RemoteResult`; `upload` `None` (restore) bisyncs only. Both calls ride
    `_rclone`; the first `Error(CloudFault)` short-circuits and lifts to the runtime `BoundaryFault`
    so `DrainReceipt.faults` stays typed and `DrainReceipt.values` carries only materialized remotes.

    Args:
        remote: The remote this child fans out to; its value binds the structlog context and env block.
        cfg: The validated settings owning the cloud config, remote paths, content root, and filters.
        dump: The local dump-file path produced by `pg_dump` (sync) or downloaded (restore).
        resync: Whether to append `--resync` to the bisync (restore, or `cfg.cloud.force_resync`).
        upload: The `<remote>:<dump_path>` target when the dump uploads (sync), else `None` (restore).

    Returns:
        An async `Work` callable returning `Ok(_RemoteResult)` once the remote's transfers complete,
        or `Error(BoundaryFault)` lifted from the first per-remote `CloudFault`.
    """
    cloud = cfg.cloud
    env = _env_for(remote, cloud)
    bisync = (
        "rclone",
        "bisync",
        str(cloud.content_root),
        f"{remote.value}:{cloud.remote_content_path}",
        "--resync-mode",
        "path1",
        "--conflict-resolve",
        "newer",
        "--conflict-loser",
        "pathname",
        "--conflict-suffix",
        "conflict",
        "--resilient",
        "--recover",
        "--filters-file",
        str(cloud.filter_file),
        "--check-access",
        "--use-json-log",
        "--stats",
        "1m",
        "--log-level",
        "INFO",
        *(("--resync",) if resync else ()),
    )

    async def _run() -> Result[_RemoteResult, BoundaryFault]:
        with structlog.contextvars.bound_contextvars(remote=remote.value):
            if upload is not None:
                match await _rclone("rclone", "copy", dump, upload, env=env, op="rclone", remote=remote):
                    case Result(tag="error", error=copy_fault):
                        return Error(copy_fault.lift())
            match await _rclone(*bisync, env=env, op="rclone", remote=remote):
                case Result(tag="ok", ok=stats):
                    return Ok(_RemoteResult(remote=remote, stats=stats, dump_path=upload if upload is not None else msgspec.UNSET))
                case Result(error=bisync_fault):
                    return Error(bisync_fault.lift())

    return _run


async def _fan_out(cfg: MaghzSettings, dump: str, *, resync: bool, upload: bool) -> DrainReceipt:
    """Drain the per-remote work over both remotes through the runtime lane, never a raw task group.

    One `Admit(retried=(RetryClass.PROC, work))` per `Remote` rides `LanePolicy.drain`; the lane owns
    the concurrency bound and the spawn-flap retry. `upload` chooses the per-remote dump target path
    (sync uploads to `<remote>:<remote_dump_path>`; restore passes `None`).

    Args:
        cfg: The validated settings owning the cloud config (capacity, remote paths, filters).
        dump: The local dump-file path the children copy and bisync against.
        resync: Whether the bisync appends `--resync` (restore, or forced on sync).
        upload: Whether the dump uploads per remote (sync) or the children bisync only (restore).

    Returns:
        The frozen `DrainReceipt` whose `values` are the materialized `_RemoteResult` block and whose
        `faults` carry the lifted per-remote boundary failures.
    """
    remote_dump = cfg.cloud.remote_dump_path
    policy = LanePolicy(capacity=len(Remote))
    units = Block.of_seq(
        Admit(retried=(RetryClass.PROC, _work(remote, cfg, dump, resync=resync, upload=f"{remote.value}:{remote_dump}" if upload else None)))
        for remote in Remote
    )
    return await drain(policy, units, Map.empty())


def _detail(receipt: DrainReceipt, op: CloudOp, *, dump_path: str | msgspec.UnsetType, restored_from: str | msgspec.UnsetType) -> CloudSyncDetail:
    """Fold a `DrainReceipt` into the `CloudSyncDetail` receipt, summing the materialized remote stats.

    `DrainReceipt.values` is `object`-typed (the lane is concept-agnostic); each entry is a
    `_RemoteResult` this fold narrows and sums. `remotes` is exactly the set that materialized — the
    failed remotes are read off the `tuple(Remote)` complement by `run`.

    Args:
        receipt: The drain evidence carrying the per-remote `_RemoteResult` values and any faults.
        op: The verb that produced the receipt, stamped onto the detail.
        dump_path: The `<remote>:<path>` the dump was written to (sync), else `msgspec.UNSET`.
        restored_from: The `<remote>:<path>` the dump was read from (restore), else `msgspec.UNSET`.

    Returns:
        The typed `CloudSyncDetail` with the summed `transferred`/`errors`/`checks`/`elapsed_s` tally.
    """
    results = _materialized(receipt)
    seed: tuple[int, int, int, float, tuple[Remote, ...]] = (0, 0, 0, 0.0, ())

    def _sum(acc: tuple[int, int, int, float, tuple[Remote, ...]], result: _RemoteResult) -> tuple[int, int, int, float, tuple[Remote, ...]]:
        transferred, errors, checks, elapsed, remotes = acc
        stats = result.stats
        return (
            transferred + stats.transferred,
            errors + stats.errors,
            checks + stats.checks,
            max(elapsed, stats.elapsedTime),
            (*remotes, result.remote),
        )

    transferred, errors, checks, elapsed, remotes = results.fold(_sum, seed)
    return CloudSyncDetail(
        op=op,
        remotes=remotes,
        transferred=transferred,
        errors=errors,
        checks=checks,
        elapsed_s=elapsed,
        dump_path=dump_path,
        restored_from=restored_from,
    )


def _materialized(receipt: DrainReceipt) -> Block[_RemoteResult]:
    """Narrow the `object`-typed drain values to the `_RemoteResult` block the fold consumes."""
    return Block.of_seq(value for value in receipt.values if isinstance(value, _RemoteResult))


@contextlib.asynccontextmanager
async def _staging() -> AsyncIterator[anyio.Path]:
    """Stage a dump directory, removing it under a shielded `CancelScope` so cleanup survives a deadline trip.

    The dump dir is created with `tempfile.mkdtemp` and torn down with `shutil.rmtree` offloaded to a
    worker thread inside `anyio.CancelScope(shield=True)`, so the `fail_after` deadline that fires
    mid-operation still completes the cleanup rather than leaking the staged archive — the shield
    protects the offload checkpoint from the in-flight cancellation.

    Yields:
        The staging directory as an `anyio.Path` for the dump-file path construction.
    """
    path = tempfile.mkdtemp(prefix="maghz-cloud-")
    try:
        yield anyio.Path(path)
    finally:
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(lambda: shutil.rmtree(path, ignore_errors=True))


async def _sync_detail(cfg: MaghzSettings) -> Result[CloudSyncDetail, CloudFault]:
    """`CloudOp.SYNC` builder: dump the ledger once, then fan the dump + content bisync to both remotes.

    `pg_dump` writes a custom-format zstd-3 archive into a shielded staging dir; its failure
    short-circuits to `Error(CloudFault(op="pg_dump"))` before any remote is touched. The drain then
    uploads the dump and bisyncs the tree per remote (`--resync` only when `cfg.cloud.force_resync`).
    The folded detail carries the remote dump path of the first materialized remote.

    Args:
        cfg: The validated settings owning the DSN, the cloud remote paths, and the force-resync flag.

    Returns:
        `Ok(CloudSyncDetail)` once the dump and both-remote drain complete (the detail's `remotes`
        names the materialized set), or `Error(CloudFault)` when `pg_dump` itself fails.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        dump = str(staging / f"{stamp}_maghz.dump")
        argv = ("pg_dump", str(cfg.database.dsn), "-F", "c", "-Z", "zstd:3", "-f", dump, "-O", "--no-privileges")
        match await _rclone(*argv, env={}, op="pg_dump", remote=None):
            case Result(tag="error", error=dump_fault):
                return Error(dump_fault)
        receipt = await _fan_out(cfg, dump, resync=cfg.cloud.force_resync, upload=True)
        first = next((result.dump_path for result in _materialized(receipt) if result.dump_path is not msgspec.UNSET), msgspec.UNSET)
        return Ok(_detail(receipt, CloudOp.SYNC, dump_path=first, restored_from=msgspec.UNSET))


async def _restore_detail(cfg: MaghzSettings) -> Result[CloudSyncDetail, CloudFault]:
    """`CloudOp.RESTORE` builder: pull the latest dump from the primary remote, replay it, then bisync back.

    The dump downloads from the Drive remote into a shielded staging dir; `pg_restore -c` drops and
    recreates before reload, and its failure short-circuits to `Error(CloudFault(op="pg_restore"))`.
    The drain then bisyncs the tree back to both remotes with `--resync` always on (restore
    re-establishes the path baseline). The detail records the `<remote>:<path>` the dump came from.

    Args:
        cfg: The validated settings owning the DSN and the cloud remote paths.

    Returns:
        `Ok(CloudSyncDetail)` once the restore and both-remote drain complete, or `Error(CloudFault)`
        when the dump download or `pg_restore` fails.
    """
    primary = Remote.DRIVE
    source = f"{primary.value}:{cfg.cloud.remote_dump_path}"
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        match await _rclone(
            "rclone", "copy", source, str(staging), "--use-json-log", "--stats", "1m", env=_env_for(primary, cfg.cloud), op="rclone", remote=primary
        ):
            case Result(tag="error", error=download_fault):
                return Error(download_fault)
        dump = await _first_dump(staging)
        argv = ("pg_restore", "-d", str(cfg.database.dsn), "-c", "-O", "--no-privileges", str(dump))
        match await _rclone(*argv, env={}, op="pg_restore", remote=None):
            case Result(tag="error", error=restore_fault):
                return Error(restore_fault)
        receipt = await _fan_out(cfg, str(dump), resync=True, upload=False)
        return Ok(_detail(receipt, CloudOp.RESTORE, dump_path=msgspec.UNSET, restored_from=f"{source}/{dump.name}"))


async def _first_dump(staging: anyio.Path) -> anyio.Path:
    """Return the first staged `*.dump` in the restore staging dir, or the dir itself when none landed.

    The download lands one archive into the staging dir; restore replays the first `*.dump`. An empty
    dir yields the dir path so the subsequent `pg_restore` fails with a clear missing-file fault
    rather than this function raising.

    Args:
        staging: The restore staging directory the dump downloaded into.

    Returns:
        The first `*.dump` path under `staging`, or `staging` itself when the download produced none.
    """
    async for entry in staging.iterdir():
        if entry.suffix == ".dump":
            return entry
    return staging


# --- [TABLES] --------------------------------------------------------------------------

# verb -> its full dump/restore builder. The key set equals `CloudOp` exactly, so `run`'s
# subscription is total; each builder owns its own staging scope, drain, and typed rail leg.
_BUILD: frozendict[CloudOp, Callable[[MaghzSettings], Awaitable[Result[CloudSyncDetail, CloudFault]]]] = frozendict({
    CloudOp.SYNC: _sync_detail,
    CloudOp.RESTORE: _restore_detail,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: CloudOp, cfg: MaghzSettings, /) -> Envelope:
    """Run one cloud-sync verb by `op`, lowering the typed rail to the stdout `Envelope` at this edge.

    `_BUILD[op]` selects the builder; the whole operation (dump/restore plus both-remote drain) runs
    inside `anyio.fail_after(cfg.cloud.op_timeout_s)`, the one permitted CLI-boundary deadline — a
    trip re-raises as `TimeoutError` at the scope boundary (`fail_after` converts its internal
    cancellation there) and propagates to the `__main__` handler, never folding into a `CloudFault`.
    An `Ok` detail projects to `Status.OK` when every targeted remote materialized, else
    `Status.FAILED` with a `Row` per remote that never reported; a builder
    `Error(CloudFault)` (pg-tool or spawn) lowers through `fault`.

    Args:
        op: The cloud-sync verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings owning the DSN, the cloud config, and the operation deadline.

    Returns:
        One stdout `Envelope` — `completed` carrying the `CloudSyncDetail` receipt (`OK` or `FAILED`
        with the failed-remote rows), or a `fault` envelope projected from the boundary `CloudFault`.
    """
    match op:
        case CloudOp.SYNC | CloudOp.RESTORE:
            with anyio.fail_after(cfg.cloud.op_timeout_s):
                outcome = await _BUILD[op](cfg)
        case unreachable:
            assert_never(unreachable)
    match outcome:
        case Result(tag="ok", ok=detail):
            missing = tuple(remote for remote in Remote if remote not in detail.remotes)
            rows = tuple(Row(key=remote.value, text="remote did not complete") for remote in missing)
            return completed(Status.FAILED if missing else Status.OK, detail, rows=rows)
        case Result(error=cloud_fault):
            return cloud_fault.envelope()


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["CloudBoundary", "CloudFault", "CloudOp", "CloudSyncDetail", "run"]
