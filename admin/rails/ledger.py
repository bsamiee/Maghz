"""Ledger rail: one polymorphic read over the maghz second-brain ledger, carried on the rail.

A single `query` entrypoint discriminates on a closed `Kind` vocabulary; each kind names one
`Projection` in the `_SQL` table — a `sqlglot` AST parsed once at import, not a raw string handed to
the driver. The key set of `_SQL` equals `Kind` exactly, so `_SQL[kind]` direct subscription is total
and `query` is a flat `.map` compose with no `match`/`assert_never` leg guarding an exhaustive table.
`_SQL` is DERIVED from the one `_TEXT` correspondence: every projection is parsed through
`parse_one(dialect=POSTGRES, error_level=RAISE)` at module load, so a malformed projection breaks the
import rather than the first query.

`Projection` admits each statement EXACTLY ONCE: `of` parses the AST and materializes every derived
fact off it — the canonical Postgres `sql`, the output `columns`, the source-table census, the
predicate/join `predicates` count, and the column-level `lineage` edges — into frozen fields at import,
because the tree is import-constant and a per-query property recompute (the full `qualify` scope-build a
lineage pass pays) is pure waste. The interior reads stored evidence: `query` reads `projection.sql`
(a field) and `projection.detail(kind, count)` mints the `LedgerDetail` receipt off the same stored
provenance, so the executed statement and its receipt can never diverge and neither is re-derived per
query. `lineage` reaches the deepest provenance primitive `sqlglot` owns — `lineage.lineage(column=None,
tree, ...)` builds every output column's lineage in ONE qualify+scope pass under a shared cross-column
cache (the dual-return form; a per-column call re-parses and re-qualifies each time), the native
`Node.walk` filtered to its downstream-free leaves naming which source column backs each ledger field.

`db.query` already carries the canonical `BoundaryFault` rail (the lift happens once inside `db.py`), so
a DB-boundary fault propagates in place onto `RuntimeRail[Envelope]` and short-circuits; `query` returns
that rail unprojected so the CLI handler's `runtime.lower` seam collapses the single surviving
`Error(BoundaryFault)` to a `fault` envelope once, at the edge, exactly as the schema and sync rails do.
`structlog.contextvars` binds the rail/kind facts once at entry, the sole cross-cutting concern.
"""

from enum import StrEnum

from frozendict import frozendict
import msgspec
from sqlglot import Dialects, ErrorLevel, exp, parse_one
from sqlglot.lineage import lineage
import structlog

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.db import QueryResult
from admin.runtime import RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


type LineageEdge = tuple[str, str]


class Kind(StrEnum):
    """The closed set of ledger projections `query` discriminates on."""

    COVERAGE = "coverage"
    GAPS = "gaps"
    STALE = "stale"
    NEXT = "next"
    OWNER = "owner"


# --- [CONSTANTS] -----------------------------------------------------------------------

# The one dialect the projections parse and re-emit under: the ledger is Postgres (pg8000), so the AST
# round-trip canonicalizes to Postgres rather than a cross-dialect transpile.
_DIALECT = Dialects.POSTGRES
# The predicate/join nodes `Projection` widens over in one `find_all` pass over the AST at admission — the
# filtering surface a projection carries (a `where`/`having`/`qualify` clause or a join), the receipt's
# structural evidence. Each is a direct `Expression` subclass with no shared predicate base, so the tuple
# is the discriminant the single `find_all` spans.
_PREDICATE_NODES: tuple[type[exp.Expression], ...] = (exp.Where, exp.Having, exp.Qualify, exp.Join)


# --- [MODELS] --------------------------------------------------------------------------


class LedgerDetail(Detail, frozen=True, tag="ledger"):
    """Which projection ran, how many rows it returned, and the AST-derived provenance of the statement.

    `count` is the materialized row count; `columns`/`tables`/`predicates`/`lineage` carry the structural
    provenance the `Projection` AST folds at admission — the output projection, the source-table census,
    the filtering/join node count, and the column-level source edges — so a consumer reads which tables a
    kind touches, how it filters, and which source column backs each output column off the typed receipt
    rather than re-parsing the SQL. The provenance fields are minted once by `Projection` and stamped here
    through `Projection.detail`, never re-spelled beside the canonical projection.
    """

    kind: Kind
    count: int
    columns: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    predicates: int = 0
    lineage: tuple[LineageEdge, ...] = ()


class Projection(msgspec.Struct, frozen=True):
    """One ledger projection admitted once: the parsed `sqlglot` AST plus its materialized provenance.

    `of` parses the statement under the Postgres `RAISE` policy (a malformed projection fails the module
    load, not the first query) and derives every fact off the tree at that one admission — `sql` re-emits
    the canonical Postgres statement the driver runs, and `columns`/`tables`/`predicates`/`lineage` fold
    the output projection, source-table census, predicate count, and column-level source edges. The tree
    is import-constant, so these are frozen fields built once rather than per-access properties paying a
    `qualify` scope-build per query; the interior reads `sql` and mints the receipt off the stored
    provenance through `detail`. `tree` is retained as the owning evidence; it is a `sqlglot` AST node
    whose bidirectional parent/child links form reference cycles, so the struct stays GC-tracked.
    """

    tree: exp.Expression
    sql: str
    columns: tuple[str, ...]
    tables: tuple[str, ...]
    predicates: int
    lineage: tuple[LineageEdge, ...]

    @staticmethod
    def of(text: str) -> Projection:
        """Parse one projection to its AST and materialize its provenance, all at this one admission.

        The statement parses under the Postgres `RAISE` policy, then `sql`/`columns`/`tables`/
        `predicates`/`lineage` derive off the tree once: `find_all(exp.Table)` is the source census,
        `find_all(*_PREDICATE_NODES)` the filter/join count, and `lineage(column=None, tree, ...)` the
        deepest provenance primitive — every output column's lineage built in ONE qualify+scope pass under
        the shared cross-column cache (the dual-return form), each output column resolving to its
        downstream-free `Node.walk` leaves so an unqualified `key`/`text` maps to its real physical source
        column rather than a table cross-product. `copy=True` (the `lineage` default) keeps the stored
        tree pristine for the `sql` field re-emit.

        Returns:
            The `Projection` owning the parsed tree and its materialized provenance; raises
            `sqlglot.ParseError` at import on a malformed statement so `_SQL` carries only parseable
            projections.
        """
        tree = parse_one(text, dialect=_DIALECT, error_level=ErrorLevel.RAISE)
        roots = lineage(None, tree, dialect=_DIALECT)
        return Projection(
            tree=tree,
            sql=tree.sql(dialect=_DIALECT),
            columns=tuple(select.alias_or_name for select in tree.selects),
            tables=tuple(sorted({table.name for table in tree.find_all(exp.Table)})),
            predicates=sum(1 for _ in tree.find_all(*_PREDICATE_NODES)),
            lineage=tuple((str(leaf.name), str(out)) for out, root in roots.items() for leaf in root.walk() if not leaf.downstream),
        )

    def detail(self, kind: Kind, count: int) -> LedgerDetail:
        """Mint the `LedgerDetail` receipt off this projection's stored provenance — the single mint.

        The one site that reads the projection's already-materialized
        `columns`/`tables`/`predicates`/`lineage` into the receipt, so the receipt's provenance is the AST
        fold this owner paid once at admission rather than a re-derived parse beside the canonical tree.

        Returns:
            The `LedgerDetail` carrying `kind`, the row `count`, and this projection's structural evidence.
        """
        return LedgerDetail(kind=kind, count=count, columns=self.columns, tables=self.tables, predicates=self.predicates, lineage=self.lineage)


# --- [TABLES] --------------------------------------------------------------------------

# kind -> one SQL projection over the ledger. Each statement yields two text columns (key, text) so the
# single row fold in `query` applies uniformly; never branch per kind. This is the ONE primary
# correspondence — `_SQL` derives its parsed `Projection` table from it, never a second hand-enumerated
# AST map. The key set equals `Kind` exactly, so `_SQL[kind]` subscription is total.
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

# kind -> its parsed `Projection`, DERIVED from `_TEXT` by admitting each statement once at import. The
# `RAISE` policy in `Projection.of` fails the module load on a malformed projection, so a broken
# statement surfaces at import rather than the first query, and the key set stays equal to `Kind`.
_SQL: frozendict[Kind, Projection] = frozendict({kind: Projection.of(text) for kind, text in _TEXT.items()})


# --- [ENTRY] ---------------------------------------------------------------------------


async def query(kind: Kind, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one ledger projection by `kind` on the domain rail, folding its rows into a bounded report.

    The projection is selected by total `_SQL[kind]` subscription — the key set equals `Kind`, so there
    is no missing-kind leg and no `match`/`assert_never` ceremony guarding an exhaustive table. The stored
    `projection.sql` is the canonical Postgres statement `db.query` runs; a DB-boundary fault lifts in
    place onto the `BoundaryFault` rail (lifted once inside `db.py`) and short-circuits, so this is a flat
    `.map` over the rail — the success leg folds the two-column rows and mints the receipt through the
    single `projection.detail` stamp off the stored provenance, the fault leg passes through untouched.
    `query` returns the rail unprojected so the CLI handler's `runtime.lower` seam collapses any surviving
    `Error(BoundaryFault)` to a `fault` envelope once, at the edge, exactly as the schema and sync rails
    do. `structlog.contextvars` binds the rail/kind facts once at entry, the sole cross-cutting concern.

    Args:
        kind: The ledger projection to run; selects one `Projection` from the `_SQL` table.
        cfg: The validated settings owning the DSN used for the projection query.

    Returns:
        `Ok(completed(...))` carrying the projected rows (`OK`) or no rows (`EMPTY`), with the AST-derived
        provenance on the `LedgerDetail` receipt, or `Error(BoundaryFault)` lifted from the database
        boundary.
    """
    structlog.contextvars.bind_contextvars(rail="ledger", kind=kind.value)
    projection = _SQL[kind]

    def _report(result: QueryResult) -> Envelope:
        rows = tuple(Row(key=str(key), text=str(text)) for key, text in result.rows)
        return completed(Status.OK if rows else Status.EMPTY, projection.detail(kind, len(rows)), rows=rows)

    return (await db.query(projection.sql, cfg)).map(_report)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Kind", "LedgerDetail", "LineageEdge", "Projection", "query"]
