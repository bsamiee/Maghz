"""Ledger rail: one polymorphic read over the maghz second-brain ledger, carried on the rail.

A single `query` entrypoint discriminates on a closed `Kind` vocabulary; each kind names one
statement in the `_SQL` table, so the SQL is data, never a branch ladder. The key set of `_SQL`
equals `Kind` exactly, so `_SQL[kind]` direct subscription is total — `match kind` is exhaustive
and closes on `assert_never`, never a missing-kind leg. Every kind folds its `QueryResult` into
bounded `Row`s through one projector, and the row count drives the `OK`/`EMPTY` outcome. The DB
boundary's `DbFault` lifts in place onto the domain-internal `RuntimeRail[Envelope]` through
`BoundaryFault(boundary=(op, message))`; `query` returns that rail unprojected so the CLI handler's
`project` seam lowers the single surviving `Error(BoundaryFault)` to a `fault` envelope once, at the
edge, exactly as the schema and sync rails do.
"""

from enum import StrEnum
from typing import assert_never

from expression import Error, Ok, Result
from frozendict import frozendict

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.db import QueryResult
from admin.runtime import BoundaryFault, RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class Kind(StrEnum):
    """The closed set of ledger projections `query` discriminates on."""

    COVERAGE = "coverage"
    GAPS = "gaps"
    STALE = "stale"
    NEXT = "next"
    OWNER = "owner"


# --- [MODELS] --------------------------------------------------------------------------


class LedgerDetail(Detail, frozen=True, tag="ledger"):
    """Which projection ran and how many rows it returned."""

    kind: Kind
    count: int


# --- [TABLES] --------------------------------------------------------------------------

# kind -> one SQL projection over the ledger. Each statement yields two text columns
# (key, text) so the single row projector applies uniformly; never branch per kind. The key
# set equals `Kind` exactly, so `query`'s `_SQL[kind]` subscription is total — no missing key.
_SQL: frozendict[Kind, str] = frozendict({
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


# --- [ENTRY] ---------------------------------------------------------------------------


async def query(kind: Kind, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one ledger projection by `kind` on the domain rail, folding its rows into a bounded report.

    The statement is selected by total `_SQL[kind]` subscription — `match kind` is exhaustive over
    the closed `Kind` vocabulary, so there is no missing-kind leg. A DB-boundary `DbFault` lifts in
    place onto the `BoundaryFault` rail and short-circuits; `query` returns the rail unprojected so
    the CLI handler's `project` seam lowers any surviving `Error(BoundaryFault)` to a `fault`
    envelope once, at the edge, exactly as the schema and sync rails do.

    Args:
        kind: The ledger projection to run; selects one statement from the `_SQL` table.
        cfg: The validated settings owning the DSN used for the projection query.

    Returns:
        `Ok(completed(...))` carrying the projected rows (`OK`) or no rows (`EMPTY`), or
        `Error(BoundaryFault)` lifted from the database boundary.
    """
    match kind:
        case Kind.COVERAGE | Kind.GAPS | Kind.STALE | Kind.NEXT | Kind.OWNER:
            match await db.query(_SQL[kind], cfg):
                case Result(tag="ok", ok=QueryResult(rows=result_rows)):
                    rows = tuple(Row(key=str(key), text=str(text)) for key, text in result_rows)
                    status = Status.OK if rows else Status.EMPTY
                    return Ok(completed(status, LedgerDetail(kind=kind, count=len(rows)), rows=rows))
                case Result(error=dbfault):
                    return Error(BoundaryFault(boundary=(dbfault.op, dbfault.message)))
        case unreachable:
            assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Kind", "LedgerDetail", "query"]
