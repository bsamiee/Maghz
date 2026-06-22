---
name: notebooklm
description: Drive Google NotebookLM programmatically via the unified CLI (`nlm`) and MCP server (`notebooklm-mcp`). Manages notebooks, sources, studio artifacts (audio/video/slides), cross-notebook queries, batch operations, pipelines, tags, and research — all backed by cookie-auth against the live NotebookLM service.
allowed-tools: Bash(nlm *) Bash(jq *) mcp__notebooklm__*
metadata:
  notebooklm-mcp-cli-version-range: "0.7.x"
---

## Prerequisites

- Package installed system-wide: `uv tool install notebooklm-mcp-cli`. Entry points on PATH: `nlm` (CLI) and `notebooklm-mcp` (stdio MCP server).
- One-time auth: `nlm login` — requires a Chromium-family desktop browser (Chrome, Arc, Brave, Edge, Chromium, Vivaldi, Opera) installed on the machine. The command connects via Chrome DevTools Protocol to extract Google session cookies. No API key, no Playwright.
- MCP registration: `nlm setup add claude-code` writes the client config automatically.
- Check version compatibility before use: `nlm --version`. When the installed version is outside `0.7.x`, stop and ask the user to run `uv tool upgrade notebooklm-mcp-cli`.

## Command discovery

`nlm --help` and `nlm <group> --help` are always authoritative. The `nlm --ai` flag prints AI-assistant-oriented documentation.

```bash
nlm --help
nlm notebook --help
nlm source --help
nlm studio --help
```

## Common recipes

For less common flags or if a command fails, run `nlm <group> --help` to discover the correct syntax. Pipe any command with `| jq` when structured data is needed.

- **List notebooks:** `nlm notebook list`
- **Create a notebook:** `nlm notebook create "Project Name"`
- **Query a notebook:** `nlm notebook query <notebook>` (answer persists to the web UI)
- **Cross-notebook query:** `nlm cross query <notebook1> <notebook2>`
- **Add a URL source:** `nlm source add <notebook> --url "https://..."`
- **Add a file source:** `nlm source add <notebook> --file <path>`
- **Add a Google Drive source:** `nlm source add <notebook> --drive <doc-id>`
- **Add inline text as a source:** `nlm source add <notebook> --text "content"`
- **Sync Drive sources:** `nlm source sync <notebook>`
- **Delete a source:** `nlm source delete <notebook> <source-id>`
- **Generate audio overview (podcast):** `nlm studio create <notebook> --audio --confirm`
- **Generate video:** `nlm studio create <notebook> --video --confirm`
- **Revise a slide deck:** `nlm slides revise <notebook> <artifact-id>`
- **Download audio artifact:** `nlm download audio <notebook> <artifact-id>`
- **Download video artifact:** `nlm download video <notebook> <artifact-id>`
- **Batch query:** `nlm batch query <notebook>`
- **Batch create:** `nlm batch create <notebook>`
- **Batch delete:** `nlm batch delete <notebook>`
- **Run a pipeline:** `nlm pipeline run <name>`
- **List pipelines:** `nlm pipeline list`
- **Add a tag:** `nlm tag add <notebook> <tag-name>`
- **List tags:** `nlm tag list <notebook>`
- **Select by tag:** `nlm tag select <notebook> --tag <tag-name>`
- **Start web research:** `nlm research start "topic"`
- **Share notebook (public link):** `nlm notebook share public <notebook>`
- **Share notebook (invite):** `nlm notebook share invite <notebook>`
- **Check auth status:** `nlm login --check`
- **Diagnose issues:** `nlm doctor`

Full command reference with all flags is in `references/command-reference.md`. Auth and profile management details are in `references/auth-profiles.md`.

## MCP server

`notebooklm-mcp` is a stdio MCP server exposing the same operations as named `mcp__notebooklm__*` tools (39 tools total). It suits interactive agent sessions where the client drives tool calls directly. The CLI (`nlm`) is the surface for scripted, batch, and pipeline flows. Both share the same auth cookie store and profiles.

This project registers the server in `.mcp.json` (project scope). `nlm setup add claude-code` writes a user-scoped registration instead; verify either with `nlm setup list`. The server registers 39 tools, so disable it when NotebookLM is not in use.

## Troubleshooting

- **Auth expired.** Cookies last approximately 2-4 weeks. Re-run `nlm login` when requests fail with auth errors. The CSRF token auto-refreshes on every failure; a full re-login is only needed when the session itself expires.
- **No Chromium browser installed.** `nlm login` requires Chrome, Arc, Brave, Edge, Chromium, Vivaldi, or Opera on the machine. Install one before attempting auth. Manual fallback: `nlm login --manual --file cookies.txt`.
- **Wrong profile active.** Use `nlm login profile list` to inspect profiles and `nlm login switch <profile>` to change the default.
- **`nlm doctor` output.** Run `nlm doctor` for a full diagnostic of auth state, browser detection, MCP registration, and connectivity.
- **Command not found.** Confirm the package is installed system-wide with `uv tool install notebooklm-mcp-cli`; the `nlm` binary must be on PATH, not inside a project venv.

## Warnings

- **Use `nlm` and `notebooklm-mcp` as the only access paths.** Never call the NotebookLM web API directly, scrape HTML, or interact with the service outside these entry points.
- **`notebooklm-cli` and `notebooklm-mcp-server` are legacy packages.** They must be uninstalled before using `notebooklm-mcp-cli`. If both are present, remove the legacy ones first: `pip uninstall notebooklm-cli notebooklm-mcp-server`.
- **`notebook query` output persists to the web UI.** Queries run via `nlm notebook query` are not ephemeral — they appear in the NotebookLM web interface.
- **Studio generation is slow and irreversible.** Always pass `--confirm` intentionally; audio/video generation triggers real processing against the Google service and cannot be cancelled mid-run.
