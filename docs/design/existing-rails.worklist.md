# [WORKLIST_EXISTING_RAILS]

Realize-ready worklist folded from `docs/design/existing-rails.md`. The blueprint is the design; this is the execution order. Working material — `admin/` source, `db/`, and the `maghz` CLI carry binding truth after realize.

---

## [01]-[OWNERS]

One canonical owner per concept. Files to create (`+`), modify (`~`), delete (`-`).

| [OP] | [FILE] | [OWNS] | [REALIZE_NOTE] |
| :--- | :----- | :----- | :------------- |
| `~` | `admin/settings/config.py` | `MaghzSettings` `BaseSettings` owner; `DatabaseConfig`/`OllamaConfig`/`InfraConfig`/`ObservabilityConfig` frozen sub-models; one `settings()` `lru_cache` factory | Verify `nested_model_default_partial_update=True` against the lockfile pydantic-settings (>=2.14.1 admitted). No surface change otherwise. |
| `~` | `admin/core/status.py` | `Status` closed `StrEnum`; `_RANK_EXIT` correspondence table driving `code`/`worst`/`fold` | Replace `MappingProxyType[Status, tuple[int,int]]` with `frozendict[Status, tuple[int,int]]`. Move `_RANK_EXIT` to a `[TABLES]` block. |
| `~` | `admin/core/model.py` | `Envelope`/`Detail`/`Report`/`Row` JSON result contract; `completed`/`fault` constructors | Add shared module-level `msgspec.json.Encoder()` instance used by `Envelope.encode`. Confirm all structs carry `gc=False`. |
| `~` | `admin/db.py` | `query` single pg8000 boundary; `DbFault` tagged by `Boundary`; `QueryResult`; `Scalar` alias | Add `_DB_LIMITER: CapacityLimiter = anyio.CapacityLimiter(8)` `[SERVICES]`; thread `limiter=_DB_LIMITER` on every `to_thread.run_sync`. Apply `@stamina.retry(on=pg8000.Error, attempts=3, wait_initial=0.5, wait_max=5.0, timeout=30.0)` to `_run_blocking`. `DbFault` gets `gc=False`. |
| `~` | `admin/infra/runner.py` | `run(op: StackOp, cfg, /)` single Automation API entrypoint; `_BUILD` dispatch table; promotes `StackOp` to this owner | Collapse `up`/`down`/`status` into `_up_detail`/`_down_detail`/`_status_detail` private builders fed by `_BUILD: frozendict[StackOp, Callable[[MaghzSettings], Awaitable[StackDetail]]]`. Move `StackOp`, `StackDetail`, `_Pull`, `_changes`, `_pull_embed_model`, `_BUILD`, `run` here from deleted `rails/stack.py`. Apply `@stamina.retry(on=(httpx.ConnectError, httpx.RemoteProtocolError), attempts=5, wait_initial=1.0, wait_max=10.0, timeout=60.0)` to `_pull_embed_model`. |
| `~` | `admin/infra/stack.py` | `define` Pulumi desired-state program; no public types | No collapse. Confirm it carries only the IaC program, not dispatch. |
| `~` | `admin/rails/schema.py` | `run(op: SchemaOp, cfg, /)` single entrypoint; `SchemaOp`; `_RUNNER` table; `SchemaDetail` receipt | Collapse `apply`/`doctor` into `_apply_detail`/`_doctor_detail` fed by `_RUNNER: frozendict[SchemaOp, Callable[...]]`. The APPLY arm runs `(synonyms_cp, thesaurus_cp, atlas)` concurrently via `anyio.create_task_group` with results over `anyio.create_memory_object_stream[tuple[int,int]](max_buffer_size=3)` keyed by declaration-order step index, then `(routines, cron)` sequentially. Each subprocess step wrapped in `anyio.move_on_after` (docker cp 30s, atlas 120s, psql 60s). Lift bare `OSError` to `DbFault(op="process", ...)`. |
| `~` | `admin/rails/ledger.py` | `query(kind: Kind, cfg, /)` polymorphic ledger read; `Kind` vocabulary; `_SQL` table; `LedgerDetail` receipt | Replace `MappingProxyType` with `frozendict[Kind, str]` in a `[TABLES]` block. Surface missing-kind as `_SQL.get(kind)` -> `Nothing -> Error(DbFault(op="query", message=f"no SQL for {kind}"))`. |
| `~` | `admin/rails/sync.py` | `run(cfg, /, *, concept: str \| None = None)` modal-arity entrypoint; `SyncDetail` receipt; `_heptabase` boundary helper | Collapse `diff`/`generate` into private `_diff`/`_generate`; `concept is None` -> `_diff`, else `_generate(cfg, concept)`. Delete `SyncOp` (never existed in source; ensure not introduced). Materialize `_CARD_LIST_DECODER`/`_CARD_REF_DECODER` module-level `msgspec.json.Decoder` instances. `SyncDetail.card_total: int \| msgspec.UnsetType = msgspec.UNSET`; `card_id: str \| msgspec.UnsetType = msgspec.UNSET`. Optionally flatten `_diff`/`_generate` bind chains with `@effect.result`. No `expression.Option[str]` import. |
| `-` | `admin/rails/stack.py` | DELETE — one-hop `run` wrapper; `StackOp`/`StackDetail`/`_BUILD`/Pulumi dispatch move to `admin/infra/runner.py` | The CLI mounts `infra.run` directly. |
| `~` | `admin/rails/__init__.py` | `[EXPORTS]` — re-export exactly the CLI mount points under one semantic alias per rail | Re-export `query as ledger`, `Kind`; `run as schema`, `SchemaOp`; `run as stack`, `StackOp` (from `admin.infra.runner`); `run as sync`. Eliminate `schema_apply`/`schema_doctor`/`sync_diff`/`sync_generate`/old `stack` aliases. |
| `~` | `admin/__init__.py` | `beartype_this_package` claw — import-time runtime contract | No change; confirm present. |
| `~` | `admin/__main__.py` | one `App`; sub-`App` for `schema`; `@app.meta.default` launcher; `main()` | Add `App(config=[cyclopts.config.Env(prefix="MAGHZ_")])`. Replace manual `anyio.run` trampoline with `App.run_async(backend="asyncio")` (catalog-confirmed present). Bind `concept: Annotated[str, Parameter(min_count=1)]` on `generate`; project `cyclopts.UNSET -> None` at the boundary before calling `sync.run`. Add `structlog.contextvars.bind_contextvars(command=cmd_name)` at the meta dispatch point. Register `stamina.instrumentation.set_on_retry_hooks([StructlogOnRetryHook])` once at `main()` startup. Mount canonical rail names; `schema apply`/`schema doctor` map to `SchemaOp`. |

`db/`, `infra` (Pulumi program), and `.mcp.json` require no changes for this domain. `.mcp.json` is owned by the `mcp` domain; existing-rails does not touch it.

---

## [02]-[ADTS]

Closed unions; every `match` over each carries `case unreachable: assert_never(unreachable)`.

| [ADT] | [OWNER] | [KIND] | [CASES / FORM] | [DISCRIMINANT] |
| :---- | :------ | :----- | :------------- | :------------- |
| `StackOp` | `admin/infra/runner.py` | `StrEnum` | `UP="up"`, `DOWN="down"`, `STATUS="status"` | `op: StackOp` -> `_BUILD[op]` |
| `SchemaOp` | `admin/rails/schema.py` | `StrEnum` (new) | `APPLY="apply"`, `DOCTOR="doctor"` | `op: SchemaOp` -> `_RUNNER[op]` |
| `Kind` | `admin/rails/ledger.py` | `StrEnum` (existing) | `COVERAGE`, `GAPS`, `STALE`, `NEXT`, `OWNER` | `kind: Kind` -> `_SQL[kind]` |
| `Status` | `admin/core/status.py` | `StrEnum` (existing) | outcome cases; `_RANK_EXIT` correspondence | severity fold via `_RANK_EXIT[self][0]`, exit via `[1]` |
| `Boundary` | `admin/db.py` | `Literal` | `"connect"`, `"query"`, `"heptabase"`, `"process"` | `DbFault.op: Boundary` |
| `sync.run` modality | `admin/rails/sync.py` | input-shape discriminant (NO enum) | `concept is None` -> DIFF; `concept is not None` -> GENERATE | presence/absence of `concept: str \| None` |

`SyncOp` is NOT introduced — input shape carries full discrimination. `Boundary` is extended in place (not forked) when the `runtime` domain lands (adds `"ingest"`, `"embed"`, `"search"`).

---

## [03]-[API_MEMBERS]

Exact external members to compose, by owner file.

`admin/__main__.py` — `cyclopts.App`, `cyclopts.App.command`, `cyclopts.App.meta`, `cyclopts.App.run_async(backend="asyncio")`, `cyclopts.config.Env(prefix=...)`, `cyclopts.Parameter(show=, allow_leading_hyphen=, min_count=)`, `cyclopts.UNSET`, `cyclopts.CycloptsError`, `cyclopts` `result_action="return_value"`; `structlog.configure`, `structlog.processors.add_log_level`, `structlog.processors.TimeStamper`, `structlog.processors.JSONRenderer`, `structlog.dev.ConsoleRenderer`, `structlog.PrintLoggerFactory`, `structlog.make_filtering_bound_logger`, `structlog.contextvars.bind_contextvars`, `structlog.get_logger`; `stamina.instrumentation.set_on_retry_hooks`, `stamina.instrumentation.StructlogOnRetryHook`.

`admin/db.py` — `anyio.to_thread.run_sync(func, limiter=)`, `anyio.CapacityLimiter`, `anyio.to_thread.current_default_thread_limiter`; `pg8000.native.Connection`, `pg8000.native.Connection.run(sql, **params)`, `pg8000.Error`, `PostgresDsn.hosts()`; `stamina.retry(on=pg8000.Error, attempts=, wait_initial=, wait_max=, timeout=)`; `expression.Result`, `expression.Ok`, `expression.Error`; `msgspec.Struct(frozen=True, gc=False, tag=...)`.

`admin/infra/runner.py` — `pulumi.automation` (`auto.Stack`, `auto.UpResult`, `auto.DestroyResult`, `auto.PreviewResult`), the Automation API up/destroy/preview calls; `anyio.to_thread.run_sync`; `httpx.AsyncClient`, `httpx.Timeout(timeout, read=None)`, `httpx.ConnectError`, `httpx.RemoteProtocolError`; `stamina.retry(on=(httpx.ConnectError, httpx.RemoteProtocolError), ...)`; `msgspec.json.decode` (streaming `_Pull`); `frozendict` (`_BUILD`).

`admin/rails/schema.py` — `anyio.run_process(argv, check=False)`, `anyio.create_task_group`, `anyio.create_memory_object_stream[tuple[int,int]](max_buffer_size=3)`, `anyio.move_on_after(seconds)` + `scope.cancelled_caught`; `frozendict` (`_RUNNER`); `msgspec.Struct(tag="schema")`.

`admin/rails/ledger.py` — `db.query` (local), `frozendict[Kind, str]` (`_SQL`), `frozendict.get` -> `expression.Option` projection; `msgspec.Struct(tag="ledger")`.

`admin/rails/sync.py` — `anyio.run_process`; `msgspec.json.Decoder(type=_CardList)`, `msgspec.json.Decoder(type=_CardRef)`, `msgspec.UNSET`, `msgspec.UnsetType`, `msgspec.Struct(tag="sync")`; `expression.Result`, `expression.Ok`, `expression.Error`, `expression.effect.result`, `expression.Result.default_with`.

`admin/core/status.py` — `frozendict[Status, tuple[int,int]]` (`_RANK_EXIT`).

`admin/core/model.py` — `msgspec.json.Encoder()` (shared instance), `msgspec.Struct(frozen=True, gc=False, tag=True/tag=...)`, `msgspec.structs.replace` (reserved).

`admin/settings/config.py` — `pydantic_settings.BaseSettings(nested_model_default_partial_update=True, env_nested_delimiter=, env_ignore_empty=True)`, `pydantic.BaseModel(frozen=True, extra="forbid")`, `functools.lru_cache`.

---

## [04]-[DEPS]

| [PACKAGE] | [BAND] | [WHY] |
| :-------- | :----- | :---- |
| `frozendict` | `pure-venv` | Admit to `pyproject.toml`. The blueprint mandates `frozendict` for all four dispatch/correspondence tables (`_RANK_EXIT`, `_SQL`, `_BUILD`, `_RUNNER`) and the §09 acceptance gate forbids `MappingProxyType`. It is NOT in the manifest and the source currently uses `MappingProxyType`. Resolves the §06/§09 internal conflict in favor of §09 (the gate). Author a `frozendict` `.api` catalog note covering `frozendict[K,V]` construction, `.get` -> Option projection, hashability/immutability for static dispatch tables. Add as a `# data:` runtime dependency. |

No other packages. `anyio`, `cyclopts`, `msgspec`, `pydantic`, `pydantic-settings`, `expression`, `stamina`, `structlog`, `pg8000`, `httpx`, `keyring`, `sqlglot`, `pulumi`, `pulumi-docker`, `pulumi-docker-build`, `psutil` are all already admitted. `psutil` stays unused in existing-rails (reserved for `runtime`). All catalog members in §03 are verified against the Rasm `.api` catalogs; `cyclopts.App.run_async(backend=)` is catalog-confirmed present (`libs/python/runtime/.api/cyclopts.md`), so the manual `anyio.run` trampoline is replaced, not kept.

---

## [05]-[RIPPLES]

Cross-domain canonical shapes. Each names the counterpart domain.

| [DOMAINS] | [CLAIM] |
| :-------- | :------ |
| `existing-rails` -> `runtime` | `Envelope`/`Report`/`Detail`/`Row`/`Status` are the canonical one-line JSON result contract. existing-rails is producer; runtime's automation runner, watch loop, and remote `--exec` are consumers. Shape must not change across the seam. |
| `existing-rails` -> `runtime` | `MaghzSettings` from `settings()` is the single configuration surface threaded into every rail; runtime's scheduler/daemon/watch read the same `DatabaseConfig.dsn`/`OllamaConfig`/`InfraConfig` facts. |
| `existing-rails` -> `runtime` | `Result[T, DbFault]` + `Boundary` literal are the pre-`runtime` interior rail. runtime lifts `db.query` to `RuntimeRail[QueryResult] = Result[QueryResult, BoundaryFault]` via an `async_boundary("query", ...)` wrapper; `DbFault.envelope()` stays as the CLI projection; `Boundary` is extended in place (`"ingest"`/`"embed"`/`"search"`), never forked. |
| `existing-rails` -> `runtime` | `StackOp.UP/DOWN/STATUS` + `infra.run(op, cfg)` are the lifecycle verbs runtime's automation `stack` command and VPS bootstrap import without re-implementing Pulumi dispatch. |
| `existing-rails` -> `runtime` | `Kind` ledger vocabulary (`COVERAGE`/`GAPS`/`STALE`/`NEXT`/`OWNER`) drives runtime's scheduled work-selection; runtime extends by adding `Kind` cases to this owner, never a parallel ledger query. |
| `existing-rails` -> `runtime`, `automation` | `sync.run(cfg, /, *, concept: str \| None = None)` + `_heptabase` + `SyncDetail.card_id` are consumed by runtime's watch loop and the automation `Sync` action. Binding contract: `sync_run(cfg, concept=None)` -> DIFF, `sync_run(cfg, concept=spec.concept)` -> GENERATE. Canonical import `from admin.rails.sync import run as sync_run`; `rails.sync_diff`/`rails.sync_generate` aliases do not exist post-realize. |
| `existing-rails` -> `runtime` | The `app` `App` in `admin/__main__.py` is the root mount point; runtime's automation/watch/schedule and remote `--exec` sub-apps register via `app.command(subapp)`. No parallel `App`. |
| `existing-rails` -> `runtime` | `_DB_LIMITER = anyio.CapacityLimiter(8)` is a pre-`runtime` bootstrap; runtime's `LanePolicy` owns `CapacityLimiter` lifecycle and `db.py` borrows the policy-managed limiter in place. One limiter owner, never two. |
| `existing-rails` -> `runtime` | The two `@stamina.retry` decorators (`_run_blocking` DB, `_pull_embed_model` HTTP) are bootstraps superseded in place by `guard(RetryClass.DB)`/`guard(RetryClass.HTTP)` from `admin/runtime/resilience.py`. Bootstrap retry params MUST match `POLICY[RetryClass.DB]`/`POLICY[RetryClass.HTTP]` to avoid a transition-boundary behavioral diff. No local `retry_boundary` aspect factory at any stage. |

---

## [06]-[DEPENDS_ON]

No other domain owner must be realized before existing-rails. existing-rails is the pre-runtime bootstrap and is itself the foundation the other domains depend on. The `runtime` domain (`docs/design/runtime.md`) is a planned SUCCESSOR, not a prerequisite: existing-rails boots a minimal resilience/concurrency posture directly (`_DB_LIMITER`, two `@stamina.retry` sites, inline `move_on_after`) that runtime later supersedes in place. Realize existing-rails first; `runtime`, `automation`, `remote`, `cloud-sync`, `mcp`, `integrations`, `n8n` consume its seams.

---

## [07]-[ACCEPTANCE]

Static (zero-exit): `ruff check admin/` (`select=["ALL"]`), `ruff format --check admin/`, `ty check admin/` (`all="error"`), `mypy admin/` (strict + pydantic plugin).

Structural:
- Every `match` over `StackOp`/`SchemaOp`/`Kind`/`Status` carries `case unreachable: assert_never(unreachable)`.
- `admin/rails/sync.py` exposes one `run(cfg, /, *, concept: str | None = None)`; `_diff`/`_generate` private; no `SyncOp`; no `expression.Option[str]` import.
- `admin/rails/schema.py` exposes one `run(op: SchemaOp, cfg, /)`.
- `admin/infra/runner.py` exposes one `run(op: StackOp, cfg, /)`; `admin/rails/stack.py` is deleted.
- `admin/rails/__init__.py` re-exports `run as schema`, `run as stack`, `run as sync`, `query as ledger` — one alias per rail; no `schema_apply`/`schema_doctor`/`sync_diff`/`sync_generate`.
- All four tables (`_RANK_EXIT`, `_SQL`, `_BUILD`, `_RUNNER`) use `frozendict`; no `MappingProxyType`; no `expression.Map`.
- All `msgspec.Struct` subclasses (incl. `DbFault`) carry `gc=False`.
- `anyio.create_task_group` + `anyio.create_memory_object_stream[tuple[int,int]](max_buffer_size=3)` (step-index keys) in `schema.run(APPLY)`; `anyio.move_on_after` (NOT `fail_after`) for deadlines.
- `_DB_LIMITER = anyio.CapacityLimiter(8)` module-level in `admin/db.py`; `limiter=_DB_LIMITER` on every `to_thread.run_sync`.
- `stamina.retry` decorates `_run_blocking` and `_pull_embed_model` directly; no local aspect factory.
- No `asyncio` import anywhere in `admin/` (ruff banned-api enforces).
- `App.run_async(backend="asyncio")` replaces the manual trampoline; `App(config=[cyclopts.config.Env(prefix="MAGHZ_")])`; `concept` bound `Annotated[str, Parameter(min_count=1)]`; CLI projects `UNSET -> None` before `sync.run`.

Runtime verbs (local dev):
- `maghz up` -> `Envelope(status="ok", report=Report(detail=StackDetail(op="up", ...)))`.
- `maghz down` -> same with `op="down"`.
- `maghz status` -> `StackDetail(op="status", result="preview", ...)`.
- `maghz schema apply` -> `SchemaDetail(op="apply", exits=(0,0,0,0,0))` on full success.
- `maghz schema doctor` -> rows of extension names.
- `maghz ledger coverage` -> `LedgerDetail(kind="coverage", count=N)`.
- `maghz sync diff` -> `SyncDetail(op="diff", drift=N, card_total=M)`.
- `maghz sync generate <concept>` -> `SyncDetail(op="generate", card_id="<uuid>")`.

Receipts:
- `SchemaDetail.exits` is exactly 5 elements in declaration order `(synonyms_cp, thesaurus_cp, atlas, routines, cron)`; a tripped `move_on_after` records a non-zero sentinel for that step, length stays 5.
- `StackDetail.resource_changes` is `Mapping[str, int]` keyed by Pulumi op names.
- `SyncDetail.card_total` is `int | msgspec.UnsetType` (`UNSET` when diff did not reach the census step); `card_id` is `str | msgspec.UnsetType` (present only on GENERATE success).
- `Envelope.code` projects to exit code via `Status._RANK_EXIT` (0 for `OK`/`SKIP`/`EMPTY`, non-zero for `FAILED`/`FAULTED`).
