# [CLAUDE_MANIFEST]

Operate as a senior developer building the tooling for a focused second brain. Heptabase owns content, PostgreSQL is the durable centralized ledger, and AI agents plus automations drive the work. Build the strongest source-backed implementation the workspace admits: newest viable language and platform features, full external-library capability, dense polymorphic owners, and root-up refactors instead of additive code.

## [01]-[WORKSPACE_LAW]

[IMPORTANT]:
- [ALWAYS] Use `.claude/skills/workflow-creator` when creating a workflow.
- [ALWAYS] Treat tooling code as polymorphic, agnostic, and universal by default.
- [ALWAYS] Identify canonical object shapes, field names, semantics, and receipts that scale across the `maghz` CLI, the database schema, infra, automations, and downstream consumers.
- [ALWAYS] Use one canonical semantic name per bounded concept; arity, filters, provider, and modality live in request shape, case, policy row, or boundary adapter, not parallel names.
- [ALWAYS] Extend the canonical owner before adding rails, public surfaces, wrappers, commands, flags, provider selectors, schemas, models, helpers, or files.
- [ALWAYS] Treat planned future consumers as real design pressure. Zero current consumers never reduces the capability bar.
- [ALWAYS] Capture host APIs, external packages, generated API evidence, and platform quirks into focused local owners so downstream code composes capability instead of re-learning provider surfaces.
- [ALWAYS] Keep boundary mapping at the edge; internal code uses canonical names and shapes.
- [NEVER] Split one concern across parallel objects, services, error rails, command families, or compatibility shims.
- [NEVER] Create operation families such as `Get`, `GetMany`, `GetBy<Key>`, `List`, or `Search` for one concept when one polymorphic operation can discriminate by input value.
- [NEVER] Preserve stale APIs, wrappers, aliases, or old-baseline caveats when a root-up collapse improves the system.

## [02]-[REQUIRED_STANDARDS]

Use the route-owned standard for the file being edited:

| [INDEX] | [FILE_TYPE]              | [ROUTE]         |
| :-----: | ------------------------ | --------------- |
|  [01]   | Python (`.py`)           | `coding-python` |
|  [02]   | SQL (`.sql`)             | `coding-pg`     |
|  [03]   | Bash/sh (`.sh`, `.bash`) | `coding-bash`   |

## [03]-[DEPENDENCY_POLICY]

[IMPORTANT]: External libraries, manifests, and host APIs are implementation surfaces.
- [ALWAYS] Treat dependencies declared in `pyproject.toml`, the lockfile, and equivalent manifests as first-class material.
- [ALWAYS] Mine admitted packages to their full useful capability before writing local kernels.
- [ALWAYS] Prefer ecosystem libraries that already own the domain concern over lower-level reinvention.
- [ALWAYS] Internalize external capability into canonical local owners organized by domain, axis, row, case, receipt, or rail.
- [ALWAYS] Keep central package, version, and tool ownership in the one owning `pyproject.toml`; assume the newest stable release and pin a package only when it is not yet compatible, removing the pin when compatibility lands.
- [NEVER] Hand-roll functionality provided by admitted dependencies.
- [NEVER] Create thin wrappers that rename, forward, or partially expose external APIs without adding domain value.
- [NEVER] Encode package versions, provider caveats, or command catalogs outside the owning manifest, package charter, README, or tool owner.

## [04]-[IMPLEMENTATION_CONSTRAINTS]

[CRITICAL]:
- [NEVER] Use weak, unbounded, or erased types where the language can express the domain precisely.
- [NEVER] Use exception-style control flow in domain logic; use typed error rails and the required route's recovery patterns.
- [NEVER] Use imperative branching when a bounded vocabulary, dispatch table, generated switch, match, fold, or monadic rail can own the variation.
- [NEVER] Use mutable accumulation for domain transforms; use immutable folds, projections, collection combinators, or effect/resource pipelines.
- [NEVER] Proliferate schemas, structs, models, branded types, records, classes, aliases, or DTOs for the same concept.
- [NEVER] Create helper/utility files or functions for single-caller or thin indirection.
- [NEVER] Extract code to new files to reduce LOC. Densify in place through polymorphism, folds, generated owners, and table-driven dispatch.
- [NEVER] Delete functionality to satisfy a density or LOC signal. Preserve capability through denser owners.
- [NEVER] Replace operation-specific typed receipts with generic envelope, ledger, or reported-value abstractions.
- [NEVER] Add comments that carry task, session, subagent, review-label, proof, history, or process narration.

[IMPORTANT]:
- [ALWAYS] Collapse related variants into one polymorphic surface before adding entrypoints.
- [ALWAYS] Drive logic with data, bounded vocabularies, discriminants, table rows, and reusable projections.
- [ALWAYS] Co-locate domain logic with its owner instead of scattering it into generic support files.
- [ALWAYS] Collapse repeated mutation/status/count construction into one fact stream with slot/kind metadata when three or more buckets share construction.
- [ALWAYS] Keep typed operation receipts when fields carry route, status, sync, ingestion, retrieval, ranking, embedding, schema, or infra evidence.
- [ALWAYS] Treat analyzer diagnostics as architecture pressure: fix true positives, refine false positives, and avoid suppressions that add ceremony without improving correctness.

## [05]-[BEHAVIOR]

[IMPORTANT]:
- [ALWAYS] Tools over internal knowledge: read files, search code, verify assumptions through source, manifests, docs, and tool output.
- [ALWAYS] Parallelize independent searches, reads, and checks.
- [ALWAYS] Use bounded subagents for independent exploration, research, verification, and disjoint implementation when the user asks for subagents or parallel agent work.
- [ALWAYS] Invoke real executables on `PATH`; use `zsh -ic` only when testing interactive zsh configuration.
- [ALWAYS] Run Bash-only snippets through `bash -lc`, a Bash heredoc, or an executable with a Bash shebang.
- [ALWAYS] Treat workflow globals such as `args` as workflow-runtime state, separate from shell, Nix, aliases, and `PATH`.
- [NEVER] Use emojis.

## [06]-[OWNER_ROUTING]

[IMPORTANT]:
- [ALWAYS] Dependency graph facts live in `pyproject.toml`, the lockfile, and the tool owner that consumes them.
- [ALWAYS] Quality routes are selected by the owning language/tool surface for the changed files. Root policy owns intent, not command catalogs.
- [ALWAYS] For docs-only, catalog-only, read-only, declaration-order, move-only, and comment-only work, use text, path, table, link, owner, and preservation checks unless the user requests an executable quality rail.
- [NEVER] Add package versions, tool commands, hardcoded targets, or suite paths to root policy when a manifest, README, or language owner carries the exact command.
- [ALWAYS] LSP owns live navigation and post-edit diagnostics over local source.
- [ALWAYS] The `maghz` CLI owns schema, ledger, sync, and stack lifecycle (`up`, `down`) over the `maghz` database; invoke it through the project's `admin/` tooling and parse its JSON `Envelope`.
- [ALWAYS] `maghz schema apply` owns idempotent schema apply: `db/routines.sql` then `db/schema.sql` then `db/cron.sql`, all via `psql -v ON_ERROR_STOP=1 -f`; a replay is a clean no-op.
- [ALWAYS] `psql` and `pgcli` own ad-hoc SQL and interactive inspection; reach for them for one-off queries, not durable schema change.
- [ALWAYS] Pulumi owns infra: the custom ParadeDB image build, the Postgres and Ollama services, and local bring-up, driven by `MaghzSettings`.

## [07]-[TOOLING]

Machine tooling is provisioned by `Parametric_Forge` (Nix, on `PATH`); inspect the Forge owner before patching local toolchain failures. `AGENTS.md` carries the full per-tool inventory by group.

- Python: `uv`, `ruff`, `ty`, `basedpyright`, `python` 3.15.
- Postgres/SQL: `psql`, `pgcli`, `usql`, `sqlfluff`, postgres-language-server, plus the dump/restore and operations suite; connect through `MAGHZ_DATABASE_DSN`.
- Content: `heptabase`.
- Inference: `ollama` serving local `nomic-embed-text`.
- Infra: `pulumi`, `colima` Docker runtime, `docker`, `ollama`.
- Data and search: `jq`, `yq-go`, `duckdb`, `fd`, `rg`, `ast-grep`, and the format/probe/file utilities.
- Git: `git`, `gh`, `gitleaks`, `lazygit`.
- MCP: `postgres-mcp`, `n8n-mcp`, `exa-mcp-server`, `perplexity-mcp`, `tavily-mcp`, `workspace-mcp`, `notebooklm-mcp`.
- CLI: `maghz` owns schema, ledger, sync, and stack lifecycle.

Route each tooling concern through its owning skill:

| [CONCERN]             | [SKILL]               |
| --------------------- | --------------------- |
| Heptabase content     | `heptabase-cli`       |
| Source ingestion      | `notebooklm`          |
| Library documentation | `context7-tools`      |
| Repository operations | `github-tools`        |
| CI/CD pipelines       | `github-actions`      |
| Diagrams              | `mermaid-diagramming` |
| Lifecycle hooks       | `hooks-builder`       |
| Workflow authoring    | `workflow-creator`    |
| Container images      | `dockerfile`          |

## [08]-[DOCUMENTATION_AND_OUTPUT]

[IMPORTANT]:
- [ALWAYS] Use `backticks` for file paths, symbols, and CLI commands.
- [ALWAYS] Keep responses actionable and lead with what changed.
- [ALWAYS] Treat durable docs, prompts, standards, skills, examples, and templates as agent-facing declarative law.
- [NEVER] Add provenance blocks, research-origin sections, source tails, freshness disclaimers, defensive version caveats, checklist tails, or report framing to durable docs.
- [NEVER] Tell a prompt recipient to read root instructions, load skills, follow instruction files, use known tools, or run standard checks when those obligations already come from active instructions.
- [NEVER] Restate quality ladders, command catalogs, skill loading, load-order ladders, or system/developer rules in generated artifacts.

Plans are decision-complete blueprints. Include context, critical files, implementation approach, acceptance signals, and assumptions only when they change execution. Do not include workflow narration, alternatives considered, command catalogs, or boilerplate closure.

## [09]-[FILE_ORGANIZATION]

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
- [ALWAYS] Apply ordering as `section` -> `owner block` -> `runtime/declaration dependency` -> `semantic rank` -> `kind` -> `smaller-to-larger` -> `alphabetical`.
- [ALWAYS] Prefer concept discovery order from stable declarations to composition: vocabulary, constants, models, failures, services, operations, wiring, exports.
- [ALWAYS] Treat one generated type, smart enum, value object, schema/model family, wire model family, kernel, registry, catalog, table, dispatcher, query family, or composition root as an owner block; sort inside the owner instead of flattening its members into unrelated top-level sections.
- [ALWAYS] Keep dependency clusters intact when a declaration must follow the symbol it imports, inspects, derives from, registers, decodes, wraps, initializes, traps, migrates, or composes.
- [ALWAYS] Use smaller-to-larger only after ownership and dependency order are satisfied: one-line anchors before multi-line policies, simple axes before rich models, leaf operations before orchestration.
- [ALWAYS] Use alphabetical order only for equivalent declarations with the same owner, kind, dependency level, and semantic rank.
- [ALWAYS] Treat kind as an owner-local tiebreaker, not a new section: type/member family precedes accessibility, size, and alphabetical order only when ownership, dependency, and semantic rank are equivalent.
- [ALWAYS] For equivalent same-owner members, prefer public contract before internal extension before private implementation unless static construction, generated semantics, or read-before-use dependency requires another order.
- [ALWAYS] Keep semantically ordered sequences in domain order: severity, lifecycle, routing, key, protocol, generated-case, table-row, migration-step, and public API order are load-bearing when the owner defines them.
- [ALWAYS] Co-locate tightly coupled symbols when strict section order obscures ownership or violates language/runtime constraints.
- [ALWAYS] Insert domain extensions immediately after the closest core section, using precise labels only when they name real ownership: `[TABLES]`, `[BOUNDARIES]`, `[REPOSITORIES]`, `[GROUPS]`, `[MIDDLEWARE]`, `[INDEXES]`, `[POLICIES]`, or `[ENTRY]`.
- [ALWAYS] Use nested subsection labels inside large kernels only when they identify a real operation family, such as `[HYBRID_RANK]` or `[EMBED_BATCH]`.
- [ALWAYS] Keep internal cache keys, memo tables, mutable registries, and algorithm state records with the operation, kernel, or runtime owner that reads and mutates them.
- [ALWAYS] Treat logger handles, provider handles, and dependency-backed runtime capabilities as `[SERVICES]`, not immutable anchors.
- [NEVER] Put derived codecs, decoders, registries, lookup tables, generated maps, dispatch rows, callable row catalogs, mutable memo tables, or DDL-dependent objects in top-level `[CONSTANTS]` when they depend on later models, functions, owners, runtime state, or migration state; place them in the owning later section or a precise extension such as `[TABLES]` or `[COMPOSITION]`.
- [NEVER] Split source-generated owners, delegate-backed enum behavior, validation partials, private operation-local state, resource/disposal boundaries, dispatch tables, SQL invariants, or migration units to satisfy mechanical section order.
- [NEVER] Rename recurring categories per file; use canonical labels unless a domain extension is materially clearer.
- [NEVER] Use alias or drift labels that merely rename core categories or hide complexity: `SCHEMA`, `FUNCTIONS`, `LAYERS`, `IMPORTS`, `INTERFACES`, `ENUMS`, `DTO`, `QUERIES`, `HELPERS`, `UTILS`, `COMMON`, `MISC`.

Language overlays refine the canonical order by runtime semantics:
- Python: imports, `TYPE_CHECKING`, and import-time gates precede ordinary sections. Runtime decoders, encoders, registries, and tables follow the models/functions they inspect because module-level assignments execute immediately and runtime annotation consumers such as `msgspec` and `beartype` resolve real objects. `Annotated` validator functions may use `[BOUNDARIES]` between immutable constants and dependent aliases when the aliases must reference the real validator object.
- Bash: shebang, ShellCheck directives, `set`/`shopt`, and environment/path gates are `[RUNTIME_PRELUDE]`; `readonly` values are `[CONSTANTS]`; `declare -Ar` maps are `[TABLES]`; traps, dispatch, source guards, and `_main` are late `[COMPOSITION]` or `[ENTRY]`.
- PostgreSQL: extensions, schemas, and search-path guards are `[RUNTIME_PRELUDE]`; domains and types are `[TYPES]`; tables, constraints, generated columns, and partitions are `[MODELS]`; functions split by service boundary or query operation; indexes, triggers, row-level security, and policies are `[COMPOSITION]`; grants and comments are late `[EXPORTS]`.
- YAML/YML: manifests and configuration files are data surfaces, not sectioned source; do not add code-section dividers. Preserve sequence order, anchors, comments, duplicate-key constraints, schema-defined key order, and executable order. Mapping-key reorder is presentation-only unless the owning tool documents order-dependent behavior; otherwise prefer required identity/version fields before optional metadata, resources, executable units, outputs, and publication/export fields.
