# `admin/` — the `maghz` operator

`admin/` is the **`maghz`** CLI: the single, agent-first operator for the Maghz second brain — a local + remote + cloud "self-driving" manager over a PostgreSQL knowledge ledger, driven by AI agents and automations. Heptabase owns content; PostgreSQL is the durable centralized ledger; `maghz` orchestrates the database lifecycle, the automation arm, secrets, remote/VPS control, cloud sync, and the MCP/skill tool surface — every concern behind one polymorphic CLI that emits a typed JSON `Envelope`.

## Goals

- **Agent-first OPERATOR** — one CLI (`maghz`) agents invoke for every lifecycle, ledger, and automation concern; research/content tools stay first-class skills/MCPs the operator composes, never re-wrapped.
- **Full local + remote + cloud self-driving manager** — local stack lifecycle + self-heal, remote/VPS over SSH, cloud sync to Google Drive + OneDrive.
- **Resilience / non-fragility** over health-monitoring noise: typed retry classes, lane-keyed admission, idempotent apply, orphan-free `up`/`down`.
- **The automation arm is the lynchpin** — a fully parameterized `Trigger × Action` ADT, agent-invocable, with typed receipts.

## Architecture (`admin/` packages)

| Package | Owns |
| --- | --- |
| `runtime/` | the lean substrate every arm composes: lanes (`drain`/`offload` + an `anyio` `CapacityLimiter`), resilience (`RetryClass` + a `POLICY` table + `guarded`/`guard`), receipts (a `Receipt` tagged-union + `@receipted` + `Signals` over the Envelope/structlog), rails (`async_boundary` over `expression`) |
| `automation/` | **the lynchpin** — `model.py` (a `Trigger` × `Action` ADT + a typed `AutomationReceipt`), `engine.py` (`drive(trigger, action)` over `watchfiles`, an APScheduler scheduler, a `psutil` governor, a `CapacityLimiter`, an NDJSON ledger) |
| `remote/` | the `--exec ssh://` surface: a pooled `asyncssh` connection, a `git ls-files` working-tree push, remote `maghz up`/`schema apply`, SFTP artifact pull, an `ExecReceipt`; the live Hostinger VPS deploy |
| `mcp/` | MCP-as-IaC: a `pydantic-settings`-typed model of the MCP server set that generates + validates the committed `${VAR}` `.mcp.json` |
| `integrations/` | the Google/Codex/Workspace wiring (`agy` Gemini-3, the Codex plugin, the Workspace MCP) |
| `settings/` | `MaghzSettings` — the one validated config owner; no other code reads `os.environ` |
| `core/` | the JSON `Envelope` / `Status` / `Detail` / `Row` receipt owners (the result + fault rail) |
| `infra/` | the Pulumi Automation API stack (the custom ParadeDB image build, `db` + `ollama` + `n8n` containers) behind one `StackOp` (`up`/`down`/`status`) verb |
| `rails/` | `schema` (idempotent psql apply), `ledger` (the read projections), `sync` (Heptabase + cloud), `stack` |
| `db.py` | the `pg8000` query boundary (every call offloads off the event loop; faults lift to a typed `DbFault`) |
| `__main__.py` | the `cyclopts` CLI entrypoint — modal-arity verbs over the rails, mapping every outcome to the JSON `Envelope` and its exit code |

## CLI surface (`maghz <verb>`)

| Verb | Does |
| --- | --- |
| `up` / `down` / `status` | converge / tear down / preview the local docker stack (Pulumi: `db` + `ollama` + `n8n`) |
| `schema apply` | apply the idempotent declarative schema (`db/schema.sql` + `routines.sql` + `cron.sql` via psql — no external diff tool) |
| `ledger <projection>` | one read projection: `coverage` \| `gaps` \| `stale` \| `next` \| `owner` |
| `sync [heptabase \| cloud]` | reconcile canonical concepts ↔ Heptabase cards; back up + bisync content to the cloud |
| `run` / `watch` / `schedule` | drive an automation (a `Trigger × Action`); each emits a typed `AutomationReceipt` |
| `mcp generate` / `validate` | emit + check the committed `.mcp.json` from the typed server model |
| `--exec ssh://<host>` | run any verb against the remote VPS |

## The automation arm (the lynchpin)

A fully parameterized `Automation = Trigger × Action`, agent-invocable:

- **`Trigger`** = `Watch` (`watchfiles` file events) · `Schedule` (APScheduler cron) · `Manual`.
- **`Action`** = `DeepResearch` · `Refine` · `CreateEntry` · `Notify` · `Embed` · `Sync` · `Sequence` · `Debounce`.
- Agents drive it via `maghz run/watch/schedule`; each run emits a typed `AutomationReceipt`, retries under `RetryClass.AGENT`, admits through lane-keyed capacity, is governed by a `psutil` resource snapshot, and appends to an NDJSON ledger. No health-monitoring noise.

## Data layer (`db/`)

- `schema.sql` (idempotent declarative: tables, enums, indexes), `routines.sql` (functions, views, triggers, exotic indexes), `cron.sql` (`pg_cron` jobs registered in `postgres`, executed in `maghz` via `schedule_in_database`).
- The custom **ParadeDB PG18** image ships a curated extension profile: `pg_search` (BM25), `pgvector` (HNSW), `pg_ivm` (incremental materialized views), `pg_net` (async HTTP → Ollama embedding), `pgmq`, `hll`, `pg_partman`, plus the `unaccent`/thesaurus/synonym FTS dictionary stack.
- **RRF hybrid search** fuses BM25 (lexical), dense `pgvector` cosine (semantic), and trigram fuzzy ranks; the in-DB `pg_net` → Ollama (`nomic-embed-text`) pipeline embeds concepts on a two-step cron tick.

## Remote / VPS

`maghz --exec ssh://<hostinger>` deploys + runs the whole stack on the live Hostinger VPS: a `git ls-files` working-tree push, remote `up` + `schema apply`, an SFTP artifact pull, all behind a typed `ExecReceipt`. Secrets reach the VPS via an `OP_SERVICE_ACCOUNT_TOKEN`; a portable `bootstrap-cli-tools.sh` brings the stack up on any machine with no hand steps.

## Cloud sync

`rclone` Google Drive + OneDrive remotes: a scheduled `pg_dump` + content backup to **both**, an `rclone bisync` of the content tree, and a restore path — driven by the `Sync` automation action and exposed as `maghz sync cloud`.

## MCP + skills

- **MCP-as-IaC** — `admin/mcp/` models the server set (`postgres`, `n8n`, `exa`, `perplexity`, `tavily`, `workspace`, `notebooklm`) and emits the committed `${VAR}`/`${VAR:-default}` `.mcp.json`, run under `op run -- claude` so secrets inject at the boundary and travel to the VPS unchanged.
- **n8n** — a Pulumi-managed container (local + VPS) with `N8N_MCP_ACCESS_ENABLED`, workflows committed via the native CLI, authored through the adopted `n8n-mcp` + `n8n-skills`.
- **Integrations** — `agy` (the Antigravity Gemini-3 Ultra OAuth CLI), the official Codex plugin (`codex-plugin-cc`), and the Google Workspace MCP (`workspace-mcp`: Gmail/Drive/Docs/Sheets/Calendar/…).
- **Owned skills** — `maghz-operator`, `automations`, `cloud-sync`, `gemini`/`agy`, `forge-usage`. **Adopted** — `n8n-mcp`, `workspace-mcp`, `postgres-mcp`, `codex-plugin`.

## Secrets

`op` (the 1Password `Tokens` vault) is the single source: the Forge `op inject` chain → the `setup-env.sh` injector → agents. New secrets (`GOOGLE_OAUTH_CLIENT_ID/SECRET`, `N8N_API_KEY`) are added to the vault + the injector; the VPS authenticates via `OP_SERVICE_ACCOUNT_TOKEN`. The committed `.mcp.json` carries only `${VAR}` placeholders — never secret values.
