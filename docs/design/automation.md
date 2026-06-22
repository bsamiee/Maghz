# [AUTOMATION_DESIGN]

Decision-complete design note for `admin/automation/`. Working material, not durable contract;
the schema, the `maghz` CLI, and the produced module tree carry the binding truth.

---

## [01]-[OWNERS]

Two modules under `admin/automation/`. Both compose on the canonical runtime substrate
(`admin/runtime/`) and register the new `_automation` sub-`App` on the existing `app`.

**`admin/automation/model.py`** — `[TYPES]` + `[MODELS]` + `[ERRORS]`

Owns every type that crosses module boundaries: the closed `Trigger` tagged union
(`Watch | Schedule | Manual`), the closed `Action` tagged union
(`AgentAction | Notify | Embed | Sync`), the `AutomationSpec` wire record that pairs one
`Trigger` with one `Action`, the `AutomationReceipt` typed receipt the engine emits (a
`Detail` subclass), and the closed `AutomationFault` `@tagged_union` error vocabulary. No
operations live here.

`DeepResearch`, `Refine`, and `CreateEntry` are collapsed into one `AgentAction` case
(COLLAPSE_SCAN [09]: three types share identical fields for one concept). `Sequence` and
`Debounce` are removed — sequencing belongs to n8n workflows, which is the durable automation
layer; the automation engine dispatches one action per trigger cycle. `Debounce` semantics
belong on the `Watch` trigger as its existing `debounce: int` field.

**`admin/automation/engine.py`** — `[SERVICES]` + `[OPERATIONS]` + `[TABLES]` + `[COMPOSITION]`

Owns the single polymorphic `drive(spec, settings)` entrypoint and all coordination:
the `watchfiles.awatch` lane, the `AsyncScheduler` registration (APScheduler 4.x),
the `psutil` governor that gates admission, the `LanePolicy.drain` composition from
`admin/runtime/lanes.py`, the NDJSON ledger writer (via `anyio.to_thread.run_sync`),
the `guard(RetryClass.*)` callers from `admin/runtime/resilience.py`, and the `anyio`
task-group structure enforcing lane isolation. The single `_exec(action, spec) -> AutomationReceipt`
dispatch owns all action execution arms under one total `match` and returns a fully-populated
`AutomationReceipt` per arm.

No third module. `admin/__main__.py` mounts the new `_automation` sub-`App`
(one `app.command(sub_app)` call) with one verb: `run`. The `--spec` JSON argument
carries the complete `AutomationSpec`; the trigger variant encoded in `spec.trigger`
determines which lane fires inside `drive`. No `watch` and `schedule` CLI aliases — those
are redundant one-hop surfaces over `trigger` type discrimination (COLLAPSE_SCAN [01],
ONE_HOP_RESOLUTION). The rails `__init__.py` re-exports `drive` alongside the existing
rail callables.

---

## [02]-[ADTs]

### Trigger (tagged union, `model.py` `[TYPES]`)

```python
# discriminant: tag_field="type", frozen=True, gc=False on all leaves
class Watch(msgspec.Struct, frozen=True, gc=False, tag="watch"):
    paths: tuple[str, ...]          # one or more absolute paths
    filter: Literal["default", "python", "none"] = "default"
    debounce: int = 1600            # ms; feeds watchfiles.awatch(debounce=)
    recursive: bool = True

class Schedule(msgspec.Struct, frozen=True, gc=False, tag="schedule"):
    cron: str                        # standard crontab expression
    jitter: int = 0                  # seconds; feeds CronTrigger(jitter=)
    timezone: str = "UTC"

class Manual(msgspec.Struct, frozen=True, gc=False, tag="manual"):
    pass                             # one-shot immediate execution

type Trigger = Watch | Schedule | Manual
type TriggerTag = Literal["watch", "schedule", "manual"]
```

Total `match` site in `engine._resolve_trigger`: all three arms explicit,
`assert_never` on the default arm. No string-kind comparison.

### Action (tagged union, `model.py` `[TYPES]`)

```python
# discriminant: tag_field="kind", frozen=True, gc=False on all leaves

class AgentSkill(StrEnum):
    DEEP_RESEARCH  = "deep_research"
    REFINE         = "refine"
    CREATE_ENTRY   = "create_entry"

class AgentAction(msgspec.Struct, frozen=True, gc=False, tag="agent"):
    skill: AgentSkill                # collapses DeepResearch | Refine | CreateEntry
    domain: str                      # domain slug
    params: msgspec.Raw = msgspec.Raw(b"null")   # deferred MCP/skill params

class Notify(msgspec.Struct, frozen=True, gc=False, tag="notify"):
    channel: Literal["stderr", "ndjson"]
    message: str

class Embed(msgspec.Struct, frozen=True, gc=False, tag="embed"):
    concept: str | None = None       # None = sweep all pending; str = single-concept enqueue

class Sync(msgspec.Struct, frozen=True, gc=False, tag="sync"):
    op: Literal["diff", "generate"]
    concept: str | None = None       # None for diff; required for generate

type Action = AgentAction | Notify | Embed | Sync
type ActionTag = Literal["agent", "notify", "embed", "sync"]
```

`DeepResearch`, `Refine`, and `CreateEntry` collapsed into `AgentAction(skill, domain, params)`.
The skill discriminant is `AgentSkill`, a closed `StrEnum`; adding a new research skill is one
new `AgentSkill` member and one new row in the `_AGENT_DISPATCH` table inside `_exec` — no
structural change to the action ADT, no new action case, every consumer untouched.

`Embed.concept` and `Sync.concept` use `str | None` at the wire boundary (msgspec-native). The
engine maps to `Option[str]` inside domain logic at the dispatch arm: `Nothing if concept is None
else Some(concept)`. This eliminates the hand-rolled `enc_hook`/`dec_hook` pair for `Option[str]`
(BOUNDARY-INTEGRITY: custom codec is a hand-rolled serialization concern the law prohibits when a
native msgspec form exists).

`Sequence` and `Debounce` are removed. Sequencing and timing composition are n8n's domain; the
automation engine dispatches one action per trigger cycle. Retaining them would seed an embryonic
mini-workflow engine inside the action ADT that would grow uncontrollably (ANTICIPATORY-COLLAPSE:
`Debounce(action=Sequence([...]))` already violates modal-arity and forces recursive Raw decode).

Total `match` in `engine._exec(action, spec)`: all four arms explicit (`AgentAction`, `Notify`,
`Embed`, `Sync`), `assert_never` on the default arm. One function — no sibling family.

### AutomationSpec (wire record, `model.py` `[MODELS]`)

```python
class AutomationSpec(msgspec.Struct, frozen=True, gc=False):
    trigger: Trigger                 # tagged union resolved by msgspec
    action: Action                   # tagged union resolved by msgspec
    lane: str = "default"            # LanePolicy key; validated at admission against cfg.automation.lane_keys
    id: str = msgspec.field(default_factory=lambda: str(uuid.uuid4()))
```

Decoded from JSON via `msgspec.json.Decoder(type=AutomationSpec)`. The trigger
and action tagged unions share `tag_field` names that do not collide; msgspec
resolves each independently by their respective discriminant fields.

`spec.lane` is validated against `cfg.automation.lane_keys` at the `_decode_spec`
admission boundary. An unknown lane key produces `AutomationFault(spec_decode=(spec_id, "unknown lane"))`,
not a silent fallback to `"default"`. The admission gate is the `cyclopts.Parameter(converter=)`
shim; it rejects unknown lanes before the spec reaches `drive`.

### AutomationReceipt (typed receipt, `model.py` `[MODELS]`)

```python
class AutomationReceipt(Detail, frozen=True, tag="automation"):
    spec_id: str
    trigger_tag: TriggerTag          # closed literal; never a bare str
    action_tag: ActionTag            # closed literal; never a bare str
    agent_skill: AgentSkill | None   # non-None only for AgentAction arm
    lane: str
    fired_at: str                    # ISO-8601 UTC
    attempt: int
    elapsed_ms: float
    rows_affected: int | None = None # Sync/Embed actions only
    job_id: str | None = None        # AgentAction: pgmq job row id
    cpu_percent: float | None = None # psutil governor snapshot at admission
    memory_rss_mb: float | None = None
```

`agent_skill` is a new field narrowing which skill fired within `AgentAction`. It is `None`
for all non-agent actions and a closed `AgentSkill` member otherwise. This eliminates the need
for consumers to decode the `params` blob to know which skill ran.

`trigger_tag` and `action_tag` carry the bounded `Literal` types, not bare `str`.

`_exec(action, spec) -> AutomationReceipt` returns a fully-populated receipt per arm. Each arm
constructs the receipt from the spec fields plus its action-specific fields (`rows_affected`,
`job_id`, `agent_skill`). The engine never assembles the receipt outside `_exec`.

### AutomationFault (@tagged_union, `model.py` `[ERRORS]`)

```python
type AutomationFaultKind = Literal[
    "spec_decode",       # msgspec.DecodeError or unknown lane at admission
    "admission_denied",  # psutil governor threshold exceeded
    "lane_overflow",     # LanePolicy at capacity; action deferred (Watch) or skipped (Manual)
    "action_transient",  # stamina-retried transient failure exhausted
    "action_permanent",  # non-retryable action body failure
    "trigger_spawn",     # watchfiles / scheduler initialization failure
    "agent_call",        # MCP/skill invocation non-retryable failure
]

@tagged_union(frozen=True)
class AutomationFault:
    tag: AutomationFaultKind = tag()
    spec_decode: tuple[str, str] = case()      # (spec_id_or_empty, detail)
    admission_denied: tuple[str, str] = case() # (spec_id, detail)
    lane_overflow: tuple[str, str] = case()    # (spec_id, lane)
    action_transient: tuple[str, str] = case() # (spec_id, detail)
    action_permanent: tuple[str, str] = case() # (spec_id, detail)
    trigger_spawn: tuple[str, str] = case()    # (lane, detail)
    agent_call: tuple[str, str] = case()       # (spec_id, detail)
```

`lane_overflow` is a new case for LanePolicy capacity exhaustion. This is distinct from
`admission_denied` (psutil ceiling): it means all lane tokens are borrowed and the action
cannot be scheduled this cycle. The NDJSON ledger records a `Status.SKIP` receipt for the
skipped cycle; agents can detect saturation trends from the ledger.

`AutomationFault` is a `@tagged_union` from `expression` — domain-internal only,
never serialized directly. Projection to `Envelope` happens exactly once at the CLI boundary
in `drive`, via a match-collapse helper in `engine.py [OPERATIONS]`:

```python
def _fault_envelope(fault: AutomationFault) -> Envelope:
    match fault:
        case AutomationFault(tag="spec_decode"):
            spec_id, detail = fault.spec_decode
            return core_fault(detail, {"kind": "spec_decode", "spec_id": spec_id})
        ...
        case unreachable:
            assert_never(unreachable)
```

`Result[AutomationReceipt, AutomationFault]` is the internal rail type from `_exec` to `drive`.
`drive` projects through `_fault_envelope`; it never raises into the CLI.

---

## [03]-[.api SURFACE]

### `watchfiles` (`libs/python/runtime/.api/watchfiles.md`)

`awatch(*paths, watch_filter, debounce, step, stop_event, recursive)` — the async
generator that feeds the Watch trigger lane. The `stop_event` is an `anyio.Event`
owned by the engine's cancel scope; closing the scope sets it and the generator
exits cleanly.

Filter selection is a correspondence table in `engine.py [TABLES]`:
`"default" -> DefaultFilter()`, `"python" -> PythonFilter()`, `"none" -> None`.
One `watch_filter=` kwarg; no per-event consumer filtering.

`Change` enum matching in the receipt: `change.raw_str()` feeds structlog context
alongside the path, not a receipt field (the receipt carries the static `TriggerTag` literal).

Nothing currently in `admin/` watches the filesystem; there is no existing surface
to replace — this is new capability.

### `APScheduler` 4.x (`libs/python/runtime/.api/apscheduler.md`)

APScheduler 4.x is the current async-first release with native anyio support. The 3.x
`AsyncIOScheduler` is asyncio-native only and couples the engine to the asyncio backend,
violating the anyio mandate. The 4.x `AsyncScheduler` uses `anyio.create_task_group`
internally and integrates cleanly with the engine's `anyio` task group. Any 3.x pin must
be removed.

`AsyncScheduler` — one scheduler instance, started as an `async with` context manager
inside `engine._schedule_lane`, sharing the anyio/asyncio event loop.

```python
# APScheduler 4.x surface
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger

async with AsyncScheduler() as scheduler:
    await scheduler.add_schedule(
        func,
        CronTrigger.from_crontab(spec.cron, timezone=spec.timezone),
        id=spec_id,
        conflict_policy=ConflictPolicy.replace,
        misfire_grace_time=120,
    )
    await scheduler.run_until_stopped()
```

Job events: subscribe via `scheduler.subscribe(callback, {JobReleased})`. The `JobReleased`
event carries `outcome: JobOutcome`, `scheduled_fire_time`, and `return_value`
(`AutomationReceipt`) or `exception` — the single observability seam for NDJSON ledger
append per fire. `JobOutcome.success`, `JobOutcome.missed` drive the receipt projection.

`JobOutcome.missed` → NDJSON ledger records a `Status.SKIP` receipt for the missed tick.

The scheduler's `async with` context manager owns its own lifecycle; it shuts down cleanly
when its scope exits inside the engine's anyio task group, eliminating the need for
`shutdown(wait=True)` offloaded via `anyio.to_thread.run_sync`.

If `APScheduler` is not yet in `pyproject.toml`, add:

```toml
"apscheduler>=4.0.0",   # scheduling: 4.x AsyncScheduler with native anyio support
```

### `psutil` (`libs/python/.api/psutil.md`)

Resource governor runs at admission (before the `LanePolicy.drain` borrow — see stacking
order in `[04]`). One `Process(os.getpid()).oneshot()` block reads `cpu_percent(interval=None)`
and `memory_info().rss` in a single syscall batch. The reading populates
`AutomationReceipt.cpu_percent` and `AutomationReceipt.memory_rss_mb`. A configurable
threshold pair (`AutomationConfig.cpu_ceil: float`, `AutomationConfig.rss_ceil_mb: float`)
gates admission: if either is exceeded the engine emits `AutomationFault(admission_denied=...)`
and returns `Status.SKIP` (Manual) or defers to the next tick (Watch).

CPU governor uses `interval=None` because the engine owns timing through `awatch`'s debounce
and the scheduler's cron tick — no blocking psutil poll.
`getloadavg` is guarded with `hasattr(psutil, "getloadavg")` before use.

The governor is implemented as a named `@aspect` (`_governor_aspect`) that runs before the
`@drained` borrow — see `[04]` for the corrected stacking order.

### `anyio` (`libs/python/.api/anyio.md`)

`create_task_group()` — the engine spawns three concurrent tasks: `_watch_lane`,
`_schedule_lane`, `_signal_lane` (SIGTERM handler via `open_signal_receiver`). Each
lane is a child task; the `ExceptionGroup` from a failing lane is caught via `except*`
and mapped to `AutomationFault(trigger_spawn=...)`.

`anyio.Event` — the Watch lane's `stop_event`; set by the cancel scope teardown.

`anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT)` — the `_signal_lane`
task awaits the first signal and cancels the task group.

`to_thread.run_sync(fn, limiter=_lane_limiter(lane))` — offloads the blocking NDJSON
ledger `write` call. The `limiter=` kwarg is always explicit.

`move_on_after(delay)` — deadline scope wrapping each `_exec(action, spec)` call inside
`_dispatch_action`; the timeout value comes from `AutomationConfig.action_timeout_s`
(no signature parameter).

### `stamina` via `admin/runtime/resilience.py`

The automation engine does NOT call `@stamina.retry(...)` directly. It composes
`guard(RetryClass.HTTP)` and `guard(RetryClass.DB)` from `admin/runtime/resilience.py`,
which return `BoundAsyncRetryingCaller` instances memoised by `functools.cache` per
`RetryClass` member. The `on=` exception mapping for each class is owned by the `POLICY`
table in `resilience.py` — not hand-rolled per-call-site.

For the agent-invocation transient case (`agent_call`), a `BackoffHook` registered via
`stamina.instrumentation.set_on_retry_hooks` is the retry hook.

`StructlogOnRetryHook` remains active (structlog is already wired in `__main__.py`).

### `msgspec` (`libs/python/.api/msgspec.md`)

`msgspec.json.Decoder(type=AutomationSpec)` — stateful, reused at module level to
decode the `--spec` JSON argument into a typed `AutomationSpec`. One decoder;
`DecodeError` is caught at the cyclopts `Parameter(converter=...)` boundary and
lifted to `AutomationFault(spec_decode=...)` then projected to a `fault` envelope.

`msgspec.Raw` — the `AgentAction.params` field holds opaque sub-payloads; the engine
decodes `Raw` to the appropriate skill's parameter struct only inside the `AgentAction`
dispatch arm that invokes it (via the `_AGENT_DISPATCH` table).

`Decoder.decode_lines` — used by the `ledger` read sub-command to replay the
NDJSON automation log file into typed `AutomationReceipt` rows.

`msgspec.json.encode(receipt)` + `anyio.to_thread.run_sync(fn, limiter=...)` — the
NDJSON append writes the inner `AutomationReceipt` (not the `DrainReceipt` wrapper)
as one `encode`-then-write call per fire. The `DrainReceipt` metadata (accepted/
cancelled/hit counts) flows into structlog context via `structlog.contextvars.bind_contextvars`,
not into the NDJSON line.

No `enc_hook`/`dec_hook` pair for `Option[str]`. `Embed.concept` and `Sync.concept`
are `str | None` at the wire level (msgspec-native); the engine projects to `Option[str]`
inside the dispatch arm.

### `cyclopts` (`libs/python/runtime/.api/cyclopts.md`)

A new `_automation` sub-`App` registered on the existing `app` in `admin/__main__.py`.

One command: `run`. It accepts `--spec` as
`Annotated[AutomationSpec, Parameter(converter=_decode_spec)]`. The trigger variant
encoded in the `AutomationSpec.trigger` field determines which lane fires inside `drive`.

```
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"sync","op":"diff"}}'
maghz automation run --spec '{"trigger":{"type":"watch","paths":["/data"]},"action":{"kind":"agent","skill":"deep_research","domain":"geometry"}}'
maghz automation run --spec '{"trigger":{"type":"schedule","cron":"0 */6 * * *"},"action":{"kind":"embed"}}'
```

The single `run` command drives all three trigger modes. `watch` and `schedule` daemon modes
run until SIGTERM via the `_signal_lane` inside the task group. No redundant `watch` and
`schedule` CLI aliases (ONE_HOP_RESOLUTION: they would each call `drive` with the same spec).

`_decode_spec` is the admission boundary: a `cyclopts.Parameter(converter=)` shim that
calls the stateful decoder, validates `spec.lane` against `cfg.automation.lane_keys`, maps
`msgspec.DecodeError` or unknown-lane errors to `cyclopts.ValidationError`. The lane
validation happens here, at admission, before any state is borrowed.

---

## [04]-[RAILS + ASPECTS]

### Error Rail

`AutomationFault` is a `@tagged_union` (see `[02]-[ADTs]`). `Result[AutomationReceipt, AutomationFault]`
is the internal rail type from `_exec` to `drive`. `BoundaryFault` from `admin/runtime/rails.py`
is NOT used directly as the automation fault type — the automation domain has its own closed
vocabulary with richer case payloads. At the CLI boundary, `drive` projects via
`_fault_envelope(fault)` (total match + `assert_never`).

### anyio Structured-Concurrency Boundary

```
anyio.run(_resolve, drive(spec, cfg))         ← existing meta launcher owns the loop
  └── create_task_group()                     ← engine creates ONE tg per drive() call
       ├── _watch_lane()    (Watch trigger only)
       ├── _schedule_lane() (Schedule trigger only; AsyncScheduler 4.x async with block)
       ├── _signal_lane()   (SIGTERM/SIGINT; always present in daemon modes)
       └── _dispatch_action() → _governor_aspect → LanePolicy.drain → move_on_after → _exec
```

`asyncio.gather` is banned by pyproject.toml's ruff rule; all concurrent spawns are
`tg.start_soon`. The `ExceptionGroup` from a crashing lane is caught via `except*` and
maps to `AutomationFault(trigger_spawn=(lane, str(exc)))`.

### `@aspect` stacking

All cross-cutting concerns on `_dispatch_action` are named aspects that compose via
the `@receipted` and `@drained` patterns from `admin/runtime/receipts.py`. The stacking
order (outer to inner) is:

1. `_governor_aspect` — **outermost**; the psutil admission gate implemented as a named
   `@aspect` decorator. Runs BEFORE any `LanePolicy.drain` token is borrowed. Returns
   `Error(AutomationFault(admission_denied=...))` or `Error(AutomationFault(lane_overflow=...))`
   immediately, without entering the drain phase. The previous design had this inner to
   `@drained`, which is wrong: the drain borrow must not happen if admission is denied.
2. `@drained("automation", redaction)` — `DrainReceipt` emission from `LanePolicy.drain`;
   feeds `psutil` RSS into the drained projection via `admin/runtime/receipts.py`. Runs
   only when the governor passes.
3. `guard(RetryClass.HTTP).on(target)` — wraps each outbound HTTP action body;
   `guard(RetryClass.DB).on(target)` wraps each DB action body. Each is a
   `BoundAsyncRetryingCaller` from `admin/runtime/resilience.py`.
4. `structlog.contextvars.bound_contextvars(spec_id=..., action=..., lane=...)` —
   context manager scope around the dispatch `match`; cleared on exit.
5. NDJSON ledger append — after `_exec` resolves, in `_record_ledger` called inside
   the `@drained` wrapper's exit hook. Writes the inner `AutomationReceipt` (extracted
   from `drain_receipt.values[0]`); never writes the `DrainReceipt` wrapper.

The corrected stacking ensures no lane token is borrowed when admission is denied. The
`DrainReceipt` metadata (accepted/cancelled/hit) goes to structlog context only, not the
NDJSON ledger line.

The `_governor_aspect` is a signature-preserving decorator: it wraps
`_dispatch_action(spec, cfg)` and returns either `Ok(receipt)` or `Error(fault)` without
mutating the wrapped function's signature. It never raises.

---

## [05]-[PAYLOADS + TABLES]

### Wire Owners (`model.py [MODELS]`)

All wire types are `msgspec.Struct(frozen=True, gc=False)` leaves. `AutomationSpec`,
`Watch`, `Schedule`, `Manual`, `AgentAction`, `Notify`, `Embed`, `Sync` are wire structs.

`AutomationReceipt` extends `Detail` (itself a `msgspec.Struct`) and carries
`tag="automation"` for tagged-union dispatch in the `Envelope` report.

`AutomationFault` is a `@tagged_union` from `expression` — domain-internal only,
never serialized directly.

`AgentAction.params: msgspec.Raw` defers skill/MCP parameter decoding to the
action-execution boundary. The engine decodes `Raw` to the appropriate skill's parameter
struct only inside the `AgentAction` dispatch arm, keyed by `action.skill` via the
`_AGENT_DISPATCH` table in `engine.py [TABLES]`.

`Embed.concept` and `Sync.concept` are `str | None` at the wire level. The engine maps
to `Option[str]` inside the dispatch arm: `Nothing if concept is None else Some(concept)`.
No `enc_hook`/`dec_hook` pair.

### Settings (`admin/settings/config.py` extension)

`AutomationConfig(BaseModel)` is added to `MaghzSettings` as a new field:

```python
class AutomationConfig(BaseModel):
    model_config = _GROUP

    max_concurrent: int = Field(default=4, ge=1)           # per-lane LanePolicy capacity
    cpu_ceil: float = Field(default=80.0, gt=0, le=100.0)  # % CPU admission gate
    rss_ceil_mb: float = Field(default=2048.0, gt=0)       # RSS MB admission gate
    action_timeout_s: float = Field(default=120.0, gt=0)   # move_on_after per _exec call
    ledger_file: Path = Path(".artifacts/automation.ndjson")
    lane_keys: tuple[str, ...] = ("default",)              # pre-declared LanePolicy keys
```

`MaghzSettings` gains `automation: AutomationConfig = Field(default_factory=AutomationConfig)`.

`action_timeout_s` is a settings field, not a signature parameter. No `timeout` param
on `drive` or `_dispatch_action`.

### Correspondence Tables (`engine.py [TABLES]`)

```python
# Filter discriminant -> watchfiles filter instance
_WATCH_FILTER: Final[Mapping[str, BaseFilter | None]] = MappingProxyType({
    "default": DefaultFilter(),
    "python":  PythonFilter(),
    "none":    None,
})

# AgentSkill -> skill-dispatch callable
# Each entry is an async callable: (action: AgentAction, spec: AutomationSpec, cfg: MaghzSettings) -> AutomationReceipt
_AGENT_DISPATCH: Final[frozendict[AgentSkill, Callable[...]]]
# populated at module level; one row per AgentSkill member; adding a new skill is one row

# Lane key -> LanePolicy (built at engine init from cfg.automation.lane_keys)
_LANE_POLICIES: Final[Mapping[str, LanePolicy]]
# {key: LanePolicy(capacity=cfg.automation.max_concurrent) for key in cfg.automation.lane_keys}
# unknown lane keys are rejected at admission; no silent fallback
```

`_AGENT_DISPATCH` collapses the three former per-skill dispatch arms into one table. Adding
`AgentSkill.WEB_SEARCH` is one new row; the `AgentAction` arm in `_exec` is unchanged.

No raw `dict[str, CapacityLimiter]` — `LanePolicy` from `admin/runtime/lanes.py` owns
the `CapacityLimiter` lifecycle. The engine composes `LanePolicy.drain(Block.of_seq([Admit.retried(cls, work)]))`;
`DrainReceipt[AutomationReceipt]` is the carrier returned from each dispatch.

### Typed Receipt

`AutomationReceipt` is the ONLY receipt type. The NDJSON ledger appends one
`msgspec.json.encode(drain_receipt.values[0])` line per fire (the inner `AutomationReceipt`,
not the `DrainReceipt` wrapper). The `drive` return type is `Envelope`; the receipt rides
inside `report.detail`.

`trigger_tag: TriggerTag` and `action_tag: ActionTag` carry closed `Literal` types —
never bare `str`. `agent_skill: AgentSkill | None` narrows the `AgentAction` arm.

---

## [06]-[DEPS]

One version change required: APScheduler must be updated from 3.x to 4.x. Every
other dependency is already declared in `pyproject.toml`:
`watchfiles`, `psutil`, `anyio`, `stamina`, `msgspec`, `cyclopts`,
`expression`, `structlog`, `httpx`.

```toml
"apscheduler>=4.0.0",   # scheduling: 4.x AsyncScheduler; native anyio support; breaking API vs 3.x
```

If the lockfile currently pins `apscheduler<4.0`, remove the pin. Verify with `uv lock --check`
after updating. The 3.x `AsyncIOScheduler` + `AsyncIOExecutor` surface documented in the prior
design is rejected: it is asyncio-only and requires `anyio.to_thread.run_sync` to call
`scheduler.shutdown(wait=True)` — a blocking call that must be offloaded. APScheduler 4.x
eliminates this entirely with `async with AsyncScheduler()`.

**`.api` catalog notes for the implement pass:**

- `libs/python/runtime/.api/apscheduler.md` must be rebuilt for the 4.x surface before
  the implement pass: `AsyncScheduler`, `CronTrigger`, `ConflictPolicy`, `JobReleased`,
  `JobOutcome`, `AsyncScheduler.subscribe`, `AsyncScheduler.add_schedule`, `AsyncScheduler.run_until_stopped`.
- `admin/runtime/resilience.py` owns `guard(RetryClass.*)` — no new `.api` entry needed.
- `admin/runtime/lanes.py` owns `LanePolicy.drain` + `Admit` + `DrainReceipt` — no new entry.
- `libs/python/.api/watchfiles.md`, `psutil.md`, `anyio.md`, `stamina.md`, `msgspec.md`, and
  `cyclopts.md` catalogs are all current.

---

## [07]-[SEAMS]

### Trigger ↔ Runtime (runtime)

`LanePolicy.drain(units: Block[Admit[T]])` from `admin/runtime/lanes.py` is the sole
admission primitive for every action dispatch. `Admit.bare`, `Admit.keyed`, `Admit.retried`,
and `Admit.offload` are the four closed `Admit` cases; the engine selects the appropriate
case per action arm. `Admit.retried(RetryClass.HTTP, work)` or `Admit.retried(RetryClass.DB, work)`
is the standard per-action unit; `Admit.offload` is for CPU-kernel thread offloads.
`DrainReceipt[AutomationReceipt]` is the result carrier from each lane; `drain_receipt.values[0]`
is the inner `AutomationReceipt` written to the NDJSON ledger. `ContentKey = NewType("ContentKey", str)`
is shared between the automation and cloud-sync domains as the session-cache key type.
`RuntimeRail[T] = Result[T, BoundaryFault]` is the canonical typed rail at the domain level.
The automation engine is a consumer of the runtime drain primitive; it does not re-declare
`CapacityLimiter` management.

The `anyio.run` invocation that the existing `__main__.py` meta launcher owns is the loop
boundary; the engine's `create_task_group()` is nested inside it. The Watch and Schedule
trigger lanes are structured concurrency participants inside that single `anyio.run` loop;
the automation engine consumes the anyio task-group, `CapacityLimiter` (via `LanePolicy`),
and stop-event contract but never re-declares the loop.

### Sync Action ↔ Heptabase Sync Rail (existing-rails)

The `Sync` action dispatches to `sync.run(cfg, concept=None)` for DIFF semantics and
`sync.run(cfg, concept=spec.concept)` for GENERATE semantics — the canonical single
entrypoint in `admin/rails/sync.py` after the existing-rails collapse. `SyncOp` is
eliminated; presence/absence of `concept` is the full discriminant. The `rails.sync_diff`
and `rails.sync_generate` re-exports no longer exist after the existing-rails realize pass;
the canonical import is `from admin.rails.sync import run as sync_run`. The seam is the
`Envelope` return from `sync_run`; the automation engine reads `envelope.status` and
`envelope.report.detail` (a `SyncDetail` instance) to populate
`AutomationReceipt.rows_affected` from `SyncDetail.drift`. When the cloud-sync domain adds
rclone-backed remote sync verbs, the `Sync` action gains a new `op` literal without
structural change to the automation engine; the cloud-sync domain owns the `CloudSyncDetail`
shape and the automation engine never reads cloud-sync internals directly.

### Embed Action ↔ DB Embed Pipeline (db)

The `Embed` action triggers the in-DB embed pipeline indirectly: it calls
`maghz.embed_enqueue()` and `maghz.embed_drain()` via `admin.db.query`. The seam is
the `db.query` surface and the `concept_embed_pending_idx` partial index. The DB
owns the embed protocol; the automation engine composes `db.query` without knowing
the pipeline internals. `Embed.concept` is `str | None`; `None` maps to the
sweep-all-pending path, `Some(name)` (derived at dispatch from the `str`) maps to a
single-concept enqueue.

### AgentAction ↔ MCP + Integrations (mcp, integrations)

`AgentAction` replaces the three former agent cases. It invokes research skills and MCP
tools keyed by `AgentSkill`. The `params: msgspec.Raw` field carries the skill-specific
parameter payload; the `_AGENT_DISPATCH` table in `engine.py` maps `AgentSkill` to the
callable that decodes `Raw` to the skill's typed struct (defined in the `mcp`/`integrations`
design) and invokes the skill. Each callable in `_AGENT_DISPATCH` is owned by the
`integrations`/`mcp` blueprints; the contract is
`(action: AgentAction, spec: AutomationSpec, cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]`.
The automation engine is skill-agnostic; it reads the result via
`_AGENT_DISPATCH[action.skill](action, spec, cfg)`. `DeepResearch`, `Refine`, and
`CreateEntry` actions carry `params: msgspec.Raw` decoded lazily inside the dispatch arm
by the skill adapter; the adapter returns `Result[AutomationReceipt, AutomationFault]` and
the `mcp`/`integrations` blueprint owns the adapter contract. The `job` table in
`db/schema.sql` receives a row for each agent invocation (populated by the dispatch callable
through `db.query`), with `job.worker_id` referencing the automation engine's registered
worker and `job.msg_id` linking to the pgmq `research` queue message.

Sequence and conditional branching are n8n's domain; the automation engine dispatches one
action per trigger cycle. Multi-step automation composes n8n workflows invoked via a future
`AgentSkill.N8N_TRIGGER` member in `_AGENT_DISPATCH`.

### AutomationReceipt ↔ Ledger Rail (ledger)

The `OWNER` ledger view (`admin/rails/ledger.py` `Kind.OWNER`) already surfaces
worker/job telemetry. The automation engine registers itself as a `worker` row on
first `drive` call. The `AutomationReceipt.job_id` links to `job.id` so `maghz ledger stale`
surfaces exhausted automation jobs alongside manual research jobs. The seam is the `db.query`
call that writes the `worker`/`job` rows; the ledger rail owns the read projection.

### Automation ↔ Runtime (resilience + lanes)

```
{domains: ["automation", "runtime"], claim: "engine.py composes LanePolicy.drain(Block.of_seq([Admit.retried(cls, work)])) from admin/runtime/lanes.py as the sole admission primitive, selecting from Admit.bare / Admit.keyed / Admit.retried / Admit.offload cases. _LANE_POLICIES maps lane keys to LanePolicy instances rather than managing raw CapacityLimiter dicts; unknown lane keys are rejected at _decode_spec admission, never silently falling back to default. DrainReceipt[AutomationReceipt] is the result carrier from each dispatch leg; the inner AutomationReceipt (drain_receipt.values[0]) is the NDJSON ledger payload — DrainReceipt metadata (accepted/cancelled/hit) flows to structlog context only, not the NDJSON line. ContentKey = NewType('ContentKey', str) is shared between automation and cloud-sync domains as the session-cache key type owned by admin/runtime/lanes.py."}

{domains: ["automation", "runtime"], claim: "engine.py composes guard(RetryClass.HTTP) and guard(RetryClass.DB) from admin/runtime/resilience.py as BoundAsyncRetryingCaller instances; no @stamina.retry(...) call appears directly in engine.py."}

{domains: ["automation", "runtime"], claim: "_governor_aspect runs outermost, before @drained borrows a LanePolicy token; admission_denied and lane_overflow faults return before any drain lifecycle begins."}

{domains: ["automation", "existing-rails"], claim: "The Sync action dispatches to sync.run(cfg, concept=None) for DIFF semantics and sync.run(cfg, concept=spec.concept) for GENERATE semantics — the canonical single entrypoint in admin/rails/sync.py after the existing-rails collapse. rails.sync_diff / rails.sync_generate aliases do not exist; the canonical import is from admin.rails.sync import run as sync_run. The automation engine reads envelope.report.detail (a SyncDetail instance) to populate AutomationReceipt.rows_affected from SyncDetail.drift."}

{domains: ["automation", "mcp", "integrations"], claim: "DeepResearch / Refine / CreateEntry actions are collapsed into AgentAction(skill=AgentSkill, ...) with params: msgspec.Raw decoded lazily inside the dispatch arm by the skill adapter. Each _AGENT_DISPATCH callable is owned by the integrations/mcp blueprints; the contract is (action: AgentAction, spec: AutomationSpec, cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]. The automation engine is skill-agnostic; it calls into the table and reads the result. A future AgentSkill.N8N_TRIGGER member invokes n8n workflows."}
```

### Automation ↔ n8n (n8n)

```
{domains: ["automation", "n8n"], claim: "Sequence and conditional branching are n8n's domain; the automation engine dispatches one action per trigger cycle. Multi-step, conditional, or fan-out automation composes n8n workflows invoked via the AgentAction(skill=AgentSkill.N8N_TRIGGER, ...) case (future AgentSkill member) in _AGENT_DISPATCH. The n8n-mcp server row is owned exclusively by admin/mcp/model.py _SERVER_TABLE; admin/rails/n8n.py never invokes the MCP server directly."}
```

---

## [08]-[PORTABILITY / VPS]

On the Hostinger VPS the automation engine runs as the `maghz` operator service account
(not root). Key differences from local:

- **File watch paths** in `Watch.paths` must be absolute paths reachable by the service
  account. The engine validates each path with `anyio.Path(p).exists()` before starting
  `awatch`; a missing path emits `AutomationFault(trigger_spawn=(lane, f"path not found: {p}"))`.
- **Resource ceilings** (`AutomationConfig.cpu_ceil`, `rss_ceil_mb`) are tuned via
  `MAGHZ_AUTOMATION__CPU_CEIL` / `MAGHZ_AUTOMATION__RSS_CEIL_MB` environment variables
  (the `pydantic-settings` `MAGHZ_` prefix + `__` nested delimiter handles this).
- **NDJSON ledger** writes to `cfg.automation.ledger_file`, defaulting to
  `.artifacts/automation.ndjson`. On the VPS this path is under the service working
  directory. `artifacts_dir` (`MaghzSettings.artifacts_dir`) is `gitignore`-listed
  and persisted across deployments.
- **No device-code / keyring** in the automation domain. Credentials for DB and Ollama
  are via the `MAGHZ_DATABASE__DSN` and `MAGHZ_OLLAMA__*` env vars already carried by
  `MaghzSettings`. The `keyring` package is available but the automation engine does not
  require it directly.
- **Daemon lifecycle** on VPS: a systemd unit or Docker CMD runs
  `maghz automation run --spec '{"trigger":{"type":"watch",...},...}'` or the schedule
  equivalent. SIGTERM triggers `open_signal_receiver` in `_signal_lane`; the task group
  cancels cleanly and the APScheduler 4.x `AsyncScheduler` context manager exits.
  No second supervisor.
- **psutil on VPS**: `virtual_memory()` and `Process.memory_info().rss` work on Linux;
  `getloadavg` is available via `os.getloadavg` on Linux so `hasattr(psutil, "getloadavg")`
  will be true. No macOS-gated sensor functions are used.
- **APScheduler 4.x on VPS**: `AsyncScheduler` is backend-agnostic; when the anyio backend
  is asyncio (the default in `admin/__main__.py`'s `anyio.run`), it integrates cleanly.

---

## [09]-[ACCEPTANCE]

**Static quality gate** (run once after the module batch is complete):

```
ruff check admin/automation/ admin/__main__.py admin/settings/config.py
ruff format --check admin/automation/
ty check
mypy admin/automation/ --no-error-summary
```

Zero diagnostics required; `ty` `error-on-warning = true` is active.

**Runtime verbs that must fire** (manual / one-shot path):

```
# One-shot: AgentAction(skill=deep_research) on manual trigger — must produce one OK envelope
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"agent","skill":"deep_research","domain":"geometry"}}'

# One-shot: Sync diff on manual trigger
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"sync","op":"diff"}}'

# Unknown lane: must produce FAULTED envelope, exit 2 (spec_decode fault, not silent default)
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"sync","op":"diff"},"lane":"nonexistent"}'

# Spec decode fault: malformed JSON — must produce one FAULTED envelope, exit 2
maghz automation run --spec 'not json'
```

**Receipts that must materialize**:

- `Envelope.status == "ok"` and `Envelope.report.detail.__type__ == "automation"` for
  a successful one-shot drive.
- `AutomationReceipt.spec_id`, `trigger_tag`, `action_tag`, `fired_at`, `elapsed_ms`
  all non-null on every successful fire; `trigger_tag` is a valid `TriggerTag` literal,
  `action_tag` is a valid `ActionTag` literal.
- For `AgentAction` arm: `AutomationReceipt.agent_skill` is a valid `AgentSkill` member.
- `AutomationReceipt.cpu_percent` and `memory_rss_mb` non-null on every fire (psutil
  governor snapshot always runs).
- One NDJSON line appended to `.artifacts/automation.ndjson` per fire; decodable as
  `AutomationReceipt` via `msgspec.json.decode(line, type=AutomationReceipt)`.
- `job` table row created for `AgentAction` actions; status `"running"` at dispatch,
  `"done"` or `"failed"` after resolution.
- `DrainReceipt[AutomationReceipt].completed == 1` for every successful one-shot dispatch;
  `drain_receipt.values[0]` is the `AutomationReceipt` written to the NDJSON ledger.

**Mutation/edge signals**:

- `psutil` governor at threshold: `_governor_aspect` returns `Error(AutomationFault(admission_denied=...))`;
  `Status.SKIP` envelope emitted; no lane borrow, no job row, no ledger write.
- Lane at capacity: `_governor_aspect` detects all tokens borrowed (via
  `LanePolicy.available_tokens == 0`), returns `Error(AutomationFault(lane_overflow=...))`;
  `Status.SKIP` envelope emitted; action deferred on Watch, skipped on Manual.
- `guard(RetryClass.HTTP)` exhausted: `AutomationFault(action_transient=...)`, `Status.FAULTED`
  envelope; job row status `"failed"`.
- SIGTERM to a running daemon: `AsyncScheduler` async context manager exits, `awatch`
  generator exits, task group cancels, one summary envelope on stdout, exit 0.
- `Schedule` trigger misfire: `JobOutcome.missed` event fires on APScheduler 4.x subscriber;
  NDJSON ledger records a `Status.SKIP` receipt for the missed tick.
- `Embed` action with `concept=None`: sweep-all-pending path in `db.query`; receipt
  carries `rows_affected` count from the embed pipeline result.
- `Sync` action with `concept="geometry"`: `sync_run(cfg, concept="geometry")` — single-concept generate path.
- `Sync` action with `concept=None` (DIFF): `sync_run(cfg, concept=None)` — sweep diff path; `rails.sync_diff` / `rails.sync_generate` aliases do not exist after existing-rails realize.
- Unknown `lane` in spec: `_decode_spec` rejects at admission, `AutomationFault(spec_decode=(id, "unknown lane: nonexistent"))` emitted.
