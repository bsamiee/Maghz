# `admin/` — the `maghz` operator

`admin/` is the **`maghz`** CLI: the single, agent-first operator for the Maghz second brain — a local + remote + cloud "self-driving" manager over a PostgreSQL knowledge ledger, driven by AI agents and automations. Heptabase owns content; PostgreSQL is the durable centralized ledger; `maghz` orchestrates database lifecycle, automation, secret consumption, remote/VPS control, and cloud sync through one polymorphic CLI that emits a typed JSON `Envelope`. Forge-owned MCP and skill surfaces remain external agent lenses.

## [01]-[GOALS]

- [OPERATOR]: one `maghz` CLI owns lifecycle, ledger, and automation concerns; research tools remain first-class skills and MCPs.
- [ESTATE]: one stage-polymorphic manager owns local, VPS, and cloud operation.
- [RESILIENCE]: typed retry classes, lane admission, idempotent apply, and orphan-free lifecycle replace monitoring noise.
- [AUTOMATION]: one parameterized `Trigger × Action` ADT emits typed receipts.

## [02]-[ARCHITECTURE_ADMIN_LAYOUT]

`infra.py` discriminates `local` Colima and `prd` VPS daemon targets through `MAGHZ_INFRA__STAGE`; every other module consumes that admitted stage.

| [INDEX] | [FILE]          | [OWNS]                                               |
| :-----: | :-------------- | :--------------------------------------------------- |
|  [01]   | `__init__.py`   | Beartype package bootstrap                           |
|  [02]   | `__main__.py`   | Cyclopts routing and final envelope lowering         |
|  [03]   | `automation.py` | Trigger-action engine and automation ledger          |
|  [04]   | `core.py`       | Envelope, status, detail, and row ADTs               |
|  [05]   | `db.py`         | Asynchronous `pg8000` query boundary                 |
|  [06]   | `infra.py`      | Stage-polymorphic Pulumi service topology            |
|  [07]   | `profile.py`    | PostgreSQL extension catalog and projections         |
|  [08]   | `rails.py`      | Schema, ledger, Heptabase, cloud, and n8n rails      |
|  [09]   | `remote.py`     | Scoped asyncssh push-execute-pull rail               |
|  [10]   | `runtime.py`    | Fault, retry, admission, drain, and signal substrate |
|  [11]   | `settings.py`   | Sole validated environment and configuration ingress |

## [03]-[CLI_SURFACE_MAGHZ_VERB]

| [INDEX] | [VERB]                                     | [DOES]                                  |
| :-----: | :----------------------------------------- | :-------------------------------------- |
|  [01]   | `up` / `down` / `status`                   | Converge, destroy, or preview the stack |
|  [02]   | `health`                                   | Census the loopback service plane       |
|  [03]   | `schema apply` / `schema doctor`           | Apply or assert declarative SQL         |
|  [04]   | `ledger <projection>`                      | Read one ledger projection              |
|  [05]   | `sync diff` / `sync generate`              | Reconcile Heptabase-backed concepts     |
|  [06]   | `cloud sync` / `cloud restore`             | Replicate or restore durable content    |
|  [07]   | `n8n export` / `n8n import` / `n8n status` | Move or census workflow files           |
|  [08]   | `automation run`                           | Execute one trigger-action request      |
|  [09]   | `exec`                                     | Run the scoped remote worktree rail     |

## [04]-[THE_AUTOMATION_ARM_THE_LYNCHPIN]

A fully parameterized `Automation = Trigger × Action`, agent-invocable:

- [TRIGGER]: `Watch` (`watchfiles` events), `Schedule` (APScheduler cron), or `Manual`.
- [ACTION]: `Notify`, `Embed`, or `Sync`; a new action lands as one struct, one dispatch arm, and one evidence row.
- Agents drive it via `maghz automation run`; each run emits a typed `AutomationReceipt`, retries under the action-owned `RetryClass`, admits through lane-keyed capacity, is governed by a `psutil` resource snapshot, and appends to an NDJSON ledger.

## [05]-[DATA_LAYER_DB]

- `schema.sql` (the `CREATE EXTENSION` census, `CREATE SCHEMA maghz`, the `kb_english` text-search configuration, enum types, tables, and plain indexes), `routines.sql` (function, trigger, exotic-index, view, and IMMV bodies that bind to those tables), `cron.sql` (`pg_cron` jobs registered in `postgres`, executed in `maghz` via `schedule_in_database`), and the `search/` text-search dictionaries (`synonyms.syn`, `thesaurus.ths`) staged into the container `tsearch_data` dir by `docker cp`. `schema apply` runs the dictionaries first, then `schema.sql`, `routines.sql`, `cron.sql` in that order.
- The PG extension profile is owned by `admin/profile.py`; it renders the `image/Dockerfile` apt block and the `db/schema.sql` `CREATE EXTENSION` census, and `maghz schema doctor` asserts the live census. The custom ParadeDB PG18 image carries `pg_search` (BM25), `pgvector` (HNSW), `pg_ivm`, `pg_net`, `pgmq`, `hll`, `pg_partman`, and the `unaccent`/thesaurus/synonym FTS dictionary stack.
- RRF hybrid search fuses BM25, dense `pgvector` cosine, and trigram fuzzy ranks; the in-database `pg_net` to Ollama pipeline embeds concepts on a two-step cron tick.

## [06]-[REMOTE_VPS]

Stage-`prd` stack verbs converge the live Hostinger VPS directly: the Pulumi program targets the VPS system daemon over `ssh://maghz-agent@<host>`, and the schema apply plus health probes ride the tunnel loopback — no remote Python toolchain exists or is needed. `maghz exec` remains the agent shell rail: a `git ls-files` working-tree push, one remote command, an SFTP artifact pull, all behind a typed `ExecReceipt`. The VPS-side secret ingress is the directory-scoped read-only Doppler token (`maghz/prd_host`) at `/srv/maghz`.

## [07]-[CLOUD_SYNC]

`rclone` schedules `pg_dump`, content backup to both remotes, content-tree bisync, and restore through the `Sync` action and `maghz cloud sync`.

## [08]-[MCP_SKILLS]

- [MCP_FLEET]: Forge owns every client registration and projects the Maghz-backed `postgres` and `doppler-remote` rows. `admin/infra.py` owns the remote `maghz-mcp` container; no `admin` rail generates client configuration.
- [N8N]: workflow automation remains outside the MCP fleet until a credentialed consumer is admitted.
- [SKILLS]: `.claude/skills/` mirrors Forge harness masters and Rasm methodology masters; the fleet rows above remain the tool surface.

## [09]-[SECRETS]

Doppler is the single backend: the `setup-env.sh` injector resolves the directory-scoped config (`maghz/dev` locally) into each agent's environment, and stage-`prd` invocations run under `doppler run --project maghz --config prd_host`. The VPS-side consumer is the read-only `maghz-host-readonly` service token scoped to `/srv/maghz`; Forge projects the remote MCP command without resolving that token on the client.
