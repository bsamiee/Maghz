"""Schema rail: one polymorphic verb over the idempotent apply and the ledger health probe.

A single `run` entrypoint discriminates on a closed `SchemaOp` and returns the domain-internal
`RuntimeRail[Envelope]`; the CLI handler projects that rail to the stdout `Envelope` through the
entrypoint's `project` seam, so the spawn-boundary fault lowers once, at the edge, never inline.
`apply` replays five steps in dependency order: the two text-search dictionary files are staged
into the container and the declarative schema is applied concurrently (`synonyms_cp`,
`thesaurus_cp`, `atlas`), then the routine objects and the cron registration run sequentially
(`routines`, `cron`). Concurrency is safe across the first three because the dictionary `docker
cp`s and the schema apply touch disjoint surfaces; `routines` runs strictly after because its
trigger/FK bodies bind to the tables `atlas` creates, and `cron` runs last against the `postgres`
maintenance DB (pg_cron lives only there; jobs execute IN maghz via `cron.schedule_in_database`).
Every SQL file is idempotent; a replay is a clean no-op. The DSN is passed explicitly (`psql
<dsn>`) rather than through the environment, because pydantic-settings reads `.env` into the
model, not `os.environ`.

Each step is deadline-bounded with `anyio.move_on_after` (not `fail_after`): a tripped deadline
silently cancels the step and records a non-zero sentinel exit, so the `exits` receipt always
has five elements in declaration order. Step exit codes fold to one outcome (`FAILED` on any
non-zero). The spawn fence routes through the canonical resilience boundary: `guard(RetryClass.PROC)`
retries transient `OSError` spawn flaps and `async_boundary('apply', ...)` lifts any surviving
escape to the `BoundaryFault` rail, so a fatal spawn fault rides the rail to the CLI projection
rather than collapsing inline. `doctor` reads the extension census on a connectivity probe; a clean
probe carries its census `Ok`, and a DB-boundary fault lifts in place to the same `BoundaryFault`
rail so the typed boundary discrimination survives to the CLI projection rather than pre-lowering.
"""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import assert_never

import anyio
from expression import Error, Ok, Result
from frozendict import frozendict
import msgspec

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.runtime import async_boundary, BoundaryFault, guard, RetryClass, RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class SchemaOp(StrEnum):
    """The closed set of schema verbs `run` discriminates on."""

    APPLY = "apply"
    DOCTOR = "doctor"


# --- [CONSTANTS] -----------------------------------------------------------------------

# The PG18 ParadeDB image shared dir; the rail stages the text-search dictionaries here
# before routines.sql creates the kb_english dictionaries that reference them by name.
_TSEARCH_DATA = "/usr/share/postgresql/18/tsearch_data"
_CONTAINER = "maghz-db"
# The exit recorded when a step's `move_on_after` deadline trips; non-zero so it folds to
# `FAILED` and reads as a deadline breach (the conventional timeout exit code).
_TIMEOUT_EXIT = 124


# --- [MODELS] --------------------------------------------------------------------------


class SchemaDetail(Detail, frozen=True, tag="schema"):
    """Which schema verb ran and its per-step exit codes."""

    op: str
    exits: tuple[int, ...] = ()


class _Step(msgspec.Struct, frozen=True, gc=False):
    """One named, deadline-bounded apply step: the command to spawn and its wall-clock budget."""

    name: str
    argv: tuple[str, ...]
    deadline: float


# --- [OPERATIONS] ----------------------------------------------------------------------


async def _step(step: _Step) -> tuple[int, str]:
    """Run one step under its deadline, returning its exit code and stderr text.

    A tripped `move_on_after` deadline cancels the call and yields the timeout sentinel; a
    spawn failure raises `OSError`, which the `async_boundary` fence lifts to a `BoundaryFault`.

    Args:
        step: The named command and wall-clock budget to spawn.

    Returns:
        `(exit_code, stderr)` where `exit_code` is the process return code or the timeout
        sentinel, and `stderr` is the decoded standard error (empty on a tripped deadline).

    Raises:
        OSError: When the step binary cannot be spawned.
    """
    with anyio.move_on_after(step.deadline):
        run = await anyio.run_process(step.argv, check=False)
        return run.returncode, run.stderr.decode(errors="replace").strip()
    # Control reaches here only when the deadline tripped and `move_on_after` swallowed the
    # cancellation; the step gets the timeout sentinel exit so the receipt folds to FAILED.
    return _TIMEOUT_EXIT, ""


async def _run_steps(concurrent: tuple[_Step, ...], sequential: tuple[_Step, ...]) -> tuple[tuple[int, str], ...]:
    """Run the concurrent steps in one task group, then the sequential steps, in declaration order.

    Each concurrent task writes its `(exit_code, stderr)` outcome into the index-keyed `outcomes`
    map under its own declaration index, so the receipt is rebuilt in declaration order regardless
    of completion order — the index is the order, not the completion sequence. The sequential steps
    run strictly after the group joins and write their trailing indices the same way.

    Args:
        concurrent: The steps run concurrently (declaration indices `0..len-1`).
        sequential: The steps run sequentially after the group (the trailing indices).

    Returns:
        One `(exit_code, stderr)` pair per step in declaration order.

    Raises:
        OSError: When any step binary cannot be spawned (sequential phase).
        BaseExceptionGroup: When a concurrent step's spawn fails inside the task group.
    """
    outcomes: dict[int, tuple[int, str]] = {}

    async def _emit(index: int, step: _Step) -> None:
        outcomes[index] = await _step(step)

    async with anyio.create_task_group() as group:
        for index, step in enumerate(concurrent):
            group.start_soon(_emit, index, step)
    for index, step in enumerate(sequential, start=len(concurrent)):
        outcomes[index] = await _step(step)
    return tuple(outcomes[index] for index in range(len(concurrent) + len(sequential)))


async def _apply_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Idempotent five-step schema apply on the rail: dictionaries and schema concurrently, then routines and cron.

    Stages the two text-search dictionary files into the container and applies the declarative
    schema concurrently (`synonyms_cp`, `thesaurus_cp`, `atlas`), then runs `routines` and `cron`
    sequentially. Every step is `-v ON_ERROR_STOP=1`; a replay produces no errors and no DDL
    mutations. Step exit codes fold to one outcome; a surviving spawn escape rides the boundary
    fault to the CLI projection rather than lowering to an `Envelope` here.

    Args:
        cfg: The validated settings owning the DSN and the schema/routines/cron file paths.

    Returns:
        `Ok(completed(...))` carrying the apply receipt — `OK` when all steps exit zero, `FAILED`
        with the non-zero exit rows (including any deadline-tripped step) — or `Error(BoundaryFault)`
        when a step binary cannot be spawned past the `PROC` retry budget.
    """
    dsn = str(cfg.database.dsn)
    search = cfg.database.schema_file.parent / "search"
    # Declaration order is the receipt order: synonyms_cp, thesaurus_cp, atlas, routines, cron.
    concurrent = (
        _Step("synonyms_cp", ("docker", "cp", str(search / "synonyms.syn"), f"{_CONTAINER}:{_TSEARCH_DATA}/maghz_synonyms.syn"), 30.0),
        _Step("thesaurus_cp", ("docker", "cp", str(search / "thesaurus.ths"), f"{_CONTAINER}:{_TSEARCH_DATA}/maghz_thesaurus.ths"), 30.0),
        _Step("atlas", ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.schema_file)), 120.0),
    )
    sequential = (
        _Step("routines", ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.routines_file)), 60.0),
        _Step("cron", ("psql", cfg.database.maintenance_dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.cron_file)), 60.0),
    )
    # The spawn fence routes through the canonical resilience boundary: `guard(RetryClass.PROC)`
    # retries transient `OSError` spawn flaps, and `async_boundary('apply', ...)` lifts any
    # surviving escape to the `BoundaryFault` rail. The fault stays unprojected — the CLI handler
    # owns the single `BoundaryFault`->`Envelope` lowering.
    match await async_boundary("apply", lambda: guard(RetryClass.PROC)(_run_steps, concurrent, sequential)):
        case Result(tag="ok", ok=outcomes):
            graded = tuple(zip((*concurrent, *sequential), outcomes, strict=True))
            exits = tuple(code for _, (code, _) in graded)
            status = Status.fold(Status.OK if code == 0 else Status.FAILED for code in exits)
            rows = tuple(Row(key=step.name, text=stderr or f"exit {code}") for step, (code, stderr) in graded if code != 0)
            return Ok(completed(status, SchemaDetail(op="apply", exits=exits), rows=rows))
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _doctor_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Probe connectivity and report the installed extension census, carried on the rail.

    The connectivity probe rides one `BoundaryFault` rail: a clean probe carries its extension
    census on the `Ok` leg, and a DB-boundary fault lifts in place through
    `BoundaryFault(boundary=(op, message))` and short-circuits on the `Error` leg, exactly as the
    `sync` rail's DIFF read does. `run` returns the rail unprojected so the CLI `project` seam
    lowers any surviving `Error(BoundaryFault)` to a `fault` envelope once, at the edge — the
    typed boundary discrimination never collapses to a stringly-typed envelope inline.

    Args:
        cfg: The validated settings owning the DSN used for the probe query.

    Returns:
        `Ok(completed(OK))` with one row per extension, or `Error(BoundaryFault)` lifted from the
        DB boundary when the connectivity probe itself fails.
    """
    match await db.query("select extname, extversion from pg_extension order by 1", cfg):
        case Result(tag="ok", ok=result):
            rows = tuple(Row(key=str(name), text="v" + str(version)) for name, version in result.rows)
            return Ok(completed(Status.OK, SchemaDetail(op="doctor"), rows=rows))
        case Result(error=dbfault):
            return Error(BoundaryFault(boundary=(dbfault.op, dbfault.message)))


# --- [TABLES] --------------------------------------------------------------------------

# op -> its full apply/probe builder. The key set equals `SchemaOp` exactly, so `run`'s
# subscription is total; each builder owns its own status fold, rows, and rail leg.
_RUNNER: frozendict[SchemaOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]] = frozendict({
    SchemaOp.APPLY: _apply_detail,
    SchemaOp.DOCTOR: _doctor_detail,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: SchemaOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one schema verb by `op` on the domain rail, dispatching through the `_RUNNER` table.

    The returned `RuntimeRail[Envelope]` is the domain-internal contract; the CLI handler lowers
    it to the stdout `Envelope` through the entrypoint's `project` seam, so a boundary fault is
    projected once, at the edge.

    Args:
        op: The schema verb to run; selects its builder from `_RUNNER`.
        cfg: The validated settings owning the DSN and the schema/routines/cron file paths.

    Returns:
        The rail the selected builder produced — `Ok(Envelope)` carrying a completed apply/probe
        receipt, or `Error(BoundaryFault)` from the apply spawn fence.
    """
    match op:
        case SchemaOp.APPLY | SchemaOp.DOCTOR:
            return await _RUNNER[op](cfg)
        case unreachable:
            assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["SchemaDetail", "SchemaOp", "run"]
