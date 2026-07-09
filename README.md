# Maghz

An agent-operated second brain. Heptabase owns note content, the PostgreSQL `maghz` database is the durable centralized ledger and hybrid-search engine, and the `admin/` Python CLI is the one operator surface that agents and automations drive. Every surface is agent-facing: the CLI emits one JSON `Envelope` per call with no human prompts, no interactive flags, and no decorative output. Automation is the central design pressure — the n8n workflows and the autonomous agent skills ride infrastructure (the schema, the embed pipeline, the rails, the MCP fleet, the VPS deploy path) that already runs. One stack definition serves two hosts: the local Mac for development parity and the `maghz` NixOS VPS as the durable home.

## [01]-[LAYOUT]

| [INDEX] | [PATH]         | [OWNS]                                                                                                    |
| :-----: | :------------- | :--------------------------------------------------------------------------------------------------------- |
|  [01]   | `admin/`       | The `maghz` cyclopts CLI as flat single-concern modules; `admin/README.md` is the per-module charter.     |
|  [02]   | `db/`          | `schema.sql`, `routines.sql`, `cron.sql`, the `search/` text-search dictionaries, and `init/n8n.sql`. Declarative and idempotent — no numbered migrations. |
|  [03]   | `image/`       | The custom ParadeDB-plus-extensions Postgres image (`Dockerfile`), its apt block generated from `admin/profile.py`. |
|  [04]   | `compose.yaml` | The transitional stack declaration: `local` and `prd` profiles run the same `db`/`ollama`/`n8n` services on the same loopback ports. |
|  [05]   | `workflows/`   | Committed n8n workflow files; `maghz n8n export`/`import` move them in and out of the container.          |
|  [06]   | `docs/`        | Durable law: `docs/standards/` (the doctrine pair plus the prose owners) and `docs/stacks/` language atlases. |
|  [07]   | `.claude/`     | Agent configuration: skills, workflows, the `setup-env.sh` secret-forwarding hook, and `bootstrap-cli-tools.sh`. |

[SEAM]: `compose.yaml` retires when `admin/infra.py` `StackOp` owns the full topology on both hosts; until then a service change lands in both surfaces in the same pass.

## [02]-[HOW_IT_WORKS]

The `admin/` package is functional Railway-Oriented Programming over one closed `BoundaryFault` family. Every domain operation returns a `RuntimeRail[Envelope]`; the CLI lowers it to one stdout `Envelope` at the edge. `admin/runtime.py` is the substrate — the rail, the fault classifier, the bounded `drain` lane, retry policies, and structured receipts — and every consumer (`rails.py`, `infra.py`, `mcp.py`, `automation.py`, `remote.py`) composes it rather than re-deriving spawn, retry, or fault handling.

Two surfaces meet at the database and never collapse into each other. The CLI rails own deterministic, receipted truth: schema apply, ledger projections, Heptabase sync, cloud backup, and infra lifecycle. The MCP fleet owns live exploration: an agent reaches the database, web research, and the VPS through MCP when it is investigating, not committing. `postgres` and `n8n` are deliberately dual-surface — the rail is the deterministic owner (schema and ledger through the CLI; n8n workflow files on disk), and the MCP is the live agent lens over the same system. Deterministic work goes through the `maghz` CLI; exploratory work goes through MCP; never the reverse.

Retrieval is hybrid and in-database: `pg_search` BM25 (lexical), `pgvector` HNSW cosine (semantic), and `pg_trgm`/FTS (fuzzy) fused through Reciprocal Rank Fusion in `maghz.search()`. Embeddings are produced in the database — `pg_net` posts each concept to local Ollama `nomic-embed-text` and the response writes back as `vector(768)` — on a two-step `pg_cron` sweep, with no application round-trip and no embedding API key.

## [03]-[CLI_SURFACE]

`maghz <command> [subcommand] [args]` (invoked as `uv run python -m admin …`). Each command discriminates on a closed verb and returns one typed `Envelope`; `maghz --help` is the live verb census.

| [INDEX] | [COMMAND]                | [DOES]                                                                                              |
| :-----: | :----------------------- | :--------------------------------------------------------------------------------------------------- |
|  [01]   | `up` / `down` / `status` | Pulumi stack lifecycle: build the image and start the db/ollama/n8n services, tear them down, or preview the converge. |
|  [02]   | `schema apply`           | Idempotent apply in dependency order: stage the `db/search/` dictionaries, then `psql` the three SQL files; a replay is a clean no-op. |
|  [03]   | `schema doctor`          | Parse the declarative SQL into an object census and assert the live `pg_extension` census equals the `admin/profile.py` catalog. |
|  [04]   | `ledger <kind>`          | Read projections over the ledger: `coverage`, `gaps`, `stale`, `next`, `owner`.                     |
|  [05]   | `sync`                   | Reconcile Heptabase cards against the ledger (`diff` the drift, `generate` the writes).             |
|  [06]   | `cloud`                  | rclone off-site backup: `pg_dump` plus bisync to the configured remotes, and restore.               |
|  [07]   | `n8n`                    | n8n workflow file export/import and an API status probe.                                            |
|  [08]   | `mcp`                    | The MCP fleet as IaC: `generate`, `validate` (every `${MAGHZ_MCP__*}` placeholder is backed), `diff`, `watch`, and `converge` for docker-run server images. |
|  [09]   | `exec` / `deploy`        | VPS operation over asyncssh: `exec` a command or `deploy` the stack, pushing the working tree and running `maghz` on the host. |
|  [10]   | `automation run`         | Drive one automation spec (`--spec`); the `trigger` selects the watch/schedule/manual lane. The agent skills it dispatches are tracked open work. |

## [04]-[MCP_FLEET]

`admin/mcp.py` is the typed owner of the 12-server fleet and generates the committed `${VAR}`-placeholder Claude `.mcp.json`; secrets resolve from environment variables and are never written to the file. `maghz mcp validate` proves every placeholder is backed; health resolves from live calls, never from prose.

| [INDEX] | [SERVER]           | [REACH]                         | [TRANSPORT]                                                    |
| :-----: | :----------------- | :------------------------------ | :-------------------------------------------------------------- |
|  [01]   | `postgres`         | live database exploration       | `forge-maghz-postgres-mcp` over `MAGHZ_MCP__DATABASE_URI`      |
|  [02]   | `exa`              | web search                      | HTTP remote                                                    |
|  [03]   | `perplexity`       | cited research                  | `forge-perplexity-mcp`                                         |
|  [04]   | `tavily`           | web search                      | `forge-tavily-mcp`                                             |
|  [05]   | `hostinger`        | VPS provider lifecycle          | `forge-hostinger-mcp`                                          |
|  [06]   | `google-workspace` | Google Workspace                | `forge-workspace-mcp`; first-use OAuth consent per account     |
|  [07]   | `notebooklm`       | source ingestion                | `notebooklm-mcp`, local cookie auth                            |
|  [08]   | `github`           | repository API                  | HTTP remote                                                    |
|  [09]   | `context7`         | live library docs               | HTTP remote                                                    |
|  [10]   | `greptile`         | whole-repo semantic code review | HTTP remote                                                    |
|  [11]   | `nuget`            | NuGet package intelligence      | `nuget-mcp`; binds only where the .NET SDK exists              |
|  [12]   | `jupyter`          | notebook research               | `forge-jupyter-mcp`; binds only where a JupyterLab server runs |

[SEAM]: the rail's Codex projection still renders `.codex/config.toml`; the repo carries no `.codex/` directory because `~/.codex/config.toml` is the sole Codex configuration home, and the projection retires with the next fleet-rail pass.

## [05]-[HOSTS_AND_ACCESS]

The stack runs identically on two hosts, and the loopback port set is invariant across them — the same DSN and service URLs resolve on either end.

- Local Mac: Colima owns the Docker runtime; `maghz up` converges the stack; every service binds `127.0.0.1`.
- `maghz` VPS: the Forge flake's `nixosConfigurations.maghz` owns the operating system — static network, firewall (SSH only), system Docker daemon, declarative users. Services stay loopback on the VPS.
- Tunnel: the Forge `vpsTunnels` row projects the VPS services onto the local loopback through a health-gated launchd tunnel agent, so local agents and MCP servers reach the remote database at the same address as the local one. The tunnel agent and the local stack profile are mutually exclusive owners of those ports — run one, never both.

Three identities partition the VPS: `root` carries only the `forge-redeploy` activation rail, `bardiasamiee` is the operator user owning the Home Manager estate, and `maghz-agent` is the workload identity owning the compose plane and the deploy workroot `/home/maghz-agent/maghz`. `maghz deploy` pushes the working tree over SFTP as `maghz-agent`, runs remote `maghz up` plus `schema apply`, and returns receipts stamped with the deployed commit. Host-level failures route to the Forge owner; stack-level failures route to the `admin/` rails.

## [06]-[BRING_UP]

1. The Docker runtime is running; the docker endpoint self-detects (`MAGHZ_INFRA__DOCKER_HOST` overrides).
2. Secrets are present in the process environment (Parametric_Forge injects them; see below).
3. `maghz up` drives Pulumi to build the custom image and start the Postgres, Ollama, and n8n services. The Ollama embed model is pulled as the converge's follow-on.
4. `maghz schema apply` then `maghz schema doctor` apply and assert the schema and extension census.
5. `maghz down` tears the whole stack down and leaves no orphaned containers, networks, or volumes.

The connection string is `MAGHZ_DATABASE_DSN`, default `postgresql://maghz@127.0.0.1:15435/maghz` — passwordless trust auth on the loopback port, with `maghz` as the superuser, so agents and MCP servers auto-authenticate.

## [07]-[CONVENTIONS]

- [NO_MIGRATIONS]: Maghz never uses migration files, `NNN_*.sql` numbered scripts, version tables, or up/down pairs. The schema is declarative: `db/schema.sql`, `db/routines.sql`, and `db/cron.sql` are each idempotent (every statement `IF NOT EXISTS`, `CREATE OR REPLACE`, or DO-guarded). A schema change edits these files in place; `maghz schema apply` replays them and a replay is a clean no-op.
- [AGENT_ONLY]: there are no human-facing flags, prompts, or decorative output. The JSON `Envelope` on stdout is the result contract; structlog diagnostics ride stderr.
- [SINGLE_OWNER]: one canonical semantic name per bounded concept; arity, provider, and modality live in request shape, case, or policy row — never parallel command families.

## [08]-[PARAMETRIC_FORGE]

[Parametric_Forge](../Parametric_Forge) is the Nix owner of both hosts: the local Mac (nix-darwin) and the `maghz` VPS (`nixosConfigurations.maghz`), deployed through the one `forge-redeploy` rail. Maghz assumes the Forge toolchain on `PATH` and never imports it; when a toolchain, secret, host, or tunnel surface fails, fix the Forge owner, not `admin/`. `AGENTS.md [06]` carries the per-tool inventory.

Secret flow: Doppler is the sole backend — the canonical `.claude/hooks/setup-env.sh` resolves each Doppler source row live (encrypted snapshot on fetch failure, per-source verdicts) and writes the selected keys into each agent's environment; the `maghz` Doppler project's `prd_host` config owns the stack secrets, and 1Password holds only operator-personal items. Doppler topology — projects, configs, service tokens — mutates only through Forge `services/` Pulumi rows.

| [INDEX] | [CONCERN]            | [FORGE_OWNER]                                                  |
| :-----: | :------------------- | :------------------------------------------------------------- |
|  [01]   | VPS operating system | `hosts/context.nix` (the `maghz` host row) + `modules/nixos/` (users, network, firewall, system Docker) |
|  [02]   | SSH access + tunnels | `modules/home/programs/shell-tools/ssh.nix` (the `vpsTunnels` registry: interactive hosts, forwards, launchd tunnel agent) |
|  [03]   | Secret custody       | `services/topology.ts` (Doppler rows) + the canonical `.claude/hooks/setup-env.sh` injection hook |
|  [04]   | GitHub repo settings | `services/topology.ts` (`@pulumi/github` rows — merge hygiene, rulesets); the services driver preview verifies, never the GitHub UI |
|  [05]   | Python toolchain     | `modules/home/programs/languages/python-tools.nix` (`uv`, `ruff`, `ty`), `…/scientific-tools.nix` (native build env) |
|  [06]   | Postgres clients     | `modules/home/programs/languages/db-tools.nix` (`psql`, `pgcli`, `pg_dump`/`pg_restore`) |
|  [07]   | Container runtime    | `modules/home/programs/container-tools/` (`colima`, `docker`), `modules/home/environments/containers.nix` (session vars) |
|  [08]   | Pulumi / Node / Git  | `…/languages/dev-tools.nix` (`pulumi`), `…/languages/node-tools.nix` (`node`/`npx`), `…/git-tools/` (`git`, `gh`) |
