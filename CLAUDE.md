# [CLAUDE_MANIFEST]

Operate as a senior developer building the tooling for a focused second brain. Heptabase owns content, PostgreSQL is the durable centralized ledger, and AI agents plus automations drive the work. Build the strongest source-backed implementation the workspace admits: newest viable language and platform features, full external-library capability, dense polymorphic owners, and root-up refactors instead of additive code.

## [01]-[MODEL_DISPATCH]

Rankings, higher = better. Cost reflects the operator's actual spend (OpenAI is near-free under a standing deal), not list price. Intelligence is how hard a problem the model absorbs unsupervised. Taste covers UI/UX, code quality, API design, and copy.

| [INDEX] | [MODEL]  | [COST] | [INTELLIGENCE] | [TASTE] |
| :-----: | :------- | :----: | :------------: | :-----: |
|  [01]   | gpt-5.5  |   9    |       8        |    5    |
|  [02]   | sonnet-5 |   5    |       4        |    6    |
|  [03]   | opus-4.8 |   4    |       7        |    7    |
|  [04]   | fable-5  |   2    |       9        |    9    |

How to apply:
- These are defaults, not limits, with standing permission to override them: when a cheaper model's output misses the bar, rerun or redo the work with a smarter model without asking. Judge the output, not the price tag; escalating costs less than shipping mediocre work.
- Cost never blocks the right model for the job; cheaper options gather information and trial runs before the work moves to a more expensive option.
- Bulk/mechanical work (clear-spec implementation, data analysis, migrations): gpt-5.5 - it's effectively free.
- Heavy exploration, investigation, and research legs: dispatch to gpt-5.5 (`codex exec`, read-only) before spawning Claude subagents - the transcript stays out of context and the usage is free.
- Anything user-facing (UI, copy, API design) needs taste ≥ 7.
- Reviews of plans/implementations: fable-5 or opus-4.8, optionally gpt-5.5 as an extra independent perspective.
- Mechanics: gpt-5.5 is only reachable through the Codex CLI - `codex exec` / `codex review` (my ~/.codex/config.toml defaults to gpt-5.5 at medium reasoning).
- Load the codex skill `.claude/skills/codex/SKILL.md` whenever dispatching work to codex - delegation triggers, invocation mechanics, sandboxing, effort tiers, sessions, and review modes live there.
- Reasoning effort defaults to medium; escalate a single run with `codex exec -c model_reasoning_effort="high"` (or `--profile xhigh`) for the hardest research, review, and design legs - multi-minute latency, reserve for depth over throughput.
- Claude models (sonnet-5, opus-4.8, fable-5) run via the Agent/Workflow model parameter.
- [NEVER]: use Haiku.

Using gpt-5.5 inside workflows and subagents (the model parameter only takes Claude models, so use a wrapper):
- Spawn a thin Claude wrapper agent with `model: 'sonnet', effort: 'low'` whose prompt instructs it to write a self-contained codex prompt, run `codex exec` via Bash, and return the report (use `schema` on the wrapper to get structured output back).
- Always label these agents with a `gpt-5.5:` prefix, e.g. `{label: 'gpt-5.5:review-auth'}` - the workflow UI shows the wrapper's Claude model, so the label is the only indication the real worker is gpt-5.5.
- Codex runs can exceed Bash's 10-minute timeout: pass an explicit timeout, or run in the background and poll for the report file.
- `codex exec -o <file>` writes the final message to a file (the report artifact to poll in background runs); `--output-schema <schema.json>` constrains the final message to a JSON Schema when the wrapper must return typed results.
- Workflow token budgets only count Claude tokens; codex work is free and invisible to `budget.spent()`.

## [02]-[WORKSPACE_LAW]

[IMPORTANT]:
- [ALWAYS]: Use `.claude/skills/workflow-creator` when creating a workflow.
- [ALWAYS]: Treat tooling code as polymorphic, agnostic, and universal by default.
- [ALWAYS]: Keep every surface agent-facing and agent-only: the CLI emits one JSON `Envelope` per call with no human-facing flags, prompts, or decorative output; agents and automations are the sole consumers, and automation is central design pressure even before the automations exist.
- [ALWAYS]: Identify canonical object shapes, field names, semantics, and receipts that scale across the `maghz` CLI, the database schema, infra, automations, and downstream consumers.
- [ALWAYS]: Use one canonical semantic name per bounded concept; arity, filters, provider, and modality live in request shape, case, policy row, or boundary adapter, not parallel names.
- [ALWAYS]: Extend the canonical owner before adding rails, public surfaces, wrappers, commands, flags, provider selectors, schemas, models, helpers, or files.
- [ALWAYS]: Treat planned future consumers as real design pressure. Zero current consumers never reduces the capability bar.
- [ALWAYS]: Capture host APIs, external packages, generated API evidence, and platform quirks into focused local owners so downstream code composes capability instead of re-learning provider surfaces.
- [ALWAYS]: Keep boundary mapping at the edge; internal code uses canonical names and shapes.
- [NEVER]: Split one concern across parallel objects, services, error rails, command families, or compatibility shims.
- [NEVER]: Create operation families such as `Get`, `GetMany`, `GetBy<Key>`, `List`, or `Search` for one concept when one polymorphic operation can discriminate by input value.
- [NEVER]: Preserve stale APIs, wrappers, aliases, or old-baseline caveats when a root-up collapse improves the system.

## [03]-[REQUIRED_STANDARDS]

Design law is the `docs/standards/` doctrine pair: `design-doctrine.md` binds every executable surface — rails, dispatch, boundaries, vocabularies — and `ops-doctrine.md` extends it onto the admin rails, SQL and schema surfaces, container topology, and automation specs. A design finding cites the doctrine card it breaks.

Use the route-owned standard for the file being edited:

| [INDEX] | [FILE_TYPE]              | [ROUTE]                              |
| :-----: | :----------------------- | :----------------------------------- |
|  [01]   | SQL (`.sql`)             | `coding-pg` + `ops-doctrine.md [03]` |
|  [02]   | Bash/sh (`.sh`, `.bash`) | `coding-bash`                        |
|  [03]   | Durable markdown (`.md`) | `docgen`                             |
|  [04]   | Mermaid fences           | `mermaid-diagramming`                |
|  [05]   | HTML artifacts (`.html`) | `html-studio`                        |

Python has no route skill: the doctrine pair plus this manifest's `[05]` constraints own Python shape, and `ruff`/`ty` gate style and types.

## [04]-[DEPENDENCY_POLICY]

[IMPORTANT]: External libraries, manifests, and host APIs are implementation surfaces.
- [ALWAYS]: Treat dependencies declared in `pyproject.toml`, the lockfile, and equivalent manifests as first-class material.
- [ALWAYS]: Mine admitted packages to their full useful capability before writing local kernels.
- [ALWAYS]: Prefer ecosystem libraries that already own the domain concern over lower-level reinvention.
- [ALWAYS]: Internalize external capability into canonical local owners organized by domain, axis, row, case, receipt, or rail.
- [ALWAYS]: Keep central package, version, and tool ownership in the one owning `pyproject.toml`; assume the newest stable release and pin a package only when it is not yet compatible, removing the pin when compatibility lands.
- [NEVER]: Hand-roll functionality provided by admitted dependencies.
- [NEVER]: Create thin wrappers that rename, forward, or partially expose external APIs without adding domain value.
- [NEVER]: Encode package versions, provider caveats, or command catalogs outside the owning manifest, package charter, README, or tool owner.

## [05]-[IMPLEMENTATION_CONSTRAINTS]

[CRITICAL]:
- [NEVER]: Use weak, unbounded, or erased types where the language can express the domain precisely.
- [NEVER]: Use exception-style control flow in domain logic; use typed error rails and the required route's recovery patterns.
- [NEVER]: Use imperative branching when a bounded vocabulary, dispatch table, generated switch, match, fold, or monadic rail can own the variation.
- [NEVER]: Use mutable accumulation for domain transforms; use immutable folds, projections, collection combinators, or effect/resource pipelines.
- [NEVER]: Proliferate schemas, structs, models, branded types, records, classes, aliases, or DTOs for the same concept.
- [NEVER]: Create helper/utility files or functions for single-caller or thin indirection.
- [NEVER]: Extract code to new files to reduce LOC. Densify in place through polymorphism, folds, generated owners, and table-driven dispatch.
- [NEVER]: Delete functionality to satisfy a density or LOC signal. Preserve capability through denser owners.
- [NEVER]: Replace operation-specific typed receipts with generic envelope, ledger, or reported-value abstractions.
- [NEVER]: Add comments that carry task, session, subagent, review-label, proof, history, or process narration.

[IMPORTANT]:
- [ALWAYS]: Collapse related variants into one polymorphic surface before adding entrypoints.
- [ALWAYS]: Drive logic with data, bounded vocabularies, discriminants, table rows, and reusable projections.
- [ALWAYS]: Co-locate domain logic with its owner instead of scattering it into generic support files.
- [ALWAYS]: Collapse repeated mutation/status/count construction into one fact stream with slot/kind metadata when three or more buckets share construction.
- [ALWAYS]: Keep typed operation receipts when fields carry route, status, sync, ingestion, retrieval, ranking, embedding, schema, or infra evidence.
- [ALWAYS]: Treat analyzer diagnostics as architecture pressure: fix true positives, refine false positives, and avoid suppressions that add ceremony without improving correctness.

## [06]-[BEHAVIOR]

[IMPORTANT]:
- [ALWAYS]: Tools over internal knowledge: read files, search code, verify assumptions through source, manifests, docs, and tool output.
- [ALWAYS]: Parallelize independent searches, reads, and checks.
- [ALWAYS]: Use bounded subagents for independent exploration, research, verification, and disjoint implementation when the user asks for subagents or parallel agent work.

## [07]-[OWNER_ROUTING]

[IMPORTANT]:
- [ALWAYS]: Dependency graph facts live in `pyproject.toml`, the lockfile, and the tool owner that consumes them.
- [ALWAYS]: Quality routes are selected by the owning language/tool surface for the changed files. Root policy owns intent, not command catalogs.
- [ALWAYS]: For docs-only, catalog-only, read-only, declaration-order, move-only, and comment-only work, use text, path, table, link, owner, and preservation checks unless the user requests an executable quality rail.
- [NEVER]: Add package versions, tool commands, hardcoded targets, or suite paths to root policy when a manifest, README, or language owner carries the exact command.
- [ALWAYS]: LSP owns live navigation and post-edit diagnostics over local source.
- [ALWAYS]: The `maghz` CLI owns schema, ledger, sync, and stack lifecycle (`up`, `down`) over the `maghz` database; invoke it through the project's `admin/` tooling and parse its JSON `Envelope`.
- [ALWAYS]: `maghz schema apply` owns idempotent declarative schema apply over `db/schema.sql`, `db/routines.sql`, and `db/cron.sql` in dependency order; a replay is a clean no-op, and `maghz schema doctor` asserts the live extension census owned by `admin/profile.py`. `AGENTS.md [05]` carries the full apply mechanism.
- [NEVER]: Create migration files, numbered `NNN_*.sql` scripts, schema-version tables, or up/down migration pairs; the schema is declarative and idempotent — change `db/schema.sql`, `db/routines.sql`, or `db/cron.sql` in place and replay through `maghz schema apply`.
- [ALWAYS]: `psql` and `pgcli` own ad-hoc SQL and interactive inspection; reach for them for one-off queries, not durable schema change.
- [ALWAYS]: Pulumi owns infra: the custom ParadeDB image build and the `db`/`ollama`/`n8n` services behind `StackOp`, driven by `MaghzSettings`. [SEAM] `compose.yaml` is the transitional parallel declaration of the same services (`local`/`prd` profiles); it retires when `StackOp` owns the full topology on both hosts, and until then a service change lands in both surfaces in the same pass.
- [ALWAYS]: `maghz exec` and `maghz deploy` own VPS operation; raw `ssh`/`docker`/`psql` against the VPS is debugging only, and every deploy receipt carries the pushed commit.
- [ALWAYS]: Route failures by seam: the stack, schema, ledger, and deploy rails are `admin/`-owned; the VPS operating system — users, network, firewall, system Docker, tunnels — is owned by the Forge flake's `nixosConfigurations.maghz` and changes through `forge-redeploy`, never through a patch in this repo.

## [08]-[TOOLING]

Machine tooling is provisioned by `Parametric_Forge` (Nix, on `PATH`) for both hosts; inspect the Forge owner before patching local toolchain failures. `AGENTS.md [06]` carries the full per-tool inventory by group, including the 12-server MCP fleet whose typed owner is `admin/mcp.py`.

Route each tooling concern through its owning skill:

| [INDEX] | [CONCERN]             | [SKILL]               |
| :-----: | :-------------------- | :-------------------- |
|  [01]   | Heptabase content     | `heptabase-cli`       |
|  [02]   | Source ingestion      | `notebooklm` MCP      |
|  [03]   | Library documentation | `context7-mcp`        |
|  [04]   | CI/CD pipelines       | `github-actions`      |
|  [05]   | Diagrams              | `mermaid-diagramming` |
|  [06]   | Lifecycle hooks       | `hooks-builder`       |
|  [07]   | Workflow authoring    | `workflow-creator`    |
|  [08]   | Notebook research     | `jupyter-notebooks`   |
|  [09]   | Secret custody        | `secrets`             |
|  [10]   | VPS / domains         | `hostinger`           |
|  [11]   | Infra as code         | `pulumi`              |

Resolve any external library's current API through `context7` before internalizing it into a canonical owner — newest-stable usage, never training-data. The web and docs research selection law (`Exa`/`Tavily` over built-in fetch, the async Exa Agent and slow `Perplexity` for deep questions, `mcp__github__*` for the GitHub API versus `gh` for local repo ops, context-isolated bulk reads) is the user-global doctrine and is not restated here.

## [09]-[DOCUMENTATION_AND_OUTPUT]

[IMPORTANT]:
- [ALWAYS]: Use `backticks` for file paths, symbols, and CLI commands.
- [ALWAYS]: Keep responses actionable and lead with what changed.
- [ALWAYS]: Treat durable docs, prompts, standards, skills, examples, and templates as agent-facing declarative law.
- [NEVER]: Add provenance blocks, research-origin sections, source tails, freshness disclaimers, defensive version caveats, checklist tails, or report framing to durable docs.
- [NEVER]: Tell a prompt recipient to read root instructions, load skills, follow instruction files, use known tools, or run standard checks when those obligations already come from active instructions.
- [NEVER]: Restate quality ladders, command catalogs, skill loading, load-order ladders, or system/developer rules in generated artifacts.

Plans are decision-complete blueprints. Include context, critical files, implementation approach, acceptance signals, and assumptions only when they change execution. Do not include workflow narration, alternatives considered, command catalogs, or boilerplate closure.

## [10]-[FILE_ORGANIZATION]

[IMPORTANT] Section separators: language comment marker + space + `---` + bracketed UPPERCASE snake label with no internal spaces + dash fill to the established language width.

```python
# --- [CONSTANTS] ------------------------------------------------------------------------
```

```sql
-- --- [MODELS] --------------------------------------------------------------------------
```

Canonical order, omitting unused sections: `TYPES` -> `CONSTANTS` -> `MODELS` -> `ERRORS` -> `SERVICES` -> `OPERATIONS` -> `COMPOSITION` -> `EXPORTS`.

`[RUNTIME_PRELUDE]` may precede the canonical order only for imports, shebangs, strict modes, session setup, and load gates.

- `[TYPES]`: type aliases, inferred types, protocols/interfaces, enums, discriminated unions, generated algebraic owners, value-object declarations.
- `[CONSTANTS]`: dependency-free immutable anchors, caps, suffixes, primitive policies, schedules, and static literals.
- `[MODELS]`: runtime schemas, records/classes, value objects, DTOs, table/domain models, receipts, result carriers.
- `[ERRORS]`: typed error rails, tagged failures, domain failure policies.
- `[SERVICES]`: service contracts, dependency surfaces, application/service classes.
- `[OPERATIONS]`: pure transforms, effect/result pipelines, algorithms, repository operations.
- `[COMPOSITION]`: layers, decorators, dependency wiring, middleware, runtime composition roots.
- `[EXPORTS]`: named exports, `__all__`, or language-equivalent public surface declarations.

[IMPORTANT]:
- [ALWAYS]: Apply ordering as `section` -> `owner block` -> `runtime/declaration dependency` -> `semantic rank` -> `kind` -> `smaller-to-larger` -> `alphabetical`.
- [ALWAYS]: Prefer concept discovery order from stable declarations to composition: vocabulary, constants, models, failures, services, operations, wiring, exports.
- [ALWAYS]: Treat one generated type, smart enum, value object, schema/model family, wire model family, kernel, registry, catalog, table, dispatcher, query family, or composition root as an owner block; sort inside the owner instead of flattening its members into unrelated top-level sections.
- [ALWAYS]: Keep dependency clusters intact when a declaration must follow the symbol it imports, inspects, derives from, registers, decodes, wraps, initializes, traps, migrates, or composes.
- [ALWAYS]: Use smaller-to-larger only after ownership and dependency order are satisfied: one-line anchors before multi-line policies, simple axes before rich models, leaf operations before orchestration.
- [ALWAYS]: Use alphabetical order only for equivalent declarations with the same owner, kind, dependency level, and semantic rank.
- [ALWAYS]: Treat kind as an owner-local tiebreaker, not a new section: type/member family precedes accessibility, size, and alphabetical order only when ownership, dependency, and semantic rank are equivalent.
- [ALWAYS]: For equivalent same-owner members, prefer public contract before internal extension before private implementation unless static construction, generated semantics, or read-before-use dependency requires another order.
- [ALWAYS]: Keep semantically ordered sequences in domain order: severity, lifecycle, routing, key, protocol, generated-case, table-row, migration-step, and public API order are load-bearing when the owner defines them.
- [ALWAYS]: Co-locate tightly coupled symbols when strict section order obscures ownership or violates language/runtime constraints.
- [ALWAYS]: Insert domain extensions immediately after the closest core section, using precise labels only when they name real ownership: `[TABLES]`, `[BOUNDARIES]`, `[REPOSITORIES]`, `[GROUPS]`, `[MIDDLEWARE]`, `[INDEXES]`, `[POLICIES]`, or `[ENTRY]`.
- [ALWAYS]: Use nested subsection labels inside large kernels only when they identify a real operation family, such as `[HYBRID_RANK]` or `[EMBED_BATCH]`.
- [ALWAYS]: Keep internal cache keys, memo tables, mutable registries, and algorithm state records with the operation, kernel, or runtime owner that reads and mutates them.
- [ALWAYS]: Treat logger handles, provider handles, and dependency-backed runtime capabilities as `[SERVICES]`, not immutable anchors.
- [NEVER]: Put derived codecs, decoders, registries, lookup tables, generated maps, dispatch rows, callable row catalogs, mutable memo tables, or DDL-dependent objects in top-level `[CONSTANTS]` when they depend on later models, functions, owners, runtime state, or migration state; place them in the owning later section or a precise extension such as `[TABLES]` or `[COMPOSITION]`.
- [NEVER]: Split source-generated owners, delegate-backed enum behavior, validation partials, private operation-local state, resource/disposal boundaries, dispatch tables, SQL invariants, or migration units to satisfy mechanical section order.
- [NEVER]: Rename recurring categories per file; use canonical labels unless a domain extension is materially clearer.
- [NEVER]: Use alias or drift labels that merely rename core categories or hide complexity: `SCHEMA`, `FUNCTIONS`, `LAYERS`, `IMPORTS`, `INTERFACES`, `ENUMS`, `DTO`, `QUERIES`, `HELPERS`, `UTILS`, `COMMON`, `MISC`.

Language overlays refine the canonical order by runtime semantics:
- Python: imports, `TYPE_CHECKING`, and import-time gates precede ordinary sections. Runtime decoders, encoders, registries, and tables follow the models/functions they inspect because module-level assignments execute immediately and runtime annotation consumers such as `msgspec` and `beartype` resolve real objects. `Annotated` validator functions may use `[BOUNDARIES]` between immutable constants and dependent aliases when the aliases must reference the real validator object.
- Bash: shebang, ShellCheck directives, `set`/`shopt`, and environment/path gates are `[RUNTIME_PRELUDE]`; `readonly` values are `[CONSTANTS]`; `declare -Ar` maps are `[TABLES]`; traps, dispatch, source guards, and `_main` are late `[COMPOSITION]` or `[ENTRY]`.
- PostgreSQL: extensions, schemas, and search-path guards are `[RUNTIME_PRELUDE]`; domains and types are `[TYPES]`; tables, constraints, generated columns, and partitions are `[MODELS]`; functions split by service boundary or query operation; indexes, triggers, row-level security, and policies are `[COMPOSITION]`; grants and comments are late `[EXPORTS]`.
- YAML/YML: manifests and configuration files are data surfaces, not sectioned source; do not add code-section dividers. Preserve sequence order, anchors, comments, duplicate-key constraints, schema-defined key order, and executable order. Mapping-key reorder is presentation-only unless the owning tool documents order-dependent behavior; otherwise prefer required identity/version fields before optional metadata, resources, executable units, outputs, and publication/export fields.
