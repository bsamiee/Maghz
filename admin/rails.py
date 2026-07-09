from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable, Generator, Mapping
import contextlib
from datetime import datetime, UTC
from enum import StrEnum
from functools import partial
from operator import itemgetter
from pathlib import Path
from subprocess import CompletedProcess  # noqa: S404
from typing import Final, override

import anyio
from expression import Error, Nothing, Ok, Result, Some
from expression.collections import Block
from frozendict import frozendict
import httpx
import msgspec
from sqlglot import Dialects, ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError
from sqlglot.lineage import lineage
import structlog

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.db import QueryResult
from admin.profile import census_diff
from admin.runtime import (
    Admit,
    boundary,
    BoundaryFault,
    Disposition,
    drain,
    DrainReceipt,
    guarded,
    LaneKey,
    LanePolicy,
    RetryClass,
    RuntimeRail,
    spawn,
    traversed,
)
from admin.settings import CloudConfig, MaghzSettings, N8nConfig, Remote, Stage


# --- [TYPES] ---------------------------------------------------------------------------


type _Tally = tuple[_RcloneStats, tuple[Remote, ...], str | msgspec.UnsetType]

_RCLONE_RETRY: Final[tuple[str, ...]] = ("--retries", "3", "--retries-sleep", "60s")
_RCLONE_LOG: Final[tuple[str, ...]] = ("--use-json-log", "--stats", "1m", "--log-level", "INFO")
_OK_EXITS: Final[frozenset[int]] = frozenset({0, 9})


class CloudOp(StrEnum):
    SYNC = "sync"  # pg_dump + content bisync to both remotes
    RESTORE = "restore"


class CloudSyncDetail(Detail, frozen=True, tag="cloud"):
    op: CloudOp
    remotes: tuple[Remote, ...]
    transferred: int = 0
    errors: int = 0
    checks: int = 0
    elapsed_s: float = 0.0
    dump_path: str | msgspec.UnsetType = msgspec.UNSET
    restored_from: str | msgspec.UnsetType = msgspec.UNSET


class _RcloneStats(msgspec.Struct, frozen=True, gc=False):
    transferred: int = msgspec.field(default=0, name="transfers")
    errors: int = 0
    checks: int = 0
    elapsedTime: float = 0.0  # noqa: N815 - rclone JSON field name, decoded verbatim

    def merge(self, other: _RcloneStats) -> _RcloneStats:

        return _RcloneStats(
            transferred=self.transferred + other.transferred,
            errors=self.errors + other.errors,
            checks=self.checks + other.checks,
            elapsedTime=max(self.elapsedTime, other.elapsedTime),
        )


class _RcloneLogLine(msgspec.Struct, frozen=True, gc=False):
    level: str = ""
    msg: str = ""
    stats: _RcloneStats | None = None


_LOG_DECODER: Final = msgspec.json.Decoder(type=_RcloneLogLine)


class _RemoteResult(msgspec.Struct, frozen=True, gc=False):
    remote: Remote
    stats: _RcloneStats
    dump_path: str | msgspec.UnsetType = msgspec.UNSET


def _env_for(remote: Remote, cfg: CloudConfig) -> Mapping[str, str]:

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

    def _decode(line: bytes) -> _RcloneStats | None:
        try:
            return _LOG_DECODER.decode(line).stats
        except msgspec.DecodeError:
            return None

    parsed = Block.of_seq(stats for line in stderr.splitlines() if line.strip() and (stats := _decode(line)) is not None)
    return parsed.fold(lambda acc, s: acc.merge(s), _RcloneStats())


def _cloud_graded(run: CompletedProcess[bytes], subject: str, remote: Remote | None) -> RuntimeRail[_RcloneStats]:

    if run.returncode in _OK_EXITS:
        return Ok(_summed(run.stderr))
    decoded = run.stderr.decode(errors="replace").strip()
    body = f"{decoded} (exit {run.returncode})" if decoded else f"{subject} exited {run.returncode}"
    name = remote.value if remote is not None else subject
    return Error(BoundaryFault(boundary=(name, body)))


async def _spawn(*argv: str, remote: Remote | None = None, env: Mapping[str, str] | None = None) -> RuntimeRail[_RcloneStats]:

    subject = argv[0]
    full = (*argv, *_RCLONE_RETRY, *_RCLONE_LOG) if subject == "rclone" else argv
    return (await spawn(full, subject=subject, retry_class=RetryClass.PROC, env=dict(env) if env is not None else None)).bind(
        lambda run: _cloud_graded(run, subject, remote)
    )


def _bisync(remote: Remote, cfg: CloudConfig, *, resync: bool) -> tuple[str, ...]:

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

    cloud = cfg.cloud
    env = _env_for(remote, cloud)
    bisync = _bisync(remote, cloud, resync=resync)
    dump_path: str | msgspec.UnsetType = upload if upload is not None else msgspec.UNSET

    async def _run() -> RuntimeRail[_RemoteResult]:
        with structlog.contextvars.bound_contextvars(remote=remote.value):
            copied: RuntimeRail[_RcloneStats] = (
                Ok(_RcloneStats()) if upload is None else await _spawn("rclone", "copy", dump, upload, env=env, remote=remote)
            )
            match copied:
                case Result(tag="error", error=copy_fault):
                    return Error(copy_fault)
                case Result():
                    pass
            return (await _spawn(*bisync, env=env, remote=remote)).map(lambda stats: _RemoteResult(remote=remote, stats=stats, dump_path=dump_path))

    return _run


async def _fan_out(cfg: MaghzSettings, dump: str, *, resync: bool, upload: bool) -> DrainReceipt[object]:

    remote_dump = cfg.cloud.remote_dump_path
    policy = LanePolicy(capacity=len(Remote), key=LaneKey("cloud.remote"))
    units = Block.of_seq(
        Admit.guarded(RetryClass.PROC, _work(remote, cfg, dump, resync=resync, upload=f"{remote.value}:{remote_dump}" if upload else None))
        for remote in Remote
    )
    return await drain(policy, units)


def _results(receipt: DrainReceipt[object]) -> Block[_RemoteResult]:

    return receipt.values.choose(lambda value: Some(value) if isinstance(value, _RemoteResult) else Nothing)


def _detail(receipt: DrainReceipt[object], op: CloudOp, *, restored_from: str | msgspec.UnsetType) -> CloudSyncDetail:

    def step(acc: _Tally, result: _RemoteResult) -> _Tally:
        stats, remotes, dump = acc
        first = dump if dump is not msgspec.UNSET else result.dump_path
        return stats.merge(result.stats), (*remotes, result.remote), first

    seed: _Tally = (_RcloneStats(), (), msgspec.UNSET)
    stats, remotes, dump_path = _results(receipt).fold(step, seed)
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

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        dump = str(staging / f"{stamp}_maghz.dump")
        match await _spawn("pg_dump", str(cfg.database.dsn), "-F", "c", "-Z", "zstd:3", "-f", dump, "-O", "--no-privileges"):
            case Result(tag="error", error=dump_fault):
                return Error(dump_fault)
            case Result():
                pass
        receipt = await _fan_out(cfg, dump, resync=cfg.cloud.force_resync, upload=True)
        return _ok(receipt, CloudOp.SYNC, restored_from=msgspec.UNSET)


async def _restore_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    primary = Remote.DRIVE
    source = f"{primary.value}:{cfg.cloud.remote_dump_path}"
    async with contextlib.AsyncExitStack() as stack:
        staging = await stack.enter_async_context(_staging())
        match await _spawn("rclone", "copy", source, str(staging), env=_env_for(primary, cfg.cloud), remote=primary):
            case Result(tag="error", error=download_fault):
                return Error(download_fault)
            case Result():
                pass
        dump = await _first_dump(staging)
        match await _spawn("pg_restore", "-d", str(cfg.database.dsn), "-c", "-O", "--no-privileges", str(dump)):
            case Result(tag="error", error=restore_fault):
                return Error(restore_fault)
            case Result():
                pass
        receipt = await _fan_out(cfg, str(dump), resync=True, upload=False)
        return _ok(receipt, CloudOp.RESTORE, restored_from=f"{source}/{dump.name}")


async def _first_dump(staging: anyio.Path) -> anyio.Path:

    async for entry in staging.iterdir():
        if entry.suffix == ".dump":
            return entry
    return staging


def _ok(receipt: DrainReceipt[object], op: CloudOp, *, restored_from: str | msgspec.UnsetType) -> RuntimeRail[Envelope]:

    detail = _detail(receipt, op, restored_from=restored_from)
    headlines = {fault.facts().get("subject"): fault.headline() for fault in receipt.faults}
    missing = tuple(remote for remote in Remote if remote not in detail.remotes)
    rows = tuple(Row(key=remote.value, text=headlines.get(remote.value, "remote did not complete")) for remote in missing)
    return Ok(completed(Status.FAILED if missing else Status.OK, detail, rows=rows))


_CLOUD_BUILD: Final[frozendict[CloudOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    CloudOp.SYNC: _sync_detail,
    CloudOp.RESTORE: _restore_detail,
})


async def cloud(op: CloudOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:

    structlog.contextvars.bind_contextvars(rail="cloud", op=op.value)
    budget = cfg.cloud.op_timeout_s
    with anyio.move_on_after(budget) as scope:
        outcome = await _CLOUD_BUILD[op](cfg)
    if scope.cancelled_caught:
        return Error(BoundaryFault(deadline=(f"cloud.{op.value}", budget)))
    return outcome


type LineageEdge = tuple[str, str]


class Kind(StrEnum):
    COVERAGE = "coverage"
    GAPS = "gaps"
    STALE = "stale"
    NEXT = "next"
    OWNER = "owner"


_LEDGER_DIALECT = Dialects.POSTGRES
_PREDICATE_NODES: tuple[type[exp.Expression], ...] = (exp.Where, exp.Having, exp.Qualify, exp.Join)


class LedgerDetail(Detail, frozen=True, tag="ledger"):
    kind: Kind
    count: int
    columns: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    predicates: int = 0
    lineage: tuple[LineageEdge, ...] = ()


class Projection(msgspec.Struct, frozen=True):
    tree: exp.Expression
    sql: str
    columns: tuple[str, ...]
    tables: tuple[str, ...]
    predicates: int
    lineage: tuple[LineageEdge, ...]

    @staticmethod
    def of(text: str) -> Projection:

        tree = parse_one(text, dialect=_LEDGER_DIALECT, into=exp.Select, error_level=ErrorLevel.RAISE)
        roots = lineage(None, tree, dialect=_LEDGER_DIALECT)
        return Projection(
            tree=tree,
            sql=tree.sql(dialect=_LEDGER_DIALECT),
            columns=tuple(select.alias_or_name for select in tree.selects),
            tables=tuple(sorted({table.name for table in tree.find_all(exp.Table)})),
            predicates=sum(1 for _ in tree.find_all(*_PREDICATE_NODES)),
            lineage=tuple((str(leaf.name), str(out)) for out, root in roots.items() for leaf in root.walk() if not leaf.downstream),
        )

    def detail(self, kind: Kind, count: int) -> LedgerDetail:

        return LedgerDetail(kind=kind, count=count, columns=self.columns, tables=self.tables, predicates=self.predicates, lineage=self.lineage)


_TEXT: frozendict[Kind, str] = frozendict({
    Kind.COVERAGE: (
        "select d.slug as key, "
        "d.name || ': ' || count(c.id) || ' concepts' as text "
        "from domain d left join concept c on c.domain_id = d.id "
        "group by d.id, d.slug, d.name order by count(c.id) desc, d.name"
    ),
    Kind.GAPS: (
        "select c.canonical_name as key, "
        "c.title || ' (' || d.slug || ')' as text "
        "from concept c join domain d on d.id = c.domain_id "
        "left join evidence e on e.concept_id = c.id "
        "where e.id is null order by d.slug, c.canonical_name"
    ),
    Kind.STALE: (
        "select j.id::text as key, "
        "j.status || ' x' || j.attempt || ' @ ' || coalesce(w.name::text, '<unassigned>') as text "
        "from job j left join worker w on w.id = j.worker_id "
        "where j.status in ('stale', 'failed', 'awaiting_review') "
        "order by j.heartbeat_at"
    ),
    Kind.NEXT: (
        "select d.slug as key, "
        "d.name || ': ' || count(c.id) || ' concepts, ' || "
        "count(c.id) filter (where e.id is null) || ' unevidenced' as text "
        "from domain d left join concept c on c.domain_id = d.id "
        "left join evidence e on e.concept_id = c.id "
        "group by d.id, d.slug, d.name "
        "order by count(c.id) asc, count(c.id) filter (where e.id is null) desc, d.name"
    ),
    Kind.OWNER: (
        "select coalesce(w.name::text, '<unassigned>') as key, "
        "w.kind || ': ' || count(j.id) || ' jobs (' || "
        "count(j.id) filter (where j.status <> 'done') || ' open)' as text "
        "from worker w left join job j on j.worker_id = w.id "
        "group by w.id, w.name, w.kind "
        "order by count(j.id) filter (where j.status <> 'done') desc, w.name"
    ),
})


_SQL: frozendict[Kind, Projection] = frozendict({kind: Projection.of(text) for kind, text in _TEXT.items()})


async def ledger(kind: Kind, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:

    structlog.contextvars.bind_contextvars(rail="ledger", kind=kind.value)
    projection = _SQL[kind]

    def _report(result: QueryResult) -> Envelope:
        rows = tuple(Row(key=str(key), text=str(text)) for key, text in result.rows)
        return completed(Status.OK if rows else Status.EMPTY, projection.detail(kind, len(rows)), rows=rows)

    return (await db.query(projection.sql, cfg)).map(_report)


class N8nOp(StrEnum):
    EXPORT = "export"
    IMPORT = "import"
    STATUS = "status"


_CONTAINER_WORKFLOWS: Final[str] = "/home/node/workflows"
_N8N_LIST_LIMIT: Final[int] = 250


class N8nDetail(Detail, frozen=True, tag="n8n"):
    op: N8nOp
    workflow_count: int = 0
    container: str = ""
    healthy: bool | msgspec.UnsetType = msgspec.UNSET


class _Cli(msgspec.Struct, frozen=True, gc=False):
    op: N8nOp
    subcommand: tuple[str, ...]


class _Workflows(msgspec.Struct, frozen=True, gc=False):
    data: tuple[msgspec.Raw, ...] = ()


class _Liveness(msgspec.Struct, frozen=True, gc=False):
    healthy: bool
    count: int


class _N8nAuth(httpx.Auth):
    __slots__ = ("_key",)

    def __init__(self, key: str) -> None:
        self._key = key

    @override
    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:

        request.headers["X-N8N-API-KEY"] = self._key
        yield request


_WORKFLOWS_DECODER: Final[msgspec.json.Decoder[_Workflows]] = msgspec.json.Decoder(type=_Workflows)
_LIMITS: Final[httpx.Limits] = httpx.Limits(max_connections=1, max_keepalive_connections=1)


def _api_key(_cfg: MaghzSettings) -> Result[_N8nAuth, BoundaryFault]:

    return Error(BoundaryFault(config=("status", "n8n API key is not configured; n8n setup is pending")))


async def _census(cfg: MaghzSettings) -> int:

    return len([entry async for entry in anyio.Path(cfg.n8n.workflows_dir).glob("*.json")])


def _n8n_graded(run: CompletedProcess[bytes], cli: _Cli, count: int, container: str) -> RuntimeRail[Envelope]:

    if run.returncode == 0:
        return Ok(completed(Status.OK, N8nDetail(op=cli.op, workflow_count=count, container=container)))
    detail = run.stderr.decode(errors="replace").strip() or f"{cli.op.value} exited {run.returncode}"
    return Error(BoundaryFault(boundary=(f"n8n.{cli.op.value}", detail)))


async def _workflow(cli: _Cli, cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    argv = ("docker", "exec", "-u", "node", cfg.n8n.container_name, "n8n", *cli.subcommand)
    match await spawn(argv, subject=f"n8n.{cli.op.value}", retry_class=RetryClass.PROC, env=dict(cfg.docker_env)):
        case Result(tag="error", error=spawn_fault):
            return Error(spawn_fault)
        case Result(ok=run):
            count = await _census(cfg) if run.returncode == 0 else 0
            return _n8n_graded(run, cli, count, cfg.n8n.container_name)


async def _probe(n8n: N8nConfig, auth: _N8nAuth) -> _Liveness:

    timeout = httpx.Timeout(connect=n8n.connect_timeout, read=n8n.connect_timeout, write=n8n.connect_timeout, pool=n8n.connect_timeout)
    async with httpx.AsyncClient(base_url=n8n.api_url, auth=auth, timeout=timeout, limits=_LIMITS, headers={"accept": "application/json"}) as client:
        health = await client.get("/healthz")
        listing = (await client.get("/api/v1/workflows", params={"limit": _N8N_LIST_LIMIT})).raise_for_status()
        return _Liveness(healthy=health.status_code == httpx.codes.OK, count=len(_WORKFLOWS_DECODER.decode(listing.content).data))


async def _status(cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    match _api_key(cfg):
        case Result(tag="error", error=config_fault):
            return Error(config_fault)
        case Result(ok=auth):
            probed = await guarded(RetryClass.HTTP, lambda: _probe(cfg.n8n, auth), subject="n8n.status")
            return probed.map(
                lambda live: completed(
                    Status.OK, N8nDetail(op=N8nOp.STATUS, workflow_count=live.count, container=cfg.n8n.container_name, healthy=live.healthy)
                )
            )


_CLI: Final[frozendict[N8nOp, _Cli]] = frozendict({
    N8nOp.EXPORT: _Cli(op=N8nOp.EXPORT, subcommand=("export:workflow", "--all", f"--output={_CONTAINER_WORKFLOWS}", "--separate")),
    N8nOp.IMPORT: _Cli(op=N8nOp.IMPORT, subcommand=("import:workflow", "--separate", f"--input={_CONTAINER_WORKFLOWS}")),
})
_N8N_BUILD: Final[frozendict[N8nOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    **{op: partial(_workflow, cli) for op, cli in _CLI.items()},
    N8nOp.STATUS: _status,
})


async def n8n(op: N8nOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:

    structlog.contextvars.bind_contextvars(rail="n8n", op=op.value)
    return await _N8N_BUILD[op](cfg)


class SchemaOp(StrEnum):
    APPLY = "apply"
    DOCTOR = "doctor"


type StepArgv = Callable[[MaghzSettings, str], tuple[str, ...]]


_CONTAINER = "maghz-db"
_TSEARCH_DATA = "/usr/share/postgresql/18/tsearch_data"
_staged = f"{_CONTAINER}:{_TSEARCH_DATA}/maghz_"
_SCHEMA_DIALECT = Dialects.POSTGRES
_TIMEOUT_EXIT = 124


class SchemaDetail(Detail, frozen=True, tag="schema"):
    op: SchemaOp
    exits: tuple[int, ...] = ()
    objects: frozendict[str, int] = frozendict()


class _Step(msgspec.Struct, frozen=True, gc=False):
    name: str
    argv: tuple[str, ...]
    deadline: float
    env: frozendict[str, str] = frozendict()  # overlay rows for daemon-facing steps (DOCKER_HOST on the cp legs)
    code: int = 0
    stderr: str = ""

    def with_exit(self, code: int, stderr: str) -> _Step:

        return msgspec.structs.replace(self, code=code, stderr=stderr)


class _Sql(msgspec.Struct, frozen=True):
    stem: str
    objects: frozendict[str, int]
    commands: int

    @staticmethod
    def of(path: Path) -> RuntimeRail[_Sql]:

        try:
            nodes = parse(path.read_text(encoding="utf-8"), dialect=_SCHEMA_DIALECT, error_level=ErrorLevel.RAISE)
            statements = tuple(node for node in nodes if node is not None)
            census = Counter(node.kind.lower() if node.kind else "object" for node in statements if isinstance(node, exp.Create))
            commands = sum(1 for node in statements if isinstance(node, exp.Command))
            return Ok(_Sql(stem=path.stem, objects=frozendict(census), commands=commands))
        except ParseError as exc:
            first = exc.errors[0] if exc.errors else {}
            finding = f"line {first.get('line', '?')}:{first.get('col', '?')} {first.get('description', str(exc))}"
            return Error(BoundaryFault(boundary=(path.stem, finding)))
        except OSError as exc:
            return Error(BoundaryFault(boundary=(path.stem, f"unreadable: {exc.strerror or exc}")))

    @property
    def total(self) -> int:

        return sum(self.objects.values())


def _cp(basename: str) -> StepArgv:

    return lambda cfg, _dsn: ("docker", "cp", str(cfg.database.schema_file.parent / "search" / basename), f"{_staged}{basename}")


async def _grade(step: _Step) -> RuntimeRail[_Step]:

    with anyio.move_on_after(step.deadline):
        return (await spawn(step.argv, subject=f"schema.{step.name}", retry_class=RetryClass.PROC, env=dict(step.env) or None)).map(
            lambda run: step.with_exit(run.returncode, run.stderr.decode(errors="replace").strip())
        )
    # `move_on_after` swallowed the cancellation; grade the contained deadline as the timeout sentinel so
    # the receipt stays total over every declared step.
    return Ok(step.with_exit(_TIMEOUT_EXIT, ""))


async def _drain_front(steps: tuple[_Step, ...]) -> Block[RuntimeRail[_Step]]:

    units = Block.of_seq(Admit.of(partial(_grade, step)) for step in steps)
    receipt: DrainReceipt[object] = await drain(_SCHEMA_LANE, units)
    graded = receipt.values.choose(lambda value: Some(value) if isinstance(value, _Step) else Nothing)
    return graded.map(Ok).append(receipt.faults.map(Error))


async def _front_sequential(steps: tuple[_Step, ...]) -> Block[RuntimeRail[_Step]]:

    return Block.of_seq([await _grade(step) for step in steps])


def _settled(graded: Block[_Step]) -> Envelope:

    by_name = {step.name: step for step in graded}
    ordered = tuple(by_name[name] for name in _STEPS if name in by_name)
    exits = tuple(step.code for step in ordered)
    status = Status.fold(Status.OK if code == 0 else Status.FAILED for code in exits)
    rows = tuple(Row(key=step.name, text=step.stderr or f"exit {step.code}") for step in ordered if step.code != 0)
    return completed(status, SchemaDetail(op=SchemaOp.APPLY, exits=exits), rows=rows)


async def _apply(cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    concurrent, sequential = _resolve(cfg, str(cfg.database.dsn))
    rails = (await _drain_front(concurrent)).append(await _front_sequential(sequential))
    return traversed(rails, by=Disposition.ABORT).map(_settled)


async def _doctor(cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    parsed, findings = traversed(_lint(cfg), by=Disposition.PARTITION).ok
    census = sum((Counter(dict(sql.objects)) for sql in parsed), Counter[str]())
    inventory = tuple(Row(key=sql.stem, text=f"{sql.total} objects, {sql.commands} commands") for sql in parsed)
    findings_rows = tuple(Row(key=fault.boundary[0], text=fault.boundary[1]) for fault in findings)
    detail = SchemaDetail(op=SchemaOp.DOCTOR, objects=frozendict(census))
    parse_status = Status.UNSUPPORTED if findings_rows else Status.OK

    def _report(result: db.QueryResult) -> Envelope:
        extensions = tuple(Row(key=str(name), text="v" + str(version)) for name, version in result.rows)
        # The census-diff gate (the `mcp validate` analog for extensions): the live `pg_extension` census
        # must equal the declared `profile` catalog. A declared-but-absent extension (apply gap) or an
        # installed-but-undeclared one (profile drift) folds to one `census:<name>` drift row and grades the
        # doctor `FAILED`, so a drifted profile surfaces as a reported defect rather than a silent skew.
        diff = census_diff(str(name) for name, _ in result.rows)
        drift_rows = tuple(Row(key=f"census:{name}", text="declared, not installed") for name in diff.missing) + tuple(
            Row(key=f"census:{name}", text="installed, not declared") for name in diff.undeclared
        )
        status = Status.FAILED if drift_rows else parse_status
        return completed(status, detail, rows=(*inventory, *findings_rows, *extensions, *drift_rows))

    return (await db.query("select extname, extversion from pg_extension order by 1", cfg)).map(_report)


def _lint(cfg: MaghzSettings) -> Block[RuntimeRail[_Sql]]:

    files = (cfg.database.schema_file, cfg.database.routines_file, cfg.database.cron_file)
    return Block.of_seq(_Sql.of(path) for path in files)


# Row columns: (argv builder, deadline, concurrent, daemon-facing). Daemon-facing rows spawn under the
# stage-resolved `DOCKER_HOST` overlay so the cp legs reach the prd container over ssh; the psql legs ride
# the DSN, which the tunnel keeps stage-agnostic.
_STEPS: frozendict[str, tuple[StepArgv, float, bool, bool]] = frozendict({
    "synonyms_cp": (_cp("synonyms.syn"), 30.0, True, True),
    "thesaurus_cp": (_cp("thesaurus.ths"), 30.0, True, True),
    "schema": (lambda cfg, dsn: ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.schema_file)), 120.0, False, False),
    "routines": (lambda cfg, dsn: ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.routines_file)), 120.0, False, False),
    "cron": (
        lambda cfg, _dsn: ("psql", cfg.database.maintenance_dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.cron_file)),
        60.0,
        False,
        False,
    ),
})


_SCHEMA_BUILD: frozendict[SchemaOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]] = frozendict({
    SchemaOp.APPLY: _apply,
    SchemaOp.DOCTOR: _doctor,
})
_SCHEMA_LANE: LanePolicy = LanePolicy(capacity=len(_STEPS), key=LaneKey("schema.apply"))


def _resolve(cfg: MaghzSettings, dsn: str) -> tuple[tuple[_Step, ...], tuple[_Step, ...]]:

    flagged = Block.of_seq(
        (_Step(name=name, argv=build(cfg, dsn), deadline=deadline, env=cfg.docker_env if daemon else frozendict()), concurrent)
        for name, (build, deadline, concurrent, daemon) in _STEPS.items()
    )
    concurrent, sequential = flagged.partition(itemgetter(1))
    return tuple(step for step, _ in concurrent), tuple(step for step, _ in sequential)


async def schema(op: SchemaOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:

    structlog.contextvars.bind_contextvars(rail="schema", op=op.value)
    return await _SCHEMA_BUILD[op](cfg)


class SyncOp(StrEnum):
    DIFF = "diff"  # drift census + live Heptabase card cross-check (no concept)
    GENERATE = "generate"


_SYNC_LIST_LIMIT: Final[str] = "100"


class SyncDetail(Detail, frozen=True, tag="sync"):
    op: SyncOp
    drifted: int | msgspec.UnsetType = msgspec.UNSET
    orphaned: int | msgspec.UnsetType = msgspec.UNSET
    card_total: int | msgspec.UnsetType = msgspec.UNSET
    card_id: str | msgspec.UnsetType = msgspec.UNSET
    card_title: str | msgspec.UnsetType = msgspec.UNSET


class _Card(msgspec.Struct, frozen=True, gc=False):
    id: str
    title: str = ""


class _CardList(msgspec.Struct, frozen=True, gc=False):
    total: int = 0
    results: tuple[_Card, ...] = ()


_CARD_LIST_DECODER: Final[msgspec.json.Decoder[_CardList]] = msgspec.json.Decoder(type=_CardList)
_CARD_DECODER: Final[msgspec.json.Decoder[_Card]] = msgspec.json.Decoder(type=_Card)


def _sync_graded[T: msgspec.Struct](run: CompletedProcess[bytes], decoder: msgspec.json.Decoder[T], argv: tuple[str, ...]) -> RuntimeRail[T]:

    if run.returncode == 0:
        return boundary("heptabase", lambda: decoder.decode(run.stdout))
    detail = run.stderr.decode(errors="replace").strip() or f"{' '.join(argv)} exit {run.returncode}"
    return Error(BoundaryFault(boundary=("heptabase", detail)))


async def _heptabase[T: msgspec.Struct](decoder: msgspec.json.Decoder[T], *argv: str) -> RuntimeRail[T]:

    return (await spawn(("heptabase", *argv), subject="heptabase", retry_class=RetryClass.PROC)).bind(lambda run: _sync_graded(run, decoder, argv))


async def _diff(cfg: MaghzSettings, _concept: str | None) -> RuntimeRail[Envelope]:

    sql = (
        "select card.card_id as key, "
        "card.drift_status || ': ' || coalesce(concept.canonical_name::text, '<unknown>') as text, "
        "(card.drift_status = 'orphaned') as is_orphaned "
        "from card left join concept on concept.id = card.concept_id "
        "where card.drift_status <> 'synced' "
        "order by card.drift_status, card.card_id"
    )
    match await db.query(sql, cfg):
        case Result(tag="ok", ok=QueryResult(rows=drift_rows)):
            drift = tuple(Row(key=str(card_id), text=str(text)) for card_id, text, _orphaned in drift_rows)
            orphaned = sum(1 for *_, is_orphaned in drift_rows if is_orphaned)
            return (await _heptabase(_CARD_LIST_DECODER, "card", "list", "--card-types", "note", "--limit", _SYNC_LIST_LIMIT)).map(
                lambda census: completed(
                    Status.OK if drift else Status.EMPTY,
                    SyncDetail(op=SyncOp.DIFF, drifted=len(drift) - orphaned, orphaned=orphaned, card_total=census.total),
                    rows=(*drift, *(Row(key=card.id, text=f"live: {card.title or '<untitled>'}") for card in census.results)),
                )
            )
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _generate(cfg: MaghzSettings, concept: str | None) -> RuntimeRail[Envelope]:

    sql = "select '# ' || coalesce(title, '') || E'\\n\\n' || coalesce(body, '') from concept where canonical_name = :name"
    match await db.query(sql, cfg, name=concept):
        case Result(tag="ok", ok=QueryResult(rows=((markdown, *_), *_))) if markdown:
            return (await _heptabase(_CARD_DECODER, "note", "create", "--content", str(markdown))).map(
                lambda card: completed(Status.OK, SyncDetail(op=SyncOp.GENERATE, card_id=card.id, card_title=card.title))
            )
        case Result(tag="ok"):
            return Ok(completed(Status.SKIP, SyncDetail(op=SyncOp.GENERATE), notes=(f"no content for concept {concept!r}",)))
        case Result(error=boundary_fault):
            return Error(boundary_fault)


_SYNC_BUILD: Final[frozendict[SyncOp, Callable[[MaghzSettings, str | None], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    SyncOp.DIFF: _diff,
    SyncOp.GENERATE: _generate,
})


async def sync(cfg: MaghzSettings, /, *, concept: str | None = None) -> RuntimeRail[Envelope]:

    op = SyncOp.DIFF if concept is None else SyncOp.GENERATE
    structlog.contextvars.bind_contextvars(rail="sync", op=op.value)
    return await _SYNC_BUILD[op](cfg, concept)


class HealthDetail(Detail, frozen=True, tag="health"):
    stage: Stage
    services: frozendict[str, str]
    extensions: int = 0
    embed_model: bool | msgspec.UnsetType = msgspec.UNSET


class _Model(msgspec.Struct, frozen=True, gc=False):
    name: str = ""


class _Tags(msgspec.Struct, frozen=True, gc=False):
    models: tuple[_Model, ...] = ()


class _Probe(msgspec.Struct, frozen=True, gc=False):
    service: str
    ok: bool
    note: str = ""
    extensions: int = 0
    embed_model: bool | msgspec.UnsetType = msgspec.UNSET


_TAGS_DECODER: Final[msgspec.json.Decoder[_Tags]] = msgspec.json.Decoder(type=_Tags)
_PROBE_TIMEOUT: Final[float] = 5.0
_HEALTH_SERVICES: Final[tuple[str, ...]] = ("postgres", "ollama", "n8n", "atuin")


async def _db_probe(cfg: MaghzSettings) -> _Probe:

    match await db.query("select count(*) from pg_extension", cfg):
        case Result(tag="ok", ok=QueryResult(rows=((count, *_), *_))):
            extensions = int(str(count))
            return _Probe(service="postgres", ok=True, note=f"{extensions} extensions", extensions=extensions)
        case Result(tag="ok"):
            return _Probe(service="postgres", ok=False, note="empty extension census")
        case Result(error=db_fault):
            return _Probe(service="postgres", ok=False, note=db_fault.headline())


async def _ollama_probe(cfg: MaghzSettings) -> _Probe:

    base = str(cfg.ollama.base_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            version = await client.get(f"{base}/api/version")
            tags = await client.get(f"{base}/api/tags")
            present = any(model.name.partition(":")[0] == cfg.ollama.embed_model for model in _TAGS_DECODER.decode(tags.content).models)
            note = f"embed_model={'present' if present else 'absent'}"
            return _Probe(service="ollama", ok=version.status_code == httpx.codes.OK, note=note, embed_model=present)
    except (httpx.HTTPError, msgspec.DecodeError) as exc:
        return _Probe(service="ollama", ok=False, note=type(exc).__name__)


async def _http_probe(service: str, url: str) -> _Probe:

    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            response = await client.get(url)
            return _Probe(service=service, ok=response.status_code == httpx.codes.OK, note=f"http {response.status_code}")
    except httpx.HTTPError as exc:
        return _Probe(service=service, ok=False, note=type(exc).__name__)


async def health(cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Probe the full service plane through its loopback ports and grade one receipt.

    A down service is a REPORTED outcome (`FAILED` with a per-service row), never a boundary fault:
    health exists to witness the plane, so the rail always completes. The probes ride the same
    loopback ports on both stages — the tunnel owns the prd mapping — so this rail carries no
    stage branch beyond the receipt's `stage` stamp.

    Returns:
        `Ok(completed(...))` carrying the `HealthDetail` service vector; `FAILED` when any probe is down.
    """
    structlog.contextvars.bind_contextvars(rail="health", stage=cfg.infra.stage.value)

    def lifted(fn: Callable[[], Awaitable[_Probe]]) -> Callable[[], Awaitable[RuntimeRail[object]]]:
        async def run() -> RuntimeRail[object]:
            return Ok(await fn())

        return run

    units = Block.of_seq(
        Admit.of(lifted(fn))
        for fn in (
            partial(_db_probe, cfg),
            partial(_ollama_probe, cfg),
            lambda: _http_probe("n8n", f"{cfg.n8n.api_url}/healthz"),
            lambda: _http_probe("atuin", str(cfg.infra.atuin_url)),
        )
    )
    receipt: DrainReceipt[object] = await drain(LanePolicy(capacity=len(_HEALTH_SERVICES), key=LaneKey("health.probe")), units)
    probed = {probe.service: probe for probe in receipt.values.choose(lambda value: Some(value) if isinstance(value, _Probe) else Nothing)}
    services = frozendict({name: ("ok" if (probe := probed.get(name)) is not None and probe.ok else "down") for name in _HEALTH_SERVICES})
    db_probe, ollama_probe = probed.get("postgres"), probed.get("ollama")
    detail = HealthDetail(
        stage=cfg.infra.stage,
        services=services,
        extensions=db_probe.extensions if db_probe is not None else 0,
        embed_model=ollama_probe.embed_model if ollama_probe is not None else msgspec.UNSET,
    )
    rows = tuple(Row(key=name, text=probed[name].note if name in probed else "probe did not complete") for name in _HEALTH_SERVICES)
    status = Status.OK if all(state == "ok" for state in services.values()) else Status.FAILED
    return Ok(completed(status, detail, rows=rows))


__all__ = [
    "CloudOp",
    "CloudSyncDetail",
    "HealthDetail",
    "Kind",
    "LedgerDetail",
    "LineageEdge",
    "N8nDetail",
    "N8nOp",
    "Projection",
    "SchemaDetail",
    "SchemaOp",
    "SyncDetail",
    "SyncOp",
    "cloud",
    "health",
    "ledger",
    "n8n",
    "schema",
    "sync",
]
