# [MACROSCOPE]

One `.macroscope/` tree drives two surfaces: the local CLI correctness engine over git changes and the hosted PR reviewer with its check runs. Config is markdown concern files plus one glob-list ignore file — no JSON schema exists anywhere, so validation is YAML-frontmatter parse, glob sanity, and the prose gate.

## [01]-[CONCERN_SPLIT]

| [INDEX] | [AXIS]      | [CHECK_RUN_AGENTS]                    | [CORRECTNESS]                      |
| :-----: | :---------- | :------------------------------------ | :--------------------------------- |
|  [01]   | Unit        | one agent = one separate check run    | folds into the one correctness pass |
|  [02]   | Frontmatter | rich field set below                  | optional `include`/`exclude` only  |
|  [03]   | Blocking    | `conclusion: failure` blocks the PR   | advisory, inherits the built-in check |
|  [04]   | Surface     | hosted GitHub Checks only             | hosted and local CLI both          |

Each check-run agent is one cross-cutting lens over the whole diff — boundary integrity, topology closure, a strongest-form adversary — seeing what the file-local correctness pass cannot; agents deliberately never re-litigate mechanical checks the correctness lane owns.

## [02]-[CHECK_RUN_AGENTS]

`.macroscope/check-run-agents/*.md` frontmatter fields: `title` (60 chars max, the Checks-tab name), `input` (`full_diff` one agent over the diff / `code_object` up to 20 parallel per-object agents, high cost / `pr_metadata` metadata only), `effort` (`low`/`medium`/`high`), `reasoning` (`off`/`low`/`medium`/`high`/`xhigh`), `model`, `conclusion` (`neutral` advisory default / `failure` may block merge), `include`/`exclude` glob arrays, `labels`/`authors`/`targets` run filters, `requiredStatusCheck`, `showToolCalls`, `waitsFor` plus `waitsForTimeout` (1-60 min) CI gating, `maxRuns` per-PR cap.

## [03]-[CORRECTNESS]

- `.macroscope/correctness/**/*.md`: frontmatter is optional and carries only `include`/`exclude` glob arrays; omitting both applies the file globally.
- Macroscope walks `correctness/` recursively — subfolders are purely organizational (globs alone decide targeting, never the folder path), only `*.md` is processed, `README.md` is ignored, and every matching file stacks cumulatively onto a changed file.
- Body shape: one `# [UPPERCASE_LABEL]` H1 plus markdown instructions.

## [04]-[IGNORE]

`.macroscope/ignore` REPLACES the built-in defaults (vendored deps, generated code, binary assets, test files) rather than extending them — preserving a default means copying its pattern in; one glob per line, `#` comments, blank lines skipped, and the file governs both code review and check-run agents. Docs name the file `ignore`; a live tree carrying `ignore.md` is honored by the installed build, and the tree on disk is ground truth over the docs' spelling.

## [05]-[DISTILL_GRAIN]

- One topic per file under its `# [LABEL]` H1: a fact lands as a clause in the owning file, and an outgrown topic becomes a sibling file, never a swollen blob.
- Altitude routing: a universal lesson lands in `correctness/general/`, a language-bound lesson in `correctness/<language>/`, a boundary or topology lens as a check-run agent.

## [06]-[CLI_SEMANTICS]

- Fix-at-root lane: `macroscope codereview --raw --in-place --base <base>` — review and fixes share the real working tree, so the fixer edits the files the review read.
- Base semantics: the default worktree flow auto-detects the base (PR base, else `origin/HEAD`), builds `<repo>/.worktrees/macroscope-review-<sha>` with uncommitted work as a baseline commit, and emits `review_worktree=<path>` on stderr; `--in-place` without `--base` diffs against `HEAD` (uncommitted only); `--in-place --base <ref>` spans committed branch work plus uncommitted.
- No status subcommand exists; `macroscope me | jq -e .success` gates auth, returning login, version, and update state as JSON.
- No per-run instruction flag exists — `.macroscope/` files are the only steering channel, so an aimed round lands its concern file first, then launches.
- `issue_event` fields: `issue_id`, `sequence` (monotonic), `path`, `line`, `severity`, `category`, `body`. Category and severity vocabularies are open — `REVIEW_TYPE_CORRECTNESS` and `medium` sit on the wire — so the adapter passes both through raw and never enum-gates them, preferring the streamed `severity` over its own assessment.
- Local runs read `correctness/**` plus `ignore`; check-run agents ride the hosted Checks surface, so a local run surfaces correctness-style issues, never per-agent check runs.

## [07]-[LANGUAGES]

Native AST-level, per-language-tuned review covers Go, Python, TypeScript, JavaScript, Vue, Java, Rust, Kotlin, Swift, and Ruby; every other language rides the agentic cross-file engine — C# included, so C# doctrine reaches the reviewer only through `correctness/csharp/*` instructions. Config files, documentation, and scripts review as non-code, which is how markdown planning corpora enter scope.
