# [DESIGN: MCP-AS-IAC]

`admin/mcp/` owns the MCP server fleet as typed code: a pydantic-settings model for every server row, a `maghz mcp` entrypoint that dispatches on `McpOp` to emit the committed `.mcp.json` (with `${VAR}` placeholders) or to round-trip-validate it. The committed `.mcp.json` is the generated artifact; `admin/mcp/` is the source of truth. Secrets inject at process boundary via `op run -- claude`, never in the file.

---

## [01]-[OWNERS]

| [FILE] | [SECTION] | [OWNS] |
| --- | --- | --- |
| `admin/mcp/__init__.py` | `[EXPORTS]` | public re-export of `McpConfig`, `mcp` |
| `admin/mcp/model.py` | `[TYPES]`+`[MODELS]`+`[TABLES]` | closed `ServerKind` StrEnum; `McpOp` StrEnum; `ServerSpec` wire record; `_SERVER_TABLE` correspondence table; `McpConfigDetail` typed receipt |
| `admin/mcp/ops.py` | `[ERRORS]`+`[OPERATIONS]` | `McpFault` closed tagged-union; private `_render`, `_write`, `_validate` transforms; single `mcp(op, cfg)` polymorphic entrypoint |
| `admin/settings/config.py` | `[MODELS]` | `McpServerSettings` nested group added to `MaghzSettings`; per-server secret references as `pydantic.SecretStr` fields |

`admin/mcp/` is a peer module under `admin/`; it does not own `MaghzSettings` and does not read `os.environ`. All server rows are declared in `admin/mcp/model.py`; settings carries only the typed secret values those rows reference.

**COUNTERFACTUAL-OWNER test:** no denser canonical owner absorbs this. The `existing-rails` domain owns CLI lifecycle ops; the `mcp` domain owns a static-artifact generation cycle that is categorically different (no DB, no Pulumi, no process spawn). The split is correct.

**ANTICIPATORY-COLLAPSE decision:** the `ServerKind`+`_SERVER_TABLE` pair is the absorbing surface. When a new server lands (e.g., `n8n-mcp` as a row, `browserbase`, a custom sidecar), it lands as one `ServerKind` case + one `_SERVER_TABLE` row. Every consumer — `_render`, the acceptance check, the CLI count assertion — updates automatically via exhaustive `match`/`assert_never`. The blueprint is already structured for this; the review tightens it below.

---

## [02]-[ADTs]

### `ServerKind` — closed fleet vocabulary

```python
class ServerKind(StrEnum):
    POSTGRES    = "postgres"
    N8N         = "n8n"
    EXA         = "exa"
    PERPLEXITY  = "perplexity"
    TAVILY      = "tavily"
    WORKSPACE   = "workspace"
    NOTEBOOKLM  = "notebooklm"
```

Total `match` over `ServerKind` drives the row-to-JSON projection in `_render`; `assert_never` closes exhaustiveness. Adding a server = one new case + one new row in `_SERVER_TABLE`; no branch proliferation.

**SURFACE-SPRAWL fix:** the original design did not specify where the `n8n-mcp` MCP server row lives — that row belongs in `_SERVER_TABLE` as `ServerKind.N8N` (`command="npx"`, `args=["-y","n8n-mcp"]`). The `n8n` blueprint seam states that `.mcp.json` is the single owner of the `n8n-mcp` row. This blueprint IS that owner; it must declare the row explicitly (see `_SERVER_TABLE` below). Without this, the row only exists in the sibling n8n blueprint's text description but not in the typed code owner.

### `McpOp` — mcp command discriminant

```python
class McpOp(StrEnum):
    GENERATE = "generate"
    VALIDATE = "validate"
```

The single `mcp(op: McpOp, cfg: MaghzSettings) -> Envelope` entrypoint in `ops.py` matches on `McpOp` and dispatches; no `generate`/`validate` name-suffix function proliferation at the public surface.

### `McpFault` — closed tagged fault union

```python
@tagged_union(frozen=True)
class McpFault:
    tag: Literal["render", "write", "validate"] = tag()
    render:   str = case()
    write:    str = case()
    validate: str = case()
```

One fault owner, three cases, each carrying the diagnostic string. `assert_never` closes the match in the envelope adapter. No parallel `RenderFault`/`WriteFault`/`ValidateFault` types.

**BOUNDARY-INTEGRITY fix:** the original `McpFault` carried bare `str` diagnostics. The fault law requires cause preservation: each `case` must carry the original provider message, not a re-phrased summary. The realize pass must ensure `_write` maps `OSError` as `McpFault(write=str(exc))` and `_validate` maps `msgspec.DecodeError` as `McpFault(validate=str(exc))` — provider message goes in, not a fixed template string.

### `McpConfigDetail` — typed operation receipt

```python
class McpConfigDetail(Detail, tag=True):
    op:           McpOp
    path:         str
    server_count: int
    servers:      tuple[str, ...]
```

Extends `admin.core.model.Detail` (`msgspec.Struct(frozen=True, tag=True)`). Emitted inside `Envelope.report.detail`; `Report.rows` carry per-server key/status lines.

**NO-TABLE-STAKES fix:** `servers: tuple[str, ...]` carries `ServerKind.value` strings. Agents parsing the envelope can enumerate which servers were rendered without re-reading the source — this is load-bearing evidence, not redundant noise. Keep the field.

### `mcp` — single polymorphic entrypoint

```python
async def mcp(op: McpOp, cfg: MaghzSettings) -> Envelope: ...
```

`op` is the modal discriminant; the match dispatches to private `_render → _write` (generate path) or `_validate` (validate path). No public siblings.

**ANTICIPATORY-COLLAPSE decision:** if a `DIFF` or `AUDIT` op ever lands (compare emitted file against table, or check placeholder coverage), it lands as a new `McpOp` case dispatched from the same entrypoint. No new entrypoint, no new module. The `McpFault` union gains a new case.

---

## [03]-[.api SURFACE]

### pydantic + pydantic-settings (`admin/settings/config.py`)

- `pydantic.SecretStr` — secret fields on `McpServerSettings`; `.get_secret_value()` called only inside `_render`, never at settings load.
- `pydantic.BaseModel` + `ConfigDict(frozen=True, extra="forbid", validate_by_name=True)` — `McpServerSettings` group (same `_GROUP` policy as sibling settings groups).
- `MaghzSettings` extended: `mcp: McpServerSettings = Field(default_factory=McpServerSettings)` under `env_prefix="MAGHZ_"` + `env_nested_delimiter="__"`, so `MAGHZ_MCP__DATABASE_URI`, `MAGHZ_MCP__N8N_API_URL`, etc. resolve from the injected op environment.
- `SettingsConfigDict(nested_model_default_partial_update=True)` already set on `MaghzSettings`; partial env overrides work without full group specification.

**ADVANCED-SURFACE fix:** the original design omitted `pydantic.Field(repr=False)` on `SecretStr` fields. Every `SecretStr` field must carry `repr=False` so secrets do not appear in logs, stack traces, or structlog events that call `repr()` on the settings object. This is a `pydantic.Field(repr=False)` annotation at the field level, not a model-level flag.

### msgspec (`admin/mcp/model.py` + `admin/core/model.py`)

- `msgspec.Struct(frozen=True, gc=False)` — `ServerSpec` wire record. `gc=False` is load-bearing here: `ServerSpec` holds only `str` and `frozendict[str, str]` fields; no circular references, GC tracking is wasted overhead.
- `msgspec.json.Encoder()` module-level instance — `ENCODER.encode(fleet_dict)` serializes the rendered fleet.
- `msgspec.json.Decoder(type=dict[str, object])` module-level instance — `DECODER.decode(buf)` for round-trip schema validation.
- `McpConfigDetail` inherits `Detail` which is `msgspec.Struct(frozen=True, tag=True)`.
- `msgspec.json.format(buf, indent=2)` — the `_write` path calls `format` before writing so the committed `.mcp.json` is human-readable (standard practice for committed config files). The original design wrote raw compact bytes; this is the correct behavior for a git-tracked file.
- `msgspec.structs.force_setattr` is not used; all construction is through `__init__`.

**ADVANCED-SURFACE addition:** `msgspec.json.schema(type=McpConfigDetail)` is available for a future `AUDIT` op that generates the JSON Schema for the receipt. Not required now but the `json.schema` function is the correct advanced-surface path if that op lands.

### expression (`admin/mcp/ops.py`)

- `expression.tagged_union(frozen=True)` + `expression.tag()` + `expression.case()` — the `McpFault` owner.
- `expression.Result[T, McpFault]` — `_render`, `_write`, `_validate` all return `Result`; `mcp()` folds to `completed()/fault()` at the envelope boundary.
- `expression.effect.result` builder — sequential `_render → _write` pipeline in the generate path uses `yield from` do-notation rather than nested lambda ladders.

**RAIL-LAW fix (critical):** the original code sketch mixes `async def` and `effect.result` incorrectly. The `effect.result` builder uses synchronous generator-coroutine protocol (`yield from`); it cannot `await` inside the generator body. The `_write` path must be split: `_render` is sync (pure fold over the table), `_write` is `async def` wrapping `anyio.Path.write_bytes`, and the `effect.result` builder only wraps the `_render` step. The `mcp()` entrypoint sequences `_render` → (result bind) → `await _write(fleet)` without a single `effect.result` builder spanning both — because `_write` is async and the builder is sync. The corrected shape:

```python
async def _generate(cfg: MaghzSettings) -> Result[McpConfigDetail, McpFault]:
    rendered: Result[dict[str, object], McpFault] = _render(cfg)
    match rendered:
        case Ok(fleet):
            return await _write(fleet, _MCP_JSON_PATH)
        case Error(_) as err:
            return err
```

`_render` is a pure sync function returning `Result[dict[str, object], McpFault]`. `_write` is async, returning `Result[McpConfigDetail, McpFault]`. The `match` bind is idiomatic and does not require the effect builder across an async boundary.

### anyio (`admin/mcp/ops.py`)

- `anyio.Path(path).write_bytes(buf)` — async file write of the generated JSON (already async at the anyio layer; no `to_thread` needed for small file writes on modern kernels).
- `anyio.Path(path).read_bytes()` — round-trip read in `_validate`.
- No task group needed; operations are sequential and local-filesystem only.

**NO-TABLE-STAKES gap:** `anyio.Path` wraps `pathlib.Path` via the asyncio event loop. For a file under a few KB (`.mcp.json` will never exceed 10KB), `anyio.Path.write_bytes` is semantically correct. However, the original design used `anyio.Path(path).write_bytes(buf)` which on the asyncio backend calls `loop.run_in_executor(None, path.write_bytes, data)` — this is correct behavior. No change needed.

---

## [04]-[RAILS + ASPECTS]

### Rail selection

`Result[T, McpFault]` from `expression` is the rail for all private transforms. `McpFault` is a closed `@tagged_union` (three cases: `render`, `write`, `validate`), each carrying a `str` diagnostic. `assert_never` closes the match at the envelope adapter boundary in `mcp()`.

The generate path sequences `_render` then `_write` with an explicit `match` bind (not `effect.result` across an async boundary — see §03 rail-law fix above):

```python
async def _generate(cfg: MaghzSettings) -> Result[McpConfigDetail, McpFault]:
    match _render(cfg):
        case Ok(fleet):
            return await _write(fleet, _MCP_JSON_PATH)
        case Error(_) as err:
            return err
```

No `anyio` task group is needed — operations are sequential (render → write → validate). The `anyio.run` boundary in `__main__.py` is the sole structured-concurrency owner.

### Aspects

No retry (`stamina`) applies — all operations are local filesystem writes and pure transforms with no transient remote boundary. Telemetry is the sole cross-cutting concern: one `structlog.get_logger()` handle (a `[SERVICES]` entry) drives inline `log.info("mcp.generate", ...)` on success and `log.error("mcp.fault", ...)` on failure, both inside `mcp()` after rail collapse. With one concern, no `@aspect` factory is warranted; the inline structlog call is the canonical form.

**LONG-TAIL coverage:** when `GENERATE` or `VALIDATE` ops propagate an `OSError` from the filesystem (disk full, permissions error), the `_write` boundary must catch it and return `Error(McpFault(write=str(exc)))` — never let a raw `OSError` escape to the CLI meta handler. The `_validate` boundary catches `msgspec.DecodeError` from `DECODER.decode(buf)` and returns `Error(McpFault(validate=str(exc)))`. Both catches are explicit (not bare `except Exception`), per the boundary-conversion law.

---

## [05]-[PAYLOADS + TABLES]

### `ServerSpec` — the per-server wire record

```python
class ServerSpec(msgspec.Struct, frozen=True, gc=False):
    command:    str
    args:       tuple[str, ...]
    env:        frozendict[str, str]
    docker_env: frozendict[str, str]
```

`frozendict[str, str]` enforces the immutable-map policy on both `env` (top-level Claude Code `env` map) and `docker_env` (Docker `-e KEY=${VAR}` pairs that `_render` folds into the `args` list for Docker invocations). `docker_env` is empty for all non-Docker servers. Keeping both in the table row means `_render` performs a pure fold over each row with no server-specific branching: if `docker_env` is non-empty, the render fold inserts `-e KEY=VALUE` pairs into the args sequence.

### Correspondence table — the fleet declaration

`_SERVER_TABLE: frozendict[ServerKind, ServerSpec]` lives in `[TABLES]` of `model.py`, after `[MODELS]`, because it depends on `ServerSpec` (a runtime class object). Placing it in `[CONSTANTS]` would violate the Python overlay law that runtime tables follow the models they reference.

| `ServerKind` | `command` | `args` | `env` keys | `docker_env` keys |
| --- | --- | --- | --- | --- |
| `POSTGRES` | `uvx` | `["postgres-mcp", "--access-mode=restricted"]` | `DATABASE_URI` | _(none)_ |
| `N8N` | `docker` | `["run","-i","--rm","--init","ghcr.io/czlonkowski/n8n-mcp:latest"]` | _(none)_ | `MCP_MODE`, `LOG_LEVEL`, `DISABLE_CONSOLE_OUTPUT`, `N8N_API_URL`, `N8N_API_KEY` |
| `EXA` | `npx` | `["-y","exa-mcp-server"]` | `EXA_API_KEY` | _(none)_ |
| `PERPLEXITY` | `npx` | `["-y","perplexity-mcp"]` | `PERPLEXITY_API_KEY` | _(none)_ |
| `TAVILY` | `npx` | `["-y","tavily-mcp"]` | `TAVILY_API_KEY` | _(none)_ |
| `WORKSPACE` | `uvx` | `["workspace-mcp", "--tool-tier", "extended"]` | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `TOKEN_DIR` _(+ conditional `OAUTH_REDIRECT_URI`)_ | _(none)_ |
| `NOTEBOOKLM` | `notebooklm-mcp` | `[]` | _(none)_ | _(none)_ |

The WORKSPACE row carries `args=["workspace-mcp", "--tool-tier", "extended"]` — not `["workspace-mcp"]`. `TOKEN_DIR` is sourced from `McpServerSettings.workspace_token_dir` (default `".cache/workspace-mcp"`). `OAUTH_REDIRECT_URI` is a conditional env key: emitted by `_render` only when `McpServerSettings.workspace_oauth_redirect_uri` is non-`None`. `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are bare env keys (not `MAGHZ_MCP__*`-prefixed — see §07 integrations seam); they are injected by `setup-env.sh` at process boundary, not resolved by `McpServerSettings`'s own prefix path for these two fields specifically.

**SURFACE-SPRAWL fix — `POSTGRES` command:** the committed `.mcp.json` uses `"command": "uvx"` with `args: ["postgres-mcp", "--access-mode=restricted"]`. The original blueprint had `"command": "uv"` with `args: ["run", "postgres-mcp", ...]`. The live `.mcp.json` is authoritative: `uvx` is the correct command. The table is corrected above.

**N8N render:** `docker_env` carries `MCP_MODE=stdio`, `LOG_LEVEL=error`, `DISABLE_CONSOLE_OUTPUT=true` as static values plus `N8N_API_URL=${MAGHZ_MCP__N8N_API_URL}` and `N8N_API_KEY=${MAGHZ_MCP__N8N_API_KEY}` as placeholder values. The `_render` fold inserts each `docker_env` pair as `("-e", "KEY=VAL")` into the rendered args list. No server-specific branch in `_render`; the table row is complete.

**`${VAR}` substitution:** `env` map values and `docker_env` values carry `${MAGHZ_MCP__<KEY>}` placeholder strings as literals in the table. `_render` does not call `.get_secret_value()` — it emits placeholders. Only `_validate` verifies JSON schema; it does not resolve secrets.

**COUNTERFACTUAL-OWNER for placeholder scheme:** an alternative design resolves secrets at generate time and commits the resolved file. This is rejected because secrets must never be committed to git. The placeholder design is the only correct approach; the current design is sound.

### `McpServerSettings` — secret group added to `MaghzSettings`

```python
class McpServerSettings(BaseModel):
    model_config = _GROUP
    database_uri:                  SecretStr       = Field(default=SecretStr("postgresql://maghz@127.0.0.1:15435/maghz"), repr=False)
    n8n_api_url:                   SecretStr | None = Field(default=None, repr=False)
    n8n_api_key:                   SecretStr | None = Field(default=None, repr=False)
    exa_api_key:                   SecretStr | None = Field(default=None, repr=False)
    perplexity_api_key:            SecretStr | None = Field(default=None, repr=False)
    tavily_api_key:                SecretStr | None = Field(default=None, repr=False)
    google_oauth_client_id:        SecretStr | None = Field(default=None, repr=False)
    google_oauth_client_secret:    SecretStr | None = Field(default=None, repr=False)
    workspace_token_dir:           str              = Field(default=".cache/workspace-mcp")
    workspace_oauth_redirect_uri:  str | None       = Field(default=None)
```

`workspace_token_dir` feeds the `TOKEN_DIR` placeholder in the WORKSPACE row. `workspace_oauth_redirect_uri` feeds the conditional `OAUTH_REDIRECT_URI` placeholder when non-`None`. Both fields are driven by integrations requirements (see §07 seam); this is the canonical absorption point. `google_oauth_client_id` and `google_oauth_client_secret` remain in `McpServerSettings` under `MAGHZ_MCP__` prefix as `SecretStr | None` for any direct use; the WORKSPACE row's `env` block for those two keys uses bare key names (not `MAGHZ_MCP__`-prefixed) because `setup-env.sh` emits them as bare `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — the `_render` function emits those placeholder strings without the `MAGHZ_MCP__` prefix, and `_validate` excludes them from the "every placeholder has a corresponding McpServerSettings field" check.

All optional fields default `None`; a `None` field means no env override — the placeholder string in `_SERVER_TABLE` travels to the file unchanged. The `database_uri` default matches `DatabaseConfig.dsn`. All `SecretStr` fields carry `repr=False` so they never appear in structlog output, repr, or stack traces.

**SEAM-INTEGRITY fix:** `McpServerSettings` must also carry `n8n_api_url` and `n8n_api_key` as explicit fields (above). The `N8N` row in `_SERVER_TABLE` references `${MAGHZ_MCP__N8N_API_URL}` and `${MAGHZ_MCP__N8N_API_KEY}` — these must have corresponding `McpServerSettings` fields or the acceptance criterion ("every placeholder has a corresponding field") fails. The original blueprint listed these but the table review confirms they are present and correct.

### `McpConfigDetail` — the operation receipt

Fields: `op`, `path`, `server_count`, `servers`. Emitted as `Envelope.report.detail` from the `completed()` call. `Report.rows` carry per-server `Row(key=kind.value, text="ok")` lines so agents can parse individual server status.

**RECEIPT-LAW check:** `McpConfigDetail` does not extend to a generic envelope. Each field carries evidence: `op` distinguishes generate from validate, `path` is the filesystem artifact, `server_count` is the machine-verifiable count, `servers` is the enumerated kinds. All are load-bearing. The receipt is correctly typed.

---

## [06]-[DEPS]

No new packages are required. All surfaces compose from already-admitted dependencies:

- `pydantic` + `pydantic-settings` — `McpServerSettings`, `SecretStr`, nested settings.
- `msgspec` — `ServerSpec`, `McpConfigDetail`, `Detail` inheritance, `Encoder`/`Decoder`, `json.format`.
- `expression` — `Result[T, McpFault]` rail, `@tagged_union`, explicit `match`-bind sequencing.
- `anyio` — `anyio.Path` async file I/O.
- `structlog` — inline observability handle.
- `cyclopts` — CLI binding of `maghz mcp generate` / `maghz mcp validate`.

`.api` catalog note: no new catalog needed. The `pydantic-settings.md`, `msgspec.md`, `expression.md`, `anyio.md`, and `structlog.md` catalogs in `Rasm/libs/python/.api/` are the authoritative advanced-surface references.

---

## [07]-[SEAMS]

**settings** (`mcp` ↔ `settings`): `McpServerSettings` is a nested group inside `MaghzSettings`. Every new secret the `mcp` domain introduces must appear in `McpServerSettings` with a `MAGHZ_MCP__*` env key; `settings()` is the sole resolver — no `os.environ` reads inside `admin/mcp/`.

**n8n + automations** (`mcp` ↔ `n8n` / `automations`): the N8N row in `_SERVER_TABLE` carries `N8N_API_URL` and `N8N_API_KEY` placeholder references. The n8n and automations blueprints supply the canonical values (live n8n instance URL, API key 1Password reference). The `mcp` domain owns only the invocation shape; n8n/automations own what the server connects to. The `n8n` blueprint states that `admin/rails/n8n.py` never invokes the MCP server directly — the `.mcp.json` row is the exclusive n8n-mcp surface, and that row is owned by this blueprint's `_SERVER_TABLE`.

**integrations** (`mcp` ↔ `integrations`): the `WORKSPACE` row in `_SERVER_TABLE` carries `args=["workspace-mcp", "--tool-tier", "extended"]` and `env` keys `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `TOKEN_DIR`, plus conditional `OAUTH_REDIRECT_URI`. The canonical values for these are declared by the `integrations` blueprint and absorbed by `McpServerSettings` as `workspace_token_dir` (for `TOKEN_DIR`) and `workspace_oauth_redirect_uri` (for `OAUTH_REDIRECT_URI`). `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are stored in `McpServerSettings` under `MAGHZ_MCP__*` prefix as `SecretStr | None` for any direct use, but the WORKSPACE row's `env` block emits them as bare keys (`${GOOGLE_OAUTH_CLIENT_ID}` / `${GOOGLE_OAUTH_CLIENT_SECRET}`) — not `MAGHZ_MCP__`-prefixed — matching the `setup-env.sh` injection from the integrations blueprint. The `_validate` acceptance criterion excludes these two bare-key placeholders from the "every placeholder has a corresponding McpServerSettings MAGHZ_MCP__ field" check. `setup-env.sh` emits both bare env keys so each consumer reads from its own prefix path; no duplication, two distinct consumers of the same secret pair. The `integrations` domain does not maintain a parallel `.mcp.json` block; there is one generated file owned by this blueprint.

**infra / secrets bootstrap** (`mcp` ↔ `infra`): `DATABASE_URI` in the `POSTGRES` row must stay in sync with `MaghzSettings.database.dsn`. `McpServerSettings.database_uri` default must match `DatabaseConfig.dsn` default (`postgresql://maghz@127.0.0.1:15435/maghz`). The infra blueprint owns the Pulumi-managed port assignment; the `mcp` domain consumes it as the default. Drift between the two is a seam conflict.

**secrets / Phase 0 env.template** (`mcp` ↔ `secrets`): the `MAGHZ_MCP__*` variable set that `op run` injects is the Forge `env.template` wiring done in Phase 0. The secrets domain owns the 1Password item references for every `MAGHZ_MCP__*` key; the `mcp` domain owns only the `${MAGHZ_MCP__*}` placeholder strings emitted in the generated `.mcp.json`.

---

## [08]-[PORTABILITY / VPS]

The generated `.mcp.json` is committed to git and travels to the VPS unchanged. `${VAR}` placeholders resolve from the VPS process environment, not the local machine.

On the VPS:
- The operator launches Claude via `op run -- claude` (or equivalent service-account injection) so `MAGHZ_MCP__*` variables are present when Claude Code reads `.mcp.json`.
- `notebooklm-mcp` runs as a system binary on PATH per AGENTS.md; no `uvx`/`npx` install needed at runtime.
- `uvx` required for `postgres-mcp` and `workspace-mcp`; `docker` required for N8N (Colima/Docker runtime provisioned by Forge); `npx`/`node` required for `exa-mcp-server`, `perplexity-mcp`, `tavily-mcp`.
- The `workspace-mcp` Google OAuth token cache lands in the process HOME under `TOKEN_DIR`; on the VPS this is the service account home. Token persistence across restarts is the operator's responsibility (mount or volume). `OAUTH_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob` must be set in the VPS environment for headless first-auth (per the integrations blueprint §08).
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` are bare env keys (not `MAGHZ_MCP__*`-prefixed — see §07 integrations seam) and require browser-based or out-of-band first-authorization. All other servers authenticate via API key only, injected by `op run`.
- `maghz mcp validate` must pass on the VPS after deploy; it is the acceptance gate for the MCP config surface on that host.

---

## [09]-[ACCEPTANCE]

- `ruff check admin/mcp/` and `ruff format --check admin/mcp/` — zero diagnostics.
- `ty check admin/mcp/` — zero errors (all=error policy).
- `mypy admin/mcp/` — zero errors under strict mode.
- `maghz mcp generate` exits `0`, writes `.mcp.json` with `indent=2` (human-readable), and the emitted file parses as valid JSON with a top-level `mcpServers` object containing exactly seven keys.
- `maghz mcp validate` exits `0` against the written file; `McpConfigDetail.server_count == 7` in the returned envelope.
- `DECODER.decode(Path(".mcp.json").read_bytes())` succeeds without `DecodeError`.
- `settings().mcp` resolves without `ValidationError` in the default env (local dev); `SecretStr` fields are `None` when the corresponding `MAGHZ_MCP__*` var is absent; no `SecretStr` value appears in `repr(settings())` output.
- `Envelope.status == Status.OK` for both `generate` and `validate` paths under the anyio runner.
- Every `${MAGHZ_MCP__*}` placeholder in the generated file has a corresponding `McpServerSettings` field; `${GOOGLE_OAUTH_CLIENT_ID}` and `${GOOGLE_OAUTH_CLIENT_SECRET}` are exempt (bare-env keys injected by `setup-env.sh` at the process boundary, not `MAGHZ_MCP__`-prefixed placeholders).
- WORKSPACE row carries `args=["workspace-mcp", "--tool-tier", "extended"]`, `env` includes `TOKEN_DIR` (from `McpServerSettings.workspace_token_dir`), and conditional `OAUTH_REDIRECT_URI` (emitted only when `McpServerSettings.workspace_oauth_redirect_uri` is non-`None`).
- `McpServerSettings` carries `workspace_token_dir: str = ".cache/workspace-mcp"` and `workspace_oauth_redirect_uri: str | None = None`.
- N8N Docker invocation in the generated file contains no bare `-e KEY=VAL` args that are not derived from `_SERVER_TABLE`; `docker_env` rows are the sole source.
- `POSTGRES` row uses `command: "uvx"`, matching the live `.mcp.json` (not `"uv"`).
- No `SecretStr.get_secret_value()` call appears outside `admin/mcp/ops.py`'s `_render` function.
- `McpFault.write` case carries the raw `OSError` message string; `McpFault.validate` case carries the raw `DecodeError` message string — no re-phrased template.
