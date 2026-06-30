---
name: agy
user-invocable: true
description: >-
  Drives the Antigravity (`agy`) CLI for Gemini 3 reasoning: synchronous prompts (review, research, summarization, adversarial critique) and the asynchronous background-task lifecycle. Use when an agent needs Gemini Pro/Flash/Nano reasoning or wants to delegate a long autonomous job to `agy task`.
---

# [H1][AGY]

Invoke the `agy` Antigravity CLI through one modal Python shim that maps the binary outcome to a typed `AgyReceipt`/`AgyFail` JSON egress on stdout.

[IMPORTANT] Invoke the shim by path under `uv run` from the project root (`uv run $CLAUDE_HOME/skills/agy/scripts/agy.py <op> ...`) so the root is on `sys.path` and the shim's `from admin.settings import settings` import resolves; the shim then reads `settings().integrations.agy_binary` (the binary path) and `settings().integrations.agy_process_timeout_s` (the `move_on_after` budget) at call time. OAuth is authoritative: `agy auth login` (`--no-browser` on a headless VPS) must complete once before any op succeeds.

## [01]-[OPS]

| [OP]   | [agy_SURFACE]           | [SYNC] | [RECEIPT_FIELD]        |
| ------ | ----------------------- | ------ | ---------------------- |
| prompt | `agy -p "<text>"`       | yes    | `output: Some(text)`   |
| task   | `agy task create "<…>"` | no     | `task_id: Some(id)`    |
| status | `agy task status <id>`  | no     | `task_id: Some(state)` |
| result | `agy task result <id>`  | no     | `output: Some(text)`   |
| cancel | `agy task cancel <id>`  | no     | both `Nothing`         |

There is no `review` op. Review, research, summarization, and adversarial critique are all prompt content — one `agy -p` invocation. The calling agent builds the prompt; the shim does not distinguish prompt intent.

## [02]-[USAGE]

```bash
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py prompt "summarize this design tradeoff: ..." --model pro
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py prompt "give a fast factual answer: ..." --model flash
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py task "refactor module X end-to-end and report"
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py status <task-id>
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py result <task-id>
uv run $CLAUDE_HOME/skills/agy/scripts/agy.py cancel <task-id>
```

The op is the first positional; `prompt` takes the prompt text next, then an optional `--model <tier>`. Task ops take the task id as their single positional.

## [03]-[MODEL_TIER]

`--model <tier>` resolves the tier alias to the Gemini model id through the shim's `_TIER` table: `pro` -> `gemini-3-pro`, `flash` -> `gemini-3-flash`, `nano` -> `gemini-3-nano`. An unrecognized token passes through verbatim so explicit model ids still work. The flag is opt-in: when no `--model` is given the shim emits no `--model` argv and `agy` applies its own default; pass `--model pro` for deepest reasoning, `--model flash` for latency-sensitive inline lookups, `--model nano` for trivial classification.

## [04]-[OUTPUT]

stdout is one JSON object. Success is `AgyReceipt` (`op`, `output`, `task_id`); failure is `AgyFail` (`op`, `fault`, `detail`). The arm is distinguished by presence of `fault`. `fault` is one of `binary_not_found`, `auth_required`, `quota_exceeded`, `process_error`. There is no `timeout` fault — a deadline trip maps to `process_error`.

## [05]-[AUTH_AND_VPS]

First auth on the local machine: `agy auth login`. On a headless VPS: `agy auth login --no-browser` emits a URL + device code; complete consent in a desktop browser. The token caches under `$HOME/.config/antigravity/` (outside the repo; no gitignore rule needed) and persists across invocations. When `agy` returns an auth-expiry exit, the shim emits `AgyFail(fault="auth_required", ...)`; surface that as a human action item. Tune the per-call budget with `MAGHZ_INTEGRATIONS__AGY_PROCESS_TIMEOUT_S` for long autonomous tasks.
