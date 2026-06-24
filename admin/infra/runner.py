"""Stack runner: one polymorphic verb over converge, tear-down, and preview of the docker stack.

This module owns the Pulumi Automation API dispatch, the `StackOp` lifecycle vocabulary, and the inline
desired-state program (`_define`) the Automation API converges — the program is folded in here
function-locally rather than split across a sibling module, so the runner and the resources it converges
are one owner. A single `run` entrypoint subscribes the closed `StackOp` into the total `_VERBS` policy
table and returns the domain-internal `RuntimeRail[Envelope]`; the CLI handler lowers that rail to the stdout
`Envelope` through the shared `runtime.lower` seam, so the Pulumi/httpx/OS boundary fault is projected
once, at the edge, never inline.

The three verbs are one parametric `_Verb` policy row over `(factory, summary, after)`: the engine-bound
Automation API method `factory` builds, the `summary` reads the verb-specific `(result_text, changes,
outputs)` triple off the result, and `after` is the optional sequential follow-on leg (`up` alone binds
the Ollama embed pull). One `_offload` worker-thread fence runs every blocking verb and one `_project`
folds every result-and-evidence pair to its receipt, so converge/destroy/preview share the offload→grade→
project chain rather than each re-deriving it — `up` is a row carrying a `factory`/`after`, not a bespoke
two-phase function. The structured `EngineEvent` stream folds into a thread-collected `_Engine` sink:
provider `DiagnosticEvent`s and failed `ResOpFailedEvent` steps grade into severity-ranked `Row`s and a
`Receipt` fact, so an engine error surfaces as addressable evidence rather than discarded stdout, and the
converge `outputs` (the `db_dsn`/`ollama_url`/`n8n_url` stack exports `_define` declares) ride the receipt
as the live endpoint census rather than being thrown away.

State lives in a local `file://` backend with an empty passphrase, so no Pulumi Cloud account is touched;
`continue_on_error` lets a single failed resource surface its diagnostic without aborting the whole
converge. `up` runs `refresh` before `up` to close Pulumi's stopped-container `must_run` gap, then pulls
the embed model into the freshly-started Ollama container so the in-DB `pg_net` embed sweep has a model to
call. The spawn fence routes through the canonical fused resilience envelope: `guarded(RetryClass.PROC,
...)` retries transient Pulumi offload flaps and `guarded(RetryClass.HTTP, ...)` rides the freshly-started
container's connection refusals, each lifting any surviving escape — including a typed `pulumi.automation`
`CommandError` — to the `BoundaryFault` rail through its single `async_boundary`, never a hand-composed
`async_boundary(..., guard(...))` doubled lift.

The heavy `pulumi`/`pulumi_docker`/`pulumi_docker_build` host-side imports are gated function-locally per
the dual-band law (a core-clean dist import would crash or slow the runtime load); their types appear in
signatures as `TYPE_CHECKING`-only structural handles the beartype claw resolves lazily.
"""

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from functools import partial
from pathlib import Path
import secrets
from typing import Final, TYPE_CHECKING

from anyio.to_thread import run_sync
from expression import Error, Ok, Result
from frozendict import frozendict
import httpx
import msgspec

from admin.core import completed, Detail, Envelope, Row, Status
from admin.profile import shared_preload_libraries
from admin.runtime import guarded, Receipt, RetryClass, RuntimeRail, Signals
from admin.settings import MaghzSettings


if TYPE_CHECKING:
    from pulumi.automation import Stack, UpResult
    from pulumi.automation.events import EngineEvent, OpType
    import pulumi_docker as docker
else:
    # Dual-band: the host-side pulumi types are gated out of the core load, so bind their names to `object`
    # at runtime. The runtime closures (`_stack`/`_up.method`/`_Engine.collect`) carry these in their
    # signatures, and the beartype claw resolves a hint at first CALL — an unbound `TYPE_CHECKING` name
    # would raise an unresolvable-forward-reference fault there. `object` is the honest runtime check (the
    # real type cannot be inspected without importing pulumi); static checkers read the gated imports above.
    Stack = UpResult = EngineEvent = OpType = docker = object


# --- [TYPES] ---------------------------------------------------------------------------


class StackOp(StrEnum):
    """The closed set of stack verbs `run` discriminates on; one `_VERBS` policy row each."""

    UP = "up"
    DOWN = "down"
    STATUS = "status"


# The Automation API op->count map a verb result carries (`UpdateSummary.resource_changes` /
# `PreviewResult.change_summary`); keyed on the `OpType` `str`-`Enum` whose `.value` `_changes` cleans.
type _Changes = Mapping[OpType | str, int]
# The exported stack-output census `up` materializes off `UpResult.outputs`: `db_dsn`/`ollama_url`/
# `n8n_url`. `down`/`status` carry no live outputs, so the empty map is the floor. The materialized census
# is a `frozendict` (PyPI `frozendict`, a `dict` subclass msgspec encodes natively) so the `frozen=True`
# `StackDetail` carrier holds no rebindable `dict`; `_Changes` stays the raw `OpType`-keyed provider map.
type _Outputs = frozendict[str, str]
# The engine-bound blocking Automation API method built off the offload's own `_Engine` sink, so every
# `on_event=engine.collect` pipes the structured stream into the receipt; the factory takes the sink and
# yields the `(stack) -> result` method the worker thread runs.
type _Method[R] = Callable[[Stack], R]
type _Factory[R] = Callable[[_Engine], _Method[R]]
# The verb-specific projection reading the `(result_text, resource_changes)` pair off one result; the one
# `_project` fold spends it and pairs it with the `_outputs` census `_project` reads uniformly off every
# result (`up` carries the live exports, `down`/`status` floor to empty), so a single projection serves
# converge/destroy/preview and the egress census lives at one point rather than in every row.
type _Summary[R] = Callable[[R], tuple[str, _Changes | None]]
# The optional sequential follow-on leg a verb binds after a clean converge — `up` alone pulls the embed
# model under `HTTP`; `down`/`status` carry `None`. It rides the converge `Envelope` on the `Ok` leg.
type _After = Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]


# --- [CONSTANTS] -----------------------------------------------------------------------

# The `DiagnosticEvent.severity` wire vocabulary that grades into a `Row` and the receipt status: a
# `"warning"` is evidence, an `"error"` gates the receipt to `FAILED`. `"info"`/`"info#err"` are progress
# noise absent from this table, so a membership test drops them at admission and the worst-severity grade
# reads each diagnostic's own rank — one primary correspondence, no parallel "is load-bearing" set.
_SEVERITY_RANK: frozendict[str, int] = frozendict({"warning": 1, "error": 2})

# The exported `pulumi.export` keys `_define` declares, surfaced as the live endpoint census on the `up`
# receipt; declaration order is the receipt-row order. A new export is one entry here plus one
# `pulumi.export` in `_define`, read once by `_outputs` off `UpResult.outputs`.
_EXPORTS: tuple[str, ...] = ("db_dsn", "ollama_url", "n8n_url")

# The OCI label set every owned container carries (the `MaghzStack.__init__` `labels` closure folds the
# per-container `title`/`alias` onto it), so the stack is one addressable logical unit in `docker ps
# --filter` and an image registry reads provenance off the running container, not just the build.
# `maghz.stack` ties every container to the `MaghzStack` component for grouped converge/teardown queries.
_OCI_BASE: frozendict[str, str] = frozendict({
    "org.opencontainers.image.vendor": "maghz",
    "org.opencontainers.image.source": "https://github.com/bsamiee/Maghz",
    "maghz.stack": "local",
})

# The bytes of the n8n encryption key minted host-side and bind-mounted into the container as a real file
# (`_n8n_key_file`): n8n reads `N8N_ENCRYPTION_KEY_FILE` at boot to decrypt stored credentials. A 32-byte
# hex key matches n8n's self-generated key width; the host file under `.cache/n8n/` (gitignored) is the
# stable source of truth across converges — never a `/run/secrets` Swarm path (absent on Colima) and never
# a keychain read.
_N8N_KEY_HEX_BYTES: Final[int] = 32
_N8N_KEY_CONTAINER_PATH: Final[str] = "/home/node/.n8n/encryptionKey"
# The dedicated-n8n-database init script, bind-mounted read-only into the db container's
# docker-entrypoint-initdb.d so the Postgres entrypoint creates the `n8n` database on first cluster init
# (n8n connects to it and creates only its own tables; it never creates the database).
_N8N_INITDB: Final[Path] = Path("db/init/n8n.sql")

# The per-container memory ceilings (MB) the converge stamps onto each `docker.Container.memory`. These are
# deployment-tuning policy values the infra runner owns, not user-facing env: the DB carries the largest
# ceiling (BM25/HNSW index builds + the embed sweep), Ollama the model-resident floor, n8n the node runtime.
# A `0` ceiling would be unbounded; these bound the Colima VM's per-container RSS so one container cannot
# starve the others. The file-descriptor `ulimit` is shared across all three (`nofile`, declared inline).
_DB_MEMORY_MB: Final[int] = 4096
_OLLAMA_MEMORY_MB: Final[int] = 6144
_N8N_MEMORY_MB: Final[int] = 1024


# --- [MODELS] --------------------------------------------------------------------------


class StackDetail(Detail, frozen=True, tag="stack"):
    """Converge/destroy/preview receipt: the Pulumi result, engine diagnostics tally, and embed-pull outcome.

    `outputs` is the live endpoint census — the `db_dsn`/`ollama_url`/`n8n_url` stack exports `_define`
    declares — that `up` materializes off `UpResult.outputs`; `down`/`status` carry no live outputs and
    leave it empty. The map rides the receipt so a converge surfaces the reachable DSN/URLs rather than
    discarding the exports the program produced. `model_pulled` is `True` only after a clean `up` embed
    pull; every other verb leaves it `False`.
    """

    op: StackOp
    result: str
    resource_changes: frozendict[str, int]
    outputs: _Outputs = frozendict()
    diagnostics: int = 0
    model_pulled: bool = False


class _Pull(msgspec.Struct, frozen=True, gc=False):
    """One streamed line of the Ollama `/api/pull` progress response.

    Only the `error` slot is load-bearing: a server-reported pull failure rides it and aborts the stream;
    every progress field Ollama also emits (`status`/`digest`/`total`) is ignored by the permissive decoder
    rather than carried as unread evidence. `parse` is the boundary admission that tolerates a non-JSON
    progress line, folding it to a no-error frame off the shared module-level `_PULL_DECODER`.
    """

    error: str | None = None

    @classmethod
    def parse(cls, line: str) -> _Pull:
        """Decode one progress line off the shared decoder; non-JSON noise folds to a no-error empty frame."""
        try:
            return _PULL_DECODER.decode(line.encode()) if line else cls()
        except msgspec.DecodeError:
            return cls()


class _Diag(msgspec.Struct, frozen=True, gc=False):
    """One graded engine diagnostic: the severity, the human message, and the optional resource urn."""

    severity: str
    message: str
    urn: str = ""

    @property
    def row(self) -> Row:
        """Project to the receipt `Row`; the key names the failing resource (urn tail) or the severity."""
        return Row(key=self.urn.rsplit("::", 1)[-1] or self.severity, text=self.message)


class _Engine(msgspec.Struct):
    """Thread-collected engine evidence sink: the structured `EngineEvent` stream folded to graded diagnostics.

    The Automation API invokes `collect` from the offload worker thread as the engine streams events; list
    appends are atomic under the GIL, so the sink accumulates without a lock and the lane reads it after the
    worker joins. Only severity-graded `DiagnosticEvent`s and failed `ResOpFailedEvent` steps are retained —
    `info`/`info#err` progress noise is dropped at admission — so `graded` yields the real
    provider-error/warning census the flat-stdout form discarded.
    """

    diags: list[_Diag] = msgspec.field(default_factory=list)

    def collect(self, event: EngineEvent) -> None:
        """Fold one streamed engine event into the graded-diagnostic sink, dropping progress noise.

        Bound as the `on_event` callback on every blocking verb; a severity-graded `DiagnosticEvent` lands
        as its graded `_Diag`, a `ResOpFailedEvent` lands as a synthetic `error` naming the failed op and
        status, and every other event class (prelude, summary, per-resource progress) is ignored.
        """
        if (diag := event.diagnostic_event) is not None and diag.severity in _SEVERITY_RANK:
            self.diags.append(_Diag(severity=diag.severity, message=diag.message.strip(), urn=diag.urn or ""))
        elif (failed := event.res_op_failed_event) is not None:
            meta = failed.metadata
            self.diags.append(_Diag(severity="error", message=f"{getattr(meta.op, 'value', meta.op)} failed (status {failed.status})", urn=meta.urn))

    def graded(self) -> tuple[Status, tuple[Row, ...], int]:
        """Grade the collected diagnostics into the receipt status, rows, and count.

        The worst severity drives the status (`FAILED` on any error, `OK` otherwise — a warning is evidence,
        not a gate), every graded diagnostic projects to a `Row`, and the count rides the receipt slot. An
        empty sink folds to `(OK, (), 0)`.

        Returns:
            The `(status, rows, count)` triple the verb projection stamps onto its `StackDetail`.
        """
        worst = max((_SEVERITY_RANK[diag.severity] for diag in self.diags), default=0)
        return (Status.FAILED if worst >= _SEVERITY_RANK["error"] else Status.OK), tuple(diag.row for diag in self.diags), len(self.diags)

    def receipt(self, op: StackOp) -> Receipt:
        """Mint one `fact` receipt naming the op and its diagnostic census for the `Signals` stderr stream."""
        census: dict[str, object] = {"diagnostics": len(self.diags), "errors": sum(1 for diag in self.diags if diag.severity == "error")}
        return Receipt.of("infra", ("emitted", op.value, census))


class _Verb(msgspec.Struct, frozen=True, gc=False):
    """One stack-verb policy row: the engine-bound `factory`, its result `summary`, and the optional `after` leg.

    The three verbs differ only in these three fields: `factory` builds the blocking method bound to the
    offload's `_Engine` sink (so `on_event=engine.collect` streams the structured events into the receipt);
    `summary` reads the verb's `(result_text, resource_changes, outputs)` triple off its result; `after` is
    the follow-on rail a clean converge binds (`up` pulls the embed model under `HTTP`, `down`/`status`
    carry `None`). `run` drives every row through the one `_offload` fence and `_project` fold, so converge/
    destroy/preview share the offload→grade→project chain — `up` is a row with a `factory`/`after`, never a
    bespoke two-phase function. `gc=False` is sound: the fields are callables and a scalar, no cycles form.
    """

    op: StackOp
    factory: _Factory[object]
    summary: _Summary[object]
    after: _After | None = None


# --- [SERVICES] ------------------------------------------------------------------------

# One reusable `_Pull` decoder for the Ollama `/api/pull` progress stream; a fresh `Decoder` per line
# re-resolves the struct schema on the hot streaming path, so the shared instance is the owner `_Pull.parse`
# reads, mirroring the `core._ENCODER`/`receipts._ENCODE` shared-codec discipline.
_PULL_DECODER: Final[msgspec.json.Decoder[_Pull]] = msgspec.json.Decoder(type=_Pull)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _n8n_key_file(cfg: MaghzSettings) -> Path:
    """Mint-or-read the host n8n encryption key file, the stable bind-mount source the container decrypts with.

    The BL-1 fix: n8n needs `N8N_ENCRYPTION_KEY` (or `_FILE`) to decrypt stored credentials, and a
    `/run/secrets` Swarm path is absent on a plain Colima container (it aborts n8n at boot). This mints a
    32-byte hex key once into `<cache_dir>/n8n/encryptionKey` (gitignored under `.cache/`) and reads the
    existing file on every later converge, so the key is stable across restarts and rebuilds — the host
    file is the source of truth, bind-mounted read-only to `_N8N_KEY_CONTAINER_PATH`. The key never rides a
    keychain: it is minted by `secrets.token_hex` and lives only in the gitignored cache file and the
    container mount. The parent `workflows_dir` contract is created alongside (the n8n host_path mount the
    `_define` program needs), so a fresh checkout converges without a missing-directory abort.

    Args:
        cfg: The validated settings owning the cache dir and the n8n workflows directory.

    Returns:
        The resolved host path of the n8n encryption key file, ready as the container bind-mount source.
    """
    cfg.n8n.workflows_dir.mkdir(parents=True, exist_ok=True)  # the n8n host_path workflows mount needs the dir to exist
    key_dir = (cfg.cache_dir / "n8n").resolve()
    key_dir.mkdir(parents=True, exist_ok=True)
    key_file = key_dir / "encryptionKey"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(_N8N_KEY_HEX_BYTES), encoding="utf-8")
        key_file.chmod(0o600)
    return key_file


def _define(cfg: MaghzSettings) -> None:
    """Declare every stack resource under one `MaghzStack` component; the inline Pulumi program `up` converges.

    Closes over the validated settings rather than reading Pulumi config and parents every resource to one
    `MaghzStack` `ComponentResource`, so `pulumi up`/`preview` group the custom PG `docker_build` image, the
    `ollama`/`db`/`n8n` containers, their `maghz` network, and the three named volumes under one logical
    unit rather than a flat resource list. The image build carries BuildKit `cacheFrom`/`cacheTo` against a
    local cache dir so the apt-layered extension build reuses cached layers across converges instead of
    cold-running every time; every container carries OCI provenance labels, a file-descriptor `ulimit`, and
    a memory ceiling, and the n8n container mounts a real host-minted encryption key file
    (`N8N_ENCRYPTION_KEY_FILE`) — never the `/run/secrets` Swarm path absent on Colima. The `depends_on`
    healthcheck gating chains image -> db -> n8n so a dependent never starts before its prerequisite is
    converged. The component's three registered outputs are re-exported as the stack `db_dsn`/`ollama_url`/
    `n8n_url` census the `up` receipt and the Automation-API outputs carry back to the settings layer. The
    heavy `pulumi`/`pulumi_docker`/`pulumi_docker_build` imports are function-local (dual-band law); this
    body and the nested `MaghzStack` class run only inside the offload worker `_stack` binds the program to.
    """
    import pulumi  # noqa: PLC0415 - dual-band: heavy host-side plugin stack, imported only inside the offloaded program
    import pulumi_docker as docker  # noqa: PLC0415
    import pulumi_docker_build as docker_build  # noqa: PLC0415

    infra = cfg.infra
    key_file = _n8n_key_file(cfg)  # mint-or-read the host n8n key + ensure the workflows dir before declaring the mount
    build_cache = (infra.state_dir / "buildkit-cache").resolve()
    build_cache.mkdir(parents=True, exist_ok=True)  # the local BuildKit cache backend needs its dir present before the build writes to it
    initdb = _N8N_INITDB.resolve()  # the n8n-database init script bind-mounted into the db container's initdb.d

    class MaghzStack(pulumi.ComponentResource):
        """The one logical-unit component grouping every maghz docker resource for grouped converge/teardown.

        Subclasses `ComponentResource` so `pulumi up`/`preview` render the image, network, volumes, and three
        containers under one `maghz:stack:MaghzStack` parent — a converge groups by logical unit, and a
        `pulumi state` query reads the whole stack as one node. Defined function-locally because its
        `ComponentResource` base is the dual-band-gated `pulumi` import; instantiated once by `_define`, it
        registers the `db_dsn`/`ollama_url`/`n8n_url` outputs the Automation API carries back.
        """

        def __init__(self) -> None:
            super().__init__("maghz:stack:MaghzStack", "maghz", None, pulumi.ResourceOptions())
            parented = pulumi.ResourceOptions(parent=self)  # every provider/resource parents to the component for grouped converge
            on = pulumi.ResourceOptions(provider=docker.Provider("colima", host=infra.docker_host, opts=parented), parent=self)
            # The BuildKit build resource is a distinct provider plugin from `docker.Provider`; pin its build
            # daemon to the same Colima socket explicitly rather than letting it fall back to ambient DOCKER_HOST.
            on_build = pulumi.ResourceOptions(provider=docker_build.Provider("colima-build", host=infra.docker_host, opts=parented), parent=self)

            image = docker_build.Image(
                "maghz-pg",
                tags=[infra.image_tag],
                context=docker_build.BuildContextArgs(location=str(infra.image_context)),
                dockerfile=docker_build.DockerfileArgs(location=str(infra.image_context / "Dockerfile")),
                build_args={"PARADEDB_TAG": infra.paradedb_tag},
                platforms=[docker_build.Platform.LINUX_ARM64],
                # BuildKit local layer cache: read prior layers on converge, write the rebuilt set with
                # `mode=max` (every intermediate stage, so the apt extension layers survive), so a re-converge
                # over an unchanged Dockerfile reuses the heavy apt install rather than running it cold.
                cache_from=[docker_build.CacheFromArgs(local=docker_build.CacheFromLocalArgs(src=str(build_cache)))],
                cache_to=[docker_build.CacheToArgs(local=docker_build.CacheToLocalArgs(dest=str(build_cache), mode=docker_build.CacheMode.MAX))],
                load=True,
                push=False,
                opts=on_build,
            )

            network = docker.Network("maghz", name="maghz", opts=on)
            pg_data = docker.Volume("maghz-data", name="maghz-data", opts=on)
            ollama_models = docker.Volume("ollama-models", name="ollama-models", opts=on)
            n8n_data = docker.Volume("n8n-data", name="n8n-data", opts=on)
            # One file-descriptor ulimit every container shares (the BM25/HNSW index builds and the n8n
            # node runtime both open many fds); declared once, spread onto each container's `ulimits`.
            nofile = docker.ContainerUlimitArgs(name="nofile", soft=65536, hard=65536)

            def labels(title: str, alias: str) -> list[docker.ContainerLabelArgs]:
                # The OCI label set for one container: the shared `_OCI_BASE` plus the per-container title
                # (`org.opencontainers.image.title`) and a `maghz.alias.<alias>` selector, so a `docker ps
                # --filter label=maghz.alias.db` finds the container. Closed over the function-local `docker`,
                # so the gated provider type never reaches a module-level beartype-resolved annotation.
                rows = {**_OCI_BASE, "org.opencontainers.image.title": title, f"maghz.alias.{alias}": "true"}
                return [docker.ContainerLabelArgs(label=key, value=value) for key, value in rows.items()]

            docker.Container(
                "ollama",
                name="maghz-ollama",
                image=infra.ollama_image,
                restart="unless-stopped",
                memory=_OLLAMA_MEMORY_MB,
                ulimits=[nofile],
                labels=labels("maghz-ollama", "ollama"),
                ports=[docker.ContainerPortArgs(internal=11434, external=infra.ollama_port, ip="127.0.0.1")],
                volumes=[docker.ContainerVolumeArgs(volume_name=ollama_models.name, container_path="/root/.ollama")],
                networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["ollama"])],
                healthcheck=docker.ContainerHealthcheckArgs(
                    tests=["CMD", "ollama", "list"], interval="10s", timeout="5s", retries=5, start_period="20s"
                ),
                opts=on,
            )

            db_container = docker.Container(
                "db",
                name="maghz-db",
                image=image.ref,
                restart="unless-stopped",
                memory=_DB_MEMORY_MB,
                ulimits=[nofile],
                labels=labels("maghz-db", "db"),
                # Trust auth on the 127.0.0.1-only port: maghz is the superuser, agents and MCP servers
                # auto-authenticate with no password. The DSN is passwordless by design (TODO secrets).
                envs=["POSTGRES_USER=maghz", "POSTGRES_DB=maghz", "POSTGRES_HOST_AUTH_METHOD=trust"],
                command=[
                    "postgres",
                    "-c",
                    # The shared-preload string is the one `profile` catalog projection, not a hand-kept literal:
                    # the `preload`-flagged extensions plus the `auto_explain` library, rendered in catalog order.
                    f"shared_preload_libraries={shared_preload_libraries()}",
                    "-c",
                    "cron.database_name=postgres",
                    "-c",
                    "cron.use_background_workers=on",
                    # pg_net is created in the maghz ledger DB and its request queue lives there, so its
                    # background worker must attach to maghz (the default 'postgres' leaves the worker idling
                    # against a DB with no pg_net schema, and embed requests never egress). The embed sweep's
                    # net.http_post -> Ollama round-trip depends on this.
                    "-c",
                    "pg_net.database_name=maghz",
                    "-c",
                    "max_worker_processes=24",
                ],
                ports=[docker.ContainerPortArgs(internal=5432, external=infra.db_port, ip="127.0.0.1")],
                volumes=[
                    docker.ContainerVolumeArgs(volume_name=pg_data.name, container_path="/var/lib/postgresql"),
                    # The n8n-database init script, read-only into initdb.d: the entrypoint creates the n8n
                    # database on first cluster init (run-once-on-empty-PGDATA), so the n8n container boots.
                    docker.ContainerVolumeArgs(host_path=str(initdb), container_path="/docker-entrypoint-initdb.d/10-n8n.sql", read_only=True),
                ],
                networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["db"])],
                healthcheck=docker.ContainerHealthcheckArgs(
                    tests=["CMD", "pg_isready", "-U", "maghz", "-d", "maghz", "-q"], interval="10s", timeout="5s", retries=5, start_period="30s"
                ),
                opts=pulumi.ResourceOptions.merge(on, pulumi.ResourceOptions(depends_on=[image])),  # gate on the image build, over the shared opts
            )

            docker.Container(
                "n8n",
                name=cfg.n8n.container_name,
                image=cfg.n8n.image,
                restart="unless-stopped",
                memory=_N8N_MEMORY_MB,
                ulimits=[nofile],
                labels=labels(cfg.n8n.container_name, "n8n"),
                envs=[
                    # BL-1 fix: n8n decrypts stored credentials with the key at `N8N_ENCRYPTION_KEY_FILE`. The
                    # file is the host-minted `_n8n_key_file` bind-mounted read-only below — a real file on a
                    # plain Colima container, never the `/run/secrets` Swarm path (absent here, aborts n8n) and
                    # never a keychain read. Stable across restarts because the host file is the source of truth.
                    f"N8N_ENCRYPTION_KEY_FILE={_N8N_KEY_CONTAINER_PATH}",
                    "DB_TYPE=postgresdb",
                    "DB_POSTGRESDB_HOST=db",  # the Docker network alias owned by the `db` container's aliases=["db"]
                    "DB_POSTGRESDB_PORT=5432",
                    "DB_POSTGRESDB_DATABASE=n8n",
                    "DB_POSTGRESDB_USER=maghz",
                    "NODE_ENV=production",
                    f"N8N_HOST={cfg.n8n.host}",
                    f"N8N_PROTOCOL={cfg.n8n.protocol}",
                    f"WEBHOOK_URL={cfg.n8n.webhook_url}",
                    f"N8N_PROXY_HOPS={cfg.n8n.proxy_hops}",
                    "GENERIC_TIMEZONE=UTC",
                ],
                # HTTPS hands the public port to the reverse proxy on the `maghz` network; the `n8n` alias is the only ingress.
                ports=[docker.ContainerPortArgs(internal=5678, external=cfg.n8n.port, ip="127.0.0.1")] if cfg.n8n.protocol == "http" else [],
                volumes=[
                    docker.ContainerVolumeArgs(volume_name=n8n_data.name, container_path="/home/node/.n8n"),
                    docker.ContainerVolumeArgs(host_path=str(cfg.n8n.workflows_dir.resolve()), container_path="/home/node/workflows"),
                    # The host-minted encryption key, read-only: the BL-1 mounted-key contract.
                    docker.ContainerVolumeArgs(host_path=str(key_file), container_path=_N8N_KEY_CONTAINER_PATH, read_only=True),
                ],
                networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["n8n"])],
                healthcheck=docker.ContainerHealthcheckArgs(
                    tests=["CMD-SHELL", "wget -qO- http://localhost:5678/healthz || exit 1"],
                    interval="15s",
                    timeout="5s",
                    retries=5,
                    start_period="30s",
                ),
                opts=pulumi.ResourceOptions.merge(on, pulumi.ResourceOptions(depends_on=[db_container])),  # gate on db, over the shared opts
            )

            # The live endpoint census, assigned onto the component then registered as its outputs: `db_dsn`
            # is the single `DatabaseConfig.dsn` owner (never an f-string that drifts from it), so the
            # Automation API carries the canonical DSN back to the settings layer rather than a re-spelled one.
            self.db_dsn = str(cfg.database.dsn)
            self.ollama_url = f"http://127.0.0.1:{infra.ollama_port}"
            self.n8n_url = cfg.n8n.api_url
            self.register_outputs({"db_dsn": self.db_dsn, "ollama_url": self.ollama_url, "n8n_url": self.n8n_url})

    stack = MaghzStack()
    pulumi.export("db_dsn", stack.db_dsn)
    pulumi.export("ollama_url", stack.ollama_url)
    pulumi.export("n8n_url", stack.n8n_url)


def _stack(cfg: MaghzSettings) -> Stack:
    from pulumi import automation as auto  # noqa: PLC0415 - dual-band: the Automation API drives the host-side plugin stack, gated off the core load

    state = cfg.infra.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)  # the file:// backend cannot open a bucket whose directory does not exist
    opts = auto.LocalWorkspaceOptions(
        project_settings=auto.ProjectSettings(name=cfg.infra.project, runtime="python", backend=auto.ProjectBackend(url=f"file://{state}")),
        # DOCKER_CERT_PATH/DOCKER_TLS_VERIFY leak in from the machine env and point the docker provider at
        # a nonexistent TLS cert dir; the Colima socket is plain, so neutralize them alongside the host.
        env_vars={"PULUMI_CONFIG_PASSPHRASE": "", "DOCKER_HOST": cfg.infra.docker_host, "DOCKER_CERT_PATH": "", "DOCKER_TLS_VERIFY": ""},
    )
    return auto.create_or_select_stack(stack_name=cfg.infra.stack, project_name=cfg.infra.project, program=partial(_define, cfg), opts=opts)


def _changes(raw: _Changes | None) -> frozendict[str, int]:
    """Normalize a Pulumi op->count map to a `frozendict` keyed on clean wire strings, reading an `OpType`'s `.value`.

    `pulumi.automation.OpType` is a bare `str`-`Enum`, so `str(member)` yields `"OpType.CREATE"` rather
    than the wire `"create"`; the `getattr(op, "value", str(op))` read takes the clean value for an enum
    key and falls back to `str` for a key the engine already delivered as a plain string. The result is a
    `frozendict` so the `frozen=True` `StackDetail` carrier never holds a rebindable `dict`.

    Returns:
        A `frozendict[str, int]` of the op->count map with clean wire-string keys, empty when `raw` is `None`.
    """
    return frozendict({getattr(op, "value", str(op)): count for op, count in (raw or {}).items()})


def _outputs(result: object) -> _Outputs:
    """Project the declared stack exports off a verb result, empty when the result carries no `outputs`.

    `up` returns a `UpResult.outputs: Mapping[str, OutputValue]`; this reads each `_EXPORTS` key's
    `OutputValue.value` (the exports `_define` declares — `db_dsn`/`ollama_url`/`n8n_url` — resolved
    plaintext because the verb runs `show_secrets=True`), so the converge surfaces the live endpoint
    census rather than discarding it. `down`/`preview` results carry no `outputs` attribute, so the
    `getattr` floor yields the empty map and the receipt slot stays empty for those verbs.

    Returns:
        A `frozendict[str, str]` of the declared export keys present on the result, or empty.
    """
    # `getattr` floor: `up` carries `outputs: Mapping[str, OutputValue]` (each `.value` the plaintext
    # export under `show_secrets=True`); `down`/`preview` carry no `outputs`, so the floor yields `{}`.
    raw = getattr(result, "outputs", {})
    return frozendict({key: str(value.value) for key in _EXPORTS if (value := raw.get(key)) is not None})


async def _offload(verb: _Verb, cfg: MaghzSettings) -> RuntimeRail[tuple[object, _Engine]]:
    """Offload one blocking Pulumi verb to a worker thread on the `PROC` fence, streaming engine evidence.

    The single offload boundary for every Automation API verb: drive one blocking unit through
    `guarded(RetryClass.PROC, run_sync, _blocking, ...)` — the fused resilience envelope wraps the
    `run_sync` worker-thread offload in the memoised `PROC` retry caller (replaying a transient `OSError`
    docker-socket flap within the budget) inside one resilience span and lifts any surviving escape —
    including a typed `pulumi.automation` `CommandError` past the `(OSError,)` budget — to the
    `BoundaryFault` rail through its single `async_boundary`. The three verbs compose this one fence rather
    than re-deriving the `run_sync` -> `guard` -> `async_boundary` chain.

    The `_Engine` sink is minted INSIDE `_blocking`, per attempt: `on_event=engine.collect` streams the
    structured `EngineEvent`s of exactly the attempt that produced the result, so a transient `OSError`
    retried by the `PROC` caller starts each replay from a clean sink rather than accumulating the doomed
    attempt's diagnostics into the graded receipt. The `Ok` leg carries the raw Pulumi result paired with
    that attempt's populated sink, so `_project` grades the live diagnostics onto its receipt.

    Args:
        verb: The policy row whose `factory` builds the engine-bound method and whose `op` stamps the
            boundary subject and the receipt.
        cfg: The validated settings driving the Pulumi stack.

    Returns:
        `Ok((result, _Engine))` carrying the raw Pulumi result and the streamed engine evidence, or
        `Error(BoundaryFault)` from the `PROC` fence.
    """

    def _blocking() -> tuple[object, _Engine]:
        # fresh sink + method per attempt so a `PROC`-retried `OSError` flap never folds the failed
        # attempt's streamed diagnostics into the graded receipt; select-or-create and the method both
        # run in the worker thread.
        engine = _Engine()
        return verb.factory(engine)(_stack(cfg)), engine

    return await guarded(RetryClass.PROC, run_sync, _blocking, subject=verb.op.value)


async def _project(verb: _Verb, result: object, engine: _Engine, cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Fold one Pulumi result and its engine evidence into the `StackDetail` envelope, then bind the `after` leg.

    `verb.summary` reads the verb-specific `(result_text, resource_changes)` pair — `up`/`down` read the run
    `.summary`, `status` reads the `.change_summary` with no run summary — and `_outputs` reads the live
    export census uniformly off the result (`up` carries it, `down`/`status` floor to empty), so the one
    projection plus the one census point serve every verb. The engine diagnostics grade the status
    (`FAILED` on any error severity, else `OK`) and contribute their `Row`s, so a clean converge that
    nonetheless logged a provider warning surfaces it as evidence without faulting; the graded census also
    emits one stderr `fact` receipt. `model_pulled` rides the detail set to `verb.after is not None` — `True`
    for `up`, `False` for `down`/`status` — and `verb.after` is the optional follow-on rail gating whether
    that detail reaches the caller: `up` binds the embed pull whose `.map` re-wraps the already-built converge
    envelope on success, so a pull fault short-circuits to `Error` and the `model_pulled=True` detail is
    discarded, leaving the flag observably `True` only on the `up`-and-pull-both-clean path; `down`/`status`
    carry `None` and project the converge envelope directly.

    Returns:
        `Ok(completed(...))` carrying the `StackDetail` receipt and graded rows (`model_pulled` reaching the
        caller `True` only after a clean `up` pull), or `Error(BoundaryFault)` from the `after` leg.
    """
    result_text, raw_changes = verb.summary(result)
    status, rows, count = engine.graded()
    Signals.emit(engine.receipt(verb.op))
    detail = StackDetail(
        op=verb.op,
        result=result_text,
        resource_changes=_changes(raw_changes),
        outputs=_outputs(result),
        diagnostics=count,
        model_pulled=verb.after is not None,
    )
    if verb.after is None:
        return Ok(completed(status, detail, rows=rows))
    return (await verb.after(cfg)).map(lambda _: completed(status, detail, rows=rows))


async def _pull_embed_model(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Pull the embed model into the freshly-started Ollama container under `HTTP`, on the rail.

    The `up` verb's `after` leg, sequential by construction after a clean converge (Ollama must run before
    the pull). One `guarded(RetryClass.HTTP, _stream, ...)` rides the freshly-started container's connection
    refusals within the budget and lifts a surviving escape to the `BoundaryFault` rail through its single
    fused `async_boundary` — the shared resilience envelope, never a hand-composed `async_boundary(...,
    guard(...))` doubled lift. The returned envelope is discarded by `_project`, whose `.map` re-wraps the
    already-built `model_pulled=True` converge envelope on this leg's `Ok`, so only the rail tag is
    load-bearing here — an `Error` here short-circuits the converge envelope away entirely. `_stream`
    streams `POST /api/pull` until the model resolves: a non-JSON progress line decodes to a no-error frame,
    and a typed `error` frame raises `httpx.HTTPError` to abort the stream — a server-reported pull failure,
    not a transport flap.

    Args:
        cfg: The settings owning the Ollama base URL, model name, and request timeout.

    Returns:
        `Ok(...)` once the model resolves (the envelope is the `_project` `.map` floor, not consumed), or
        `Error(BoundaryFault)` from the `HTTP` fence on a server-reported failure or exhausted transport.
    """

    async def _stream() -> None:
        body = {"model": cfg.ollama.embed_model}
        timeout = httpx.Timeout(cfg.ollama.request_timeout, read=None)  # read=None: a streaming pull has no read deadline
        async with (
            httpx.AsyncClient(base_url=str(cfg.ollama.base_url), timeout=timeout) as client,
            client.stream("POST", "/api/pull", json=body) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                # A non-JSON progress line is benign noise; decode it to a no-error frame so only a typed
                # `error` field — never malformed bytes — aborts the stream.
                if (frame := _Pull.parse(line)).error:
                    raise httpx.HTTPError(frame.error)

    return (await guarded(RetryClass.HTTP, _stream, subject="pull")).map(lambda _: completed(Status.OK))


# --- [TABLES] --------------------------------------------------------------------------


def _up(engine: _Engine) -> _Method[UpResult]:
    """Build the `up` method bound to `engine`: refresh to close the stopped-container `must_run` gap, then converge.

    `refresh` runs first so a stopped container is re-detected before `up`'s `must_run` gate, then `up`
    converges under `continue_on_error` (a single failed resource surfaces its diagnostic on the engine
    stream without aborting the whole converge). Both legs thread `on_event=engine.collect`, so the
    refresh's and the converge's structured events both grade onto the one receipt.

    Returns:
        The `(stack) -> UpResult` method the offload worker thread runs, bound to `engine`.
    """

    def method(stack: Stack) -> UpResult:
        stack.refresh(on_event=engine.collect)
        return stack.up(on_event=engine.collect, continue_on_error=True)

    return method


# op -> its `_Verb` policy row. The key set equals `StackOp` exactly, so `run`'s subscription is total; the
# three verbs share the one `_offload`/`_project` chain and differ only by `(factory, summary, after)`.
# `up` carries the refresh-then-converge `_up` factory and the embed-pull `after` leg; `down`/`status` are
# data rows naming only their engine-bound method (`Stack.destroy` under `continue_on_error` / `Stack.preview`)
# and the `(result_text, changes)` pair read off their result — `up`/`down` off the run `UpdateSummary`,
# `status` off the `.change_summary`. The live-export census is `_project`'s uniform `_outputs(result)` read,
# not a per-row field. A new verb is one `StackOp` case plus one row, no branch.
_VERBS: frozendict[StackOp, _Verb] = frozendict({
    StackOp.UP: _Verb(
        op=StackOp.UP, factory=_up, summary=lambda result: (result.summary.result, result.summary.resource_changes), after=_pull_embed_model
    ),
    StackOp.DOWN: _Verb(
        op=StackOp.DOWN,
        factory=lambda engine: lambda stack: stack.destroy(on_event=engine.collect, continue_on_error=True),
        summary=lambda result: (result.summary.result, result.summary.resource_changes),
    ),
    StackOp.STATUS: _Verb(
        op=StackOp.STATUS,
        factory=lambda engine: lambda stack: stack.preview(on_event=engine.collect),
        summary=lambda result: ("preview", result.change_summary),
    ),
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: StackOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one stack verb by `op` on the domain rail, dispatching through the total `_VERBS` policy table.

    `_VERBS[op]` is the verb policy row; the key set equals `StackOp` exactly, so the subscription is total
    without a guarding `match`/`assert_never` — a member added without its row breaks loudly at the
    subscription. The row's blocking method offloads to a worker thread under `guarded(RetryClass.PROC, ...)`
    through the shared `_offload` fence with the engine stream graded onto the receipt, then `_project`
    folds the result-and-evidence pair to the `StackDetail` envelope and binds the optional `after` leg
    (`up`'s embed pull). The returned `RuntimeRail[Envelope]` is the domain-internal contract; the CLI
    handler lowers it to the stdout `Envelope` through the shared `runtime.lower` seam, so a Pulumi/httpx/OS
    boundary fault is projected once, at the edge.

    Args:
        op: The stack verb to run; selects its policy row from `_VERBS`.
        cfg: The validated settings driving the Pulumi stack and Ollama reach.

    Returns:
        `Ok(Envelope)` carrying a completed converge, destroy, or preview receipt (graded by the engine
        diagnostics, the `up` row carrying the live `outputs` census and `model_pulled`), or
        `Error(BoundaryFault)` from the offload or the `after` fence.
    """
    verb = _VERBS[op]
    # `_project` is awaitable (it binds the `after` leg), so the offload `Ok` pair meets it through a
    # `match` rather than `Result.bind`, whose mapper is synchronous — the one async-bind seam in the rail.
    match await _offload(verb, cfg):
        case Result(tag="ok", ok=(result, engine)):
            return await _project(verb, result, engine, cfg)
        case Result(error=boundary_fault):
            return Error(boundary_fault)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["StackDetail", "StackOp", "run"]
