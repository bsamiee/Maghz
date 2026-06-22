# NotebookLM CLI — Full Command Reference

All commands accept `--help`. `nlm --ai` prints AI-assistant documentation. Pipe output to `jq` for structured parsing.

---

## notebook

```bash
nlm notebook list
nlm notebook create "<name>"
nlm notebook query <notebook>
nlm notebook share public <notebook>
nlm notebook share invite <notebook>
```

`notebook query` persists the answer to the NotebookLM web UI — it is not ephemeral.

---

## source

```bash
nlm source add <notebook> --url "https://..."
nlm source add <notebook> --file <path>
nlm source add <notebook> --drive <doc-id>
nlm source add <notebook> --text "inline content"
nlm source sync <notebook>
nlm source delete <notebook> <source-id>
```

`source sync` refreshes Google Drive-linked sources. `source delete` requires the source ID returned by `source add` or visible in `notebook list` output.

---

## studio

```bash
nlm studio create <notebook> --audio --confirm
nlm studio create <notebook> --video --confirm
nlm slides revise <notebook> <artifact-id>
```

`--confirm` is required for audio and video generation; it acknowledges that processing runs against the live Google service.

---

## download

```bash
nlm download audio <notebook> <artifact-id>
nlm download video <notebook> <artifact-id>
```

`artifact-id` is returned by `studio create`.

---

## batch

```bash
nlm batch query <notebook>
nlm batch create <notebook>
nlm batch delete <notebook>
```

---

## cross

```bash
nlm cross query <notebook1> <notebook2>
```

Runs a query across two notebooks simultaneously.

---

## pipeline

```bash
nlm pipeline run <name>
nlm pipeline list
```

---

## tag

```bash
nlm tag add <notebook> <tag-name>
nlm tag list <notebook>
nlm tag select <notebook> --tag <tag-name>
```

---

## research

```bash
nlm research start "topic"
```

---

## config

```bash
nlm config set auth.browser chromium
```

Sets the preferred browser for CDP-based auth. Valid values correspond to installed Chromium-family browsers.

---

## setup

```bash
nlm setup add claude-code
nlm setup add claude-desktop
nlm setup add gemini
nlm setup add github-copilot
nlm setup add cursor
nlm setup add cline
nlm setup add windsurf
nlm setup add antigravity
nlm setup add json
nlm setup list
nlm setup remove claude-code
```

`setup add json` outputs a raw JSON config block for manual integration.

---

## skill

```bash
nlm skill install cline
nlm skill install openclaw
nlm skill install codex
nlm skill install antigravity
nlm skill update
```

Installs or updates AI-agent skill definitions for external tools.

---

## doctor

```bash
nlm doctor
```

Runs a full diagnostic: auth state, browser detection, MCP registration status, and service connectivity.

---

## MCP tool catalog

The `notebooklm-mcp` stdio server registers 39 tools. Confirmed tool names include:

`notebook_list`, `notebook_create`, `source_add`, `notebook_query`, `studio_create`, `studio_revise`, `download_artifact`, `notebook_share_public`, `notebook_share_invite`, `source_sync_drive`, `batch`, `cross_notebook_query`, `pipeline`, `tag`, `research_start`

Run `nlm --ai` or inspect the MCP server manifest for the full enumerated list. Disable the MCP server when NotebookLM is not in active use.
