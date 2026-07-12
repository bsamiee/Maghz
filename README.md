# Maghz

An agent-operated second brain. Heptabase owns note content, the PostgreSQL `maghz` database is the durable centralized ledger and hybrid-search engine, and the `admin/` Python CLI is the one operator surface that agents and automations drive. Every surface is agent-facing: the CLI emits one JSON `Envelope` per call with no human prompts, no interactive flags, and no decorative output. Automation is the central design pressure — the n8n workflows ride infrastructure (the schema, embed pipeline, rails, and VPS deploy path) that already runs. One stack definition serves two hosts: the local Mac for development parity and the `maghz` NixOS VPS as the durable home.

## [01]-[LAYOUT]

The codemap is a regenerable projection of the repository root.

```text codemap
Maghz/
├── admin/      maghz CLI modules and package charter
├── db/         declarative SQL, search dictionaries, and n8n bootstrap
├── image/      ParadeDB-derived Postgres image and apt projection
├── workflows/  committed n8n workflow files
├── docs/       doctrine, prose standards, and language stacks
└── .claude/    skills, hooks, scripts, and agent configuration
```

`admin/infra.py` `StackOp` owns the full service topology on both hosts: `MAGHZ_INFRA__STAGE` selects `local` (Colima) or `prd` (the VPS system daemon over the derived `ssh://` endpoint), and one Pulumi program serves both stacks.

## [02]-[HOW_IT_WORKS]

The `admin/` package is functional Railway-Oriented Programming over one closed `BoundaryFault` family. Every domain operation returns a `RuntimeRail[Envelope]`; the CLI lowers it to one stdout `Envelope` at the edge. `admin/runtime.py` is the substrate — the rail, the fault classifier, the bounded `drain` lane, retry policies, and structured receipts — and every consumer module composes it rather than re-deriving spawn, retry, or fault handling.

Two surfaces meet at the database and never collapse into each other. The CLI rails own deterministic, receipted truth: schema apply, ledger projections, Heptabase sync, cloud backup, and infrastructure lifecycle. The MCP fleet owns live exploration: an agent reaches the database, web research, and the VPS through MCP when it is investigating, not committing. PostgreSQL is deliberately dual-surface: schema and ledger mutation stay on the CLI rail, while the Forge fleet exposes a live read lens. Deterministic work goes through `maghz`; exploratory work goes through MCP; never the reverse. n8n remains container-plane only: workflows move by file export/import, status is the unauthenticated `/healthz` liveness plus the on-disk census, and no n8n API key or MCP row exists. API-managed workflow ownership requires an explicit credential and consumer admission.

Retrieval is hybrid and in-database: `pg_search` BM25 (lexical), `pgvector` HNSW cosine (semantic), and `pg_trgm`/FTS (fuzzy) fused through Reciprocal Rank Fusion in `maghz.search()`. Embeddings are produced in the database — `pg_net` posts each concept to local Ollama `nomic-embed-text` and the response writes back as `vector(768)` — on a two-step `pg_cron` sweep, with no application round-trip and no embedding API key.

## [03]-[CLI_SURFACE]

`maghz <command> [subcommand] [args]` (invoked as `uv run python -m admin …`). Each command discriminates on a closed verb and returns one typed `Envelope`; `maghz --help` is the live verb census.

| [INDEX] | [COMMAND]                | [DOES]                                                     |
| :-----: | :----------------------- | :--------------------------------------------------------- |
|  [01]   | `up` / `down` / `status` | Stage-selected Pulumi lifecycle for db, Ollama, and n8n    |
|  [02]   | `health`                 | Loopback service census; down services grade `failed`      |
|  [03]   | `schema apply`           | Stage dictionaries and idempotently apply the SQL surfaces |
|  [04]   | `schema doctor`          | Parse SQL and assert the live extension catalog            |
|  [05]   | `ledger <kind>`          | Read one ledger projection                                 |
|  [06]   | `sync`                   | Diff or generate Heptabase-backed concepts                 |
|  [07]   | `cloud`                  | Dump, bisync, or restore configured cloud remotes          |
|  [08]   | `n8n`                    | Export, import, or census committed workflows              |
|  [09]   | `exec`                   | Push, execute, and pull through the scoped SSH rail        |
|  [10]   | `automation run`         | Dispatch one typed trigger-action specification            |

## [04]-[MCP_BOUNDARY]

`Parametric_Forge/modules/home/programs/shell-tools/mcp-fleet.nix` is the sole MCP registration owner for Claude, Codex, and VS Code. This repository publishes no client configuration and exposes no MCP provisioning verb. The Forge manifest carries the Maghz-backed `postgres` lens through `forge-maghz-postgres-mcp` and the read-only `doppler-remote` lens through the VPS `maghz-mcp` container; `forge-mcp reconcile`, `doctor`, and `drift` own projection, health, and parity. MCP remains exploratory: schema, ledger, synchronization, and service lifecycle mutations enter through `maghz`.

## [05]-[HOSTS_AND_ACCESS]

The stack runs identically on two hosts, and the loopback port set is invariant across them — the same DSN and service URLs resolve on either end.

- Local Mac: Colima owns the Docker runtime; `maghz up` converges the stack; every service binds `127.0.0.1`.
- `maghz` VPS: the Forge flake's `nixosConfigurations.maghz` owns the operating system — static network, firewall (SSH only), system Docker daemon, declarative users. Services stay loopback on the VPS.
- Tunnel: the Forge `vpsTunnels` row projects the VPS services onto the local loopback through a health-gated launchd tunnel agent, so local agents and MCP servers reach the remote database at the same address as the local one. The tunnel agent and the local stack profile are mutually exclusive owners of those ports — run one, never both.

Three identities partition the VPS: `root` carries only the `forge-redeploy` activation rail, `bardiasamiee` is the operator user owning the Home Manager estate, and `maghz-agent` is the workload identity (docker group) owning the service plane and the agent workroot `/srv/maghz`, whose Doppler service token (`maghz/prd_host`, read-only, scoped to that directory) is its secret ingress. Stage-`prd` rails drive the VPS daemon from the operator machine over `ssh://maghz-agent@<host>` — the converge, the schema apply, and the health probes all ride the tunnel-invariant loopback ports. Host-level failures route to the Forge owner; stack-level failures route to the `admin/` rails.

## [06]-[BRING_UP]

1. The Docker runtime is running; the docker endpoint self-detects (`MAGHZ_INFRA__DOCKER_HOST` overrides).
2. Secrets are present in the process environment (Parametric_Forge injects them; see below).
3. `maghz up` drives Pulumi to build the custom image and start the Postgres, Ollama, and n8n services. The Ollama embed model is pulled as the converge's follow-on.
4. `maghz schema apply` then `maghz schema doctor` apply and assert the schema and extension census.
5. `maghz down` tears the whole stack down and leaves no orphaned containers, networks, or volumes.
6. Stage `prd` runs the same ladder against the VPS daemon: `doppler run --project maghz --config prd_host -- env MAGHZ_INFRA__STAGE=prd uv run maghz up`, then `schema apply` and `health` through the live tunnel. The tunnel must own the loopback ports first — stop the local stack before kickstarting it.

The connection string is `MAGHZ_DATABASE_DSN`, default `postgresql://maghz@127.0.0.1:15435/maghz` — passwordless trust auth on the loopback port, with `maghz` as the superuser, so agents and MCP servers auto-authenticate.

## [07]-[CONVENTIONS]

- [NO_MIGRATIONS]: Maghz never uses migration files, `NNN_*.sql` numbered scripts, version tables, or up/down pairs. The schema is declarative: `db/schema.sql`, `db/routines.sql`, and `db/cron.sql` are each idempotent (every statement `IF NOT EXISTS`, `CREATE OR REPLACE`, or DO-guarded). A schema change edits these files in place; `maghz schema apply` replays them and a replay is a clean no-op.
- [AGENT_ONLY]: there are no human-facing flags, prompts, or decorative output. The JSON `Envelope` on stdout is the result contract; structlog diagnostics ride stderr.
- [SINGLE_OWNER]: one canonical semantic name per bounded concept; arity, provider, and modality live in request shape, case, or policy row — never parallel command families.

## [08]-[PARAMETRIC_FORGE]

[Parametric_Forge](../Parametric_Forge) is the Nix owner of both hosts: the local Mac (nix-darwin) and the `maghz` VPS (`nixosConfigurations.maghz`), deployed through the one `forge-redeploy` rail. Maghz assumes the Forge toolchain on `PATH` and never imports it; when a toolchain, secret, host, or tunnel surface fails, fix the Forge owner, not `admin/`. `AGENTS.md [06]` carries the per-tool inventory.

Secret flow: Doppler is the sole backend — the canonical `.claude/hooks/setup-env.sh` resolves each Doppler source row live (encrypted snapshot on fetch failure, per-source verdicts) and writes the selected keys into each agent's environment; the `maghz` Doppler project's `prd_host` config owns the stack secrets, and 1Password holds only operator-personal items. Doppler topology — projects, configs, service tokens — mutates only through Forge `services/` Pulumi rows.

All owner paths below resolve from `Parametric_Forge`.

| [INDEX] | [CONCERN]            | [FORGE_OWNER]                                 |
| :-----: | :------------------- | :-------------------------------------------- |
|  [01]   | VPS operating system | `hosts/context.nix` and `modules/nixos/`      |
|  [02]   | SSH access + tunnels | `modules/home/programs/shell-tools/ssh.nix`   |
|  [03]   | Secret custody       | `services/topology.ts` and the session hook   |
|  [04]   | GitHub repo settings | `services/topology.ts`                        |
|  [05]   | Python toolchain     | `python-tools.nix` and `scientific-tools.nix` |
|  [06]   | Postgres clients     | `db-tools.nix`                                |
|  [07]   | Container runtime    | `container-tools/` and `containers.nix`       |
|  [08]   | Pulumi / Node / Git  | Language and git-tool modules                 |
