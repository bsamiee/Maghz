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
from admin.runtime import Fact, guarded, Receipt, RetryClass, RuntimeRail, Signals
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from pulumi.automation import DestroyResult, PreviewResult, Stack, UpResult
    from pulumi.automation.events import EngineEvent, OpType
    import pulumi_docker as docker
else:
    # Dual-band: the host-side pulumi types are gated out of the core load, so bind their names to `object`
    # at runtime. The runtime closures (`_stack`/the `_Method` bodies/`_Engine.collect`) carry these in their
    # signatures, and the beartype claw resolves a hint at first CALL — an unbound `TYPE_CHECKING` name
    # would raise an unresolvable-forward-reference fault there. `object` is the honest runtime check (the
    # real type cannot be inspected without importing pulumi); static checkers read the gated imports above.
    Stack = UpResult = DestroyResult = PreviewResult = EngineEvent = OpType = docker = object


class StackOp(StrEnum):
    UP = "up"
    DOWN = "down"
    STATUS = "status"


type _Outputs = frozendict[str, str]


type _Projected = tuple[str, frozendict[str, int], _Outputs]


type _Method[R] = Callable[[Stack], R]


type _Factory[R] = Callable[[_Engine], _Method[R]]


type _Summary[R] = Callable[[R], tuple[str, frozendict[str, int]]]


type _Drive = Callable[[_Engine, Stack], _Projected]


type _After = Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]


_SEVERITY_RANK: frozendict[str, int] = frozendict({"warning": 1, "error": 2})


_EXPORTS: tuple[str, ...] = ("db_dsn", "ollama_url", "n8n_url")


_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


_OCI_BASE: frozendict[str, str] = frozendict({
    "org.opencontainers.image.vendor": "maghz",
    "org.opencontainers.image.source": "https://github.com/bsamiee/Maghz",
    "maghz.stack": "local",
})


_N8N_KEY_HEX_BYTES: Final[int] = 32


_N8N_KEY_CONTAINER_PATH: Final[str] = "/home/node/.n8n/encryptionKey"


_N8N_INITDB: Final[Path] = _REPO_ROOT / "db/init/n8n.sql"


_DB_MEMORY_MB: Final[int] = 4096


_OLLAMA_MEMORY_MB: Final[int] = 6144


_N8N_MEMORY_MB: Final[int] = 1024


class StackDetail(Detail, frozen=True, tag="stack"):
    op: StackOp
    result: str
    resource_changes: frozendict[str, int]
    outputs: _Outputs = frozendict()
    diagnostics: int = 0
    model_pulled: bool = False


class _Pull(msgspec.Struct, frozen=True, gc=False):
    error: str | None = None

    @classmethod
    def parse(cls, line: str) -> _Pull:

        try:
            return _PULL_DECODER.decode(line.encode()) if line else cls()
        except msgspec.DecodeError:
            return cls()


class _Diag(msgspec.Struct, frozen=True, gc=False):
    severity: str
    message: str
    urn: str = ""

    @property
    def row(self) -> Row:

        return Row(key=self.urn.rsplit("::", 1)[-1] or self.severity, text=self.message)


class _Engine(msgspec.Struct):
    diags: list[_Diag] = msgspec.field(default_factory=list)

    def collect(self, event: EngineEvent) -> None:

        if (diag := event.diagnostic_event) is not None and diag.severity in _SEVERITY_RANK:
            self.diags.append(_Diag(severity=diag.severity, message=diag.message.strip(), urn=diag.urn or ""))
        elif (failed := event.res_op_failed_event) is not None:
            meta = failed.metadata
            self.diags.append(_Diag(severity="error", message=f"{getattr(meta.op, 'value', meta.op)} failed (status {failed.status})", urn=meta.urn))

    def graded(self) -> tuple[Status, tuple[Row, ...], int]:

        worst = max((_SEVERITY_RANK[diag.severity] for diag in self.diags), default=0)
        return (Status.FAILED if worst >= _SEVERITY_RANK["error"] else Status.OK), tuple(diag.row for diag in self.diags), len(self.diags)

    def receipt(self, op: StackOp) -> Receipt:

        census: dict[str, object] = {"diagnostics": len(self.diags), "errors": sum(1 for diag in self.diags if diag.severity == "error")}
        return Receipt.of("infra", Fact("emitted", op.value, census))


class _Verb(msgspec.Struct, frozen=True, gc=False):
    op: StackOp
    drive: _Drive
    after: _After | None = None


_PULL_DECODER: Final[msgspec.json.Decoder[_Pull]] = msgspec.json.Decoder(type=_Pull)


def _n8n_key_file(cfg: MaghzSettings) -> Path:

    cfg.n8n.workflows_dir.mkdir(parents=True, exist_ok=True)  # the n8n host_path workflows mount needs the dir to exist
    key_dir = (cfg.cache_dir / "n8n").resolve()
    key_dir.mkdir(parents=True, exist_ok=True)
    key_file = key_dir / "encryptionKey"
    try:
        with key_file.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(_N8N_KEY_HEX_BYTES))
        key_file.chmod(0o600)
    except FileExistsError:
        key_file.chmod(0o600)
    return key_file


def _define(cfg: MaghzSettings) -> None:

    import pulumi  # noqa: PLC0415 - dual-band: heavy host-side plugin stack, imported only inside the offloaded program
    import pulumi_docker as docker  # noqa: PLC0415
    import pulumi_docker_build as docker_build  # noqa: PLC0415

    infra = cfg.infra
    key_file = _n8n_key_file(cfg)  # mint-or-read the host n8n key + ensure the workflows dir before declaring the mount
    build_cache = (infra.state_dir / "buildkit-cache").resolve()
    build_cache.mkdir(parents=True, exist_ok=True)  # the local BuildKit cache backend needs its dir present before the build writes to it
    initdb = _N8N_INITDB.resolve()  # the n8n-database init script bind-mounted into the db container's initdb.d

    class MaghzStack(pulumi.ComponentResource):
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


def _changes(raw: Mapping[OpType, int] | None) -> frozendict[str, int]:

    # `getattr` floor: the wire may surface bare `str` op keys where the static type promises `OpType`.
    return frozendict({str(getattr(op, "value", op)): count for op, count in (raw or {}).items()})


def _outputs(result: object) -> _Outputs:

    # `getattr` floor: `up` carries `outputs: Mapping[str, OutputValue]` (each `.value` the plaintext
    # export under `show_secrets=True`); `down`/`preview` carry no `outputs`, so the floor yields `{}`.
    raw = getattr(result, "outputs", {})
    return frozendict({key: str(value.value) for key in _EXPORTS if (value := raw.get(key)) is not None})


def _driven[R](factory: _Factory[R], summary: _Summary[R]) -> _Drive:

    # the typed factory/summary pairing is sealed inside this closure, so the `_Verb` table row and the
    # offload rail carry only the already-projected `_Projected` and no erased result crosses a signature.
    def drive(engine: _Engine, stack: Stack) -> _Projected:
        result = factory(engine)(stack)
        text, changes = summary(result)
        return text, changes, _outputs(result)

    return drive


async def _offload(verb: _Verb, cfg: MaghzSettings) -> RuntimeRail[tuple[_Projected, _Engine]]:

    def _blocking() -> tuple[_Projected, _Engine]:
        # fresh sink + drive per attempt so a `PROC`-retried `OSError` flap never folds the failed
        # attempt's streamed diagnostics into the graded receipt; select-or-create and the verb method
        # both run in the worker thread.
        engine = _Engine()
        return verb.drive(engine, _stack(cfg)), engine

    return await guarded(RetryClass.PROC, lambda: run_sync(_blocking), subject=verb.op.value)


async def _project(verb: _Verb, projected: _Projected, engine: _Engine, cfg: MaghzSettings) -> RuntimeRail[Envelope]:

    result_text, changes, outputs = projected
    status, rows, count = engine.graded()
    Signals.emit(engine.receipt(verb.op))
    detail = StackDetail(
        op=verb.op, result=result_text, resource_changes=changes, outputs=outputs, diagnostics=count, model_pulled=verb.after is not None
    )
    if verb.after is None:
        return Ok(completed(status, detail, rows=rows))
    return (await verb.after(cfg)).map(lambda _: completed(status, detail, rows=rows))


async def _pull_embed_model(cfg: MaghzSettings) -> RuntimeRail[Envelope]:

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


def _up(engine: _Engine) -> _Method[UpResult]:

    def method(stack: Stack) -> UpResult:
        stack.refresh(on_event=engine.collect)
        return stack.up(on_event=engine.collect, continue_on_error=True)

    return method


def _down(engine: _Engine) -> _Method[DestroyResult]:

    def method(stack: Stack) -> DestroyResult:
        return stack.destroy(on_event=engine.collect, continue_on_error=True)

    return method


def _preview(engine: _Engine) -> _Method[PreviewResult]:

    def method(stack: Stack) -> PreviewResult:
        return stack.preview(on_event=engine.collect)

    return method


def _converged(result: UpResult | DestroyResult) -> tuple[str, frozendict[str, int]]:

    return result.summary.result, _changes(result.summary.resource_changes)


def _previewed(result: PreviewResult) -> tuple[str, frozendict[str, int]]:

    return "preview", _changes(result.change_summary)


_VERBS: frozendict[StackOp, _Verb] = frozendict({
    StackOp.UP: _Verb(op=StackOp.UP, drive=_driven(_up, _converged), after=_pull_embed_model),
    StackOp.DOWN: _Verb(op=StackOp.DOWN, drive=_driven(_down, _converged)),
    StackOp.STATUS: _Verb(op=StackOp.STATUS, drive=_driven(_preview, _previewed)),
})


async def run(op: StackOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:

    verb = _VERBS[op]
    # `_project` is awaitable (it binds the `after` leg), so the offload `Ok` pair meets it through a
    # `match` rather than `Result.bind`, whose mapper is synchronous — the one async-bind seam in the rail.
    match await _offload(verb, cfg):
        case Result(tag="ok", ok=(projected, engine)):
            return await _project(verb, projected, engine, cfg)
        case Result(error=boundary_fault):
            return Error(boundary_fault)


__all__ = ["StackDetail", "StackOp", "run"]
