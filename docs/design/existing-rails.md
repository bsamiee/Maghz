# [DESIGN_EXISTING_RAILS]

Decision-complete design note for the existing-rails refactor domain. This is working material — not a durable API contract. The schema, the `maghz` CLI, and `admin/` source carry the binding truth after realize.

---

## [01]-[OWNERS]

One module, one concept. No parallel families.

| [MODULE] | [SECTION] | [CANONICAL_CONCEPT_OWNED] |
| :------- | :-------- | :------------------------ |
| `admin/settings/config.py` | `[MODELS]` + `[COMPOSITION]` | `MaghzSettings` — the single `BaseSettings` owner; `DatabaseConfig`, `OllamaConfig`, `InfraConfig`, `ObservabilityConfig` as frozen sub-models; one `settings()` lru_cache factory |
| `admin/core/status.py` | `[TYPES]` + `[CONSTANTS]` | `Status` — closed `StrEnum` with `_RANK_EXIT` correspondence table driving `code`/`worst`/`fold` |
| `admin/core/model.py` | `[MODELS]` + `[OPERATIONS]` | `Envelope` / `Detail` / `Report` / `Row` — the one JSON result contract; `completed` and `fault` constructors |
| `admin/db.py` | `[TYPES]` + `[MODELS]` + `[ERRORS]` + `[OPERATIONS]` | `query` — the single pg8000 boundary; `DbFault` (tagged by `Boundary`); `QueryResult`; `Scalar` type alias |
| `admin/infra/stack.py` | `[OPERATIONS]` | `define` — the Pulumi desired-state program; no public types |
| `admin/infra/runner.py` | `[OPERATIONS]` | `run` — single polymorphic Automation API entrypoint over `StackOp`; `_BUILD` dispatch table |
| `admin/rails/schema.py` | `[CONSTANTS]` + `[MODELS]` + `[OPERATIONS]` | `run` — one entrypoint over `SchemaOp`; `SchemaDetail` receipt |
| `admin/rails/ledger.py` | `[TYPES]` + `[MODELS]` + `[TABLES]` + `[OPERATIONS]` | `query` — one polymorphic ledger read; `Kind` vocabulary; `_SQL` correspondence table; `LedgerDetail` receipt |
| `admin/rails/sync.py` | `[MODELS]` + `[OPERATIONS]` | `run` — one polymorphic sync verb discriminating on `concept: str \| None`; `SyncDetail` receipt; `_heptabase` boundary helper |
| `admin/rails/__init__.py` | `[EXPORTS]` | re-exports exactly the public entrypoints the CLI mounts |
| `admin/__init__.py` | `[RUNTIME_PRELUDE]` | `beartype_this_package` claw — import-time runtime contract enforcement |
| `admin/__main__.py` | `[SERVICES]` + `[COMPOSITION]` + `[ENTRY]` | one `App`; sub-`App` for `schema`; `@app.meta.default` launcher; `main()` |

**Route conflicts detected in existing source requiring collapse:**

- `admin/rails/sync.py` exposes two top-level functions `diff` and `generate` — collapse into one `run(cfg, /, *, concept: str | None = None)` entrypoint where `concept is None` selects DIFF semantics and `concept is not None` selects GENERATE (COLLAPSE_SCAN [01]: sibling names, shared `_heptabase` preamble, same `Envelope` return rail). `SyncOp` is eliminated — the presence/absence of `concept` is the discriminant, making the explicit op vocabulary redundant.
- `admin/infra/runner.py` exposes three separate async functions `up`/`down`/`status` — collapse into one `run(op: StackOp, ...)` entrypoint; `admin/rails/stack.py` is deleted; its `run` wrapper was a one-hop violation (COLLAPSE_SCAN [06]).
- `admin/rails/schema.py` exposes `apply`/`doctor` — two arms of one `SchemaOp` discriminant; collapse into `run(op: SchemaOp, ...)`.
- `admin/rails/__init__.py` re-exports renamed surfaces (`query as ledger`, `apply as schema_apply`, `doctor as schema_doctor`, `run as stack`, `diff as sync_diff`, `generate as sync_generate`) — alias hops are one-hop violations (COLLAPSE_SCAN [06]); the CLI mounts canonical names directly after collapse.

**Temporal boundary — pre-runtime bootstrap:**

The `admin/runtime/` package (designed in `docs/design/runtime.md`) does not yet exist. The existing-rails realize pass boots a minimal resilience and concurrency posture directly in `admin/db.py` and `admin/rails/`. When the `runtime` domain lands, these bootstraps are replaced in place by the runtime owners without changing public entrypoints. The seam details are in `[07]-[SEAMS]`.

---

## [02]-[ADTS]

Every bounded verb family is one closed `StrEnum` discriminant under one total `match`/`assert_never`.

### `StackOp` (existing — promote to infra boundary)

```python
class StackOp(StrEnum):
    UP = "up"
    DOWN = "down"
    STATUS = "status"
```

Owner: `admin/infra/runner.py` (not `admin/rails/stack.py` — the infra module owns the Pulumi dispatch).

```python
# [TABLES] — in admin/infra/runner.py
_BUILD: frozendict[StackOp, Callable[[MaghzSettings], Awaitable[StackDetail]]] = frozendict({
    StackOp.UP: _up_detail,
    StackOp.DOWN: _down_detail,
    StackOp.STATUS: _status_detail,
})

async def run(op: StackOp, cfg: MaghzSettings, /) -> Envelope:
    match op:
        case StackOp.UP | StackOp.DOWN | StackOp.STATUS:
            detail = await _BUILD[op](cfg)
            return completed(detail)
        case unreachable:
            assert_never(unreachable)
```

`admin/rails/stack.py` is deleted; its `run` becomes `infra.run` directly.

### `SchemaOp` (new — collapses `apply`/`doctor`)

```python
class SchemaOp(StrEnum):
    APPLY = "apply"
    DOCTOR = "doctor"
```

Owner: `admin/rails/schema.py`.

```python
# [TABLES] — in admin/rails/schema.py
_RUNNER: frozendict[SchemaOp, Callable[[MaghzSettings], Awaitable[SchemaDetail]]] = frozendict({
    SchemaOp.APPLY: _apply_detail,
    SchemaOp.DOCTOR: _doctor_detail,
})

async def run(op: SchemaOp, cfg: MaghzSettings, /) -> Envelope:
    match op:
        case SchemaOp.APPLY | SchemaOp.DOCTOR:
            detail = await _RUNNER[op](cfg)
            return completed(detail)
        case unreachable:
            assert_never(unreachable)
```

### `sync.run` modal-arity entrypoint (replaces `SyncOp`)

`SyncOp` is eliminated. The presence of `concept: str` fully determines the branch — an explicit op discriminant is redundant when input shape already carries the full discrimination. The one polymorphic entrypoint:

```python
async def run(cfg: MaghzSettings, /, *, concept: str | None = None) -> Envelope:
    if concept is None:
        return await _diff(cfg)
    return await _generate(cfg, concept)
```

`concept is None` → DIFF; `concept is not None` → GENERATE. The CLI positional for `generate` passes the raw `str` argument directly; `sync diff` passes no concept argument. No `SyncOp`, no `Option[str]` in the domain signature. `beartype_this_package` enforces `concept: str | None` — no cross-parameter invariant that beartype cannot check is required. The automation `Sync` action in `automation.md` sets `concept` to `None` for DIFF and a non-None `str` for GENERATE.

### `Kind` (existing — no change)

Five-case `StrEnum` (`COVERAGE`, `GAPS`, `STALE`, `NEXT`, `OWNER`) in `admin/rails/ledger.py`.

Modal-arity entrypoint: `query(kind: Kind, cfg: MaghzSettings, /) -> Envelope` — already correct.

### `Boundary` (existing — in-place extension protocol)

```python
type Boundary = Literal["connect", "query", "heptabase", "process"]
```

Owner: `admin/db.py`. This literal is the closed fault vocabulary for the pre-`runtime` bootstrap. When the `runtime` domain lands, `admin/db.py` is edited in place to extend it:

```python
# after runtime domain lands — edit in place, no new owner
type Boundary = Literal["connect", "query", "heptabase", "process", "ingest", "embed", "search"]
```

The `runtime` domain does NOT own a parallel `Boundary` type. Python `Literal` aliases are extended by redefining them in the owning module. Every consumer of `Boundary` that uses total `match` + `assert_never` will break loudly at type-check time when new cases are added — which is the correct anticipatory signal.

---

## [03]-[.api SURFACE]

### `cyclopts` — `admin/__main__.py`

Current surface uses: `App`, `App.command`, `App.meta.default`, `Parameter`, `CycloptsError`, `app.parse_args`, `anyio.run` (manual). Valid, but can deepen:

**Gaps vs full catalog (`libs/python/runtime/.api/cyclopts.md`):**

- The meta dispatcher pattern in cyclopts: the `@app.meta.default` function receives the command coroutine and calls `anyio.run(coro, backend='asyncio')` explicitly. Before assuming `App.run_async` exists, the implement pass must verify its presence in the admitted `cyclopts` version via the `.api` catalog before replacing the manual `anyio.run` trampoline. If `App.run_async(backend=)` is confirmed present, replace the manual trampoline; if absent, the manual `anyio.run` in `_launch` is correct and kept as-is.
- The `generate` subcommand's `concept: str` parameter needs a non-empty guarantee; bind `Annotated[str, Parameter(min_count=1)]`.
- `config.Env(prefix="MAGHZ_")` is the missing config source layer: the settings model already reads `MAGHZ_` env vars via pydantic-settings, but the CLI does not thread `config.Env` so `--log-level` and `--log-format` cannot be overridden from env at dispatch time. Add `App(config=[config.Env(prefix="MAGHZ_")])`.
- `cyclopts.UNSET` is used to represent the absent-vs-None distinction for `concept` at the CLI boundary; the CLI adapter projects `UNSET -> None` and a present string directly to `concept: str | None` before calling `sync.run`. With `SyncOp` eliminated, no `Option[str]` conversion is needed — the projection is `UNSET -> None`, string value -> the string.
- `ResultAction` / `result_action="return_value"` is already used in `main()`. Keep; this is correct.

**Members composed:**
- `App(name, help, config=[config.Env(...)])` — `cyclopts.App`, `cyclopts.config.Env`
- `@app.command(name=...)` — `App.command`
- `@app.meta.default` — `App.meta`
- `app.meta(result_action="return_value", exit_on_error=False)` — `ResultAction` string literal
- `UNSET` — absent optional marker at CLI boundary; projected to `None` before domain entry
- `Parameter(show=False, allow_leading_hyphen=True)` / `Parameter(min_count=1)` — `cyclopts.Parameter`

### `anyio` — `admin/db.py`, `admin/rails/schema.py`, `admin/rails/sync.py`

Current surface uses `anyio.to_thread.run_sync`, `anyio.run_process`. Full catalog gaps:

- `anyio.to_thread.run_sync(func, limiter=...)` — the pg8000 offload in `admin/db.py` uses `run_sync` without an explicit `CapacityLimiter`. Add one module-level `_DB_LIMITER: CapacityLimiter = anyio.CapacityLimiter(8)` in `admin/db.py` as a pre-`runtime` bootstrap. This limiter is a TEMPORARY owner: when the `runtime` domain lands and `LanePolicy` owns `CapacityLimiter` lifecycle, `db.py` will be edited to borrow the policy-managed limiter instead. Until then, the 8-token module-level bootstrap is the correct bounded subsystem posture.
- `anyio.run_process(argv, check=False)` — already used in schema/sync correctly. No gaps.
- `anyio.create_task_group()` — used in `schema.run(SchemaOp.APPLY)` for the concurrent phase. The task group runs `[synonyms_cp, thesaurus_cp, atlas]` concurrently; `[routines, cron]` run sequentially after. Results are collected via `anyio.create_memory_object_stream[tuple[int, int]](max_buffer_size=3)` where each tuple is `(step_index, exit_code)`. After the task group exits, the receive stream is drained in `range(3)` order to reconstruct the deterministic `exits` tuple for `SchemaDetail`. `step_index` is the declaration-order index (0=synonyms_cp, 1=thesaurus_cp, 2=atlas) so ordering is preserved regardless of task completion order.
- `anyio.move_on_after(timeout)` — not `fail_after`. Per the `runtime.md` concurrency law, deadline scopes inside domain code use `move_on_after` (silently cancel with `scope.cancelled_caught`) rather than `fail_after` (raises `TimeoutError`). Each subprocess step inside `schema.run(SchemaOp.APPLY)` is wrapped with `async with anyio.move_on_after(seconds) as scope:` followed by `if scope.cancelled_caught: ...` to record a timeout exit code. Deadlines: `docker cp` — 30s, `atlas` — 120s, `psql` steps — 60s each. The pre-`runtime` bootstrap implements this directly; `@deadline_bound` using `fail_after` is rejected.

**Members composed:** `anyio.to_thread.run_sync` (with explicit `CapacityLimiter`), `anyio.run_process`, `anyio.create_task_group`, `anyio.move_on_after`, `anyio.create_memory_object_stream`, `anyio.CapacityLimiter`, `anyio.to_thread.current_default_thread_limiter`.

### `expression` — `admin/db.py`, `admin/rails/ledger.py`, `admin/rails/sync.py`

Current surface uses `Result`, `Ok`, `Error` with structural pattern matching. Full catalog gaps:

- `effect.result` builder — `admin/rails/sync.py`'s nested `match` chains in `_diff` and `_generate` have sequential bind steps that are readable but hand-rolled. The `@effect.result` builder flattens them to linear `yield from db.query(...)` / `yield from _heptabase(...)` chains.
- `pipe` / `compose` — not triggered; no three+ sequential transforms on one value.
- `Result.map_error` — not used; `dbfault.envelope(...)` is already the projection. No gap.

**Members composed:** `Result`, `Ok`, `Error`, `effect.result`, `Result.default_with`.

### `stamina` — pre-`runtime` bootstrap, no local aspect factory

Zero `@retry` decorators exist on any boundary call. The three transient-failure surfaces:

1. `db.query` / `_connect` — `pg8000.Error` on transient connection loss is retryable; the current rail surfaces every error as a `DbFault` immediately.
2. `_pull_embed_model` (httpx) — `httpx.ConnectError`/`httpx.RemoteProtocolError` on the Ollama container being briefly unavailable post-`up`.
3. `_heptabase` (sync `_diff`/`_generate`) — `OSError` on `heptabase` CLI spawn failure; not retried (CLI spawn failure is structural, not transient).

The pre-`runtime` bootstrap applies `stamina.retry` directly as a decorator on `_run_blocking` (DB) and `_pull_embed_model` (httpx):

```python
# admin/db.py — pre-runtime bootstrap; replaced by guard(RetryClass.DB) when runtime lands
@stamina.retry(on=pg8000.Error, attempts=3, wait_initial=0.5, wait_max=5.0, timeout=30.0)
def _run_blocking(...): ...

# admin/infra/runner.py — pre-runtime bootstrap; replaced by guard(RetryClass.HTTP) when runtime lands
@stamina.retry(on=(httpx.ConnectError, httpx.RemoteProtocolError), attempts=5, wait_initial=1.0, wait_max=10.0, timeout=60.0)
async def _pull_embed_model(...): ...
```

A local `retry_boundary` aspect factory is NOT designed — that would seed a parallel retry surface that the `runtime` domain would have to delete. `stamina.retry` is applied directly at these two sites. When the `runtime` domain lands, these two decorators are replaced with `guard(RetryClass.DB).on(target)` and `guard(RetryClass.HTTP).on(target)` from `admin/runtime/resilience.py`; that is a targeted in-place edit, not a proliferation.

`stamina.instrumentation.StructlogOnRetryHook` registered once at `main()` startup alongside `_observe` so retry events land on the structlog pipeline.

**Members composed:** `stamina.retry` (decorator, two sites), `stamina.instrumentation.set_on_retry_hooks`, `stamina.instrumentation.StructlogOnRetryHook`.

### `msgspec` — `admin/core/model.py`, `admin/rails/stack.py`, `admin/rails/sync.py`

Current surface: `Struct(frozen=True, gc=False)`, `msgspec.json.encode`, `msgspec.json.decode`, `msgspec.Struct` subclasses with `tag=True`/`tag="..."`.

Gaps:
- `msgspec.json.Decoder(type=T)` — `admin/rails/sync.py` uses `msgspec.json.decode(run.stdout, type=into)` as a one-shot call per invocation. A module-level `Decoder` instance eliminates the type-resolution overhead on repeated calls. Materialize `_CARD_LIST_DECODER = msgspec.json.Decoder(type=_CardList)` and `_CARD_REF_DECODER = msgspec.json.Decoder(type=_CardRef)`.
- `msgspec.UNSET` / `msgspec.UnsetType` — `SyncDetail.card_id` and `SyncDetail.card_total` use `int | None` and `str | None`. For agent-facing wire shapes, `card_id: str | msgspec.UnsetType = msgspec.UNSET` makes explicit absence distinct from `null`. Adopt for both fields: `card_total: int | msgspec.UnsetType = msgspec.UNSET` and `card_id: str | msgspec.UnsetType = msgspec.UNSET`.
- `msgspec.structs.replace` — not currently used; relevant when partial updates to frozen structs are needed in future automation consumers.

**Members composed:** `Struct(frozen=True, gc=False)`, `Struct(frozen=True, tag=True/tag="...")`, `json.Encoder()` (shared instance in `Envelope.encode`), `json.Decoder(type=T)` (module-level instances), `UNSET`/`UnsetType` for explicit absence.

### `pydantic` / `pydantic-settings` — `admin/settings/config.py`

Current surface is at full advanced depth: `BaseSettings(nested_model_default_partial_update=True)`, `env_nested_delimiter`, `env_ignore_empty`, `frozen=True`, `extra="forbid"`. No gaps.

`nested_model_default_partial_update=True` lands on pydantic-settings 2.14.x; confirm against the lockfile version before realize.

### `structlog` — `admin/__main__.py`

Current surface uses `structlog.configure` with `add_log_level`, `TimeStamper`, `JSONRenderer`/`ConsoleRenderer`. Gap:

- `structlog.contextvars.bind_contextvars(command=cmd_name)` — not used. Add at the `@app.meta.default` dispatch point so every log event carries the command name. `contextvars` propagates across `anyio` task boundaries.
- `structlog.stdlib.add_logger_name` — already omitted from the pipeline (correct; logger names are meaningless with `beartype_this_package`).

**Members composed:** `structlog.configure`, `structlog.processors.add_log_level`, `structlog.processors.TimeStamper`, `structlog.processors.JSONRenderer`, `structlog.dev.ConsoleRenderer`, `structlog.PrintLoggerFactory`, `structlog.make_filtering_bound_logger`, `structlog.contextvars.bind_contextvars`, `structlog.get_logger`.

### `pg8000` — `admin/db.py`

Current `_connect` hand-extracts host/port from `PostgresDsn.hosts()[0]` because pg8000 has no DSN-string parser. This is the correct path; no native DSN admission surface exists in pg8000.

`pg8000.native.Connection.run(sql, **params)` — named-parameter binding already used correctly.

Gap: `pg8000.native.Connection` has no `autocommit` property toggle; `run` executes in autocommit by default. Multi-statement transactions require `BEGIN`/`COMMIT` emitted as statements. No current rail uses transactions; note this for the ingestion domain.

### `httpx` — `admin/rails/stack.py`

Current `_pull_embed_model` uses `httpx.AsyncClient` with streaming. Surface is correct; gaps:

- `httpx.Timeout(cfg.ollama.request_timeout, read=None)` — already used; `read=None` is the correct infinite-read-timeout for a streaming pull. No gap.
- `stamina.retry` wrapper for `ConnectError`/`RemoteProtocolError` — missing (see §03 stamina above).

---

## [04]-[RAILS + ASPECTS]

### Result rail

`Result[T, DbFault]` is the interior rail for the pre-`runtime` bootstrap. `db.query` returns `Result[QueryResult, DbFault]`; each rail collapses it to `Envelope` at its boundary. `DbFault.envelope()` is the projection.

**Temporal lift:** when `admin/runtime/` lands, `db.query` returns `RuntimeRail[QueryResult] = Result[QueryResult, BoundaryFault]` for domain-internal consumers. CLI command handlers in `admin/__main__.py` project through `DbFault.envelope()` (or a runtime-domain helper) to `Envelope`. The two surfaces — `DbFault` as the CLI projection helper and `BoundaryFault` as the interior rail — are kept distinct and never collapsed. This seam is named in `[07]-[SEAMS]`.

`_heptabase` in `sync.py` reuses `DbFault` as the heptabase-boundary rail — correct (`Boundary = Literal["connect", "query", "heptabase", "process"]`). The `"process"` arm covers `OSError` from `anyio.run_process` in the schema rail (currently bare `OSError` in a naked `except`; lift to `DbFault(op="process", message=str(exc)).envelope(...)`).

### CLOSED fault vocabulary

```python
type Boundary = Literal["connect", "query", "heptabase", "process"]
```

`DbFault.op: Boundary` is the fault vocabulary. `Status` is the outcome vocabulary. These are the only two fault axes in the pre-`runtime` bootstrap; no bare `str` failures escape the interior.

Entrypoint fault boundary catches `ValidationError` (settings), `CycloptsError` (CLI), and `Exception` (process escape) — all collapse to `fault(str(exc), {...})`. No new fault type needed.

### anyio structured-concurrency boundary

The `@app.meta.default` launcher in `__main__.py` is the sole event-loop owner (via the manual `anyio.run` trampoline, or `App.run_async` if verified present in the admitted cyclopts version). Every concurrent section uses `anyio.create_task_group`:

- `schema.run(SchemaOp.APPLY)` — task group for the concurrent (`synonyms_cp`, `thesaurus_cp`, `atlas`) phase, then sequential (`routines`, `cron`). Results flow back through `anyio.create_memory_object_stream[tuple[int, int]](max_buffer_size=3)` keyed by step index to reconstruct the deterministic `SchemaDetail.exits` tuple in declaration order (not completion order). Each step is deadline-bounded with `anyio.move_on_after(seconds)` — NOT `fail_after`; a tripped deadline sets `scope.cancelled_caught` and records a sentinel exit code for that step.
- `infra.run(StackOp.UP)` — existing sequential flow: `infra.up(cfg)` then `_pull_embed_model(cfg)`; no concurrent promotion needed (Ollama must be running before pull).
- `db.query` — thread offload via `anyio.to_thread.run_sync` with explicit `_DB_LIMITER`.

Never `asyncio.gather`, never `asyncio.TaskGroup`, never `asyncio.create_task`.

### `@aspect` stacking

One recurring cross-cutting pattern applies in the pre-`runtime` bootstrap. No local aspect factory is introduced; applying `stamina.retry` directly at two sites does not meet the COLLAPSE_SCAN [12] threshold of three+ co-occurring applications.

No `@deadline_bound` using `fail_after` — deadline scopes are inline `anyio.move_on_after` context managers at each subprocess step in `schema.run(SchemaOp.APPLY)`. This is correct because the deadline scope body is four lines (enter CM, call subprocess, check `scope.cancelled_caught`, record result) and occurs only inside one function — extracting it to an aspect would create a single-caller private helper violation.

No `@aspect` for observability (structlog is configured once globally; per-call binding uses `structlog.contextvars.bind_contextvars` at the meta dispatcher, not a decorator).

When the `runtime` domain lands, `@receipted` and `@drained` from `admin/runtime/receipts.py` replace the inline structlog calls; that is an in-place substitution, not a proliferation.

### Cancellation policy

`anyio.move_on_after` is the deadline primitive at every external subprocess call. `db.query` timeout comes from `pg8000`'s `timeout` connection parameter (blocking driver; `run_sync` is cancellable via `abandon_on_cancel=True` if the connection is abandoned on cancel — note: verify the pg8000 native API supports this; otherwise the 30s `stamina` timeout is the sole bound).

---

## [05]-[PAYLOADS + TABLES]

### Wire structs (`msgspec.Struct(frozen=True, gc=False)`)

All egress and internal boundary shapes. Every struct is `gc=False` because none holds cyclic references — this applies to `DbFault` as well; the "may be GC-traced through closures" rationale is not a cycle and does not exempt from `gc=False`:

- `Envelope(status, report, error, error_context)` — the one stdout result; `gc=False`, `frozen=True`.
- `Report(detail, rows, artifacts, notes)` — the evidence carrier; `gc=False`, `frozen=True`.
- `Row(key, text)` — one bounded result row; `gc=False`, `frozen=True`.
- `Detail` base — `frozen=True, tag=True`; subclasses carry `tag="ledger"|"schema"|"stack"|"sync"`.
- `LedgerDetail(kind, count)` — ledger receipt; `tag="ledger"`, `gc=False`.
- `SchemaDetail(op, exits)` — schema receipt; `tag="schema"`, `gc=False`. `exits: tuple[int, ...]` with exactly 5 elements in declaration order: `(synonyms_cp, thesaurus_cp, atlas, routines, cron)`.
- `StackDetail(op, result, resource_changes, model_pulled)` — stack receipt; `tag="stack"`, `gc=False`.
- `SyncDetail(op, drift, card_total, card_id)` — sync receipt; `tag="sync"`, `gc=False`. `card_total: int | msgspec.UnsetType = msgspec.UNSET`, `card_id: str | msgspec.UnsetType = msgspec.UNSET`. `op: str` encodes `"diff"` or `"generate"` — derived from `concept is None` at construction time.
- `_Pull(status, error)` — internal streaming frame; `gc=False`, `frozen=True`.
- `_CardList(total)` — internal heptabase boundary; `gc=False`, `frozen=True`.
- `_CardRef(id, title)` — internal heptabase boundary; `gc=False`, `frozen=True`.
- `QueryResult(columns, rows)` — DB boundary receipt; `gc=False`, `frozen=True`.
- `DbFault(op, message)` — boundary error carrier; `frozen=True`, `gc=False` (two `str` fields, no cycles; the closure concern does not create a reference cycle in the struct).

### Validated ingress (`pydantic.BaseModel`)

- `DatabaseConfig`, `OllamaConfig`, `InfraConfig`, `ObservabilityConfig` — sub-models of `MaghzSettings`; `frozen=True, extra="forbid"`.
- `MaghzSettings(BaseSettings)` — single settings owner; `frozen=True, extra="forbid", env_ignore_empty=True, nested_model_default_partial_update=True`.

No `UNSET`/`Raw` on pydantic side (settings have defaults; no partial-update wire path on ingress).

### `frozendict` correspondence tables

All static definition-time dispatch and correspondence tables use `frozendict` per the OWNER_CHOOSER: `frozendict` for immutable map rows, `Map` for persistent keyed updates. Dispatch tables are static — `frozendict` is the correct owner for all four:

- `_RANK_EXIT: frozendict[Status, tuple[int, int]]` — in `admin/core/status.py`. The two projections (`code`, severity fold) derive from this single table. `frozendict` replaces any current `MappingProxyType` (which is a rejected form per TABLE_DISPATCH law: "MappingProxyType over mutable storage" is in the reject list). Missing-key is structurally impossible here since the key set equals `Status` exactly and the table is constructed with every member.
- `_SQL: frozendict[Kind, str]` — in `admin/rails/ledger.py`. `frozendict` replaces `MappingProxyType`. Missing-kind is surfaced as `Option[str]` via `_SQL.get(kind)` projected to `Nothing -> Error(DbFault(op="query", message=f"no SQL for {kind}"))` at the lookup site.
- `_BUILD: frozendict[StackOp, Callable[...]]` — in `admin/infra/runner.py` (after collapse). `frozendict`.
- `_RUNNER: frozendict[SchemaOp, Callable[...]]` — in `admin/rails/schema.py` (new, after collapse). `frozendict`.

`expression.Map` is not used for dispatch tables. It is the correct owner only for maps that accumulate persistent updates across operations; none of these four tables do.

No shared mutable state. No registries. No module-level mutable dicts.

### Typed receipts

Every rail emits exactly one typed `Detail` subclass. The receipt carries which verb ran, which projection/kind/op, the primary count or resource state, and any auxiliary evidence (exit codes, drift counts, card IDs). No receipt is replaced with a generic `IReceipt`; no field is `Any`.

---

## [06]-[DEPS]

### Existing (no change to admission)

`anyio`, `beartype`, `cyclopts`, `msgspec`, `pydantic`, `pydantic-settings`, `expression`, `stamina`, `structlog`, `pg8000`, `httpx`, `keyring`, `sqlglot`, `pulumi`, `pulumi-docker`, `pulumi-docker-build` — all in `pyproject.toml`.

### No new packages to admit

The full house-pattern bar is achieved by deeper composition of already-admitted packages. No new runtime dependency is required for the existing-rails domain.

`psutil` is admitted but unused by `admin/` currently. Reserve for the `runtime` domain's watch/daemon surfaces; do not introduce it into existing rails unless a receipt field requires it.

### `.api` catalog note

All catalog members composed in §03 are verified against the Rasm `.api` catalogs already present. No new `.api` catalog authoring is required for this domain.

**Cyclopts `App.run_async` verification:** the implement pass must check whether `App.run_async(backend=)` is present in the admitted `cyclopts` version by inspecting `libs/python/runtime/.api/cyclopts.md` or running `uv run python -c "import cyclopts; print(dir(cyclopts.App))"`. If absent, the manual `anyio.run(coro, backend='asyncio')` trampoline in `@app.meta.default` is kept unchanged.

---

## [07]-[SEAMS]

Cross-domain canonical shapes and receipts this domain shares or produces.

**Seam 1 — Envelope contract (existing-rails ↔ runtime)**

The `Envelope` / `Report` / `Detail` / `Row` / `Status` shapes are the canonical one-line JSON result contract that the runtime domain's automation runner, watch loop, and remote `--exec` verb will parse. The runtime domain is the consumer; existing-rails is the producer. The receipt shape must not change between the two domains.

**Seam 2 — `MaghzSettings` (existing-rails ↔ runtime)**

`MaghzSettings` threads from the existing-rails `settings()` factory into every rail and is the configuration surface the runtime domain's scheduler/daemon/watch modes will also read. The `DatabaseConfig.dsn`, `OllamaConfig`, and `InfraConfig` fields are shared facts.

**Seam 3 — `DbFault` / `Boundary` rail lift (existing-rails ↔ runtime)**

The typed `Result[T, DbFault]` rail and `Boundary` literal are the pre-`runtime` interior error rail. When the `runtime` domain lands:
- `db.query` returns `RuntimeRail[QueryResult] = Result[QueryResult, BoundaryFault]` for domain-internal consumers (the `async_boundary("query", ...)` wrapper converts `DbFault` to `BoundaryFault`).
- `DbFault.envelope()` remains the CLI-projection helper; `DbFault` is NOT eliminated.
- `Boundary` in `admin/db.py` is extended in place to include `"ingest"`, `"embed"`, `"search"` when those rails land; the `runtime` domain does not own a parallel `Boundary` type.

**Seam 4 — `StackOp` lifecycle (existing-rails ↔ runtime)**

`StackOp.UP`/`DOWN`/`STATUS` are the lifecycle verbs the runtime domain's automation `stack` command and VPS bootstrap also invoke. The entrypoint is `infra.run(op, cfg)` after collapse; the runtime domain imports `StackOp` and `infra.run` without re-implementing Pulumi dispatch.

**Seam 5 — `Kind` ledger vocabulary (existing-rails ↔ runtime)**

The ledger `Kind` cases (`COVERAGE`, `GAPS`, `STALE`, `NEXT`, `OWNER`) are read by the runtime domain's scheduled automation to drive work selection. The runtime domain consumes the `Envelope` stdout and extends it only by adding new `Kind` cases to the existing-rails owner, not by introducing a parallel ledger query.

**Seam 6 — `sync.run` / heptabase boundary (existing-rails ↔ runtime, automation)**

The `sync.run(cfg, /, *, concept: str | None = None)` entrypoint and `_heptabase` boundary helper are consumed by the runtime domain's watch loop that triggers re-sync on content change. The `SyncDetail` receipt carries `card_id` used by the watch domain to link generated cards back to concepts. The canonical import after collapse is `from admin.rails.sync import run as sync_run`; the `rails.sync_diff` / `rails.sync_generate` re-export aliases do not exist after the existing-rails realize pass. The automation domain's `Sync` action dispatches to `sync_run(cfg, concept=None)` for DIFF and `sync_run(cfg, concept=spec.concept)` for GENERATE — this is the binding contract.

**Seam 7 — `cyclopts` App entrypoint (existing-rails ↔ runtime)**

The `app` instance in `admin/__main__.py` is the mount point the runtime domain's automation/watch/schedule and remote `--exec` sub-apps are registered onto via `app.command(subapp)`. The existing `app` is the root; the runtime domain does not construct a parallel `App`.

**Seam 8 — `_DB_LIMITER` bootstrap (existing-rails ↔ runtime)**

The module-level `_DB_LIMITER: CapacityLimiter = anyio.CapacityLimiter(8)` in `admin/db.py` is a pre-`runtime` bootstrap. When the `runtime` domain lands, `LanePolicy` owns `CapacityLimiter` lifecycle; `db.py` is edited to borrow the policy-managed limiter (from the composition root) instead of the module-level bootstrap. This is a targeted in-place replacement: one `CapacityLimiter` owner always, never two.

**Seam 9 — `stamina.retry` decorators → `guard` supersession (existing-rails ↔ runtime)**

The two `@stamina.retry` decorators on `_run_blocking` (DB) and `_pull_embed_model` (httpx) are pre-`runtime` bootstraps. When the `runtime` domain lands, `admin/db.py`'s local retry decoration is superseded by `guard(RetryClass.DB)` imported from `admin/runtime/resilience.py`; the existing-rails realize pass imports `guard` and removes its own direct `@stamina.retry` application at that site. Analogously, `_pull_embed_model` moves to `guard(RetryClass.HTTP)`. The `POLICY` table in `resilience.py` owns the retry parameters for both classes; the parameters in the bootstrap `@stamina.retry` calls must match what `POLICY[RetryClass.DB]` and `POLICY[RetryClass.HTTP]` will declare to avoid a behavioral diff at the transition boundary. No local `retry_boundary` aspect factory is introduced at any stage — the two direct sites do not trigger the COLLAPSE_SCAN [12] threshold.

---

## [08]-[PORTABILITY / VPS]

The existing-rails domain operates on the live Hostinger VPS as follows:

**Connection:** `MAGHZ_DATABASE_DSN` is the sole DSN surface. On the VPS, this env var points to the managed Postgres service (not the local Docker container). `DatabaseConfig.dsn` reads it directly; no code change required.

**Stack operations:** `StackOp.UP`/`DOWN`/`STATUS` invoke the Pulumi Automation API against a `file://` backend in `InfraConfig.state_dir`. On the VPS, `state_dir` resolves to an operator-owned path (e.g., `/var/lib/maghz/pulumi`); this is a settings value, not hardcoded.

**Schema apply:** `atlas schema apply` and `psql -f` are Forge-provided CLI tools on `PATH`. The VPS must have these on `PATH` for the schema rail to work. No Python code change.

**Heptabase CLI:** The `heptabase` CLI is a local Mac binary; it is not available on the VPS. The `sync.run(cfg, /, *, concept: str | None = None)` verbs are CLI-local operations. On the VPS, a future remote-exec seam (runtime domain) calls back to the local CLI via SSH/asyncssh. The existing-rails design does not need to account for this — it owns only the local CLI boundary.

**Secrets / credentials:** `MaghzSettings` reads from `.env` and env vars only; no keyring reads in existing-rails. `keyring` is admitted but reserved for the runtime domain's OAuth token cache. The existing-rails domain is credential-free.

**Token caches:** No token caches in existing-rails. Gitignored by default through `.cache/` already in `.gitignore`.

**Service account:** The operator service account (`maghz` Postgres user) is declared in `POSTGRES_USER=maghz`; `DatabaseConfig` connects as that user. No VPS-specific auth change.

---

## [09]-[ACCEPTANCE]

Gate signals for the realize pass:

**Static quality (zero-exit required):**
- `ruff check admin/` — zero errors; `select = ["ALL"]` with configured ignores.
- `ruff format --check admin/` — zero formatting deltas.
- `ty check admin/` — zero errors; `all = "error"`.
- `mypy admin/` — zero errors; strict mode with pydantic plugin.

**Structural correctness:**
- Every `match` over a closed `StrEnum` carries a `case unreachable: assert_never(unreachable)` arm.
- `beartype_this_package` installed in `admin/__init__.py` — no change.
- `stamina.retry` decorates `_run_blocking` (DB connect/query) and `_pull_embed_model` (httpx) directly — no local aspect factory.
- `anyio.create_task_group()` used in `schema.run(SchemaOp.APPLY)` for the concurrent cp+atlas phase; results collected via `anyio.create_memory_object_stream[tuple[int, int]](max_buffer_size=3)` with step-index keys.
- `anyio.move_on_after` (not `fail_after`) is the deadline primitive in `schema.run(SchemaOp.APPLY)`.
- No `asyncio` import anywhere in `admin/`.
- `admin/rails/sync.py` exposes one `run(cfg: MaghzSettings, /, *, concept: str | None = None)` entrypoint; `_diff` and `_generate` are private; `SyncOp` does not exist.
- `admin/rails/schema.py` exposes one `run(op: SchemaOp, cfg, /)` entrypoint.
- `admin/infra/runner.py` exposes one `run(op: StackOp, cfg, /)` entrypoint; `admin/rails/stack.py` is deleted.
- `admin/rails/__init__.py` re-exports `run as schema`, `run as stack`, `run as sync`, `query as ledger` — one semantic alias per rail, eliminating the `schema_apply`/`schema_doctor`/`sync_diff`/`sync_generate` alias family.
- All four dispatch tables (`_RANK_EXIT`, `_SQL`, `_BUILD`, `_RUNNER`) use `frozendict`; no `MappingProxyType`, no `expression.Map`.
- All `msgspec.Struct` subclasses carry `gc=False` including `DbFault`.
- `concept` parameter on `sync.run` is `str | None`; no `Option[str]` in the domain signature; no `SyncOp`.
- CLI adapter in `__main__.py` projects raw `str` concept argument to `concept=concept_str` and absent argument to `concept=None` before calling `sync.run`.
- `_DB_LIMITER: CapacityLimiter = anyio.CapacityLimiter(8)` declared at module level in `admin/db.py`; passed as `limiter=_DB_LIMITER` on every `to_thread.run_sync` call.
- No `Option[str]` import from `expression` in `admin/rails/sync.py`.

**Runtime verbs that must fire (local dev):**
- `maghz up` → `Envelope(status="ok", report=Report(detail=StackDetail(op="up", ...)))` on stdout.
- `maghz down` → same shape with `op="down"`.
- `maghz status` → `StackDetail(op="status", result="preview", ...)`.
- `maghz schema apply` → `SchemaDetail(op="apply", exits=(0,0,0,0,0))` when all steps succeed.
- `maghz schema doctor` → rows of extension names.
- `maghz ledger coverage` → `LedgerDetail(kind="coverage", count=N)`.
- `maghz sync diff` → `SyncDetail(op="diff", drift=N, card_total=M)`.
- `maghz sync generate <concept>` → `SyncDetail(op="generate", card_id="<uuid>")`.

**Receipts that must materialize:**
- `SchemaDetail` `exits` tuple must have exactly 5 elements in declaration order: `(synonyms_cp, thesaurus_cp, atlas, routines, cron)`.
- `StackDetail` `resource_changes` is `Mapping[str, int]` — keys are string Pulumi op names.
- `SyncDetail.card_total` is `int | msgspec.UnsetType`; `msgspec.UNSET` when the diff call did not reach the Heptabase census step.
- `SyncDetail.card_id` is `str | msgspec.UnsetType`; present only on GENERATE success.
- `Envelope.code` projects to exit code via `Status._RANK_EXIT` (zero for `OK`/`SKIP`/`EMPTY`, non-zero for `FAILED`/`FAULTED`).
- A tripped `move_on_after` deadline in `schema.run(SchemaOp.APPLY)` records a non-zero sentinel exit code for the timed-out step; `SchemaDetail.exits` still has 5 elements.
