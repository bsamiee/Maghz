# [CODERABBIT]

`.coderabbit.yaml` at the repository root owns CodeRabbit behavior for hosted and CLI reviews alike; organization and workspace overrides outrank it, and it outranks every UI setting. Top-level `inheritance: true` opts into the central config in a repository named `coderabbit`, the chain stopping at the first parent lacking the flag. Reviews are language-general; per-language depth rides the static-analysis tool gates below.

## [01]-[SCHEMA_AND_LIMITS]

A real JSON Schema (Draft 2020-12) validates the file: `https://coderabbit.ai/integrations/schema.v2.json`, mirrored at `https://storage.googleapis.com/coderabbit_public_assets/schema.v2.json`. Validate with `ajv` against the pinned URL or a `# yaml-language-server: $schema=<url>` modeline, never a vendored copy.

| [INDEX] | [FIELD]                                         | [LIMIT]     |
| :-----: | :---------------------------------------------- | :---------- |
|  [01]   | `reviews.path_instructions[].instructions`      | 20000 chars |
|  [02]   | `tone_instructions`                             | 250 chars   |
|  [03]   | `pre_merge_checks.custom_checks[].instructions` | 10000 chars |
|  [04]   | `knowledge_base.learnings.approval_delay`       | 0-30 days   |

`tone_instructions` is a top-level key, a sibling of `reviews` — nesting it under `reviews` fails the schema.

## [02]-[DISTILL_GRAIN]

A fact lands as one clause inside its owning `reviews.path_instructions` block — `{path, instructions}` with `path` a minimatch glob — never as a per-fact path row; a new block is earned by a new territory (a language branch, a doctrine surface, a test or tooling tree), and the 20000-char ceiling prices clause density per block.

## [03]-[GUIDANCE_CHANNELS]

Four channels, routed by durability and origin:

- [PATH_INSTRUCTIONS]: durable reviewer law versioned in the repo — the DISTILL surface above.
- [GUIDELINE_FILES]: `knowledge_base.code_guidelines.filePatterns` absorbs doctrine files wholesale — plain globs or `{files, applyTo}` objects whose comma-separated `applyTo` globs scope a guideline set to the paths it governs; defaults cover the `CLAUDE.md`/`AGENTS.md` agent-rule family.
- [RUN_CONTEXT]: `-c <files...>` on `coderabbit review` attaches per-run instruction files.
- [LEARNINGS]: hosted-PR chat-taught facts (`@coderabbitai remember`) stored server-side; `learnings.scope` picks `local`/`global`/`auto`, `approval_delay` gates auto-apply, and `opt_out: true` erases stored data irrevocably.

## [04]-[HIGH_LEVERAGE_FIELDS]

- `reviews.profile`: `quiet` | `chill` | `assertive`.
- `reviews.path_filters`: include/exclude globs, `!` prefixing excludes.
- `reviews.pre_merge_checks`: per-check `off`/`warning`/`error`; `error` blocks the PR under `reviews.request_changes_workflow: true`.
- `reviews.tools.<tool>.enabled`: per-tool static-analysis gates over the schema's tool catalog (`ruff`, `biome`, `shellcheck`, `gitleaks`, and peers); `ast-grep` alone takes `essential_rules` instead of `enabled`.
- `reviews.finishing_touches` / `reviews.slop_detection.enabled` / `reviews.enable_prompt_for_ai_agents`: post-review recipes, slop screening, inline AI-fix prompts.
- `knowledge_base.mcp.usage`: `auto`/`enabled`/`disabled` plus `disabled_servers[]`.
- `knowledge_base.linked_repositories[]`: `{repository, instructions}` cross-repo context rows.

## [05]-[STREAM_AND_STORE]

`--agent` emits NDJSON on stdout with line types `review_context`, `status`, `heartbeat`, `finding`, `complete`; a streamed `finding` carries only `{severity, fileName, codegenInstructions, suggestions}` — lean by design, so the stream alone loses title, comment, and line range.

Rich per-finding records live at `~/.coderabbit/reviews/<repoHash>/<subHash>/reviews/<epochMs>/<uuid>.json`, one file per finding: `title`, `comment` (markdown carrying the proposed-fix diff), `lineRange`, `commentCategory`, `severity`, `codegenInstructions`, `fingerprint` (CodeRabbit's own dedup key, distinct from the rail's content hash), `diff`; sibling `internalState.json` carries the walkthrough summary in `rawSummaryMap`, and sibling `git.json` carries `workingDirectory` plus `timestamp` — the run-to-store correlation key. Severity ranks `critical` > `major` > `minor` > `trivial` > `info`. Consume `codegenInstructions` first with `comment` as fallback; `coderabbit review findings` reprints the previous run, so a finished review is never re-run to recover its findings.
