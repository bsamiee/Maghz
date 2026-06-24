# Maghz

An agent-operated second brain. Heptabase owns note content, the PostgreSQL 18.4 `maghz` database is the durable centralized ledger and hybrid-search engine, and the `admin/` Python CLI is the one operator surface that agents and automations drive. Every surface is agent-facing: the CLI emits one JSON `Envelope` per call with no human prompts, no interactive flags, and no decorative output. Automation is the central design pressure — the n8n workflows and the autonomous agent skills are not built yet, but the infrastructure they ride (the schema, the embed pipeline, the rails, the MCP fleet, the VPS deploy path) is in place and verified live.

## Layout

| [PATH]     | [OWNS]                                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `admin/`   | The `maghz` cyclopts CLI, the runtime rail substrate (`admin/runtime/`), the domain rails (`admin/rails/`), the Pulumi infra (`admin/infra/`), the MCP fleet (`admin/mcp/`), the automation engine (`admin/automation/`), and `admin/profile.py` (the typed PG extension census). |
| `db/`      | `schema.sql`, `routines.sql`, `cron.sql`, the `search/` text-search dictionaries, and `init/n8n.sql`. Declarative and idempotent — no numbered migrations. |
| `image/`   | The custom ParadeDB-plus-extensions Postgres image (`Dockerfile`), its apt block generated from `admin/profile.py`.              |
| `.claude/` | Agent configuration: skills, workflows, the `setup-env.sh` secret-forwarding hook, and `bootstrap-cli-tools.sh`.                 |

## How it works

The `admin/` package is functional Railway-Oriented Programming over one closed `BoundaryFault` family. Every domain operation returns a `RuntimeRail[Envelope]`; the CLI lowers it to one stdout `Envelope` at the edge. `admin/runtime/` is the substrate — the rail, the fault classifier, the bounded `drain` lane, retry policies, and structured receipts — and every consumer (`rails/`, `infra/`, `mcp/`, `automation/`) composes it rather than re-deriving spawn, retry, or fault handling.

Two surfaces meet at the database and never collapse into each other. The **CLI rails** own deterministic, receipted truth: schema apply, ledger projections, Heptabase sync, cloud backup, and infra lifecycle. The **MCP fleet** owns live exploration: an agent reaches the database, web research, and the VPS through MCP when it is investigating, not committing. `postgres` and `n8n` are deliberately dual-surface — the rail is the deterministic owner (schema and ledger through the CLI; n8n workflow files on disk), and the MCP is the live agent lens over the same system. Deterministic work goes through the `maghz` CLI; exploratory work goes through MCP; never the reverse.

Retrieval is hybrid and in-database: `pg_search` BM25 (lexical), `pgvector` HNSW cosine (semantic), and `pg_trgm`/FTS (fuzzy) fused through Reciprocal Rank Fusion in `maghz.search()`. Embeddings are produced in the database — `pg_net` posts each concept to local Ollama `nomic-embed-text` and the response writes back as `vector(768)` — on a two-step `pg_cron` sweep, with no application round-trip and no embedding API key.

## CLI surface

`maghz <command> [subcommand] [args]` (invoked as `uv run python -m admin …`). Each command discriminates on a closed verb and returns one typed `Envelope`.

| [COMMAND]            | [DOES]                                                                                                       |
| -------------------- | ----------------------------------------------------------------------------------------------------------- |
| `up` / `down` / `status` | Pulumi stack lifecycle: build the image and start the db/ollama/n8n services, tear them down, or preview the converge. |
| `schema apply`       | Idempotent apply in dependency order: `docker cp` the `db/search/` dictionaries, then `psql -v ON_ERROR_STOP=1 -f` over `db/schema.sql` -> `db/routines.sql` -> `db/cron.sql`. A replay is a clean no-op. |
| `schema doctor`      | Parse the declarative SQL into an object census and assert the live `pg_extension` census equals the `admin/profile.py` catalog. |
| `ledger <kind>`      | Read projections over the ledger: `coverage`, `gaps`, `stale`, `next`, `owner`.                             |
| `sync`               | Reconcile Heptabase cards against the ledger (`diff` the drift, `generate` the writes).                     |
| `cloud`              | rclone off-site backup: `pg_dump` plus bisync to the configured remotes, and restore.                       |
| `n8n`                | n8n workflow file export/import and an API status probe.                                                    |
| `mcp`                | The `.mcp.json` fleet as IaC: `generate`, `validate` (every `${MAGHZ_MCP__*}` placeholder is backed), `diff` against the committed file, `watch` to regenerate on change, `converge` the docker-run server images. |
| `exec` / `deploy`    | VPS operation over asyncssh: `exec` a command or `deploy` the stack, pushing the working tree and running `maghz` on the host. |
| `automation run`     | Drive one automation spec (`--spec`); the `trigger` selects the watch/schedule/manual lane. The agent skills it dispatches are pending. |

## MCP fleet

`admin/mcp/ops.py` is the typed owner of the 8-server fleet and generates the committed `${VAR}`-placeholder `.mcp.json`; secrets resolve at the `op run -- claude` boundary and are never written to the file.

| [SERVER]     | [REACH]                          | [STATUS]                                                |
| ------------ | -------------------------------- | ------------------------------------------------------- |
| `postgres`   | live database exploration        | live (`uvx --python 3.13 postgres-mcp`)                 |
| `exa`        | web search                       | live                                                    |
| `perplexity` | cited research                   | live                                                    |
| `tavily`     | web search                       | live                                                    |
| `hostinger`  | VPS management                   | live                                                    |
| `workspace`  | Google Workspace                 | pending the Google OAuth credentials                    |
| `n8n`        | workflow automation              | pending the n8n API key                                 |
| `notebooklm` | source ingestion                 | local cookie auth                                       |

## Bring-up

1. Colima and the Docker runtime are running; the docker endpoint self-detects (`MAGHZ_INFRA__DOCKER_HOST` overrides).
2. Secrets are present in the process environment (Parametric_Forge injects them; see below).
3. `maghz up` drives Pulumi to build the custom image and start the Postgres, Ollama, and n8n services. The Ollama embed model is pulled as the converge's follow-on.
4. `maghz schema apply` then `maghz schema doctor` apply and assert the schema and extension census.
5. `maghz down` tears the whole stack down and leaves no orphaned containers, networks, or volumes.

The connection string is `MAGHZ_DATABASE_DSN`, default `postgresql://maghz@127.0.0.1:15435/maghz` — passwordless trust auth on the loopback port, with `maghz` as the superuser, so agents and MCP servers auto-authenticate.

## Conventions

- **No migrations.** Maghz never uses migration files or `NNN_*.sql` numbered scripts, version tables, or up/down pairs. The schema is declarative: `db/schema.sql`, `db/routines.sql`, and `db/cron.sql` are each idempotent (every statement `IF NOT EXISTS`, `CREATE OR REPLACE`, or DO-guarded). A schema change edits these files in place; `maghz schema apply` replays them and a replay is a clean no-op.
- **Agent-only.** There are no human-facing flags, prompts, or decorative output. The JSON `Envelope` on stdout is the result contract; structlog diagnostics ride stderr.
- **Single owner per concept.** One canonical semantic name per bounded concept; arity, provider, and modality live in request shape, case, or policy row — never parallel command families.

## Parametric_Forge

[Parametric_Forge](../Parametric_Forge) is the local-macOS Nix/Home-Manager owner of the machine toolchain and secret injection. Maghz assumes it on `PATH` and never imports it; when a toolchain or secret surface fails, fix the Forge owner, not `admin/`. `AGENTS.md [06]` carries the full per-tool inventory.

Secret flow: `op inject` runs at `home-manager switch` against `~/.config/op/env.template`, writing `~/.config/hm-op-session.sh`; the shell sources it at login; `.claude/hooks/setup-env.sh` forwards the selected keys into each agent's environment.

| [CONCERN]            | [FORGE OWNER]                                                  |
| -------------------- | ------------------------------------------------------------- |
| Secret injection     | `modules/home/programs/shell-tools/1password.nix` (+ generated `~/.config/op/env.template`, `~/.config/hm-op-session.sh`) |
| Python toolchain     | `modules/home/programs/languages/python-tools.nix` (`uv`, `ruff`, `ty`), `…/scientific-tools.nix` (native build env) |
| Postgres clients     | `modules/home/programs/languages/db-tools.nix` (`psql`, `pgcli`, `pg_dump`/`pg_restore`) |
| Container runtime    | `modules/home/programs/container-tools/colima.nix` (`colima`, `docker`), `modules/home/environments/containers.nix` (session vars) |
| Pulumi / Node / Git  | `…/languages/dev-tools.nix` (`pulumi`), `…/languages/node-tools.nix` (`node`/`npx`), `…/git-tools/` (`git`, `gh`) |

Gaps Forge does not cover: `GOOGLE_OAUTH_*` and `N8N_API_KEY` are absent from the vault template; `ollama` has no Forge owner; Forge is local-macOS only and provisions no remote/VPS box.
