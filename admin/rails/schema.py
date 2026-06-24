"""Schema rail: one polymorphic verb over the idempotent apply and the static-plus-connectivity doctor probe.

A single `run` entrypoint discriminates on a closed `SchemaOp` and returns the domain-internal
`RuntimeRail[Envelope]`; the CLI handler projects that rail to the stdout `Envelope` through the
`runtime.lower` seam, so the boundary fault lowers once, at the edge, never inline. The verb table
`_BUILD` is total over `SchemaOp`, so `run` is a direct subscription — `await _BUILD[op](cfg)` — with no
`match`/`assert_never` ceremony guarding an already-exhaustive `frozendict`.

`apply` replays five `psql`/`docker cp` steps as two ordered fronts. The two text-search dictionary
`docker cp`s (`synonyms_cp`, `thesaurus_cp`) are mutually independent and the concurrent front fans them
out over the one substrate `drain`; the three `psql` applies (`schema`, `routines`, `cron`) are the second
front, awaited strictly in declaration order — `schema` first because it creates the extensions, the
`kb_english` configuration, and every table; `routines` next because its trigger/FK/exotic-index bodies
bind to those tables and that configuration; `cron` last against the `postgres` maintenance DB (pg_cron
lives only there; jobs execute IN maghz via `cron.schedule_in_database`). The concurrent front fully drains
before the sequential front begins, so the dictionary files are staged before `schema` creates the
`kb_english` dictionaries that reference them by name. The concurrent fan-out is never a raw
`anyio.create_task_group`: it is one `drain` over
`Block.of_seq(Admit.of(lambda: _grade(step)))` under the memoised `_LANE` `CapacityLimiter`, so the
concurrency bound and the lossless `(values, faults)` fan-in are the runtime lane's, never hand-rolled
stream/index machinery — the exact shape `cloud._fan_out` composes. The sequential front is a plain
in-order `await` (a hard dependency is not a bounded fan-out, so it owns no lane). `_grade` self-bounds
each spawn under its own `anyio.move_on_after` (never `fail_after`, whose `TimeoutError` would escape
without a receipt), grading a tripped deadline as the contained `_TIMEOUT_EXIT` step rather than a lost
unit, so the lane carries no deadline of its own. Every step is `-v ON_ERROR_STOP=1` and idempotent; a
replay is a clean no-op. The DSN is passed explicitly (`psql <dsn>`) rather than through the environment,
because pydantic-settings reads `.env` into the model, not `os.environ`.

Each step routes its subprocess through the one canonical `runtime.spawn` boundary —
`anyio.run_process(check=False)` under `guard(RetryClass.PROC)` with the exhausted-retry escape lifted to
the `BoundaryFault` rail — so this rail never re-derives the offload/retry/grade chain, and the lane
admits the already-guarded `_grade` as a `bare` unit (a `retried` admission would nest the retry). Both
fronts' rails fold through `traversed(ABORT)` and `_settled` re-orders the graded steps off the step
`name` into `_STEPS` declaration order: a genuine spawn fault (a binary missing past the retry budget)
short-circuits the whole apply onto the rail, while a non-zero `psql` exit is graded DATA the receipt
reports as a `FAILED` row.

`doctor` is a preflight over both planes. The static plane parses the three declarative SQL files through
the `sqlglot` PostgreSQL plane into one `_Sql` AST owner apiece — the same parse-once-materialize-structure
discipline the `ledger` rail's `Projection` applies, the structural census frozen onto the owner at the one
`of` admission, never a per-access property recompute over the import-constant tree. Each file's `objects`
census (`exp.Create.kind` -> the table/index/function/view/... object tally) and `commands` count (the
PG-specific `DO`/trigger bodies that degrade to a `Command` node) fold once off the parsed tree. A genuine
syntax break surfaces as an `UNSUPPORTED` finding row through `traversed(PARTITION)` WITHOUT aborting the
probe, the census still folding for every file that parses; the per-kind object tally rides the
`SchemaDetail` receipt as structural inventory evidence. The connectivity plane then reads the installed
extension census on a `db.query` probe, composed as a flat `.map` over the one `BoundaryFault` rail: a
clean preflight carries its census rows, object rows, and extension `Ok`; a DB-boundary fault propagates in
place (lifted once inside `db.py`) so the typed boundary discrimination survives to the CLI projection
rather than pre-lowering.
"""

# --- [RUNTIME_PRELUDE] -----------------------------------------------------------------

from collections import Counter
from collections.abc import Awaitable, Callable
from enum import StrEnum
import logging
from operator import itemgetter
from pathlib import Path

import anyio
from expression import Error, Nothing, Ok, Some
from expression.collections import Block
from frozendict import frozendict
import msgspec
from sqlglot import Dialects, ErrorLevel, exp, parse
from sqlglot.errors import ParseError
import structlog

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.profile import census_diff
from admin.runtime import Admit, BoundaryFault, Disposition, drain, DrainReceipt, LanePolicy, RetryClass, RuntimeRail, traversed
from admin.runtime.rails import spawn  # `spawn` is the subprocess owner in `runtime.rails`, absent from the `runtime` facade re-export
from admin.settings import MaghzSettings


# A PG-specific `DO`/trigger/policy body sqlglot cannot fully model degrades to a `Command` node and
# emits one WARN line on the stdlib `sqlglot` logger per occurrence; the census counts those degradations
# as data, so that warn stream is pure noise on the result channel. Silenced once at import — a foreign
# stdlib logger the structlog ban does not own, so its level is set directly rather than re-routed.
logging.getLogger("sqlglot").setLevel(logging.ERROR)  # noqa: TID251 - foreign third-party stdlib logger, not a Maghz pipeline log


# --- [TYPES] ---------------------------------------------------------------------------


class SchemaOp(StrEnum):
    """The closed set of schema verbs `run` discriminates on; the `value` indexes `_BUILD` and the CLI."""

    APPLY = "apply"
    DOCTOR = "doctor"


# One `_STEPS` policy column: the argv builder applied to the settings and resolved DSN at plan time.
type StepArgv = Callable[[MaghzSettings, str], tuple[str, ...]]


# --- [CONSTANTS] -----------------------------------------------------------------------

_CONTAINER = "maghz-db"
# The PG18 ParadeDB image shared dir; the rail stages the text-search dictionaries here before
# routines.sql creates the kb_english dictionaries that reference them by name. `_staged` is the
# `<container>:<dir>/maghz_` target prefix the two `docker cp` rows append the dictionary basename to,
# folded once so each `_STEPS` row stays a single readable line.
_TSEARCH_DATA = "/usr/share/postgresql/18/tsearch_data"
_staged = f"{_CONTAINER}:{_TSEARCH_DATA}/maghz_"
# The dialect every declarative SQL file is authored, parsed, and census-folded under; the ledger AST
# round-trip canonicalizes to the same Postgres plane (pg8000), never a cross-dialect transpile.
_DIALECT = Dialects.POSTGRES
# The exit folded onto a step whose `move_on_after` deadline tripped before a `CompletedProcess`
# returned; non-zero so it grades to `FAILED` and reads as a deadline breach (the conventional code).
_TIMEOUT_EXIT = 124


# --- [MODELS] --------------------------------------------------------------------------


class SchemaDetail(Detail, frozen=True, tag="schema"):
    """Which schema verb ran, its per-step exit codes, and the doctor's folded declarative-object census.

    `exits` carries one code per apply step in declaration order (empty for `doctor`), so a consumer
    reads the full step grade off this canonical receipt rather than re-deriving it from the rows.
    `objects` carries the doctor's structural DDL census — the `exp.Create.kind` object tally
    (`table`/`index`/`function`/`view`/...) summed across the three declarative files, off the parsed
    AST — so a consumer reads what the schema declares off the typed receipt rather than re-parsing the
    SQL; empty for `apply` and absent on the wire when no object is counted. `op` is the closed `SchemaOp`
    discriminant, not a bare `str`, so the receipt carries the verb typed to its domain like every sibling.
    """

    op: SchemaOp
    exits: tuple[int, ...] = ()
    objects: frozendict[str, int] = frozendict()


class _Step(msgspec.Struct, frozen=True, gc=False):
    """One named apply step: its resolved command, wall-clock budget, and (after spawn) its graded exit.

    `argv` is the fully-resolved command (the `_STEPS` row's builder applied to settings and DSN at plan
    time); `code`/`stderr` are folded on by `_grade` (through `with_exit`) off the spawned
    `CompletedProcess` or the deadline sentinel, so one struct carries the step from plan through grade
    without a parallel outcome tuple.
    """

    name: str
    argv: tuple[str, ...]
    deadline: float
    code: int = 0
    stderr: str = ""

    def with_exit(self, code: int, stderr: str) -> _Step:
        """Derive the graded step, folding the spawned exit code and decoded stderr onto this row."""
        return msgspec.structs.replace(self, code=code, stderr=stderr)


class _Sql(msgspec.Struct, frozen=True):
    """One parsed declarative SQL file admitted once: its `objects` census and `commands` count, by stem.

    `of` parses the file under the Postgres `RAISE` policy and materializes the structural census off the
    tree at that one admission — `objects` is the `exp.Create.kind` object tally (lowercased:
    `table`/`index`/`function`/`view`/`schema`/`trigger`/..., an unset kind folding under `object`) frozen
    as a `frozendict`, and `commands` the count of PG-specific bodies (`DO`/`CREATE TRIGGER`/...) that
    degraded to a `Command` node. The tree is import-time-or-once constant, so these are frozen fields
    built once rather than per-access properties re-walking the AST per read — the same
    parse-once-materialize-structure discipline the `ledger` rail's `Projection` applies. A genuine syntax
    break lifts to a `boundary` finding fault the doctor folds to an `UNSUPPORTED` row, while a valid PG
    `DO`/trigger body is a `Command` census entry, not a fault. Not `gc=False`: `objects` is a `frozendict`
    container, so the leaf-only elision does not apply.
    """

    stem: str
    objects: frozendict[str, int]
    commands: int

    @staticmethod
    def of(path: Path) -> RuntimeRail[_Sql]:
        """Parse one declarative SQL file under the Postgres `RAISE` policy, materializing its census once.

        `sqlglot.parse(error_level=RAISE)` raises `ParseError` on a genuine syntax break (PostgreSQL-
        specific DDL it cannot model degrades to a `Command` node rather than raising, so a valid
        trigger/policy body is census data, not a false positive). One `Counter` pass over the `exp.Create`
        nodes folds the `objects` tally (frozen to `frozendict`) and one `sum` the `commands` degradations,
        both off the same tree at this single admission so inventory and parse status can never diverge.
        Both the `ParseError` finding and the `OSError` read break mint the `boundary` leaf directly
        against the file stem — a static lint finding the doctor folds to an `UNSUPPORTED` row, never a
        `db.query` boundary or a spawn fault, so the typed `BoundaryFault` family carries it without a
        second fence.

        Returns:
            `Ok(_Sql)` carrying the materialized census when the file parses clean, or
            `Error(BoundaryFault(boundary=(stem, finding)))` for a parse break or an unreadable file.
        """
        try:
            nodes = parse(path.read_text(encoding="utf-8"), dialect=_DIALECT, error_level=ErrorLevel.RAISE)
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
        """The total declared-object count over this file's materialized `objects` census."""
        return sum(self.objects.values())


# --- [OPERATIONS] ----------------------------------------------------------------------


def _cp(basename: str) -> StepArgv:
    """Build one `docker cp` step argv staging a `search/<basename>` dictionary into the container tsearch dir.

    The one parameterized `docker cp` builder the two dictionary rows share: the source resolves off the
    schema file's sibling `search/` directory and the target appends the basename to the `_staged`
    `<container>:<dir>/maghz_` prefix, so a third dictionary is one `_STEPS` row naming its basename
    rather than a second near-identical `lambda cfg, _dsn: ("docker", "cp", ...)` literal.

    Args:
        basename: The `search/` dictionary filename (`synonyms.syn`/`thesaurus.ths`) staged and renamed.

    Returns:
        A `StepArgv` closure resolving the `docker cp <search>/<basename> <staged>maghz_<basename>` argv.
    """
    return lambda cfg, _dsn: ("docker", "cp", str(cfg.database.schema_file.parent / "search" / basename), f"{_staged}{basename}")


async def _grade(step: _Step) -> RuntimeRail[_Step]:
    """Spawn one step under its own wall-clock deadline, returning its outcome rail.

    The subprocess rides the one canonical `runtime.spawn` boundary (`anyio.run_process(check=False)`
    under `guard(RetryClass.PROC)`), so a transient spawn flap replays in the `PROC` budget and the lane
    admits this as a `bare` unit (the spawn already guards; a `retried` admission would nest the retry). A
    completed spawn — any exit code — is `Ok(graded_step)`: a non-zero `psql` exit is graded DATA, not a
    fault. An exhausted spawn escape (a missing binary past the retry budget) rides the `BoundaryFault` on
    the `Error` leg, so `_settled` short-circuits the apply. The whole spawn — and only the spawn — sits
    inside `anyio.move_on_after(step.deadline)`: a tripped deadline cancels the spawn and the post-scope
    sentinel grades the step `FAILED` (`_TIMEOUT_EXIT`), a CONTAINED per-step deadline rather than a lost
    unit, so the enclosing lane carries no deadline of its own and stays purely a concurrency bound.

    Args:
        step: The named command and wall-clock budget to spawn.

    Returns:
        `Ok(graded_step)` for a completed spawn (any exit, including the contained deadline-sentinel), or
        `Error(BoundaryFault)` for an exhausted spawn escape.
    """
    with anyio.move_on_after(step.deadline):
        return (await spawn(step.argv, subject=f"schema.{step.name}", retry_class=RetryClass.PROC)).map(
            lambda run: step.with_exit(run.returncode, run.stderr.decode(errors="replace").strip())
        )
    # `move_on_after` swallowed the cancellation; grade the contained deadline as the timeout sentinel so
    # the receipt stays total over every declared step.
    return Ok(step.with_exit(_TIMEOUT_EXIT, ""))


async def _drain_front(steps: tuple[_Step, ...]) -> Block[RuntimeRail[_Step]]:
    """Drain one concurrent front over the substrate lane, reprojecting the receipt to the step rails.

    One `Admit.of(lambda: _grade(step))` per step rides `drain(_LANE, units)`, so the concurrency bound
    and the `(values, faults)` fan-in are the runtime lane's — never a raw `anyio.create_task_group` with
    an unbounded `start_soon`, the exact shape `cloud._fan_out` composes. Each child returns its full
    `RuntimeRail[_Step]`, so `DrainReceipt.values` carries the graded `_Step`s and `DrainReceipt.faults`
    the exhausted spawn escapes; this reprojects them to one `Block[RuntimeRail[_Step]]` the apply folds
    through `traversed(ABORT)` alongside the sequential front. The `step=step` default binds the loop
    variable so each deferred thunk captures its own step, not the last iterate.

    Args:
        steps: The steps drained concurrently in this front (the lane caps in-flight at `_LANE.capacity`).

    Returns:
        One `RuntimeRail[_Step]` per step — `Ok(graded_step)` from `DrainReceipt.values`, `Error` from
        `DrainReceipt.faults` — completion-ordered (the apply re-orders off the step `name`).
    """
    units = Block.of_seq(Admit.of(lambda step=step: _grade(step)) for step in steps)
    receipt: DrainReceipt[object] = await drain(_LANE, units)
    graded = receipt.values.choose(lambda value: Some(value) if isinstance(value, _Step) else Nothing)
    return graded.map(Ok).append(receipt.faults.map(Error))


async def _front_sequential(steps: tuple[_Step, ...]) -> Block[RuntimeRail[_Step]]:
    """Run a dependent front strictly in order, each step awaited before the next, returning its rails.

    `schema` then `routines` then `cron` cannot fan out: `schema` creates the extensions, the `kb_english`
    configuration, and the tables; `routines` binds its triggers, FKs, and exotic indexes to them; `cron`
    registers against the maintenance DB after those exist. So each awaits `_grade` in declaration order —
    the same per-step spawn/deadline body the concurrent front drains, with no lane because a hard
    sequential dependency is an in-order `await`, not a bounded fan-out (the concurrency owner governs
    concurrent units, never dependent steps). Declaration order IS completion order here.

    Args:
        steps: The dependent steps run strictly in declaration order.

    Returns:
        One `RuntimeRail[_Step]` per step in declaration order.
    """
    return Block.of_seq([await _grade(step) for step in steps])


def _settled(graded: Block[_Step]) -> Envelope:
    """Project the ABORT-folded graded steps to the apply envelope, in `_STEPS` declaration order.

    The concurrent front yields completion order, so the steps re-order off their `name` into `_STEPS`
    declaration order; `exits` then folds one code per step in that order. A non-zero `psql` exit is
    graded DATA: `Status.fold` grades the apply `FAILED` and one `Row` reports each non-zero step (its
    stderr or the bare exit). A clean replay is `OK` with no rows and no DDL mutation.

    Args:
        graded: The graded steps the ABORT fold recovered (every step reached, no spawn fault).

    Returns:
        The apply `Envelope` — `OK` when all steps exit zero, else `FAILED` with one row per non-zero step.
    """
    by_name = {step.name: step for step in graded}
    ordered = tuple(by_name[name] for name in _STEPS if name in by_name)
    exits = tuple(step.code for step in ordered)
    status = Status.fold(Status.OK if code == 0 else Status.FAILED for code in exits)
    rows = tuple(Row(key=step.name, text=step.stderr or f"exit {step.code}") for step in ordered if step.code != 0)
    return completed(status, SchemaDetail(op=SchemaOp.APPLY, exits=exits), rows=rows)


async def _apply(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Idempotent five-step schema apply on the rail: stage the dictionaries concurrently, then apply schema, routines, cron.

    Resolves the `_STEPS` policy rows into the concurrent and sequential `_Step` fronts, drains the
    concurrent front over the substrate lane and awaits the sequential front in order, then folds every
    step's outcome rail through `traversed(ABORT)`. The two fronts run strictly in sequence —
    `schema`/`routines`/`cron` after `synonyms_cp`/`thesaurus_cp` — because the sequential applies bind to
    the staged dictionaries and to the objects each prior apply creates; within the concurrent front the
    lane fans the dictionary stages out under one `CapacityLimiter`. A genuine spawn fault short-circuits
    the whole apply onto the rail (lowered once at
    the CLI edge) while non-zero `psql` exits ride the `Ok` leg as graded `_Step`s. `_settled` re-orders
    the graded steps into `_STEPS` declaration order off the step `name`, so the receipt's `exits` carry
    one code per step in declaration order regardless of completion order. A replay produces no errors and
    no DDL mutations.

    Args:
        cfg: The validated settings owning the DSN and the schema/routines/cron file paths.

    Returns:
        `Ok(completed(...))` carrying the apply receipt — `OK` when all steps exit zero, `FAILED` with the
        non-zero exit rows (including any deadline-tripped step) — or `Error(BoundaryFault)` when a step
        binary cannot be spawned past the `PROC` retry budget.
    """
    concurrent, sequential = _resolve(cfg, str(cfg.database.dsn))
    rails = (await _drain_front(concurrent)).append(await _front_sequential(sequential))
    return traversed(rails, by=Disposition.ABORT).map(_settled)


async def _doctor(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Fold the declarative-object census off the parsed SQL files, then probe the extension census, on the rail.

    The static plane parses the three SQL files into `_Sql` AST owners through `traversed(PARTITION)`:
    every file is linted and the materialized census reads off each that parses, a syntax break landing as
    an `UNSUPPORTED` finding row WITHOUT aborting the probe (a static finding is a reportable defect, not a
    boundary breach). The per-kind object tally sums across the parsed files (each carries its own frozen
    `objects` census, materialized once at `of`) onto the `SchemaDetail` receipt, and one row per file
    reports its `<n> objects, <m> commands` inventory. The connectivity probe is composed as a flat `.map`
    over the one `BoundaryFault` rail — a clean probe carries its extension census on the `Ok` leg and a
    `db.query` boundary fault propagates in place (lifted once inside `db.py`), exactly as `ledger.query`
    and the `sync` DIFF read do. The live `pg_extension` census then folds through the `profile`
    `census_diff` — the extension analog of the `mcp validate` placeholder-coverage gate: a declared-but-
    absent or installed-but-undeclared extension grades the doctor `FAILED` and rides a `census:<name>` drift
    row, so a profile/DB skew is a reported defect. `run` returns the rail unprojected so the CLI `lower`
    seam collapses any surviving `Error(BoundaryFault)` to a `fault` envelope once, at the edge.

    Args:
        cfg: The validated settings owning the DSN and the schema/routines/cron file paths.

    Returns:
        `Ok(completed(...))` with one row per file inventory, one finding row per parse break, one row per
        installed extension, and one `census:<name>` row per catalog/DB drift — `FAILED` on any census drift,
        else `UNSUPPORTED` when a file fails to parse, else `OK` — carrying the summed object census on the
        receipt; or `Error(BoundaryFault)` lifted from the connectivity probe.
    """
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
    """Parse each declarative SQL file under the PostgreSQL plane into its `_Sql` AST-owner rail.

    The three files map through `_Sql.of`; the doctor folds the resulting block through
    `traversed(PARTITION)` so every file is linted — its census collected on the `Ok` leg, its parse/read
    break partitioned onto the `Error` leg as a `boundary` finding — never short-circuited.

    Args:
        cfg: The validated settings owning the schema/routines/cron file paths.

    Returns:
        One `RuntimeRail[_Sql]` per file in declaration order: `Ok(_Sql)` carrying the parsed AST, or
        `Error(BoundaryFault(boundary=(stem, finding)))` for a parse or read break.
    """
    files = (cfg.database.schema_file, cfg.database.routines_file, cfg.database.cron_file)
    return Block.of_seq(_Sql.of(path) for path in files)


# --- [TABLES] --------------------------------------------------------------------------

# The apply step policy: one row per step naming its argv builder (applied to the settings and resolved
# DSN at plan time), its wall-clock deadline, and whether it joins the concurrent front. Declaration
# order is the receipt order: synonyms_cp, thesaurus_cp run concurrently; schema, routines, cron run
# sequentially after, in that order. A third dictionary is one `_cp("<name>")` row, a fourth `psql` file
# one `psql` lambda row — never a hand-built `_Step(...)` literal threaded through the runner. The
# dictionary rows share the one `_cp` builder; the `psql` builders bind the DSN (`schema`/`routines`
# against the ledger, `cron` against the maintenance DB) so the runner spawns a fully-resolved command and
# the front partition is data off the concurrency flag.
_STEPS: frozendict[str, tuple[StepArgv, float, bool]] = frozendict({
    "synonyms_cp": (_cp("synonyms.syn"), 30.0, True),
    "thesaurus_cp": (_cp("thesaurus.ths"), 30.0, True),
    "schema": (lambda cfg, dsn: ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.schema_file)), 120.0, False),
    "routines": (lambda cfg, dsn: ("psql", dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.routines_file)), 120.0, False),
    "cron": (lambda cfg, _dsn: ("psql", cfg.database.maintenance_dsn, "-v", "ON_ERROR_STOP=1", "-f", str(cfg.database.cron_file)), 60.0, False),
})

# op -> its apply/doctor builder. The key set equals `SchemaOp` exactly, so `run`'s subscription is
# total; each builder owns its own status fold, rows, and rail leg. A new verb is one case plus one row.
_BUILD: frozendict[SchemaOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]] = frozendict({
    SchemaOp.APPLY: _apply,
    SchemaOp.DOCTOR: _doctor,
})


# --- [COMPOSITION] ---------------------------------------------------------------------

# The concurrent-front lane: the substrate-memoised `CapacityLimiter` keyed on this frozen `LanePolicy`
# identity bounds the in-flight `docker cp`/`psql` spawns at `len(_STEPS)` (every step admits cleanly even
# if the whole table joined one front). No `deadline` — each step self-bounds inside `_grade`'s
# `move_on_after`, so the lane is purely the concurrency bound, never a second timeout escaping the front.
_LANE: LanePolicy = LanePolicy(capacity=len(_STEPS))


def _resolve(cfg: MaghzSettings, dsn: str) -> tuple[tuple[_Step, ...], tuple[_Step, ...]]:
    """Resolve the `_STEPS` policy rows into the concurrent and sequential `_Step` fronts in declaration order.

    One pass over `_STEPS` builds each `_Step` paired with its concurrency flag, then `Block.partition`
    splits the concurrent front from the sequential one in declaration order — never a second `_STEPS`
    scan rebuilding a name->flag side map.

    Returns:
        A `(concurrent, sequential)` pair of step tuples, each in `_STEPS` declaration order.
    """
    flagged = Block.of_seq(
        (_Step(name=name, argv=build(cfg, dsn), deadline=deadline), concurrent) for name, (build, deadline, concurrent) in _STEPS.items()
    )
    concurrent, sequential = flagged.partition(itemgetter(1))
    return tuple(step for step, _ in concurrent), tuple(step for step, _ in sequential)


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: SchemaOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one schema verb by `op` on the domain rail, dispatching through the total `_BUILD` table.

    `structlog.contextvars.bind_contextvars` scopes the rail/op facts once at entry — the sole
    cross-cutting concern, a single bind rather than an `@aspect`, the same seam `sync`/`cloud`/`n8n`
    open. `_BUILD` is total over `SchemaOp`, so the dispatch is a direct subscription with no `match`/
    `assert_never` guard. The returned `RuntimeRail[Envelope]` is the domain-internal contract; the CLI
    handler lowers it to the stdout `Envelope` through the `runtime.lower` seam, so a boundary fault is
    projected once, at the edge.

    Args:
        op: The schema verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings owning the DSN and the schema/routines/cron file paths.

    Returns:
        The rail the selected builder produced — `Ok(Envelope)` carrying a completed apply/doctor
        receipt, or `Error(BoundaryFault)` from the apply spawn fence.
    """
    structlog.contextvars.bind_contextvars(rail="schema", op=op.value)
    return await _BUILD[op](cfg)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["SchemaDetail", "SchemaOp", "run"]
