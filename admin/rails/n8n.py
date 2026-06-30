"""n8n rail: one polymorphic verb over workflow export/import and the pending REST liveness census.

`run(op, cfg)` discriminates a closed `N8nOp` and returns the domain-internal `RuntimeRail[Envelope]`
the CLI `runtime.lower` seam collapses once at the edge — the same rail contract `schema`/`sync`/`ledger`
expose, never a bespoke self-lowering carrier. There is no per-rail fault carrier: every boundary mints
`BoundaryFault` directly (`config` for the pending REST auth setup, `boundary` for a non-zero
`docker exec` grade, `wire` for a reached-but-non-200 REST status, plus the spawn/transport leaves the
substrate `CLASSIFY` fold owns), so the typed `resource`/`deadline`/`wire` discrimination — and its retry
receipts — survive to the projection.

`_BUILD` is the verb table, one row per `N8nOp` over the shared `(cfg) -> RuntimeRail[Envelope]` shape;
the EXPORT/IMPORT rows carry their `_Cli` policy value (the Server-CLI subcommand the container runs),
so the two container verbs are one `_workflow` runner over a data row rather than two near-identical
functions, and STATUS its authenticated REST probe. The key set equals `N8nOp` exactly, so `run`'s
`_BUILD[op](cfg)` subscription is total and needs no `match`/`assert_never` ceremony around an
already-exhaustive `frozendict`.

EXPORT and IMPORT exec the n8n Server CLI into the running container through the one `runtime.spawn`
boundary (`anyio.run_process(check=False)` under `guard(RetryClass.PROC)`, the spawn-flap retry and the
exhausted-escape lift owned once in the substrate); this rail matches the returned `CompletedProcess`,
awaits the async `_census` over `anyio.Path.glob` only on a zero exit, and threads it into the pure
`_graded` exit projection (no blocking glob on the grade, the directory scan off the worker-thread pool).
The workflow count derives from the host-mounted `workflows_dir` `*.json` census — counted AFTER the
export writes one `<id>.json` per workflow, BEFORE the import reads them — never stdout prose.

STATUS is currently gated because n8n is not configured and no API-token owner exists. `_api_key` returns
one typed `Error(BoundaryFault(config=...))` before any socket opens; once n8n is deliberately configured,
the dormant `_N8nAuth`/`_probe` path can bind the admitted key at client construction and ride the existing
`guarded(RetryClass.HTTP, ...)` envelope without introducing keychain prompts or interactive unlocks.
`structlog` binds the rail context at entry; the receipt fields ride the egress at the `lower` edge.
"""

from collections.abc import Awaitable, Callable, Generator
from enum import StrEnum
from subprocess import CompletedProcess  # noqa: S404 - the graded spawn result type `_graded` reads, never spawned here
from typing import Final, override

import anyio
from expression import Error, Ok, Result
from frozendict import frozendict
import httpx
import msgspec
import structlog

from admin.core import completed, Detail, Envelope, Status
from admin.runtime import BoundaryFault, guarded, RetryClass, RuntimeRail
from admin.runtime.rails import spawn
from admin.settings import MaghzSettings, N8nConfig


# --- [TYPES] ---------------------------------------------------------------------------


class N8nOp(StrEnum):
    """The closed set of n8n verbs `run` discriminates on; the `value` indexes `_BUILD` and the CLI.

    The set is shaped to absorb a future BOOTSTRAP case (the REST `POST /api/v1/users/me/api-key` step)
    as one new member plus one `_BUILD` row, with every consumer untouched — never a parallel verb surface.
    """

    EXPORT = "export"
    IMPORT = "import"
    STATUS = "status"


# --- [CONSTANTS] -----------------------------------------------------------------------

# The container path the host `workflows_dir` bind-mounts to; the n8n CLI reads/writes one `<id>.json`
# per workflow here, and the host-side census reads the same files off `cfg.n8n.workflows_dir`.
_CONTAINER_WORKFLOWS: Final[str] = "/home/node/workflows"

# The live REST page bound: one decoded page carries the whole workflow census the count reports.
_LIST_LIMIT: Final[int] = 250


# --- [MODELS] --------------------------------------------------------------------------


class N8nDetail(Detail, frozen=True, tag="n8n"):
    """Which n8n verb ran, the workflow file/API count, the exec-ed container, and confirmed liveness.

    `healthy` is `bool | UnsetType` so a STATUS-confirmed true/false liveness is distinct from the
    never-probed EXPORT/IMPORT ops: `msgspec.UNSET` encodes ABSENT on the wire rather than `null`,
    preserving that distinction for downstream agent consumers. `workflow_count` carries the host-mounted
    `*.json` census for EXPORT/IMPORT and the live REST `/api/v1/workflows` total for STATUS. The
    `tag="n8n"` discriminant encodes as `$type` in `Envelope.report.detail`; the receipt folds into the
    shared `completed`/`fault` surface with no parallel DTO.
    """

    op: N8nOp
    workflow_count: int = 0
    container: str = ""
    healthy: bool | msgspec.UnsetType = msgspec.UNSET


class _Cli(msgspec.Struct, frozen=True, gc=False):
    """One n8n Server-CLI verb row: the `N8nOp` stamped into the receipt and the `node`-exec subcommand.

    The behavior-carrying policy value the `_BUILD` EXPORT/IMPORT rows hold — `op` keys the receipt and
    the fault subject, `subcommand` is the `n8n` CLI verb and flags exec-ed inside the container. A new
    container verb is one row, never a third near-identical `_export`/`_import` function the body re-derives.
    """

    op: N8nOp
    subcommand: tuple[str, ...]


class _Workflows(msgspec.Struct, frozen=True, gc=False):
    """The n8n public REST `GET /api/v1/workflows` envelope; only the `data` length is load-bearing.

    `forbid_unknown_fields` stays default so the unmodelled `nextCursor` and per-workflow object fields
    are ignored — the census reads `len(data)` off one decoded page, the count STATUS reports. Each member
    decodes as `msgspec.Raw` (the deferred-decode carrier), so the per-workflow object bodies are never
    materialized — only the array length is read, the cheapest decode of a page whose only load-bearing
    datum is its cardinality.
    """

    data: tuple[msgspec.Raw, ...] = ()


class _Liveness(msgspec.Struct, frozen=True, gc=False):
    """The STATUS probe census: `/healthz` liveness and the live REST workflow total, named not positional.

    The two facts the `_probe` client scope yields, carried as a named leaf owner (both fields are
    non-container leaves, so `gc=False` holds) rather than an anonymous `(bool, int)` pair the `_status`
    receipt fold would read by magic index — the receipt destructures `healthy`/`count` by name, so a
    third probe fact lands as one field with the fold untouched.
    """

    healthy: bool
    count: int


# --- [SERVICES] ------------------------------------------------------------------------


class _N8nAuth(httpx.Auth):
    """Dormant n8n REST auth flow for the future admitted `X-N8N-API-KEY`.

    The `httpx.Auth` flow is the credential seam the .api auth law mandates once n8n setup admits a real
    API-key owner: the key binds at client construction (`auth=`), never `None`-as-default and never an
    interior `headers` map threaded through `_probe`. The secret is held on this flow instance and written
    onto the outbound request header inside `auth_flow`, the single injection edge; `__slots__` and the
    absent `__repr__` keep it out of logs and tracebacks, the n8n analog of `SecretStr.get_secret_value`.
    """

    __slots__ = ("_key",)

    def __init__(self, key: str) -> None:
        self._key = key

    @override
    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        """Set the `X-N8N-API-KEY` header on the outbound request and yield it once (single-leg flow)."""
        request.headers["X-N8N-API-KEY"] = self._key
        yield request


# One process-wide decoder for the REST workflows envelope, resolved once at import rather than per probe;
# the decode escape rides the `guarded` HTTP fence so a malformed payload lifts through the one `CLASSIFY`
# authority (`DecodeError` -> `boundary`) rather than a hand-rolled catch.
_WORKFLOWS_DECODER: Final[msgspec.json.Decoder[_Workflows]] = msgspec.json.Decoder(type=_Workflows)

# The pool bound for the STATUS probe client: one connection carries the two sequential idempotent legs,
# so a single keepalive connection with the default expiry is the whole pool a probe ever opens.
_LIMITS: Final[httpx.Limits] = httpx.Limits(max_connections=1, max_keepalive_connections=1)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _api_key(_cfg: MaghzSettings) -> Result[_N8nAuth, BoundaryFault]:
    """Return the current n8n REST auth state.

    n8n is not set up yet, so there is no admitted API-token owner. The status rail fails truthfully instead
    of advertising a fake environment variable or vault item.

    Args:
        _cfg: The validated settings; unused until n8n is configured.

    Returns:
        `Error(BoundaryFault(config=...))` naming the `status` subject while n8n is not configured.
    """
    return Error(BoundaryFault(config=("status", "n8n API key is not configured; n8n setup is pending")))


async def _census(cfg: MaghzSettings) -> int:
    """Count the host-mounted `*.json` workflow files off `anyio.Path.glob`, never a blocking `Path.glob`.

    The census reads after the container exec writes/reads one `<id>.json` per workflow. `anyio.Path.glob`
    yields each match off the worker-thread pool, so the directory scan never blocks the event loop — the
    house async-filesystem idiom (`cloud._staging`/`_first_dump`), not the sync `pathlib.Path.glob` that
    would stall the loop on the mounted directory stat.

    Returns:
        The count of `*.json` workflow files in the host-mounted `workflows_dir`.
    """
    return len([entry async for entry in anyio.Path(cfg.n8n.workflows_dir).glob("*.json")])


def _graded(run: CompletedProcess[bytes], cli: _Cli, count: int, container: str) -> RuntimeRail[Envelope]:
    """Project one completed container exit to the typed rail: a zero exit censuses, any other faults.

    The pure exit grade over the `CompletedProcess` `spawn` returns, the house idiom every subprocess rail
    shares (`cloud._graded`/`schema`). A zero exit folds the already-counted host-mounted `*.json` census
    into the EXPORT/IMPORT receipt (`healthy` stays `UNSET`, liveness was never probed); any non-zero exit
    mints `Error(BoundaryFault(boundary=...))` directly, carrying the verb subject and the decoded container
    stderr — never a per-rail fault carrier, never a raised exception. The census is computed off the async
    `_census` in `_workflow` and threaded in, so this projection stays pure (no blocking I/O on the grade).

    Returns:
        `Ok(completed(OK, N8nDetail))` carrying the post-exec file count on a zero exit, or
        `Error(BoundaryFault)` for a non-zero exit grade.
    """
    if run.returncode == 0:
        return Ok(completed(Status.OK, N8nDetail(op=cli.op, workflow_count=count, container=container)))
    detail = run.stderr.decode(errors="replace").strip() or f"{cli.op.value} exited {run.returncode}"
    return Error(BoundaryFault(boundary=(f"n8n.{cli.op.value}", detail)))


async def _workflow(cli: _Cli, cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Exec one n8n Server-CLI verb into the container through `runtime.spawn`, grading the exit to the rail.

    The one container-verb runner the EXPORT/IMPORT `_BUILD` rows share: `spawn` owns the
    `anyio.run_process(check=False)` + `guard(RetryClass.PROC)` spawn-flap retry + the exhausted-escape
    lift, so this leg matches the one `guard`-stacked spawn rail, awaits the async `_census` only on a zero
    exit (the count is `0` past a fault, never read), and threads it into the pure `_graded` exit projection
    — the I/O stays on the async rail, `_graded` stays pure. `export:workflow --all --separate` writes one
    `<id>.json` per workflow into the container's `_CONTAINER_WORKFLOWS` bind-mount of `cfg.n8n.workflows_dir`;
    `import:workflow --separate --input` reads it back. The count is the host-mounted `*.json` census read
    after the exec — never stdout prose; an import reads, not writes, so the host census is stable across the
    exec and equals the post-exec read.

    Args:
        cli: The `_Cli` policy row carrying the receipt `op` and the `node`-exec Server-CLI subcommand.
        cfg: The validated settings owning the n8n container name and the workflows directory.

    Returns:
        `Ok(completed(OK, N8nDetail))` carrying the host-mounted `*.json` census on a zero exit, or
        `Error(BoundaryFault)` for a non-zero exit grade or a spawn flap past the `PROC` budget.
    """
    argv = ("docker", "exec", "-u", "node", cfg.n8n.container_name, "n8n", *cli.subcommand)
    match await spawn(argv, subject=f"n8n.{cli.op.value}", retry_class=RetryClass.PROC):
        case Result(tag="error", error=spawn_fault):
            return Error(spawn_fault)
        case Result(ok=run):
            count = await _census(cfg) if run.returncode == 0 else 0
            return _graded(run, cli, count, cfg.n8n.container_name)


async def _probe(n8n: N8nConfig, auth: _N8nAuth) -> _Liveness:
    """Probe `/healthz` liveness and the authenticated `/api/v1/workflows` census in one client scope.

    The retried inner of the STATUS boundary, idempotent and network-fragile, so the caller drives it under
    `guarded(RetryClass.HTTP, ...)` after n8n setup admits a real API key. One long-lived `httpx.AsyncClient`
    carries both legs under an explicit per-phase `httpx.Timeout` (the config `connect_timeout` floors connect
    and bounds read/write/pool) and the single-connection pool `_LIMITS`: the admitted key binds at
    construction as the `_N8nAuth` flow, so neither leg threads a `headers` map. `/healthz` (no auth needed, but the flow signs it harmlessly)
    grades liveness in place against `httpx.codes.OK` — a reached-but-non-200 health is `False`, a domain
    result, not an escape — while `GET /api/v1/workflows` reads the live server-side census, decoded through
    the shared `_WORKFLOWS_DECODER`. A reached non-200 on the API leg `raise_for_status`-es into the
    `httpx.HTTPStatusError` the substrate `CLASSIFY` lands as `wire`, so the status code survives to the
    projection; a transport escape past the retry budget lifts at the caller's `guarded` envelope.

    Args:
        n8n: The validated n8n config owning the derived `api_url` and the connect timeout.
        auth: The `_N8nAuth` flow minted once at admission, bound at client construction.

    Returns:
        The `_Liveness` census naming `/healthz` liveness and the live REST workflow total.

    Raises:
        httpx.HTTPError: When a transport leg fails past the retry budget (connect/read/protocol/status).
        OSError: When the socket layer fails past the retry budget.
    """
    timeout = httpx.Timeout(connect=n8n.connect_timeout, read=n8n.connect_timeout, write=n8n.connect_timeout, pool=n8n.connect_timeout)
    async with httpx.AsyncClient(base_url=n8n.api_url, auth=auth, timeout=timeout, limits=_LIMITS, headers={"accept": "application/json"}) as client:
        health = await client.get("/healthz")
        listing = (await client.get("/api/v1/workflows", params={"limit": _LIST_LIMIT})).raise_for_status()
        return _Liveness(healthy=health.status_code == httpx.codes.OK, count=len(_WORKFLOWS_DECODER.decode(listing.content).data))


async def _status(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Return the current n8n status rail.

    `_api_key` is the synchronous admission edge: because n8n setup is still pending and no API-key owner
    exists, it short-circuits to a typed config fault before any socket opens. Once n8n is configured, the
    same edge can mint `_N8nAuth` and `guarded(RetryClass.HTTP, _probe, ...)` will drive the retried probe
    under the runtime resilience envelope.

    Args:
        cfg: The validated settings owning the derived n8n `api_url` and the connect timeout.

    Returns:
        `Ok(completed(OK, N8nDetail(op=STATUS, healthy=...)))` carrying the live workflow census after
        n8n is configured, or `Error(BoundaryFault)` while setup is pending.
    """
    match _api_key(cfg):
        case Result(tag="error", error=config_fault):
            return Error(config_fault)
        case Result(ok=auth):
            probed = await guarded(RetryClass.HTTP, _probe, cfg.n8n, auth, subject="n8n.status")
            return probed.map(
                lambda live: completed(
                    Status.OK, N8nDetail(op=N8nOp.STATUS, workflow_count=live.count, container=cfg.n8n.container_name, healthy=live.healthy)
                )
            )


# --- [TABLES] --------------------------------------------------------------------------

# The primary container-verb correspondence: each EXPORT/IMPORT op -> its `_Cli` Server-CLI policy row.
# `export:workflow --all --separate` writes one `<id>.json` per workflow into the `_CONTAINER_WORKFLOWS`
# bind-mount; `import:workflow --separate --input` reads it back. `_BUILD` derives its two container rows
# from this map, so the subcommand lives once as data — a new container verb is one `_CLI` row.
_CLI: Final[frozendict[N8nOp, _Cli]] = frozendict({
    N8nOp.EXPORT: _Cli(op=N8nOp.EXPORT, subcommand=("export:workflow", "--all", f"--output={_CONTAINER_WORKFLOWS}", "--separate")),
    N8nOp.IMPORT: _Cli(op=N8nOp.IMPORT, subcommand=("import:workflow", "--separate", f"--input={_CONTAINER_WORKFLOWS}")),
})

# op -> its workflow/liveness builder on the shared `(cfg) -> RuntimeRail[Envelope]` rail, derived from
# `_CLI`: the EXPORT/IMPORT rows bind one `_workflow` runner over their `_Cli` policy row (the Server-CLI
# subcommand is data, not a second function), STATUS rides the authenticated REST envelope under
# `guarded(RetryClass.HTTP, ...)`. The key set equals `N8nOp` exactly, so `run`'s `_BUILD[op]` subscription
# is total — a new verb is one member plus one row, never a branch.
_BUILD: Final[frozendict[N8nOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    **{op: (lambda cfg, cli=cli: _workflow(cli, cfg)) for op, cli in _CLI.items()},
    N8nOp.STATUS: _status,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: N8nOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one n8n verb by `op` on the domain rail, dispatching through the total `_BUILD` table.

    `structlog.contextvars.bind_contextvars` scopes the rail/op facts once at entry — the sole
    cross-cutting concern, a single bind rather than an `@aspect`. `_BUILD[op](cfg)` selects the builder
    over the exhaustive table (no `match`/`assert_never` ceremony around an already-total `frozendict`);
    the builder returns the domain-internal `RuntimeRail[Envelope]`, which the CLI handler lowers to the
    stdout `Envelope` through the one `runtime.lower` seam — the EXPORT/IMPORT exit grade and the STATUS
    transport/`wire` escape both ride that single edge.

    Args:
        op: The n8n verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings owning the n8n container name, workflows directory, and API URL.

    Returns:
        The rail the selected builder produced — `Ok(Envelope)` carrying the typed `N8nDetail` receipt
        (with `detail.healthy` absent on the wire for EXPORT/IMPORT), or `Error(BoundaryFault)` from the
        container exit grade, pending n8n auth setup, or the REST transport boundary.
    """
    structlog.contextvars.bind_contextvars(rail="n8n", op=op.value)
    return await _BUILD[op](cfg)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["N8nDetail", "N8nOp", "run"]
