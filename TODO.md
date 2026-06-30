# TODO — deferred MCP-fleet finalization

Two items deferred from the MCP-fleet modernization. Each needs one human action an agent cannot perform (dashboard access / browser OAuth consent). The agent-executable steps and everything already learned are captured here so completion is fast and correct. Trigger an agent with the noted phrase once the prerequisite exists.

## 1. Context7 Pro — private sources + rules (dashboard)

Context7 Pro dashboard (high value, only you can): add Rasm/Maghz/Forge as private sources (Sources → Add → GitHub), set Global Rules. The MCP exposes only `resolve-library-id`/`query-docs` — it cannot manage the account; private-source add + policies are REST-automatable, but Rules are dashboard-only. Once your repos are indexed, `query-docs` serves your own internal APIs through the same rail.

Detail already verified:
- The live MCP endpoint exposes ONLY `resolve-library-id` + `query-docs` (empty prompts/resources capabilities) — no account, source, or rule tool exists.
- REST API IS automatable with the Pro key (`Authorization: Bearer ${CONTEXT7_API_KEY}`): `POST /api/v2/add/repo/{github|gitlab|bitbucket|...}`, `POST /api/v2/add/{openapi|website|confluence|llmstxt}`, `POST /api/v1/refresh`, `GET`/`PATCH /api/v2/policies`. Private-source add/refresh and teamspace policies can be scripted (the existing `context7-tools` REST client pattern could be extended into an admin verb if desired).
- NOT automatable: Global Rules + Library-Specific Rules are dashboard-only (no documented API).
- Per-repo control travels in a committed `context7.json` at each repo root: `folders`/`excludeFolders`/`excludeFiles` scope the parse; embedded `rules` (≤200 chars each) surface as recommendations whenever that library's docs are retrieved. Refresh re-parses and is charged only for changed content.
- Mechanism / payoff: once Rasm/Maghz/Forge are indexed, `resolve-library-id` returns their `/org/project` IDs and `query-docs` serves our own internal APIs/patterns through the identical rail agents already use for public libraries.

Action: dashboard → teamspace Sources → Add → GitHub → authorize → submit Rasm, Maghz, Forge; set Global Rules; optionally commit a `context7.json` per repo and/or script add+refresh via the REST API. Owner/Admin role required (Developer is read-only).

## 2. Google Workspace MCP first-use consent

State: `google-workspace` is registered at Claude user scope, Codex user scope, and Maghz project scope. Forge owns `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `WORKSPACE_MCP_CREDENTIALS_DIR`; Maghz commits only `${VAR}` placeholders.

Decision: use `workspace-mcp` as the single Google Workspace MCP server. It covers Gmail, Drive, Docs, Sheets, Slides, Calendar, Forms, Tasks, Chat, Apps Script, and Custom Search as tools under one server. Do not add service-specific `workspace` or `gcloud-*` MCP server rows.

Remaining human step: first-use OAuth consent. The first Workspace MCP call opens a browser. Sign in and grant scopes for `b.samiee93@gmail.com`, then repeat for `b.samiee@mzn-group.com` if both accounts should be available. Tokens persist under `WORKSPACE_MCP_CREDENTIALS_DIR`; later local Claude/Codex/Maghz sessions reuse the same cache.

Remote Maghz VPS: copy the locally populated `WORKSPACE_MCP_CREDENTIALS_DIR` contents to the VPS when remote agents need the same Workspace access. Set `workspace_oauth_redirect_uri` only for a Web OAuth client with a localhost callback; the current Desktop OAuth client does not need it.
