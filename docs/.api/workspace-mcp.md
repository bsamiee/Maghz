# [API][WORKSPACE-MCP]

Capability catalog for the Google Workspace MCP server consumed via the Forge-owned `forge-workspace-mcp` wrapper. The server is a row in the mcp blueprint's `_SERVER_TABLE` (`ServerKind.GOOGLE_WORKSPACE`, emitted as `google-workspace`), not a `libs/python` import. This catalog is the authoritative contract the mcp Google Workspace row and `IntegrationsConfig` absorb: Forge owns the workspace credentials dir and OAuth credentials, Maghz owns only the optional OAuth redirect URI, mcp owns the generated row, and `McpServerSettings` carries no workspace fields. The env keys `_render` emits are the server's real variable names — `WORKSPACE_MCP_CREDENTIALS_DIR` (the credentials directory; alias `GOOGLE_MCP_CREDENTIALS_DIR`) and `GOOGLE_OAUTH_REDIRECT_URI` (the redirect override) — not `TOKEN_DIR`/`OAUTH_REDIRECT_URI`, which the server does not read.

## [01]-[SERVICE_GROUPS]

Twelve service groups, gated by `--tool-tier`:

| [SERVICE]    | core | extended | complete |
| ------------ | :--: | :------: | :------: |
| Gmail        | yes  |   yes    |   yes    |
| Drive        | yes  |   yes    |   yes    |
| Calendar     | yes  |   yes    |   yes    |
| Tasks        | yes  |   yes    |   yes    |
| Docs         |  —   |   yes    |   yes    |
| Sheets       |  —   |   yes    |   yes    |
| Slides       |  —   |   yes    |   yes    |
| Contacts     |  —   |   yes    |   yes    |
| Forms        |  —   |   yes    |   yes    |
| Search       |  —   |   yes    |   yes    |
| Chat         |  —   |   yes    |   yes    |
| Apps Script  |  —   |    —     |   yes    |

`core` is Gmail/Drive/Calendar/Tasks only. `extended` adds the document and collaboration surfaces and is the canonical default for research/refine automation. `complete` adds Apps Script.

## [02]-[INVOCATION]

```
command:  uvx
args:     ["workspace-mcp", "--tool-tier", "extended"]
```

The mcp `google-workspace` row carries exactly this `args` list. OAuth 2.0 over stdio is the default transport; OAuth 2.1 multi-user (`MCP_ENABLE_OAUTH21=true` + `--transport streamable-http`) is out of scope for the single-user local + VPS pattern.

## [03]-[ENV_CONTRACT]

| [KEY]                   | [REQUIRED]        | [SOURCE]                                                        |
| ----------------------- | ----------------- | -------------------------------------------------------------- |
| `GOOGLE_OAUTH_CLIENT_ID`     | yes          | bare key folded by `_BareEnvSource` into `IntegrationsConfig.google_oauth_client_id` (`SecretStr \| None`); emitted as a bare `${GOOGLE_OAUTH_CLIENT_ID}` placeholder, never resolved into `.mcp.json` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | yes          | bare key folded by `_BareEnvSource` into `IntegrationsConfig.google_oauth_client_secret` (`SecretStr \| None`); emitted as a bare `${GOOGLE_OAUTH_CLIENT_SECRET}` placeholder |
| `WORKSPACE_MCP_CREDENTIALS_DIR` | yes       | Machine-level env var owned by Forge; `_render` commits `${WORKSPACE_MCP_CREDENTIALS_DIR}` so Claude, Codex, and Maghz share one token cache. This is the server's canonical credentials-dir key (alias `GOOGLE_MCP_CREDENTIALS_DIR`); the server default when unset is `~/.google_workspace_mcp/credentials` |
| `GOOGLE_OAUTH_REDIRECT_URI`  | headless only | `IntegrationsConfig.workspace_oauth_redirect_uri` (`str \| None`); `_render` emits it only when `cfg.integrations.workspace_oauth_redirect_uri` is non-None (the redirect override the server reads via `os.getenv("GOOGLE_OAUTH_REDIRECT_URI")`) |

`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `WORKSPACE_MCP_CREDENTIALS_DIR` are bare env keys in the `google-workspace` row — NOT `MAGHZ_MCP__`-prefixed. In the committed `.mcp.json` they render as bare `${GOOGLE_OAUTH_*}` and `${WORKSPACE_MCP_CREDENTIALS_DIR}` placeholders. The mcp `_validate` coverage check matches only `${MAGHZ_MCP__<KEY>}` via `_PLACEHOLDER`, so these bare placeholders never match and are exempt by construction. `GOOGLE_OAUTH_REDIRECT_URI` is emitted only when the settings field is present.

## [04]-[OAUTH_FLOW]

stdio OAuth 2.0 is the local default. First consent triggers a browser flow; the token persists in the `WORKSPACE_MCP_CREDENTIALS_DIR` directory (gitignored via the `.cache/` rule) across sessions. On a headless VPS set `GOOGLE_OAUTH_REDIRECT_URI` (via `MAGHZ_INTEGRATIONS__WORKSPACE_OAUTH_REDIRECT_URI`) to the deployment's reverse-proxy callback URL so the consent redirect resolves: complete the flow in a browser against that callback. The VPS token file is never committed.
