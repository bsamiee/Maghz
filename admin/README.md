# `admin/` — the `maghz` operator

`admin/` is the **`maghz`** CLI: the single, agent-first operator for the Maghz second brain — a local + remote + cloud "self-driving" manager over a PostgreSQL knowledge ledger, driven by AI agents and automations. Heptabase owns content; PostgreSQL is the durable centralized ledger; `maghz` orchestrates the database lifecycle, the automation arm, secrets, remote/VPS control, cloud sync, and the MCP/skill tool surface — every concern behind one polymorphic CLI that emits a typed JSON `Envelope`.

## Goals

- **Agent-first OPERATOR** — one CLI (`maghz`) agents invoke for every lifecycle, ledger, and automation concern; research/content tools stay first-class skills/MCPs the operator composes, never re-wrapped.
- **Full local + remote + cloud self-driving manager** — local stack lifecycle + self-heal, remote/VPS over SSH, cloud sync to Google Drive + OneDrive.
- **Resilience / non-fragility** over health-monitoring noise: typed retry classes, lane-keyed admission, idempotent apply, orphan-free `up`/`down`.
- **The automation arm is the lynchpin** — a fully parameterized `Trigger × Action` ADT, agent-invocable, with typed receipts.

## Architecture (`admin/` layout)

Flat-file owners:

| File | Owns |
| --- | --- |
| `core.py` | the JSON `Envelope` / `Status` / `Detail` / `Row` receipt owners (the result + fault rail) |
| `db.py` | the `pg8000` query boundary (every call offloads off the event loop; faults lift to the one `BoundaryFault` family) |
| `profile.py` | the typed PG extension catalog (`_PROFILE` / `Extension`) rendering the `image/Dockerfile` apt block and the `db/schema.sql` `CREATE EXTENSION` census |
| `settings.py` | `MaghzSettings` — the one validated config owner; no other code reads `os.environ` |
| `remote.py` | the `exec`/`deploy` commands: one scoped `asyncssh` connection, a `git ls-files` working-tree push, remote `maghz up`/`schema apply`, SFTP artifact pull, an `ExecReceipt`; the live Hostinger VPS deploy |
| `__main__.py` | the `cyclopts` CLI entrypoint — modal-arity verbs over the rails, mapping every outcome to the JSON `Envelope` and its exit code |

Subpackages:

| Package | Owns |
| --- | --- |
| `runtime/` | the lean substrate every arm composes: lanes (`lanes.py`), resilience (`resilience.py` — `RetryClass` + a `POLICY` table + `guard`), receipts (`receipts.py` — a `Receipt` tagged-union + `Signals` over the Envelope/structlog), rails (`rails.py` — `async_boundary` over `expression`) |
| `rails/` | `schema.py` (idempotent psql apply + doctor), `ledger.py` (the read projections), `sync.py` (Heptabase reconcile), `cloud.py` (Drive + OneDrive backup/bisync), `n8n.py` (workflow export/import) |
| `infra/` | `runner.py` — the Pulumi Automation API stack (the custom ParadeDB image build, `db` + `ollama` + `n8n` containers) behind one `StackOp` (`up`/`down`/`status`) verb |
| `mcp/` | MCP-as-IaC: `ops.py` models the 8-server fleet and generates + validates the committed `${VAR}` `.mcp.json` |
| `automation/` | **the lynchpin** — `model.py` (a `Trigger` × `Action` ADT + a typed `AutomationReceipt`), `engine.py` (`drive(trigger, action)` over `watchfiles`, an APScheduler scheduler, a `psutil` governor, a `CapacityLimiter`, an NDJSON ledger) |

## CLI surface (`maghz <verb>`)

| Verb | Does |
| --- | --- |
| `up` / `down` / `status` | converge / tear down / preview the local docker stack (Pulumi: `db` + `ollama` + `n8n`) |
| `schema apply` / `schema doctor` | apply the idempotent schema (`docker cp` of the `db/search/` dictionaries, then `psql` over `db/schema.sql` + `db/routines.sql` + `db/cron.sql`); assert the live extension census |
| `ledger <projection>` | one read projection over the ledger |
| `sync diff` / `sync generate` | reconcile canonical concepts against Heptabase cards |
| `cloud sync` / `cloud restore` | back up + bisync content to Google Drive + OneDrive; restore |
| `n8n export` / `n8n import` / `n8n status` | move committed workflows in and out of the n8n container |
| `automation run` | drive an automation (a `Trigger × Action`); emits a typed `AutomationReceipt` |
| `mcp generate` / `validate` / `diff` / `watch` | emit, check, diff, and watch the committed `.mcp.json` from the typed server model |
| `exec` / `deploy` | run any verb against, or deploy the whole stack to, the remote VPS |

## The automation arm (the lynchpin)

A fully parameterized `Automation = Trigger × Action`, agent-invocable:

- **`Trigger`** = `Watch` (`watchfiles` file events) · `Schedule` (APScheduler cron) · `Manual`.
- **`Action`** = `DeepResearch` · `Refine` · `CreateEntry` · `Notify` · `Embed` · `Sync` · `Sequence` · `Debounce`.
- Agents drive it via `maghz automation run`; each run emits a typed `AutomationReceipt`, retries under `RetryClass.AGENT`, admits through lane-keyed capacity, is governed by a `psutil` resource snapshot, and appends to an NDJSON ledger. No health-monitoring noise.

## Data layer (`db/`)

- `schema.sql` (the `CREATE EXTENSION` census, `CREATE SCHEMA maghz`, the `kb_english` text-search configuration, enum types, tables, and plain indexes), `routines.sql` (function, trigger, exotic-index, view, and IMMV bodies that bind to those tables), `cron.sql` (`pg_cron` jobs registered in `postgres`, executed in `maghz` via `schedule_in_database`), and the `search/` text-search dictionaries (`synonyms.syn`, `thesaurus.ths`) staged into the container `tsearch_data` dir by `docker cp`. `schema apply` runs the dictionaries first, then `schema.sql`, `routines.sql`, `cron.sql` in that order.
- The PG extension profile is owned by `admin/profile.py`; it renders the `image/Dockerfile` apt block and the `db/schema.sql` `CREATE EXTENSION` census, and `maghz schema doctor` asserts the live census. The custom **ParadeDB PG18** image carries `pg_search` (BM25), `pgvector` (HNSW), `pg_ivm`, `pg_net`, `pgmq`, `hll`, `pg_partman`, and the `unaccent`/thesaurus/synonym FTS dictionary stack.
- **RRF hybrid search** fuses BM25 (lexical), dense `pgvector` cosine (semantic), and trigram fuzzy ranks; the in-DB `pg_net` → Ollama (`nomic-embed-text`) pipeline embeds concepts on a two-step cron tick.

## Remote / VPS

`maghz exec` and `maghz deploy` run and deploy the whole stack on the live Hostinger VPS: a `git ls-files` working-tree push, remote `up` + `schema apply`, an SFTP artifact pull, all behind a typed `ExecReceipt`. Secrets reach the VPS via an `OP_SERVICE_ACCOUNT_TOKEN`.

## Cloud sync

`rclone` Google Drive + OneDrive remotes: a scheduled `pg_dump` + content backup to **both**, an `rclone bisync` of the content tree, and a restore path — driven by the `Sync` automation action and exposed as `maghz cloud sync`.

## MCP + skills

- **MCP-as-IaC** — `admin/mcp/ops.py` models the 8-server fleet (`postgres`, `n8n`, `workspace`, `notebooklm`, `exa`, `perplexity`, `tavily`, `hostinger`) and emits the committed `${VAR}`/`${VAR:-default}` `.mcp.json`, run under `op run -- claude` so secrets inject at the boundary and travel to the VPS unchanged.
- **n8n** — a Pulumi-managed container (local + VPS) with `N8N_MCP_ACCESS_ENABLED`, workflows committed via the native CLI, authored through the adopted `n8n-mcp` + `n8n-skills`.
- **Owned skills** — `maghz-operator`, `automations`, `cloud-sync`, `agy`, `forge-usage`. **Adopted** — `n8n-mcp`, `workspace-mcp`, `postgres-mcp`, `heptabase-cli`.

## Secrets

`op` (the 1Password `Tokens` vault) is the single source: the Forge `op inject` chain → the `setup-env.sh` injector → agents. Secrets are added to the vault and the injector; the VPS authenticates via `OP_SERVICE_ACCOUNT_TOKEN`. The committed `.mcp.json` carries only `${VAR}` placeholders — never secret values.
