# [OPS_DOCTRINE]

Service-estate law extending the design doctrine onto operational Python rails, SQL and schema surfaces, container topology, and workflow automation. Every surface is agent-first: complete typed requests in, one envelope or receipt out, diagnostics on a side channel.

## [01]-[USE_WHEN]

Apply when writing or reviewing admin CLIs, infrastructure verbs, database schema and routines, container manifests, and automation specs. A finding cites the card it breaks.

## [02]-[ADMIN_RAILS]

[RAIL_LOWERER]:
- Law: CLI handlers bind request shapes, call owner rails, lower one envelope, and map status to exit code; envelope construction is centralized in one completed constructor and one fault constructor.
- Rejected: Command bodies implementing domain behavior, multi-line prints as results, branching on exceptions at the edge, ad hoc JSON payloads per command.
- Example: `async def _run(spec: Spec) -> Envelope: return lower(await operate(spec, settings()))`

[RUNTIME_SUBSTRATE]:
- Law: One runtime owner exposes guarded execution, lane policies, drains, signal handling, and receipt emission; driver adapters offload blocking work through lane limiters and return typed results.
- Rejected: Per-module retry loops, local limiters, free task groups, blocking DB or SSH work on the event loop, scattered thread offloads.
- Example: `receipt = await drain(LanePolicy(capacity=4, key=LaneKey("shape.apply")), units)`

[VERB_ROWS]:
- Law: Infrastructure verbs are table rows carrying operation, provider method, summary projection, and optional after-hook; a new verb is one enum member, one request case, one dispatch row, and one receipt shape when evidence differs.
- Rejected: Separate up/down/status implementations with duplicated provider setup, new command families, copied helpers, branching added to the CLI.
- Example: `VERBS = {Op.UP: Verb(Op.UP, drive=driven(up, summary), after=pull)}`

[TYPED_SUBPROCESS]:
- Law: Process calls route through one async spawn adapter with retry class, environment projection, and receipt grading.
- Rejected: `subprocess.run` in domain code, shell strings, unchecked return codes, stdout fragments as results.
- Example: `await spawn(("tool", "apply", path), subject="tool.apply", retry_class=Retry.PROC)`

[SETTINGS_INGRESS]:
- Law: One validated immutable settings owner feeds every adapter and projection, with derived properties computing dependent forms.
- Rejected: Direct `os.environ` reads, runtime config mutation, duplicate DSN fields, CLI-only secrets, inline credentials.
- Example: `class Settings(BaseSettings, frozen=True): database: Database; automation: Automation`

[CLOSED_FAULTS]:
- Law: A closed fault vocabulary partitions config, resource, deadline, api, wire, boundary, and aggregate failures, and maps provider errors once at the seam.
- Rejected: Message-substring handling at call sites, retrying terminal faults, one catch-all string class.
- Example: `FAULTS.choose(lambda row: Some(row.project(subject, cause)) if isinstance(cause, row.catches) else Nothing)`

[OPERATION_RECEIPTS]:
- Law: Each operation emits a typed receipt carrying route, resource changes, diagnostics, skipped work, counts, timings, and artifact names; heavy provider SDK imports live inside offloaded program bodies.
- Rejected: Success text as evidence, bare counters, stderr as the result channel, provider imports at module import time when only parsing is needed.
- Example: `class StackReceipt(Detail, frozen=True): op: Op; changes: Mapping[str, int]; diagnostics: int`

## [03]-[SQL_SURFACES]

[DECLARATIVE_LEDGER]:
- Law: Canonical schema files are idempotent, dependency ordered, and replay to no-op on a settled database.
- Rejected: Numbered migrations, up/down pairs, schema-version tables, imperative patch scripts.
- Example: `CREATE TABLE IF NOT EXISTS shape (...); CREATE INDEX IF NOT EXISTS shape_key_idx ON shape(key);`

[SET_ALGEBRA]:
- Law: Relational transforms, ranking, refresh, dedup, queue drains, and ledgers execute in SQL when the database owns the operation.
- Rejected: Row-by-row application loops, application-side reconciliation, N+1 query projections.
- Example: `WITH ranked AS (...) INSERT INTO result SELECT ... FROM ranked WHERE ...;`

[EXTENSION_CENSUS]:
- Law: Installed extensions are admitted product capabilities surfaced through typed routines; one catalog renders installation and the schema prelude, and a doctor rail asserts live parity with the declared set.
- Rejected: Hand-built search, queue, vector, cron, or fuzzy matching beside an installed extension, duplicate extension lists across Dockerfiles, docs, schema, and code.
- Example: `SELECT extname FROM pg_extension EXCEPT SELECT name FROM declared_extension;`

[CANONICAL_TABLES]:
- Law: Tables model canonical concepts once — native enums and domains, constraints, generated columns, FKs, typed JSON schemas — and durable routines qualify their schema explicitly.
- Rejected: DTO tables, staging copies without semantics, parallel enum and check vocabularies, ambient `public` assumptions in durable routines.
- Example: `CREATE TYPE status AS ENUM ('pending','running','done');`

[POLYMORPHIC_ROUTINES]:
- Law: One routine accepts typed parameters and fuses modalities internally; rank fusion combines ordinal ranks under parameterized weights, never raw scores across engines.
- Rejected: One function per caller, separate lexical, vector, and fuzzy query functions, caller-side merge arithmetic over incomparable score scales.
- Example: `CREATE FUNCTION search(query_text text, query_vec vector(768) DEFAULT NULL) RETURNS TABLE (...)`

[ASYNC_RECEIPTS]:
- Law: Outbound async work carries a durable receipt row — request id, target id, content hash, enqueue time, drain time, expiry path — and cron registration is idempotent composition over a table of job rows.
- Rejected: Fire-and-forget requests without join keys, duplicated schedule setup, unmanaged job bodies.
- Example: `CREATE TABLE request_receipt(request_id bigint PRIMARY KEY, shape_id uuid, content_hash bytea, drained_at timestamptz);`

[SQL_PROJECTIONS]:
- Law: Application SQL that becomes a durable projection is parsed into AST metadata, and its receipt carries columns, tables, predicates, and lineage.
- Rejected: Opaque query strings as durable projections, unbounded projection drift, lineage recovered by hand.
- Example: `Projection(sql=tree.sql(dialect="postgres"), columns=..., tables=...)`

[LOCK_POSTURE]:
- Law: Populated-table DDL states its lock posture with bound acquisition when replay runs live.
- Rejected: Unbounded live replay stalls, `CONCURRENTLY` inside transactions.
- Example: `SET lock_timeout='3s'; CREATE INDEX IF NOT EXISTS ...; RESET lock_timeout;`

## [04]-[CONTAINER_TOPOLOGY]

[ONE_OWNER]:
- Law: One tool-native owner declares the service graph; any secondary manifest is generated from it and binds no truth.
- Rejected: Live Compose beside live IaC for the same services, divergent ports, duplicated env, manual container commands as lifecycle.
- Example: `SERVICES = {Service.DB: Container(...), Service.WORKER: Container(...)}`

[SERVICE_ROWS]:
- Law: Each service row carries image or build, ports, volumes, health, labels, resources, dependencies, network aliases, and receipt projection; profiles discriminate environments over one closed service set.
- Rejected: Copied container blocks, stringly name filters, hardcoded cross-container hostnames, separate manifests per environment with drifted shapes.
- Example: `ServiceRow(name="db", image=image.ref, ports=(Port(5432, cfg.db_port),), health=Health(...))`

[PARAMETERIZED_RESOURCES]:
- Law: Typed settings feed every resource argument — ports, image tags, paths, memory, model names — and derived URLs and DSNs come from one config owner.
- Rejected: Hardcoded host ports, inline image tags, protocol branches in service bodies.
- Example: `ports=[Port(internal=5432, external=cfg.database.port, ip="127.0.0.1")]`

[BUILD_CAPABILITY]:
- Law: Image build is a declared resource carrying context, Dockerfile, build args, platform, and cache posture, with load or push stated explicitly.
- Rejected: Shell build commands as lifecycle, untracked build args, ambient build cache.
- Example: `Image(context=cfg.image_context, args={"VARIANT": cfg.variant}, cache=Cache(local=cfg.cache_dir))`

[SECRET_EDGES]:
- Law: Secrets mount as files or env references injected at the edge; committed manifests carry placeholders only.
- Rejected: Inline passwords, checked-in tokens, generated configs containing resolved secrets.
- Example: `envs=["TOKEN_FILE=/run/secrets/token"]`

[HEALTH_AND_STATE]:
- Law: Each service row owns a health contract — command, interval, timeout, retries, start period — and durable state lives in named volumes with explicit owners and permissions.
- Rejected: Sleep loops as readiness, anonymous volumes, host-path sprawl, cache paths by convention only.
- Example: `Health(test=("CMD","service","health"), interval="10s", timeout="5s", retries=5)`

[QUERYABLE_RUNTIME]:
- Law: Labels and aliases generated from service rows are the runtime query API, and every topology operation emits a receipt with resource-change counts, outputs, and diagnostics.
- Rejected: Container-name coupling, parsing process listings as inspection, silent up/down/status.
- Example: `StackReceipt(op=Op.UP, resource_changes=changes, outputs=outputs, diagnostics=count)`

## [05]-[AUTOMATION]

[TRIGGER_ACTION]:
- Law: Automation is one spec pairing a typed trigger variant with a typed action variant; lane, id, policy, and receipt are shared across all pairings.
- Rejected: Separate watch, schedule, and manual command families, shell command blobs as actions, free-form JSON without decoding.
- Example: `class Spec(Struct): trigger: Watch | Schedule | Manual; action: Agent | Notify | Sync`

[PROVIDER_PRIMITIVES]:
- Law: Scheduler and watcher providers own schedule and watch semantics; trigger cases carry every provider-owned parameter — paths, filters, cron, timezone, jitter, debounce, recursion.
- Rejected: Hand-rolled polling loops, cron parsing by string split, filesystem recursion by manual walk.
- Example: `CronTrigger.from_crontab(spec.cron, timezone=spec.timezone)`

[LANE_ADMISSION]:
- Law: Each run passes capacity, deadline, resource, and known-lane admission before executing, and every non-execution outcome records a skip receipt with reason and spec id.
- Rejected: Unbounded task spawning, best-effort concurrency, dropped ticks, silent saturation.
- Example: `Gate(reason=GateReason.SATURATED, spec_id=spec.id, detail="lane full")`

[DURABLE_EVIDENCE]:
- Law: Automation receipts record trigger tag, action tag, lane, attempt, elapsed time, affected rows, job id, and resource snapshot; workflow exports are typed projections while canonical behavior lives in spec rows.
- Rejected: Free logs as evidence, mutable report dicts, hand-edited exported workflow JSON treated as canonical.
- Example: `AutomationReceipt(spec_id=id, trigger_tag="manual", action_tag="sync", elapsed_ms=elapsed)`

[COMPOSED_ACTIONS]:
- Law: Action dispatch calls the canonical owner rail and projects its receipt into automation evidence; an unsupported dispatch arm returns a typed fault until a real owner exists.
- Rejected: Reimplemented sync, embed, or notification logic inside actions, placeholder no-ops, unimplemented arms returning OK.
- Example: `return (await sync(cfg, key)).map(project_sync_evidence)`

[NO_HUMAN_MODE]:
- Law: Agents submit complete specs and parse one envelope; long-running lanes install one signal receiver, cancel the task group, and ledger accepted work before shutdown.
- Rejected: Prompts, interactive selection, decorative CLI output, orphaned watchers, per-action signal handling.
- Example: `automation run --spec '<json Spec>' -> Envelope`
