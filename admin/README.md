# `admin/` — the `maghz` operator

`admin/` is the **`maghz`** CLI: the single, agent-first operator for the Maghz second brain — a local + remote + cloud "self-driving" manager over a PostgreSQL knowledge ledger, driven by AI agents and automations. Heptabase owns content; PostgreSQL is the durable centralized ledger; `maghz` orchestrates the database lifecycle, the automation arm, secrets, remote/VPS control, cloud sync, and the MCP/skill tool surface — every concern behind one polymorphic CLI that emits a typed JSON `Envelope`.

## Goals

- **Agent-first OPERATOR** — one CLI (`maghz`) agents invoke for every lifecycle, ledger, and automation concern; research/content tools stay first-class skills/MCPs the operator composes, never re-wrapped.
- **Full local + remote + cloud self-driving manager** — local stack lifecycle + self-heal, remote/VPS over SSH, cloud sync to Google Drive + OneDrive.
- **Resilience / non-fragility** over health-monitoring noise: typed retry classes, lane-keyed admission, idempotent apply, orphan-free `up`/`down`.
- **The automation arm is the lynchpin** — a fully parameterized `Trigger × Action` ADT, agent-invocable, with typed receipts.

## Architecture (`admin/` layout)

| File | Owns |
| --- | --- |
| `__init__.py` | package import bootstrap: beartype claw and warning suppression only |
| `__main__.py` | the `cyclopts` CLI entrypoint: modal verbs over owner rails, lowering every outcome to the JSON `Envelope` and exit code |
| `automation.py` | the `Trigger × Action` automation ADT and engine over `watchfiles`, APScheduler, lane admission, psutil receipts, and NDJSON ledger writes |
| `core.py` | the JSON `Envelope` / `Status` / `Detail` / `Row` receipt owners (the result + fault rail) |
| `db.py` | the `pg8000` query boundary (every call offloads off the event loop; faults lift to the one `BoundaryFault` family) |
| `infra.py` | Pulumi Automation API stack for the custom PG image, `db`, `ollama`, and `n8n` containers behind `StackOp` (`up` / `down` / `status`), stage-discriminated: `local` converges Colima, `prd` converges the VPS system daemon over the derived `ssh://` endpoint |
| `mcp.py` | MCP-as-IaC: the 12-server fleet and the Claude `.mcp.json` plus Codex `.codex/config.toml` projections |
| `profile.py` | the typed PG extension catalog (`_PROFILE` / `Extension`) rendering the `image/Dockerfile` apt block and the `db/schema.sql` `CREATE EXTENSION` census |
| `rails.py` | schema apply/doctor, ledger projections, Heptabase sync, cloud backup/restore, and n8n workflow rails |
| `remote.py` | the `exec` request rail: one scoped `asyncssh` connection, git working-tree push, remote command, and SFTP artifact pull |
| `runtime.py` | boundary rails, retry policy, lane admission, structured drains, typed receipts, and `Signals` logging |
| `settings.py` | `MaghzSettings` — the one validated config owner; no other code reads `os.environ` |

## CLI surface (`maghz <verb>`)

| Verb | Does |
| --- | --- |
| `up` / `down` / `status` | converge / tear down / preview the `MAGHZ_INFRA__STAGE`-selected docker stack (Pulumi: `db` + `ollama` + `n8n`) |
| `health` | probe the service plane (postgres, ollama, n8n, atuin) through the loopback ports; a down service grades `failed` |
| `schema apply` / `schema doctor` | apply the idempotent schema (`docker cp` of the `db/search/` dictionaries, then `psql` over `db/schema.sql` + `db/routines.sql` + `db/cron.sql`); assert the live extension census |
| `ledger <projection>` | one read projection over the ledger |
| `sync diff` / `sync generate` | reconcile canonical concepts against Heptabase cards |
| `cloud sync` / `cloud restore` | back up + bisync content to Google Drive + OneDrive; restore |
| `n8n export` / `n8n import` / `n8n status` | move committed workflows in and out of the n8n container |
| `automation run` | drive an automation (a `Trigger × Action`); emits a typed `AutomationReceipt` |
| `mcp generate` / `validate` / `diff` / `watch` | emit, check, diff, and watch the committed Claude and Codex MCP configs from the typed server model |
| `exec` | run one command on the remote VPS under the pushed working tree |

## The automation arm (the lynchpin)

A fully parameterized `Automation = Trigger × Action`, agent-invocable:

- **`Trigger`** = `Watch` (`watchfiles` file events) · `Schedule` (APScheduler cron) · `Manual`.
- **`Action`** = `AgentAction` · `Notify` · `Embed` · `Sync`.
- Agents drive it via `maghz automation run`; each run emits a typed `AutomationReceipt`, retries under the action-owned `RetryClass`, admits through lane-keyed capacity, is governed by a `psutil` resource snapshot, and appends to an NDJSON ledger.

## Data layer (`db/`)

- `schema.sql` (the `CREATE EXTENSION` census, `CREATE SCHEMA maghz`, the `kb_english` text-search configuration, enum types, tables, and plain indexes), `routines.sql` (function, trigger, exotic-index, view, and IMMV bodies that bind to those tables), `cron.sql` (`pg_cron` jobs registered in `postgres`, executed in `maghz` via `schedule_in_database`), and the `search/` text-search dictionaries (`synonyms.syn`, `thesaurus.ths`) staged into the container `tsearch_data` dir by `docker cp`. `schema apply` runs the dictionaries first, then `schema.sql`, `routines.sql`, `cron.sql` in that order.
- The PG extension profile is owned by `admin/profile.py`; it renders the `image/Dockerfile` apt block and the `db/schema.sql` `CREATE EXTENSION` census, and `maghz schema doctor` asserts the live census. The custom **ParadeDB PG18** image carries `pg_search` (BM25), `pgvector` (HNSW), `pg_ivm`, `pg_net`, `pgmq`, `hll`, `pg_partman`, and the `unaccent`/thesaurus/synonym FTS dictionary stack.
- **RRF hybrid search** fuses BM25 (lexical), dense `pgvector` cosine (semantic), and trigram fuzzy ranks; the in-DB `pg_net` → Ollama (`nomic-embed-text`) pipeline embeds concepts on a two-step cron tick.

## Remote / VPS

Stage-`prd` stack verbs converge the live Hostinger VPS directly: the Pulumi program targets the VPS system daemon over `ssh://maghz-agent@<host>`, and the schema apply plus health probes ride the tunnel loopback — no remote Python toolchain exists or is needed. `maghz exec` remains the agent shell rail: a `git ls-files` working-tree push, one remote command, an SFTP artifact pull, all behind a typed `ExecReceipt`. The VPS-side secret ingress is the directory-scoped read-only Doppler token (`maghz/prd_host`) at `/srv/maghz`.

## Cloud sync

`rclone` Google Drive + OneDrive remotes: a scheduled `pg_dump` + content backup to **both**, an `rclone bisync` of the content tree, and a restore path — driven by the `Sync` automation action and exposed as `maghz cloud sync`.

## MCP + skills

- **MCP-as-IaC** — `admin/mcp.py` models the 12-server fleet (`postgres`, `google-workspace`, `notebooklm`, `exa`, `perplexity`, `tavily`, `hostinger`, `github`, `context7`, `greptile`, `nuget`, `jupyter`) and emits the committed Claude `.mcp.json` plus Codex `.codex/config.toml` projections from one table. Secret values stay in environment variables and never in generated config files.
- **n8n** — future workflow automation surface; not part of the active MCP fleet until n8n is deliberately configured.
- **Skills** — the estate skill mirror under `.claude/skills/` propagates from its masters (Forge harness skills, Rasm methodology skills); the MCP fleet rows above are the tool surface.

## Secrets

Doppler is the single backend: the `setup-env.sh` injector resolves the directory-scoped config (`maghz/dev` locally) into each agent's environment, and stage-`prd` invocations run under `doppler run --project maghz --config prd_host`. The VPS-side consumer is the read-only `maghz-host-readonly` service token scoped to `/srv/maghz`. The committed `.mcp.json` carries only `${VAR}` placeholders — never secret values.
