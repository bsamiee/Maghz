# [GREPTILE]

Greptile reviews committed unmerged commits against a base ref — uncommitted edits never enter, so work commits first, and work sitting on the base moves to a branch or passes `-b <base>` (remote-tracking refs accepted). Reviews are language-agnostic over the diff; `ignorePatterns` and `--include` (for sensitivity-held files) are the only file gates.

## [01]-[RUN_FACTS]

- Command roster: `review` (subcommands `show [id]` and `status`), `config [path]`, `login`, `logout`, `whoami`, `settings`, `update`; `onboard` and `fix` sit outside review work.
- `review` flags: `--json` emits the full findings document on stdout — the harvest source; `-b/--branch <base>` sets the base; `--instructions <text>` carries per-review focus through the same channel as `@greptile <instructions>` on a PR; `--resume` continues the latest unfinished review with no new spend; `--include` admits sensitivity-held files.
- `review status [--commit <ref>] [--json]` reports the most recent review status for a commit, `HEAD` by default.
- `greptile config [path]` prints the effective review configuration — `.greptile/` merged with dashboard and org rules, `path` scoping resolution to one file; a distilled rule proves itself by appearing in this output, which the rail's `verify` verb shells.
- `settings` keys: `color`, `apiBaseUrl` and `webBaseUrl` (self-hosted origin and dashboard URLs), `review.output`, `review.layout`, `review.context`, `review.width`.
- An oversized diff refuses client-side — `this review is too large to send. Split it into smaller commits and try again.` on stderr, exit 1, no ledger row, no spend; a large campaign lands as slice commits reviewed incrementally, each run passing `-b` at the prior boundary.
- Billing is per-use metered (`billing_not_configured` rejects before dispatch); per-review credit counts are dashboard territory, never a CLI fact.

## [02]-[CONFIG_CASCADE]

`.greptile/` in any directory configures reviews for that tree; three optional files, plus a single-file form (`greptile.json` or `.greptile.json`) that loses to a same-directory `.greptile/`.

- [CONFIG]: `config.json` — review settings, run filters, structured rules, cross-repo context.
- [RULES]: `rules.md` — free-prose review charter; severities and rule ids live only in `config.json`.
- [FILES]: `files.json` — `{"files": [{path, description, scope?}]}` points the reviewer at load-bearing repo files; `path` resolves relative to the directory holding `.greptile/`, so doctrine-pointing without duplication is the sanctioned use.

Cascade (Greptile's documented behavior): the walk from repository root to each reviewed file collects every `.greptile/` on the path — scalars take the most-specific value, arrays replace parent arrays, and rules, file references, and instructions accumulate; org enforced rules always win, and a child disables an inherited rule by listing its `id` in `disabledRules`.

## [03]-[CONFIG_FIELDS]

| [INDEX] | [FIELD]                                   | [SHAPE_AND_EFFECT]                                                  |
| :-----: | :---------------------------------------- | :------------------------------------------------------------------ |
|  [01]   | `strictness`                              | int `1`/`2`/`3`; higher filters harder                              |
|  [02]   | `commentTypes`                            | subset of `syntax`, `logic`, `style`, `info`                        |
|  [03]   | `ignorePatterns`                          | one newline-separated gitignore-syntax string, never an array       |
|  [04]   | `rules`                                   | rows of `{id, rule, severity, enabled, scope?}`                     |
|  [05]   | `disabledRules`                           | inherited rule ids disabled for this tree                           |
|  [06]   | `instructions`                            | free-form reviewer text; concatenates down the cascade              |
|  [07]   | `context.repos`                           | `owner/repo` list, same SCM host and credentials                    |
|  [08]   | `triggerOnUpdates` / `triggerOnDrafts`    | PR re-review and draft-review toggles                               |
|  [09]   | `statusCheck` / `statusCommentsEnabled`   | commit status check; PR status comments                             |
|  [10]   | `fixWithAI`                               | appends AI-fix prompts to findings                                  |
|  [11]   | section toggles                           | `{included, collapsible, defaultOpen}` per summary section          |
|  [12]   | PR-side filters                           | label, author, branch, and keyword include/exclude filters          |

`rules` rows: `severity` is `low`/`medium`/`high`, `scope` a glob array relative to the `.greptile/` directory, and a row without `scope` applies tree-wide.

## [04]-[DISTILL_GRAIN]

- A lesson lands as one sentence in its owning `rules.md` section or as one id-bearing, severity-scoped `config.json` row a child can disable; an outgrown row splits into sibling ids, never a mega-rule.
- Security lands as high-severity `rules` rows, `rules.md` sections, or org enforced dashboard rules — no security mode or flag exists.
- No JSON Schema exists for `config.json`: `greptile config` is the format gate — a landed rule is effective only when it survives the cascade into the resolved output — and a raw JSON parse is the syntactic floor alone. Greptile's `settings-schema.json` governs the CLI settings keys, never `config.json`.

## [05]-[RETRIEVAL_BRIDGE]

- `~/.greptile/reviews.json` is the CLI-local ledger, an object `{version, reviews[]}` — never a bare array; rows carry `runId`, `remoteUrl`, `baseRef`/`headRef`, `baseSha`/`headSha`, `createdAt`/`completedAt`, `commentCount`, `status` (`IN_FLIGHT`/`COMPLETED`), `accountKey`.
- `runId` is a CLI-local UUID and never the MCP `codeReviewId`; bridge a CLI run to its MCP row through `mcp__greptile__list_code_reviews` matched on `headSha`/`baseSha` plus timestamp — CLI runs surface there as `source: "headless"` with `mergeRequest` null.
- MCP starts no local review: `trigger_code_review` is PR/MR-only, so the CLI is the local rail and no branch or PR is ever created to run one. MCP value is retrieval — `get_code_review` (keyed by `codeReviewId`), `search_greptile_comments` full-text search — plus the org custom-context tools, the one channel `.greptile/` files cannot touch.
