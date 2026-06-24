"""Cloud-sync rail: one polymorphic verb driving `rclone` to back up and restore the maghz ledger.

A single `run` entrypoint discriminates a closed `CloudOp` over the total `_BUILD` table and returns the
domain-internal `RuntimeRail[Envelope]` the CLI `runtime.lower` seam collapses once at the edge — the same
contract `schema`/`sync`/`ledger`/`n8n` expose, never a per-rail `.envelope()` self-lowering. `SYNC` dumps
the ledger and bisyncs the content tree to both remotes; `RESTORE` pulls the latest dump and bisyncs back.
`_BUILD` is the verb table, one row per `CloudOp`, exhaustive — so `run(op)` is `await _BUILD[op](cfg)`
with no `match`/`assert_never` ceremony around a total subscription.

Every subprocess rides the one substrate `runtime.spawn` boundary (`anyio.run_process(check=False)` +
`guard(RetryClass.PROC)` + the exhausted-`OSError` lift), so this rail owns no `@stamina.retry`, no spawn
flap loop, and no raised-exit carrier. `_graded` is the pure rclone/pg exit projection over the returned
`CompletedProcess`: `0`/`9` are success (`9` = no files transferred), every other non-zero exit mints
`Error(BoundaryFault(boundary=(subject, detail)))` directly — the one closed fault family, no per-rail
`CloudFault`. rclone's transient exit `5` is retried by rclone itself (`--retries`/`--retries-sleep` on the
argv), where transient backoff belongs; exit `7` (quota/auth) is fatal and a re-spawn cannot clear it, so
it surfaces as a `boundary` fault rather than a doomed Python-side replay.

The remote fan-out is never a raw `anyio.create_task_group` — it is one `drain` over
`Block.of_seq([Admit.guarded(RetryClass.PROC, work) for remote in Remote])`, so the concurrency bound,
per-unit deadline, and spawn-flap retry are the runtime lane's. Each child returns its full
`RuntimeRail[_RemoteResult]`, so `DrainReceipt.values` carries the materialized remotes and the lossless
`DrainReceipt.faults` the typed boundary failures with no lift arm in the child. `_detail` folds the
materialized values once through `_results`; `_ok` projects a partial remote failure to `Status.FAILED`,
naming each failed remote off its own `BoundaryFault.headline()` (the lossless drain fault, not a generic
string) and covering any remote that never reported off the `tuple(Remote)` complement.

Secrets ride the op-injected environment only: the per-remote rclone token resolves from
`RemoteCredentials.token` (the `MAGHZ_CLOUD__REMOTES__*` env owner) — the macOS login keychain is never
read or written, so no Touch-ID/password prompt can surface from a backup. The whole operation is bounded
by `anyio.move_on_after(cfg.cloud.op_timeout_s)` at this CLI edge: a tripped deadline is CONTAINED and
minted as `Error(BoundaryFault(deadline=(op, budget)))` carrying the budget the substrate egress preserves
as a native scalar — never a raw `TimeoutError` escaping the rail without a typed receipt. The dump staging
dir is the native `anyio.TemporaryDirectory`, torn down inside a shielded `CancelScope` so the cleanup
survives a deadline trip; no `asyncio` is imported anywhere.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
import contextlib
from datetime import datetime, UTC
from enum import StrEnum
from subprocess import CompletedProcess  # noqa: S404 - the graded `runtime.spawn` result type, never spawned here
from typing import Final

import anyio
from expression import Error, Nothing, Ok, Result, Some
from expression.collections import Block
from frozendict import frozendict
import msgspec
import structlog

from admin.core import completed, Detail, Envelope, Row, Status
from admin.runtime import Admit, BoundaryFault, drain, DrainReceipt, LanePolicy, RetryClass, RuntimeRail
from admin.runtime.rails import spawn
from admin.settings import CloudConfig, MaghzSettings, Remote


# --- [TYPES] ---------------------------------------------------------------------------


class CloudOp(StrEnum):
    """The closed verb vocabulary `run` discriminates on; one `_BUILD` row per member.

    Shaped to absorb a future PRUNE case (a remote dump-retention sweep) as one new member plus one
    `_BUILD` row, every consumer untouched — never a parallel verb surface.
    """

    SYNC = "sync"  # pg_dump + content bisync to both remotes
    RESTORE = "restore"  # pg_restore from a remote dump + content bisync back


# The `_detail` fold accumulator: the running summed stats, the materialized remotes, and the first sync
# dump path (PEP 695 lazy, so the later `_RcloneStats` model forward-references cleanly).
type _Tally = tuple[_RcloneStats, tuple[Remote, ...], str | msgspec.UnsetType]


# --- [CONSTANTS] -----------------------------------------------------------------------

# rclone owns its own transient (exit-5) backoff: three high-level retries spaced 60 s apart, where a
# temporary-error retry belongs — never a Python-side re-spawn of the whole bisync. `--use-json-log`
# emits the summary `stats` line `_summed` folds; `--stats 1m` exceeds any op so the single end-of-run
# summary fires while the periodic ticks stay suppressed (`--stats 0` would suppress the summary too).
_RCLONE_RETRY: Final[tuple[str, ...]] = ("--retries", "3", "--retries-sleep", "60s")
_RCLONE_LOG: Final[tuple[str, ...]] = ("--use-json-log", "--stats", "1m", "--log-level", "INFO")
# Success exits: `0` clean, `9` clean with no files transferred (`--error-on-no-transfer` semantics).
_OK_EXITS: Final[frozenset[int]] = frozenset({0, 9})


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

    `transferred` decodes from the rclone wire key `transfers` (`transferred` is never a key rclone
    emits, so a field named `transferred` would decode to its `0` default on every line);
    `msgspec.field(name="transfers")` binds the wire key while the receipt fold keeps the domain name.
    `forbid_unknown_fields` stays default so the unmodelled `bytes`/`speed`/`totalTransfers` keys are ignored.
    """

    transferred: int = msgspec.field(default=0, name="transfers")
    errors: int = 0
    checks: int = 0
    elapsedTime: float = 0.0  # noqa: N815 - rclone JSON field name, decoded verbatim

    def merge(self, other: _RcloneStats) -> _RcloneStats:
        """Fold another stats line into this one: sum the counters, take the monotone elapsed maximum.

        The one stats-accumulation kernel `_summed` (per-line stderr fold) and `_detail` (per-remote
        result fold) both reduce through, so the counter/elapsed correspondence lives in exactly one
        place rather than re-spelled per fold site.

        Returns:
            The summed `_RcloneStats` carrying the combined transfer/error/check counts and the run-max elapsed.
        """
        return _RcloneStats(
            transferred=self.transferred + other.transferred,
            errors=self.errors + other.errors,
            checks=self.checks + other.checks,
            elapsedTime=max(self.elapsedTime, other.elapsedTime),
        )


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


# --- [SERVICES] ------------------------------------------------------------------------

# One decoder for the rclone `--use-json-log` line shape, resolved once at import rather than per stderr
# line; `_summed` scans every line through it inside a `try/except msgspec.DecodeError`.
_LOG_DECODER: Final = msgspec.json.Decoder(type=_RcloneLogLine)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _env_for(remote: Remote, cfg: CloudConfig) -> Mapping[str, str]:
    """Assemble the immutable `RCLONE_CONFIG_<REMOTE>_*` env block for one remote, total over `Remote`.

    The token is the op-injected `RemoteCredentials.token` (the `MAGHZ_CLOUD__REMOTES__<REMOTE>__TOKEN`
    env owner) — never the macOS login keychain, so a backup cannot raise a Touch-ID/password prompt;
    an absent token simply yields an empty rclone token the auth then rejects with a typed exit. Drive
    carries the service-account strategy (`SCOPE`, `SERVICE_ACCOUNT_CREDENTIALS` as the raw service-account
    JSON blob rclone parses verbatim — never a base64 wrapper, which rclone cannot decode); OneDrive
    carries the personal-drive selector (`DRIVE_ID`). The two arms add disjoint keys on top of the shared
    `common` block; `match remote` is total over the closed vocabulary.

    Returns:
        A frozen `frozendict[str, str]` of the remote's rclone env config, ready as `env=` for `spawn`.
    """
    conf = cfg.remotes[remote]
    prefix = f"RCLONE_CONFIG_{remote.value.upper()}"
    common = {
        f"{prefix}_TYPE": remote.value,
        f"{prefix}_CLIENT_ID": conf.client_id,
        f"{prefix}_CLIENT_SECRET": conf.client_secret,
        f"{prefix}_TOKEN": conf.token,
    }
    match remote:
        case Remote.DRIVE:
            return frozendict({**common, f"{prefix}_SCOPE": "drive", f"{prefix}_SERVICE_ACCOUNT_CREDENTIALS": conf.service_account_credentials})
        case Remote.ONEDRIVE:
            return frozendict({**common, f"{prefix}_DRIVE_ID": conf.drive_id})


def _summed(stderr: bytes) -> _RcloneStats:
    """Fold the rclone `--use-json-log` stderr into one summed `_RcloneStats`, skipping non-JSON lines.

    Each line decodes through the shared `_LOG_DECODER`; a `msgspec.DecodeError` (banner/progress noise)
    is skipped, and only lines carrying a nested `stats` object contribute through `_RcloneStats.merge`,
    so the counter-sum/elapsed-max correspondence is the one stats kernel, not re-spelled here.

    Returns:
        The folded `_RcloneStats`; a zero-sentinel `_RcloneStats()` when no stats line decodes.
    """

    def _decode(line: bytes) -> _RcloneStats | None:
        try:
            return _LOG_DECODER.decode(line).stats
        except msgspec.DecodeError:
            return None

    parsed = Block.of_seq(stats for line in stderr.splitlines() if line.strip() and (stats := _decode(line)) is not None)
    return parsed.fold(lambda acc, s: acc.merge(s), _RcloneStats())


def _graded(run: CompletedProcess[bytes], subject: str, remote: Remote | None) -> RuntimeRail[_RcloneStats]:
    """Project one completed subprocess exit to the typed rail: success folds stats, any other exit faults.

    The pure rclone/pg exit grade over the `CompletedProcess` `spawn` returns. `0`/`9` are success and
    fold the `--use-json-log` summary through `_summed`; a pg exit carries no JSON-log line, so the per-line
    `msgspec.DecodeError` skip lands the same zero sentinel without a `rclone`/`pg` knob selecting two
    bodies. Every other non-zero exit mints `Error(BoundaryFault(boundary=(subject, detail)))` directly,
    the detail carrying the decoded stderr and the exit code, the subject the remote value (when bound) or
    the tool name — so `DrainReceipt.faults` and the `run` projection name which remote never materialized
    from one closed fault family, no per-rail carrier. rclone's transient exit `5` never reaches here: the
    `--retries`/`--retries-sleep` argv retries it in rclone; a surviving `5`, like `7`, is a real fault.

    Returns:
        `Ok(_RcloneStats)` on a `0`/`9` exit, or `Error(BoundaryFault)` for any other exit.
    """
    if run.returncode in _OK_EXITS:
        return Ok(_summed(run.stderr))
    decoded = run.stderr.decode(errors="replace").strip()
    body = f"{decoded} (exit {run.returncode})" if decoded else f"{subject} exited {run.returncode}"
    name = remote.value if remote is not None else subject
    return Error(BoundaryFault(boundary=(name, body)))


async def _spawn(*argv: str, remote: Remote | None = None, env: Mapping[str, str] | None = None) -> RuntimeRail[_RcloneStats]:
    """Run one rclone/pg subprocess through the substrate `spawn` boundary, grading the exit to the rail.

    The one subprocess leg the whole rail composes: `spawn(retry_class=RetryClass.PROC)` owns the
    spawn-flap `OSError` retry and the exhausted-retry lift, the `argv[0]` tool name IS the fault subject
    (`rclone`/`pg_dump`/`pg_restore`), and the returned `CompletedProcess` grades through `_graded` — one
    `guard`-stacked spawn plus the pure exit projection, never a hand-rolled retry loop nor a `_rclone`/`_pg`
    sibling pair. The rclone leg alone carries the `--retries`/`--retries-sleep` transient-exit-5 backoff
    and the `--use-json-log` summary tail (derived off the `rclone` tool, not a caller flag) and rides its
    per-remote `RCLONE_CONFIG_*` env; a pg leg inherits the op-injected `PG*` environment and threads its
    DSN through `argv` (the `cfg.database.dsn` sole owner takes no settings handle here).

    Args:
        argv: The full command; `argv[0]` is the tool name minted as the fault subject.
        remote: The bound remote whose `value` names a per-remote fault, or `None` for a pg/tool fault.
        env: The rclone `RCLONE_CONFIG_*` env block, or `None` to inherit (the pg `PG*` path).

    Returns:
        `Ok(_RcloneStats)` on a `0`/`9` exit (the folded rclone summary or the pg zero sentinel), or
        `Error(BoundaryFault)` for a fatal exit or an exhausted spawn flap lifted at the `spawn` boundary.
    """
    subject = argv[0]
    full = (*argv, *_RCLONE_RETRY, *_RCLONE_LOG) if subject == "rclone" else argv
    return (await spawn(full, subject=subject, retry_class=RetryClass.PROC, env=dict(env) if env is not None else None)).bind(
        lambda run: _graded(run, subject, remote)
    )


def _bisync(remote: Remote, cfg: CloudConfig, *, resync: bool) -> tuple[str, ...]:
    """Build the rclone bisync argv for one remote's content tree (the `_RCLONE_LOG`/`_RCLONE_RETRY` tail is appended by `_spawn`).

    `--resync` re-establishes the path1 baseline (restore, or `force_resync`); the conflict policy keeps
    the newer side and suffixes the loser; `--filters-file` scopes the tree; `--check-access` guards a
    half-mounted remote. The deadline/concurrency live on the runtime lane, never on this argv.

    Returns:
        The rclone bisync command tuple for `remote`, sans the shared log/retry tail.
    """
    return (
        "rclone",
        "bisync",
        str(cfg.content_root),
        f"{remote.value}:{cfg.remote_content_path}",
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
        str(cfg.filter_file),
        "--check-access",
        *(("--resync",) if resync else ()),
    )


def _work(remote: Remote, cfg: MaghzSettings, dump: str, *, resync: bool, upload: str | None) -> Callable[[], Awaitable[RuntimeRail[_RemoteResult]]]:
    """Build the per-remote drain child: bind the structlog context, copy the dump, then bisync the tree.

    `upload` set (sync) runs `rclone copy <dump> <remote>:<dump_path>` before the bisync and records its
    path on the `_RemoteResult`; `upload` `None` (restore) bisyncs only. Both legs ride `_spawn`, so the
    first `Error(BoundaryFault)` short-circuits the `bind` chain and the child returns it directly — no
    lift arm, because `_graded` already minted the one closed fault family. The lane drain carries the
    returned rail into `DrainReceipt.values`/`.faults`.

    Returns:
        An async `Work` callable returning `Ok(_RemoteResult)` once the remote's transfers complete, or
        `Error(BoundaryFault)` from the first per-remote rclone fault.
    """
    cloud = cfg.cloud
    env = _env_for(remote, cloud)
    bisync = _bisync(remote, cloud, resync=resync)
    dump_path: str | msgspec.UnsetType = upload if upload is not None else msgspec.UNSET

    async def _run() -> RuntimeRail[_RemoteResult]:
        with structlog.contextvars.bound_contextvars(remote=remote.value):
            if upload is not None:
                match await _spawn("rclone", "copy", dump, upload, env=env, remote=remote):
                    case Result(tag="error", error=copy_fault):
                        return Error(copy_fault)
            return (await _spawn(*bisync, env=env, remote=remote)).map(
                lambda stats: _RemoteResult(remote=remote, stats=stats, dump_path=dump_path)
            )

    return _run


async def _fan_out(cfg: MaghzSettings, dump: str, *, resync: bool, upload: bool) -> DrainReceipt[object]:
    """Drain the per-remote work over both remotes through the runtime lane, never a raw task group.

    One `Admit.guarded(RetryClass.PROC, work)` per `Remote` rides `LanePolicy.drain`; the lane owns the
    concurrency bound and the spawn-flap retry. `upload` chooses the per-remote dump target (sync uploads
    to `<remote>:<remote_dump_path>`; restore passes `None`).

    Returns:
        The frozen `DrainReceipt` whose `values` are the materialized `_RemoteResult` block and whose
        `faults` carry the per-remote boundary failures.
    """
    remote_dump = cfg.cloud.remote_dump_path
    policy = LanePolicy(capacity=len(Remote))
    units = Block.of_seq(
        Admit.guarded(RetryClass.PROC, _work(remote, cfg, dump, resync=resync, upload=f"{remote.value}:{remote_dump}" if upload else None))
        for remote in Remote
    )
    return await drain(policy, units)


def _results(receipt: DrainReceipt[object]) -> Block[_RemoteResult]:
    """Narrow the concept-agnostic `DrainReceipt.values` to the `_RemoteResult` block, the one boundary cast.

    The lane is `object`-typed by substrate design, so the cloud boundary narrows its values exactly
    once here; `_detail` and the dump-path pick both read this block rather than each re-running an
    `isinstance(value, _RemoteResult)` filter over `receipt.values`.

    Returns:
        The materialized `_RemoteResult`s the drain recovered, in completion order.
    """
    return receipt.values.choose(lambda value: Some(value) if isinstance(value, _RemoteResult) else Nothing)


def _detail(receipt: DrainReceipt[object], op: CloudOp, *, restored_from: str | msgspec.UnsetType) -> CloudSyncDetail:
    """Fold a `DrainReceipt` into the `CloudSyncDetail` receipt, summing the materialized remote stats.

    The narrowed `_results` block is folded once: the per-remote stats accumulate through
    `_RcloneStats.merge` and the materialized `remotes` plus the first sync dump path collect in the same
    pass, so `remotes` is exactly the set that reported and the failed remotes are read off the
    `tuple(Remote)` complement by `_ok`.

    Returns:
        The typed `CloudSyncDetail` with the summed `transferred`/`errors`/`checks`/`elapsed_s` tally,
        the materialized `remotes`, and the first materialized remote dump path (sync only).
    """
    def step(acc: _Tally, result: _RemoteResult) -> _Tally:
        stats, remotes, dump = acc
        first = dump if dump is not msgspec.UNSET else result.dump_path
        return stats.merge(result.stats), (*remotes, result.remote), first

    stats, remotes, dump_path = _results(receipt).fold(step, (_RcloneStats(), (), msgspec.UNSET))
    return CloudSyncDetail(
        op=op,
        remotes=remotes,
        transferred=stats.transferred,
        errors=stats.errors,
        checks=stats.checks,
        elapsed_s=stats.elapsedTime,
        dump_path=dump_path,
        restored_from=restored_from,
    )


@contextlib.asynccontextmanager
async def _staging() -> AsyncIterator[anyio.Path]:
    """Stage a dump directory through `anyio.TemporaryDirectory`, tearing it down under a shielded scope.

    The native async temp-dir owner creates and offloads the recursive cleanup; entering yields the
    `str` root this wraps in an `anyio.Path` for the dump-file path construction. `__aexit__` runs inside
    `anyio.CancelScope(shield=True)` so a `move_on_after` deadline that fires mid-operation still completes
    the cleanup rather than leaking the staged archive — the shield protects the cleanup offload checkpoint
    from the in-flight cancellation.

    Yields:
        The staging directory as an `anyio.Path` for the dump-file path construction.
    """
    # Manual enter/exit (not `async with`) so the cleanup `__aexit__` runs inside the shield: a context
    # manager cannot inject a `CancelScope(shield=True)` into its own teardown, so the dunder calls are
    # the load-bearing form here, not the PLC2801 default.
    tmp = anyio.TemporaryDirectory(prefix="maghz-cloud-")
    root = await tmp.__aenter__()  # noqa: PLC2801
    try:
        yield anyio.Path(root)
    finally:
        with anyio.CancelScope(shield=True):
            await tmp.__aexit__(None, None, None)


async def _sync_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """`CloudOp.SYNC` builder: dump the ledger once, then fan the dump + content bisync to both remotes.

    `pg_dump` writes a custom-format zstd-3 archive into a shielded staging dir; its failure
    short-circuits before any remote is touched. The drain then uploads the dump and bisyncs the tree per
    remote (`--resync` only when `force_resync`). The folded detail carries the remote dump path of the
    first materialized remote; `_ok` names any remote that never reported.

    Returns:
        `Ok(completed(...))` carrying the `CloudSyncDetail`, or `Error(BoundaryFault)` when `pg_dump` fails.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        dump = str(staging / f"{stamp}_maghz.dump")
        match await _spawn("pg_dump", str(cfg.database.dsn), "-F", "c", "-Z", "zstd:3", "-f", dump, "-O", "--no-privileges"):
            case Result(tag="error", error=dump_fault):
                return Error(dump_fault)
        receipt = await _fan_out(cfg, dump, resync=cfg.cloud.force_resync, upload=True)
        return _ok(receipt, CloudOp.SYNC, restored_from=msgspec.UNSET)


async def _restore_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """`CloudOp.RESTORE` builder: pull the latest dump from the primary remote, replay it, then bisync back.

    The dump downloads from the Drive remote into a shielded staging dir; `pg_restore -c` drops and
    recreates before reload, and its failure short-circuits. The drain then bisyncs the tree back to both
    remotes with `--resync` always on (restore re-establishes the path baseline). The detail records the
    `<remote>:<path>` the dump came from.

    Returns:
        `Ok(completed(...))` carrying the `CloudSyncDetail`, or `Error(BoundaryFault)` when the dump
        download or `pg_restore` fails.
    """
    primary = Remote.DRIVE
    source = f"{primary.value}:{cfg.cloud.remote_dump_path}"
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        match await _spawn("rclone", "copy", source, str(staging), env=_env_for(primary, cfg.cloud), remote=primary):
            case Result(tag="error", error=download_fault):
                return Error(download_fault)
        dump = await _first_dump(staging)
        match await _spawn("pg_restore", "-d", str(cfg.database.dsn), "-c", "-O", "--no-privileges", str(dump)):
            case Result(tag="error", error=restore_fault):
                return Error(restore_fault)
        receipt = await _fan_out(cfg, str(dump), resync=True, upload=False)
        return _ok(receipt, CloudOp.RESTORE, restored_from=f"{source}/{dump.name}")


async def _first_dump(staging: anyio.Path) -> anyio.Path:
    """Return the first staged `*.dump` in the restore staging dir, or the dir itself when none landed.

    The download lands one archive; restore replays the first `*.dump`. An empty dir yields the dir path
    so the subsequent `pg_restore` fails with a clear missing-file fault rather than this function raising.

    Returns:
        The first `*.dump` path under `staging`, or `staging` itself when the download produced none.
    """
    async for entry in staging.iterdir():
        if entry.suffix == ".dump":
            return entry
    return staging


def _ok(receipt: DrainReceipt[object], op: CloudOp, *, restored_from: str | msgspec.UnsetType) -> RuntimeRail[Envelope]:
    """Project a drained receipt to the `Ok` envelope leg, `FAILED` with per-remote fault rows on a partial drain.

    The folded `_detail.remotes` is the set that reported; the `tuple(Remote)` complement names every
    remote that never completed. A complete drain is `Status.OK`; a partial drain is `Status.FAILED`
    carrying one `Row` per failed remote — the row text the remote's own `BoundaryFault.headline()` off
    the lossless `DrainReceipt.faults` (so the cause survives, not a generic string), falling back to a
    plain "remote did not complete" only for a remote absent from both the values and the faults. A
    single-remote failure surfaces without aborting the other.

    Returns:
        `Ok(completed(OK | FAILED, detail, rows=<failed-remote rows>))`.
    """
    detail = _detail(receipt, op, restored_from=restored_from)
    headlines = {fault.facts().get("subject"): fault.headline() for fault in receipt.faults}
    missing = tuple(remote for remote in Remote if remote not in detail.remotes)
    rows = tuple(Row(key=remote.value, text=headlines.get(remote.value, "remote did not complete")) for remote in missing)
    return Ok(completed(Status.FAILED if missing else Status.OK, detail, rows=rows))


# --- [TABLES] --------------------------------------------------------------------------

# verb -> its full dump/restore builder on the interior `RuntimeRail[Envelope]`. The key set equals
# `CloudOp` exactly, so `run`'s subscription is total — `run(op)` is `await _BUILD[op](cfg)`, no
# match/`assert_never` around an exhaustive table. Each builder owns its own staging scope, drain, and
# typed rail leg, returning the rail `run` bounds with the op deadline and surfaces to the CLI `lower` seam.
_BUILD: Final[frozendict[CloudOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    CloudOp.SYNC: _sync_detail,
    CloudOp.RESTORE: _restore_detail,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: CloudOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one cloud-sync verb by `op` on the domain rail, dispatching through the total `_BUILD` table.

    `_BUILD[op]` selects the builder over the exhaustive table (no `match`/`assert_never` ceremony around
    a total subscription). The whole operation runs inside `anyio.move_on_after(cfg.cloud.op_timeout_s)`,
    the one permitted CLI-boundary deadline: a tripped deadline is CONTAINED — the scope cancels the
    in-flight builder and the rail surfaces `Error(BoundaryFault(deadline=(op, budget)))` carrying the
    budget the substrate egress preserves as a native scalar, never a raw `TimeoutError` escaping without
    a typed receipt. The returned `RuntimeRail[Envelope]` is the domain-internal contract; the CLI handler
    lowers it to the stdout `Envelope` through the one `runtime.lower` seam, so an `Ok` carries the
    `completed` envelope (`OK`, or `FAILED` with one row per remote that never reported) and a surviving
    `Error(BoundaryFault)` projects to a `fault` envelope once, at the edge — this rail self-lowers no fault.

    Args:
        op: The cloud-sync verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings owning the DSN, the per-remote credentials, and the op deadline.

    Returns:
        The rail the selected builder produced under the op deadline — `Ok(Envelope)` carrying the typed
        `CloudSyncDetail` receipt, or `Error(BoundaryFault)` from a subprocess boundary or a contained
        deadline trip.
    """
    structlog.contextvars.bind_contextvars(rail="cloud", op=op.value)
    budget = cfg.cloud.op_timeout_s
    with anyio.move_on_after(budget) as scope:
        outcome = await _BUILD[op](cfg)
    if scope.cancelled_caught:
        return Error(BoundaryFault(deadline=(f"cloud.{op.value}", budget)))
    return outcome


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["CloudOp", "CloudSyncDetail", "run"]
