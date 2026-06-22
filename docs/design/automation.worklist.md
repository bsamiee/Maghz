# [AUTOMATION_WORKLIST]

Realize-ready worklist for domain `automation`. The blueprint `automation.md` is the design;
this is the execution order, the exact owners, ADTs, `.api` members, deps, ripples, dependency
gate, and acceptance signals. One canonical owner per concept; no parallel surface beyond what
the blueprint sanctioned.

---

## [01]-[OWNERS]

| [OWNER FILE] | [DISPOSITION] | [OWNS] |
| ------------ | ------------- | ------ |
| `admin/automation/__init__.py` | create | Package marker; no re-exports (the rails `__init__` carries the public `drive` re-export). |
| `admin/automation/model.py` | create | `[TYPES]` `[CONSTANTS]` `[MODELS]` `[ERRORS]`. The closed `Trigger` union (`Watch \| Schedule \| Manual`), the closed `Action` union (`AgentAction \| Notify \| Embed \| Sync`), the `AgentSkill` StrEnum, the `Trigger`/`TriggerTag`/`Action`/`ActionTag` aliases, the `AutomationSpec` wire record, the `AutomationReceipt` typed receipt (`Detail` subclass, `tag="automation"`), the `AutomationFault` `@tagged_union` vocabulary. No operations. |
| `admin/automation/engine.py` | create | `[SERVICES]` `[OPERATIONS]` `[TABLES]` `[COMPOSITION]`. The single polymorphic `drive(spec, cfg) -> Envelope` entrypoint; the `_decode_spec` admission boundary; the `_watch_lane` / `_schedule_lane` / `_signal_lane` / `_dispatch_action` anyio lanes; the total `_exec(action, spec) -> Result[AutomationReceipt, AutomationFault]` dispatch; the `_governor_aspect` named aspect; `_fault_envelope`; `_record_ledger`; the `_WATCH_FILTER`, `_AGENT_DISPATCH`, `_LANE_POLICIES` tables. |
| `admin/settings/config.py` | modify | Add `AutomationConfig(BaseModel)`; add `automation: AutomationConfig = Field(default_factory=AutomationConfig)` field on `MaghzSettings`. |
| `admin/__main__.py` | modify | Mount the `_automation` sub-`App` on `app` (one `app.command(...)` registration) with one verb `run`; `--spec` is `Annotated[AutomationSpec, Parameter(converter=_decode_spec)]`. |
| `admin/rails/__init__.py` | modify | Re-export `drive` alongside the existing rail callables. |
| `db/schema.sql` | modify (owned by `db` domain) | `job` / `worker` rows are written by the `AgentAction` dispatch callable via `db.query`; the table shape is the `db` domain's owner — automation only composes the write, it does not author DDL. Listed here only as the consumed seam. |

No third automation module. `watch` / `schedule` CLI aliases are NOT created (ONE_HOP_RESOLUTION:
they would each call `drive` with the same spec; the `trigger` discriminant selects the lane).

---

## [02]-[ADTs]

| [ADT] | [SECTION] | [DISCRIMINANT] | [CASES] |
| ----- | --------- | -------------- | ------- |
| `Trigger` | `model.py [TYPES]` | `tag_field="type"`, `msgspec.Struct(frozen=True, gc=False)` leaves | `Watch(paths, filter, debounce, recursive, tag="watch")` · `Schedule(cron, jitter, timezone, tag="schedule")` · `Manual(tag="manual")`. `type Trigger = Watch \| Schedule \| Manual`; `type TriggerTag = Literal["watch","schedule","manual"]`. |
| `Action` | `model.py [TYPES]` | `tag_field="kind"`, `msgspec.Struct(frozen=True, gc=False)` leaves | `AgentAction(skill: AgentSkill, domain, params: msgspec.Raw, tag="agent")` · `Notify(channel, message, tag="notify")` · `Embed(concept: str \| None, tag="embed")` · `Sync(op: Literal["diff","generate"], concept: str \| None, tag="sync")`. `type Action = AgentAction \| Notify \| Embed \| Sync`; `type ActionTag = Literal["agent","notify","embed","sync"]`. |
| `AgentSkill` | `model.py [TYPES]` | `StrEnum` (closed; in-arm discriminant, not an action case) | `DEEP_RESEARCH="deep_research"` · `REFINE="refine"` · `CREATE_ENTRY="create_entry"`. Adding a skill = one member + one `_AGENT_DISPATCH` row; no action-ADT change. |
| `AutomationSpec` | `model.py [MODELS]` | wire record `msgspec.Struct(frozen=True, gc=False)` | `trigger: Trigger`, `action: Action`, `lane: str = "default"`, `id: str` (uuid4 default_factory). The two unions' `tag_field` names (`type` vs `kind`) do not collide; msgspec resolves each independently. |
| `AutomationReceipt` | `model.py [MODELS]` | `Detail` subclass `frozen=True, tag="automation"` | `spec_id`, `trigger_tag: TriggerTag`, `action_tag: ActionTag`, `agent_skill: AgentSkill \| None`, `lane`, `fired_at` (ISO-8601 UTC), `attempt`, `elapsed_ms`, `rows_affected: int \| None`, `job_id: str \| None`, `cpu_percent: float \| None`, `memory_rss_mb: float \| None`. Closed `Literal` tag fields, never bare `str`. |
| `AutomationFault` | `model.py [ERRORS]` | `@tagged_union(frozen=True)` from `expression`, `tag: AutomationFaultKind = tag()` | `spec_decode` · `admission_denied` · `lane_overflow` · `action_transient` · `action_permanent` · `trigger_spawn` · `agent_call`; each `case()` is `tuple[str, str]`. `AutomationFaultKind = Literal[...]`. Domain-internal; projected to `Envelope` once at `drive` via `_fault_envelope` (total `match` + `assert_never`). |

Removed by design (do NOT re-add): `Sequence`, `Debounce` action cases (sequencing is n8n's domain;
debounce is `Watch.debounce`); the `DeepResearch`/`Refine`/`CreateEntry` parallel action cases
(collapsed into `AgentAction(skill, ...)`); any `Option[str]` `enc_hook`/`dec_hook` codec pair
(`Embed.concept`/`Sync.concept` are msgspec-native `str | None` at the wire, projected to
`Option[str]` only inside the dispatch arm).

Total `match` sites with `assert_never` default arm: `engine._resolve_trigger` (3 arms),
`engine._exec` (4 arms), `engine._fault_envelope` (7 arms).

---

## [03]-[API_MEMBERS]

| [PACKAGE] | [MEMBERS] | [USE] |
| --------- | --------- | ----- |
| `watchfiles` | `awatch(*paths, watch_filter, debounce, step, stop_event, recursive)`, `DefaultFilter`, `PythonFilter`, `BaseFilter`, `Change`, `Change.raw_str()` | Watch trigger lane async generator; `stop_event` is the engine's `anyio.Event`; filter selection via `_WATCH_FILTER` table; `change.raw_str()` -> structlog context only (not a receipt field). |
| `apscheduler` (4.x) | `AsyncScheduler` (async ctx mgr), `AsyncScheduler.add_schedule`, `AsyncScheduler.run_until_stopped`, `AsyncScheduler.subscribe`, `apscheduler.triggers.cron.CronTrigger`, `CronTrigger.from_crontab`, `ConflictPolicy.replace`, `JobReleased`, `JobOutcome.success`, `JobOutcome.missed` | Schedule trigger lane; one `async with AsyncScheduler()` inside `_schedule_lane`; `subscribe(callback, {JobReleased})` is the single NDJSON-append observability seam; `JobOutcome.missed` -> `Status.SKIP` receipt. The 4.x ctx-mgr owns lifecycle (no `shutdown(wait=True)` thread offload). |
| `psutil` | `Process(os.getpid()).oneshot()`, `cpu_percent(interval=None)`, `memory_info().rss`, `hasattr(psutil, "getloadavg")` guard | `_governor_aspect` admission gate; one `oneshot()` batch reads CPU% + RSS; populates `AutomationReceipt.cpu_percent` / `memory_rss_mb`; `interval=None` (engine owns timing). |
| `anyio` | `create_task_group()`, `Event`, `open_signal_receiver(SIGTERM, SIGINT)`, `to_thread.run_sync(fn, limiter=...)`, `move_on_after(delay)`, `anyio.Path(p).exists()` | One task group per `drive`; `Event` is the watch `stop_event`; `_signal_lane` awaits first signal; ledger write offloaded with explicit `limiter=`; `move_on_after(cfg.automation.action_timeout_s)` wraps `_exec`; path existence check before `awatch`. `except*` catches lane `ExceptionGroup` -> `trigger_spawn`. |
| `msgspec` | `json.Decoder(type=AutomationSpec)` (module-level, reused), `DecodeError`, `Raw`, `Decoder.decode_lines`, `json.encode`, `json.decode(line, type=AutomationReceipt)` | Stateful decoder for `--spec`; `Raw` defers `AgentAction.params` decode to the dispatch arm; `decode_lines` replays the NDJSON ledger; `encode(drain_receipt.values[0])` writes one ledger line per fire. |
| `cyclopts` | `App`, `app.command(...)`, `Parameter(converter=_decode_spec)`, `ValidationError`, `UNSET` | New `_automation` sub-`App`; `run` verb; `_decode_spec` converter is the admission boundary mapping `DecodeError`/unknown-lane -> `ValidationError`. |
| `expression` | `Result`, `Ok`, `Error`, `Option`, `Some`, `Nothing`, `@tagged_union`, `tag()`, `case()`, `Map`, `Map.of_seq`, `Map.try_find` | `Result[AutomationReceipt, AutomationFault]` internal rail; `AutomationFault` tagged union; `Option[str]` projection at dispatch arms; `Map` is the keyed-table form for `_AGENT_DISPATCH` and `_LANE_POLICIES` (runtime owner law — NOT `frozendict`). |
| `structlog` | `contextvars.bind_contextvars`, `contextvars.bound_contextvars`, `get_logger` | `DrainReceipt` metadata (accepted/cancelled/hit) -> structlog context only; per-dispatch `bound_contextvars(spec_id, action, lane)` scope; `Change.raw_str()` + path context. |
| `os` / `signal` / `uuid` / `types.MappingProxyType` | `os.getpid`, `signal.SIGTERM`, `signal.SIGINT`, `uuid.uuid4`, `MappingProxyType` | pid for psutil; signals for `_signal_lane`; uuid for `AutomationSpec.id`; `MappingProxyType` only for the static instance map `_WATCH_FILTER`. |

Runtime-owner composition (no new `.api`; consumed from `admin/runtime/`):
`LanePolicy.drain(units: Block[Admit])`, `Admit.bare` / `Admit.keyed` / `Admit.retried(RetryClass, work)` / `Admit.offload`,
`Block.of_seq`, `DrainReceipt[AutomationReceipt]`, `drain_receipt.values[0]`, `LanePolicy.available_tokens`
(from `admin/runtime/lanes.py`); `guard(RetryClass.HTTP)` / `guard(RetryClass.DB)` returning
`BoundAsyncRetryingCaller` (from `admin/runtime/resilience.py`); `@receipted` / `@drained` aspect
patterns (from `admin/runtime/receipts.py`); `RuntimeRail[T] = Result[T, BoundaryFault]` (from
`admin/runtime/rails.py`). `stamina.instrumentation.set_on_retry_hooks` / `BackoffHook` for the
`agent_call` transient retry hook is composed via `resilience.py`, not called directly.

Consumed-rail seam members: `sync.run(cfg, /, *, concept)` returning `Envelope` with
`SyncDetail.drift` (from `admin/rails/sync.py`); `db.query` for `maghz.embed_enqueue()` /
`maghz.embed_drain()` and `worker`/`job` row writes (from `admin/db.py` / `db` domain);
`_AGENT_DISPATCH[skill](action, spec, cfg) -> Result[AutomationReceipt, AutomationFault]` callables
(owned by `mcp` / `integrations` domains).

---

## [04]-[DEPS]

| [PACKAGE] | [BAND] | [ACTION] | [.api CATALOG NOTE] |
| --------- | ------ | -------- | ------------------- |
| `watchfiles` | pure-venv | admit to `pyproject.toml` | Author `libs/python/runtime/.api/watchfiles.md` (new): `awatch(*paths, watch_filter, debounce, step, stop_event, recursive)` async generator, `DefaultFilter` / `PythonFilter` / `BaseFilter`, `Change` enum + `Change.raw_str()`, anyio `stop_event` integration. New capability — nothing in `admin/` currently watches the filesystem. |
| `apscheduler` (`>=4.0.0`) | pure-venv | admit to `pyproject.toml`; if any `apscheduler<4.0` pin exists, remove it; verify `uv lock --check` | Rebuild `libs/python/runtime/.api/apscheduler.md` for the 4.x async-first surface BEFORE the implement pass: `AsyncScheduler` (async ctx mgr), `CronTrigger` / `from_crontab`, `ConflictPolicy`, `add_schedule`, `run_until_stopped`, `subscribe`, `JobReleased`, `JobOutcome.success` / `.missed`. The 3.x `AsyncIOScheduler` + `AsyncIOExecutor` surface is rejected (asyncio-only; violates the anyio mandate). |

Already declared (verified present in `pyproject.toml`): `anyio>=4.14.0`, `psutil>=7.2.2`,
`stamina>=26.1.0`, `msgspec>=0.21.1`, `cyclopts>=4.18.0`, `expression>=5.6.0`,
`structlog>=26.1.0`, `httpx>=0.28.1`. `.api` catalogs for these are current.

NOT admitted (do NOT add): `frozendict` — the runtime owner's law forbids it; `expression.Map`
is the keyed-dispatch-table form for `_AGENT_DISPATCH` and `_LANE_POLICIES`. This corrects the
blueprint's `frozendict[AgentSkill, Callable]` annotation to `Map[AgentSkill, Work]`.

---

## [05]-[RIPPLES]

```
{domains: ["automation", "runtime"], claim: "engine.py composes LanePolicy.drain(Block.of_seq([Admit.retried(cls, work)])) from admin/runtime/lanes.py as the sole admission primitive, selecting Admit.bare / Admit.keyed / Admit.retried / Admit.offload per arm. _LANE_POLICIES is an expression.Map[str, LanePolicy] built from cfg.automation.lane_keys (NOT a raw CapacityLimiter dict, NOT frozendict); unknown lane keys are rejected at _decode_spec admission, never falling back to default. DrainReceipt[AutomationReceipt] carries each dispatch; drain_receipt.values[0] (the inner AutomationReceipt) is the NDJSON ledger payload while DrainReceipt accepted/cancelled/hit metadata flows to structlog context only. ContentKey = NewType('ContentKey', str) is owned by admin/runtime/lanes.py and shared with the cloud-sync domain as the session-cache key type."}

{domains: ["automation", "runtime"], claim: "engine.py composes guard(RetryClass.HTTP) and guard(RetryClass.DB) from admin/runtime/resilience.py as BoundAsyncRetryingCaller instances; no @stamina.retry(...) decorator and no stamina.retry call appears directly in engine.py. The agent_call transient hook registers a BackoffHook via stamina.instrumentation.set_on_retry_hooks through resilience.py, not at the call site."}

{domains: ["automation", "runtime"], claim: "_governor_aspect is a signature-preserving named @aspect that runs OUTERMOST, before @drained borrows a LanePolicy token; admission_denied (psutil ceiling) and lane_overflow (LanePolicy.available_tokens == 0) faults return Error(...) before any drain lifecycle begins. The @receipted / @drained aspect patterns and RuntimeRail[T] = Result[T, BoundaryFault] rail are owned by admin/runtime/; the automation domain declares its own AutomationFault vocabulary and never substitutes BoundaryFault as the automation fault type."}

{domains: ["automation", "existing-rails"], claim: "The Sync action dispatches to sync.run(cfg, concept=None) for DIFF and sync.run(cfg, concept=spec.concept) for GENERATE — the canonical single entrypoint admin/rails/sync.py after the existing-rails collapse. SyncOp and the rails.sync_diff / rails.sync_generate aliases do not exist; the canonical import is `from admin.rails.sync import run as sync_run`. The engine reads envelope.report.detail (a SyncDetail instance) and populates AutomationReceipt.rows_affected from SyncDetail.drift."}

{domains: ["automation", "db"], claim: "The Embed action calls maghz.embed_enqueue() and maghz.embed_drain() via admin.db.query; Embed.concept=None maps to the sweep-all-pending path and Some(name) to single-concept enqueue against the concept_embed_pending_idx partial index. The AgentAction dispatch callable writes a job row (status 'running' at dispatch, 'done'/'failed' after) and a worker row through db.query; job.worker_id references the automation engine's registered worker and job.msg_id links the pgmq research queue message. The db domain owns the job/worker/embed DDL and the embed protocol; automation only composes db.query."}

{domains: ["automation", "mcp", "integrations"], claim: "DeepResearch / Refine / CreateEntry collapse into AgentAction(skill: AgentSkill, domain, params: msgspec.Raw) with params decoded lazily inside the AgentAction dispatch arm by the skill adapter. _AGENT_DISPATCH is an expression.Map[AgentSkill, Work], one row per AgentSkill member; each callable is owned by the integrations/mcp blueprints with contract (action: AgentAction, spec: AutomationSpec, cfg: MaghzSettings) -> Result[AutomationReceipt, AutomationFault]. The automation engine is skill-agnostic — it reads _AGENT_DISPATCH[action.skill](...) and never decodes Raw itself. A future AgentSkill.N8N_TRIGGER member is the n8n entry."}

{domains: ["automation", "n8n"], claim: "Sequence and conditional branching are n8n's domain; the automation engine dispatches exactly one action per trigger cycle. Multi-step / conditional / fan-out automation composes n8n workflows invoked via the future AgentAction(skill=AgentSkill.N8N_TRIGGER, ...) case in _AGENT_DISPATCH. The n8n-mcp server row is owned exclusively by admin/mcp/model.py _SERVER_TABLE; admin/rails/n8n.py never invokes the MCP server directly."}

{domains: ["automation", "ledger"], claim: "The OWNER ledger view (admin/rails/ledger.py Kind.OWNER) surfaces worker/job telemetry; the automation engine registers itself as a worker row on first drive call and AutomationReceipt.job_id links to job.id so `maghz ledger stale` surfaces exhausted automation jobs alongside manual research jobs. The seam is the db.query write of worker/job rows; the ledger rail owns the read projection."}

{domains: ["automation", "cloud-sync"], claim: "When the cloud-sync domain adds rclone-backed remote sync verbs, the Sync action gains a new op literal without structural change to the automation engine; cloud-sync owns the CloudSyncDetail shape and the automation engine never reads cloud-sync internals directly. ContentKey is shared as the session-cache key type owned by admin/runtime/lanes.py."}
```

---

## [06]-[DEPENDS_ON]

| [DOMAIN KEY] | [WHY — OWNERS THAT MUST EXIST FIRST] |
| ------------ | ------------------------------------- |
| `runtime` | `admin/runtime/lanes.py` (`LanePolicy`, `Admit`, `Block.of_seq`, `DrainReceipt`, `ContentKey`, `available_tokens`), `admin/runtime/resilience.py` (`guard`, `RetryClass`, `BoundAsyncRetryingCaller`, `POLICY`), `admin/runtime/receipts.py` (`@receipted`, `@drained`), `admin/runtime/rails.py` (`RuntimeRail`, `BoundaryFault`, `async_boundary`). Hard blocker — `drive` cannot compose without these. |
| `existing-rails` | `admin/rails/sync.py` `run(cfg, /, *, concept)` + `SyncDetail.drift` after the `SyncOp` collapse. Blocks the `Sync` action arm. |
| `db` | `job` / `worker` tables, `maghz.embed_enqueue()` / `maghz.embed_drain()` routines, `concept_embed_pending_idx`, `db.query` surface, pgmq `research` queue. Blocks the `Embed` and `AgentAction` arms (job-row writes). |
| `mcp` + `integrations` | The `_AGENT_DISPATCH` callables (`(action, spec, cfg) -> Result[AutomationReceipt, AutomationFault]`) and the per-skill `params` structs. Blocks the `AgentAction` arm body; the engine ships the table shape, the counterparts ship the rows. |
| `ledger` | `admin/rails/ledger.py` `Kind.OWNER` worker/job read projection. Soft — automation writes the rows; ledger reads them. Engine can land before ledger read view exists. |
| `n8n` (future) | `AgentSkill.N8N_TRIGGER` row + `admin/mcp/model.py _SERVER_TABLE` n8n-mcp server. Not a current blocker; one future `AgentSkill` member + one `_AGENT_DISPATCH` row. |

Build order: `runtime` -> (`existing-rails`, `db`) -> (`mcp`, `integrations`) -> `automation` -> (`ledger` read view).

---

## [07]-[ACCEPTANCE]

Static gate (one batch after the module set is complete; zero diagnostics required, `ty`
`error-on-warning = true` active):

```
ruff check admin/automation/ admin/__main__.py admin/settings/config.py
ruff format --check admin/automation/
ty check
mypy admin/automation/ --no-error-summary
```

Runtime verbs that must fire:

```
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"agent","skill":"deep_research","domain":"geometry"}}'   # OK envelope
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"sync","op":"diff"}}'                                    # OK envelope
maghz automation run --spec '{"trigger":{"type":"manual"},"action":{"kind":"sync","op":"diff"},"lane":"nonexistent"}'               # FAULTED, exit 2 (spec_decode, not silent default)
maghz automation run --spec 'not json'                                                                                              # FAULTED, exit 2
```

Receipts that must materialize:
- `Envelope.status == "ok"` and `Envelope.report.detail.__type__ == "automation"` on a successful one-shot drive.
- `AutomationReceipt.spec_id`, `trigger_tag` (valid `TriggerTag`), `action_tag` (valid `ActionTag`), `fired_at`, `elapsed_ms` non-null on every success.
- `AgentAction` arm: `AutomationReceipt.agent_skill` is a valid `AgentSkill` member.
- `cpu_percent` and `memory_rss_mb` non-null on every fire (governor snapshot always runs).
- One NDJSON line per fire appended to `.artifacts/automation.ndjson`, decodable via `msgspec.json.decode(line, type=AutomationReceipt)`.
- `job` table row for `AgentAction`: `"running"` at dispatch, `"done"`/`"failed"` after resolution.
- `DrainReceipt[AutomationReceipt].completed == 1` per successful one-shot; `drain_receipt.values[0]` is the ledgered receipt.

Mutation / edge signals:
- psutil at ceiling: `_governor_aspect` -> `Error(admission_denied)`; `Status.SKIP`; no lane borrow, no job row, no ledger write.
- Lane at capacity (`LanePolicy.available_tokens == 0`): `_governor_aspect` -> `Error(lane_overflow)`; `Status.SKIP`; deferred on Watch, skipped on Manual.
- `guard(RetryClass.HTTP)` exhausted: `action_transient`; `Status.FAULTED`; job row `"failed"`.
- SIGTERM to a daemon: `AsyncScheduler` ctx exits, `awatch` exits, task group cancels, one summary envelope on stdout, exit 0.
- `Schedule` misfire: `JobOutcome.missed` subscriber event -> `Status.SKIP` receipt for the missed tick.
- `Embed` `concept=None`: sweep-all-pending via `db.query`; receipt `rows_affected` from the embed result.
- `Sync` `concept="geometry"`: `sync_run(cfg, concept="geometry")` generate path; `concept=None`: `sync_run(cfg, concept=None)` diff path (no `sync_diff`/`sync_generate` aliases).
- Unknown `lane`: `_decode_spec` rejects at admission with `spec_decode=(id, "unknown lane: nonexistent")`.
```
