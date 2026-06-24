# Maghz — Remaining Work

Working checklist for closing out the operator rebuild. The substrate and the five consumer folders
are rebuilt and green; what remains is the IaC/PG/MCP finalization, tooling self-containment, secrets,
and live bring-up.

## Current state

- `admin/` substrate + `automation`/`mcp`/`rails`/`infra`/`remote` consumers: rebuilt, `ruff` + `ty` clean, package imports, `maghz --help` works.
- WF-B's IaC deepen, PG deepen, roots consolidation, and whole-repo gate were cut short by transient API rate-limits — rolled into the finalization workflow below.
- `.mcp.json` was trimmed to 4 servers (`postgres`, `n8n`, `workspace`, `notebooklm`); the target is 8 (see §3).
- Docs (`README.md`, `CLAUDE.md`, `AGENTS.md`) updated for the MCP fleet and the `[07]` tooling table; the `exa`/`perplexity`/`tavily` research skills and the vendored codex were removed.

## 1. Errors — fixed

- `ty` seam: `__main__.py` lowers every rails-op `RuntimeRail[Envelope]` to `Envelope`; `mcp`/`automation`/`cloud`/`n8n` self-lower. Clean.
- beartype: `admin/__init__.py` now sets `BeartypeConf(..., warning_cls_on_decorator_exception=None)` — the `tools/assay` idiom — silencing the benign "cannot decorate" warnings for the PEP 695 generic `DrainReceipt[T]` and the cycle-deferred `spawn`. The boundary check still applies everywhere beartype can decorate.
- `mypy`/`basedpyright` are not installed; `ty` + `ruff` are the project gates.

## 2. Finalization workflow (the big remaining pass)

A per-file critique/redteam workflow starting at IaC (substrate + consumers are done — do not redo). Rolls in WF-B's rate-limited tail and finalizes to a green whole-repo gate:

- IaC self-containment — keep `admin/infra/runner.py`'s rail (`docker_build.Image` + local BuildKit `CacheFrom/ToLocalArgs`, `file://` backend, per-endpoint `docker.Provider(host=...)`, Automation API inline program); make `docker_host` self-detect (`admin/settings.py:117` hardcodes the Colima socket); one program drives local `unix://` and remote `ssh://`; `LINUX_AMD64` for the VPS; add a `BOOTSTRAP` verb + `MAGHZ_REMOTE_KEY_FILE` + known-hosts capture.
- PG — finish against the REAL stack (§4); do NOT add `pgvectorscale`/`pg_squeeze`.
- roots/barrels + whole-repo multi-language gate to green.

## 3. MCP fleet — target 8

Re-add the three research servers and convert hostinger:

| Server | Launch | Notes |
|--------|--------|-------|
| postgres | `uvx postgres-mcp --access-mode=restricted` | needs the DB up |
| n8n | `docker ... ghcr.io/czlonkowski/n8n-mcp` | needs n8n API + key |
| workspace | `uvx workspace-mcp --tool-tier extended` | Google OAuth; one-time browser consent |
| notebooklm | `notebooklm-mcp` | cookie/Chromium login; local-only |
| exa | `npx exa-mcp-server` | re-add |
| perplexity | `npx @perplexity-ai/mcp-server` | re-add; pin the OFFICIAL package |
| tavily | `npx tavily-mcp` | re-add |
| hostinger | `hostinger-api-mcp` (verify) | CONVERT the `hostinger-tools` skill; uses `HOSTINGER_TOKEN` |

- NO office/OneDrive MCP — `Aanerud/MCP-Microsoft-Office` needs an Azure app (none available).
- NO Heptabase MCP — no public API; the `heptabase-cli` skill stays the only integration.
- Keep the `${VAR}` placeholder model; `maghz mcp generate`/`validate`/`doctor` own the artifact.

## 4. PG extension stack (the real one)

Owned by `admin/profile.py` `_PROFILE`, which generates the `image/Dockerfile` apt block and the `db/routines.sql` `CREATE EXTENSION` census; `maghz schema doctor` asserts the live census. Base = ParadeDB `0.24.1-pg18` (`pg_search` BM25, `vector`/pgvector HNSW, `pg_ivm`, `pg_cron`, contrib) + layered `pg_net`, `pgmq`, `pg_jsonschema`, `hll`, `pg_partman`, `hypopg`. The full census also carries `pg_trgm`, `unaccent`, `fuzzystrmatch`, `citext`, `ltree`, `pgcrypto`, `btree_gin`, `btree_gist`, `pg_stat_statements`, `tablefunc`. There is NO `pgvectorscale` and NO `pg_squeeze` — the semantic index is pgvector HNSW, not DiskANN.

Document this in README/AGENTS pointing to `admin/profile.py` as the owner — do not duplicate the full census.

## 5. Tooling / provisioning / self-containment

Maghz is ~80% Forge-independent. To make it self-contained (Forge = CLI tooling only):

- Add a Maghz-owned flake/devshell reproducing the `AGENTS.md [07]` roster (uv, pulumi, postgres clients, colima, docker, ollama, node, etc.).
- Self-detect `docker_host` instead of the hardcoded Colima socket (`admin/settings.py:117`).
- Mint a Maghz-owned `op` template + `op run` wrapper to replace free-riding Forge's `hm-op-session.sh`.
- Fresh-deploy gaps NOT auto-provisioned: `ollama` (install script + service), `heptabase` (no public install — local only), `notebooklm`/`nlm` (browser-only — local only). `.claude/scripts/bootstrap-cli-tools.sh apply` self-provisions the rest on a fresh box.
- Cloud: inject secrets via `OP_SERVICE_ACCOUNT_TOKEN` → `op inject` at deploy/startup (ephemeral `.env`), never a committed secret.

## 6. Secrets + ENV vars

No secrets folder in the repo — secrets flow through process env only. Local: `op inject` (biometric) at Forge rebuild → `~/.config/hm-op-session.sh` → `.claude/hooks/setup-env.sh` forwards selected keys to subagents.

### Already in the `Tokens` vault (real)

`Exa API Key`, `Perplexity Sonar API Key`, `Tavily Auth Token`, `CONTEXT7_API_KEY`, `HOSTINGER_TOKEN`, and the GitHub tokens. The injection chain (`Parametric_Forge/modules/home/programs/shell-tools/1password.nix` `op/env.template` + `.claude/hooks/setup-env.sh` `_ENV_KEYS`) already carries these.

### MISSING — create these (and where to get them)

| Secret | Where to get it | Then |
|--------|-----------------|------|
| `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` | NOT on this machine (no `gcloud`, no `client_secret*.json`, no rclone config found). Google Cloud Console → create/select a project → enable the Drive API + Workspace APIs (Gmail/Calendar/Sheets) → APIs & Services → Credentials → Create OAuth client ID → **Desktop app** → download the JSON (holds both values). | Add a `Google OAuth App` item to `Tokens` with `client_id` + `client_secret` fields; add the two `op://Tokens/Google OAuth App/...` lines to `op/env.template` + the keys to `setup-env.sh`. |
| Google Drive service account (headless rclone) | Same GCP project → IAM → Service Accounts → create → grant Drive scope → download the JSON key. | Store raw JSON in `Tokens/MAGHZ_CLOUD_DRIVE_SERVICE_ACCOUNT`; reference `MAGHZ_CLOUD__REMOTES__DRIVE__SERVICE_ACCOUNT_CREDENTIALS`. |
| OneDrive token (Azure-free) | `rclone authorize onedrive` — uses rclone's BUILT-IN OAuth client, NO personal Azure app, NO `AZURE_*` env. Browser consent → rclone prints the token JSON. | Store in `Tokens/MAGHZ_CLOUD_ONEDRIVE_TOKEN`; reference `MAGHZ_CLOUD__REMOTES__ONEDRIVE__TOKEN`. |
| `op signin` | Run `op signin` (Touch ID) before creating any vault item — the CLI is currently not signed in (desktop integration reads but does not write unattended). | — |
| n8n API key | DEFERRED (leave n8n for now). When ready: n8n UI → Settings → API → create key. | `Tokens/MAGHZ_N8N_API_KEY` → `MAGHZ_MCP__N8N_API_KEY`. |

Non-secret literals (no vault item): `MAGHZ_DATABASE_DSN` = `postgresql://maghz@127.0.0.1:15435/maghz` (local trust-auth), `MAGHZ_MCP__N8N_API_URL` = `http://127.0.0.1:5678`.

NO Azure anywhere: no `AZURE_*` env vars, no office MCP; OneDrive uses rclone's built-in client.

## 7. Live-proof (last)

Real bring-up, no smoke tests: `maghz up` (Pulumi → Postgres + Ollama + n8n), `maghz schema apply`/`doctor` (extension census), exercise every `maghz` CLI command, the 8 MCP servers, the VPS `maghz exec`/`deploy`, and `maghz cloud sync`.

## Sequence

1. Finalization workflow (§2–§5) → green whole-repo.
2. Docstring/comment hygiene sweep.
3. Secrets (§6) — can start in parallel.
4. Live-proof (§7).
