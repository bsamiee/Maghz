"""Sync rail: one polymorphic verb reconciling canonical concepts with their Heptabase cards.

A single `run` entrypoint discriminates on the presence of `concept` — absent selects `SyncOp.DIFF`,
present selects `SyncOp.GENERATE` — then routes that verb through the total `_BUILD` table. DIFF reads
the drift ledger (cards whose `drift_status` left `synced`, or whose concept vanished) and cross-checks
it against the live Heptabase `card list` census; GENERATE reads a concept's canonical content from the
ledger and materializes a Heptabase `note create` card from it. `_diff`/`_generate` ride the
domain-internal `RuntimeRail[Envelope]` and short-circuit the first boundary fault; `run` returns the
rail unprojected so the CLI handler's `runtime.lower` seam collapses the single surviving
`Error(BoundaryFault)` to a `fault` envelope once, at the edge.

Both boundaries fold to one `BoundaryFault` rail with no per-rail carrier: `db.query` already carries it
(the lift happens once inside `db.py`), so a DB fault propagates in place, and every `heptabase` CLI verb
rides the substrate `runtime.spawn` boundary (`anyio.run_process(check=False)` under
`guard(RetryClass.PROC)`, lifting the exhausted-retry escape once) — `_heptabase` composes one
`spawn(...).bind(_graded)` over that boundary, the pure `_graded` exit projection decoding stdout through
the synchronous `boundary` fence on a zero exit and minting the `boundary` leaf on any other, exactly the
`cloud`/`n8n` `_graded` shape; the substrate `Result.bind` short-circuits a spawn fault in place rather
than a hand-rolled `Error` pass-through, so the spawn flap/retry/lift chain is owned by the substrate and
this rail composes it rather than re-deriving it.
`_BUILD` is total over `SyncOp`, so the verb dispatch is a direct subscription with no `match`/
`assert_never` ceremony around an already-exhaustive `frozendict` — the same shape `schema`/`cloud`/`n8n`
expose. `structlog` binds the rail/op facts once at entry, the sole cross-cutting concern.
"""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from subprocess import CompletedProcess  # noqa: S404 - the graded spawn result type this rail reads, never spawned here
from typing import Final

from expression import Error, Ok, Result
from frozendict import frozendict
import msgspec
import structlog

from admin import db
from admin.core import completed, Detail, Envelope, Row, Status
from admin.db import QueryResult
from admin.runtime import boundary, BoundaryFault, RetryClass, RuntimeRail
from admin.runtime.rails import spawn
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class SyncOp(StrEnum):
    """The closed verb vocabulary `run` discriminates on by `concept` arity; one `_BUILD` row each.

    The set is shaped to absorb a future reconciliation verb (a PRUNE that retires the orphaned cards
    DIFF surfaces, a BACKFILL that GENERATEs every unmaterialized concept) as one new member plus one
    `_BUILD` row, every consumer untouched — never a parallel verb surface. `run` maps the `concept`
    arity onto a member rather than branching on it inline, so the arity discriminant and the verb table
    are the one dispatch.
    """

    DIFF = "diff"  # drift census + live Heptabase card cross-check (no concept)
    GENERATE = "generate"  # materialize one concept's canonical content into a note card


# --- [CONSTANTS] -----------------------------------------------------------------------

# The `card list` page bound: the documented `--limit` ceiling (max 100), so one decoded page carries the
# whole live-note census the DIFF cross-check reports — the sync analog of `n8n._LIST_LIMIT`.
_LIST_LIMIT: Final[str] = "100"


# --- [MODELS] --------------------------------------------------------------------------


class SyncDetail(Detail, frozen=True, tag="sync"):
    """Which sync verb ran, the drift partition, and the Heptabase census/created-card evidence.

    DIFF carries the `drifted`/`orphaned` partition of the ledger read (a card whose `drift_status` left
    `synced` vs a card whose concept vanished) and the live `card_total` census count; GENERATE carries
    the new `card_id`/`card_title`. Every slot a given verb never touches rides `msgspec.UNSET` so it
    encodes ABSENT on the wire rather than `null`, preserving the verb distinction for downstream agent
    consumers — DIFF carries no `card_id`, GENERATE no `card_total`.
    """

    op: SyncOp
    drifted: int | msgspec.UnsetType = msgspec.UNSET
    orphaned: int | msgspec.UnsetType = msgspec.UNSET
    card_total: int | msgspec.UnsetType = msgspec.UNSET
    card_id: str | msgspec.UnsetType = msgspec.UNSET
    card_title: str | msgspec.UnsetType = msgspec.UNSET


class _Card(msgspec.Struct, frozen=True, gc=False):
    """One heptabase card's identity evidence — its `id` and `title` — the one shape both boundaries carry.

    The `card list` page rows and the `note create` receipt are the same card-identity concept (the only
    slots either boundary spends are the `id` and the `# heading` first-line `title`), so one owner sources
    the DIFF census rows and the GENERATE receipt rather than two byte-identical structs; the unmodelled
    `objectType`/`createdAt`/... wire keys ride the default `forbid_unknown_fields=False` and are ignored.
    """

    id: str
    title: str = ""


class _CardList(msgspec.Struct, frozen=True, gc=False):
    """The `heptabase card list` envelope: the paginated `total` plus the live `results` census rows.

    `total` is the load-bearing cross-check count; `results` carries the page of live note cards so the
    DIFF receipt reports which cards exist alongside the count, off one decode of the one CLI payload.
    """

    total: int = 0
    results: tuple[_Card, ...] = ()


# --- [SERVICES] ------------------------------------------------------------------------

# One decoder per `heptabase` boundary shape, bound to its struct so the schema is resolved once at
# import rather than per invocation; the decode escape rides the canonical synchronous `boundary` fence.
# Both the `card list` page and the `note create` receipt project to the one `_Card`/`_CardList` owner.
_CARD_LIST_DECODER: Final[msgspec.json.Decoder[_CardList]] = msgspec.json.Decoder(type=_CardList)
_CARD_DECODER: Final[msgspec.json.Decoder[_Card]] = msgspec.json.Decoder(type=_Card)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _graded[T: msgspec.Struct](run: CompletedProcess[bytes], decoder: msgspec.json.Decoder[T], argv: tuple[str, ...]) -> RuntimeRail[T]:
    """Project one completed `heptabase` exit to the typed rail: a zero exit decodes stdout, any other faults.

    The pure exit grade over the `CompletedProcess` `spawn` returns, the house idiom every subprocess rail
    shares (`cloud._graded`/`n8n._graded`). A zero exit decodes stdout through the synchronous `boundary`
    fence, so a malformed/empty payload lifts via the one `CLASSIFY` authority (`DecodeError`/
    `ValidationError` -> `boundary`); any non-zero exit mints `Error(BoundaryFault(boundary=...))` directly,
    carrying the `heptabase` subject and the decoded stderr (or the argv-and-code fallback). The spawn-flap
    retry and the exhausted-escape lift stay owned by `runtime.spawn`; the caller's `.bind` threads this
    grade only on the `Ok(CompletedProcess)` leg, so a spawn escape short-circuits without a hand-rolled
    pass-through arm.

    Returns:
        `Ok(T)` on a zero exit with decodable stdout, or `Error(BoundaryFault)` for a non-zero exit or a
        malformed/empty payload.
    """
    if run.returncode == 0:
        return boundary("heptabase", lambda: decoder.decode(run.stdout))
    detail = run.stderr.decode(errors="replace").strip() or f"{' '.join(argv)} exit {run.returncode}"
    return Error(BoundaryFault(boundary=("heptabase", detail)))


async def _heptabase[T: msgspec.Struct](decoder: msgspec.json.Decoder[T], *argv: str) -> RuntimeRail[T]:
    """Run a `heptabase` CLI verb through the substrate spawn boundary and grade its exit, on the rail.

    `spawn` owns the `anyio.run_process(check=False)` + `guard(RetryClass.PROC)` spawn-flap retry and the
    exhausted-escape lift, so this leg composes the one `guard`-stacked spawn call and `.bind`s the pure
    `_graded` exit projection — the substrate `Result.bind` short-circuits a spawn fault in place, so this
    helper never re-mints the `Error` leg by hand. Every CLI failure therefore rides one typed
    `BoundaryFault` rail to the projection through the same `spawn(...).bind(_graded)` shape `cloud`/`n8n`
    expose.

    Args:
        decoder: The pre-built msgspec decoder for the verb's JSON stdout shape.
        argv: The `heptabase` subcommand and its arguments.

    Returns:
        `Ok(T)` on a zero exit with decodable stdout, or `Error(BoundaryFault)` for a spawn escape, a
        non-zero exit, or a malformed/empty payload.
    """
    return (await spawn(("heptabase", *argv), subject="heptabase", retry_class=RetryClass.PROC)).bind(
        lambda run: _graded(run, decoder, argv)
    )


async def _diff(cfg: MaghzSettings, _concept: str | None) -> RuntimeRail[Envelope]:
    """Report drifted/orphaned cards and cross-check the live Heptabase note census, on the rail.

    The ledger read and the census cross-check ride one `BoundaryFault` rail: a DB fault lifts in place
    and short-circuits before the `heptabase` CLI ever spawns, and a CLI fault rides the same rail. The
    orphan partition keys on the `drift_status = 'orphaned'` enum value — the modeled orphan signal, not a
    dangling FK: `card.concept_id` is `NOT NULL ... ON DELETE CASCADE`, so a vanished concept cascade-
    deletes its card and `concept.id is null` can never fire, leaving the enum value the only honest
    discriminant. So `is_orphaned` reads the status, the LEFT JOIN supplies the canonical name for the row
    text, and the receipt partitions orphaned vs drifted off one query; the census `results` page joins as
    live-card rows alongside the drift rows. `run` returns the rail unprojected so the CLI `runtime.lower`
    seam collapses any surviving `Error(BoundaryFault)` to a `fault` envelope once, at the edge.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.
        _concept: Unbound for DIFF; the `_BUILD` row shape is uniform across verbs and the arity
            discriminant routes a present concept to GENERATE before this builder runs.

    Returns:
        `Ok(completed(OK))` with one row per non-synced card and one per live note card (`EMPTY` when no
        drift), the receipt carrying the drifted/orphaned partition and the live card total; or
        `Error(BoundaryFault)` from the DB or CLI boundary.
    """
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
            return (await _heptabase(_CARD_LIST_DECODER, "card", "list", "--card-types", "note", "--limit", _LIST_LIMIT)).map(
                lambda census: completed(
                    Status.OK if drift else Status.EMPTY,
                    SyncDetail(op=SyncOp.DIFF, drifted=len(drift) - orphaned, orphaned=orphaned, card_total=census.total),
                    rows=(*drift, *(Row(key=card.id, text=f"live: {card.title or '<untitled>'}") for card in census.results)),
                )
            )
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _generate(cfg: MaghzSettings, concept: str | None) -> RuntimeRail[Envelope]:
    """Materialize a Heptabase note card from one concept's canonical content, on the rail.

    The ledger read lifts a DB fault in place and short-circuits before the `heptabase` CLI spawns; an
    unknown concept folds to a `SKIP` envelope on the `Ok` leg (a found, empty result is not a fault).
    The `note create` receipt carries the new card id and the returned title. `run` returns the rail
    unprojected so the CLI `runtime.lower` seam collapses any surviving `Error(BoundaryFault)` once.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.
        concept: The `canonical_name` of the concept to render into a card; always present for GENERATE
            (the arity discriminant routes a `None` concept to DIFF before this builder runs).

    Returns:
        `Ok(completed(OK))` carrying the new card id and title, `Ok(completed(SKIP))` when the concept
        is unknown, or `Error(BoundaryFault)` from the DB or CLI boundary.
    """
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


# --- [TABLES] --------------------------------------------------------------------------

# verb -> its reconciliation builder on the shared `(cfg, concept) -> RuntimeRail[Envelope]` rail. The
# key set equals `SyncOp` exactly, so `run`'s `_BUILD[op]` subscription is total — a new verb is one
# member plus one row, never a `concept is None` branch threaded through the body. The uniform row shape
# carries `concept` to both builders; `_diff` leaves it unbound and `_generate` reads the
# arity-guaranteed value, so the one table dispatches both arity modalities.
_BUILD: Final[frozendict[SyncOp, Callable[[MaghzSettings, str | None], Awaitable[RuntimeRail[Envelope]]]]] = frozendict({
    SyncOp.DIFF: _diff,
    SyncOp.GENERATE: _generate,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(cfg: MaghzSettings, /, *, concept: str | None = None) -> RuntimeRail[Envelope]:
    """Reconcile concepts with Heptabase on the domain rail, selecting the verb by `concept` arity.

    The `concept` arity maps onto a `SyncOp` member (`None` -> DIFF, present -> GENERATE) routed through
    the total `_BUILD` table — the arity discriminant and the verb dispatch are the one subscription, no
    `match`/`assert_never` ceremony around an exhaustive `frozendict`. `structlog.contextvars` scopes the
    rail/op facts once at entry, the sole cross-cutting concern. Both verbs ride the domain-internal
    `RuntimeRail[Envelope]`; the CLI handler lowers it to the stdout `Envelope` through the
    `runtime.lower` seam, so the single surviving `Error(BoundaryFault)` is projected once, at the edge,
    never inline — the same contract the schema and ledger rails expose.

    Args:
        cfg: The validated settings owning the DSN and the Heptabase CLI reach.
        concept: When `None`, run DIFF (drift census); when a `canonical_name`, run GENERATE
            (materialize that concept's card).

    Returns:
        The DIFF or GENERATE rail — `Ok(Envelope)` carrying the sync receipt, or `Error(BoundaryFault)`
        from the DB or CLI boundary.
    """
    op = SyncOp.DIFF if concept is None else SyncOp.GENERATE
    structlog.contextvars.bind_contextvars(rail="sync", op=op.value)
    return await _BUILD[op](cfg, concept)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["SyncDetail", "SyncOp", "run"]
