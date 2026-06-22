"""n8n rail: one polymorphic verb over workflow export, import, and container liveness.

A single `run` entrypoint discriminates on a closed `N8nOp` and lowers to the stdout `Envelope`
itself — it owns the `completed`/`fault` lift, so the CLI binds it with no `project` seam, the same
self-lowering contract the `cloud` rail exposes. EXPORT and IMPORT exec into the running container
through the sole `_exec` boundary, which drives `anyio.run_process(..., check=False)` and grades the
exit into the typed `N8nFault` rail (`op`/`message`/`exit_code`); a non-zero `docker exec` exit is a
domain `Error(N8nFault)`, never a raised exception. The workflow count derives from the host-mounted
`workflows_dir` `*.json` census — counted AFTER the export writes one `<id>.json` per workflow, and
BEFORE the import reads them — never from the user-facing stdout prose. STATUS rides `httpx` against
`cfg.n8n.api_url` `/healthz`: the retried `_probe_health` inner carries the `stamina.retry` liveness
aspect (idempotent, network-fragile) and returns the bare liveness `bool`, folding the
`httpx.HTTPStatusError` of a reached-but-non-200 service in place to `False` — a domain result, never
a fault. Its `_status_detail` boundary then lowers the surviving transport escape (a `httpx.HTTPError`
or `OSError` past the retry budget) to `Error(N8nFault(op=STATUS, exit_code=None))`, the same
exhausted-retry-to-rail discipline `cloud._rclone` applies, so the STATUS leg never raises into `run`.
`_BUILD` is the verb table, one row per `N8nOp`; the key set equals
`N8nOp` exactly, so `run`'s subscription is total and the closed `match` proves it through
`assert_never`. `run` folds the `Result` rail to one `completed`/`fault` envelope at this single edge,
binding `structlog.get_logger()` once at entry to emit the receipt fields to stderr — a single bind,
never an `@aspect` wrapper.
"""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import assert_never

import anyio
from expression import Error, Ok, Result
from frozendict import frozendict
import httpx
from msgspec import UNSET, UnsetType
import stamina
import structlog

from admin.core import completed, Detail, Envelope, fault, Status
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class N8nOp(StrEnum):
    """The closed set of n8n verbs `run` discriminates on; the `value` indexes `_BUILD` and the CLI.

    The `StrEnum` value is the dispatch key into `_BUILD` and the closed `error_context["op"]`
    vocabulary carried into `fault()` as `op.value`. The set is shaped to absorb a future BOOTSTRAP
    case (the deferred REST `POST /api/v1/users/me/api-key` step) as one new case plus one `_BUILD`
    row, without a parallel verb surface.
    """

    EXPORT = "export"
    IMPORT = "import"
    STATUS = "status"


# --- [MODELS] --------------------------------------------------------------------------


class N8nDetail(Detail, frozen=True, tag="n8n"):
    """Which n8n verb ran, the workflow file count, the exec-ed container, and confirmed liveness.

    `healthy` is `bool | UnsetType` so a STATUS-confirmed true/false liveness is distinct from the
    never-probed EXPORT/IMPORT ops: `msgspec.UNSET` encodes as ABSENT on the wire rather than `null`,
    preserving that distinction for downstream agent consumers. The `tag="n8n"` discriminant encodes
    as `$type` in `Envelope.report.detail`; the receipt folds into the existing `completed`/`fault`
    surface from `admin.core` with no parallel DTO.
    """

    op: N8nOp
    workflow_count: int = 0
    container: str = ""
    healthy: bool | UnsetType = UNSET


# --- [ERRORS] --------------------------------------------------------------------------


class N8nFault(Detail, frozen=True, tag="n8n_fault"):
    """The sole boundary failure both n8n boundaries lift: a `docker exec` exit grade or a STATUS transport escape.

    `op` is the verb; `message` is the decoded container stderr (EXPORT/IMPORT) or the transport
    description (STATUS). `exit_code` is the non-zero `docker exec` return for the process boundary and
    `None` for the STATUS transport escape, which carries no process exit — the same `int | None`
    discipline `CloudFault` uses for its non-process (`spawn`) seam. `_exec` and `_status_detail` each
    return it on the `Error` leg rather than raising, so a process failure or an exhausted-retry
    transport escape is a domain result the `run` fold lowers to `fault()`, never an exception in
    domain flow. `envelope()` lowers it to the stdout shape once, omitting `exit_code` when absent.
    """

    op: N8nOp
    message: str
    exit_code: int | None = None

    def envelope(self) -> Envelope:
        """Lower this fault to the stdout `fault` envelope, stamping `op` and the `exit_code` only when present."""
        exit_code = {"exit_code": str(self.exit_code)} if self.exit_code is not None else {}
        return fault(self.message, {"op": self.op.value, **exit_code})


# --- [OPERATIONS] ----------------------------------------------------------------------


async def _exec(op: N8nOp, cfg: MaghzSettings, *subcommand: str) -> Result[None, N8nFault]:
    """Exec one n8n Server CLI subcommand into the running container; grade the exit to the typed rail.

    The sole subprocess boundary: `anyio.run_process(..., check=False)` so this owns exit
    interpretation. A zero exit is `Ok(None)`; any non-zero exit is `Error(N8nFault)` carrying the
    verb, the decoded stderr, and the exit code — never a raised exception.

    Args:
        op: The verb stamped into a lifted fault (`EXPORT`/`IMPORT`).
        cfg: The validated settings owning the n8n container name.
        subcommand: The `n8n` Server CLI verb and its flags, exec-ed as `node` inside the container.

    Returns:
        `Ok(None)` on a zero exit, or `Error(N8nFault)` carrying the exit code and decoded stderr.
    """
    run = await anyio.run_process(
        ["docker", "exec", "-u", "node", cfg.n8n.container_name, "n8n", *subcommand],
        check=False,
    )
    if run.returncode == 0:
        return Ok(None)
    message = run.stderr.decode(errors="replace").strip() or f"{op.value} exited {run.returncode}"
    return Error(N8nFault(op=op, message=message, exit_code=run.returncode))


def _census(cfg: MaghzSettings) -> int:
    """Count the `*.json` workflow files in the host-mounted `workflows_dir` (small, non-hot path)."""
    return sum(1 for _ in Path(cfg.n8n.workflows_dir).glob("*.json"))


async def _export_detail(cfg: MaghzSettings) -> Result[N8nDetail, N8nFault]:
    """Export every workflow to one `<id>.json` per file, then census the host-mounted directory.

    `n8n export:workflow --all --separate` writes one JSON file per workflow into the container's
    `/home/node/workflows`, the host bind-mount of `cfg.n8n.workflows_dir`; the count is the
    post-exec `*.json` census, never stdout prose. A non-zero exit lifts to `Error(N8nFault)`.

    Args:
        cfg: The validated settings owning the n8n container name and the workflows directory.

    Returns:
        `Ok(N8nDetail(op=EXPORT))` carrying the post-exec file count and the exec-ed container
        (`healthy` stays `UNSET`, liveness was never probed), or `Error(N8nFault)` on a non-zero exit.
    """
    return (await _exec(N8nOp.EXPORT, cfg, "export:workflow", "--all", "--output=/home/node/workflows", "--separate")).map(
        lambda _: N8nDetail(op=N8nOp.EXPORT, workflow_count=_census(cfg), container=cfg.n8n.container_name)
    )


async def _import_detail(cfg: MaghzSettings) -> Result[N8nDetail, N8nFault]:
    """Census the host-mounted directory, then import every `<id>.json` workflow into the container.

    The count is the pre-exec `*.json` census of `cfg.n8n.workflows_dir` (the files about to be read);
    `n8n import:workflow --separate --input /home/node/workflows` reads that host bind-mount. A
    non-zero exit lifts to `Error(N8nFault)`.

    Args:
        cfg: The validated settings owning the n8n container name and the workflows directory.

    Returns:
        `Ok(N8nDetail(op=IMPORT))` carrying the pre-exec file count and the exec-ed container
        (`healthy` stays `UNSET`, liveness was never probed), or `Error(N8nFault)` on a non-zero exit.
    """
    count = _census(cfg)
    return (await _exec(N8nOp.IMPORT, cfg, "import:workflow", "--separate", "--input=/home/node/workflows")).map(
        lambda _: N8nDetail(op=N8nOp.IMPORT, workflow_count=count, container=cfg.n8n.container_name)
    )


@stamina.retry(on=(httpx.HTTPError, OSError), attempts=3)
async def _probe_health(cfg: MaghzSettings) -> bool:
    """Probe `/healthz` once under the retry aspect, returning liveness; a non-200 is `False`, not an escape.

    The retried inner of the STATUS boundary: idempotent and network-fragile, so it carries the
    `stamina.retry` aspect over the transport fault set. A reached-but-non-200 service is a
    domain-level result — `raise_for_status()`'s `httpx.HTTPStatusError` is caught in place and
    returns `False`, so a status code never triggers the retry. Only a transport `httpx.HTTPError` or
    `OSError` raises through the retry budget for the `_status_detail` boundary to lower.

    Args:
        cfg: The validated settings owning the derived n8n `api_url` and the connect timeout.

    Returns:
        `True` on a `/healthz` 200, `False` on a reached non-200 status.

    Raises:
        httpx.HTTPError: When the transport itself fails past the retry budget (connect/read/protocol).
        OSError: When the socket layer fails past the retry budget.
    """
    async with httpx.AsyncClient(base_url=cfg.n8n.api_url, timeout=cfg.n8n.connect_timeout) as client:
        try:
            response = await client.get("/healthz")
            _ = response.raise_for_status()
        except httpx.HTTPStatusError:
            return False
    return True


async def _status_detail(cfg: MaghzSettings) -> Result[N8nDetail, N8nFault]:
    """Run the retried `/healthz` probe, lowering an exhausted-retry transport escape to the typed rail.

    `_probe_health` owns the probe and the `@stamina.retry`; this boundary lowers the surviving
    transport escape (a `httpx.HTTPError` or `OSError` past the retry budget) to `Error(N8nFault)`,
    so the STATUS leg honors the `Result[N8nDetail, N8nFault]` rail and `run` never sees a raised
    exit — the same exhausted-retry-to-rail discipline `cloud._rclone` applies. The `exit_code` is
    `None`: a transport escape carries no process exit. A reached non-200 is `healthy=False`, never a
    fault (handled inside the probe).

    Args:
        cfg: The validated settings owning the derived n8n `api_url` and the connect timeout.

    Returns:
        `Ok(N8nDetail(op=STATUS, healthy=<liveness>))` on a reached service (200 or non-200), or
        `Error(N8nFault(op=STATUS, exit_code=None))` when the transport fails past the retry budget.
    """
    try:
        return Ok(N8nDetail(op=N8nOp.STATUS, healthy=await _probe_health(cfg)))
    except (httpx.HTTPError, OSError) as exc:
        return Error(N8nFault(op=N8nOp.STATUS, message=str(exc) or f"{N8nOp.STATUS.value} transport failed"))


# --- [TABLES] --------------------------------------------------------------------------

# op -> its workflow/liveness builder on the typed `Result[N8nDetail, N8nFault]` rail. The key set
# equals `N8nOp` exactly, so `run`'s subscription is total and the closed `match` proves it. EXPORT
# and IMPORT exec the container through `_exec` and census the bind-mount; STATUS carries its own
# retry aspect and folds a non-200 in place — each builder owns its own receipt and rail leg.
_BUILD: frozendict[N8nOp, Callable[[MaghzSettings], Awaitable[Result[N8nDetail, N8nFault]]]] = frozendict({
    N8nOp.EXPORT: _export_detail,
    N8nOp.IMPORT: _import_detail,
    N8nOp.STATUS: _status_detail,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: N8nOp, cfg: MaghzSettings, /) -> Envelope:
    """Run one n8n verb by `op`, lowering the typed rail to a single `completed`/`fault` envelope at this edge.

    `structlog.get_logger()` binds at entry and emits the receipt fields to stderr — the sole
    cross-cutting concern, a single bind rather than an `@aspect`. The closed `match op` (terminated
    by `assert_never`) dispatches through the total `_BUILD` table; the selected builder returns the
    typed `Result[N8nDetail, N8nFault]` rail. An `Ok` detail lowers to `completed(Status.OK, ...)`,
    and an `Error(N8nFault)` lowers through `N8nFault.envelope()` with `error_context["op"]` carrying
    `op.value` — the EXPORT/IMPORT exit grade and the STATUS transport escape both ride the one rail,
    never a `pulumi.automation.errors.CommandError`, which is an infra/stack concern.

    Args:
        op: The n8n verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings owning the n8n container name, workflows directory, and API URL.

    Returns:
        One `Envelope`: `Status.OK` carrying the typed `N8nDetail` receipt (with `detail.healthy`
        absent on the wire for EXPORT/IMPORT), or a `Status.FAULTED` envelope carrying the boundary
        fault message and the `op` context (plus `exit_code` for the EXPORT/IMPORT process boundary).
    """
    log = structlog.get_logger()
    match op:
        case N8nOp.EXPORT | N8nOp.IMPORT | N8nOp.STATUS:
            outcome = await _BUILD[op](cfg)
        case unreachable:
            assert_never(unreachable)
    match outcome:
        case Result(tag="ok", ok=detail):
            await log.ainfo("n8n.report", op=op.value, container=detail.container, workflow_count=detail.workflow_count)
            return completed(Status.OK, detail)
        case Result(error=n8n_fault):
            await log.aerror("n8n.fault", op=op.value, exit_code=n8n_fault.exit_code, detail=n8n_fault.message)
            return n8n_fault.envelope()


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["N8nDetail", "N8nFault", "N8nOp", "run"]
