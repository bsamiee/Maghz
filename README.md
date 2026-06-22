# Maghz

A focused second brain. Heptabase owns content, the PostgreSQL 18.4 `maghz` database is the durable centralized ledger, and AI agents plus automations drive the work.

## Layout

| [PATH]     | [OWNS]                                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `admin/`   | The `maghz` cyclopts CLI (JSON-envelope output) and the Pulumi infra in `admin/infra/`, driven by `MaghzSettings`. |
| `db/`      | The Atlas declarative `schema.sql` and idempotent `routines.sql`. No numbered migrations.                          |
| `image/`   | The custom ParadeDB-plus-extensions Postgres image (`Dockerfile`).                                                 |
| `.claude/` | Agent configuration, skills, and workflows.                                                                        |

## Tooling

Machine tooling is provisioned by [Parametric_Forge](../Parametric_Forge) (Nix, on `PATH`). `AGENTS.md` carries the full per-tool inventory.

- Python: `uv`, `ruff`, `ty`, `basedpyright`, `python` 3.15.
- Postgres/SQL: `psql`, `pgcli`, `usql`, `atlas`, `sqlfluff`, postgres-language-server, plus the dump/restore and operations suite.
- Content: `heptabase`.
- Inference: `ollama` serving local `nomic-embed-text`.
- Infra: `pulumi`, `colima` Docker runtime, `docker`.
- Data and search: `jq`, `yq-go`, `duckdb`, `fd`, `rg`, `ast-grep`.
- Git: `git`, `gh`, `gitleaks`, `lazygit`.
- MCP: `postgres-mcp`, `notebooklm-mcp`.
- CLI: `maghz`.

## Connect

The connection string is `MAGHZ_DATABASE_DSN`, default `postgresql://maghz@127.0.0.1:15435/maghz`. Embeddings run against local Ollama `nomic-embed-text` with no API key. Retrieval is hybrid pg_search BM25, pgvector, and pg_trgm/FTS fused through RRF.

## Bring-up

- `maghz up` drives Pulumi to build the custom image and start the Postgres and Ollama services.
- `maghz schema apply` runs Atlas against `db/schema.sql` and applies `db/routines.sql`.
- `maghz ledger ...` and `maghz sync ...` move records between Heptabase and the database.
