# [ROOT_AGENTS]

[REQUIRED]: Read and follow `CLAUDE.md` before this file.

## [01]-[NAVIGATION]

Read full target files before editing. Read minimal surrounding files needed to prove ownership, existing patterns, and route conflicts.
For declaration-order passes, preserve generated semantic/key bands; split grouped entries only when grouping obscures ownership, and keep compact generated rows when they are the clearer owner-local table.

## [02]-[TRUST_AND_PRESERVATION]

Skills are execution aids and mining input, not durable documentation authority. Promote portable rules through `docs/`, source, manifests, generated contracts, tool owners, or trusted instruction overlays after current behavior is verified.

Design notes live in `docs/`. They are working material for a decision, not durable contract; the schema, the `maghz` CLI, and the infra code carry the binding truth.

Before finalizing non-trivial repository work, classify observed agent mistakes by owner: machine default, repo root policy, source or documentation owner, tool README, or confidence gap. Refine an existing rule first; add a new rule only for a repeated mistake or a single high-risk miss such as wrong owner routing, destructive command risk, fake confirmation, unsupported claims, or code-quality regression. Do not copy session narration, report frames, memory notes, or research summaries into active instructions.

Quality cadence is gated at planned milestones, not after every edit; run at most one narrow owner-scoped proof at the planned gate.

## [03]-[ENGINEERING_CONTRACT]

Owners internalize the full admitted capability of their platform, host APIs, and route-owned packages behind focused surfaces. Limited entry count never means limited capability. Automations, agents, and downstream consumers compose from these owners instead of re-learning raw provider APIs, lifecycle rules, wire shapes, and failure handling.

A broad or foundational concern starts with a design note in `docs/` before production source: capture the manifests, the real package APIs, and the surviving capability, then collapse it into owner ledgers and decision-complete pages. Zero consumers never lowers ambition; it requires full-capability design.

All tooling, docs, and code discover owners through manifests, configured roots, route maps, and tool catalog rows. Current paths are inputs, never reusable doctrine.

Every tool routes generated storage, caches, coverage files, snapshots, and scratch artifacts through the owning language/tool configuration. Do not rely on ambient CLI defaults or gitignore-only tolerance for root litter; configure the tool in `pyproject.toml`, tool manifests, or test conftests so outputs land under `.cache`, `.artifacts`, or another owner-declared path.

## [04]-[TOPOLOGY]

Maghz is a focused second brain. Heptabase owns content, the PostgreSQL `maghz` database is the durable centralized ledger, and the `admin/` tooling moves data between them. Interpret every task through that frame before choosing shape: capability lands in the deepest owner that can absorb it, while the CLI binds intent, host edges, and output.

Three surfaces meet at the wire and never collapse into each other. Heptabase content flows into the ledger and back through sync; the `maghz` database holds the canonical schema (`db/schema.sql`) plus idempotent routines (`db/routines.sql`); the `admin/` Python tooling owns the CLI, the Pulumi infra, and `MaghzSettings`.

Infra is Pulumi-managed and Forge-provided, and one stack definition serves two hosts. The custom ParadeDB image (`image/Dockerfile`) and the `db`/`ollama`/`n8n` services are declared as Pulumi Python IaC in `admin/infra.py`; locally they run on the Colima/Docker runtime that `Parametric_Forge` provisions, and on the `maghz` NixOS VPS they run on the system Docker daemon that the Forge flake's `nixosConfigurations.maghz` declares. Services bind loopback on both hosts with an invariant port set; the Forge `vpsTunnels` launchd agent projects the VPS services onto the local loopback, and that tunnel and the local stack are mutually exclusive owners of the ports. Port invariance cuts both ways: with the tunnel live, the same loopback DSN reaches the production VPS database — prove which owner holds the ports before any mutating rail. `StackOp` owns the full topology on both hosts: `MAGHZ_INFRA__STAGE` discriminates the daemon endpoint, and there is no parallel manifest. Apple Container is not the Maghz runtime until its Docker Engine API, `docker cp`, BuildKit cache, network-alias, healthcheck, and named-volume contracts have a proved equivalent owner — the service plane depends on every one of them, so Colima locally and the system Docker daemon on the VPS stay the sole runtime here.

Three identities partition the VPS, and each carries exactly one concern: `root` carries only the key-based `forge-redeploy` activation rail; `bardiasamiee` is the operator user owning the Home Manager estate and the interactive `ssh maghz` session; `maghz-agent` is the workload identity (docker group, no wheel) owning the service plane and the agent workroot `/srv/maghz`, with a directory-scoped read-only Doppler token (`maghz/prd_host`) as its secret ingress. Stage-`prd` rails operate as `maghz-agent` from the operator machine: the converge drives the VPS daemon over `ssh://maghz-agent@<host>`, the schema apply and health probes ride the tunnel loopback, and `maghz exec` pushes the working tree over SFTP, runs one command in the workroot, and stamps every receipt with the pushed commit. Host identity, network, firewall, and tunnel changes route to the Forge owner; nothing in this repo mutates the host.

Retrieval is hybrid: pg_search BM25, pgvector, and pg_trgm/FTS fused through RRF, with embeddings produced by local Ollama `nomic-embed-text`. The schema and routines own that contract; agents compose it through the `maghz` CLI rather than re-deriving query shapes.

## [05]-[TOOL_OWNERS]

The `maghz` CLI is the campaign surface. It is a cyclopts CLI under `admin/` that emits one JSON `Envelope` per invocation: stdout carries the result, stderr carries structlog diagnostics. Parse the stdout `Envelope` as the result channel; stderr is transport noise unless the envelope says otherwise.

The CLI owns schema, ledger, sync, and stack lifecycle. `maghz schema apply` is idempotent and runs in dependency order — first two `docker cp` steps staging the `db/search/` text-search dictionaries into the container `tsearch_data` dir, then `psql -v ON_ERROR_STOP=1 -f` over `db/schema.sql` (the `CREATE EXTENSION` census, `CREATE SCHEMA maghz`, the `kb_english` text-search configuration, enum types, tables, and plain indexes, all IF NOT EXISTS), `db/routines.sql` (function, trigger, exotic-index, view, and IMMV bodies), then `db/cron.sql` (pg_cron registration); `maghz ledger` and `maghz sync` move records between Heptabase and the database; `maghz up` and `maghz down` drive Pulumi to build the custom image and start or stop the Postgres, Ollama, and n8n services.

`psql` and `pgcli` own ad-hoc SQL and interactive inspection over `MAGHZ_DATABASE_DSN`. Reach for `psql`/`pgcli` for one-off queries, never for durable schema change.

The `heptabase` CLI owns content read and write; the database is the ledger, not the content store. Treat Heptabase as the source of truth for notes and the ledger as the durable index over them.

Pulumi owns infra state. The custom ParadeDB image and the service topology live in `admin/infra.py`, fed by the one `MaghzSettings` owner in `admin/settings.py`; direct `forge-provision`, `forge-scientific-env`, direct Docker/Compose, port, and credential work are Forge-level debugging, not campaign surfaces.

MCP servers extend reach without owning truth. The 12-server fleet is owned by `admin/mcp.py`, which generates the committed Claude `.mcp.json` (`~/.codex/config.toml` is the sole Codex configuration home; the rail's residual Codex projection retires with the next fleet pass): `postgres` explores the live database, `google-workspace` reaches Google Workspace, `notebooklm` ingests sources, `exa`/`perplexity`/`tavily` run web search and cited research, `hostinger` manages the VPS, the HTTP remotes `github` (repository API), `context7` (live library docs), and `greptile` (whole-repo semantic code review) extend reach, the host-process `nuget` server surfaces NuGet package intelligence (latest version, vulnerability/deprecation, safe-upgrade sets, supply-chain review) wherever the .NET 10 SDK and `nuget-mcp` launcher exist, and the host-process `jupyter` server routes through the Forge-owned `forge-jupyter-mcp` launcher. Resolve any external library's current API through `context7` before its findings bind; the full web/docs tool-selection and chaining law is the user-global doctrine. All are exploration aids whose findings promote into schema, routines, or CLI behavior before they bind: deterministic work — schema apply, ledger mutations, stack lifecycle — always routes through the `maghz` CLI, never an MCP.

Remote Workspace automation uses `gws` with `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/home/maghz-agent/.config/gws/credentials.json`; the `google-workspace` MCP remains the interactive MCP surface, while `gws` owns batch/headless Workspace scripts.

Maghz remote may bootstrap the `agy` binary for parity, but Antigravity auth remains local-first until an official portable/headless credential flow is verified. Do not copy opaque `~/.gemini` auth state to the VPS by default.

## [06]-[TOOLING]

`Parametric_Forge` provisions the machine toolchain through Nix and puts it on `PATH`; inspect the Forge owner before patching a local toolchain failure. Reach for the native tool that owns the concern instead of re-deriving its behavior in `admin/` Python. `fmt [--check] [target...]` is the universal formatter front door — every file type routes to its owning formatter, and project law (pyproject.toml, [tool.sqlfluff], .editorconfig) always outranks the machine defaults.

| [INDEX] | [GROUP]          | [TOOLS]                                                                                                                                        |
| :-----: | :--------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
|  [01]   | Python           | `uv`, `ruff`, `ty`, `python` (3.15)                                                                                                            |
|  [02]   | Postgres clients | `psql`, `pgcli`, `usql`, `sqlfluff`, `pgformatter`, `postgres-language-server`                                                                 |
|  [03]   | Postgres ops     | `pg_activity`, `pgmetrics`, `pgbadger`, `pgloader`, `pg_dump`/`pg_restore`/`pg_isready`, `createdb`/`dropdb`                                   |
|  [04]   | Containers/IaC   | `colima` (Docker runtime), `docker` (oci-tools), `pulumi`, `container` (Forge-approved OCI experiments only)                                                                                      |
|  [05]   | Kubernetes       | `kubectl`, `k9s`, `helm`, `kustomize` (for the future cloud and frontend deploy)                                                               |
|  [06]   | Inference        | `ollama`                                                                                                                                       |
|  [07]   | Content          | `heptabase`                                                                                                                                    |
|  [08]   | HTTP/API probes  | `xh`, `curlie`, `hurl`                                                                                                                         |
|  [09]   | Data/format      | `jq`, `jnv`, `yq-go`, `duckdb`, `parquet-tools`, `miller`, `qsv`, `csvlens`                                                                    |
|  [10]   | Search/nav       | `fd`, `rg` (ripgrep), `ast-grep`, `fzf`, `serpl`, `sd`, `bat`, `eza`, `zoxide`                                                                 |
|  [11]   | Shell            | `bash`, `shellcheck`, `shfmt`, `bash-language-server`                                                                                          |
|  [12]   | YAML             | `yamlfmt`, `yamllint`, `yaml-language-server`                                                                                                  |
|  [13]   | TOML             | `taplo`                                                                                                                                        |
|  [14]   | Git              | `git`, `gh`, `gitleaks`, `lazygit`                                                                                                             |
|  [15]   | Files/misc       | `ouch`, `trash`, `watchexec`, `rsync`, `rclone`, `hyperfine`, `glow`, `pandoc`                                                                 |
|  [16]   | MCP              | `postgres`, `google-workspace`, `notebooklm`, `exa`, `perplexity`, `tavily`, `hostinger`, `github`, `context7`, `greptile`, `nuget`, `jupyter` |

## [07]-[DOCUMENTATION]

Route README, ADR, architecture, design-note, API, reference, code documentation, how-to, runbook, and instruction-file work through `docs/`.

Keep generated documentation, prompts, skills, standards, examples, templates, and reusable guidance project-agnostic by default. Do not mention this project by name, repository-specific paths, local commands, local package names, project functions, concrete source files, or project-only docs unless the target file explicitly exists to describe this repository's own usage, routing, or implementation. Generic examples use neutral names, the placeholder alphabet, and code-safe shapes. Use concrete repository names, paths, functions, commands, versions, dates, IDs, or package facts only when the document's job is to describe that exact source-backed repository surface.

Future-facing standards, plans, and target designs do not inherit current drift; remove stale paths, stale commands, compatibility prose, old-baseline caveats, partial-adoption apologies, and invented routes instead of preserving them.

Durable docs, prompts, standards, skills, examples, and reusable templates are agent-facing declarative law, not reports, walkthroughs, origin logs, or checklist tails.
