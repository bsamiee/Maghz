# integrations — Design Blueprint

Three external AI/Workspace integrations surface as agent tools: `agy` (Google Antigravity CLI, successor to Gemini CLI as of June 18 2026), `codex-plugin-cc` (OpenAI Codex from inside Claude Code), and `workspace-mcp` (taylorwilsdon Google Workspace MCP server, `uvx workspace-mcp`). The Gemini CLI is dead for individual accounts; `agy` replaces it unconditionally. `GEMINI_API_KEY` is an optional side-channel for nano/flash-tier calls only — it does not replace OAuth. A `GEMINI_API_KEY` bypass via API key auth is a pending feature in `antigravity-cli` (issue #78, open as of 2026-06-22) and is not yet supported; design against OAuth as the authoritative flow.

**Ownership boundary**: The `workspace-mcp` server is a row in the mcp blueprint's `_SERVER_TABLE` (`ServerKind.WORKSPACE`). The integrations domain owns the canonical shape requirements for that row (tool-tier argument, token-dir env key, VPS redirect-URI env key, credential field names); the mcp blueprint's table row and `McpServerSettings` absorb those requirements as authoritative data. The integrations domain does not maintain a parallel `.mcp.json` block; there is one generated file and one owner.

---

## [01] OWNERS

| Owner file | Section | What it owns |
| --- | --- | --- |
| `.claude/skills/agy/SKILL.md` | skill | `agy` invocation: prompt, task delegation, model-tier dispatch |
| `.claude/skills/agy/scripts/agy.py` | operations | Python shim: validates `agy` on PATH, dispatches by `AgyOp`, emits `AgyReceipt` or `AgyFail` JSON |
| `.claude/skills/codex/SKILL.md` | skill | `codex:review`, `codex:adversarial-review`, `codex:rescue`/`status`/`result`/`cancel` |
| `admin/settings/config.py` | `[MODELS]` | `IntegrationsConfig` group nested into `MaghzSettings` — carries `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `workspace_token_dir`, `workspace_process_timeout_s`, and `agy_process_timeout_s` |
| `.gitignore` | — | token cache dirs and credential files |

`IntegrationsConfig` is the only Python-land addition; it extends `MaghzSettings` as a new nested group under the existing `env_nested_delimiter="__"` regime. No new Python module file; the addition lands in `admin/settings/config.py` alongside `DatabaseConfig`, `OllamaConfig`, `InfraConfig`.

The `agy` and `codex` skill scripts follow the `exa-tools`/`perplexity-tools`/`tavily-tools` pattern already realized in `.claude/skills/`: a `SKILL.md` frontmatter + instructions file plus a `scripts/` Python module that wraps the binary.

The `workspace-mcp` server row is owned exclusively by the mcp blueprint's `_SERVER_TABLE` (`ServerKind.WORKSPACE`) and its `McpServerSettings`. Integrations declares the requirements; mcp absorbs them as the source of truth. The seam is explicit in [07].

---

## [02] ADTs

### agy subcommand discriminant

```python
type AgyOp = Literal["prompt", "task", "status", "cancel", "result"]
```

`"prompt"` is the single synchronous op — it covers all textual requests including review, research, summarization, and adversarial critique. The calling agent constructs the prompt payload; the shim does not distinguish prompt intent. Introducing `"review"` as a distinct `AgyOp` would be a name-suffix modality (`MODAL_ARITY` violation): there is no `agy review` subcommand; it would be `agy -p "<review prompt>"` — identical to any other prompt. The task family (`"task"`, `"status"`, `"cancel"`, `"result"`) covers the asynchronous background-job lifecycle.

One modal entrypoint `agy(op: AgyOp, *, args: Sequence[str]) -> None` writes egress JSON to stdout. `match op` with `assert_never` exhausts all cases. `"prompt"` is synchronous (blocking `agy -p`); `"task"`, `"status"`, `"cancel"`, `"result"` are asynchronous job-management ops against `agy task ...`.

### agy fault vocabulary (closed)

```python
type AgyFault = Literal["binary_not_found", "auth_required", "quota_exceeded", "process_error"]
```

`"timeout"` is removed. `anyio.run_process()` raises `TimeoutError` only when a `move_on_after` scope wraps the call. The shim wraps the call with `anyio.move_on_after(cfg.integrations.agy_process_timeout_s)`, so `TimeoutError` maps to `"process_error"` (transient — the process did not complete in budget). Keeping a distinct `"timeout"` case would require re-projecting `process_error` into timeout at the caller, which is a no-information split. One fault carrier for all process-level transient failures is the correct collapse.

**Retry predicate**: `stamina.retry` wraps `anyio.run_process()` directly. At that level, `anyio.ExceptionGroup` containing `CalledProcessError` with a 137/143 (kill) exit code, or a bare `anyio.BrokenWorkerProcess`, signals transient. The predicate inspects `exc` before fault mapping:

```python
def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, ExceptionGroup):
        return any(isinstance(e, ProcessLookupError) for e in exc.exceptions)
    return isinstance(exc, (ProcessLookupError, BrokenPipeError))
```

Auth failures (`exit 1` + stderr match) and quota failures (`exit 2` + stderr match) are non-retryable and project to `"auth_required"` / `"quota_exceeded"` post-mapping. The retry predicate fires only before mapping; the mapping fires after the final attempt.

### agy wire receipts — closed egress family

```python
class AgyReceipt(msgspec.Struct, frozen=True, gc=False):
    op: AgyOp
    output: Option[str]      # Nothing for job-management ops; Some(text) for prompt
    task_id: Option[str]     # Some(id) for task-create and task-status

class AgyFail(msgspec.Struct, frozen=True, gc=False):
    op: AgyOp
    fault: AgyFault
    detail: str              # stderr or exception message; never optional
```

`Option[str]` (from `expression`) replaces `str | None` on both `output` and `task_id`. The `msgspec` `enc_hook`/`dec_hook` pair for `Option` is established in the automation blueprint — the agy shim registers the same pair on its module-level encoder/decoder. One codec registration per module; no per-field override.

`Ok(receipt)` → `msgspec.json.encode(receipt)` on stdout; `Error(fail)` → `msgspec.json.encode(fail)` on stdout. The arm is distinguished by presence of `fault` field — no generic `status`/`error` envelope.

### codex skill — no Python shim

`codex-plugin-cc` is a Claude Code plugin installed via `/plugin marketplace add openai/codex-plugin-cc`. Its skills (`/codex:review`, `/codex:adversarial-review`, `/codex:rescue`, etc.) are delivered by the plugin system itself. The Maghz codex `SKILL.md` is an invocation guide contextualizing these slash commands for Maghz research/refine actions. No Python shim is written for codex.

### IntegrationsConfig fields

```python
class IntegrationsConfig(BaseModel):
    model_config = _GROUP
    google_oauth_client_id:     str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_SECRET")
    workspace_token_dir:        Path = Path(".cache/workspace-mcp")
    workspace_oauth_redirect_uri: str | None = None   # set to "urn:ietf:wg:oauth:2.0:oob" on headless VPS
    agy_binary:                 Path = Path("agy")    # resolved on PATH; override for VPS non-PATH installs
    agy_process_timeout_s:      float = Field(default=120.0, gt=0)  # move_on_after budget per agy call
```

`GEMINI_API_KEY` is NOT admitted here. That field has no current consumer in `agy` (issue #78 is open). Admitting a dead field violates `SHAPE_BUDGET`; add it when `antigravity-cli` ships the feature.

`MaghzSettings` gains `integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)`. Canonical env paths: `MAGHZ_INTEGRATIONS__GOOGLE_OAUTH_CLIENT_ID`, `MAGHZ_INTEGRATIONS__GOOGLE_OAUTH_CLIENT_SECRET`, `MAGHZ_INTEGRATIONS__WORKSPACE_TOKEN_DIR`, `MAGHZ_INTEGRATIONS__WORKSPACE_OAUTH_REDIRECT_URI`, `MAGHZ_INTEGRATIONS__AGY_BINARY`, `MAGHZ_INTEGRATIONS__AGY_PROCESS_TIMEOUT_S`.

`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` also map directly into `McpServerSettings` fields (mcp blueprint) as `MAGHZ_MCP__GOOGLE_OAUTH_CLIENT_ID` / `MAGHZ_MCP__GOOGLE_OAUTH_CLIENT_SECRET`. The integrations config carries these for the `agy` auth context and the `setup-env.sh` injection; the mcp blueprint carries them for the generated server row. Both fields must be set identically; the integrations config is the canonical source name, and the setup hook emits both bare keys (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`) so each consumer reads from its own path.

**`McpServerSettings` additions driven by this blueprint** (the mcp blueprint absorbs these; listed here as the seam contract):

- `workspace_token_dir: str = ".cache/workspace-mcp"` — feeds `TOKEN_DIR` placeholder in the WORKSPACE row's env block.
- `workspace_oauth_redirect_uri: str | None = None` — feeds `OAUTH_REDIRECT_URI` placeholder when non-None.
- `google_oauth_client_id: SecretStr | None = None` — already present in mcp blueprint.
- `google_oauth_client_secret: SecretStr | None = None` — already present in mcp blueprint.

The WORKSPACE row in `_SERVER_TABLE` must carry `args=["workspace-mcp", "--tool-tier", "extended"]` and `env` keys `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `TOKEN_DIR`, plus a conditional `OAUTH_REDIRECT_URI` key (emitted by `_render` when `McpServerSettings.workspace_oauth_redirect_uri` is non-None). This conditional is the one structural branch in `_render` driven by a settings value; it does not require a new `ServerSpec` case because it is a single optional env key injection, not a structural difference in the server spec.

---

## [03] .api SURFACE

### agy (`antigravity-cli` Go binary)

`agy` is a closed-source Go binary (v1.0.0+, June 2026). There is no Python SDK. Full surface consumed:

- `agy -p "<prompt>" [--model <tier>]` — single-turn synchronous prompt. `--model` selects `gemini-3-pro`, `gemini-3-flash`, `gemini-3-nano` (or tier aliases). Exit 0 on success. Stdout is the response; stderr is diagnostics.
- `agy task create "<prompt>"` — spawns a background autonomous task; returns a task ID on stdout.
- `agy task status <id>` — JSON task state on stdout.
- `agy task result <id>` — completed task output.
- `agy task cancel <id>` — cancels a running task.
- `agy auth login` — browser OAuth flow (interactive). On VPS: `agy auth login --no-browser` emits a URL + device code.
- `agy --version` — version probe.

The Python shim in `scripts/agy.py` wraps `anyio.run_process()` inside `anyio.move_on_after(cfg.integrations.agy_process_timeout_s)` to call the binary, captures stdout/stderr as `bytes`, maps exit code + stderr patterns to `AgyFault`, and projects to the wire receipt pair. Nothing is hand-rolled — the shim delegates entirely to the `agy` binary surface.

Headless non-TTY: the shim passes `-p`/`--prompt` unconditionally, bypassing the TUI. When `agy` gains a `--output json` flag, replace raw stdout parse with `--output json` decode.

### workspace-mcp (`workspace-mcp` PyPI package, v1.21.3, 2026-06-17)

Consumed via `uvx workspace-mcp` — no Python import. The canonical row lives in the mcp blueprint's `_SERVER_TABLE` (`ServerKind.WORKSPACE`). The authoritative specification for this row is:

```
command:  uvx
args:     ["workspace-mcp", "--tool-tier", "extended"]
env keys: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, TOKEN_DIR
          + conditional OAUTH_REDIRECT_URI (headless VPS only)
```

`--tool-tier extended` covers Gmail, Drive, Calendar, Docs, Sheets, Slides, Tasks, Contacts, Forms, Search, Chat, Apps Script. `--tool-tier core` is lighter (Gmail, Drive, Calendar, Tasks); `--tool-tier complete` adds all 12 services. `extended` is the correct default for research/refine automation use.

OAuth 2.0 (stdio mode, default) is the local flow. `TOKEN_DIR` is the canonical token persistence path (`workspace-mcp`'s documented env key). `OAUTH_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob` enables headless consent on VPS (see [08]).

OAuth 2.1 multi-user (`MCP_ENABLE_OAUTH21=true` + `--transport streamable-http`) is out of scope for the single-user local + VPS pattern here.

**`.api` catalog**: author `.claude/skills/agy/workspace-mcp.api.md` listing the 12 service groups, tool-tier membership, and env-var contract for the implement pass. No Rasm `.api/` catalog entry (not a `libs/python` import).

### codex-plugin-cc (`openai/codex-plugin-cc`, v1.0.4, 2026-04-18)

Installed as a Claude Code plugin:

```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex-plugin-cc
```

Provides: `/codex:review`, `/codex:adversarial-review`, `/codex:rescue`, `/codex:status`, `/codex:result`, `/codex:cancel`. Requires Node.js 18.18+ and a ChatGPT subscription (or `OPENAI_API_KEY`). The plugin bundles its own `SKILL.md` + `hooks.json`; Maghz does not vendor these. `OPENAI_API_KEY` must be emitted by `setup-env.sh`.

---

## [04] RAILS + ASPECTS

### Rail selection

The `agy` shim is a boundary-only script: it calls the binary via `anyio.run_process()`, maps the outcome to `Result[AgyReceipt, AgyFault]`, then projects to egress JSON. The `Result` rail is chosen once at the `anyio.run_process()` boundary and carried through the match — never re-projected mid-pipeline.

`FileNotFoundError` (binary missing) → `Error("binary_not_found")`. Non-zero exit mapped via stderr pattern match to `"auth_required"` or `"quota_exceeded"`. `TimeoutError` (from `move_on_after` scope expiry) → `Error("process_error")`. The `except` clause names exact exception types; no bare `except Exception`.

### Structured concurrency

`anyio.move_on_after(cfg.integrations.agy_process_timeout_s)` wraps `anyio.run_process()` — this is the timeout scope. The shim entry point is driven by a direct `anyio.run()` call from the CLI entrypoint. No `asyncio.gather` anywhere.

### Aspects

One named aspect applies at the shim boundary:

```python
@stamina.retry(on=_is_transient, attempts=2, wait_initial=0.5)
async def _run_process(cmd: Sequence[str]) -> anyio.abc.CompletedProcess: ...
```

Scope: wraps `anyio.run_process()` inside the `move_on_after` scope. The predicate `_is_transient` (specified in [02]) fires only on transient spawn failures — not on auth, quota, or timeout. Stacking order: `move_on_after` scope (outermost) → `stamina.retry` → raw `anyio.run_process()`.

No additional aspect stacking in the shim. Future addition of telemetry or contract checking alongside retry collapses into one parameterized aspect factory per `DEFINITION_TIME_ASPECTS`.

---

## [05] PAYLOADS + TABLES

### agy wire egress — two-arm receipt family

`AgyReceipt` and `AgyFail` (both `msgspec.Struct, frozen=True, gc=False`) are the closed egress pair, described in [02]. `Option[str]` fields encode via the shared `enc_hook`/`dec_hook` pair (same codec pattern as the automation blueprint's `Embed`/`Sync` fields). No generic envelope; the struct type encodes the arm.

### IntegrationsConfig (pydantic `BaseModel` nested in `MaghzSettings`)

Follows the `_GROUP = ConfigDict(frozen=True, extra="forbid", validate_by_name=True)` pattern as all sibling config groups. Fields described in [02]. `google_oauth_client_id` and `google_oauth_client_secret` are `str | None` (absence is valid at settings boot; the shim and MCP row fail at use time if absent, not at settings load).

### frozendict/Map policy

No `frozendict` or `Map` usage directly in this domain. The model tier correspondence table lives as `MappingProxyType[str, str]` in the shim module under `[CONSTANTS]` — composed of primitive string literals with no model or runtime dependency:

```python
_TIER: MappingProxyType[str, str] = MappingProxyType({
    "pro":   "gemini-3-pro",
    "flash": "gemini-3-flash",
    "nano":  "gemini-3-nano",
})
```

Default tier for Maghz automation use: `"pro"` (Gemini 3 Pro / Ultra plan). The SKILL.md documents `"flash"` for latency-sensitive inline lookups.

### Typed receipts

`AgyReceipt` (success arm) and `AgyFail` (fault arm) are the only receipt types. No generic ledger, no `IReceipt`, no `dict[str, Any]` payload. `AgyReceipt.output: Option[str]` carries `Nothing` for job-management ops and `Some(text)` for prompt ops; `AgyReceipt.task_id: Option[str]` carries `Some(id)` for task-create and task-status, `Nothing` otherwise.

---

## [06] DEPS

No new Python packages required in `pyproject.toml`. All three integrations are external binary/plugin/uvx surfaces, not imported Python libraries. `msgspec`, `anyio`, `stamina`, and `expression` are already admitted.

| Surface | Install mechanism | Band |
| --- | --- | --- |
| `agy` (antigravity-cli) | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` — installs to `~/.local/bin/agy`; Forge provisions it | machine-level binary |
| `workspace-mcp` | `uvx workspace-mcp` (uvx pulls from PyPI at invocation time) | mcp blueprint `_SERVER_TABLE` row |
| `codex-plugin-cc` | `/plugin marketplace add openai/codex-plugin-cc` then `/plugin install` inside Claude Code | Claude Code plugin system |
| Node.js 18.18+ | required by `codex-plugin-cc`; Forge provisions it | machine-level |

**`.api` catalog note**: author `.claude/skills/agy/workspace-mcp.api.md` listing service groups, tool-tier membership, and env-var contract before the implement pass. No Rasm `.api/` catalog entry needed (not a `libs/python` dependency).

---

## [07] SEAMS

Cross-domain canonical shapes, names, and receipts this blueprint shares with other domains. Each entry identifies the counterpart blueprint that owns the other side.

**workspace server shape ↔ mcp blueprint**

```json
{"domains": ["integrations", "mcp"], "claim": "The WORKSPACE row in _SERVER_TABLE (mcp blueprint) must carry args=[\"workspace-mcp\", \"--tool-tier\", \"extended\"] and env keys GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, TOKEN_DIR (from McpServerSettings.workspace_token_dir), plus conditional OAUTH_REDIRECT_URI (from McpServerSettings.workspace_oauth_redirect_uri when non-None). Integrations declares these requirements; mcp absorbs them as authoritative row data via McpServerSettings.workspace_token_dir (str, default '.cache/workspace-mcp') and McpServerSettings.workspace_oauth_redirect_uri (str | None, default None). There is no parallel .mcp.json block in integrations; the mcp blueprint is the single generated-file owner."}
```

**OAuth secret pair ↔ mcp blueprint + secrets-bootstrap**

```json
{"domains": ["integrations", "mcp", "secrets-bootstrap"], "claim": "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are stored and injected by secrets-bootstrap (keyring or .env + setup-env.sh). IntegrationsConfig carries them as str | None under MAGHZ_INTEGRATIONS__ prefix for agy OAuth context. McpServerSettings carries them as SecretStr | None under MAGHZ_MCP__ prefix for any direct use. The WORKSPACE row in _SERVER_TABLE emits these as bare env keys (${GOOGLE_OAUTH_CLIENT_ID}, ${GOOGLE_OAUTH_CLIENT_SECRET} — NOT MAGHZ_MCP__-prefixed) because setup-env.sh injects them bare so each consumer reads from its own prefix path. Two distinct consumers; no duplication; _validate excludes these two bare-key placeholders from the per-field McpServerSettings check."}
```

**agy + codex skills ↔ automations**

```json
{"domains": ["integrations", "automations"], "claim": "The automations domain invokes agy (for Gemini Pro reasoning) and /codex:adversarial-review via SKILL.md descriptions. Receipt contract: agy success projects AgyReceipt.output (Option[str], decode via Some(text)), codex:review returns a structured review block. The automation engine's DeepResearch/Refine/CreateEntry actions decode params: msgspec.Raw to the skill's parameter struct defined here. Automations compose through the skill, never re-derive the invocation surface."}
```

**OPENAI_API_KEY ↔ secrets-bootstrap / setup-env.sh**

```json
{"domains": ["integrations", "secrets-bootstrap"], "claim": "OPENAI_API_KEY must appear in setup-env.sh _ENV_KEYS and be emitted to the Claude env file; secrets-bootstrap owns storage, integrations owns the requirement declaration."}
```

**workspace_token_dir + workspace_oauth_redirect_uri ↔ mcp blueprint McpServerSettings**

```json
{"domains": ["integrations", "mcp"], "claim": "IntegrationsConfig.workspace_token_dir and workspace_oauth_redirect_uri declare the canonical field names and defaults. McpServerSettings carries workspace_token_dir (str, default '.cache/workspace-mcp') and workspace_oauth_redirect_uri (str | None, default None) so _render can emit TOKEN_DIR and conditional OAUTH_REDIRECT_URI placeholders into the generated WORKSPACE server row. Integrations owns the semantic requirement; mcp owns the structural absorption into McpServerSettings and _SERVER_TABLE rendering. This is the confirmed seam resolution: McpServerSettings already has these two fields per the mcp blueprint §05."}
```

---

## [08] PORTABILITY / VPS

All three integrations require one-time human-interactive auth on the local machine. Tokens then persist on the VPS and re-auth via device code.

**agy on VPS:**
- `agy` binary installed via the same `install.sh` script (idempotent). `~/.local/bin/agy` on PATH.
- First auth: `agy auth login --no-browser` — emits a URL + device code. The operator completes auth on a desktop browser.
- Token cached in `~/.config/antigravity/` (XDG cache dir; gitignored since it is in `$HOME`).
- Re-auth trigger: when `agy` returns exit code indicating auth expiry, the shim emits `AgyFail(fault="auth_required", ...)`; the agent surfaces this as a human action item.
- Headless non-TTY: shim always passes `-p`; no interactive TTY is ever spawned.
- `agy_process_timeout_s` (default 120 s) controls `move_on_after`; tune via `MAGHZ_INTEGRATIONS__AGY_PROCESS_TIMEOUT_S` on VPS if long autonomous tasks are expected.

**workspace-mcp on VPS:**
- `uvx workspace-mcp` pulls from PyPI at run time; `uv` must be on PATH.
- `TOKEN_DIR` set to `.cache/workspace-mcp` (gitignored via `.cache/` rule); persists across sessions.
- First auth: MCP client triggers the OAuth flow. On headless VPS, `OAUTH_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob` enables out-of-band consent: the operator copies the consent URL to a local browser, completes consent, and receives a code to paste back. Set `MAGHZ_INTEGRATIONS__WORKSPACE_OAUTH_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob` in the VPS environment; `McpServerSettings.workspace_oauth_redirect_uri` absorbs it into the generated `.mcp.json` WORKSPACE row's `env` block via the conditional `_render` path.
- After first consent the token file in `TOKEN_DIR` persists. The VPS token file is never committed.
- OAuth 2.1 (`MCP_ENABLE_OAUTH21=true` + `--transport streamable-http`) for multi-user server deployments is a future path; the single-user stdio default is sufficient here.

**codex-plugin-cc on VPS:**
- Claude Code plugin; runs where Claude Code runs. Node.js 18.18+ must be on PATH.
- `OPENAI_API_KEY` available via `setup-env.sh`. No persistent token; API-key auth is stateless.

---

## [09] ACCEPTANCE

**Structural gate (ruff/ty/mypy):**
- `ruff check admin/settings/config.py` — zero diagnostics after adding `IntegrationsConfig`.
- `ty check admin/settings/config.py` — zero errors.
- `mypy admin/settings/config.py` — zero errors (pydantic mypy plugin active).
- `ruff check .claude/skills/agy/scripts/agy.py` — zero diagnostics; `AgyOp` match is exhaustive with `assert_never`; no `"review"` case in `AgyOp`.
- `ty check .claude/skills/agy/scripts/agy.py` — zero errors; `Result[AgyReceipt, AgyFail]` is the sole rail; `AgyFault` contains no `"timeout"` case; `AgyReceipt.output` and `task_id` are `Option[str]`, not `str | None`.

**Runtime probes (manual; not CI-automated for external auth flows):**
- `agy --version` returns a version string without error.
- `uv run .claude/skills/agy/scripts/agy.py prompt "say hello" --model flash` — stdout is valid `AgyReceipt` JSON; `msgspec.json.decode(out, type=AgyReceipt)` succeeds; `output` decodes to `Some(str)`.
- `uv run .claude/skills/agy/scripts/agy.py prompt "fail" --model bad-model` — stdout is valid `AgyFail` JSON; `fault` is a member of `AgyFault`; no `"timeout"` case fires.
- `uvx workspace-mcp --version` — confirms `workspace-mcp` reachable via uvx.
- `python -c "from admin.settings import settings; print(settings().integrations)"` — no `ValidationError`; `workspace_token_dir` defaults to `Path('.cache/workspace-mcp')`; `workspace_oauth_redirect_uri` defaults to `None`; `gemini_api_key` field absent.
- `.mcp.json` WORKSPACE row (after `maghz mcp generate`) carries `args=["workspace-mcp", "--tool-tier", "extended"]` and `env` block includes `TOKEN_DIR`; `OAUTH_REDIRECT_URI` absent when `McpServerSettings.workspace_oauth_redirect_uri` is `None`, present when set.

**Skill load probe:**
- Claude Code session: `agy` skill appears in skill list; `/agy` invokes without usage error.
- Claude Code session: `/codex:review` slash command resolves after `codex-plugin-cc` plugin is installed.

**Token persistence:**
- After first OAuth consent: `ls .cache/workspace-mcp/` contains a token file; `.cache/` remains gitignored.
- `agy` auth token persists across CLI invocations without re-prompting.

**setup-env.sh gate:**
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OPENAI_API_KEY` all appear in `_ENV_KEYS` array.
- Session start hook emits these keys when set in the environment.

**Seam coherence gate (manual):**
- `maghz mcp generate` produces a `.mcp.json` WORKSPACE row whose `args` list contains `"--tool-tier"` and `"extended"` — confirming the mcp blueprint absorbed the integrations requirement.
- `McpServerSettings` in `admin/settings/config.py` carries `workspace_token_dir` and `workspace_oauth_redirect_uri` fields — confirming the seam absorption.
