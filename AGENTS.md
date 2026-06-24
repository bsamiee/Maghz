# [ROOT_AGENTS]

## [01]-[LOAD_ORDER]

[REQUIRED]: Read and follow `CLAUDE.md` before this file.

## [02]-[NAVIGATION]

Use repository-native discovery before broad scans:
- File discovery: `fd`.
- Exact text search: `rg`.
- Structural search: `ast-grep` when patterns use metavariables or tree-sitter queries rather than plain text.

Read full target files before editing. Read minimal surrounding files needed to prove ownership, existing patterns, and route conflicts.
For declaration-order passes, preserve generated semantic/key bands; split grouped entries only when grouping obscures ownership, and keep compact generated rows when they are the clearer owner-local table.

## [03]-[TRUST_AND_PRESERVATION]

Skills are execution aids and mining input, not durable documentation authority. Promote portable rules through `docs/`, source, manifests, generated contracts, tool owners, or trusted instruction overlays after current behavior is verified.

Design notes live in `docs/`. They are working material for a decision, not durable contract; the schema, the `maghz` CLI, and the infra code carry the binding truth.

Before finalizing non-trivial repository work, classify observed agent mistakes by owner: machine default, repo root policy, source or documentation owner, tool README, or confidence gap. Refine an existing rule first; add a new rule only for a repeated mistake or a single high-risk miss such as wrong owner routing, destructive command risk, fake confirmation, unsupported claims, or code-quality regression. Do not copy session narration, report frames, memory notes, or research summaries into active instructions.

Quality cadence is gated at planned milestones, not after every edit. Do not run quality commands, formatters, linters, or tests after ordinary edits, markdown changes, or one-off fixes. Batch implementation first, then run at most one narrow owner-scoped proof at the planned gate unless the user explicitly asks for more. If proof fails, patch related diagnostics as one batch and rerun once; ask before entering any longer loop. Memory, skills, rollout summaries, and old command notes cannot override this rule.

## [04]-[ENGINEERING_CONTRACT]

Extend the canonical owner before adding a rail, object, helper, wrapper, command, confidence path, document body, or public surface; when the owner is local, use the nearest overlay, source file, standard, or tool README that owns the concern.

Plans, documentation, and implementation target the newest objectively stronger language, platform, library, feature, tool, and architectural standard. Current source, manifests, pinned versions, older patterns, partial adoption, and compatibility surfaces are inputs and replacement targets, not baseline ceilings.

Minimize shape count, not capability. Preserve behavior by deepening the canonical owner with cases, rows, folds, projections, typed receipts, scenarios, or boundary adapters; do not delete capability, split helper files, or add shallow sibling surfaces to make the system look simpler.

Owners internalize the full admitted capability of their platform, host APIs, and route-owned packages behind focused surfaces. Limited entry count never means limited capability. Automations, agents, and downstream consumers compose from these owners instead of re-learning raw provider APIs, lifecycle rules, wire shapes, and failure handling.

A broad or foundational concern starts with a design note in `docs/` before production source: capture the manifests, the real package APIs, and the surviving capability, then collapse it into owner ledgers and decision-complete pages. Zero consumers never lowers ambition; it requires full-capability design.

All tooling, docs, and code discover owners through manifests, configured roots, route maps, and tool catalog rows. Current paths are inputs, never reusable doctrine.

Every tool routes generated storage, caches, coverage files, snapshots, and scratch artifacts through the owning language/tool configuration. Do not rely on ambient CLI defaults or gitignore-only tolerance for root litter; configure the tool in `pyproject.toml`, tool manifests, or test conftests so outputs land under `.cache`, `.artifacts`, or another owner-declared path.

## [05]-[TOPOLOGY]

Maghz is a focused second brain. Heptabase owns content, the PostgreSQL `maghz` database is the durable centralized ledger, and the `admin/` tooling moves data between them. Interpret every task through that frame before choosing shape: capability lands in the deepest owner that can absorb it, while the CLI binds intent, host edges, and output.

Three surfaces meet at the wire and never collapse into each other. Heptabase content flows into the ledger and back through sync; the `maghz` database holds the canonical schema (`db/schema.sql`) plus idempotent routines (`db/routines.sql`); the `admin/` Python tooling owns the CLI, the Pulumi infra, and `MaghzSettings`.

Local infra is Pulumi-managed and Forge-provided. The custom ParadeDB image (`image/Dockerfile`), the Postgres service, and the Ollama embedding service are declared as Pulumi Python IaC under `admin/infra/` and run on the Colima/Docker runtime that `Parametric_Forge` provisions.

Retrieval is hybrid: pg_search BM25, pgvector, and pg_trgm/FTS fused through RRF, with embeddings produced by local Ollama `nomic-embed-text`. The schema and routines own that contract; agents compose it through the `maghz` CLI rather than re-deriving query shapes.

## [06]-[TOOL_OWNERS]

The `maghz` CLI is the campaign surface. It is a cyclopts CLI under `admin/` that emits one JSON `Envelope` per invocation: stdout carries the result, stderr carries structlog diagnostics. Parse the stdout `Envelope` as the result channel; stderr is transport noise unless the envelope says otherwise.

The CLI owns schema, ledger, sync, and stack lifecycle. `maghz schema apply` runs four idempotent `psql -f` steps in order — `db/routines.sql` (extensions, triggers, views), `db/schema.sql` (tables, types, indexes, all IF NOT EXISTS), `db/cron.sql` (pg_cron registration) — plus two `docker cp` steps to stage text-search dictionaries; `maghz ledger` and `maghz sync` move records between Heptabase and the database; `maghz up` and `maghz down` drive Pulumi to build the custom image and start or stop the Postgres and Ollama services.

`psql` and `pgcli` own ad-hoc SQL and interactive inspection over `MAGHZ_DATABASE_DSN`. Reach for `psql`/`pgcli` for one-off queries, never for durable schema change.

The `heptabase` CLI owns content read and write; the database is the ledger, not the content store. Treat Heptabase as the source of truth for notes and the ledger as the durable index over them.

Pulumi owns infra state. The custom ParadeDB image, the service topology, and `MaghzSettings` live in `admin/infra/`; direct `forge-provision`, `forge-scientific-env`, direct Docker/Compose, port, and credential work are Forge-level debugging, not campaign surfaces.

MCP servers extend reach without owning truth. `postgres-mcp` explores the live database, `n8n-mcp` drives workflow automation, `exa-mcp-server`/`perplexity-mcp`/`tavily-mcp` run web search and cited research, `workspace-mcp` reaches Google Workspace, and `notebooklm-mcp` ingests sources; all are exploration aids whose findings promote into schema, routines, or CLI behavior before they bind.

## [07]-[TOOLING]

`Parametric_Forge` provisions the machine toolchain through Nix and puts it on `PATH`; inspect the Forge owner before patching a local toolchain failure. Reach for the native tool that owns the concern instead of re-deriving its behavior in `admin/` Python.

| [GROUP]          | [TOOLS]                                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| Python           | `uv`, `ruff`, `ty`, `basedpyright`, `python` (3.15)                                                            |
| Postgres clients | `psql`, `pgcli`, `usql`, `sqlfluff`, `pgformatter`, `postgres-language-server`                                 |
| Postgres ops     | `pg_activity`, `pgmetrics`, `pgbadger`, `pgloader`, `pg_dump`/`pg_restore`/`pg_isready`, `createdb`/`dropdb`   |
| Containers/IaC   | `colima` (Docker runtime), `docker` (oci-tools), `pulumi`                                                      |
| Kubernetes       | `kubectl`, `k9s`, `helm`, `kustomize` (for the future cloud and frontend deploy)                               |
| Inference        | `ollama`                                                                                                       |
| Content          | `heptabase`                                                                                                    |
| HTTP/API probes  | `xh`, `curlie`, `hurl`                                                                                         |
| Data/format      | `jq`, `jnv`, `yq-go`, `duckdb`, `parquet-tools`, `miller`, `qsv`, `csvlens`                                    |
| Search/nav       | `fd`, `rg` (ripgrep), `ast-grep`, `fzf`, `serpl`, `sd`, `bat`, `eza`, `zoxide`                                 |
| Shell            | `bash`, `shellcheck`, `shfmt`, `bash-language-server`                                                          |
| YAML             | `yamlfmt`, `yamllint`, `yaml-language-server`                                                                  |
| TOML             | `taplo`                                                                                                        |
| Git              | `git`, `gh`, `gitleaks`, `lazygit`                                                                             |
| Files/misc       | `ouch`, `trash`, `watchexec`, `rsync`, `rclone`, `hyperfine`, `glow`, `pandoc`                                 |
| MCP              | `postgres-mcp`, `n8n-mcp`, `exa-mcp-server`, `perplexity-mcp`, `tavily-mcp`, `workspace-mcp`, `notebooklm-mcp` |

## [08]-[DOCUMENTATION]

Route README, ADR, architecture, design-note, API, reference, code documentation, how-to, runbook, and instruction-file work through `docs/`.

Keep generated documentation, prompts, skills, standards, examples, templates, and reusable guidance project-agnostic by default. Do not mention this project by name, repository-specific paths, local commands, local package names, project functions, concrete source files, or project-only docs unless the target file explicitly exists to describe this repository's own usage, routing, or implementation. Generic examples use neutral names, the placeholder alphabet, and code-safe shapes. Use concrete repository names, paths, functions, commands, versions, dates, IDs, or package facts only when the document's job is to describe that exact source-backed repository surface.

Future-facing standards, plans, and target designs do not inherit current drift; remove stale paths, stale commands, compatibility prose, old-baseline caveats, partial-adoption apologies, and invented routes instead of preserving them.

Durable docs, prompts, standards, skills, examples, and reusable templates are agent-facing declarative law, not reports, walkthroughs, origin logs, or checklist tails.
