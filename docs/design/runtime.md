# [MAGHZ_RUNTIME_BLUEPRINT]

Runtime substrate: lean concurrency, resilience, receipts, and rails for the `admin/runtime/` cluster. Every other domain (`automation`, `remote`, `cloud-sync`, `mcp`) composes on these four owners — they never re-implement what this layer declares.

---

## [01]-[OWNERS]

Four modules live under a new `admin/runtime/` package. No fifth file is added; every pressure point collapses in-place.

| [FILE]                        | [OWNER CONCEPT]                                            | [SECTIONS]                                                                               |
| ----------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `admin/runtime/lanes.py`      | `LanePolicy` — bounded drain + offload                     | `[TYPES]` `[CONSTANTS]` `[MODELS]` `[OPERATIONS]` `[TABLES]` `[COMPOSITION]`            |
| `admin/runtime/resilience.py` | `RetryClass` — one policy-table StrEnum                    | `[TYPES]` `[CONSTANTS]` `[MODELS]` `[OPERATIONS]` `[TABLES]` `[COMPOSITION]`            |
| `admin/runtime/receipts.py`   | `Receipt` + `Signals` — evidence + log pipeline            | `[TYPES]` `[CONSTANTS]` `[MODELS]` `[ERRORS]` `[SERVICES]` `[OPERATIONS]` `[COMPOSITION]` |
| `admin/runtime/rails.py`      | `async_boundary` + `RuntimeRail` — typed rail + conversion | `[TYPES]` `[CONSTANTS]` `[OPERATIONS]`                                                   |

The existing `admin/db.py` already owns the thread-offload boundary via `anyio.to_thread.run_sync`; its `DbFault` + `query` stay. The existing `admin/core/model.py` (`Envelope`/`Detail`/`Report`/`Row`) and `admin/core/status.py` (`Status`) are the CLI-output owners — they are NOT subsumed. `rails.py` carries the domain-internal typed-result rail; `model.py` carries the CLI stdout wire shape. The two never collapse.

The `existing-rails.md` blueprint's local `retry_boundary` aspect in `admin/db.py` is superseded by `guard(RetryClass.DB)` from this module. `admin/db.py` imports `guard` from `admin/runtime/resilience` and removes its own local aspect helper.

`[SERVICES]` section is removed from `lanes.py` and `resilience.py` because `LanePolicy` and `Policy` are frozen value objects, not service boundaries. The `[SERVICES]` section in `receipts.py` owns `Signals`, the one process-global structured-log service.

---

## [02]-[ADTs]

### `admin/runtime/rails.py` — `RuntimeRail[T]`

```python
# [TYPES]
type RuntimeRail[T] = Result[T, "BoundaryFault"]

# [MODELS] — one closed fault family
@tagged_union(frozen=True)
class BoundaryFault:
    tag: FaultTag = tag()
    config: tuple[str, str] = case()      # (subject, detail)
    resource: tuple[str, str] = case()    # (subject, detail)
    deadline: tuple[str, float] = case()  # (subject, budget)
    api: tuple[str, str] = case()         # (subject, detail)
    boundary: tuple[str, str] = case()    # (subject, detail)
    aggregate: tuple["BoundaryFault", ...] = case()

type FaultTag = Literal["config", "resource", "deadline", "api", "boundary", "aggregate"]
```

The `match` over `BoundaryFault` is total; every arm carries `assert_never`. The aggregate law combines without flattening. `facts() -> dict[str, object]` projects every leaf to a plain `dict[str, object]` carrying `subject`/`detail`/`budget`/`members` keys so the `receipts.py` `rejected` case spreads it into the structured log event. `frozendict` is not used here: `facts()` is a projection method returning a transient view, not a stored immutable value; the dict is consumed immediately by `structlog` and never stored.

`async_boundary(subject: str, thunk: Callable[[], Awaitable[T]]) -> RuntimeRail[T]` is the one async conversion at every fallible boundary: it awaits the thunk, iterates `CLASSIFY` for the first matching exception family, and returns `Error(BoundaryFault(...))`. `boundary(subject: str, thunk: Callable[[], T]) -> RuntimeRail[T]` is the sync mirror. No `catch` parameter exists on either function — the `CLASSIFY` table is the sole exception-to-fault mapping authority. A caller that needs a custom exception family adds a row to `CLASSIFY`, never a custom `catch` kwarg. The `catch` parameter is a knob: deleting it loses no information the `CLASSIFY` table cannot answer. Rejected by `KNOB_TEST` law.

`CLASSIFY: Final[tuple[tuple[type[Exception], ...], Callable[[str, str], BoundaryFault]]]` — an ordered tuple of `(exception-family-tuple, builder)` pairs; the boundary conversion iterates with `isinstance` and the first matching family wins. A plain `tuple` of pairs is the correct owner for ordered-linear-scan dispatch: `Block` is for traversal with combinators, not a linear `isinstance` probe. Each entry's first element is itself a `tuple[type[Exception], ...]` so one row covers multiple exception siblings without proliferating rows.

```
(anyio.BrokenWorkerProcess, anyio.BrokenResourceError, anyio.ClosedResourceError) → resource
(anyio.TimeoutError,)                                                               → deadline
(msgspec.DecodeError, msgspec.ValidationError)                                      → boundary
(OSError,)                                                                          → boundary
(beartype.roar.BeartypeCallHintViolation,)                                          → api
(Exception,)                                                                        → boundary   # catch-all; last row
```

The remote domain's implement pass verifies and extends `CLASSIFY` with asyncssh exception rows if not already present:
```
(asyncssh.ProcessError, asyncssh.SFTPError)                  → boundary
(asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable)   → api
(asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError) → resource
```
`CLASSIFY` is the sole extension contract; the remote domain adds rows, never a new function. These additions must appear before the `(OSError,)` row and definitely before `(Exception,)`.

### `admin/runtime/lanes.py` — `Admit` + `LanePolicy`

`@tagged_union` from `expression` does not support PEP 695 `[T]` generic syntax at the class level. `Admit` is declared without a type parameter; `Work` and `ContentKey` use concrete `object` bounds at the tagged-union level. Callers that need type-specific `Admit` values are parameterized at call-site via `drain`'s return type annotation.

```python
# [TYPES]
ContentKey = NewType("ContentKey", str)   # NewType for ty/mypy enforcement; transparent at runtime
type Work = Callable[[], Awaitable[RuntimeRail[object]]]

# [MODELS]
@tagged_union(frozen=True)
class Admit:
    tag: AdmitTag = tag()
    bare: Work = case()
    keyed: tuple[ContentKey, Work] = case()
    retried: tuple[RetryClass, Work] = case()
    offload: tuple[Callable[[], object], Option["anyio.CapacityLimiter"]] = case()

type AdmitTag = Literal["bare", "keyed", "retried", "offload"]
```

`offload` is the fourth `Admit` case — CPU-kernel thread-offload — collapsing what was a separate method into the one `drain` entrypoint. `drain` discriminates admission by case via `ADMIT_TABLE`.

`LanePolicy` is a `@dataclass(frozen=True, slots=True, kw_only=True)` value object, not a `msgspec.Struct`: it carries `Option[float]` which msgspec cannot serialize without a custom hook, it is never wire-encoded, and its only consumer is the `drain` module-level function. A frozen dataclass is the correct `OWNER_CHOOSER` row for a pure internal value object.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LanePolicy:
    capacity: int
    deadline: Option[float] = field(default=Nothing)
```

`DrainReceipt` is likewise a `@dataclass(frozen=True, slots=True)`, not a `msgspec.Struct`: it carries `Block[object]` and `Map[ContentKey, object]` which are not msgspec-serializable. It is domain-internal evidence, never wire-encoded.

```python
@dataclass(frozen=True, slots=True)
class DrainReceipt:
    accepted: int
    completed: int
    cancelled: int
    rejected: int
    values: Block[object] = field(default_factory=Block.empty)
    cache: Map[ContentKey, object] = field(default_factory=Map.empty)
    faults: Block[BoundaryFault] = field(default_factory=Block.empty)
    hit: int = 0
```

One `async def drain(policy: LanePolicy, units: Block[Admit], cache: Map[ContentKey, object]) -> DrainReceipt` module-level function (not a method) is the sole polymorphic entrypoint. It discriminates admission by case via `ADMIT_TABLE`, creates one `anyio.create_task_group()` per call, deadline-wraps each unit with `anyio.move_on_after`, thread-offloads `offload` cases through `anyio.to_thread.run_sync(fn, limiter=limiter)`, and collects results through a `MemoryObjectSendStream`/`MemoryObjectReceiveStream` pair.

`ContentKey` is a `NewType("ContentKey", str)` — `NewType` is the correct branding primitive under py3.15 and the Rasm law; `type ContentKey = str` is a transparent alias that ty/mypy cannot distinguish from `str`.

`ADMIT_TABLE: Final[tuple[tuple[AdmitTag, KeyFn, MakeFn], ...]]` — one row per case as a plain `tuple` of named triples (using a simple named 3-tuple or a module-local `@dataclass`). `frozendict` is not admitted in `pyproject.toml` and PEP 603 was not merged into py3.15; the stdlib does not inject `builtins.frozendict`. Until `frozendict` is explicitly admitted, dispatch tables use `expression.Map` (for persistent keyed lookup) or plain `tuple` of rows (for ordered linear scan). `ADMIT_TABLE` is a keyed lookup by `AdmitTag`, so `Map[AdmitTag, tuple[KeyFn, MakeFn]]` is the correct owner. The `expression.Map` is the right table form for static definition-time keyed dispatch per `existing-rails.md` §05 — that blueprint correctly identifies `frozendict` as an unadmitted package and defaults to `expression.Map` for dispatch tables. This blueprint aligns.

### `admin/runtime/resilience.py` — `RetryClass`

```python
class RetryClass(StrEnum):
    DB = "db"        # pg8000 + OSError transients; the db.py thread-offload fence
    HTTP = "http"    # httpx timeouts; Ollama pull stream; stack rail httpx calls
    PROC = "proc"    # anyio.run_process OSError; atlas/psql/heptabase spawn
    SECRET = "secret"  # keyring.errors.KeyringLocked + OSError (future VPS path)

class RetryMode(StrEnum):
    EMIT = "emit"
    SILENT = "silent"
    TEST = "test"
```

`Policy` is a `@dataclass(frozen=True, slots=True, kw_only=True)`, not a `msgspec.Struct`. It carries `target: stamina.ExcOrBackoffHook` — a union of exception types and callables — which msgspec cannot encode, and it is never serialized. A frozen dataclass with optional fields using `UNSET`-style sentinels is not the right pattern here: use `field(default=None)` with `float | None` since these are pure runtime policy values without a wire-absent distinction. `Policy.schedule() -> dict[str, float]` projects non-`None` columns to a `**`-passable `stamina` keyword dict.

```python
_UNSET_WAIT: Final = None  # sentinel: defer to stamina default

@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    attempts: int
    timeout: float
    target: stamina.ExcOrBackoffHook
    wait_initial: float | None = None
    wait_max: float | None = None
    wait_jitter: float | None = None
    wait_exp_base: float | None = None

    def schedule(self) -> dict[str, float | stamina.ExcOrBackoffHook]:
        base: dict[str, float | stamina.ExcOrBackoffHook] = {
            "on": self.target, "attempts": self.attempts, "timeout": self.timeout
        }
        if self.wait_initial is not None: base["wait_initial"] = self.wait_initial
        if self.wait_max is not None: base["wait_max"] = self.wait_max
        if self.wait_jitter is not None: base["wait_jitter"] = self.wait_jitter
        if self.wait_exp_base is not None: base["wait_exp_base"] = self.wait_exp_base
        return base
```

`guard(cls: RetryClass) -> BoundAsyncRetryingCaller` is `functools.cache`-memoised per member. A `BoundAsyncRetryingCaller` is a reusable **caller**, not a decorator: its `__call__` signature is `(afn, /, *args, **kwargs) -> Awaitable[T]`. Use pattern: `await guard(RetryClass.DB)(target_fn, *args, **kwargs)`. It is NOT used as `@guard(RetryClass.DB)`. The "retry as decorator" use case is `@stamina.retry(on=..., ...)` applied at definition time. `guard` is for runtime call-site use without wrapping definitions. The blueprint previously claimed "decorator use" which was wrong; corrected to "call-site bound caller."

`retrying(cls: RetryClass)` returns a fresh `stamina.retry_context(...)` iterator each call, consumed as `async for attempt in retrying(cls):`. These are not collapsible: `guard` returns a bound caller (reusable, memoised, stateful identity), `retrying` returns a fresh iterator (single-use inline block). Both are kept; neither is the other.

`INSTALL_TABLE: Final[Map[RetryMode, Callable[[], None]]]` — one row per `RetryMode` member. `install(mode: RetryMode)` dispatches through `Map.try_find(mode).default_with(lambda: ...)()`. `expression.Map` is the correct owner (keyed lookup, static, not accumulated).

`POLICY: Final[Map[RetryClass, Policy]]` — keyed directly on `RetryClass`. Totality is structural: every `RetryClass` member has exactly one row.

### `admin/runtime/receipts.py` — `Receipt` + `Signals`

```python
# [TYPES]
type Phase = Literal["admitted", "retry", "emitted"]
type ReceiptTag = Literal["fact", "rejected", "drained"]

# Protocol — declared in [MODELS]
class ReceiptContributor(Protocol):
    def contribute(self) -> tuple[str, dict[str, object]]: ...
    # returns (subject, facts-dict); facts-dict carries domain-specific key-value evidence

# [MODELS]
@tagged_union(frozen=True)
class Receipt:
    tag: ReceiptTag = tag()
    fact: tuple[Phase, str, str, dict[str, object]] = case()   # (phase, owner, subject, facts)
    rejected: tuple[str, BoundaryFault] = case()               # (owner, fault)
    drained: tuple[str, DrainReceipt, int] = case()            # (owner, receipt, rss_bytes)

type LogLevel = Literal["debug", "info", "warning", "error"]
```

`frozendict` is removed from the `fact` case payload. The immutability invariant of the tagged union is satisfied by `frozen=True` on the `@tagged_union` decorator (which freezes the union instance itself); the `dict[str, object]` payload inside the case is the transient facts carrier consumed by `Signals.emit` and never mutated or stored elsewhere. If interior code must store facts durably, it stores the entire `Receipt` (which is frozen), not the dict. Using `frozendict` requires an unadmitted package; using a `dict` here is safe because the union case payload is read-only by convention once the `Receipt` is constructed (the frozen union instance cannot be reassigned). The alternative — `tuple[tuple[str, object], ...]` — is overly verbose for a structlog event dict.

`drained` case carries `(owner: str, receipt: DrainReceipt, rss_bytes: int)` — the `rss_bytes` field integrates the `psutil` RSS snapshot that `@drained` collects at drain completion. This closes the structural gap where `DrainReceipt` had no RSS field but `@drained` collected RSS evidence.

`Phase` is renamed from `"planned"` to `"retry"`: the `retry` phase covers in-flight `RetryDetails` evidence emitted before the next attempt. "planned" was ambiguous; "retry" is the precise domain event.

`Receipt.of(owner: str, evidence: object) -> Receipt` is the shape-polymorphic factory. It discriminates on the concrete type of `evidence`:
- `BoundaryFault` → `Receipt(rejected=(owner, evidence))`
- `tuple[DrainReceipt, int]` → `Receipt(drained=(owner, evidence[0], evidence[1]))`
- `tuple[Phase, str, dict[str, object]]` → `Receipt(fact=(evidence[0], owner, evidence[1], evidence[2]))`

`Receipt.project(self) -> tuple[LogLevel, dict[str, object]]` is the total `(level, event_dict)` fold via total `match`/`assert_never`. The projected event dict is passed to `Signals.emit` for the structlog pipeline.

```python
# [TYPES]
type LevelMethod = Callable[["structlog.BoundLogger", str, dict[str, object]], None]

# [TABLES]
PHASE_LEVEL: Final[Map[Phase, LogLevel]] = Map.of_seq([("admitted", "debug"), ("retry", "warning"), ("emitted", "info")])
LEVEL_METHOD: Final[Map[LogLevel, tuple[LevelMethod, LevelMethod]]] = ...
# each row: (sync_emit, async_emit) pair of bound-logger method selectors
```

`LevelMethod` is declared as a type alias for the structlog bound-logger emit callable. `LEVEL_METHOD` maps each `LogLevel` to a `(sync, async)` pair of method-selector callables. Both tables use `expression.Map` (keyed static dispatch, not accumulated).

```python
# [SERVICES]
class Signals:
    """Process-global structured-log service. One instance per process; configured once."""
    _logger: ClassVar[structlog.BoundLogger]

    @classmethod
    def configure(cls, fmt: Literal["json", "console"]) -> None: ...

    @classmethod
    def emit(cls, receipt: Receipt, *, redact: Redaction | None = None) -> None: ...

    @classmethod
    async def emit_async(cls, receipt: Receipt, *, redact: Redaction | None = None) -> None: ...
```

`Signals` is a `ClassVar`-backed singleton: no instantiation, one `configure` call at startup. `redact: Redaction | None = None` (where `Redaction` is a `frozenset[str]` of field keys to omit from the event dict) — uses `None` not `Option` because this is a boundary-only parameter and `None` is the genuine "no redaction" sentinel, not a domain absence.

---

## [03]-[.api SURFACE]

All members are verified against the Rasm `.api` catalogs at `libs/python/.api/` and `libs/python/runtime/.api/`.

### `anyio` (`libs/python/.api/anyio.md`)

| [MEMBER]                                                       | [OWNER]        | [USE]                                                                              |
| -------------------------------------------------------------- | -------------- | ---------------------------------------------------------------------------------- |
| `to_thread.run_sync(fn, *args, limiter=)`                      | `lanes.py`     | thread-offload for pg8000 fence and `Admit.offload` CPU kernels                    |
| `to_thread.current_default_thread_limiter()`                   | `lanes.py`     | default `CapacityLimiter` when policy carries `Nothing`                            |
| `CapacityLimiter(total_tokens)`                                | `lanes.py`     | one per `LanePolicy` identity; `functools.cache`-memoised; overridable per offload |
| `create_task_group()`                                          | `lanes.py`     | one structured task group per `drain` call                                         |
| `move_on_after(delay, shield=False)`                           | `lanes.py`     | per-unit deadline scope inside the task group                                      |
| `create_memory_object_stream[T](max_buffer_size)`              | `lanes.py`     | result channel collecting `DrainReceipt` components from task arms                |
| `run_process(command, *, check=False, ...)`                    | existing rails | already in `schema.py`; thread-safe under `PROC` retry class                      |
| `BrokenWorkerProcess` / `BrokenResourceError` / `ClosedResourceError` | `rails.py` | `resource` classification row in `CLASSIFY`                               |
| `TimeoutError`                                                 | `rails.py`     | `deadline` classification row in `CLASSIFY`                                        |

Hand-rolled today: `schema.py` wraps `anyio.run_process` in a bare `try/except OSError` returning `fault(...)` — this must compose through `async_boundary("apply", ...)` instead, lifting to `RuntimeRail` for domain-internal consumers while the CLI boundary still projects to `Envelope`.

`fail_after` is explicitly removed from domain code: `move_on_after` inside `drain` returns a `DrainReceipt` with `cancelled` count on deadline trip; `fail_after` raises and propagates an exception, which conflicts with the `RuntimeRail` return model. Never use `fail_after` in domain code; it is a CLI-boundary or process-level primitive only. `schema.run(SchemaOp.APPLY)` uses `anyio.move_on_after` (not `fail_after`) for per-step deadlines; a tripped scope sets `scope.cancelled_caught` and records a sentinel exit code, producing a valid `DrainReceipt` with non-zero `cancelled` count rather than raising. `anyio.fail_after` is reserved for whole-operation boundaries at the CLI layer (e.g., cloud-sync's `run` function wraps the full operation in `anyio.fail_after(cfg.cloud.op_timeout_s)` at the `Envelope`-returning boundary, not inside domain functions).

### `stamina` (`libs/python/.api/stamina.md`)

| [MEMBER]                                                    | [OWNER]          | [USE]                                                                            |
| ----------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------- |
| `AsyncRetryingCaller(attempts=..., timeout=..., wait_*=...)` | `resilience.py` | construct the reusable caller; policy frozen at construction                     |
| `AsyncRetryingCaller.on(target)` → `BoundAsyncRetryingCaller` | `resilience.py` | bind exception target; `guard()` caches the bound caller per `RetryClass` member |
| `retry_context(on=, **schedule)`                            | `resilience.py`  | `retrying(cls)` rebuilds per call for `async for` inline blocks                  |
| `Attempt.num` / `Attempt.next_wait`                         | `receipts.py`    | per-attempt receipt facts                                                        |
| `instrumentation.RetryDetails`                              | `receipts.py`    | `retry_num`/`wait_for`/`waited_so_far`/`caused_by` fields read by receipt hook   |
| `instrumentation.RetryHookFactory`                          | `resilience.py`  | `RetryReceiptHook` factory that mints a `fact`-phase `retry` receipt on each retry attempt |
| `instrumentation.StructlogOnRetryHook`                      | `resilience.py`  | structlog warning in the `RETRY_HOOKS` stack                                     |
| `instrumentation.set_on_retry_hooks(hooks)`                 | `resilience.py`  | `INSTALL_TABLE[RetryMode.EMIT]` action; process-global hook registration         |
| `set_testing(True)`                                         | `resilience.py`  | `INSTALL_TABLE[RetryMode.TEST]` action; collapses backoff for deterministic specs |
| `ExcOrBackoffHook` / `BackoffHook`                          | `resilience.py`  | the typed `target` field in `Policy`                                             |

Usage clarification for `guard`: `guard(RetryClass.DB)` returns a `BoundAsyncRetryingCaller`. Call pattern: `await guard(RetryClass.DB)(target_coro_fn, *args, **kwargs)` — NOT `@guard(RetryClass.DB)`. The bound caller calls the function and handles retries internally; it does not return a decorated callable. For definition-time decoration, use `@stamina.retry(on=..., **policy.schedule())` directly.

Hand-rolled today: `stack.py` has a bare `try/except (auto.errors.CommandError, httpx.HTTPError, OSError)` → `fault(...)`. This must route through `async_boundary` + `guard(RetryClass.HTTP)` for the Ollama pull, and `guard(RetryClass.PROC)` for spawn-level failures.

### `expression` (`libs/python/.api/expression.md`)

| [MEMBER]                                          | [OWNER]                            | [USE]                                                          |
| ------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------- |
| `Result[T, E]` / `Ok` / `Error`                  | `rails.py`                         | `RuntimeRail[T]` carrier                                       |
| `Option[T]` / `Some` / `Nothing`                 | `lanes.py`                         | `CapacityLimiter` override in `Admit.offload`; `LanePolicy.deadline` |
| `@tagged_union` / `tag()` / `case()`             | `rails.py` `lanes.py` `receipts.py` | every closed union                                             |
| `effect.result[Any, BoundaryFault]()`            | `rails.py`                         | `railed` computation-expression builder for sequential bind    |
| `pipe` / `compose`                               | domain code                        | primary composition surface                                    |
| `Block.of_seq` / `Block.choose` / `Block.fold`   | `lanes.py`                         | drain unit traversal and result accumulation                   |
| `Map.of_seq` / `Map.try_find` / `Map.add`        | `lanes.py` `resilience.py` `receipts.py` | dispatch tables; `POLICY`, `INSTALL_TABLE`, `PHASE_LEVEL`, `LEVEL_METHOD` |
| `Result.to_option` / `Result.swap`               | `lanes.py`                         | split oks vs faults from resolved rails                        |
| `NewType`                                        | `lanes.py`                         | `ContentKey = NewType("ContentKey", str)` branding             |

`Map` is the correct `OWNER_CHOOSER` form for all static definition-time keyed dispatch tables (`ADMIT_TABLE`, `POLICY`, `INSTALL_TABLE`, `PHASE_LEVEL`, `LEVEL_METHOD`). `frozendict` is not admitted in `pyproject.toml` and PEP 603 (stdlib `builtins.frozendict`) was not ratified for py3.15. Every prior reference to `frozendict` in this blueprint is replaced by `expression.Map` for keyed tables and plain `dict[str, object]` for transient evidence projections.

### `structlog` (`libs/python/.api/structlog.md`)

| [MEMBER]                                                                 | [OWNER]        | [USE]                                                          |
| ------------------------------------------------------------------------ | -------------- | -------------------------------------------------------------- |
| `configure(processors=..., wrapper_class=...)`                           | `receipts.py`  | one process-global pipeline call in `Signals.configure`        |
| `make_filtering_bound_logger(min_level)`                                 | `receipts.py`  | compile sub-threshold calls to no-ops                          |
| `contextvars.merge_contextvars`                                          | `receipts.py`  | first processor; ambient context propagation                   |
| `contextvars.bind_contextvars(**kw)` / `bound_contextvars(**kw)`        | domain         | scoped per-rail context (e.g., `rail="db"`, `op="query"`)      |
| `processors.JSONRenderer(serializer=...)`                                | `receipts.py`  | production output; paired with `BytesLoggerFactory`            |
| `dev.ConsoleRenderer`                                                    | `receipts.py`  | dev output selected by `ObservabilityConfig.format`            |
| `processors.TimeStamper` / `processors.dict_tracebacks` / `processors.add_log_level` | `receipts.py` | pipeline chain processors                          |
| `testing.capture_logs()`                                                 | specs          | test sink without a real logger                                |
| `BytesLoggerFactory`                                                     | `receipts.py`  | production JSON byte sink                                      |

Hand-rolled today: `admin/__main__.py` and each rail emit `Envelope` JSON to stdout. That stays. `structlog` targets `stderr` diagnostics only, already mandated by `AGENTS.md` and `ObservabilityConfig`.

### `msgspec` (`libs/python/.api/msgspec.md`)

| [MEMBER]                                                           | [OWNER]       | [USE]                                                               |
| ------------------------------------------------------------------ | ------------- | ------------------------------------------------------------------- |
| `Struct(frozen=True, gc=False)`                                    | existing only | `DrainReceipt` and `Policy` are NOT msgspec structs — see §02       |
| `UNSET` / `UnsetType`                                              | (removed)     | `Policy` uses `float | None` not `UNSET`; wire structs unaffected   |
| `json.Encoder(enc_hook=repr, order="deterministic").encode`        | `receipts.py` | renderer serializer for the structlog JSON pipeline                 |
| `msgspec.DecodeError` / `ValidationError`                          | `rails.py`    | `boundary` classification row in `CLASSIFY`                         |

`DrainReceipt` and `Policy` are `@dataclass(frozen=True, slots=True)` owners, not `msgspec.Struct`. They carry `expression.Block`, `expression.Map`, `Option`, `type[Exception]`, and `Callable` fields — none of which msgspec can encode. `msgspec.Struct(frozen=True, gc=False)` is reserved for wire/egress shapes that are encoded/decoded across a process or network boundary. Internal domain evidence that never crosses a wire must not use `msgspec.Struct`.

### `psutil` (`libs/python/.api/psutil.md`)

| [MEMBER]                                            | [OWNER]        | [USE]                                                   |
| --------------------------------------------------- | -------------- | ------------------------------------------------------- |
| `Process()` (own process)                           | `receipts.py`  | RSS snapshot in `@drained` decorator at drain exit      |
| `Process.oneshot()` + `memory_info().rss`           | `receipts.py`  | one syscall per drained emit; guarded `NoSuchProcess`/`AccessDenied` |

RSS is passed into `Receipt.drained` as the third tuple element `rss_bytes: int`. On `NoSuchProcess`/`AccessDenied`, the aspect emits `rss_bytes=0` rather than failing the drain.

---

## [04]-[RAILS + ASPECTS]

### Rail hierarchy

```
RuntimeRail[T]   = Result[T, BoundaryFault]     ← domain-internal; lanes + resilience
Envelope                                         ← CLI stdout wire; model.py; projects from Status
Result[QueryResult, DbFault]                     ← db.py only; lifts to Envelope at CLI boundary
```

Domain code inside `admin/runtime/` returns `RuntimeRail[T]`. CLI command handlers in `admin/__main__.py` project through a helper that converts `Error(BoundaryFault)` → `fault(...)` `Envelope`. The two shapes are never collapsed.

### Fault vocabulary — `BoundaryFault`

Closed `FaultTag` literal: `config | resource | deadline | api | boundary | aggregate`. The `CLASSIFY` table (ordered `tuple` of `(exception-family-tuple, builder)` pairs, declared in `rails.py` `[CONSTANTS]`) is the sole conversion path. Adding a new exception family is one row, never a new function or a new `catch` parameter.

```
(anyio.BrokenWorkerProcess, anyio.BrokenResourceError, anyio.ClosedResourceError) → resource
(anyio.TimeoutError,)                                                               → deadline
(msgspec.DecodeError, msgspec.ValidationError)                                      → boundary
(OSError,)                                                                          → boundary
(beartype.roar.BeartypeCallHintViolation,)                                          → api
(Exception,)                                                                        → boundary   # last row; catch-all
```

### `anyio` concurrency boundary

- `create_task_group()` — only structured task groups; never `asyncio.gather` or `asyncio.create_task`.
- `move_on_after` — every drain unit is deadline-bounded; `fail_after` is never used in domain code (a deadline trip returns `DrainReceipt` with `cancelled` count, not a raw exception).
- `CapacityLimiter` — one per `LanePolicy` identity, memoised by `functools.cache`; shared across drain + offload on that policy; per-`Admit.offload` override carries an `Option[CapacityLimiter]` inside the case payload.
- `to_thread.run_sync(fn, limiter=)` — thread offload for pg8000 and for `Admit.offload` kernels; explicit `limiter` argument on every call.

### Aspects — `@receipted` and `@drained`

`@receipted(owner: str, phase: Phase, redact: Redaction | None = None)` wraps a `ReceiptContributor`-returning operation. The `ReceiptContributor` protocol is declared in `receipts.py` `[MODELS]` and requires one method: `contribute() -> tuple[str, dict[str, object]]` (returns `(subject, facts_dict)`). On return, the aspect calls `Signals.emit(Receipt.of(owner, ("emitted", subject, facts_dict)))`. Sync and async wrappers share one factory; `asyncio.iscoroutinefunction` discriminates the wrapper body. No inline `emit` call survives inside a `@receipted` body.

`@drained(owner: str, redact: Redaction | None = None)` wraps an `async def` that calls `drain(...)`. On exit it: (1) probes `psutil.Process().oneshot()` + `memory_info().rss` (with `NoSuchProcess`/`AccessDenied` guarded to 0), (2) calls `Signals.emit(Receipt.of(owner, (receipt, rss_bytes)))` where the two-element tuple discriminates the `drained` case in `Receipt.of`. Applied via `functools.wraps`.

Stacking order: `@drained` is outermost (drain lifetime); `@receipted` is per-operation inner. A definition decorated with both has `@drained` applied last (outermost in effect).

`@stamina.retry` / `guard(cls)` — retry is always a `stamina`-mediated mechanism, never a manual `for` loop with `anyio.sleep`.

`structlog.contextvars.bind_contextvars(**kw)` — ambient context binds at the boundary scope; never repeated per log call.

---

## [05]-[PAYLOADS + TABLES]

### `@dataclass(frozen=True, slots=True)` owners (domain-internal; NOT wire-encoded)

```python
# lanes.py
@dataclass(frozen=True, slots=True, kw_only=True)
class LanePolicy:
    capacity: int
    deadline: Option[float] = field(default=Nothing)

@dataclass(frozen=True, slots=True)
class DrainReceipt:
    accepted: int
    completed: int
    cancelled: int
    rejected: int
    values: Block[object] = field(default_factory=Block.empty)
    cache: Map[ContentKey, object] = field(default_factory=Map.empty)
    faults: Block[BoundaryFault] = field(default_factory=Block.empty)
    hit: int = 0

# resilience.py
@dataclass(frozen=True, slots=True, kw_only=True)
class Policy:
    attempts: int
    timeout: float
    target: stamina.ExcOrBackoffHook
    wait_initial: float | None = None
    wait_max: float | None = None
    wait_jitter: float | None = None
    wait_exp_base: float | None = None
```

These three are never wire-encoded; they carry `expression` collection types and `Callable`/exception-type fields incompatible with msgspec. `@dataclass(frozen=True, slots=True)` is the correct `OWNER_CHOOSER` row for internal value objects with no wire lifecycle.

### `msgspec.Struct` owners (wire/egress only — existing shapes unchanged)

The existing `msgspec.Struct(frozen=True, gc=False)` shapes (`Envelope`, `Report`, `Row`, `Detail` subclasses, `QueryResult`, `DbFault`) remain unchanged. The runtime domain adds no new `msgspec.Struct` owners.

### Correspondence tables — `expression.Map` throughout

All definition-time keyed dispatch tables use `expression.Map` (persistent keyed structure, `Map.of_seq`, `Map.try_find`). `frozendict` is not admitted and PEP 603 was not ratified for py3.15; `MappingProxyType` is rejected by table-dispatch law.

```
ADMIT_TABLE : Map[AdmitTag, tuple[KeyFn, MakeFn]]     — in lanes.py [TABLES]
POLICY      : Map[RetryClass, Policy]                  — in resilience.py [TABLES]; keyed on enum member, not .value
INSTALL_TABLE: Map[RetryMode, Callable[[], None]]      — in resilience.py [TABLES]
PHASE_LEVEL : Map[Phase, LogLevel]                     — in receipts.py [TABLES]
LEVEL_METHOD: Map[LogLevel, tuple[LevelMethod, LevelMethod]] — in receipts.py [TABLES]
CLASSIFY    : tuple[tuple[tuple[type[Exception], ...], Callable[[str, str], BoundaryFault]], ...] — in rails.py [CONSTANTS]; ordered linear-scan
```

`CLASSIFY` uses a plain `tuple` of pairs, not `Map`, because it is an ordered linear scan (first match wins) and `Map` is unordered. Every other table uses `Map` because lookup is by key, not by order.

### `pydantic` owners (existing, extended not replaced)

`MaghzSettings` already owns every environment value. No additional `BaseSettings` subclass is added; `ObservabilityConfig.format` (`"json"` | `"console"`) selects the structlog renderer in `Signals.configure`.

### Typed receipts per rail

Each CLI rail declares one `Detail` subclass (already in place: `LedgerDetail`, `SchemaDetail`, `StackDetail`, `SyncDetail`). These are the CLI typed receipts; they do not implement `ReceiptContributor`. Domain-internal operations that emit evidence implement `ReceiptContributor` (declared in `receipts.py`). The `ReceiptContributor` protocol surface is available to all domains that compose on `admin/runtime/receipts.py`.

---

## [06]-[DEPS]

No new packages are added. `frozendict` is explicitly NOT admitted: PEP 603 was not ratified for py3.15 stdlib, and `expression.Map` serves all keyed dispatch table needs. If a future domain requires immutable dict with O(1) lookup (rather than AVL-tree traversal), admit `frozendict` at that point with a floor pin.

All required capability is already admitted in `pyproject.toml`:

| [PACKAGE]    | [VERSION FLOOR] | [BAND]  | [CAPABILITY MINED]                                                                              |
| ------------ | --------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `anyio`      | `>=4.14.0`      | runtime | `CapacityLimiter`, `move_on_after`, `create_task_group`, `create_memory_object_stream`, `to_thread.run_sync(limiter=)` — NOT yet used with explicit `limiter` in `db.py` |
| `stamina`    | `>=26.1.0`      | runtime | `AsyncRetryingCaller`, `BoundAsyncRetryingCaller`, `retry_context`, `RetryHookFactory`, `set_on_retry_hooks`, `set_testing` — currently zero-used; `schema.py` and `stack.py` have bare try/except |
| `expression` | `>=5.6.0`       | runtime | `@tagged_union`/`tag`/`case`; `Block`; `Map`; `effect.result`; `NewType` — `Result`/`Ok`/`Error` already in `db.py`; `Block`/`Map`/`@tagged_union` are zero-used today |
| `structlog`  | `>=26.1.0`      | runtime | `configure`/`make_filtering_bound_logger`/`bind_contextvars`/`JSONRenderer`/`BytesLoggerFactory`/`dict_tracebacks` — currently unconfigured |
| `msgspec`    | `>=0.21.1`      | runtime | `json.Encoder(enc_hook=repr, order="deterministic")` for structlog renderer — basic `Struct`/`json.encode` already used |
| `psutil`     | `>=7.2.2`       | runtime | `Process().oneshot()` + `memory_info().rss` — zero-used today                                   |
| `keyring`    | (no floor pin)  | runtime | `keyring.errors.KeyringLocked` as `SECRET` retry target — reserved for VPS credential path      |

`.api` catalog note: `keyring` has a Rasm catalog at `libs/python/runtime/.api/keyring.md`. Before the realize pass, verify `KeyringLocked` class path on the installed version. All other packages have current catalogs.

---

## [07]-[SEAMS]

Every seam names both this domain (`runtime`) and the counterpart domain it touches. Counterpart blueprint owners are expected to align their shapes to the canonical owners declared here.

```
{domains: ["runtime", "db"], claim: "admin/db.py query() returns Result[QueryResult, DbFault]; the realize pass threads the pg8000 fence through guard(RetryClass.DB) imported from admin/runtime/resilience — the existing-rails direct @stamina.retry on _run_blocking is removed and replaced by this canonical surface. The two-phase lift: db.query returns Result[QueryResult, DbFault] pre-runtime; when the runtime domain lands, async_boundary('query', ...) wraps it to lift DbFault to BoundaryFault for domain-internal consumers as RuntimeRail[QueryResult] = Result[QueryResult, BoundaryFault]; DbFault.envelope() remains the CLI-projection helper and DbFault is NOT eliminated. The Boundary literal in admin/db.py is extended in place with 'ingest'/'embed'/'search' when those rails land; the runtime domain does NOT declare a parallel Boundary type."}

{domains: ["runtime", "existing-rails"], claim: "The existing-rails blueprint's local retry_boundary aspect (admin/db.py [COMPOSITION]) is superseded by guard(RetryClass.*) from admin/runtime/resilience. The existing-rails realize pass imports guard and removes its own local aspect."}

{domains: ["runtime", "schema"], claim: "admin/rails/schema.py apply() uses bare try/except OSError → fault(); the realize pass routes the spawn fence through async_boundary('apply', ...) + guard(RetryClass.PROC) so transient spawn failures retry, returning RuntimeRail[SchemaEvidence] at domain level and projecting to Envelope only at the CLI handler."}

{domains: ["runtime", "stack"], claim: "admin/rails/stack.py run() uses bare try/except (CommandError, HTTPError, OSError); the realize pass routes the Pulumi fence through async_boundary + PROC class and the Ollama pull through async_boundary + guard(RetryClass.HTTP) with the BackoffHook reading the retry_after header, returning RuntimeRail[StackEvidence] at domain level."}

{domains: ["runtime", "sync"], claim: "admin/rails/sync.py _heptabase() uses bare try/except OSError and returns DbFault; the realize pass moves the heptabase CLI spawn fence to async_boundary('heptabase', ...) + guard(RetryClass.PROC) returning RuntimeRail so transient CLI spawn failures retry before the CLI boundary projects to Envelope."}

{domains: ["runtime", "automation"], claim: "The automation domain composes drain(policy, units, cache) with Admit.bare / Admit.keyed / Admit.retried / Admit.offload as its unit-of-work admission primitive; DrainReceipt[AutomationReceipt] is the canonical result carrier; drain_receipt.values[0] is the inner AutomationReceipt written to the NDJSON ledger — the DrainReceipt metadata (accepted/cancelled/hit) flows to structlog context only, not the NDJSON line; RuntimeRail[T] is the canonical typed rail; ContentKey = NewType('ContentKey', str) is shared between automation and cloud-sync domains. The _LANE_POLICIES map maps lane keys to LanePolicy instances; unknown lane keys are rejected at _decode_spec admission, never silently falling back to default. The _governor_aspect runs outermost before @drained borrows any LanePolicy token; admission_denied and lane_overflow faults return before any drain lifecycle begins. engine.py composes guard(RetryClass.HTTP) and guard(RetryClass.DB) as BoundAsyncRetryingCaller instances; no @stamina.retry(...) call appears directly in engine.py."}

{domains: ["runtime", "remote"], claim: "The remote domain composes guard(RetryClass.SECRET) for keyring-backed credential reads and guard(RetryClass.HTTP) for outbound HTTP and SSH transient faults (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError are structurally equivalent to httpx.ConnectError and are retried under RetryClass.HTTP's policy). async_boundary('remote', ...) is the single fault-lift at every remote I/O edge. The RetryClass.HTTP policy target must cover asyncssh transient exception types alongside httpx transients; if the POLICY table's target is typed as a specific httpx exception set, the remote domain's seam requires broadening to accept asyncssh transients within the same RetryClass.HTTP policy (preferred) or the addition of RetryClass.SSH as a distinct class. The CLASSIFY table rows for asyncssh are added by the remote implement pass (see §02 ADTs above)."}

{domains: ["runtime", "cloud-sync"], claim: "The cloud-sync domain uses drain with Admit.retried cases carrying RetryClass.PROC for rclone process fences, threading the ContentKey-keyed session cache to short-circuit already-synced artifacts across multi-stage DrainReceipt fronts. DrainReceipt[_RemoteResult] is the canonical result carrier from the cloud-sync drain phase; the domain never opens a raw anyio.create_task_group(). CloudSyncDetail (tag='cloud') is emitted inside the shared Envelope contract; the runtime receipt consumer dispatches on detail.tag == 'cloud' and projects transferred, errors, checks, elapsed_s, dump_path/restored_from (msgspec.UNSET-defaulting) as named evidence fields."}

{domains: ["runtime", "mcp"], claim: "The MCP domain composes Signals.emit and Receipt.of as its structured diagnostic surface; BoundaryFault is the typed error the MCP handler lifts through async_boundary at the tool call edge, projecting to Envelope for the CLI channel. McpFault (the mcp domain's own closed @tagged_union) projects to BoundaryFault.boundary at the async_boundary conversion point; BoundaryFault is the domain-internal rail type, McpFault is the operation-scoped fault vocabulary."}
```

---

## [08]-[PORTABILITY/VPS]

The Hostinger VPS (the live operator service account) touches this substrate through two seams:

**Credential boundary** — `keyring` already admitted. On the VPS, `MAGHZ_DATABASE_DSN` and service tokens may arrive via keyring (OS keychain), environment variables, or gitignored `.env`. `MaghzSettings` already resolves from `env_file=".env"` + env vars — no new settings surface is needed. The `SECRET` retry class (`RetryClass.SECRET`) guards `keyring.errors.KeyringLocked` + `OSError` on any tier that probes the keychain; the `stamina` `wait_initial` widens so a locked keyring retries after a brief OS handshake.

**Bootstrap and device-code flow** — no interactive TTY on the VPS. Settings carry the DSN and tokens directly; device-code is a future automation domain concern. `admin/runtime/` has no bootstrap surface of its own.

**Token caches** — gitignored under `.cache/`; `MaghzSettings.cache_dir` already owns the path. No runtime module writes to `.cache/` directly.

**Colima / Docker runtime** — `stack.py` Pulumi operations run only locally (Colima). On the VPS, the infra channel is absent; the `StackOp` rail would return `Status.UNSUPPORTED`. This is a CLI boundary concern, not a runtime module concern.

**structlog on the VPS** — `ObservabilityConfig.format = "json"` is the default and must be the VPS default. `ConsoleRenderer` is dev-only, selected by `format = "console"`.

---

## [09]-[ACCEPTANCE]

The gate signals for the implement pass:

- `ruff check admin/runtime/ --select ALL` with the existing `pyproject.toml` ignore set: zero diagnostics.
- `ty check` (the binding type gate): zero errors over `admin/`.
- `mypy --config-file pyproject.toml admin/` (advisory): zero errors on the new modules; existing mypy overrides for `pg8000` remain.
- Runtime verbs that must fire:
  - `drain(LanePolicy(capacity=4), Block.of_seq([Admit(bare=coro)]), Map.empty())` returns a `DrainReceipt` with `accepted == 1` and `completed == 1`.
  - `drain(LanePolicy(capacity=4), Block.of_seq([Admit(offload=(cpu_fn, Nothing))]), Map.empty())` returns a `DrainReceipt` with `accepted == 1` and `completed == 1` via thread-offload.
  - `guard(RetryClass.DB)` returns a `BoundAsyncRetryingCaller`; calling it twice returns the same cached instance (identity equality via `functools.cache`).
  - `Signals.emit(Receipt.of("db", BoundaryFault(boundary=("query", "timeout"))))` writes one structured JSON line to the configured logger without raising.
  - `async_boundary("test", lambda: anyio.sleep(0))` returns `Ok(None)`.
  - `install(RetryMode.TEST)` → `stamina.is_testing()` is `True`.
  - `INSTALL_TABLE.try_find(RetryMode.EMIT).default_value(lambda: None)()` sets the process-global hook list.
- Receipts that must materialize:
  - `DrainReceipt` with non-zero `rejected` count carries a `Block[BoundaryFault]` with at least one addressable fault.
  - `Receipt.of("db", BoundaryFault(boundary=("query", "timeout")))` mints a `rejected` case projecting a `warning`-level line carrying `subject`/`detail` keys.
  - On a retry (guarded `HTTP` or `DB` class with a transient exception), `RetryDetails` fields (`retry_num`, `wait_for`, `waited_so_far`, `caused_by`) materialize as a `fact`-phase `retry` receipt carrying a `dict[str, object]` payload.
  - `@drained` on a completed drain call produces a `drained`-case `Receipt` carrying non-negative `rss_bytes`; `rss_bytes == 0` only when `psutil` access is denied, never as a default.
