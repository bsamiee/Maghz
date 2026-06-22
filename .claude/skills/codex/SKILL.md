---
name: codex
user-invocable: true
description: >-
  Contextualizes the plugin-delivered OpenAI Codex slash commands (`/codex:review`, `/codex:adversarial-review`, `/codex:rescue`, `/codex:status`, `/codex:result`, `/codex:cancel`, `/codex:setup`) for Maghz research and refine actions. Use when an agent wants a second-model code review, adversarial critique, or a long-running Codex rescue task from inside Claude Code.
---

# [H1][CODEX]

Run OpenAI Codex from inside Claude Code through the `codex-plugin-cc` plugin. The plugin delivers its own slash commands and `hooks.json`; Maghz vendors no Python shim and no copy of those files. This guide contextualizes the slash commands for Maghz use.

[IMPORTANT] These are plugin-delivered slash commands, not a Maghz shim. They resolve only after the plugin is installed and the local Codex CLI is authenticated. The plugin drives the global `codex` binary (`npm install -g @openai/codex`, Node.js 18.18+) and reuses its authentication. Two auth paths satisfy it: a one-time interactive `!codex login` (a ChatGPT account, including Free), whose token lives in the Codex CLI's own config; or a stateless `OPENAI_API_KEY` in the session environment. `OPENAI_API_KEY` is the secrets-bootstrap contract — `setup-env.sh` carries it in `_ENV_KEYS` and emits it at session start, so when the key is stored the slash commands authenticate with no interactive login. This skill declares the requirement; secrets-bootstrap owns storage and emission.

## [01]-[INSTALL]

```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

`/codex:setup` is the readiness gate: it reports whether the `codex` binary is present and signed in, offers to install it when npm is available, and toggles the optional pre-commit review gate (`--enable-review-gate` / `--disable-review-gate`). Run it before the first review; rerun it after `!codex login` if a command reports Codex unavailable. Usage counts toward Codex limits.

## [02]-[COMMANDS]

| [COMMAND]                   | [PURPOSE]                                                           |
| --------------------------- | ------------------------------------------------------------------- |
| `/codex:review`             | Second-model read-only review of the current diff or named scope    |
| `/codex:adversarial-review` | Steerable hostile redteam pass — find what the first model missed   |
| `/codex:rescue`             | Delegate a stuck refactor/debug task to a long background Codex run |
| `/codex:status`             | State of an in-flight Codex task                                    |
| `/codex:result`             | Completed output of a Codex task                                    |
| `/codex:cancel`             | Cancel a running Codex task                                         |
| `/codex:setup`              | Codex readiness check, optional install, review-gate toggle         |

`review`/`adversarial-review` are synchronous review passes; `rescue`/`status`/`result`/`cancel` are the asynchronous background-job lifecycle, mirroring the `agy task` create/status/result/cancel shape so an agent reasons about both delegated-task families the same way.

## [03]-[MAGHZ_USE]

Compose `/codex:review` and `/codex:adversarial-review` into the research/refine loop as the second-model adversary alongside `agy` (Gemini) reasoning — never as a replacement for the route-owned quality gate. The two adversaries are complementary: `agy` carries Gemini Pro/Flash reasoning over a prompt payload, Codex carries an independent model over the actual diff. `/codex:rescue` delegates a stuck refactor to a long autonomous run and the `status`/`result`/`cancel` family covers its lifecycle, the same task vocabulary as `agy task`.
