# [RUNTIME_WORKLIST]

Realize-ready worklist folding `docs/design/runtime.md` into executable OWNER work. The `runtime` domain is the substrate every other domain (`automation`, `remote`, `cloud-sync`, `mcp`, `existing-rails`) composes on; it is realized FIRST. No new package is admitted; all seven packages already sit in `pyproject.toml`. The `.api` density bar is the Rasm `libs/python/.api/` catalogs cited in the blueprint plus `docs/stacks/python/` — Maghz has no local `libs/` tree, so no `.api` note is authored here.

---

## [01]-[OWNERS]

A new `admin/runtime/` package (`admin/runtime/__init__.py` re-exports the public surface). Four owner modules; no fifth file. Two existing files are modified in place.

| [FILE] | [ACTION] | [OWNS — dense polymorphic type] |
| ------ | -------- | -------------------------------- |
| `admin/runtime/rails.py` | create | `RuntimeRail[T] = Result[T, BoundaryFault]` + the closed `BoundaryFault` `@tagged_union` + `CLASSIFY` linear-scan table + `async_boundary`/`boundary` (the sole exception→fault conversions). Sections: `[TYPES]` `[CONSTANTS]` `[OPERATIONS]`. |
| `admin/runtime/lanes.py` | create | `LanePolicy` (frozen dataclass value object) + `Admit` `@tagged_union` + `DrainReceipt` (frozen dataclass) + the one `async def drain` entrypoint + `ADMIT_TABLE: Map[AdmitTag, ...]`. Sections: `[TYPES]` `[CONSTANTS]` `[MODELS]` `[OPERATIONS]` `[TABLES]` `[COMPOSITION]`. |
| `admin/runtime/resilience.py` | create | `RetryClass`/`RetryMode` StrEnums + `Policy` (frozen dataclass) + `guard`/`retrying`/`install` + `POLICY`/`INSTALL_TABLE` Maps + `RetryReceiptHook` factory. Sections: `[TYPES]` `[CONSTANTS]` `[MODELS]` `[OPERATIONS]` `[TABLES]` `[COMPOSITION]`. |
| `admin/runtime/receipts.py` | create | `Receipt` `@tagged_union` + `ReceiptContributor` Protocol + `Signals` ClassVar singleton service + `@receipted`/`@drained` aspects + `PHASE_LEVEL`/`LEVEL_METHOD` Maps. Sections: `[TYPES]` `[CONSTANTS]` `[MODELS]` `[ERRORS]` `[SERVICES]` `[OPERATIONS]` `[COMPOSITION]`. |
| `admin/runtime/__init__.py` | create | Re-export the public surface: `RuntimeRail`, `BoundaryFault`, `async_boundary`, `boundary`, `LanePolicy`, `Admit`, `ContentKey`, `DrainReceipt`, `drain`, `RetryClass`, `RetryMode`, `Policy`, `guard`, `retrying`, `install`, `Receipt`, `ReceiptContributor`, `Signals`, `receipted`, `drained`. |
| `admin/db.py` | modify | Remove no local aspect (none exists yet; the `existing-rails` `retry_boundary` is its concern). Keep `DbFault`/`QueryResult`/`query` unchanged. The pg8000 fence threads through `guard(RetryClass.DB)` imported from `admin.runtime.resilience`; `Boundary` literal extends in place (`'ingest'/'embed'/'search'`) when those rails land — never a parallel `Boundary`. |
| `admin/__main__.py` | modify | Replace the inline `_observe` structlog `configure` call with `Signals.configure(fmt)`; the `--log-level`/`--log-format` seam now drives `Signals` once at the pre-dispatch seam. Add the CLI-boundary projection helper that converts `Error(BoundaryFault)` → `fault(...)` `Envelope`. |
| `admin/rails/schema.py` | modify | `apply()` bare `try/except OSError → fault` is replaced by `async_boundary('apply', ...)` + `guard(RetryClass.PROC)`; returns `RuntimeRail[SchemaEvidence]` at domain level, projects to `Envelope` only at the CLI handler. `move_on_after` (never `fail_after`) for per-step deadlines. |
| `admin/rails/stack.py` | modify | `run()` bare `try/except (CommandError, HTTPError, OSError)` routes through `async_boundary` + `guard(RetryClass.PROC)` for the Pulumi fence and `async_boundary` + `guard(RetryClass.HTTP)` for the Ollama pull (`BackoffHook` reads the `retry_after` header); returns `RuntimeRail[StackEvidence]`. |
| `admin/rails/sync.py` | modify | `_heptabase()` bare `try/except OSError` returning `DbFault` moves to `async_boundary('heptabase', ...)` + `guard(RetryClass.PROC)` returning `RuntimeRail` so transient CLI spawn faults retry before the CLI boundary projects to `Envelope`. |

The existing `admin/core/model.py` (`Envelope`/`Detail`/`Report`/`Row`) and `admin/core/status.py` (`Status`) are NOT subsumed: `rails.py` owns the domain-internal typed-result rail, `model.py` owns the CLI stdout wire shape; the two never collapse. `[SERVICES]` is absent from `lanes.py`/`resilience.py` (frozen value objects, not service boundaries); `receipts.py` `[SERVICES]` owns `Signals` alone.

---

## [02]-[ADTs]

`admin/runtime/rails.py` — `BoundaryFault` (`@tagged_union(frozen=True)`), discriminant `FaultTag = Literal["config","resource","deadline","api","boundary","aggregate"]`. Cases: `config: tuple[str,str]`, `resource: tuple[str,str]`, `deadline: tuple[str,float]`, `api: tuple[str,str]`, `boundary: tuple[str,str]`, `aggregate: tuple[BoundaryFault, ...]`. `match` is total with `assert_never`; aggregate combines without flattening. `facts() -> dict[str, object]` projects each leaf to `subject`/`detail`/`budget`/`members` keys for structlog spread. `RuntimeRail[T] = Result[T, BoundaryFault]`.

`admin/runtime/rails.py` — `CLASSIFY: Final[tuple[tuple[tuple[type[Exception], ...], Callable[[str,str], BoundaryFault]], ...]]` ordered linear-scan (plain `tuple`, NOT `Map` — first `isinstance` match wins). Rows in order: `(anyio.BrokenWorkerProcess, anyio.BrokenResourceError, anyio.ClosedResourceError)→resource`; `(anyio.TimeoutError,)→deadline`; `(msgspec.DecodeError, msgspec.ValidationError)→boundary`; `(OSError,)→boundary`; `(beartype.roar.BeartypeCallHintViolation,)→api`; `(Exception,)→boundary` (catch-all, last). The `remote` implement pass inserts asyncssh rows BEFORE `(OSError,)`: `(asyncssh.ProcessError, asyncssh.SFTPError)→boundary`, `(asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable)→api`, `(asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError)→resource`. `CLASSIFY` is the SOLE extension contract: rows, never a `catch` kwarg, never a new function.

`admin/runtime/lanes.py` — `Admit` (`@tagged_union(frozen=True)`, NO PEP 695 type param — `expression.@tagged_union` does not support class-level `[T]`), discriminant `AdmitTag = Literal["bare","keyed","retried","offload"]`. Cases: `bare: Work`, `keyed: tuple[ContentKey, Work]`, `retried: tuple[RetryClass, Work]`, `offload: tuple[Callable[[], object], Option[anyio.CapacityLimiter]]`. `Work = Callable[[], Awaitable[RuntimeRail[object]]]`; `ContentKey = NewType("ContentKey", str)`. `drain` discriminates by case via `ADMIT_TABLE: Map[AdmitTag, tuple[KeyFn, MakeFn]]`.

`admin/runtime/resilience.py` — `RetryClass(StrEnum)`: `DB="db"`, `HTTP="http"`, `PROC="proc"`, `SECRET="secret"`. `RetryMode(StrEnum)`: `EMIT="emit"`, `SILENT="silent"`, `TEST="test"`. Both are closed bounded vocabularies; `POLICY: Map[RetryClass, Policy]` is structurally total (one row per member, keyed on the member not `.value`).

`admin/runtime/receipts.py` — `Receipt` (`@tagged_union(frozen=True)`), discriminant `ReceiptTag = Literal["fact","rejected","drained"]`. Cases: `fact: tuple[Phase, str, str, dict[str, object]]` (phase, owner, subject, facts), `rejected: tuple[str, BoundaryFault]` (owner, fault), `drained: tuple[str, DrainReceipt, int]` (owner, receipt, rss_bytes). `Phase = Literal["admitted","retry","emitted"]` (`"retry"`, not `"planned"`). `Receipt.of(owner, evidence)` shape-polymorphic factory discriminating on `evidence` concrete type (`BoundaryFault`→`rejected`; `tuple[DrainReceipt,int]`→`drained`; `tuple[Phase,str,dict]`→`fact`). `Receipt.project(self) -> tuple[LogLevel, dict[str,object]]` total fold via `match`/`assert_never`.

Non-union owners (frozen dataclasses, NOT `msgspec.Struct` — they carry `expression.Block`/`Map`/`Option`/`Callable`/exception-type fields msgspec cannot encode): `LanePolicy(capacity:int, deadline:Option[float]=Nothing)`; `DrainReceipt(accepted, completed, cancelled, rejected:int, values:Block[object], cache:Map[ContentKey,object], faults:Block[BoundaryFault], hit:int=0)`; `Policy(attempts:int, timeout:float, target:stamina.ExcOrBackoffHook, wait_initial/wait_max/wait_jitter/wait_exp_base:float|None=None)` with `schedule() -> dict[str, float|ExcOrBackoffHook]` projecting non-`None` columns to a `**`-passable stamina kwarg dict.

---

## [03]-[API_MEMBERS]

`anyio` — `to_thread.run_sync(fn, *args, limiter=)` (lanes: pg8000 fence + `Admit.offload` kernels); `to_thread.current_default_thread_limiter()` (lanes: default limiter on `Nothing`); `CapacityLimiter(total_tokens)` (lanes: one per `LanePolicy`, `functools.cache`-memoised); `create_task_group()` (lanes: one structured group per drain — never `asyncio.gather`/`create_task`); `move_on_after(delay, shield=False)` (lanes: per-unit deadline scope; a tripped scope sets `cancelled` count, never raises); `create_memory_object_stream[T](max_buffer_size)` (lanes: result channel); `BrokenWorkerProcess`/`BrokenResourceError`/`ClosedResourceError` (rails: `resource` row); `TimeoutError` (rails: `deadline` row); `run_process(command, *, check=False)` (existing schema/sync, `PROC` class). `fail_after` is FORBIDDEN in domain code — CLI/process-boundary only (e.g. cloud-sync wraps the whole op at the `Envelope` boundary).

`stamina` — `AsyncRetryingCaller(attempts=, timeout=, wait_*=)` (resilience: reusable caller, policy frozen at construction); `AsyncRetryingCaller.on(target) -> BoundAsyncRetryingCaller` (resilience: `guard()` caches the bound caller per `RetryClass` member via `functools.cache`); `retry_context(on=, **schedule)` (resilience: `retrying(cls)` rebuilds per `async for` block); `Attempt.num`/`Attempt.next_wait` (receipts: per-attempt facts); `instrumentation.RetryDetails` (receipts: `retry_num`/`wait_for`/`waited_so_far`/`caused_by`); `instrumentation.RetryHookFactory` (resilience: `RetryReceiptHook` minting a `fact`-phase `retry` receipt); `instrumentation.StructlogOnRetryHook` (resilience: warning in the hook stack); `instrumentation.set_on_retry_hooks(hooks)` (resilience: `INSTALL_TABLE[RetryMode.EMIT]`); `set_testing(True)` (resilience: `INSTALL_TABLE[RetryMode.TEST]`); `is_testing()` (acceptance probe); `ExcOrBackoffHook`/`BackoffHook` (resilience: `Policy.target`). `guard` call shape: `await guard(RetryClass.DB)(afn, *args, **kwargs)` — NOT `@guard(...)`. Definition-time decoration is `@stamina.retry(on=, **policy.schedule())`.

`expression` — `Result[T,E]`/`Ok`/`Error` (rails: `RuntimeRail` carrier); `Option[T]`/`Some`/`Nothing` (lanes: `CapacityLimiter` override, `LanePolicy.deadline`); `@tagged_union`/`tag()`/`case()` (every closed union); `effect.result[Any, BoundaryFault]()` (rails: sequential-bind builder); `pipe`/`compose` (primary composition); `Block.empty`/`Block.of_seq`/`Block.choose`/`Block.fold` (lanes: unit traversal + accumulation); `Map.empty`/`Map.of_seq`/`Map.try_find`/`Map.add` (all dispatch tables); `Result.to_option`/`Result.swap` (lanes: split oks vs faults); `NewType` (lanes: `ContentKey`). `Map` is the OWNER_CHOOSER form for every static keyed table; `CLASSIFY` is the one ordered linear-scan exception (plain `tuple`).

`structlog` — `configure(processors=, wrapper_class=, logger_factory=, cache_logger_on_first_use=)` (receipts: `Signals.configure` — moves the inline `__main__._observe` body here); `make_filtering_bound_logger(min_level)` (receipts: no-op sub-threshold); `contextvars.merge_contextvars` (receipts: first processor); `contextvars.bind_contextvars(**kw)`/`bound_contextvars(**kw)` (domain: scoped per-rail context); `processors.JSONRenderer(serializer=)` (receipts: prod output, paired with `BytesLoggerFactory`); `dev.ConsoleRenderer` (receipts: dev output by `ObservabilityConfig.format`); `processors.TimeStamper`/`processors.dict_tracebacks`/`processors.add_log_level` (receipts: chain); `BytesLoggerFactory` (receipts: prod byte sink); `testing.capture_logs()` (specs). structlog targets stderr only; stdout `Envelope` JSON stays.

`msgspec` — `json.Encoder(enc_hook=repr, order="deterministic").encode` (receipts: structlog JSON serializer); `DecodeError`/`ValidationError` (rails: `boundary` row). `Struct(frozen=True, gc=False)` stays wire/egress only; `DrainReceipt`/`Policy`/`LanePolicy` are NOT `msgspec.Struct`. `UNSET` unused by runtime owners.

`psutil` — `Process()` (receipts: own-process RSS in `@drained`); `Process.oneshot()` + `memory_info().rss` (receipts: one syscall per drained emit; `NoSuchProcess`/`AccessDenied` guarded to `rss_bytes=0`).

`keyring` — `keyring.errors.KeyringLocked` (resilience: `RetryClass.SECRET` target, reserved VPS credential path). Verify the `KeyringLocked` class path on the installed version before realize.

---

## [04]-[DEPS]

No new package is admitted. All seven required packages are already in `pyproject.toml` (`anyio>=4.14.0`, `stamina>=26.1.0`, `expression>=5.6.0`, `structlog>=26.1.0`, `msgspec>=0.21.1`, `psutil>=7.2.2`, `keyring` no floor pin) — all `pure-venv` band. `frozendict` is explicitly NOT admitted: PEP 603 was not ratified for py3.15 stdlib and `expression.Map` serves every keyed dispatch need; admit it only at a future point that needs O(1) immutable-dict lookup, with a floor pin. Maghz has no local `libs/` tree, so no `.api` catalog note is authored — the density bar is the Rasm `.api` catalogs the blueprint cites plus `docs/stacks/python/`.

| [PACKAGE] | [BAND] | [.api NOTE] |
| --------- | ------ | ----------- |
| `anyio` | pure-venv | already admitted; mine `CapacityLimiter`/`move_on_after`/`create_task_group`/`create_memory_object_stream`/`to_thread.run_sync(limiter=)` — none yet used with explicit `limiter` |
| `stamina` | pure-venv | already admitted; currently zero-used — `AsyncRetryingCaller`/`BoundAsyncRetryingCaller`/`retry_context`/`RetryHookFactory`/`set_on_retry_hooks`/`set_testing` |
| `expression` | pure-venv | already admitted; `Block`/`Map`/`@tagged_union` zero-used today (`Result`/`Ok`/`Error` already in `db.py`) |
| `structlog` | pure-venv | already admitted; currently configured inline in `__main__._observe` — moves to `Signals.configure` |
| `msgspec` | pure-venv | already admitted; add `json.Encoder(enc_hook=repr, order="deterministic")` for the structlog renderer |
| `psutil` | pure-venv | already admitted; zero-used today — `Process().oneshot()` + `memory_info().rss` |
| `keyring` | pure-venv | already admitted; verify `keyring.errors.KeyringLocked` class path on installed version |

---

## [05]-[RIPPLES]

Cross-domain canonical shapes this domain OWNS; each counterpart aligns to it, never declares a parallel surface.

- domains `[runtime, db]`: `admin/db.py query()` returns `Result[QueryResult, DbFault]`; the realize pass threads the pg8000 fence through `guard(RetryClass.DB)`. Two-phase lift: pre-runtime `query` stays `Result[QueryResult, DbFault]`; once runtime lands, `async_boundary('query', ...)` wraps it to lift `DbFault`→`BoundaryFault` for domain-internal consumers as `RuntimeRail[QueryResult]`. `DbFault.envelope()` stays the CLI projection; `DbFault` is NOT eliminated. The `Boundary` literal extends in place (`'ingest'/'embed'/'search'`) — runtime declares no parallel `Boundary`.
- domains `[runtime, existing-rails]`: the existing-rails local `retry_boundary` aspect is SUPERSEDED by `guard(RetryClass.*)`; the existing-rails realize pass imports `guard` and removes its own local aspect.
- domains `[runtime, schema]`: `admin/rails/schema.py apply()` routes the spawn fence through `async_boundary('apply', ...)` + `guard(RetryClass.PROC)` returning `RuntimeRail[SchemaEvidence]`, projecting to `Envelope` only at the CLI handler.
- domains `[runtime, stack]`: `admin/rails/stack.py run()` routes the Pulumi fence through `async_boundary` + `PROC` and the Ollama pull through `async_boundary` + `guard(RetryClass.HTTP)` with a `BackoffHook` reading the `retry_after` header, returning `RuntimeRail[StackEvidence]`.
- domains `[runtime, sync]`: `admin/rails/sync.py _heptabase()` moves the heptabase CLI spawn fence to `async_boundary('heptabase', ...)` + `guard(RetryClass.PROC)` returning `RuntimeRail` so transient spawn faults retry before the CLI boundary projects to `Envelope`.
- domains `[runtime, automation]`: automation composes `drain(policy, units, cache)` with `Admit.bare/keyed/retried/offload`; `DrainReceipt` is the canonical result carrier; `drain_receipt.values[0]` is the inner receipt to the NDJSON ledger while `accepted/cancelled/hit` flow to structlog context only; `RuntimeRail[T]` is the canonical rail; `ContentKey = NewType('ContentKey', str)` is shared with cloud-sync. `engine.py` composes `guard(RetryClass.HTTP)`/`guard(RetryClass.DB)` — no direct `@stamina.retry(...)`.
- domains `[runtime, remote]`: remote composes `guard(RetryClass.SECRET)` for keyring reads and `guard(RetryClass.HTTP)` for outbound HTTP and SSH transients; asyncssh transient types broaden the `RetryClass.HTTP` policy target (preferred) rather than adding a `RetryClass.SSH`. `async_boundary('remote', ...)` is the single fault-lift; remote inserts the asyncssh `CLASSIFY` rows (before `(OSError,)`).
- domains `[runtime, cloud-sync]`: cloud-sync uses `drain` with `Admit.retried` carrying `RetryClass.PROC` for rclone fences, threading the `ContentKey`-keyed session cache across multi-stage `DrainReceipt` fronts; never opens a raw `anyio.create_task_group()`; `CloudSyncDetail (tag='cloud')` rides the shared `Envelope` contract.
- domains `[runtime, mcp]`: mcp composes `Signals.emit` + `Receipt.of` as its diagnostic surface; `BoundaryFault` is the typed error the handler lifts via `async_boundary` at the tool-call edge; `McpFault` projects to `BoundaryFault.boundary` at the conversion point.

---

## [06]-[DEPENDS_ON]

None. `runtime` is the substrate every other domain depends on; it must be realized BEFORE `db` (rewiring), `existing-rails`, `schema`, `stack`, `sync`, `automation`, `remote`, `cloud-sync`, and `mcp`. The only existing owners it imports are `admin.core` (`Envelope`/`fault`/`Status` — for the CLI projection helper) and `admin.settings` (`MaghzSettings.log` / `ObservabilityConfig.format` — for `Signals.configure`), both already realized.

---

## [07]-[ACCEPTANCE]

- `ruff check admin/runtime/ --select ALL` with the existing `pyproject.toml` ignore set: zero diagnostics.
- `ty check` over `admin/` (binding gate): zero errors.
- `mypy --config-file pyproject.toml admin/` (advisory): zero errors on new modules; the existing `pg8000` overrides remain.
- Runtime verbs: `drain(LanePolicy(capacity=4), Block.of_seq([Admit(bare=coro)]), Map.empty())` → `DrainReceipt` with `accepted==1`, `completed==1`; `drain(..., [Admit(offload=(cpu_fn, Nothing))], ...)` → `accepted==1`, `completed==1` via thread-offload; `guard(RetryClass.DB)` returns a `BoundAsyncRetryingCaller`, twice → same cached instance (`functools.cache` identity); `Signals.emit(Receipt.of("db", BoundaryFault(boundary=("query","timeout"))))` writes one structured JSON line without raising; `async_boundary("test", lambda: anyio.sleep(0))` → `Ok(None)`; `install(RetryMode.TEST)` → `stamina.is_testing()` is `True`; `INSTALL_TABLE.try_find(RetryMode.EMIT).default_value(lambda: None)()` sets the process-global hook list.
- Receipts: a non-zero-`rejected` `DrainReceipt` carries a `Block[BoundaryFault]` with at least one addressable fault; `Receipt.of("db", BoundaryFault(boundary=("query","timeout")))` mints a `rejected` case projecting a `warning`-level line with `subject`/`detail` keys; a guarded `HTTP`/`DB` retry materializes `RetryDetails` (`retry_num`/`wait_for`/`waited_so_far`/`caused_by`) as a `fact`-phase `retry` receipt with a `dict[str,object]` payload; `@drained` on a completed drain produces a `drained`-case `Receipt` with non-negative `rss_bytes` (`0` only on `psutil` access denial, never as default).
