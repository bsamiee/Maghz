# [WORKLIST: MCP-AS-IAC]

Realize-ready worklist folded from `docs/design/mcp.md`. The blueprint is the design; this is the execution order. `admin/mcp/` is the source of truth for the MCP server fleet; the committed `.mcp.json` is the generated artifact carrying `${VAR}` placeholders. Secrets inject at process boundary via `op run -- claude`, never written to the file.

---

## [01]-[OWNERS]

| [FILE] | [ACTION] | [SECTIONS] | [OWNS] |
| --- | --- | --- | --- |
| `admin/mcp/model.py` | create | `[TYPES]`+`[MODELS]`+`[TABLES]` | `ServerKind` StrEnum (closed fleet vocabulary), `McpOp` StrEnum (op discriminant), `ServerSpec` `msgspec.Struct(frozen=True, gc=False)` wire record, `McpConfigDetail(Detail)` typed receipt, `_SERVER_TABLE: frozendict[ServerKind, ServerSpec]` correspondence table (in `[TABLES]`, after `[MODELS]`, because it references the `ServerSpec` runtime class) |
| `admin/mcp/ops.py` | create | `[ERRORS]`+`[SERVICES]`+`[OPERATIONS]` | `McpFault` closed `@tagged_union(frozen=True)`; one `structlog.get_logger()` handle (`[SERVICES]`); private sync `_render(cfg) -> Result[dict[str, object], McpFault]`, async `_write(fleet, path) -> Result[McpConfigDetail, McpFault]`, async `_validate(path) -> Result[McpConfigDetail, McpFault]`, async `_generate(cfg)`; single polymorphic `async def mcp(op: McpOp, cfg: MaghzSettings) -> Envelope` entrypoint that matches on `McpOp`, folds `Result` to `completed()`/`fault()`, and emits the inline telemetry |
| `admin/mcp/__init__.py` | create | `[EXPORTS]` | public re-export of `McpConfig` (the `McpServerSettings` group alias as referenced by the blueprint) and `mcp`; `__all__` surface |
| `admin/settings/config.py` | modify | `[MODELS]` | add `McpServerSettings(BaseModel)` group (`model_config = _GROUP`) with per-server `SecretStr | None` fields (all `repr=False`), plus `workspace_token_dir`/`workspace_oauth_redirect_uri`; add `mcp: McpServerSettings = Field(default_factory=McpServerSettings)` to `MaghzSettings`; extend `__all__` |
| `admin/__main__.py` | modify | `[CONSTANTS]`+`[COMPOSITION]` | add `_MCP = Group("MCP", sort_key=...)`; mount an `_mcp` sub-`App` with `generate`/`validate` commands binding `rails.mcp(McpOp.GENERATE|VALIDATE, settings())` |
| `admin/rails/__init__.py` | modify | re-export | re-export `mcp` and `McpOp` from `admin.mcp` so the entrypoint types the polymorphic `mcp` parameter (matches the existing `Kind`/`StackOp` re-export pattern) |
| `.mcp.json` | regenerate (artifact) | n/a | the `maghz mcp generate` output: top-level `mcpServers` object with exactly seven keys, `indent=2`, `${MAGHZ_MCP__*}` placeholders; committed to git, never hand-edited |

`admin/mcp/` is a peer module under `admin/`; it does not own `MaghzSettings` and never reads `os.environ`. All server rows are declared in `admin/mcp/model.py`; `McpServerSettings` carries only the typed secret values those rows reference. The `ServerKind`+`_SERVER_TABLE` pair is the absorbing surface: a new server lands as one `ServerKind` case + one `_SERVER_TABLE` row; every consumer (`_render`, acceptance check, count assertion) updates via exhaustive `match`/`assert_never`. A future `DIFF`/`AUDIT` op lands as a new `McpOp` case dispatched from the same `mcp()` entrypoint plus a new `McpFault` case — no new entrypoint, no new module.

---

## [02]-[ADTs]

| [ADT] | [KIND] | [DISCRIMINANT] | [CASES] | [CLOSURE] |
| --- | --- | --- | --- | --- |
| `ServerKind` | `StrEnum` | enum value (`str`) | `POSTGRES="postgres"`, `N8N="n8n"`, `EXA="exa"`, `PERPLEXITY="perplexity"`, `TAVILY="tavily"`, `WORKSPACE="workspace"`, `NOTEBOOKLM="notebooklm"` | total `match` over `ServerKind` in `_render` row-to-JSON projection, closed by `assert_never` |
| `McpOp` | `StrEnum` | enum value (`str`) | `GENERATE="generate"`, `VALIDATE="validate"` | `match op` in `mcp()` dispatches to `_generate` / `_validate`, closed by `assert_never` |
| `McpFault` | `expression.tagged_union(frozen=True)` | `tag: Literal["render","write","validate"]` | `render: str = case()`, `write: str = case()`, `validate: str = case()` | `match` in the envelope adapter inside `mcp()`, closed by `assert_never`; each case carries the raw provider message (not a re-phrased template) |
| `McpConfigDetail` | `Detail` subclass (`msgspec.Struct(frozen=True, tag=True)`) | tag (msgspec union tag) | fields `op: McpOp`, `path: str`, `server_count: int`, `servers: tuple[str, ...]` | emitted in `Envelope.report.detail`; `servers` carries `ServerKind.value` strings as load-bearing evidence |
| `ServerSpec` | `msgspec.Struct(frozen=True, gc=False)` | n/a (record) | `command: str`, `args: tuple[str, ...]`, `env: frozendict[str, str]`, `docker_env: frozendict[str, str]` | one table row per `ServerKind`; `gc=False` is load-bearing (only `str`/`frozendict` fields, no cycles) |

`McpFault` is one fault owner with three cases — no parallel `RenderFault`/`WriteFault`/`ValidateFault`. `_write` maps `OSError` as `McpFault(write=str(exc))`; `_validate` maps `msgspec.DecodeError` as `McpFault(validate=str(exc))`. Both catches are explicit (not bare `except Exception`).

---

## [03]-[API_MEMBERS]

| [PACKAGE] | [MEMBER] | [USE] |
| --- | --- | --- |
| `expression` | `tagged_union` | decorator for the `McpFault` closed union owner |
| `expression` | `tag` | the `McpFault.tag` discriminant field |
| `expression` | `case` | each `McpFault` case slot |
| `expression` | `Result[T, McpFault]` | return rail for `_render`, `_write`, `_validate`, `_generate` |
| `expression` | `Ok` / `Error` | `match`-bind in `_generate` (sync `_render` result bound before the async `_write`; no `effect.result` builder across the async boundary) |
| `msgspec` | `Struct(frozen=True, gc=False)` | `ServerSpec` wire record |
| `msgspec` | `Struct(frozen=True, tag=True)` | `McpConfigDetail` via `Detail` inheritance |
| `msgspec` | `json.Encoder()` | module-level `ENCODER`; `ENCODER.encode(fleet_dict)` serializes the rendered fleet |
| `msgspec` | `json.Decoder(type=dict[str, object])` | module-level `DECODER`; `DECODER.decode(buf)` round-trip schema validation in `_validate` |
| `msgspec` | `json.format(buf, indent=2)` | `_write` formats before write so the committed `.mcp.json` is human-readable |
| `pydantic` | `SecretStr` | secret fields on `McpServerSettings`; `.get_secret_value()` called only inside `_render` (never at settings load) |
| `pydantic` | `Field(repr=False)` | every `SecretStr` field carries `repr=False` so secrets never reach `repr`/logs/stack traces |
| `pydantic` | `BaseModel` + `ConfigDict` (via `_GROUP`) | `McpServerSettings` group (frozen, extra=forbid, validate_by_name) |
| `pydantic` | `Field(default_factory=...)` | `mcp: McpServerSettings` nested group on `MaghzSettings` |
| `pydantic-settings` | `SettingsConfigDict(env_prefix="MAGHZ_", env_nested_delimiter="__", nested_model_default_partial_update=True)` | already on `MaghzSettings`; `MAGHZ_MCP__<KEY>` resolves the nested group |
| `anyio` | `Path(path).write_bytes(buf)` | async write of the generated JSON in `_write` |
| `anyio` | `Path(path).read_bytes()` | async round-trip read in `_validate` |
| `structlog` | `get_logger()` | one `[SERVICES]` handle; inline `log.info("mcp.generate", ...)` on success, `log.error("mcp.fault", ...)` on failure inside `mcp()` after rail collapse |
| `cyclopts` | `App` / `App.command` / `Group` | mounts `maghz mcp generate` / `maghz mcp validate` (existing CLI grammar owner) |
| `admin.core.model` | `Detail`, `Envelope`, `Report`, `Row`, `completed`, `fault` | `McpConfigDetail` extends `Detail`; `mcp()` folds to `completed(status, detail, rows=...)` / `fault(...)`; `Report.rows` carry `Row(key=kind.value, text="ok")` per server |
| `admin.core.status` | `Status` (`Status.OK`, `Status.FAULTED`) | the envelope status projected from the rail result |

`frozendict` is the immutable-map carrier for `ServerSpec.env` / `ServerSpec.docker_env` — confirm the active `frozendict` provider during realize (stdlib `types.MappingProxyType` is the fallback if `frozendict` is not already admitted; see DEPS).

`msgspec.json.schema(type=McpConfigDetail)` is the advanced-surface path reserved for a future `AUDIT` op; not realized now.

---

## [04]-[DEPS]

No new external packages are required by the blueprint. Every surface composes from already-admitted dependencies: `pydantic`, `pydantic-settings`, `msgspec`, `expression`, `anyio`, `structlog`, `cyclopts`.

| [PACKAGE] | [BAND] | [STATUS] | [.api CATALOG NOTE] |
| --- | --- | --- | --- |
| `pydantic` / `pydantic-settings` | pure-venv | already admitted | `Rasm/libs/python/.api/pydantic-settings.md` — `SecretStr`, `Field(repr=False)`, nested-group + `MAGHZ_MCP__` partial-update resolution (authoritative; no new note) |
| `msgspec` | pure-venv | already admitted | `Rasm/libs/python/.api/msgspec.md` — `Struct(gc=False)`, `json.Encoder`/`json.Decoder`/`json.format`, tagged `Detail` inheritance (authoritative; no new note) |
| `expression` | pure-venv | already admitted | `Rasm/libs/python/.api/expression.md` — `tagged_union`/`tag`/`case`, `Result[T,E]`, `Ok`/`Error` match-bind (authoritative; no new note) |
| `anyio` | pure-venv | already admitted | `Rasm/libs/python/.api/anyio.md` — `anyio.Path.write_bytes`/`read_bytes` async file I/O (authoritative; no new note) |
| `structlog` | pure-venv | already admitted | `Rasm/libs/python/.api/structlog.md` — `get_logger`, inline event emission (authoritative; no new note) |

DEP-PREP STEP: none. No package admission, no `.api` catalog authoring. If the active `frozendict` provider is not already in `pyproject.toml`, that is the only admission decision — resolve it against the existing settings/model owners during realize rather than introducing a parallel immutable-map type.

The seven MCP server binaries (`postgres-mcp`, `n8n-mcp` via Docker, `exa-mcp-server`, `perplexity-mcp`, `tavily-mcp`, `workspace-mcp`, `notebooklm-mcp`) are runtime invocation targets emitted as command/args rows in `.mcp.json` — they are NOT Python dependencies and are NOT admitted to `pyproject.toml`. Their runtime availability (`uvx`/`npx`/`docker`/PATH binary) is the VPS/Forge concern per §08.

---

## [05]-[RIPPLES]

| [DOMAINS] | [CLAIM] |
| --- | --- |
| `mcp` ↔ `settings` | `McpServerSettings` is a nested group inside `MaghzSettings` (owned by `settings`/`admin/settings/config.py`). Every secret the `mcp` domain introduces is a `MAGHZ_MCP__*` field there; `settings()` is the sole resolver — no `os.environ` reads in `admin/mcp/`. `settings` owns the resolver; `mcp` owns the placeholder strings. |
| `mcp` ↔ `n8n` | The `ServerKind.N8N` row in `_SERVER_TABLE` (`command="docker"`, args ending `ghcr.io/czlonkowski/n8n-mcp:latest`, `docker_env` carrying `MCP_MODE=stdio`/`LOG_LEVEL=error`/`DISABLE_CONSOLE_OUTPUT=true`/`N8N_API_URL`/`N8N_API_KEY`) is the EXCLUSIVE n8n-mcp surface. The `n8n` domain owns the live instance URL + API-key 1Password reference (the values); `mcp` owns the invocation shape (the row). `admin/rails/n8n.py` never invokes the MCP server directly. |
| `mcp` ↔ `integrations` | The `ServerKind.WORKSPACE` row carries `args=["workspace-mcp","--tool-tier","extended"]` and env keys `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `TOKEN_DIR`, conditional `OAUTH_REDIRECT_URI`. `integrations` owns the canonical row requirements (tool-tier arg, token-dir key, redirect-URI key, credential field names); `mcp`'s table row + `McpServerSettings.workspace_token_dir`/`workspace_oauth_redirect_uri` absorb them as authoritative data. `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` emit as BARE `${KEY}` placeholders (not `MAGHZ_MCP__`-prefixed) matching `setup-env.sh` injection; `_validate` exempts these two from the "every placeholder has a `MAGHZ_MCP__` field" check. `integrations` maintains no parallel `.mcp.json` block. |
| `mcp` ↔ `infra` | `DATABASE_URI` in the `ServerKind.POSTGRES` row must stay in sync with `MaghzSettings.database.dsn`. `McpServerSettings.database_uri` default (`postgresql://maghz@127.0.0.1:15435/maghz`) MUST equal `DatabaseConfig.dsn` default. `infra` owns the Pulumi-managed port assignment; `mcp` consumes it as the default. Drift is a seam conflict. |
| `mcp` ↔ `secrets` | The `MAGHZ_MCP__*` variable set that `op run` injects is the Forge `env.template` wiring (Phase 0). `secrets` owns the 1Password item references for every `MAGHZ_MCP__*` key; `mcp` owns only the `${MAGHZ_MCP__*}` placeholder strings emitted in `.mcp.json`. |

---

## [06]-[DEPENDS_ON]

| [DOMAIN_KEY] | [WHY MUST EXIST FIRST] |
| --- | --- |
| `settings` | `McpServerSettings` is added to `MaghzSettings` (owned by `admin/settings/config.py`); `mcp(op, cfg)` takes `cfg: MaghzSettings`. The settings owner and `_GROUP`/`SettingsConfigDict` policy must be realized before the `mcp` group attaches. `DatabaseConfig.dsn` default is the source of the `database_uri` default the infra seam pins. |
| `runtime` | The repo law (`runtime` blueprint) states every domain composes on the `admin/runtime/` owners — `admin.core` (`Detail`/`Envelope`/`Report`/`Row`/`Status`/`completed`/`fault`) is the receipt/status substrate `mcp()` folds into. These owners already exist in `admin/core/`; they must be realized before `mcp` can emit envelopes. |

`mcp` does NOT depend on `n8n`, `integrations`, `infra`, or `secrets` owners to exist before realize: those are RIPPLE counterparts that supply data values for `_SERVER_TABLE` rows and 1Password references, not Python owners `admin/mcp/` imports. The placeholder strings in `_SERVER_TABLE` are self-contained literals; the counterpart domains resolve them at process boundary, not at `mcp` realize time. `mcp` composes no `stamina` retry and no `admin/runtime/` resilience owner (filesystem-only, no transient remote boundary) — its sole `runtime` dependency is the `admin.core` envelope substrate.

---

## [07]-[ACCEPTANCE]

Gate signals (run only the owner-scoped Python rail at the planned milestone):

- `ruff check admin/mcp/` and `ruff format --check admin/mcp/` — zero diagnostics.
- `ty check admin/mcp/` — zero errors (all=error policy).
- `mypy admin/mcp/` — zero errors under strict mode.
- `maghz mcp generate` exits `0`, writes `.mcp.json` with `indent=2`, parses as valid JSON with a top-level `mcpServers` object containing exactly seven keys.
- `maghz mcp validate` exits `0` against the written file; `McpConfigDetail.server_count == 7` in the returned envelope.
- `DECODER.decode(Path(".mcp.json").read_bytes())` succeeds without `DecodeError`.
- `settings().mcp` resolves without `ValidationError` in default env (local dev); `SecretStr` fields are `None` when the corresponding `MAGHZ_MCP__*` var is absent; no `SecretStr` value appears in `repr(settings())`.
- `Envelope.status == Status.OK` for both `generate` and `validate` paths under the `anyio` runner.
- Every `${MAGHZ_MCP__*}` placeholder in the generated file has a corresponding `McpServerSettings` field; `${GOOGLE_OAUTH_CLIENT_ID}` and `${GOOGLE_OAUTH_CLIENT_SECRET}` are exempt (bare-env keys injected by `setup-env.sh` at the process boundary).
- `ServerKind.WORKSPACE` row carries `args=["workspace-mcp","--tool-tier","extended"]`, `env` includes `TOKEN_DIR` (from `workspace_token_dir`), conditional `OAUTH_REDIRECT_URI` emitted only when `workspace_oauth_redirect_uri` is non-`None`.
- `McpServerSettings` carries `workspace_token_dir: str = ".cache/workspace-mcp"` and `workspace_oauth_redirect_uri: str | None = None`.
- `ServerKind.N8N` Docker invocation contains no bare `-e KEY=VAL` args not derived from `_SERVER_TABLE`; `docker_env` rows are the sole source (each folded as `("-e","KEY=VAL")`).
- `ServerKind.POSTGRES` row uses `command: "uvx"` (matching the live `.mcp.json`, not `"uv"`).
- No `SecretStr.get_secret_value()` call appears outside `_render` in `admin/mcp/ops.py`.
- `McpFault.write` carries the raw `OSError` message string; `McpFault.validate` carries the raw `DecodeError` message string — no re-phrased template.
- `McpServerSettings.database_uri` default equals `DatabaseConfig.dsn` default (`postgresql://maghz@127.0.0.1:15435/maghz`) — infra seam consistency.
