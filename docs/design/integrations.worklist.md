# integrations — Realize Worklist

Realize-ordered execution of `docs/design/integrations.md`. The design is decision-complete; this worklist names the exact owners, ADTs, members, deps, ripples, dependency order, and gates the implement pass executes. No redesign, no production code here.

The domain ships three external surfaces as agent tools: `agy` (Antigravity CLI, OAuth-authoritative), `codex-plugin-cc` (Claude Code plugin, no Python shim), and `workspace-mcp` (a row owned by the mcp blueprint). The only Python-land code is `IntegrationsConfig` (settings group) plus the `agy` skill shim; everything else is skill markdown, `.api` catalog, `.gitignore`, and a seam the mcp domain absorbs.

---

## [01] OWNERS — files to create/modify

| Owner file | Action | Section(s) | Dense type / what it owns |
| --- | --- | --- | --- |
| `admin/settings/config.py` | modify | `[MODELS]` | `IntegrationsConfig(BaseModel)` nested group; `MaghzSettings.integrations` field added under `env_nested_delimiter="__"`. Sibling of `DatabaseConfig`/`OllamaConfig`/`InfraConfig`/`ObservabilityConfig`. Reuses module-level `_GROUP = ConfigDict(frozen=True, extra="forbid", validate_by_name=True)`. Extend `__all__` with `"IntegrationsConfig"`. |
| `.claude/skills/agy/scripts/agy.py` | create | `[RUNTIME_PRELUDE]` `[TYPES]` `[CONSTANTS]` `[MODELS]` `[ERRORS]` `[OPERATIONS]` `[COMPOSITION]` | The full `agy` boundary shim. Owns `AgyOp`/`AgyFault` unions, `_TIER` correspondence table, `AgyReceipt`/`AgyFail` egress pair, `_is_transient` predicate, `@stamina.retry`-wrapped `_run_process`, and the one modal `agy(op, *, args)` entrypoint driven by `anyio.run`. Imports `cfg = settings()` from `admin.settings` for `agy_process_timeout_s` + `agy_binary` (runs via `uv run -m`, not standalone `--script`). |
| `.claude/skills/agy/SKILL.md` | create | skill | Invocation guide: prompt/task/status/cancel/result dispatch, `_TIER` model-tier selection (`pro` default, `flash` latency), VPS `--no-browser` auth note. `user-invocable: true`. |
| `.claude/skills/agy/workspace-mcp.api.md` | create | `.api` catalog | The `workspace-mcp` capability catalog: 12 service groups, `core`/`extended`/`complete` tool-tier membership, env-var contract (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `TOKEN_DIR`, conditional `OAUTH_REDIRECT_URI`), OAuth stdio-default flow. Not a `libs/python` import — no Rasm `.api/` entry. |
| `.claude/skills/codex/SKILL.md` | create | skill | Contextualizes the plugin-delivered `/codex:review`, `/codex:adversarial-review`, `/codex:rescue`, `/codex:status`, `/codex:result`, `/codex:cancel` slash commands for Maghz research/refine. No Python shim, no vendored `hooks.json`. Documents `/plugin marketplace add openai/codex-plugin-cc` + `OPENAI_API_KEY` requirement. |
| `.gitignore` | modify | — | Confirm token cache coverage. `.cache/` already covers `.cache/workspace-mcp/`; `agy` token lands in `$HOME/.config/antigravity/` (outside repo, no rule needed). No new rule required unless a repo-local agy cache is introduced. |

`IntegrationsConfig` is the only new Python type. No new Python module file — it lands inline in `admin/settings/config.py`. The mcp blueprint owns the `.mcp.json` WORKSPACE row exclusively; integrations writes no `.mcp.json` block.

---

## [02] ADTs — closed unions, cases, discriminant

### `AgyOp` — subcommand discriminant (closed `Literal`)
```python
type AgyOp = Literal["prompt", "task", "status", "cancel", "result"]
```
Discriminant: the `op` positional. `match op` + `assert_never` exhausts. `"prompt"` is the single synchronous op (covers review/research/summarize/adversarial — all are `agy -p`); `"task"`/`"status"`/`"cancel"`/`"result"` are the async background-job lifecycle against `agy task ...`. NO `"review"` case — a name-suffix modality is a `MODAL_ARITY` violation; review is prompt content, not a subcommand.

### `AgyFault` — fault vocabulary (closed `Literal`)
```python
type AgyFault = Literal["binary_not_found", "auth_required", "quota_exceeded", "process_error"]
```
NO `"timeout"` case. `TimeoutError` from the `anyio.move_on_after(cfg.integrations.agy_process_timeout_s)` scope maps to `"process_error"` (transient, no-information split otherwise). Mapping table: `FileNotFoundError` -> `binary_not_found`; exit 1 + stderr auth match -> `auth_required`; exit 2 + stderr quota match -> `quota_exceeded`; `TimeoutError`/other non-zero -> `process_error`. Mapping fires post-retry; the retry predicate fires pre-mapping.

### `_is_transient` — retry predicate (pre-mapping)
```python
def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, ExceptionGroup):
        return any(isinstance(e, ProcessLookupError) for e in exc.exceptions)
    return isinstance(exc, (ProcessLookupError, BrokenPipeError))
```
Fires only on transient spawn failures (kill exit 137/143, broken worker). NOT on auth, quota, or deadline.

### `AgyReceipt` / `AgyFail` — closed egress pair
```python
class AgyReceipt(msgspec.Struct, frozen=True, gc=False):
    op: AgyOp
    output: Option[str]      # Nothing for job-management ops; Some(text) for prompt
    task_id: Option[str]     # Some(id) for task-create/status; Nothing otherwise

class AgyFail(msgspec.Struct, frozen=True, gc=False):
    op: AgyOp
    fault: AgyFault
    detail: str              # stderr or exception message; never optional
```
Arm distinguished by presence of `fault` — no generic `status`/`error` envelope. `Ok(receipt)` -> `msgspec.json.encode(receipt)` on stdout; `Error(fail)` -> `msgspec.json.encode(fail)` on stdout.

### `IntegrationsConfig` — settings group (pydantic `BaseModel`)
```python
class IntegrationsConfig(BaseModel):
    model_config = _GROUP
    google_oauth_client_id:       str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret:   str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_SECRET")
    workspace_token_dir:          Path = Path(".cache/workspace-mcp")
    workspace_oauth_redirect_uri: str | None = None
    agy_binary:                   Path = Path("agy")
    agy_process_timeout_s:        float = Field(default=120.0, gt=0)
```
`MaghzSettings` gains `integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)`. Env paths under `MAGHZ_INTEGRATIONS__`. `GEMINI_API_KEY` is NOT admitted (no consumer; antigravity-cli #78 open) — `SHAPE_BUDGET` violation to add a dead field.

### codex — no ADT, no shim
`codex-plugin-cc` is plugin-delivered. No `CodexOp`, no Python. `SKILL.md` only.

---

## [03] API_MEMBERS — exact external members to compose

| Package | Member | Use in shim |
| --- | --- | --- |
| `anyio` | `anyio.run(afn)` | drives the shim entry from the CLI boundary; no `asyncio.gather`. |
| `anyio` | `anyio.run_process(command, *, check=False)` | spawns the `agy` binary; captures stdout/stderr as `bytes`, exit code. |
| `anyio` | `anyio.move_on_after(delay)` | outermost deadline scope wrapping the process call; trip -> `TimeoutError` -> `process_error`. |
| `anyio` | `anyio.abc.CompletedProcess` (`returncode`, `stdout`, `stderr`) | the spawn result inspected for exit-code + stderr mapping. |
| `stamina` | `stamina.retry(on=_is_transient, attempts=2, wait_initial=0.5)` | decorates `_run_process`; stacking order `move_on_after` (outer) -> `stamina.retry` -> `run_process`. |
| `expression` | `Option[str]`, `Some`, `Nothing` | `AgyReceipt.output` / `AgyReceipt.task_id` typed optionals (not `str | None`). |
| `expression` | `Result[AgyReceipt, AgyFault]`, `Ok`, `Error` | the single boundary rail; chosen once at `run_process`, carried through the match. |
| `msgspec` | `msgspec.Struct(frozen=True, gc=False)` | `AgyReceipt` / `AgyFail` base. |
| `msgspec` | `msgspec.json.Encoder` / `msgspec.json.encode` | egress encode to stdout. |
| `msgspec` | `enc_hook` / `dec_hook` on module-level encoder/decoder | `Option[str]` codec — see RIPPLE [05] for the automation-domain alignment (msgspec-native `str | None` at wire, project to `Option` at arm) vs. shared-hook decision. |
| `pydantic` | `BaseModel`, `Field`, `ConfigDict` (via `_GROUP`) | `IntegrationsConfig` group. |
| `builtins` | `ExceptionGroup`, `ProcessLookupError`, `BrokenPipeError`, `FileNotFoundError`, `TimeoutError`, `assert_never` | exact `except`-named types; no bare `except Exception`. |
| `types` | `MappingProxyType` | `_TIER` model-tier table in `[CONSTANTS]`. |

External binary surface consumed (no Python SDK): `agy -p "<prompt>" [--model <tier>]`, `agy task create|status|result|cancel <…>`, `agy auth login [--no-browser]`, `agy --version`. `--model` tiers `gemini-3-pro|flash|nano`. The shim delegates entirely; nothing is hand-rolled.

`workspace-mcp` and `codex-plugin-cc` expose no importable Python member — they are `uvx`/plugin surfaces. Their contract is the `.api.md` catalog and the mcp `_SERVER_TABLE` row.

---

## [04] DEPS — packages to admit + `.api` catalog note

No new `pyproject.toml` admissions. `msgspec`, `anyio`, `stamina`, `expression`, `pydantic`, `pydantic-settings` are already admitted (runtime domain owns the rail packages).

| Surface | Install mechanism | Band | `.api` note |
| --- | --- | --- | --- |
| `agy` (antigravity-cli) | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` -> `~/.local/bin/agy`; Forge provisions | cli (machine-level binary) | No Rasm `.api/` entry (not a Python import). Surface documented inline in `agy/SKILL.md`. |
| `workspace-mcp` | `uvx workspace-mcp` (PyPI at invocation) | cli (mcp `_SERVER_TABLE` row) | Author `.claude/skills/agy/workspace-mcp.api.md`: 12 service groups, tool-tier membership, env contract. No Rasm `.api/`. |
| `codex-plugin-cc` | `/plugin marketplace add openai/codex-plugin-cc` -> `/plugin install` | cli (Claude Code plugin) | No `.api` catalog; plugin self-describes. Slash commands documented in `codex/SKILL.md`. |
| Node.js 18.18+ | Forge-provisioned | cli (machine-level, codex dependency) | none. |

Catalog note (must land before implement codes the shim): `workspace-mcp.api.md` is the only authored catalog; it lists the env-var contract the mcp `_SERVER_TABLE` WORKSPACE row consumes and the tool-tier rationale (`extended` default).

---

## [05] RIPPLES — cross-domain canonical shapes

```json
{"domains": ["integrations", "mcp"], "claim": "The WORKSPACE row in _SERVER_TABLE (admin/mcp/model.py) carries command='uvx', args=['workspace-mcp','--tool-tier','extended'], env keys GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, TOKEN_DIR (sourced from McpServerSettings.workspace_token_dir, default '.cache/workspace-mcp'), plus conditional OAUTH_REDIRECT_URI emitted by _render only when McpServerSettings.workspace_oauth_redirect_uri is non-None. Integrations declares the requirement; mcp owns the row + the _render conditional branch. No parallel .mcp.json block in integrations. mcp blueprint §05 confirms both McpServerSettings fields already exist."}
```
```json
{"domains": ["integrations", "mcp", "secrets-bootstrap"], "claim": "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are bare env keys in the WORKSPACE row (NOT MAGHZ_MCP__-prefixed). IntegrationsConfig carries them under MAGHZ_INTEGRATIONS__ for agy OAuth context; McpServerSettings carries them under MAGHZ_MCP__ as SecretStr|None for direct use; setup-env.sh (secrets-bootstrap) injects them bare so each consumer reads its own prefix path. mcp _validate must exclude these two bare placeholders from the per-field McpServerSettings check. Two consumers, one canonical source name, no duplication."}
```
```json
{"domains": ["integrations", "automation"], "claim": "The automation engine's _AGENT_DISPATCH table (automation blueprint) keys AgentAction.skill=AgentSkill to skill adapters with contract (action: AgentAction, spec: AutomationSpec, cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]. agy success projects AgyReceipt.output (Option[str], decode Some(text)); codex:review returns a structured review block. AgentAction.params: msgspec.Raw is decoded lazily inside the dispatch arm against the skill's parameter struct. Automations compose through the agy/codex skills, never re-derive the invocation surface."}
```
```json
{"domains": ["integrations", "automation"], "claim": "Option[str] codec alignment: the automation blueprint COLLAPSED the Embed.concept/Sync.concept enc_hook/dec_hook pair to msgspec-native str|None at the wire, projecting to Option[str] only at the dispatch arm. The agy shim's AgyReceipt.output/task_id are Option[str] domain fields encoded to JSON for the egress channel — these REQUIRE the enc_hook/dec_hook pair on the agy module-level encoder/decoder because the struct itself is wire-encoded (unlike Embed/Sync which are decoded inbound). The two domains are not in conflict: automation decodes inbound (native str|None), agy encodes outbound (needs the Option hook). Implement registers the Option enc_hook/dec_hook on the agy module encoder/decoder only."}
```
```json
{"domains": ["integrations", "secrets-bootstrap"], "claim": "OPENAI_API_KEY (codex), GOOGLE_OAUTH_CLIENT_ID, and GOOGLE_OAUTH_CLIENT_SECRET must appear in setup-env.sh _ENV_KEYS and be emitted to the Claude env file. secrets-bootstrap owns storage + the setup-env.sh _ENV_KEYS array + the session-start emission hook; integrations owns the requirement declaration only."}
```

---

## [06] DEPENDS_ON — domains whose owners must exist first

| Domain key | Why it must be realized first |
| --- | --- |
| `runtime` | Owns the admitted rail packages and the `Result`/`stamina`/`anyio`/`msgspec` patterns the agy shim composes (`async_boundary`, `RuntimeRail`, classification). Everything depends on runtime. |
| `mcp` | Owns `admin/mcp/model.py` `_SERVER_TABLE` + `admin/settings/config.py` `McpServerSettings` (`workspace_token_dir`, `workspace_oauth_redirect_uri`, the two OAuth `SecretStr` fields). The WORKSPACE row + conditional `_render` branch live there; integrations only declares the requirement. |
| `secrets-bootstrap` | Owns `setup-env.sh` + the `_ENV_KEYS` array + the session-start emission hook that injects `OPENAI_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`. Without it the agy OAuth context + codex + workspace rows have no credential source. |

`automation` is a downstream CONSUMER of this domain (it dispatches `agy`/`codex` via `_AGENT_DISPATCH`), not a prerequisite — realize integrations before automation's agent-action arms.

---

## [07] ACCEPTANCE — gate signals

### Structural gate (ruff/ty/mypy zero)
- `ruff check admin/settings/config.py` — zero diagnostics after `IntegrationsConfig`.
- `ty check admin/settings/config.py` — zero errors.
- `mypy admin/settings/config.py` — zero errors (pydantic plugin active).
- `ruff check .claude/skills/agy/scripts/agy.py` — zero; `AgyOp` match exhaustive with `assert_never`; no `"review"` case.
- `ty check .claude/skills/agy/scripts/agy.py` — zero; `Result[AgyReceipt, AgyFault]` sole rail; `AgyFault` has no `"timeout"`; `AgyReceipt.output`/`task_id` are `Option[str]`, not `str | None`; `except` names exact types, no bare `except Exception`.

### Runtime probes (manual; external-auth flows not CI-automated)
- `agy --version` returns a version string.
- `uv run .claude/skills/agy/scripts/agy.py prompt "say hello" --model flash` — stdout is valid `AgyReceipt` JSON; `msgspec.json.decode(out, type=AgyReceipt)` succeeds; `output` decodes to `Some(str)`.
- `uv run .claude/skills/agy/scripts/agy.py prompt "fail" --model bad-model` — stdout is valid `AgyFail` JSON; `fault` is an `AgyFault` member; no `"timeout"` fires.
- `uvx workspace-mcp --version` — reachable via uvx.
- `python -c "from admin.settings import settings; print(settings().integrations)"` — no `ValidationError`; `workspace_token_dir` defaults `Path('.cache/workspace-mcp')`; `workspace_oauth_redirect_uri` defaults `None`; no `gemini_api_key` field.
- `.mcp.json` WORKSPACE row (after `maghz mcp generate`) carries `args=["workspace-mcp","--tool-tier","extended"]` and `env` includes `TOKEN_DIR`; `OAUTH_REDIRECT_URI` absent when `workspace_oauth_redirect_uri` is `None`, present when set.

### Skill / plugin load
- `agy` skill appears in the skill list; `/agy` invokes without usage error.
- `/codex:review` resolves after `codex-plugin-cc` install.

### Token persistence
- After first OAuth consent: `ls .cache/workspace-mcp/` contains a token file; `.cache/` remains gitignored.
- `agy` token persists across invocations without re-prompting.

### Seam coherence (manual)
- `maghz mcp generate` produces a WORKSPACE row whose `args` contains `"--tool-tier"` and `"extended"` — mcp absorbed the integrations requirement.
- `McpServerSettings` in `admin/settings/config.py` carries `workspace_token_dir` and `workspace_oauth_redirect_uri`.
- `setup-env.sh _ENV_KEYS` contains `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OPENAI_API_KEY`.
</content>
</invoke>
