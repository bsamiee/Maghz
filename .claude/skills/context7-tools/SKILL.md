---
name: context7-tools
user-invocable: false
description: >-
  Queries version-specific library documentation from Context7. Use when fetching API references, code examples,
  or conceptual guides for npm/PyPI packages. Resolves library IDs, retrieves docs by topic. Not for web search.
---

# [H1][CONTEXT7-TOOLS]

Query Context7 library documentation. Matches MCP tool structure (resolve-library-id, query-docs).

[IMPORTANT] Context7 pulls up-to-date, version-specific documentation from source. Supports private documents (early access). Community-driven library coverage.

## [01]-[COMMANDS]

| [CMD]   | [ARGS]                 | [RETURNS]                       |
| ------- | ---------------------- | ------------------------------- |
| resolve | `<library> [query]`    | Top 5 matching IDs with scores  |
| docs    | `<library-id> <query>` | Documentation filtered by query |
| lookup  | `<library> <query>`    | Resolve + docs in one call      |

## [02]-[USAGE]

```bash
# Resolve library -> see options
uv run $CLAUDE_HOME/skills/context7-tools/scripts/context7.py resolve effect

# Resolve with query filter
uv run $CLAUDE_HOME/skills/context7-tools/scripts/context7.py resolve react "server components"

# Fetch docs for specific ID
uv run $CLAUDE_HOME/skills/context7-tools/scripts/context7.py docs /effect-ts/effect "Services"

# Unified: resolve + docs
uv run $CLAUDE_HOME/skills/context7-tools/scripts/context7.py lookup react "hooks"

# Unified: with version-specific query
uv run $CLAUDE_HOME/skills/context7-tools/scripts/context7.py lookup vite "v7 migration guide"
```

## [03]-[ARGUMENTS]

**resolve**: `<library> [query]`
- `library` — Library name to search (required, e.g., `effect`, `react`, `vite`)
- `query` — Optional query to narrow results

**docs**: `<library-id> <query>`
- `library-id` — Context7 library ID (required, e.g., `/effect-ts/effect`)
- `query` — Documentation topic to retrieve (required)

**lookup**: `<library> <query>`
- `library` — Library name (required)
- `query` — Topic to fetch docs for (required)

## [04]-[SELECTION_LOGIC]

`lookup` auto-selects library by: VIP status -> highest benchmark score.

Use `resolve` first when disambiguation needed (e.g., multiple React packages).

## [05]-[OUTPUT]

Commands return JSON or plain text.

| [INDEX] | [CMD]     | [RESPONSE]                                            |
| :-----: | --------- | ----------------------------------------------------- |
|  [01]   | `resolve` | JSON array: `[{id, title, score, vip}]`               |
|  [02]   | `docs`    | Plain text documentation prefixed with `[library-id]` |
|  [03]   | `lookup`  | Plain text documentation (same as docs)               |

## [06]-[ENVIRONMENT]

| [VAR]              | [REQUIRED] | [DESCRIPTION]                  |
| ------------------ | ---------- | ------------------------------ |
| `CONTEXT7_API_KEY` | No         | Optional bearer token for auth |

## [07]-[ERROR_HANDLING]

- HTTP errors print `[ERROR] <status>: <body>` and exit 1
- Connection errors print `[ERROR] <message>` and exit 1
- No library found: `[ERROR] No library found for '<query>'` and exit 1
