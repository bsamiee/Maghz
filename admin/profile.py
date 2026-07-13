"""The typed PostgreSQL extension profile: one catalog owner generating every downstream extension surface.

The single source of truth for the maghz-pg extension set. Before this owner the profile was hand-kept
in four uncoordinated places — the `infra` `shared_preload_libraries` argv, the `image/Dockerfile` apt
list, the `db/schema.sql` `CREATE EXTENSION` prelude, and the `db/cron.sql` pg_cron line — so a profile
edit had to be mirrored four times or drift. Here the `_PROFILE` `frozendict[Extension, ExtensionSpec]`
declares each extension once and the four downstream surfaces are pure projections of it: the Dockerfile
apt block (rows whose `source` is layered, i.e. not the ParadeDB base), the schema prelude (rows whose
`target_db` is `maghz`), the cron pg_cron line (rows whose `target_db` is `postgres`), and the
`shared_preload_libraries` string (rows whose `preload` flag is set, plus the `auto_explain` library that
carries no SQL object). A new extension is one `Extension` case plus one `_PROFILE` row, and every surface
re-renders from it — never a fifth hand-edited site.

`census_diff` is the catalog's verify projection (the `pg_extension`-vs-declared assertion the schema
`doctor` verb folds): it takes the live `pg_extension` census the DB probe returns and reports the
declared-but-absent and installed-but-undeclared sets against the `target_db == maghz` membership, the
extension catalog's live coverage gate. `auto_explain` and `pg_cron`
are excluded from the maghz census by construction — `auto_explain` registers no `pg_extension` row and
`pg_cron` lives only in the `postgres` maintenance DB — so the diff compares the maghz catalog membership
against the maghz `pg_extension` rows exactly.

This module is pure data and pure projection — no rail, no validated-settings handle, and I/O only inside
the `regenerate` seam. The `infra` runner
reads `shared_preload_libraries()` for the container command, and the three committed surfaces are
GENERATED from `schema_prelude()`/`cron_prelude()`/`dockerfile_apt_block()`, so the catalog is imported by
the generator and the runner, never the reverse.
"""

from collections.abc import Callable, Iterable
from enum import StrEnum
from pathlib import Path
import re

from frozendict import frozendict
import msgspec

from admin.settings import EMBED_DIM, EMBED_ENDPOINT, EMBED_MODEL, REPO_ROOT


# --- [TYPES] ---------------------------------------------------------------------------


type _Region = tuple[Path, str, Callable[[], str]]


class Source(StrEnum):
    """Where the extension's binaries come from; the Dockerfile apt fold keys on `is_layered`.

    `PARADEDB_BASE` ships in the `paradedb/paradedb` image (pg_search/vector/pg_ivm/pg_cron and all
    contrib), so it is never apt-installed; `PGDG` and `PIGSTY` are the two layered apt repos the image
    adds. A new repo is one member plus the rows that name it — the apt block folds every non-base source.
    """

    PARADEDB_BASE = "paradedb-base"
    PGDG = "pgdg"
    PIGSTY = "pigsty"

    @property
    def is_layered(self) -> bool:
        """Whether this source is apt-installed in the image build (every source but the ParadeDB base)."""
        return self is not Source.PARADEDB_BASE


class TargetDb(StrEnum):
    """The database the extension is created in; the routines/cron preludes fold on this discriminant.

    `MAGHZ` extensions are created by `routines.sql` against the ledger DB; `POSTGRES` is the lone
    `pg_cron` case, which can inhabit only the `postgres` maintenance DB (its jobs reach `maghz` through
    `cron.schedule_in_database`). `NONE` is the `auto_explain` library — a shared-preload module with no
    `CREATE EXTENSION` form — so it rides the preload string but no `CREATE EXTENSION` prelude.
    """

    MAGHZ = "maghz"
    POSTGRES = "postgres"
    NONE = "none"


class Category(StrEnum):
    """The capability band each extension serves; carried as inventory evidence, not a code discriminant.

    Purely descriptive — the projections key on `source`/`target_db`/`preload`, never on category — so a
    re-banding is one column edit with every generated surface byte-identical. The bands name the retrieval
    triad (`SEARCH`), the embedding egress + queue (`PIPELINE`), the incremental/partition maintenance
    (`MAINTENANCE`), the fuzzy/text dedup stack (`TEXT`), the crypto/containment primitives (`PRIMITIVE`),
    and the observability libraries (`OBSERVABILITY`).
    """

    SEARCH = "search"
    PIPELINE = "pipeline"
    MAINTENANCE = "maintenance"
    TEXT = "text"
    PRIMITIVE = "primitive"
    OBSERVABILITY = "observability"


class Extension(StrEnum):
    """The closed extension vocabulary; `value` is the `CREATE EXTENSION` / `pg_extension.extname` name.

    One member per extension (and per shared-preload library) in the maghz-pg profile; the member value is
    the canonical PostgreSQL extension name the `CREATE EXTENSION` statement and the `pg_extension` census
    use, so a member doubles as its own catalog key and its own wire name. Declaration order is the rendered
    `CREATE EXTENSION` order — `pgmq` precedes the extensions that may `CASCADE`-pull a dependency, and the
    contrib/text members follow the layered ones, matching the dependency-safe apply sequence. A new
    extension is one case here plus one `_PROFILE` row; every downstream surface re-renders from the pair.
    """

    VECTOR = "vector"
    PG_SEARCH = "pg_search"
    PG_IVM = "pg_ivm"
    PG_NET = "pg_net"
    PGMQ = "pgmq"
    PG_JSONSCHEMA = "pg_jsonschema"
    HLL = "hll"
    PG_PARTMAN = "pg_partman"
    HYPOPG = "hypopg"
    PG_TRGM = "pg_trgm"
    UNACCENT = "unaccent"
    FUZZYSTRMATCH = "fuzzystrmatch"
    CITEXT = "citext"
    LTREE = "ltree"
    PGCRYPTO = "pgcrypto"
    BTREE_GIN = "btree_gin"
    BTREE_GIST = "btree_gist"
    PG_STAT_STATEMENTS = "pg_stat_statements"
    TABLEFUNC = "tablefunc"
    PG_CRON = "pg_cron"
    AUTO_EXPLAIN = "auto_explain"  # shared-preload library only, no CREATE EXTENSION / pg_extension row


# --- [CONSTANTS] -----------------------------------------------------------------------

# The committed-artifact paths, anchored on the repo root so `regenerate` is CWD-proof. Each carries a
# `[CATALOG:<tag>] ... [/CATALOG:<tag>]` sentinel region the `regenerate` rewriter replaces with the
# catalog projection, so the four downstream surfaces are GENERATED from `_PROFILE` rather than hand-kept.
_SCHEMA_SQL = REPO_ROOT / "db/schema.sql"
_CRON_SQL = REPO_ROOT / "db/cron.sql"
_ROUTINES_SQL = REPO_ROOT / "db/routines.sql"
_DOCKERFILE = REPO_ROOT / "image/Dockerfile"

# Extensions present in every maghz database outside the curated profile: `plpgsql` is the built-in
# procedural language PostgreSQL installs in every database, and the PostGIS trio ships preinstalled in the
# ParadeDB base image. `census_diff` excludes these from the undeclared-drift set so the schema `doctor`
# flags only a genuine out-of-band install, never the base image's own extensions.
_CENSUS_IGNORE: frozenset[str] = frozenset({"plpgsql", "postgis", "postgis_tiger_geocoder", "postgis_topology"})


# --- [MODELS] --------------------------------------------------------------------------


class ExtensionSpec(msgspec.Struct, frozen=True, gc=False):
    """One extension's full catalog row: provenance, target DB, preload requirement, and apply flags.

    `source` keys the Dockerfile apt fold (a layered source emits one apt line; the base emits none);
    `target_db` keys the routines/cron preludes (a `maghz` row emits a `CREATE EXTENSION`, the lone
    `postgres` row emits the cron pg_cron line, a `none` library emits neither); `preload` keys the
    `shared_preload_libraries` fold; `cascade` appends `CASCADE` to the `CREATE EXTENSION` for an extension
    that pulls a dependency (`pgmq`). `apt_package` is the Debian package basename under the
    `postgresql-18-` prefix, present only for a layered source — the names diverge from the extension name
    (`pg_net` -> `pg-net`, `pg_partman` -> `partman`), so the package basename is declared, not derived.
    `category` is descriptive inventory; no projection keys on it. `gc=False` holds: every field is a
    `str`/`bool`/enum leaf with no container, so no reference cycle can form.
    """

    name: Extension
    category: Category
    source: Source
    target_db: TargetDb
    preload: bool = False
    cascade: bool = False
    apt_package: str = ""

    @property
    def create_statement(self) -> str:
        """The idempotent `CREATE EXTENSION IF NOT EXISTS <name>[ CASCADE];` for a SQL-object extension."""
        return f"CREATE EXTENSION IF NOT EXISTS {self.name.value}{' CASCADE' if self.cascade else ''};"

    @property
    def apt_line(self) -> str:
        """The `postgresql-18-<apt_package>` apt package token a layered extension contributes to the build."""
        return f"postgresql-18-{self.apt_package}"


class CensusDiff(msgspec.Struct, frozen=True, gc=False):
    """The catalog-vs-live `pg_extension` census reconciliation the schema `doctor` verb asserts.

    `missing` names every `target_db == maghz` extension the catalog declares that the live `pg_extension`
    census lacks (an apply gap — the image or `routines.sql` never created it); `undeclared` names every
    installed `pg_extension` row the maghz catalog does not declare (profile drift — an extension created
    out of band). `aligned` is the clean verdict: both empty. The diff is computed against the maghz
    catalog membership only (`auto_explain` registers no row, `pg_cron` lives in `postgres`), so the two
    structural exclusions never read as drift.
    """

    missing: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()

    @property
    def aligned(self) -> bool:
        """Whether the live maghz census matches the declared catalog exactly (no missing, no undeclared)."""
        return not self.missing and not self.undeclared


# --- [TABLES] --------------------------------------------------------------------------

# The one extension catalog: `Extension` -> its full `ExtensionSpec` row. Every downstream surface is a
# pure projection of this map — the Dockerfile apt block (layered rows), the routines `CREATE EXTENSION`
# prelude (`maghz` rows), the cron pg_cron line (`postgres` row), and the `shared_preload_libraries` string
# (`preload` rows) — so the profile is declared exactly once and a new extension is one `Extension` case
# plus one row here. Declaration order is the rendered apply order: ParadeDB-base contrib and the layered
# `pgmq` (which `CASCADE`s) lead, the fuzzy/text/primitive contrib follows, and the two non-maghz members
# (`pg_cron` in `postgres`, the `auto_explain` library) close. The key set equals `Extension` exactly, so
# every projection folds the total catalog with no membership guard.
_PROFILE: frozendict[Extension, ExtensionSpec] = frozendict({
    Extension.VECTOR: ExtensionSpec(name=Extension.VECTOR, category=Category.SEARCH, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.PG_SEARCH: ExtensionSpec(
        name=Extension.PG_SEARCH, category=Category.SEARCH, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ, preload=True
    ),
    Extension.PG_IVM: ExtensionSpec(name=Extension.PG_IVM, category=Category.MAINTENANCE, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.PG_NET: ExtensionSpec(
        name=Extension.PG_NET, category=Category.PIPELINE, source=Source.PIGSTY, target_db=TargetDb.MAGHZ, preload=True, apt_package="pg-net"
    ),
    Extension.PGMQ: ExtensionSpec(
        name=Extension.PGMQ, category=Category.PIPELINE, source=Source.PIGSTY, target_db=TargetDb.MAGHZ, cascade=True, apt_package="pgmq"
    ),
    Extension.PG_JSONSCHEMA: ExtensionSpec(
        name=Extension.PG_JSONSCHEMA, category=Category.PIPELINE, source=Source.PIGSTY, target_db=TargetDb.MAGHZ, apt_package="pg-jsonschema"
    ),
    Extension.HLL: ExtensionSpec(name=Extension.HLL, category=Category.MAINTENANCE, source=Source.PGDG, target_db=TargetDb.MAGHZ, apt_package="hll"),
    Extension.PG_PARTMAN: ExtensionSpec(
        name=Extension.PG_PARTMAN, category=Category.MAINTENANCE, source=Source.PGDG, target_db=TargetDb.MAGHZ, apt_package="partman"
    ),
    Extension.HYPOPG: ExtensionSpec(
        name=Extension.HYPOPG, category=Category.MAINTENANCE, source=Source.PGDG, target_db=TargetDb.MAGHZ, apt_package="hypopg"
    ),
    Extension.PG_TRGM: ExtensionSpec(name=Extension.PG_TRGM, category=Category.TEXT, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.UNACCENT: ExtensionSpec(name=Extension.UNACCENT, category=Category.TEXT, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.FUZZYSTRMATCH: ExtensionSpec(
        name=Extension.FUZZYSTRMATCH, category=Category.TEXT, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ
    ),
    Extension.CITEXT: ExtensionSpec(name=Extension.CITEXT, category=Category.TEXT, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.LTREE: ExtensionSpec(name=Extension.LTREE, category=Category.TEXT, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.PGCRYPTO: ExtensionSpec(name=Extension.PGCRYPTO, category=Category.PRIMITIVE, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.BTREE_GIN: ExtensionSpec(name=Extension.BTREE_GIN, category=Category.PRIMITIVE, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ),
    Extension.BTREE_GIST: ExtensionSpec(
        name=Extension.BTREE_GIST, category=Category.PRIMITIVE, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ
    ),
    Extension.PG_STAT_STATEMENTS: ExtensionSpec(
        name=Extension.PG_STAT_STATEMENTS, category=Category.OBSERVABILITY, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ, preload=True
    ),
    Extension.TABLEFUNC: ExtensionSpec(
        name=Extension.TABLEFUNC, category=Category.MAINTENANCE, source=Source.PARADEDB_BASE, target_db=TargetDb.MAGHZ
    ),
    Extension.PG_CRON: ExtensionSpec(
        name=Extension.PG_CRON, category=Category.MAINTENANCE, source=Source.PARADEDB_BASE, target_db=TargetDb.POSTGRES, preload=True
    ),
    Extension.AUTO_EXPLAIN: ExtensionSpec(
        name=Extension.AUTO_EXPLAIN, category=Category.OBSERVABILITY, source=Source.PARADEDB_BASE, target_db=TargetDb.NONE, preload=True
    ),
})


# --- [OPERATIONS] ----------------------------------------------------------------------


def shared_preload_libraries() -> str:
    """Project the `shared_preload_libraries` GUC value: every `preload` row's name, in catalog order.

    The comma-joined library list the `infra` runner threads into the container `postgres -c
    shared_preload_libraries=...` command. `pg_search`/`pg_cron`/`pg_net`/`pg_stat_statements` are the
    preloaded extensions and `auto_explain` the preload-only library; declaration order is the load order.

    Returns:
        The comma-separated preload-library string (no spaces), e.g.
        `pg_search,pg_net,pg_stat_statements,pg_cron,auto_explain`.
    """
    return ",".join(spec.name.value for spec in _PROFILE.values() if spec.preload)


def schema_prelude() -> str:
    """Project the `schema.sql` `CREATE EXTENSION` prelude: every `maghz`-target row, in catalog order.

    One idempotent `CREATE EXTENSION IF NOT EXISTS <name>[ CASCADE];` per `target_db == maghz` extension,
    newline-joined in declaration order so a `CASCADE` extension (`pgmq`) precedes any dependent. `pg_cron`
    (target `postgres`) and `auto_explain` (the library, target `none`) are excluded by the fold, so the
    maghz prelude carries exactly the 19 ledger extensions. Rendered into `db/schema.sql`, which `maghz
    schema apply` runs before `routines.sql`, so the extensions exist when the tables reference `vector`
    and `citext`.

    Returns:
        The newline-joined `CREATE EXTENSION` block for the maghz ledger database.
    """
    return "\n".join(spec.create_statement for spec in _PROFILE.values() if spec.target_db is TargetDb.MAGHZ)


def cron_prelude() -> str:
    """Project the `cron.sql` extension prelude: every `postgres`-target row (the lone `pg_cron` line).

    `pg_cron` is the one `target_db == postgres` extension — it can inhabit only the maintenance DB — so
    this renders its single `CREATE EXTENSION IF NOT EXISTS pg_cron;`. Kept a fold (not a literal) so a
    second maintenance-DB extension lands as one catalog row with no edit here.

    Returns:
        The newline-joined `CREATE EXTENSION` block for the `postgres` maintenance database.
    """
    return "\n".join(spec.create_statement for spec in _PROFILE.values() if spec.target_db is TargetDb.POSTGRES)


def dockerfile_apt_block() -> str:
    r"""Project the Dockerfile apt install list: every layered (`source != paradedb-base`) row's package.

    One `postgresql-18-<apt_package>` token per layered extension, newline-joined with a trailing `\`
    continuation and two-space indent so the block drops verbatim into the Dockerfile heredoc's
    `apt-get install -y --no-install-recommends \\` body. The ParadeDB-base extensions emit nothing (they
    ship in the base image), so the block carries exactly the PGDG (`partman`/`hll`/`hypopg`) and PIGSTY
    (`pg-net`/`pgmq`/`pg-jsonschema`) packages.

    Returns:
        The backslash-continued, two-space-indented apt package block for the image build heredoc.
    """
    return " \\\n".join(f"  {spec.apt_line}" for spec in _PROFILE.values() if spec.source.is_layered)


_REGIONS: tuple[_Region, ...] = (
    (
        _DOCKERFILE,
        "apt",
        lambda: (
            "# Edit the `_PROFILE` catalog and regenerate; do not hand-edit this block.\n"
            f"apt-get install -y --no-install-recommends \\\n{dockerfile_apt_block()}"
        ),
    ),
    (
        _SCHEMA_SQL,
        "extensions",
        lambda: (
            "-- Edit the `_PROFILE` catalog and regenerate; do not hand-edit this block. The schema `doctor` verb\n"
            f"-- asserts the live pg_extension census equals this declared set (census_diff).\n{schema_prelude()}"
        ),
    ),
    (_CRON_SQL, "extensions", lambda: f"-- Edit the `_PROFILE` catalog and regenerate; do not hand-edit this block.\n{cron_prelude()}"),
)


def regenerate() -> tuple[Path, ...]:
    """Rewrite each committed file's `[CATALOG:<tag>]` sentinel region from the catalog projection, in place.

    The generation seam: for each `_REGIONS` row, the `[CATALOG:<tag>] ... [/CATALOG:<tag>]` block's interior
    is replaced with the row's projection (the apt block, the maghz `CREATE EXTENSION` prelude, the cron
    pg_cron line), preserving the sentinel comment lines and everything outside the region. So a profile edit
    is one `_PROFILE` change plus one `regenerate()` call, and the three committed artifacts re-derive from
    the one catalog through a single generate cycle. A file written with no
    interior change is rewritten byte-identically (idempotent).

    Returns:
        The paths whose region content changed, empty when every committed region already matched the catalog.

    Raises:
        ValueError: A committed SQL artifact contradicts the embed contract after regeneration.
    """
    changed: list[Path] = []
    for path, tag, project in _REGIONS:
        original = path.read_text(encoding="utf-8")
        pattern = re.compile(rf"(?P<open>\[CATALOG:{re.escape(tag)}\][^\n]*\n).*?(?P<close>[^\n]*\[/CATALOG:{re.escape(tag)}\])", re.DOTALL)
        # search-and-splice (each tag's sentinel region is unique per file): the projection drops in
        # verbatim, so no `sub` replacement-template escape processing can corrupt a backslash-bearing block.
        found = pattern.search(original)
        rewritten = original if found is None else f"{original[: found.start()]}{found['open']}{project()}\n{found['close']}{original[found.end() :]}"
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
            changed.append(path)
    drift = _embed_drift()
    if drift:
        msg = "; ".join(drift)
        raise ValueError(f"embed contract drift: {msg}")
    return tuple(changed)


def _embed_drift() -> tuple[str, ...]:
    """Assert the committed SQL carries the embed contract; one row per mismatched surface, empty when aligned."""
    routines = _ROUTINES_SQL.read_text(encoding="utf-8")
    schema = _SCHEMA_SQL.read_text(encoding="utf-8")
    dims = set(re.findall(r"vector\((\d+)\)", routines + schema))
    checks = (
        (f"'{EMBED_ENDPOINT}'" in routines, f"routines.sql embed endpoint is not {EMBED_ENDPOINT}"),
        (f"'{EMBED_MODEL}'" in routines, f"routines.sql embed model is not {EMBED_MODEL}"),
        (dims == {str(EMBED_DIM)}, f"vector dimension sites {sorted(dims)} are not all {EMBED_DIM}"),
    )
    return tuple(message for aligned, message in checks if not aligned)


def census_diff(installed: Iterable[str]) -> CensusDiff:
    """Reconcile the live maghz `pg_extension` census against the declared `target_db == maghz` catalog.

    `missing` is the declared-maghz set minus the installed set (an extension the catalog declares but the
    DB lacks — an apply gap); `undeclared` is the installed set minus the declared-maghz set (an extension
    installed out of band the catalog does not own — profile drift), after subtracting `_CENSUS_IGNORE` (the
    built-in `plpgsql` and the ParadeDB-base PostGIS trio, present in every database outside the profile).
    The comparison is the maghz catalog membership only: `auto_explain` registers no `pg_extension` row and
    `pg_cron` lives in the `postgres` DB, so neither is in the maghz declared set and neither reads as drift.

    Args:
        installed: The `pg_extension.extname` values the maghz connectivity probe returned.

    Returns:
        The `CensusDiff` naming the missing and undeclared extension sets (both empty when aligned), each
        sorted for a deterministic receipt.
    """
    declared = frozenset(spec.name.value for spec in _PROFILE.values() if spec.target_db is TargetDb.MAGHZ)
    live = frozenset(installed) - _CENSUS_IGNORE
    return CensusDiff(missing=tuple(sorted(declared - live)), undeclared=tuple(sorted(live - declared)))


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "Category",
    "CensusDiff",
    "Extension",
    "ExtensionSpec",
    "Source",
    "TargetDb",
    "census_diff",
    "cron_prelude",
    "dockerfile_apt_block",
    "schema_prelude",
    "shared_preload_libraries",
]
