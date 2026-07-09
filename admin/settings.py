"""Typed configuration admission: the one validated config surface the CLI, Pulumi infra, and every rail read.

`MaghzSettings` is the single owner of every environment value — no other code reads `os.environ`. It
feeds the cyclopts CLI, the Pulumi infrastructure program, and every rail through its validated subgroups
and the process-wide `settings()` accessor. This module is the public config surface; reaching past it for
a deeper symbol is a boundary leak. The beartype import claw installed at the `admin.*` package root
already type-checks every re-exported callable at its boundary.
"""

from collections.abc import Mapping
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, override, Self

from frozendict import frozendict
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, GetPydanticSchema, model_validator, PostgresDsn, SecretStr
from pydantic_core import core_schema
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


# --- [TYPES] ---------------------------------------------------------------------------

type LogFormat = Literal["json", "console"]
type LogLevel = Literal["debug", "info", "warning", "error"]


class Stage(StrEnum):
    """The closed deployment-stage vocabulary discriminating every stage-dependent row.

    `LOCAL` converges the Mac parity stack against the Colima daemon; `PRD` converges the identical
    service graph against the VPS system daemon over SSH. The tunnel maps the VPS loopback ports onto
    the local loopback one-to-one, so every rail above the docker layer (DSN, ollama, n8n, atuin
    probes) is stage-agnostic by construction — only docker-daemon-facing surfaces read this switch.
    """

    LOCAL = "local"
    PRD = "prd"


class Remote(StrEnum):
    """The closed cloud-backup remote vocabulary; `value` is the rclone remote name and the `RCLONE_CONFIG_<REMOTE>_*` env prefix key.

    Owned here because it is the typed key of `CloudConfig.remotes` and the settings layer cannot
    depend upward on the `admin.rails` rail that consumes it. The rail imports this enum from
    `admin.settings`; it is never re-declared there.
    """

    DRIVE = "drive"
    ONEDRIVE = "onedrive"


# --- [CONSTANTS] -----------------------------------------------------------------------

_GROUP = ConfigDict(frozen=True, extra="forbid")
_BARE_ENV: frozendict[str, tuple[str, str]] = frozendict({
    "CODERABBIT_API_KEY": ("integrations", "coderabbit_api_key"),
    "CONTEXT7_API_KEY": ("integrations", "context7_api_key"),
    "MAGHZ_DATABASE_DSN": ("database", "dsn"),
    "DOCKER_HOST": ("infra", "docker_host"),
    "EXA_API_KEY": ("integrations", "exa_api_key"),
    "GH_PROJECTS_TOKEN": ("integrations", "gh_projects_token"),
    "GH_TOKEN": ("integrations", "gh_token"),
    "GITHUB_TOKEN": ("integrations", "github_token"),
    "MAGHZ_REMOTE_HOST": ("remote", "host"),
    "MAGHZ_REMOTE_PORT": ("remote", "port"),
    "MAGHZ_REMOTE_USER": ("remote", "user"),
    "MAGHZ_REMOTE_KEY_FILE": ("remote", "key_file"),
    "MAGHZ_REMOTE_KNOWN_HOSTS": ("remote", "known_hosts"),
    "MAGHZ_REMOTE_WORKROOT": ("remote", "workroot"),
    "GOOGLE_WORKSPACE_PROJECT_ID": ("integrations", "google_workspace_project_id"),
    "GOOGLE_OAUTH_CLIENT_ID": ("integrations", "google_oauth_client_id"),
    "GOOGLE_OAUTH_CLIENT_SECRET": ("integrations", "google_oauth_client_secret"),
    "GREPTILE_API_KEY": ("integrations", "greptile_api_key"),
    "HOSTINGER_API_TOKEN": ("integrations", "hostinger_api_token"),
    "JUPYTER_TOKEN": ("integrations", "jupyter_token"),
    "OP_SERVICE_ACCOUNT_TOKEN": ("integrations", "op_service_account_token"),
    "PERPLEXITY_API_KEY": ("integrations", "perplexity_api_key"),
    "TAVILY_API_KEY": ("integrations", "tavily_api_key"),
})


# The docker endpoint defaults to the first reachable local socket so a Colima/Docker-Desktop/native host
# all converge without a hand-set `DOCKER_HOST`; the `_BARE_ENV` `DOCKER_HOST` route still overrides it.
# Probed in order: the Colima `~/.local/share` socket, the legacy `~/.colima` socket, the Docker Desktop
# user socket, then the system socket; the Colima default is the floor when none is present yet (a stack
# brought up later creates it, and an explicit `DOCKER_HOST` wins regardless).
def _detect_docker_host() -> str:
    """Return `unix://<socket>` for the first existing local docker socket, the Colima default as the floor."""
    candidates = (
        Path.home() / ".local/share/colima/default/docker.sock",
        Path.home() / ".colima/default/docker.sock",
        Path.home() / ".docker/run/docker.sock",
        Path("/var/run/docker.sock"),
    )
    return f"unix://{next((socket for socket in candidates if socket.exists()), candidates[0])}"


# --- [MODELS] --------------------------------------------------------------------------


class DatabaseConfig(BaseModel):
    """Connection and schema-apply inputs for the maghz ledger."""

    model_config = _GROUP

    dsn: PostgresDsn = Field(default=PostgresDsn("postgresql://maghz@127.0.0.1:15435/maghz"))
    schema_file: Path = Path("db/schema.sql")
    routines_file: Path = Path("db/routines.sql")
    cron_file: Path = Path("db/cron.sql")
    connect_timeout: int = Field(default=10, ge=1)

    @property
    def maintenance_dsn(self) -> str:
        """The same server reached on the `postgres` maintenance DB, where pg_cron and its scheduler live.

        Rebuilt through `PostgresDsn.build` over the parsed host, credentials, query, and fragment of the
        single-host ledger DSN so connection options survive while only `path` is repointed to `postgres`.
        The value object owns the round-trip, so no `urllib` string surgery is needed.
        """
        host = self.dsn.hosts()[0]
        return str(
            PostgresDsn.build(
                scheme=self.dsn.scheme,
                username=host["username"],
                password=host["password"],
                host=host["host"],
                port=host["port"],
                path="postgres",
                query=self.dsn.query,
                fragment=self.dsn.fragment,
            )
        )


class OllamaConfig(BaseModel):
    """Local embedding model server reached by the CLI (query-time) and the DB (`pg_net`)."""

    model_config = _GROUP

    base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    embed_model: str = "nomic-embed-text"
    embed_dim: int = Field(default=768, ge=1)
    request_timeout: float = Field(default=30.0, gt=0)


class InfraConfig(BaseModel):
    """Pulumi Automation API inputs for the docker service graph; `stage` discriminates the daemon.

    The Pulumi stack name equals `stage.value`, so local and prd desired state live as sibling stacks
    in the one file backend and never fight over each other's resources. `docker_host` is the LOCAL
    daemon endpoint only; the prd endpoint derives from the remote SSH facts at `MaghzSettings.docker_host`.
    `atuin_url` is the Nix-owned sync server's loopback probe row — health alignment, never lifecycle.
    """

    model_config = _GROUP

    project: str = "maghz"
    stage: Stage = Stage.LOCAL
    image_tag: str = "maghz-pg:0.1.0"
    paradedb_tag: str = "0.24.1-pg18"
    ollama_image: str = "ollama/ollama:0.30.10"
    db_port: int = Field(default=15435, ge=1024, le=65535)
    ollama_port: int = Field(default=11434, ge=1024, le=65535)
    docker_host: str = Field(default_factory=_detect_docker_host)
    atuin_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8788")
    doppler_mcp_image: str = "node:22-alpine"
    doppler_mcp_version: str = "1.0.5"
    state_dir: Path = Path(".cache/pulumi")
    image_context: Path = Path("image")


class HookConfig(BaseModel):
    """The Doppler-webhook redeploy consumer: image, port, and signing-secret custody.

    `signing_secret` (`MAGHZ_HOOK__SIGNING_SECRET`, Doppler `maghz/prd_host`) is the HMAC key the
    consumer verifies `X-Doppler-Signature` with; the Forge services estate passes the same value to
    the Doppler Webhook resource, so custody is the one Doppler row. An unset secret leaves the
    consumer failing closed. `port` is the host binding — public on prd (Doppler must reach it),
    loopback on local — while the in-container listener stays fixed on 9000.
    """

    model_config = _GROUP

    image: str = "python:3.14-alpine"
    container_name: str = "maghz-hook"
    port: int = Field(default=9000, ge=1024, le=65535)
    signing_secret: SecretStr | None = Field(default=None, repr=False)
    server_file: Path = Path("hook/server.py")


class N8nConfig(BaseModel):
    """The sole owner of every n8n knob: container image/name, port, URL shape, VPS-proxy overrides, and `workflows_dir`.

    `api_url` is a derived property over `protocol`/`host`/`port` (no `MAGHZ_N8N__API_URL` env, the VPS
    override sets `PROTOCOL`/`HOST`); it returns a bare `str`, not `AnyHttpUrl`, because the `httpx`
    `base_url` consumer needs the host:port form with no trailing slash that `AnyHttpUrl` would normalize in.
    `webhook_url` is the typed `AnyHttpUrl` and stays independent: the reverse-proxy public URL differs from
    the internal `api_url`. `encryption_key` is the PRD credential-store key (`MAGHZ_N8N__ENCRYPTION_KEY`,
    Doppler `maghz/prd_host`): the prd container receives it as `N8N_ENCRYPTION_KEY` so the key survives any
    volume loss; the local stage keeps the host-minted key FILE mount and never reads this field.
    """

    model_config = _GROUP

    image: str = "n8nio/n8n:2.27.3"
    encryption_key: SecretStr | None = Field(default=None, repr=False)
    container_name: str = "maghz-n8n"
    port: int = Field(default=5678, ge=1024, le=65535)
    host: str = "127.0.0.1"
    protocol: Literal["http", "https"] = "http"
    webhook_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:5678/")
    proxy_hops: int = Field(default=0, ge=0)
    connect_timeout: float = Field(default=10.0, gt=0)
    workflows_dir: Path = Path("workflows/n8n")

    @property
    def api_url(self) -> str:
        """Canonical n8n API URL derived from protocol, host, and port; never stored redundantly."""
        return f"https://{self.host}" if self.protocol == "https" else f"http://{self.host}:{self.port}"


class ObservabilityConfig(BaseModel):
    """structlog rendering selection; diagnostics ride stderr, never the result channel."""

    model_config = _GROUP

    level: LogLevel = "info"
    format: LogFormat = "json"


class IntegrationsConfig(BaseModel):
    """External agent-tool surfaces: the `agy` Antigravity CLI, Workspace OAuth, and remote agent token projection.

    The OAuth keys and forwarded agent tokens arrive bare and `_BareEnvSource` folds them into this
    canonical group. The Workspace MCP token cache path is machine-owned by Forge as
    `WORKSPACE_MCP_CREDENTIALS_DIR`; the Google Workspace CLI credential-file path is remote-machine
    material minted by `admin.remote`. `SecretStr` keeps credentials out of `repr`/logs; `.get_secret_value()`
    is read only at the injection edge.
    """

    model_config = _GROUP

    coderabbit_api_key: SecretStr | None = Field(default=None, repr=False)
    context7_api_key: SecretStr | None = Field(default=None, repr=False)
    exa_api_key: SecretStr | None = Field(default=None, repr=False)
    gh_projects_token: SecretStr | None = Field(default=None, repr=False)
    gh_token: SecretStr | None = Field(default=None, repr=False)
    github_token: SecretStr | None = Field(default=None, repr=False)
    google_oauth_client_id: SecretStr | None = Field(default=None, repr=False)
    google_oauth_client_secret: SecretStr | None = Field(default=None, repr=False)
    google_workspace_project_id: str | None = None
    greptile_api_key: SecretStr | None = Field(default=None, repr=False)
    hostinger_api_token: SecretStr | None = Field(default=None, repr=False)
    jupyter_token: SecretStr | None = Field(default=None, repr=False)
    op_service_account_token: SecretStr | None = Field(default=None, repr=False)
    perplexity_api_key: SecretStr | None = Field(default=None, repr=False)
    tavily_api_key: SecretStr | None = Field(default=None, repr=False)
    workspace_oauth_redirect_uri: str | None = None
    agy_binary: Path = Path("agy")
    agy_process_timeout_s: float = Field(default=120.0, gt=0)


class McpServerSettings(BaseModel):
    """The MCP-exclusive secret references whose field *names* back the `admin.mcp` `${MAGHZ_MCP__<KEY>}` placeholder rows.

    Only `McpServerSettings.model_fields` (the name set) is read — `mcp/ops.py` emits each placeholder as a
    literal `${MAGHZ_MCP__<KEY>}` (never resolved) and VALIDATE asserts every committed placeholder backs a
    name here, so the `.mcp.json` carries no secret and no field *value* is consumed. `database_uri` is one
    such name-backing declaration, not a second DSN mint: `DatabaseConfig.dsn` is the sole DSN owner and the
    rendered file substitutes `${MAGHZ_MCP__DATABASE_URI}` at `op run` time. The Google OAuth credentials are
    not duplicated — `IntegrationsConfig` owns them and the Google Workspace overlay emits them bare. n8n has
    no MCP/API token configured yet, so it declares no secret-backed field here.
    """

    model_config = _GROUP

    database_uri: SecretStr | None = Field(default=None, repr=False)


class AutomationConfig(BaseModel):
    """Admission ceilings, lane capacity, and the NDJSON ledger path for the automation engine.

    `lane_keys` pre-declares every valid `LanePolicy` key; an unknown `spec.lane` is rejected
    at `_decode_spec` admission rather than coerced. `cpu_ceil` / `rss_ceil_mb` are the
    `_governor_aspect` gate; `action_timeout_s` wraps each `_exec` via `move_on_after`.
    """

    model_config = _GROUP

    max_concurrent: int = Field(default=4, ge=1)
    cpu_ceil: float = Field(default=80.0, gt=0, le=100.0)
    rss_ceil_mb: float = Field(default=2048.0, gt=0)
    action_timeout_s: float = Field(default=120.0, gt=0)
    ledger_file: Path = Path(".artifacts/automation.ndjson")
    lane_keys: tuple[str, ...] = ("default",)

    @model_validator(mode="after")
    def _require_default_lane(self) -> Self:  # noqa: N804 - mode="after" instance validator; pydantic mandates `self`
        """Enforce `"default" in lane_keys` so the engine's `policies[spec.lane]` total-index holds by construction."""
        if "default" not in self.lane_keys:
            raise ValueError(f'lane_keys must contain "default" (the AutomationSpec.lane default); got {self.lane_keys}')
        return self


class RemoteConfig(BaseModel):
    """SSH facts for the live VPS the `remote` domain targets: host identity, push concurrency, and timeouts.

    `host`/`user` default empty so an unconfigured operator validates and the `remote` rail surfaces the
    missing target as a `config` fault rather than dialing an empty host. `key_file` is the explicit SSH
    private key the connection authenticates with; `None` (the default) lets `asyncssh` use the running
    agent (the Forge 1Password SSH agent) plus the default key locations, so the common path needs no key
    path. `known_hosts` stays a raw `str` (untyped env ingress): `RemoteTarget.from_config` narrows it to
    the typed `KnownHostsPolicy` at the domain boundary, never here. `sftp_*` bound the
    `CapacityLimiter`/`SFTPClient.put` push fan-out; the connect/keepalive columns build one `SSHClientConnectionOptions`.
    """

    model_config = _GROUP

    host: str = ""
    port: int = Field(default=22, ge=1, le=65535)
    user: str = ""
    key_file: Path | None = None
    known_hosts: str = Field(default_factory=lambda: str(Path("~/.ssh/known_hosts").expanduser()))
    workroot: str = "/srv/maghz"
    sftp_push_concurrency: int = Field(default=8, ge=1)
    sftp_max_requests: int = Field(default=128, ge=1)
    connect_timeout: float = Field(default=15.0, gt=0)
    keepalive_interval: float = Field(default=15.0, gt=0)
    keepalive_count_max: int = Field(default=3, ge=1)


class RemoteCredentials(BaseModel):
    """Per-remote OAuth credential surface the `_env_for` adapter folds into the rclone subprocess env.

    Remote-agnostic at the type level; the rail's `match remote` arm selects per-remote fields.
    `service_account_credentials` is the Drive key as raw JSON (rclone parses verbatim, never base64);
    `drive_id` is the OneDrive selector; `token` is the op-injected OAuth token
    (`MAGHZ_CLOUD__REMOTES__<REMOTE>__TOKEN`), the sole secret source — never a keychain/`rclone.conf`
    read, so a backup raises no Touch-ID/password prompt. All default empty so an unconfigured remote
    validates and `_env_for` omits the absent keys.
    """

    model_config = _GROUP

    client_id: str = ""
    client_secret: str = ""
    token: str = ""
    drive_id: str = ""
    service_account_credentials: str = ""


type RemoteTable = Annotated[
    frozendict[Remote, RemoteCredentials],
    GetPydanticSchema(lambda _source, handler: core_schema.no_info_after_validator_function(frozendict, handler(dict[Remote, RemoteCredentials]))),
]


class CloudConfig(BaseModel):
    """rclone-driven off-site backup configuration: per-remote credentials, remote/local paths, and the operation deadline.

    `remotes` is a typed `frozendict[Remote, RemoteCredentials]`; `_seed_remotes` guarantees every
    `tuple(Remote)` key is present so `cfg.cloud.remotes[remote]` is total over the closed vocabulary.
    `op_timeout_s` is the sync/restore deadline as a policy value on the config, never a per-call parameter.
    """

    model_config = _GROUP

    remotes: RemoteTable = Field(default_factory=lambda: frozendict({remote: RemoteCredentials() for remote in Remote}))
    remote_content_path: str = "maghz/content"
    remote_dump_path: str = "maghz/dumps"
    content_root: Path = Path()
    filter_file: Path = Path(".rclone-filter")
    op_timeout_s: float = Field(default=3600.0, gt=0)
    force_resync: bool = False

    @model_validator(mode="before")
    @classmethod
    def _seed_remotes(cls, data: object, /) -> object:
        """Overlay the parsed `MAGHZ_CLOUD__REMOTES__<REMOTE>__*` partial onto a full `tuple(Remote)` seed so `remotes[remote]` stays total.

        The nested-env source replaces (not merges) the `default_factory`, so absent remotes are re-seeded
        empty; `Remote` is a `StrEnum`, so member-keyed and `value`-keyed ingress collapse under `str(key)`.
        An unknown provided key survives into the seed for the `frozendict[Remote, RemoteCredentials]` schema
        to reject at the `[key]` position rather than being silently dropped here.

        Returns:
            The input, with `remotes` seeded over `tuple(Remote)` when it carries a `remotes` mapping.
        """
        if isinstance(data, Mapping) and isinstance(provided := data.get("remotes"), Mapping):
            by_value = {str(key): value for key, value in provided.items()}
            seeded = {remote.value: by_value.get(remote.value, {}) for remote in Remote}
            return {**data, "remotes": seeded | {k: v for k, v in by_value.items() if k not in seeded}}
        return data


# --- [SERVICES] ------------------------------------------------------------------------


class _BareEnvSource(EnvSettingsSource):
    """Routes flat env keys that miss the canonical `MAGHZ_<GROUP>__<FIELD>` path to their owning field via the `_BARE_ENV` table.

    Covers bootstrap/toolchain keys the operator does not control (`MAGHZ_DATABASE_DSN`, `DOCKER_HOST`,
    `GOOGLE_OAUTH_*`) and the single-underscore flat `remote` names whose lone `_` the nested splitter never
    treats as a group boundary. Folds off `self.env_vars` (no direct `os.environ`) and ranks below
    `env_settings`, so a canonical `__` key and a programmatic init kwarg both still win.
    """

    @override
    def __call__(self) -> dict[str, dict[str, str]]:
        present = frozendict({(group, field): raw for env_key, (group, field) in _BARE_ENV.items() if (raw := self.env_vars.get(env_key.lower()))})
        groups: frozendict[str, None] = frozendict.fromkeys(group for group, _ in present)
        return {group: {field: raw for (g, field), raw in present.items() if g == group} for group in groups}


class MaghzSettings(BaseSettings):
    """The one validated config object threaded through every operator surface."""

    model_config = SettingsConfigDict(
        env_prefix="MAGHZ_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        frozen=True,
        extra="forbid",
        nested_model_default_partial_update=True,
    )

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    infra: InfraConfig = Field(default_factory=InfraConfig)
    n8n: N8nConfig = Field(default_factory=N8nConfig)
    hook: HookConfig = Field(default_factory=HookConfig)
    remote: RemoteConfig = Field(default_factory=RemoteConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    mcp: McpServerSettings = Field(default_factory=McpServerSettings)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    log: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    cache_dir: Path = Path(".cache")
    artifacts_dir: Path = Path(".artifacts")

    @property
    def docker_host(self) -> str:
        """The stage-resolved docker daemon endpoint every provider and docker-CLI spawn targets.

        LOCAL reads the detected/overridden local socket; PRD derives `ssh://<user>@<host>` from the
        one remote SSH owner, so the daemon endpoint and the SSH target can never drift apart.
        """
        return f"ssh://{self.remote.user}@{self.remote.host}" if self.infra.stage is Stage.PRD else self.infra.docker_host

    @property
    def docker_env(self) -> frozendict[str, str]:
        """The `DOCKER_HOST` overlay row injected into every docker-CLI subprocess (`docker cp`/`exec`)."""
        return frozendict({"DOCKER_HOST": self.docker_host})

    @model_validator(mode="after")
    def _require_prd_rows(self) -> Self:  # noqa: N804 - mode="after" instance validator; pydantic mandates `self`
        """PRD admission: the SSH target and the n8n credential-store key must exist before any converge."""
        if self.infra.stage is Stage.PRD:
            missing = [
                name
                for name, present in (
                    ("MAGHZ_REMOTE_HOST", bool(self.remote.host)),
                    ("MAGHZ_REMOTE_USER", bool(self.remote.user)),
                    ("MAGHZ_N8N__ENCRYPTION_KEY", self.n8n.encryption_key is not None),
                    ("MAGHZ_HOOK__SIGNING_SECRET", self.hook.signing_secret is not None),
                )
                if not present
            ]
            if missing:
                raise ValueError(f"stage=prd requires {', '.join(missing)} (doppler maghz/prd_host)")
        return self

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, _BareEnvSource(settings_cls), dotenv_settings, file_secret_settings)


# --- [COMPOSITION] ---------------------------------------------------------------------


@cache
def settings() -> MaghzSettings:
    """The process-wide validated settings, resolved once at first call."""
    return MaghzSettings()


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "AutomationConfig",
    "CloudConfig",
    "DatabaseConfig",
    "HookConfig",
    "InfraConfig",
    "IntegrationsConfig",
    "LogFormat",
    "LogLevel",
    "MaghzSettings",
    "McpServerSettings",
    "N8nConfig",
    "ObservabilityConfig",
    "OllamaConfig",
    "Remote",
    "RemoteConfig",
    "RemoteCredentials",
    "RemoteTable",
    "Stage",
    "settings",
]
