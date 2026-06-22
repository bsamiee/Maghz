"""Sync rail: one polymorphic verb reconciling canonical concepts with their Heptabase cards.

A single `run` entrypoint discriminates on the presence of `concept`: absent selects DIFF,
present selects GENERATE. DIFF reads the drift ledger (cards whose `drift_status` left `synced`,
or whose concept vanished) and cross-checks it against the live Heptabase card census via the
`heptabase` CLI. GENERATE reads a concept's canonical content from the ledger and materializes a
new Heptabase note card from it. `_diff`/`_generate` ride the domain-internal `RuntimeRail[Envelope]`
and short-circuit the first boundary fault; `run` returns that rail unprojected so the CLI handler's
`project` seam lowers the single surviving `Error(BoundaryFault)` to a `fault` envelope once, at the
edge, exactly as the schema rail does. Both boundaries fold to one `BoundaryFault` rail: the DB
boundary's `DbFault` lifts in place through `BoundaryFault(boundary=(op, message))`, and the
`heptabase` CLI fence rides `async_boundary('heptabase', ...)` so the typed `resource`/`deadline`/
`boundary` discrimination — and its retry receipts — survive to the projection rather than collapsing
to a stringly-typed carrier.
"""

import anyio
from expression import Error, Ok, Result
import msgspec

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.db import QueryResult
from admin.runtime import async_boundary, boundary, BoundaryFault, guard, RetryClass, RuntimeRail
from admin.settings import MaghzSettings


# --- [MODELS] --------------------------------------------------------------------------


class SyncDetail(Detail, frozen=True, tag="sync"):
    """Which sync verb ran, the drift count, and the live Heptabase card total."""

    op: str
    drift: int = 0
    card_total: int | msgspec.UnsetType = msgspec.UNSET
    card_id: str | msgspec.UnsetType = msgspec.UNSET


class _CardList(msgspec.Struct, frozen=True, gc=False):
    """The `heptabase card list` envelope: only the total is load-bearing for the cross-check."""

    total: int = 0


class _CardRef(msgspec.Struct, frozen=True, gc=False):
    """The `heptabase note create` receipt."""

    id: str
    title: str = ""


# --- [BOUNDARIES] ----------------------------------------------------------------------

# One decoder per heptabase boundary shape, bound to its struct so the schema is resolved once
# at import rather than per invocation; the decode escape rides the canonical `boundary` fence.
_CARD_LIST_DECODER = msgspec.json.Decoder(type=_CardList)
_CARD_REF_DECODER = msgspec.json.Decoder(type=_CardRef)


# --- [OPERATIONS] ----------------------------------------------------------------------


async def _heptabase[T: msgspec.Struct](decoder: msgspec.json.Decoder[T], *argv: str) -> RuntimeRail[T]:
    """Run a `heptabase` CLI verb and decode its stdout through `decoder`, on the boundary rail.

    Args:
        decoder: The pre-built msgspec decoder for the verb's JSON stdout shape.
        argv: The `heptabase` subcommand and its arguments.

    Returns:
        `Ok(T)` on a zero exit with decodable stdout, or `Error(BoundaryFault)` for a spawn escape,
        a non-zero exit, or a malformed/empty payload — every CLI failure on one typed rail, so the
        `resource`/`deadline` discrimination from the spawn fence survives to the CLI projection.
    """
    # The heptabase CLI spawn fence routes through the canonical resilience boundary:
    # `guard(RetryClass.PROC)` retries transient spawn flaps, and `async_boundary('heptabase', ...)`
    # lifts any surviving spawn escape to the typed `BoundaryFault` rail (resource/deadline/boundary).
    # The non-zero-exit leg mints a `boundary` leaf against the same `heptabase` subject; the decode
    # leg rides the synchronous `boundary` fence, so a malformed/empty payload lifts through the one
    # `CLASSIFY` authority (DecodeError/ValidationError -> `boundary`) rather than a hand-rolled catch.
    match await async_boundary("heptabase", lambda: guard(RetryClass.PROC)(anyio.run_process, ["heptabase", *argv], check=False)):
        case Result(tag="ok", ok=run) if run.returncode == 0:
            return boundary("heptabase", lambda: decoder.decode(run.stdout))
        case Result(tag="ok", ok=run):
            detail = run.stderr.decode(errors="replace").strip() or f"{' '.join(argv)} exit {run.returncode}"
            return Error(BoundaryFault(boundary=("heptabase", detail)))
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _diff(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Report drifted/orphaned cards and cross-check the live Heptabase card total, on the rail.

    The ledger read and the census cross-check ride one `BoundaryFault` rail: a DB fault lifts in
    place and short-circuits before the `heptabase` CLI ever spawns, and a CLI fault rides the same
    rail. `run` returns the rail unprojected so the CLI `project` seam lowers any surviving
    `Error(BoundaryFault)` to a `fault` envelope once, at the edge.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.

    Returns:
        `Ok(completed(OK))` with one row per drifted card (`EMPTY` when none), annotated with the
        live card total; or `Error(BoundaryFault)` from the DB or CLI boundary.
    """
    sql = (
        "select card.card_id as key, "
        "card.drift_status || ': ' || coalesce(concept.canonical_name::text, '<orphaned>') as text "
        "from card left join concept on concept.id = card.concept_id "
        "where card.drift_status <> 'synced' or concept.id is null "
        "order by card.drift_status, card.card_id"
    )
    match await db.query(sql, cfg):
        case Result(tag="ok", ok=QueryResult(rows=drift_rows)):
            rows = tuple(Row(key=str(card_id), text=str(text)) for card_id, text in drift_rows)
            return (await _heptabase(_CARD_LIST_DECODER, "card", "list", "--card-types", "note", "--limit", "1")).map(
                lambda census: completed(
                    Status.OK if rows else Status.EMPTY, SyncDetail(op="diff", drift=len(rows), card_total=census.total), rows=rows
                )
            )
        case Result(error=dbfault):
            return Error(BoundaryFault(boundary=(dbfault.op, dbfault.message)))


async def _generate(cfg: MaghzSettings, concept: str) -> RuntimeRail[Envelope]:
    """Materialize a Heptabase note card from one concept's canonical content, on the rail.

    The ledger read lifts a DB fault in place and short-circuits before the `heptabase` CLI spawns;
    an unknown concept folds to a `SKIP` envelope on the `Ok` leg (a found, empty result is not a
    fault). `run` returns the rail unprojected so the CLI `project` seam lowers any surviving
    `Error(BoundaryFault)` to a `fault` envelope once, at the edge.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.
        concept: The `canonical_name` of the concept to render into a card.

    Returns:
        `Ok(completed(OK))` carrying the new card id, `Ok(completed(SKIP))` when the concept is
        unknown, or `Error(BoundaryFault)` from the DB or CLI boundary.
    """
    sql = "select '# ' || coalesce(title, '') || E'\\n\\n' || coalesce(body, '') from concept where canonical_name = :name"
    match await db.query(sql, cfg, name=concept):
        case Result(tag="ok", ok=QueryResult(rows=((markdown, *_), *_))) if markdown:
            return (await _heptabase(_CARD_REF_DECODER, "note", "create", "--content", str(markdown))).map(
                lambda ref: completed(Status.OK, SyncDetail(op="generate", card_id=ref.id))
            )
        case Result(tag="ok"):
            return Ok(completed(Status.SKIP, SyncDetail(op="generate"), notes=(f"no content for concept {concept!r}",)))
        case Result(error=dbfault):
            return Error(BoundaryFault(boundary=(dbfault.op, dbfault.message)))


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(cfg: MaghzSettings, /, *, concept: str | None = None) -> RuntimeRail[Envelope]:
    """Reconcile concepts with Heptabase on the domain rail, selecting DIFF or GENERATE by `concept` arity.

    Both verbs ride the domain-internal `RuntimeRail[Envelope]`; the CLI handler lowers it to the
    stdout `Envelope` through the `project` seam, so the single surviving `Error(BoundaryFault)` is
    projected once, at the edge, never inline — the same contract the schema rail exposes.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.
        concept: When `None`, run DIFF (drift census); when a `canonical_name`, run GENERATE
            (materialize that concept's card).

    Returns:
        The DIFF or GENERATE rail — `Ok(Envelope)` carrying the sync receipt, or `Error(BoundaryFault)`
        from the DB or CLI boundary.
    """
    return await (_diff(cfg) if concept is None else _generate(cfg, concept))


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["SyncDetail", "run"]
