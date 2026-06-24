# Maghz Program — Handoff & Post-Compact Context

The single source of truth for the Maghz rebuild program. Read this FIRST after any compaction.

## 0. Post-compact fast context-regain (read in this order)

1. This file (the whole program).
2. The task list (the canonical sequence + status).
3. `Rasm/.claude/workflows/{rebuild-code.js, maghz-deepen.js, maghz-doc-hygiene.js}` — the authored workflows.
4. `Rasm/.claude/workflows/{rebuild-python.js, implement.js}` — the doctrine/orchestration templates the others derive from.
5. The bar exemplars: `Rasm/libs/python/runtime/.planning/{reliability/faults.md, execution/lanes.md}` (the realized "bar as real code").
6. Live state: run `/workflows` (any WF still running?) and `git -C /Users/bardiasamiee/Documents/99.Github/Maghz status --short` + `git -C .../Maghz diff --stat`.

## 1. The three repos and their relation

- **Rasm** (`/Users/bardiasamiee/Documents/99.Github/Rasm`, the cwd / orchestration repo): owns the QUALITY BAR (`libs/python/.planning/` design pages + `libs/python/.api/` catalogs), the workflows (`.claude/workflows/`), the `workflow-creator` skill, and the standards (`docs/standards/`). NOT a rebuild target.
- **Maghz** (`/Users/bardiasamiee/Documents/99.Github/Maghz`, THE target): a "focused second brain" — PostgreSQL 18.4 `maghz` ledger + Heptabase content (via a `heptabase` CLI) + AI agents/automations. `admin/` = the `maghz` cyclopts CLI (JSON-envelope) + Pulumi IaC; `db/` = Atlas declarative `schema.sql` + `routines.sql` (no numbered migrations); `image/` = ParadeDB-plus-extensions Dockerfile; `.claude/` = skills/workflows. Edited DIRECTLY ON MAIN; `HEAD` (single commit `d2b0911`) is the rollback anchor.
- **Parametric_Forge** (`/Users/bardiasamiee/Documents/99.Github/Parametric_Forge`, the machine owner): Nix/home-manager. Provisions ALL CLI tooling (comprehensive — rclone/op/gh/uv/psql18/duckdb/pulumi/rsync/ssh all present), the `op`/1Password secret injection (vault `Tokens` → `op/env.template` → `~/.config/hm-op-session.sh` → `.claude/hooks/setup-env.sh` → subagents), and the SSH/VPS config (host `n8n` @ `31.97.131.41`, user `n8n-agent`, with a Codex-OAuth tunnel on port 1455). NOT a rebuild target EXCEPT: rewrite its legacy `setup-env.sh` to the canonical atomic pattern + add the Maghz secret references to `op/env.template`.

## 2. The quality bar / floor (non-negotiable)

- **BASE/FLOOR = the Rasm `libs/python/.planning/` corpus** — the realized, transcription-complete Python design pages. Maghz `admin/` code must MATCH that deep form as real `.py`. The runtime spine maps 1:1: `faults.md`→`BoundaryFault/RuntimeRail/CLASSIFY`, `lanes.md`→`Admit/LanePolicy/DrainReceipt`, `resilience.md`→`RetryClass/guard`, `receipts.md`→`Receipt/Signals`. (`EXEMPLAR_PINS` in `maghz-deepen.js` pins each owner to its exact page.)
- **`.api`: use Rasm's where the deps overlap** — shared `libs/python/.api/*` (expression, msgspec, pydantic, pydantic-settings, anyio, beartype, stamina, structlog, opentelemetry-*, psutil, numpy) + folder `libs/python/runtime/.api/*` (apscheduler, asyncssh, cyclopts, httpx, keyring, watchfiles, fsspec, gcsfs, universal-pathlib, msgspec).
- **New external libs Maghz adds and Rasm does NOT catalog** (pulumi, pulumi-docker, pulumi-docker-build, pg8000, sqlglot; PG-side pgvectorscale/pg_squeeze): **RAW ephemeral research** of the installed package surface (`uv run python -c ...` in the Maghz env) + official docs, to the SAME depth as a `.api` catalog. **Author NO new `.api` files anywhere** — just do it properly inline.
- **NOT the bar**: `docs/stacks/python/` and the `coding-python` skill are de-emphasized; the doctrine is embedded directly in the workflow prompts and the `.planning` exemplars are the floor.
- **Posture**: aggressive greenfield over already-strong code — collapse harder (target 30-50% LOC cut), preserve AND enhance capability (never delete), never invent churn on already-optimal code.

## 3. Workflows — authored / missing / sequence

All authored via the `workflow-creator` skill and gated by `scripts/validate-workflow.mjs` + `scripts/dry-run.mjs`. Opus for every author/critique/redteam stage (inherited model); sonnet only for discovery/scout; single-agent gates (internal ruff/ty fix-loop, not multi-round); decision-loaded to avoid wasteful re-scout; pool CAP 10; pipeline default, barrier only when a stage needs all prior results.

| WF | File (`Rasm/.claude/workflows/`) | Status | Scope |
|----|------|--------|-------|
| WF1 | `rebuild-code.js` | RUNNING (full, `wf_605e7a58-f5f`) | admin/ Python rebuild to the bar: Scout→Topology-Plan→Substrate→Consumers→Reconcile→Roots→whole-admin gate. ~31 agents. Narrow `mcp` run already validated GREEN. |
| WF-B | `maghz-deepen.js` | AUTHORED + VALIDATED (34 agents) | The DEEP pass; SUPERSEDES WF1's admin work. Substrate→Consumers→IaC→PG→Reconcile→Roots→Gate. Hardened doctrine: `CONCURRENCY`+`BANDS` consts, `DEEP_FORM` checklist (~30 floor-raisers), `EXEMPLAR_PINS`, decision-loaded `FILEMAP`(31→21)/`COLLAPSE`(BoundaryFault unification, `db.query`→RuntimeRail, `runtime.spawn`)/`EXT_CATALOG`(one typed owner generating Dockerfile+SQL+preload)/`PULUMI_DEEPEN`/`MCP_TRIM`(7→4)/`PG_DOCTOR`(pgvectorscale+pg_squeeze+GUCs+liveness). |
| WF-D | `maghz-doc-hygiene.js` | AUTHORED + VALIDATED (1 + N_folders + 1 agents; opus Clean) | FINAL comment/docstring hygiene over ALL Maghz code files. Discover→Clean(1 agent/sub-folder)→Verify. Law: CLAUDE.md `[FILE_ORGANIZATION]` + `docs/standards/style-guide.md` + `docs/standards/reference/code-documentation.md` (Google docstrings/Bash contract comments/`COMMENT ON`). Main dividers dash-filled; sub-section labels NO trailing dashes; header docstrings 1-2 lines simple. Excludes `pyproject.toml`/lockfiles/`.json`/`.md`/`.yaml`. Comments+docstrings ONLY, never logic. Runs LAST. |
| WF-C | `maghz-sweep.js` | NOT AUTHORED — likely unnecessary | Original "all-files all-language quality sweep" intent is now mostly absorbed by WF-B (admin+IaC+PG+SQL+Dockerfile) and WF-D (comments). Residual surface = `.claude/` tooling code only. DECIDE post-compact whether to author; default = skip. |

**Run order:** WF1 (finishing) → **WF-B** → [WF-C only if warranted] → **WF-D** → **live-proof**. (WF-B must settle `config.py` before the secret env-name wiring; the no-keychain `cloud.py`/n8n directive is in WF-B's `COLLAPSE`.)

WF-B must add a directive (fold into its run): **no-keychain** — `cloud.py` + the n8n key use the op-injected env as PRIMARY, never the macOS login keychain (`keyring` demoted to fallback / removed); `N8N_API_KEY` is vaulted (`op://Tokens/...`), not keychained.

## 4. Critique vs Redteam (per `rebuild-python.js` — the definitional approach)

- **author/rebuild** (effort `max`): ground-up build to the doctrine; fix-in-place; log only genuine cross-FILE residuals.
- **critique** (effort `xhigh`): DOCTRINAL-CONFORMANCE AUDIT — ultra-harsh, unagreeable; run the 6 MECHANICAL checklists line-by-line and repair every hit: (1) COLLAPSE_SCAN, (2) OWNER_CHOOSER, (3) KNOB_TEST, (4) ASPECTS, (5) RAILS, (6) PAYLOADS/FROZENDICT/PEP. Mechanical conformance to the named laws.
- **redteam** (effort `max`): ADVERSARIAL ARCHITECT — burden of proof on the design. (A) COUNTERFACTUAL on the core owner/algebra/dispatch (is it categorically the strongest the doctrine admits?), (B) ANTICIPATORY_COLLAPSE (next-feature diff lands as ONE declaration?), (C) LONG-TAIL/multi-dimensional edge+failure attack, (D) BOUNDARY-INTEGRITY, (E) SURFACE-SPRAWL-IN-TIME — PLUS a full cold re-review of every conformance dimension. Fundamental design, not a re-run of the mechanical checklist.
- WF-B layers the `DEEP_FORM` checklist (the floor-raiser deep-form rules) onto both critique and redteam.

## 5. State now (running / done)

- WF1 full run: IN PROGRESS. Narrow `mcp` run: DONE, green (it collapsed `mcp/model.py`→`ops.py`, gate passed; that throwaway state is in the working tree, superseded by the full run).
- WF-D: AUTHORED + VALIDATED (`maghz-doc-hygiene.js`), waiting to run LAST.
- WF-B: authored, validated, waiting to run after WF1.
- Maghz working tree: dirty on main with WF1 edits; `git diff HEAD` shows cumulative change; `git checkout HEAD -- <file>` reverts.

## 6. Tooling / secrets / integrations (live-proof prerequisites)

- **`op` is NOT signed in** → one-time `op signin` (Touch ID) needed before any vault op. No keychain usage anywhere in Forge (clean). No `OP_SERVICE_ACCOUNT_TOKEN` (only biometric) — add one only if the VPS needs `op inject` (the cloud design uses a VPS `.env` fallback instead, so likely not needed).
- **Forge `setup-env.sh`** is legacy append-mode → rewrite to the canonical atomic pattern (keep its `ANTHROPIC_API_KEY`). **Maghz `setup-env.sh`** already exports `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `N8N_API_KEY`, `OPENAI_API_KEY`; add the final `MAGHZ_MCP__DATABASE_URI`/`MAGHZ_DATABASE_DSN`/`MAGHZ_MCP__N8N_API_URL`/`MAGHZ_MCP__N8N_API_KEY` AFTER WF-B settles `config.py`. The dropped exa/perplexity/tavily MCP keys are NOT needed (skills use the bare `EXA_API_KEY`/etc. already present).
- **Gemini = LOCAL `agy` (Antigravity), already installed + OAuth'd** (`/Applications/Antigravity.app` + `~/.antigravity/oauth_creds.json`). Wire: symlink `~/.local/bin/agy` → the `~/.antigravity` binary (or set `MAGHZ_INTEGRATIONS__AGY_BINARY`). The Maghz `agy` skill exists. No Forge, no API key. (OAuth-subscription Gemini elsewhere is banned/dead — local agy only.)
- **Codex = CLI installed + logged in** (`~/.codex/auth.json`). DECISION: REMOVE `Maghz/.claude/skills/codex`, download `openai/codex-plugin-cc` into a tmp dir, COPY its files into Maghz as vendored local skill/command files (NOT plugin-manager-based) → portable local+remote. Not Forge.
- **Google Workspace** (`workspace-mcp`, in `.mcp.json`): GCP OAuth desktop app → `GOOGLE_OAUTH_CLIENT_ID/SECRET` (vault) + one-time browser consent (token dir copyable to VPS).
- **Google Drive** (rclone, `cloud.py` rail): service-account JSON (base64, vault) or OAuth; configured via `RCLONE_CONFIG_DRIVE_*` env (no `rclone.conf`).
- **OneDrive** (rclone, `cloud.py` rail): Azure app registration → `client_id/secret/drive_id` (vault) + token; `RCLONE_CONFIG_ONEDRIVE_*` env. Client-secret rotation required.
- **n8n**: `N8N_ENCRYPTION_KEY` (root-owned file; WF-B fixes the `stack.py` mount gap BL-1 + the missing `workflows/n8n` dir), `N8N_API_KEY` (mint post-first-boot via `POST /api/v1/users/me/api-key`, then vault). `.mcp.json` post-trim = 4 servers (postgres, n8n, workspace, notebooklm).
- **VPS** = `n8n`@`31.97.131.41` (user `n8n-agent`) = `MAGHZ_REMOTE_HOST`; SSH via Forge's 1Password SSH agent; `admin/remote/` uses asyncssh exec/deploy.

## 7. [NEEDS USER] checklist

- `op signin` (Touch ID).
- GCP: create the OAuth desktop app (Workspace + Drive) + a service account (Drive) → provide values.
- Azure: app registration (OneDrive) → `client_id/secret/drive_id`.
- One-time consents: workspace-mcp browser auth, rclone Drive/OneDrive `authorize`.
- Provide the values to create the `op://Tokens/...` items.
- n8n admin first-boot → mint the API key.
- Confirm: codex vendored into Maghz (not plugin), agy symlink/path.

## 8. The live-proof (final phase, after the rebuilds + tooling)

Real, no smoke tests: wire all secrets into Forge `op/env.template` + `forge-redeploy switch` (only after WF1/WF-B finish so the toolchain isn't disrupted mid-run); local bring-up (`forge-provision up`/`maghz up` Pulumi → Postgres+Ollama+n8n; `maghz schema apply` via Atlas; `pg_isready`); exercise EVERY `maghz` CLI command against live infra + the `doctor` liveness assertions (extension census, shared_preload, cron jobs, embed loop, the `mz_*` indexes); remote VPS (`maghz exec`/`maghz deploy`); cloud sync (`maghz cloud sync` to Drive+OneDrive). Zero errors across all touched languages (ruff+ty, sqlfluff/sqruff, hadolint, json validity).

## 9. Process / quality expectations (carry into every WF)

- Use `workflow-creator`: author → `validate-workflow.mjs` (clear errors) → `dry-run.mjs` (parseOk+ran+deterministic) before any run; `meta` is a pure literal; no backticks in `meta`.
- Lean + optimized: no wasted/nonsense phases; decision-loaded over re-scout; single-agent gates with internal loops; pipeline by default; parallel/barrier only when a stage needs all prior results; pool CAP 10.
- Opus for all authoring/critique/redteam; sonnet only for mechanical discovery/scout/gate.
- Preserve capability, never delete; never inflate already-optimal code.
