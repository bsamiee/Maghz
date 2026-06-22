# Authentication and Profile Management

Auth uses Chrome DevTools Protocol (CDP) cookie extraction.

---

## How auth works

`nlm login` connects to an installed Chromium-family browser via CDP, navigates to NotebookLM, and extracts Google session cookies. No API key, no Playwright, no headless browser install required — a standard desktop browser must already be installed. Cookies are stored locally and reused across `nlm` and `notebooklm-mcp` invocations. The CSRF token refreshes automatically on every request failure. Session cookies last approximately 2-4 weeks before a full re-login is required.

---

## Supported browsers

Chrome, Arc, Brave, Edge, Chromium, Vivaldi, Opera.

Set a preference explicitly:

```bash
nlm config set auth.browser chromium
```

---

## Auth commands

```bash
nlm login                                                        # Auto-mode: launches CDP, extracts cookies
nlm login --check                                                # Check current auth status without re-logging
nlm login --profile work                                         # Login under a named profile
nlm login --manual --file cookies.txt                            # Import cookies from a file (no browser required)
nlm login --provider openclaw --cdp-url http://127.0.0.1:18800   # External CDP endpoint
```

---

## Profile management

Named profiles support multiple Google accounts. Each profile stores its own cookie set.

```bash
nlm login --profile <name>             # Login and store credentials under <name>
nlm login switch <profile>             # Set <profile> as the active default
nlm login profile list                 # List all saved profiles
nlm login profile delete <name>        # Remove a profile
nlm login profile rename <old> <new>   # Rename a profile
```

When no `--profile` flag is passed, commands use the currently active default profile.

---

## MCP session auth

The `notebooklm-mcp` server reads the same local cookie store as `nlm`. Auth established via `nlm login` is immediately available to the MCP server without additional configuration. Each MCP server startup extracts a fresh per-session ID automatically.

---

## Troubleshooting auth

| Symptom | Action |
|---|---|
| Request returns 401 / auth error | Run `nlm login --check`; if expired, run `nlm login` |
| No browser detected | Install Chrome, Arc, Brave, Edge, Chromium, Vivaldi, or Opera |
| Need to use a remote/headless machine | Use `nlm login --manual --file cookies.txt` with cookies exported from a desktop session |
| Wrong Google account active | `nlm login profile list`, then `nlm login switch <correct-profile>` |
| Persistent failures after re-login | Run `nlm doctor` for full diagnostic output |
