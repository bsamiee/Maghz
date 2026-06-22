"""Typed configuration admission for the Maghz operator.

`MaghzSettings` is the single owner of every environment value; it feeds both the
cyclopts CLI and the Pulumi infrastructure program. No other code reads `os.environ`.
"""

from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, override, Self

from frozendict import frozendict
from pydantic import AnyHttpUrl, BaseModel, computed_field, ConfigDict, Field, GetPydanticSchema, model_validator, PostgresDsn, SecretStr
from pydantic_core import core_schema
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


# --- [TYPES] ---------------------------------------------------------------------------

type LogFormat = Literal["json", "console"]
type LogLevel = Literal["debug", "info", "warning", "error"]


class Remote(StrEnum):
    """The closed cloud-backup remote vocabulary; `value` is the rclone remote name and the `RCLONE_CONFIG_<REMOTE>_*` env prefix key.

    Owned here because it is the typed key of `CloudConfig.remotes` and the settings layer cannot
    depend upward on the `admin.rails.cloud` rail that consumes it. The rail imports this enum from
    `admin.settings`; it is never re-declared there.
    """

    DRIVE = "drive"
    ONEDRIVE = "onedrive"


# --- [CONSTANTS] -----------------------------------------------------------------------

_GROUP = ConfigDict(frozen=True, extra="forbid", validate_by_name=True)

_BARE_ENV: frozendict[str, tuple[str, str]] = frozendict({
    "MAGHZ_DATABASE_DSN": ("database", "dsn"),
    "DOCKER_HOST": ("infra", "docker_host"),
    "MAGHZ_REMOTE_HOST": ("remote", "host"),
    "MAGHZ_REMOTE_PORT": ("remote", "port"),
    "MAGHZ_REMOTE_USER": ("remote", "user"),
    "MAGHZ_REMOTE_KNOWN_HOSTS": ("remote", "known_hosts"),
    "MAGHZ_REMOTE_WORKROOT": ("remote", "workroot"),
    "GOOGLE_OAUTH_CLIENT_ID": ("integrations", "google_oauth_client_id"),
    "GOOGLE_OAUTH_CLIENT_SECRET": ("integrations", "google_oauth_client_secret"),
})


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
    """Pulumi Automation API inputs for the local docker stack."""

    model_config = _GROUP

    project: str = "maghz"
    stack: str = "local"
    image_tag: str = "maghz-pg:0.1.0"
    paradedb_tag: str = "0.24.1-pg18"
    ollama_image: str = "ollama/ollama:0.30.10"
    db_port: int = Field(default=15435, ge=1024, le=65535)
    ollama_port: int = Field(default=11434, ge=1024, le=65535)
    docker_host: str = Field(default=f"unix://{Path.home() / '.local/share/colima/default/docker.sock'}")
    state_dir: Path = Path(".cache/pulumi")
    image_context: Path = Path("image")


class N8nConfig(BaseModel):
    """The sole owner of every n8n knob: container image/name, port, URL shape, VPS-proxy overrides, `workflows_dir`, and the encryption-key path.

    Nested on `MaghzSettings` as `n8n`; `define()` in `admin/infra/stack.py` reads `cfg.n8n.*` for every
    n8n docker resource and `InfraConfig` carries no n8n fields. `api_url` is a `@computed_field` derived
    from `protocol`, `host`, and `port` so the canonical n8n URL can never drift from its parts and no
    `MAGHZ_N8N__API_URL` env var exists — the VPS override sets `MAGHZ_N8N__PROTOCOL=https` and
    `MAGHZ_N8N__HOST=...` and `api_url` recomputes. It returns a bare `str`, NOT an `AnyHttpUrl`, on
    purpose: the wire contract and the `httpx` `base_url` consumer require the host:port form with no
    trailing slash, which `AnyHttpUrl` normalization would inject. `webhook_url` stays independent because
    the public webhook URL behind a reverse proxy differs from the internal `api_url`; it is the typed
    `AnyHttpUrl` URL value object (the same owner `OllamaConfig.base_url` uses) so a malformed override is
    rejected at admission, and its `__str__` round-trips byte-identically into the container
    `WEBHOOK_URL` env. `N8N_ENCRYPTION_KEY` is NEVER
    stored here: `encryption_key_file` is only the path injected via `N8N_ENCRYPTION_KEY_FILE` to a
    root-owned secret file the `secrets` domain provisions. The `MAGHZ_N8N__` nested-delimiter prefix
    resolves all non-computed fields.
    """

    model_config = _GROUP

    image: str = "n8nio/n8n:2.27.3"
    container_name: str = "maghz-n8n"
    port: int = Field(default=5678, ge=1024, le=65535)
    host: str = "127.0.0.1"
    protocol: Literal["http", "https"] = "http"
    webhook_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:5678/")
    proxy_hops: int = Field(default=0, ge=0)
    connect_timeout: float = Field(default=10.0, gt=0)
    workflows_dir: Path = Path("workflows/n8n")
    encryption_key_file: str = "/run/secrets/n8n_encryption_key"

    @computed_field
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
    """External agent-tool surfaces: the `agy` Antigravity CLI and the Google Workspace MCP OAuth context.

    Carries the canonical OAuth credential names and token paths the `agy` shim and the mcp WORKSPACE
    row both consume. The two OAuth keys are injected bare (`GOOGLE_OAUTH_CLIENT_ID`,
    `GOOGLE_OAUTH_CLIENT_SECRET`) by the secrets bootstrap; `_BareEnvSource` folds those bare keys into
    this group so each consumer reads its own canonical name. `SecretStr` keeps the credentials out of
    `repr`, structlog events, and stack traces; `.get_secret_value()` is read only at the injection edge.
    """

    model_config = _GROUP

    google_oauth_client_id: SecretStr | None = Field(default=None, repr=False)
    google_oauth_client_secret: SecretStr | None = Field(default=None, repr=False)
    workspace_token_dir: Path = Path(".cache/workspace-mcp")
    workspace_oauth_redirect_uri: str | None = None
    agy_binary: Path = Path("agy")
    agy_process_timeout_s: float = Field(default=120.0, gt=0)


class McpServerSettings(BaseModel):
    """The MCP-exclusive secret references the `admin.mcp` `_SERVER_TABLE` placeholder rows resolve against.

    Carries only the secrets no other group owns: the `DATABASE_URI` the `postgres` row mirrors from
    `DatabaseConfig.dsn`, and the four provider API surfaces (`n8n`, `exa`, `perplexity`, `tavily`).
    Every value is a `${MAGHZ_MCP__<KEY>}` placeholder in the committed `.mcp.json`; the real secret is
    resolved here only inside `admin.mcp.ops._render` via `.get_secret_value()`, never at settings load.
    The Google Workspace OAuth credentials and token paths the WORKSPACE row needs are NOT duplicated
    here — `IntegrationsConfig` is their canonical owner and `_render` reads them from `cfg.integrations`.
    `database_uri` derives its default from `DatabaseConfig.dsn` (the sole owner of the DSN literal) so the
    infra seam holds by construction and no env override can drift the two apart; the five provider fields
    default `None` so an absent `MAGHZ_MCP__*` var leaves the row placeholder untouched. `repr=False` keeps
    each secret out of `repr`, structlog events, and tracebacks.
    """

    model_config = _GROUP

    database_uri: SecretStr = Field(default_factory=lambda: SecretStr(str(DatabaseConfig().dsn)), repr=False)
    n8n_api_url: SecretStr | None = Field(default=None, repr=False)
    n8n_api_key: SecretStr | None = Field(default=None, repr=False)
    exa_api_key: SecretStr | None = Field(default=None, repr=False)
    perplexity_api_key: SecretStr | None = Field(default=None, repr=False)
    tavily_api_key: SecretStr | None = Field(default=None, repr=False)


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
    def _require_default_lane(self) -> Self:  # noqa: N804 - mode="after" is an instance validator; pydantic mandates `self`, not `cls`
        """Reject a `lane_keys` that drops `"default"` at config admission, not at the first faulted drive.

        `AutomationSpec.lane` defaults to `"default"`, `_decode_spec` admits a spec only when its lane is
        in `lane_keys`, and `drive` indexes `_lane_policies(cfg)[spec.lane]` over the `Map` built from
        `lane_keys`. An override such as `MAGHZ_AUTOMATION__LANE_KEYS=["research","heavy"]` would therefore
        fault every default-lane spec at admission and break the engine's own documented one-shot path. The
        invariant `"default" in lane_keys` is enforced here, in the canonical owner of `lane_keys`, so the
        engine's `policies[spec.lane]` total-index holds by construction rather than by assumption.

        Returns:
            This validated config when `"default"` is present in `lane_keys`.

        Raises:
            ValueError: `lane_keys` omits `"default"`, the lane every unqualified `AutomationSpec` resolves to.
        """
        if "default" not in self.lane_keys:
            raise ValueError(f'lane_keys must contain "default" (the AutomationSpec.lane default); got {self.lane_keys}')
        return self


class RemoteConfig(BaseModel):
    """SSH facts for the live VPS the `remote` domain targets: host identity, push concurrency, and timeouts.

    The peer subgroup to `InfraConfig` (local Pulumi state) — `InfraConfig` owns the local docker stack,
    `RemoteConfig` owns the remote SSH target the `exec`/`deploy` rails reach over asyncssh. `host`/`user`
    default empty so an unconfigured operator validates and the CLI surfaces the missing target instead of
    a partial connect. `known_hosts` stays a raw `str` here because it is untyped env ingress: the
    `MAGHZ_REMOTE_KNOWN_HOSTS` value reaches asyncssh only after `RemoteTarget.from_config` narrows it to
    the typed `KnownHostsPolicy` (`"insecure"` literal escape hatch, every other string a `Path`) at the
    domain boundary — the policy collapse is owned there, never in this validated model. `sftp_*` thread
    into every `SFTPClient.put(max_requests=...)` under the `anyio.CapacityLimiter(sftp_push_concurrency)`
    push fan-out; the connect/keepalive columns build the one `SSHClientConnectionOptions` per connection.
    """

    model_config = _GROUP

    host: str = ""
    port: int = Field(default=22, ge=1, le=65535)
    user: str = ""
    known_hosts: str = Field(default_factory=lambda: str(Path("~/.ssh/known_hosts").expanduser()))
    workroot: str = "~/maghz"
    sftp_push_concurrency: int = Field(default=8, ge=1)
    sftp_max_requests: int = Field(default=128, ge=1)
    connect_timeout: float = Field(default=15.0, gt=0)
    keepalive_interval: float = Field(default=15.0, gt=0)
    keepalive_count_max: int = Field(default=3, ge=1)


class RemoteCredentials(BaseModel):
    """Per-remote OAuth credential surface the `_env_for` adapter folds into the rclone subprocess env.

    Every field is remote-agnostic at the type level; the rail's `match remote` arm selects which fields
    matter per remote. `service_account_credentials` holds the Drive service-account key as the raw JSON
    blob rclone's `RCLONE_CONFIG_DRIVE_SERVICE_ACCOUNT_CREDENTIALS` option parses verbatim (never a
    base64 wrapper — rclone cannot decode one), and is empty for OneDrive; `drive_id` is the OneDrive
    personal-drive selector and is empty for Drive. `token` is the VPS env fallback read when `keyring`
    resolves to the null backend. All fields default empty so an unconfigured remote validates and the
    `_env_for` adapter simply omits the absent keys.
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

    `remotes` is a typed `frozendict[Remote, RemoteCredentials]` keyed by the `Remote` enum — never a bare
    string. `GetPydanticSchema` lets pydantic validate each value as a `RemoteCredentials`, coerce the
    `MAGHZ_CLOUD__REMOTES__<REMOTE>__*` lowercase string keys into `Remote`, reject unknown remotes, then
    freeze the result into a `frozendict` the rail shares across drain tasks without a defensive copy.
    `_seed_remotes` runs first to guarantee every `tuple(Remote)` key is present so the rail's
    `cfg.cloud.remotes[remote]` indexing is total over the closed vocabulary regardless of which remotes
    the environment names. `op_timeout_s` is the `anyio.fail_after` deadline policy, not a call parameter.
    """

    model_config = _GROUP

    remotes: RemoteTable = Field(default_factory=lambda: frozendict({remote: RemoteCredentials() for remote in Remote}))
    remote_content_path: str = "maghz/content"
    remote_dump_path: str = "maghz/dumps"
    content_root: Path = Path()
    filter_file: Path = Path(".rclone-filter")
    op_timeout_s: float = Field(default=3600.0, gt=0)
    force_resync: bool = False
    keyring_service: str = "maghz"

    @model_validator(mode="before")
    @classmethod
    def _seed_remotes(cls, data: object, /) -> object:
        """Overlay the parsed `MAGHZ_CLOUD__REMOTES__<REMOTE>__*` partial onto a full `tuple(Remote)` seed before per-value validation.

        The `pydantic-settings` nested-env source delivers `remotes` as `dict[str, dict]` carrying only
        the remotes the environment names; this seeds the absent remotes with empty mappings so the typed
        table covers the entire closed vocabulary. Inputs already keyed by `Remote` (programmatic init,
        re-validation of an existing `frozendict`) are honored alongside string keys, and a per-remote
        value that is not a mapping falls through unchanged to per-value validation, which raises the
        precise pydantic error rather than being masked here. Any env-named key outside the closed
        `Remote` vocabulary (a typo such as `MAGHZ_CLOUD__REMOTES__GDRIVE__*`) is carried through into the
        seed so the typed `frozendict[Remote, RemoteCredentials]` schema rejects it at the `[key]` position
        rather than this seed silently dropping a misrouted credential block.

        Returns:
            The input unchanged unless it is a mapping carrying a `remotes` mapping, in which case a copy
            whose `remotes` slot holds one entry per `Remote` (the env-provided value or an empty mapping)
            plus any unknown provided key left in place for the closed-vocabulary schema to reject.
        """
        if isinstance(data, Mapping) and isinstance(provided := data.get("remotes"), Mapping):
            known = {remote.value: remote for remote in Remote}
            seeded = {remote.value: provided.get(remote.value, provided.get(remote, {})) for remote in Remote}
            unknown = {key: value for key, value in provided.items() if key not in known and key not in Remote}
            return {**data, "remotes": {**seeded, **unknown}}
        return data


# --- [SERVICES] ------------------------------------------------------------------------


class _BareEnvSource(EnvSettingsSource):
    """Routes flat environment keys that miss the canonical `MAGHZ_<GROUP>__<FIELD>` path to the field that owns them.

    `EnvSettingsSource` walks a nested group only through the double-underscore `MAGHZ_<GROUP>__<FIELD>`
    path, and a `validation_alias` on a sub-model field is invisible to it. Two key shapes therefore
    cannot reach their slot unaided: keys the secrets bootstrap or Docker toolchain export with a name
    the operator does not control (`MAGHZ_DATABASE_DSN`, `DOCKER_HOST`, `GOOGLE_OAUTH_CLIENT_ID`,
    `GOOGLE_OAUTH_CLIENT_SECRET`), and the single-underscore flat operator names the `remote` contract
    fixes (`MAGHZ_REMOTE_HOST`/`PORT`/`USER`/`KNOWN_HOSTS`/`WORKROOT`), whose single underscore the
    nested splitter never treats as a group boundary. `_BARE_ENV` is the one table mapping each such key
    to its `(group, field)` slot. This source folds every present key into its `{group: {field: value}}`
    overlay off the framework-loaded `self.env_vars` map (no direct `os.environ` read) and sits one rank
    below `env_settings`, so a canonical nested `__` key still wins and a programmatic init kwarg wins
    over both.
    """

    @override
    def __call__(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for env_key, (group, field) in _BARE_ENV.items():
            raw = self.env_vars.get(env_key.lower())
            if raw:
                out.setdefault(group, {})[field] = raw
        return out


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
    remote: RemoteConfig = Field(default_factory=RemoteConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    mcp: McpServerSettings = Field(default_factory=McpServerSettings)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    log: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    cache_dir: Path = Path(".cache")
    artifacts_dir: Path = Path(".artifacts")

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


@lru_cache(maxsize=1)
def settings() -> MaghzSettings:
    """The process-wide validated settings, resolved once at first call."""
    return MaghzSettings()


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "AutomationConfig",
    "CloudConfig",
    "DatabaseConfig",
    "InfraConfig",
    "IntegrationsConfig",
    "MaghzSettings",
    "McpServerSettings",
    "N8nConfig",
    "ObservabilityConfig",
    "OllamaConfig",
    "Remote",
    "RemoteConfig",
    "RemoteCredentials",
    "settings",
]
