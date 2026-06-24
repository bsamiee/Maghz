export const meta = {
  name: 'maghz-deepen',
  description: 'DEEP decision-loaded rebuild of the Maghz operator to the EXACT Rasm runtime .planning exemplar pages as real code, PLUS the settled architecture surgery (31->21 file collapse, BoundaryFault unification, runtime.spawn boundary), the IaC push (Pulumi BuildKit cache + ComponentResource + one typed extension catalog generating Dockerfile/SQL/preload + .mcp.json 7->4), and the world-class PG18.4 extension setup (pgvectorscale + pg_squeeze + GUC tuning + doctor liveness assertions). Supersedes rebuild-code at a much harder floor. PER-FILE author-critique-redteam (each target file its own impl(max) -> critique(xhigh) -> redteam(max) chain, pooled) so critique and redteam are line-by-line adversarial on one file; substrate-first then a substrate gate barrier; consumers fully parallel against the locked substrate; category IaC + PG; cross-file reconcile; barrel + init/main consolidation; whole-repo multi-language gate. Runs from Rasm, reads the Rasm bar by absolute path, edits Maghz by absolute path, directly on main.',
  whenToUse: 'The deep second Maghz pass: realize the runtime-exemplar floor, the re-architecture, the IaC/extension-catalog, and the PG18.4 push after the first rebuild-code pass, at per-file adversarial granularity',
  phases: [
    { title: 'Substrate', detail: 'per-file: each substrate target (core.py, runtime/rails+resilience+lanes+receipts, db.py, settings.py) gets its OWN impl-critique-redteam chain against the locked ownership contract + the FILEMAP flatten + the COLLAPSE; pooled, then ONE ruff+ty gate barrier' },
    { title: 'Consumers', detail: 'per-file across ALL consumer targets (automation, mcp, rails, infra.py, remote.py) against the locked substrate: each file its OWN impl-critique-redteam chain, fully parallel pooled, then per-folder ruff+ty gates in parallel' },
    { title: 'IaC', detail: 'category: Pulumi deepening (BuildKit cache, ComponentResource, outputs->settings, n8n key fix) + the one typed extension catalog generating Dockerfile/routines/cron/preload + .mcp.json 7->4; impl-critique-redteam then multi-language gate' },
    { title: 'PG', detail: 'category: PG18.4 push: pgvectorscale + pg_squeeze + pgvector iterative-scan GUCs + the doctor census/preload/pipeline/index liveness assertions; impl-critique-redteam then multi-language gate' },
    { title: 'Reconcile', detail: 'bounded loop: cross-file residuals union-find clustered, fix(max) then adversarial verify(xhigh), then a multi-language re-gate' },
    { title: 'Roots', detail: 'single consolidation agent: rewrite every package barrel + __main__.py to the final API surface + CLI wiring' },
    { title: 'Gate', detail: 'whole-repo multi-language gate (ruff+ty over admin, sqlfluff/sqruff over db, hadolint over image, json validity over .mcp.json) to green' },
  ],
}

// --- [TYPES] -- structured-output schemas (reused verbatim from rebuild-code) -------------
const FIXLOG = { type: 'object', additionalProperties: false, required: ['file', 'verdict', 'summary'], properties: { file: { type: 'string' }, verdict: { type: 'string', enum: ['rebuilt', 'refined', 'clean'] }, collapsed: { type: 'string' }, residual_high: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['files', 'claim'], properties: { files: { type: 'array', items: { type: 'string' } }, claim: { type: 'string' } } } }, summary: { type: 'string' } } }
const GATE_RESULT = { type: 'object', additionalProperties: false, required: ['green', 'ruff_clean', 'ty_clean'], properties: { green: { type: 'boolean' }, ruff_clean: { type: 'boolean' }, ty_clean: { type: 'boolean' }, rounds: { type: 'number' }, remaining: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['file', 'rule', 'message'], properties: { file: { type: 'string' }, rule: { type: 'string' }, message: { type: 'string' } } } }, advisory: { type: 'array', items: { type: 'string' } } } }
const RECONCILE_FIX = { type: 'object', additionalProperties: false, required: ['files', 'verdict', 'summary'], properties: { files: { type: 'array', items: { type: 'string' } }, verdict: { type: 'string', enum: ['fixed', 'clean'] }, summary: { type: 'string' } } }
const RECONCILE_VERIFY = { type: 'object', additionalProperties: false, required: ['overall', 'claims'], properties: { overall: { type: 'boolean' }, claims: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['claim', 'status'], properties: { claim: { type: 'string' }, status: { type: 'string', enum: ['fixed', 'invalid', 'open'] }, evidence: { type: 'string' } } } } } }

// --- [CONSTANTS] -- cross-repo paths, caps, the domain skeleton -------------------------
const MAGHZ = '/Users/bardiasamiee/Documents/99.Github/Maghz'
const ADMIN = MAGHZ + '/admin'
const RASM_BAR = '/Users/bardiasamiee/Documents/99.Github/Rasm/libs/python'
const CAP = 10
const MAX_RECONCILE_ROUNDS = 3
const STAGGER_MS = 1500
const SUBSTRATE_DOMAINS = ['core', 'runtime', 'settings', 'db']
const CONSUMERS = ['automation', 'mcp', 'rails', 'infra', 'remote']
// glob forms so a gate path is robust to the FILEMAP flatten (admin/core* matches core/ OR core.py)
const SUBSTRATE_GATE = 'admin/core* admin/settings* admin/runtime admin/db.py'
const scopePath = (s) => s === 'db' ? 'admin/db.py' : s === 'runtime' ? 'admin/runtime' : 'admin/' + s + '*'
const consumerGate = (f) => 'admin/' + f + '*'
const shortLabel = (f) => f.replace(/^admin\//, '')

// --- [INPUT] -- args = optional phase/domain scope | empty/ALL = the whole deep pass -------
const SCOPE = (typeof args === 'string' && args.trim() && args.trim().toUpperCase() !== 'ALL') ? args.trim() : (args && typeof args === 'object' && args.scope ? String(args.scope).trim() : '')
const COMMIT = !!(args && typeof args === 'object' && args.commit === true)

// --- [HARNESS] -- steady bounded worker pool (reused verbatim) ----------------------------
const pool = async (items, cap, worker) => {
  const out = new Array(items.length)
  let next = 0
  const run = async (slot) => {
    if (slot) await new Promise((res) => setTimeout(res, slot * STAGGER_MS))
    while (next < items.length) { const i = next++; out[i] = await worker(items[i], i) }
  }
  await Promise.all(Array.from({ length: Math.min(cap, items.length) }, (_, slot) => run(slot)))
  return out
}

// --- [MODELS] -- the doctrine preamble: reused verbatim from rebuild-code -----------------
const LAW = [
  'Maghz operator codebase: the executable Python package under ' + ADMIN + ' (real .py source on disk, NOT markdown design pages). You rebuild the SOURCE FILES in place. DENSITY BAR + CAPABILITY REFERENCE: the Rasm libs/python planning corpus is your worked EXEMPLAR FLOOR — read the relevant pages under ' + RASM_BAR + '/<folder>/.planning/ (especially ' + RASM_BAR + '/runtime/.planning/{execution,reliability,observability,transport}) for the target density, and the .api catalogs for capability: the shared/universal ' + RASM_BAR + '/.api/*.md (expression, pydantic, pydantic-settings, msgspec, anyio, beartype, stamina, structlog, opentelemetry-*, psutil, numpy) AND the folder ' + RASM_BAR + '/runtime/.api/*.md (apscheduler, asyncssh, cyclopts, fsspec, gcsfs, httpx, keyring, universal-pathlib, watchfiles, msgspec). Cite ONLY members real in those .api catalogs or verified by reading the installed package in the Maghz env. Maghz own docs/design/ is IGNORED entirely — never read it; infer intent from code behavior.',
  'POSTURE — AGGRESSIVE GREENFIELD over ALREADY-STRONG code: this codebase is already dense, modern, expression-style (tagged_union fault families, frozen msgspec.Struct, frozendict tables, anyio, stamina, structlog, total match/assert_never, PEP 695). Your job is NOT to fix naive code — it is to COLLAPSE HARDER across files (target 30-50pct LOC reduction via polymorphic collapse), ENHANCE capability (denser owners, MORE features, never fewer), and freely RESTRUCTURE files within the admin domain skeleton per the locked target layout. Every contract is open to total redesign (CLI surface, .mcp.json output, DB schema, wire/JSON shapes) BUT capability is PRESERVED AND ENHANCED, never dropped. Where a fence is already at the bar, deepen or collapse it further; never regress correctness, boundary law, or the gate; never invent churn on code already optimal — prove it optimal by finding the real cross-file collapse instead.',
  'WRITE-FULLY MANDATE: every fix you identify you MUST make NOW via Edit/Write directly in the .py source file on disk — the structured fix-log you return is a REPORT of edits ALREADY MADE, never a to-do list or hedge; leave nothing behind except genuine cross-FILE items (report those in residual_high). If after real investigation a file is already optimal, return verdict=clean.',
].join('\n')
const ULTRA = [
  'OPERATIVE DOCTRINE (embedded — do NOT go read docs/stacks/python or the coding-python skill; they are NOT the bar): hold every fence to the laws stated in THIS prompt and to the worked density of the Rasm libs/python/.planning/ exemplar pages. The .planning corpus is the bar; the .api catalogs are the capability surface.',
  'LIFECYCLE SPINE (BOUNDARY_ADMISSION): every fence flows Raw -> Payload -> Canonical owner -> Rail -> Projection -> Egress. Raw material is admitted EXACTLY ONCE into an evidence-carrying owner (Pydantic/`TypedDict` payload at ingress); interior code never re-validates, never sees `None`-as-failure, sentinels, or provider shapes; egress projects outward (`msgspec.Struct` wire) from the canonical owner. Parameterize BOTH ingress AND egress so the same owner sources and sinks across many providers/apps without touching its interior.',
  'SHAPE LAW: one concept owns exactly ONE type (SHAPE_BUDGET) — variants are cases in one closed family, never sibling types; one rich polymorphic surface over many shallow (DEEP_SURFACES); the owner is shaped for the family it will ABSORB (ANTICIPATORY_COLLAPSE) so the next case/dimension/modality lands as ONE declaration with every consumer untouched or broken loudly at type-check. Choose each owner by the OWNER_CHOOSER discriminants — admission (trusted/untrusted), identity regime (value/tag/key/reference), variant arity (one/closed-family/open), payload timing (def-time/runtime), openness (closed/semi/open) -> the right owner among `TypedDict`, Pydantic, `msgspec.Struct`, frozen dataclass, rich class, `StrEnum`/`Literal`, `sentinel`, `Option`/`Result`, `frozendict`/`Map`/`tuple`, `Protocol`. A misplaced shape traces to one mis-answered discriminant.',
  'ASPECT-FIRST (DEFINITION_TIME_ASPECTS): every CROSS-CUTTING capability — retry, telemetry/spans, validation, contracts, memoization, registration, receipts, fault rails — is a SIGNATURE- and RAIL-PRESERVING decorator (inline `**P` + `functools.wraps`) that materializes policy, STACKS in deterministic order (bottom-up at definition, top-down at call), and NEVER raises into domain flow (a failing aspect returns the rail `Error`). Two-to-four wrappers that always co-occur collapse into ONE parameterized aspect factory. Code reads as STACKED DECORATORS over a thin pure core, never inline-repeated concerns or sibling helper functions; the domain transform itself stays a pure function/fold.',
  'DERIVATION + ARITY: cases sharing generative structure are DERIVED — one primary `frozendict` correspondence declared, every secondary map derived from it (DERIVED_LOGIC), or a fold/comprehension — never enumerated arms. Configuration enters as ONE behavior-carrying value (vocabulary member, tagged variant, frozen policy table), never flag sets the body re-derives (POLICY_VALUES). ONE entrypoint owns every modality (singular/plural/batch/stream), discriminating on the INPUT SHAPE (`T | Iterable[T]` normalized once at the head), never a name suffix or a `mode`/`batch` knob (MODAL_ARITY); a `timeout`/`retry`/`deadline` is an aspect or an `anyio` scope, never a signature param (KNOB_TEST).',
  'RAILS (rails-and-effects): the narrowest carrier that states the outcome, chosen ONCE at admission — `Option[T]` non-failing absence, `Result[T, E]` typed fallibility, `effect.result` do-notation for sequential `bind`, `Block`/`Map` immutable traversal, an `anyio` task group as the failure boundary (NEVER `asyncio.gather`), `stamina.retry` as the decorator (never a sleep-loop). The fault type `E` is a CLOSED vocabulary — `Literal` set, `StrEnum`, or `@tagged_union` family — NEVER a bare `str` for a multi-cause domain. Accumulate-vs-abort is a correctness decision fixed at the boundary: `map2`/accumulating-fold for independent operands (a `bind` chain over independents reports only the first failure), `bind` short-circuit for dependent steps. Cancellation is not failure; resource cleanup is `AsyncExitStack` + a shielded scope.',
  'STACK .api CAPABILITY (load-bearing): FIRST inventory the COMPLETE catalog set under ' + RASM_BAR + ' — BOTH the shared/universal ' + RASM_BAR + '/.api/*.md (anyio, expression, msgspec, pydantic, pydantic-settings, beartype, structlog, stamina, numpy, psutil, opentelemetry-*) AND the folder ' + RASM_BAR + '/runtime/.api/*.md (apscheduler, asyncssh, cyclopts, fsspec, gcsfs, httpx, keyring, universal-pathlib, watchfiles, msgspec) — then mine them for the full ADVANCED surface of each package (combinators, hooks, native pipelines, discriminators, async mirrors) and how packages STACK. DIFF that inventory against what the file already uses: every admitted catalog whose domain the file admits but does NOT yet use is an ADOPTION TARGET. Compose EVERY relevant admitted library into single dense operations woven as ONE rail, and ALWAYS layer the shared/universal rails (expression Result/Option, msgspec/pydantic discriminated models, beartype validation, stamina retry, structlog + opentelemetry spans, anyio structured concurrency) ON TOP OF the folder-specific domain packages — e.g. msgspec dec_hook -> pydantic discriminated union -> stamina retry_context -> opentelemetry span around the domain op — NOT flat one-shot per-library uses. Use the DEEPEST primitive each package itself reaches for (LIBRARY_DEPTH); reject surface-level single-feature subsets and any thin rename wrapper. For the packages Rasm has NO .api catalog for — pulumi, pulumi-docker, pulumi-docker-build, pg8000, sqlglot — do RAW EPHEMERAL research: read the installed package surface in the Maghz env (bash -lc "cd ' + MAGHZ + ' && uv run python -c ...") and the official docs. Author NO catalog files anywhere. Cite a member only after you have seen it in the installed package or its docs.',
  'PRESERVE all capability (densify, never delete functionality). Where a fence is already dense, deepen; where it is flat/naive, build ground-up. Never regress correctness or boundary law.',
].join('\n')
const PATLAW = [
  'PY-VERSION LAW: target Python 3.15 on the full modern band (3.11/3.12/3.13/3.14/3.15) — advanced patterns ONLY, zero legacy idioms, IDENTICAL conventions across every folder and package.',
  'NEVER write `from __future__ import annotations`. NEVER use legacy typing: use PEP 585 builtin generics (`list[T]`, `dict[K, V]`, `tuple[...]`, `set[T]`) NOT `typing.List/Dict/Tuple/Set`; PEP 604 unions (`X | None`, `A | B`) NOT `Optional`/`Union`; PEP 695 type parameters (`class C[T]:`, `def f[T](...)`, `type Alias[T] = ...`) NOT `TypeVar` + `Generic`. Use `Self`, `override`, `TypeIs`/`TypeGuard`, `assert_never`, `ReadOnly`, `TypedDict` + `NotRequired`/`Required`, `LiteralString`, `enum.StrEnum`/`IntEnum`, and `@dataclass(slots=True, frozen=True)` or `msgspec.Struct`/pydantic models where each best fits.',
  'PAYLOADS — NEWEST FORM: ingress payloads are static `TypedDict` contracts with `closed=True` or `extra_items=T` and per-key `Required[]`/`NotRequired[]`/`ReadOnly[T]`, admitted through a module-level `TypeAdapter`, with `Unpack[TypedDict]` at root keyword entrypoints (never forwarded through interiors); extension bands fold into `frozendict`/tuple evidence at materialization, and `msgspec.Struct(frozen=True)` owns wire/egress. NO `dict[str, Any]` bags, homogeneous `**kwargs`, or `Mapping[str, object]` payloads.',
  'FROZENDICT (py3.15 builtin): `from builtins import frozendict` is the owner for immutable map rows, dispatch/policy TABLES (one primary `frozendict[K, tuple[...]]`, secondary maps derived from it), payload `extra_items` extension bands, and immutable evidence — REJECT `MappingProxyType`, a module-level mutable `dict` used as a table, tuple-pair pseudo-maps, and mutate-then-freeze. Prefer total `match`/structural pattern matching over if-chains, walrus where it tightens, `assert_never` on closed unions, and PEP 750 t-strings / PEP 749 deferred annotations where relevant. Keep every choice CONSISTENT across folders so the corpus reads as one ultra-advanced codebase.',
].join('\n')
const BOUNDARIES = 'BOUNDARY LAW: keep every admin domain owner strictly in its lane. The substrate (core/runtime/settings/db) is imported by consumers, never the reverse; consumers consume the locked substrate shapes and NEVER redefine or edit a substrate file; internal code uses canonical names and shapes with mapping only at the edge; do not trample a sibling domain while densifying; respect the import dependency direction.'
const CODESTRUCT = 'CODE STRUCTURE: apply the CLAUDE.md [FILE_ORGANIZATION] law to every .py module — section dividers (comment marker + space + `---` + bracketed `[UPPERCASE_LABEL]` + dash-fill) in the canonical order (RUNTIME_PRELUDE -> TYPES -> CONSTANTS -> MODELS -> ERRORS -> SERVICES -> OPERATIONS -> COMPOSITION -> EXPORTS, omitting unused), ordered owner-block -> dependency -> semantic-rank -> kind -> smaller-to-larger -> alphabetical. Module/function docstrings are contract-first and minimal; names and types carry the meaning, not prose.'
const COMMENTS = 'COMMENT HYGIENE: code is agent-facing — comment for the next agent, never as a tutorial. KEEP the canonical section-divider headers. Beyond dividers, comment ONLY where intent is not already obvious from names, types, and signatures: default to ZERO comments on self-evident code; at most 1 line where a comment genuinely earns its place; 1-2 lines only for a truly subtle invariant, contract, or boundary. NO restating the code, no narration, no task/process/session/history/proof/review comments, no docstring bloat. Densify names and types so comments are rarely needed; cut every low-value comment.'
const DOC = [LAW, '', ULTRA, '', PATLAW, '', BOUNDARIES, '', CODESTRUCT, '', COMMENTS].join('\n')

// --- [MODELS] -- the HARDENED additions: the deep realized-corpus floor the doctrine missed -
const CONCURRENCY = [
  'CONCURRENCY (anyio structured forms — the DEEP bar, far beyond "use anyio not asyncio"): a bounded concurrency owner opens ONE anyio.create_task_group under ONE CapacityLimiter memoised per frozen-hashable lane identity (functools.cache, shared across drain AND offload — a fresh CapacityLimiter per call bounds nothing) and ONE move_on_after(deadline.default_value(inf)) scope (NEVER fail_after, whose TimeoutError escapes the bounded lane without a receipt). A tripped deadline is CONTAINED and reported as a cancelled count with partial values/faults intact. Each unit sends its FULL RuntimeRail[T] over a create_memory_object_stream so the typed Block[Fault] and the recovered Block[T] survive into a lossless parameterized receipt — never a pre-collapsed bool or count-only return.',
  'CPU-BOUND OFFLOAD: route a CPU kernel through anyio.to_interpreter.run_sync (PEP 734 per-subinterpreter GIL, no pickle) under the SAME lane CapacityLimiter and move_on_after, never a process-pool serialization tax. Stitch the W3C trace context across the no-pickle hop: propagate.inject into a dict[str,str] carrier before the hop, a module-level shim propagate.extract+context.attach (token-paired detach in finally) inside the worker. A transient worker cold-start crash retries via an optional retry=RetryClass.<class> wrapping the offload leg in guard(cls) — never a per-caller re-spawn loop. The kernel is RECEIVED, never imported by the lane.',
  'RETRY TRIAD: retry policy is ONE behavior-carrying RetryClass(StrEnum) whose every member binds a frozen Policy row (attempts, timeout, a stamina ExcOrBackoffHook target, four UNSET-defaulting wait_* backoff columns). ONE Policy.schedule projection drops the UNSET columns into the **-spread stamina keyword schema, read once by both the cached bound-caller and the inline retry_context. The target is the FULL stamina discriminator: a bare exception tuple OR a BackoffHook (a Retry-After/server-rate predicate, a by-__qualname__ hook for a provider dark on the runtime band, a status-code predicate). Expose the native triad over the one row — guard(cls) (cached BoundAsyncRetryingCaller), guarded(cls, fn, *args, subject) (the fused span + async_boundary terminal-lift envelope every fetch leg delegates to), guarded_sync, retrying(cls) — plus the sync mirror; never a hand-rolled sleep-loop nor a per-call wait knob threaded through guarded.',
  'SCHEDULING + WATCH: cron/interval/one-off is the apscheduler Trigger union on ONE AsyncIOScheduler (never BlockingScheduler/croniter/aiocron/a hand-rolled anyio.sleep loop), with a single add_listener fire-seam pushing JobExecutionEvent over a bounded memory-object stream whose send_nowait is wrapped in suppress(WouldBlock) (a backpressured overflow is the scheduler coalesce/misfire policy, not a raise). File-change feeds use watchfiles.awatch + a BaseFilter, matching the Change enum — never a stat poll loop.',
  'RESOURCE BRACKETS: materialize a resource result INSIDE its `with` bracket so it releases on success/fault/cancellation (a connection leaked past the run is a defect). The boundary catch takes a native type[BaseException] | tuple[...]: narrow it to a real multi-class engine surface, but choose the BROAD Exception deliberately when the backend roots are DISJOINT (a driver error vs an ORM error vs pyarrow) and a classifying CLASSIFY fold owns the dispatch.',
].join('\n')
const BANDS = [
  'DUAL-BAND IMPORT LAW: a dist clean on the runtime core imports module-top; a dist gated to a companion band (or heavy host-side, like pulumi/pulumi-docker) is typed STRUCTURALLY under `if TYPE_CHECKING:` (@runtime_checkable Protocol phantom handles) and imported function-locally with `# noqa: PLC0415` inside the body that needs it — never module-top (it would crash/slow the core load). A transient whose package is dark on the core is named by __qualname__ in a BackoffHook, never imported as a type. A DecompressFn/ProviderFn Protocol seam injects the gated capability rather than hardwiring its import. For Maghz: pg8000/sqlglot are core-clean (module-top); the Pulumi program imports gate function-locally where define() is built.',
  'ADMISSION + SINGLE-MINT: narrow untrusted input with beartype.door.is_bearable/TypeIs BEFORE a gated import or expensive call, and emit a domain reject as a DIRECT Error(BoundaryFault(...)) — distinct from an exceptional boundary fence; a thunk that raises a TypeError for the fence to re-catch is the deleted form. Honor the single-mint invariant: a value minted by one owner is DECODED elsewhere on the rail and re-spelled NOWHERE — a duplicated rendering/pack beside the canonical projection is a defect.',
  'STRUCTURAL PORTS: type a heterogeneous capability set against a structural Protocol (force_flush/shutdown), never object. A cross-cutting evidence port (ReceiptContributor.contribute -> Iterable[Receipt]) STREAMS a sequence so a multi-phase producer yields several facts; siblings flatten to scalar receipt fields so the receipt owner imports no producer module except one deliberate acyclic value-object edge.',
].join('\n')
const DEEP_FORM = [
  'DEEP-FORM CHECKLIST (the realized-corpus bar — a SHALLOW satisfaction of a named pattern is a DEFECT; each below is the mechanically-strict form, drawn from the Rasm runtime/compute/data .planning pages):',
  'SHAPES: a behavior-carrying StrEnum binds its secondary scalar onto the member via __new__ (member.arity=arity), never a parallel dict[Member,scalar] sidecar — the member IS the row, and every catalogued datum MUST be SPENT in dispatch (an unread enum property is dead pressure, a defect). A closed family carries DIVERGENT per-case tuple payloads (never one flat struct with method:str + nullable union-of-all-slots), the Literal tag IS the discriminant read as .tag (never a .method alias), each case gets a named @staticmethod smart-constructor filling defaults + freezing Sequence->tuple at the edge. A frozen=True carrier field is tuple/frozenset/frozendict, never list/set/dict/Sequence. msgspec.Struct(gc=False) ONLY when every field is a non-container leaf; a struct holding a tuple-of-objects/Map/callable/struct-ref stays GC-tracked. Nested unions own DISTINCT tag_field names; an open tail is ClosedEnum | OneConstrainedArm (Annotated[str, Meta(pattern=...)]), never widening the field to str; recover a minted discriminant from struct.__struct_config__.tag.',
  'RAILS: railed = effect.result[Any, E]() is ONE bound module-level builder applied only past a 3-level interleaved-bind threshold (below it use .map/.bind; for a homogeneous Block of evaluated rails use traversed, NOT a railed re-collect); bind loop vars as defaults (cell=cell) so deferred thunks do not capture the last iterate. Accumulate/abort/partition is ONE traversed(rails,*,by=Disposition) fold whose @overload arms keyed on the Disposition Literal carry the per-disposition OUTPUT shape — never three sibling functions nor a runtime union the caller re-narrows. The fault family is ONE tagged_union with an aggregate case (a combine flatten law); leaf construction is ONE ORDERED CLASSIFY:Block[(exc-family,builder)] folded choose->try_head->default_with (row order load-bearing: a subclass exc precedes its base), never per-case factories nor a next()/or totality; facts() is ONE total match -> dict[str,object] carrying NATIVE int/float scalars (a pre-str()/f-string coerce is a defect); recovery keys on frozenset[FaultTag] membership. RECORD-DONT-ENFORCE: a validation/contract owner returns Ok(claim) carrying a status even when the claim FAILS — the rail is Error only on infrastructure fault; enforcement is the caller match.',
  'ASPECTS: a cross-cutting aspect that varies per owner is parameterized over an INJECTED accessor triple (read/write/reentrant or owner/redaction) and over [R,**P]/[**P,R:Port] so ONE factory serves every owner + concrete receipt subtype — never a name-bound guard hardcoding Owner._slot nor a case ConcreteReceipt() re-pin; the subtype is PRESERVED through the bound, not erased to the Protocol. The aspect dispatches sync-vs-async by inspect.iscoroutinefunction ONCE at decoration, folding both arms onto ONE core, the async arm awaiting the library loop-friendly mirror (structlog ainfo) bound as the 2nd element of a (sync,async) selector row — a getattr(log,level)/getattr(log,"a"+level) over an open namespace is the deleted form. Placement is load-bearing: a redaction processor runs chain-resident AFTER the contextvars/trace injectors; a context-propagation seam splits into a pure extract->Context value the rail threads and a SEPARATE token-paired attach @contextmanager. @beartype(conf=FAULT_CONF) (one shared BeartypeConf(violation_type=BeartypeCallHintViolation)) decorates EXACTLY the public admission seams (.of/.run/.admit); interior folds carry NO contract decorator.',
  'API-STACKING: a dispatch/policy frozendict binds enum keys to the ECOSYSTEMS OWN callables (operator.gt, a library check method, a driver closure) — collapsing N match arms to one lookup that re-implements nothing; where the enum VALUE can BE the library symbol, dispatch by getattr(lib, self.value)(...). Stack span+fault-fence+retry+codec into ONE direction-parameterized woven fold where a (verb,kind,annotate) row is the only direction axis — a CONSUMER decode and a PRODUCER encode share one span-open and one boundary fence, never a second rail per direction. Mine msgspec to its DEEPEST surface: convert(mapping,Struct,strict=False) coerces wire strings AND runs Meta bounds in the C core (a direct Struct(...) bypasses them); msgspec.Raw is a deferred-decode carrier; to_builtins->overlay->convert is the single-pass partial patch; inspect.multi_type_info/json.schema_components/structs.fields are a LIVE type-contract; a bound overflowing int64 is rejected at Decoder construction so a wire slot carries a Meta(ge=0) floor and the upper ceiling stays the owner construction guard; reshape a known tagged-union wire array via a two-stage Raw re-decode, NEVER a dec_hook. Reach the package deepest native primitive (a dual-return flag, a lineage engine like sqlglot.lineage, one shared application registry) over a hand cross-product or per-module instances.',
  'PAYLOADS: realize the spine with a RAILED content key — ContentIdentity.of(...) -> RuntimeRail[ContentKey] derived ONCE at the head and bound/threaded into every downstream arm, never re-minted inside a boundary thunk nor repr()-hashed. Parameterize egress over OUTPUT SHAPE through @overload on a view Literal (KeyView/AttrShape/SecretShape) so ONE owner sinks as value-object/hex/LE-bytes/JSON/to_builtins record — never a per-render method. Domain facts ride as NATIVE scalars on a dict[str,object] straight to ONE msgspec.json.Encoder(enc_hook=repr, order="deterministic") (the encoder owns coercion; the deterministic key order doubles as the canonical hash input) — a producer-side str()/f-string/join pre-coerce is a defect; mint a named-fact map from a _SLOTS[tag] name-table zipped with the destructured case tuple under strict=True so table and payload cannot drift.',
].join('\n')
const DOC2 = [DOC, '', CONCURRENCY, '', BANDS].join('\n')

// --- [MODELS] -- NO-KEYCHAIN LAW (security-critical: op-injected env primary, never login keychain) -
const NO_KEYCHAIN = 'NO-KEYCHAIN LAW (security-critical, non-negotiable): admin/rails/cloud.py and the n8n API-key path use the op-injected ENVIRONMENT as the PRIMARY and only secret source — the macOS login keychain is NEVER read or written. REMOVE every keyring usage (no keyring.get_password fallback that could surface a Touch-ID/password prompt); a secret resolves from os.environ (op-injected MAGHZ_*/provider env) or it is absent and the rail returns a typed BoundaryFault, never a keychain prompt and never an interactive unlock. N8N_API_KEY is vaulted as op://Tokens/N8N_API_KEY and reaches the process as env; it is never stored in or read from a keychain. rclone cloud tokens ride MAGHZ_CLOUD__REMOTES__* env, never a keychain/rclone.conf secret. Demote keyring to nothing — if a settings field defaulted to a keyring lookup, repoint it at the env owner.'

// --- the rebuild-python critique/redteam SPEC, reused verbatim + the DEEP_FORM extension ----
const T = {
  getFamily: '`get`/`get_many`/`get_by_id`', table: 'a `frozendict` table or fold algebra', collapse: 'one closed `@tagged_union`/discriminated-Pydantic family', constTable: 'one `frozendict`/`StrEnum`', aspectFactory: 'one parameterized aspect factory',
  owners: '`TypedDict`/Pydantic/`msgspec.Struct`/frozen dataclass/rich class/`StrEnum`/`Literal`/`sentinel`/`Option`/`Result`/`frozendict`/`Map`/`tuple`/`Protocol`', nullFail: '`None`-as-failure', receipt: '',
  flags: '`strict: bool`/`mode`/`batch` flag', knobScope: 'an aspect or `anyio` scope', aspectForm: 'a SIGNATURE- and RAIL-PRESERVING stacked decorator (inline `**P` + `functools.wraps`)', unit: 'functions',
  rails: 'the narrowest carrier that states the outcome — `Option[T]` non-failing absence, `Result[T, E]` typed fallibility, `effect.result` do-notation, an `anyio` task group as the failure boundary (NEVER `asyncio.gather`), `stamina.retry` as the decorator (never a sleep-loop)', faultVocab: '`Literal` set / `StrEnum` / `@tagged_union` family', looseFault: 'a bare `str` fault', accumulate: '`map2`/accumulating-fold for independents, `bind` short-circuit for dependents', dispatch: '`match`', foldForm: 'fold/comprehension',
  check6: 'PAYLOADS/FROZENDICT/PEP — payloads are `closed=`/`extra_items=` `TypedDict` via a module-level `TypeAdapter` with `Unpack[TypedDict]` at root entrypoints; `frozendict` (builtin) owns tables/evidence (no `MappingProxyType`/dict-table/tuple-pairs); PEP 585/604/695 only, no `from __future__ import annotations`, no legacy typing; total `match` + `assert_never`.',
  doctrine: 'the Rasm libs/python/.planning/ exemplar pages and the .api catalogs', compileWord: 'type-check', boundaryExtra: '', memberVerify: 'verify the member exists in the `.api` catalog or by reading the installed package', coldDims: 'payload/`frozendict`/PEP conformance, both-tier `.api` maximization, py3.15-modern typing, CONCURRENCY + BANDS + DEEP-FORM conformance',
}
const critiqueTemplate = (t) => [
  'You are an ULTRA-HARSH, UNAGREEABLE auditor: assume a violation exists in every fence until you prove otherwise, and "good enough" is rejected. Run these MECHANICAL checklists line-by-line and REPAIR every hit in place (a fix, never a ledger note):',
  '(1) COLLAPSE_SCAN — apply the move for any signal (3+ instances makes it mandatory): sibling prefix/suffix names -> one modality-polymorphic entrypoint; the same return rail differing only by arity -> input-shape discrimination; a ' + t.getFamily + ' family -> one input-keyed entrypoint; functions differing only by a literal -> parameterize the literal as policy; a bool parameter selecting two bodies -> one derived body or policy value; a function calling exactly one other -> delete the hop; a class/owner exposing one public method -> a free operation or fold-on-owner; parallel dispatch arms repeating structure -> ' + t.table + '; 3+ parallel types / sibling factories / near-duplicate shapes for one concept -> ' + t.collapse + '; 3+ sibling constants for one concept -> ' + t.constTable + '; a wrapper renaming a package API -> use the package surface directly; the same 2-4 wrappers/decorators recurring -> ' + t.aspectFactory + '.',
  '(2) OWNER_CHOOSER — for EVERY shape re-derive the owner from the 5 discriminants (admission, identity regime, variant arity, payload timing, openness); if it is not the discriminant-correct owner (' + t.owners + '), replace it. Kill every parallel DTO, one-field wrapper, field-rename shape, tag-only shape, and ' + t.nullFail + '.' + t.receipt,
  '(3) KNOB_TEST — delete each parameter: if the value already encodes what it carried, it was a knob — collapse a ' + t.flags + ' into a policy value or input-shape discriminant, and move every `timeout`/`retry`/`deadline` out of the signature into ' + t.knobScope + '.',
  '(4) ASPECTS — every cross-cutting concern (retry/telemetry/validation/contracts/memo/registration/receipts/fault rails) MUST be ' + t.aspectForm + ' that never raises into domain flow; 2-4 co-occurring wrappers collapse into one aspect; deterministic stacking order verified. Inline-repeated concerns and sibling helper ' + t.unit + ' are defects.',
  '(5) RAILS — ' + t.rails + ', the narrowest carrier chosen once; the fault type is a CLOSED ' + t.faultVocab + ' (' + t.looseFault + ' for a multi-cause domain is a defect); accumulate-vs-abort disposition correct (' + t.accumulate + '); total ' + t.dispatch + ' with exhaustiveness; NO exception control flow in domain logic, NO mutable accumulation (' + t.foldForm + ').',
  '(6) ' + t.check6,
].join('\n')
const redteamTemplate = (t) => [
  'You are the LAST and MOST AGGRESSIVE pass: assume the author and critique missed things and that the chosen design is not the strongest until proven, with the burden of proof on the design, never on you. Open BOTH `.api` tiers, the relevant ' + t.doctrine + '. Attack from every direction and REPAIR every defect in place — no soft-pedalling, no could/should, a fix never a ledger.',
  'PRIMARY LENS — fundamental design, multi-faceted / multi-dimensional / multi-directional: (A) COUNTERFACTUAL on the core choice — is the owner, the algebra, and the dispatch form categorically the strongest the doctrine admits, or does a denser owner (' + t.collapse + '), ' + t.table + ', or a DEEPER admitted-package primitive collapse the whole fence? If a fundamentally stronger design exists, rebuild to it — never defend the incumbent. (B) ANTICIPATORY_COLLAPSE — compute the DIFF OF THE NEXT FEATURE: when the next case/dimension/knob/modality/provider arrives, does it land as ONE declaration with every consumer untouched (or broken loudly at ' + t.compileWord + ')? If it would touch multiple sites, reshape so the growth axis is a case, row, policy value, or carrier swap. (C) LONG-TAIL + MULTI-DIMENSIONAL — attack every input/output/edge/failure mode (empty, singular, plural, stream, malformed, concurrent, cancelled, partial-failure, version-skew); is the accumulate-vs-abort disposition correct for the REAL boundary; are BOTH ingress AND egress parameterized so this owner sources and sinks across hundreds of apps without interior edits? (D) BOUNDARY-INTEGRITY — a concern owned twice in a runtime, ' + t.boundaryExtra + 'a folder mixing concerns, a concern scattered across folders, or any coupling to a sibling owner\'s INTERIOR (vs its wire/seam) is a defect: fix it, or record it as a cross-file residual. (E) SURFACE-SPRAWL-IN-TIME — an admitted package whose `.api` exposes capability the fence re-derives by hand, flat code below the operator depth the packages reach, a phantom member, or a thin wrapper: collapse to package depth and ' + t.memberVerify + '.',
  'ALSO — FULL COLD ADVERSARIAL RE-REVIEW (run this every time, NOT only when an architectural restructure is warranted): re-attack every conformance dimension with fresh hostile eyes, trusting nothing the prior passes claimed — the COLLAPSE_SCAN signals, OWNER_CHOOSER correctness per shape, the KNOB_TEST per param, the ASPECT taxonomy, rail + closed-fault-vocabulary discipline, ' + t.coldDims + ', and comment hygiene — and fix every defect. Even absent a structural rebuild, the code must end objectively denser, more correct, and more powerful than the critique left it; if the strongest form is genuinely already present, prove it by finding nothing — never invent churn.',
].join('\n')
const critiqueDeep = (t) => critiqueTemplate(t) + '\n' + DEEP_FORM
const redteamDeep = (t) => redteamTemplate(t) + '\n' + DEEP_FORM

// --- [TABLES] -- EXEMPLAR_PINS: each Maghz substrate owner -> the EXACT runtime page it matches -
const EXEMPLAR_PINS = [
  { owner: 'BoundaryFault / RuntimeRail / CLASSIFY / boundary+async_boundary+trapped / traversed+Disposition / railed', page: RASM_BAR + '/runtime/.planning/reliability/faults.md' },
  { owner: 'RetryClass / Policy / POLICY / guard / guarded / guarded_sync / retrying / install', page: RASM_BAR + '/runtime/.planning/reliability/resilience.md' },
  { owner: 'LanePolicy.drain / Admit+ADMIT_TABLE / DrainReceipt / offload(PEP734+trace-stitch) / StagePlan / LaneSource / feed / @drained', page: RASM_BAR + '/runtime/.planning/execution/lanes.md' },
  { owner: 'Receipt / Signals / @receipted / @drained / Redaction / ReceiptContributor / sync+async level mirror', page: RASM_BAR + '/runtime/.planning/observability/receipts.md' },
  { owner: 'telemetry install (SignalSpec row table, latched one-shot, force_flush+shutdown drain, resource detector merge)', page: RASM_BAR + '/runtime/.planning/observability/telemetry.md' },
  { owner: 'wire/egress (_traced direction-parameterized woven rail, msgspec convert(strict=False))', page: RASM_BAR + '/runtime/.planning/transport/wire.md' },
  { owner: 'ContentIdentity / ContentKey (railed content key threaded by bind, @overload egress views)', page: RASM_BAR + '/runtime/.planning/evidence/identity.md' },
  { owner: 'Hlc / CausalFrame / clock (single-mint, gc=False leaf cells)', page: RASM_BAR + '/runtime/.planning/clock/clock.md' },
  { owner: 'db + rails .api-stacking-into-one-rail (guarded . worker-offload . fault-lift; frozendict of ecosystem callables; resource brackets)', page: RASM_BAR + '/data/.planning/tabular/query.md' },
  { owner: 'SmartEnum __new__ data-carry + divergent-tuple cases + named smart-constructors', page: RASM_BAR + '/compute/.planning/numerics/quantity.md' },
]
const PINS_TEXT = EXEMPLAR_PINS.map((p) => '- ' + p.owner + '  ->  ' + p.page).join('\n')

// --- [TABLES] -- the DECISION-LOADED architecture (settled by the investigations) ---------
const FILEMAP = [
  'FILEMAP (the settled 31->~21 restructure — EXECUTE it, do not re-derive; never drop a behavior, fold each deleted module into the named owner):',
  'SUBSTRATE: admin/core/{status.py+model.py+__init__.py} -> ONE admin/core.py (Status + Detail/Row/Report/Envelope + completed/fault, the result algebra). admin/settings/{config.py+__init__.py} -> ONE admin/settings.py (MaghzSettings + all subgroups + settings()). admin/runtime/ STAYS a package (rails/resilience/lanes/receipts + barrel). admin/db.py STAYS (returns RuntimeRail[QueryResult]).',
  'CONSUMERS: admin/infra/{stack.py folded INTO runner}+__init__.py -> ONE admin/infra.py (runner dispatch absorbing the Pulumi program define()). admin/remote/{connection.py+ops.py+__init__.py} -> ONE admin/remote.py (target/connection lifecycle + exec/deploy ops). admin/rails/ STAYS (the __init__ CLI mount barrel + ledger/schema/sync/n8n/cloud). admin/automation/ STAYS (model + engine). admin/mcp/ STAYS (the ops owner + _SERVER_TABLE; a prior pass may have folded model into ops — keep that collapse, never split it back).',
].join('\n')
const COLLAPSE = [
  'COLLAPSE (the settled cross-file unifications — execute every one):',
  '1. ONE BoundaryFault fault family: DELETE the three per-rail carriers DbFault, CloudFault, N8nFault and their .envelope()/.lift() methods. Each rail mints BoundaryFault(boundary=(subject,detail)) directly (remote/ops.py already proves a rail uses BoundaryFault carrier-free).',
  '2. db.query returns RuntimeRail[QueryResult] (Result[QueryResult, BoundaryFault]) DIRECTLY — the lift happens once inside db.py, so the 4 identical DbFault->BoundaryFault lift arms in ledger/schema/sync vanish.',
  '3. ONE runtime.spawn(argv, *, subject, retry_class) -> RuntimeRail[CompletedProcess] boundary owning anyio.run_process(check=False) + guard(retry_class) + exit-grading + stderr-decode — the 4 hand-rolled subprocess+exit+stderr sites in cloud/n8n/schema/sync (and the git pair in remote) compose it instead of re-deriving the offload->guard->grade chain.',
  '4. Drop the redundant match/assert_never ceremony around a TOTAL _BUILD frozendict subscription — run(op) = await _BUILD[op](cfg) when the table is already exhaustive.',
].join('\n')
const EXT_CATALOG = [
  'EXT_CATALOG (the typed extension/profile owner — the one structural IaC defect to fix):',
  'The extension set is hand-maintained in FOUR uncoordinated places (admin/infra shared_preload_libraries, image/Dockerfile apt list, db/routines.sql CREATE EXTENSION, db/cron.sql). Build ONE typed catalog (the mcp _SERVER_TABLE / `mcp generate` analogue): an ExtensionSpec-keyed frozendict, each row carrying name, category, requires_shared_preload:bool, cascade:bool, source (paradedb-base|pgdg|pigsty), target_db (maghz|postgres).',
  'GENERATE the four downstream surfaces from the ONE catalog: the Dockerfile apt block (rows source!=paradedb-base), the routines.sql CREATE EXTENSION prelude (target_db==maghz), the cron.sql pg_cron line (target_db==postgres), and the shared_preload_libraries string (requires_shared_preload==true). Add a doctor census-diff verb asserting the installed pg_extension census == the declared catalog (mirroring `mcp validate` for .mcp.json).',
  'Keep all 19 current extensions (vector, pg_search, pg_ivm, pg_net, pgmq, pg_jsonschema, hll, pg_partman, hypopg, pg_trgm, unaccent, fuzzystrmatch, citext, ltree, pgcrypto, btree_gin, btree_gist, pg_stat_statements, tablefunc + pg_cron in postgres). CASCADE discipline already correct.',
].join('\n')
const PULUMI_DEEPEN = [
  'PULUMI_DEEPEN (deepen admin/infra.py stack/runner — the orchestration layer is already excellent, the resource declarations are shallow):',
  'docker_build.Image gains BuildKit cacheFrom/cacheTo (CacheFromArgs(local=...)/CacheToArgs(local=..., mode="max")) so the apt-layered extension build is not re-run cold every converge. Wrap the stack as a ComponentResource (a MaghzStack) so converge/preview group by logical unit. docker.Container gains OCI labels, ulimits, memory limits, and healthcheck depends_on gating between db and dependents.',
  'Feed pulumi.export typed Outputs back through the Automation API (up_result.outputs["db_dsn"].value) into the settings layer instead of the f-string db_dsn that DUPLICATES + DRIFTS FROM DatabaseConfig.dsn. Fix BL-1: the stack must actually provide N8N_ENCRYPTION_KEY to the n8n container (a real mounted key file or a pulumi secret), not a /run/secrets path absent on Colima/macOS; create the missing workflows/n8n directory contract the n8n host_path mount needs. Hold the dual-band law: heavy pulumi imports gate function-locally where define() is built.',
].join('\n')
const MCP_TRIM = [
  'MCP_TRIM (.mcp.json 7->4, the one genuine surface dedup):',
  'Web research is triplicated SIX ways (exa/perplexity/tavily as BOTH MCP servers AND skill CLIs) for a single agent-in-session consumer. DROP the three research MCP servers (exa, perplexity, tavily) from the mcp domain _SERVER_TABLE and regenerate .mcp.json — KEEP the three skill CLIs (zero idle context cost, portable, callable from a future research rail). .mcp.json drops from 7 to 4 servers: postgres, n8n, workspace, notebooklm (the genuinely-interactive servers with no skill-CLI equivalent).',
  'Postgres + n8n stay DUAL-SURFACE deliberately (the rail owns deterministic truth, the MCP owns live agent exploration — two distinct consumers). Ownership rule: surface is chosen by CONSUMER (deterministic code -> rail; live agent exploration -> MCP; on-demand portable reach -> skill), not by concern.',
].join('\n')
const PG_DOCTOR = [
  'PG_DOCTOR (make "world-class, running" VERIFIABLE — extend the schema doctor verb):',
  'Liveness assertions, each a typed rail returning the census/gap as evidence (mirroring mcp validate): (1) installed pg_extension census == the declared EXT_CATALOG (fail on drift); (2) SHOW shared_preload_libraries == the catalog requires_shared_preload rows; (3) the cron.job rows are registered AND the pg_net->Ollama embed loop is draining (embed_request draining / >=1 embedding written); (4) the 6 exotic mz_* search indexes exist (the BM25/HNSW/gin/trgm engine).',
  'PG CAPABILITY: target PG18.4 (paradedb 0.24.1-pg18 ships >=18.4). ADD pgvectorscale (DiskANN, the one material scale gap for >1M concepts, via PIGSTY postgresql-18-pgvectorscale) + pg_squeeze (autonomous bloat) to the catalog. TUNE pgvector-0.8 iterative-scan GUCs (hnsw.iterative_scan=relaxed_order) in the maghz.search filtered-semantic CTE. Do NOT add PostGIS/TimescaleDB/pg_duckdb (they do not fit a knowledge ledger).',
].join('\n')

// --- [TABLES] -- the PER-FILE unit sets (decision-loaded from FILEMAP) --------------------
// Each substrate file owns named canonical shapes; the ownership map is the locked contract
// every file authors against so the parallel per-file impl converges (gate barrier reconciles).
const SUBSTRATE_FILES = [
  { file: 'admin/core.py', folder: 'core', owns: 'Status, Detail, Row, Report, Envelope, completed(), fault() — the result/envelope algebra', from: 'admin/core/{status.py,model.py,__init__.py}', pin: '' },
  { file: 'admin/runtime/rails.py', folder: 'runtime', owns: 'BoundaryFault (ONE tagged_union + aggregate case + combine flatten law), RuntimeRail, CLASSIFY (ordered Block[(exc-family,builder)] choose/try_head/default_with fold), boundary, async_boundary, trapped, traversed + Disposition @overload fold, railed, spawn(argv,*,subject,retry_class)->RuntimeRail[CompletedProcess]', from: '', pin: RASM_BAR + '/runtime/.planning/reliability/faults.md  (+ execution/lanes.md for the spawn boundary)' },
  { file: 'admin/runtime/resilience.py', folder: 'runtime', owns: 'RetryClass (StrEnum __new__ data-carry), Policy + POLICY row table, guard, guarded, guarded_sync, retrying, install — the retry triad over ONE row', from: '', pin: RASM_BAR + '/runtime/.planning/reliability/resilience.md' },
  { file: 'admin/runtime/receipts.py', folder: 'runtime', owns: 'Receipt, Signals, @receipted, Redaction, ReceiptContributor (streamed evidence port), sync+async structlog level mirror', from: '', pin: RASM_BAR + '/runtime/.planning/observability/receipts.md' },
  { file: 'admin/runtime/lanes.py', folder: 'runtime', owns: 'LanePolicy.drain, Admit + ADMIT_TABLE, DrainReceipt (lossless), offload (PEP734 to_interpreter + W3C trace-stitch), StagePlan, LaneSource, feed, @drained', from: '', pin: RASM_BAR + '/runtime/.planning/execution/lanes.md' },
  { file: 'admin/db.py', folder: 'db', owns: 'QueryResult, query(...) -> RuntimeRail[QueryResult] (the BoundaryFault lift happens ONCE here; .api-stack guarded . worker-offload . fault-lift in one call; a frozendict of pg8000 callables; request-scoped resource brackets)', from: '', pin: RASM_BAR + '/data/.planning/tabular/query.md' },
  { file: 'admin/settings.py', folder: 'settings', owns: 'MaghzSettings + all subgroups + settings()', from: 'admin/settings/{config.py,__init__.py}', pin: '' },
]
const SUBSTRATE_CONTRACT = 'LOCKED SUBSTRATE OWNERSHIP MAP (every substrate file owns its shapes and imports siblings BY NAME against these exact owners — author to this contract so the parallel per-file rebuild converges; the substrate gate barrier reconciles any drift):\n' + SUBSTRATE_FILES.map((s) => '- ' + s.file + ' OWNS: ' + s.owns).join('\n')
const CONSUMER_FILES = [
  { file: 'admin/automation/model.py', folder: 'automation', note: '', extra: '' },
  { file: 'admin/automation/engine.py', folder: 'automation', note: '', extra: '' },
  { file: 'admin/mcp/ops.py', folder: 'mcp', note: 'mcp owns the _SERVER_TABLE that generates .mcp.json; fold any mcp/model.py shapes into this ONE owner (a prior pass may already have collapsed model into ops — keep that collapse, never split it back).', extra: '' },
  { file: 'admin/rails/ledger.py', folder: 'rails', note: '', extra: '' },
  { file: 'admin/rails/schema.py', folder: 'rails', note: '', extra: '' },
  { file: 'admin/rails/sync.py', folder: 'rails', note: '', extra: '' },
  { file: 'admin/rails/n8n.py', folder: 'rails', note: 'Compose runtime.spawn for the n8n CLI legs; the n8n API key is op-injected env.', extra: NO_KEYCHAIN },
  { file: 'admin/rails/cloud.py', folder: 'rails', note: 'rclone Drive/OneDrive sync rail; tokens are MAGHZ_CLOUD__REMOTES__* env.', extra: NO_KEYCHAIN },
  { file: 'admin/infra.py', folder: 'infra', note: 'FILEMAP merge: fold admin/infra/stack.py INTO admin/infra.py (the runner dispatch absorbs the Pulumi program define()). Hold the dual-band import law: gate heavy pulumi/pulumi-docker imports function-locally with # noqa: PLC0415 where define() is built.', extra: '' },
  { file: 'admin/remote.py', folder: 'remote', note: 'FILEMAP merge: merge admin/remote/connection.py + ops.py into admin/remote.py (target/connection lifecycle + exec/deploy ops over asyncssh; the git push/pull pair composes runtime.spawn).', extra: '' },
]

// --- [OPERATIONS] -- gate prompts (python + multi-language) -------------------------------
const gateFixPrompt = (paths) => [DOC, '', 'TASK: RUN THE MAGHZ PYTHON GATE on the rebuilt files and FIX every diagnostic IN PLACE until green — loop ENTIRELY WITHIN THIS ONE TASK (run, fix, re-run, repeat; never stop at the first pass). Run it yourself, exactly this (the bash -lc cd form avoids a cd permission prompt):',
  '  bash -lc "cd ' + MAGHZ + ' && uv run ruff check ' + paths + ' && uv run ty check ' + paths + '"',
  'ty is the BINDING gate ([tool.ty.rules] all=error, error-on-warning=true; respect-type-ignore-comments=false so a `# type: ignore` does NOTHING); ruff must also be clean. mypy/basedpyright are ADVISORY — note them in `advisory`, do not loop on them. Read each diagnostic, fix the SOURCE: never add a type-ignore, never weaken a type to silence ty, never edit pyproject to relax a rule, never delete capability to pass. A broken package barrel (__init__.py) re-export is yours to fix here. Re-run after EACH fix and KEEP GOING until both ruff and ty are clean, or you can prove a diagnostic is a real cross-file residual outside these paths. Return GATE_RESULT with green, ruff_clean, ty_clean, the number of internal fix passes in `rounds`, and any `remaining` diagnostics if not green.',
  'PATHS: ' + paths].join('\n')
const multiGatePrompt = (pyPaths) => [DOC, '', 'TASK: RUN THE FULL MULTI-LANGUAGE MAGHZ GATE and FIX every diagnostic IN PLACE until green — loop within this one task (run each, fix the source, re-run until clean). The checks, in order:',
  '  PYTHON (BINDING): bash -lc "cd ' + MAGHZ + ' && uv run ruff check ' + pyPaths + ' && uv run ty check ' + pyPaths + '"  — ty binding; never a type-ignore, never relax a rule, never delete capability.',
  '  SQL: bash -lc "cd ' + MAGHZ + ' && sqlfluff lint db --dialect postgres ; sqruff lint db"  — fix DDL/routines/cron; if a linter is genuinely absent on PATH note it in advisory and skip (not a failure).',
  '  DOCKERFILE: bash -lc "cd ' + MAGHZ + ' && hadolint image/Dockerfile"  — fix; if hadolint is absent, advisory.',
  '  MCP CONFIG: confirm .mcp.json parses as JSON (a one-line python json.load) AND run `bash -lc "cd ' + MAGHZ + ' && uv run python -m admin mcp validate"` so every ${MAGHZ_MCP__...} placeholder is backed and the server count is the post-trim 4.',
  'green = ruff AND ty clean AND every other language parses + lints clean (a genuinely-absent linter is advisory, never a hard failure). Return GATE_RESULT with green/ruff_clean/ty_clean, the internal fix-pass count in `rounds`, `remaining` if not green, and `advisory` for any skipped-tool notes.',
  'PYTHON PATHS: ' + pyPaths].join('\n')
const gateLoop = async (label, paths, phaseTag) => agent(gateFixPrompt(paths), { label: 'gate:' + label, phase: phaseTag, schema: GATE_RESULT, effort: 'high', stallMs: 600000 })
const multiGateLoop = async (label, pyPaths, phaseTag) => agent(multiGatePrompt(pyPaths), { label: 'gate:' + label, phase: phaseTag, schema: GATE_RESULT, effort: 'high', stallMs: 600000 })

// --- [OPERATIONS] -- reconcile clustering (reused verbatim) -------------------------------
const clusterByFiles = (items) => {
  const parent = new Map(); const find = (f) => { let p = f; while (parent.get(p) !== p) p = parent.get(p); return p }; const add = (f) => { if (!parent.has(f)) parent.set(f, f) }
  for (const it of items) { (it.files || []).forEach(add); for (let i = 1; i < (it.files || []).length; i++) parent.set(find(it.files[i]), find(it.files[0])) }
  const by = new Map()
  for (const it of items) { const root = (it.files && it.files.length) ? find(it.files[0]) : '__none__'; (by.get(root) || by.set(root, []).get(root)).push(it) }
  return [...by.values()]
}
const reconcileFixPrompt = (cl) => [DOC2, '', 'TASK: RECONCILE these cross-FILE residuals deferred by the realize + review passes (edit the .py source on disk). NO severity — treat EVERY residual as must-address. Read EVERY listed file. For each: if it is a real cross-file defect, FIX it in place (unify the shared type/seam/rail, repair the boundary issue), preserving all capability and regressing no file; if a residual is FACTUALLY INCORRECT, leave it and say why — never silently skip a real one. Residuals:\n' + JSON.stringify(cl, null, 1)].join('\n')
const reconcileVerifyPrompt = (cl, fix) => [DOC, '', 'TASK: ADVERSARIAL VERIFY, one verdict per claim. Read the named files from disk and classify each residual: "fixed" (real defect, now genuinely resolved), "invalid" (the claim is factually wrong — cite why), or "open" (real defect still NOT resolved). Default to "open" on doubt; mark "invalid" ONLY when you can show the claim is wrong. Claims:\n' + JSON.stringify(cl, null, 1) + '\nFiles the fixer touched: ' + JSON.stringify((fix && fix.files) || [])].join('\n')
const commitMaghz = (tag) => agent('TASK: run exactly `bash -lc "cd ' + MAGHZ + ' && git add -A && git commit -m \'maghz-deepen: ' + tag + ' green\'"` and report the commit short-hash. If there is nothing to commit, say so. Make no other change.', { label: 'commit:' + tag, phase: 'Gate', model: 'haiku', effort: 'low', stallMs: 120000 })

// --- [OPERATIONS] -- per-file impl/critique/redteam prompt builders -----------------------
const substrateImplPrompt = (s) => [DOC2, '', 'TASK: REBUILD the single Maghz substrate file ' + s.file + ' to the EXACT Rasm runtime exemplar form as REAL CODE. Author ONLY ' + s.file + ' (create it if the FILEMAP folds sources into it). You OWN: ' + s.owns + (s.from ? ('. FOLD IN (never drop a behavior): ' + s.from) : '') + '.',
  s.pin ? ('EXEMPLAR PIN — READ the pinned page and realize its EXACT DEEP FORM (the page IS the bar as real code: its CLASSIFY table, its traversed+Disposition @overload fold, its aggregate fault + combine law, its memoised-per-identity CapacityLimiter + move_on_after lane, its lossless DrainReceipt, its PEP-734 offload + trace-stitch, its accessor-injected aspects + sync/async mirror, its native-scalar facts to a deterministic encoder, its railed content key): ' + s.pin) : '',
  '', SUBSTRATE_CONTRACT, '', FILEMAP, '', COLLAPSE, '',
  'Import sibling substrate shapes BY NAME against the ownership map above (the import resolves once every substrate file lands; the substrate gate reconciles). For pg8000/sqlglot do RAW research of the installed surface in the Maghz env — no catalog. Capability PRESERVED AND ENHANCED. Author ONLY ' + s.file + '. Return ONE FIXLOG (file=' + s.file + ') + residual_high {files, claim} for any genuine cross-FILE item.'].join('\n')
const consumerImplPrompt = (c) => [DOC2, '', 'TASK: REBUILD the single Maghz consumer file ' + c.file + ' to the FULL hardened bar, against the ALREADY-LOCKED substrate on disk. ' + (c.note || ''),
  'Consume the locked substrate shapes VERBATIM (BoundaryFault/RuntimeRail/guard/guarded/spawn/Receipt/Signals/Admit/DrainReceipt/QueryResult/...); NEVER redefine a substrate shape or edit a substrate file (record a substrate defect as residual_high {files:[the_substrate_file, ' + c.file + '], claim}).',
  '', COLLAPSE, '',
  (c.folder === 'rails' || c.folder === 'db') ? ('For db/rails .api-stacking hold the bar of ' + RASM_BAR + '/data/.planning/tabular/query.md (guarded . worker-offload . fault-lift in ONE call; a frozendict of the ecosystems OWN callables; request-scoped resource brackets). ') : '',
  c.extra ? (c.extra + '\n') : '',
  'Compose pulumi/pulumi-docker/sqlglot via RAW ephemeral research + the DUAL-BAND import law (gate heavy host-side imports function-locally with # noqa: PLC0415). Every contract is open to redesign; capability PRESERVED AND ENHANCED. Author ONLY ' + c.file + '. Return ONE FIXLOG (file=' + c.file + ') + residual_high {files, claim}.'].join('\n')
const fileCritiquePrompt = (file, pin, extra) => [DOC2, '', 'TASK: DOCTRINAL-CONFORMANCE AUDIT + FIX IN PLACE of the single rebuilt Maghz file ' + file + '. Read ' + file + ' FULLY first, then audit it LINE-BY-LINE — this is a single-file harsh adversarial pass, no folder-blob skimming.',
  pin ? ('EXEMPLAR PIN (the file must match its EXACT deep form): ' + pin) : '',
  extra ? extra : '',
  'If ' + file + ' is a CONSUMER file the substrate is LOCKED — never edit a substrate file; a substrate-spanning issue is residual_high {files:[the_substrate_file, ' + file + '], claim}. If it is a SUBSTRATE file you may refine it but keep every locked shape name/signature stable.',
  critiqueDeep(T),
  'Return ONE FIXLOG (file=' + file + ') + residual_high {files, claim}.'].join('\n')
const fileRedteamPrompt = (file, pin, extra) => [DOC2, '', 'TASK: ADVERSARIAL ARCHITECT RED-TEAM + FIX IN PLACE of the single rebuilt Maghz file ' + file + ' — the LAST and MOST AGGRESSIVE pass over THIS ONE file, burden of proof on the design. Read ' + file + ' FULLY, open BOTH .api tiers + the relevant exemplar page, and attack it from every direction.',
  pin ? ('EXEMPLAR PIN (end at its EXACT deep form or it is not done): ' + pin) : '',
  extra ? extra : '',
  'If ' + file + ' is a CONSUMER file the substrate is LOCKED — never edit a substrate file; a substrate-spanning issue is residual_high {files:[the_substrate_file, ' + file + '], claim}.',
  redteamDeep(T),
  'Repair every defect in ' + file + ' in place. Return ONE FIXLOG (file=' + file + ') + residual_high {files, claim}.'].join('\n')

// --- [OPERATIONS] -- the per-file chain (impl -> critique -> redteam; redteam ALWAYS runs) -
const fileChain = async (file, pin, extra, implPrompt, phaseTag) => {
  const impl = await agent(implPrompt, { label: 'impl:' + shortLabel(file), phase: phaseTag, schema: FIXLOG, effort: 'max', stallMs: 420000 })
  if (!impl) return null
  const crit = await agent(fileCritiquePrompt(file, pin, extra), { label: 'crit:' + shortLabel(file), phase: phaseTag, schema: FIXLOG, effort: 'xhigh', stallMs: 420000 })
  const redteam = await agent(fileRedteamPrompt(file, pin, extra), { label: 'rt:' + shortLabel(file), phase: phaseTag, schema: FIXLOG, effort: 'max', stallMs: 420000 })
  return { file, folder: null, logs: [impl, crit, redteam].filter(Boolean) }
}

// --- [OPERATIONS] -- category (IaC / PG) impl/critique/redteam (cross-file, not per-file) --
const iacImplPrompt = () => [DOC2, '', 'TASK: REALIZE the IaC deepening on the rebuilt Maghz code (author .py + the generated artifacts). Three settled work items:',
  '', PULUMI_DEEPEN, '', EXT_CATALOG, '', MCP_TRIM, '', NO_KEYCHAIN, '',
  'The mcp domain _SERVER_TABLE owns .mcp.json generation; the EXT_CATALOG is the NEW typed owner (place it in admin/infra.py or a new admin/profile.py module within the skeleton) that GENERATES image/Dockerfile apt + db/routines.sql + db/cron.sql CREATE EXTENSION preludes + the shared_preload_libraries string. Edit admin/infra.py (Pulumi), admin/mcp/*, image/Dockerfile, db/*.sql, and regenerate .mcp.json. Hold the dual-band import law (pulumi heavy imports function-local). Return ONE FIXLOG (file=iac) + residual_high {files, claim}.'].join('\n')
const iacCritiquePrompt = () => [DOC2, '', 'TASK: DOCTRINAL-CONFORMANCE AUDIT + FIX IN PLACE of the IaC layer (admin/infra*, admin/mcp*, the EXT_CATALOG owner, image/Dockerfile, db/*.sql, .mcp.json). Assert the EXT_CATALOG is the SINGLE source generating all four downstream surfaces (no 4-place duplication remains), the Pulumi deepening landed (BuildKit cache, ComponentResource, outputs->settings, n8n key fix), .mcp.json is the post-trim 4 servers, and the n8n key path honors the NO-KEYCHAIN law. ' + critiqueDeep(T) + '\nReturn ONE FIXLOG (file=iac) + residual_high {files, claim}.'].join('\n')
const iacRedteamPrompt = () => [DOC2, '', 'TASK: ADVERSARIAL ARCHITECT RED-TEAM + FIX IN PLACE of the IaC layer. Attack: does any extension still live in a 2nd place outside the catalog? does the DSN still drift from DatabaseConfig.dsn? is the n8n key path still /run/secrets or a keychain lookup? is any pulumi/pulumi-docker capability the page reaches re-derived by hand? ' + redteamDeep(T) + '\nReturn ONE FIXLOG (file=iac) + residual_high {files, claim}.'].join('\n')
const pgImplPrompt = () => [DOC2, '', 'TASK: PUSH the PostgreSQL 18.4+ setup to world-class and make it VERIFIABLE (author the catalog rows + db/*.sql + the doctor rail).',
  '', PG_DOCTOR, '', 'The EXT_CATALOG (built in the IaC phase) is the typed owner — ADD the pgvectorscale + pg_squeeze rows, set the pgvector iterative-scan GUCs in maghz.search, regenerate the downstream SQL/Dockerfile/preload from the catalog, and extend the schema doctor verb with the four liveness assertions. Return ONE FIXLOG (file=pg) + residual_high {files, claim}.'].join('\n')
const pgCritiquePrompt = () => [DOC2, '', 'TASK: DOCTRINAL-CONFORMANCE AUDIT + FIX IN PLACE of the PG layer (the EXT_CATALOG rows, db/schema.sql, db/routines.sql, the doctor rail). Assert pgvectorscale + pg_squeeze are catalogued + generated, the GUCs are set in the search CTE, and the four doctor liveness assertions are real typed rails returning evidence. ' + critiqueDeep(T) + '\nReturn ONE FIXLOG (file=pg) + residual_high {files, claim}.'].join('\n')
const pgRedteamPrompt = () => [DOC2, '', 'TASK: ADVERSARIAL ARCHITECT RED-TEAM + FIX IN PLACE of the PG layer. Attack: is the DiskANN index actually offered for scale? do the doctor assertions actually fail on a real drift (census/preload/pipeline/index)? is any SQL hand-edited out of sync with the catalog? ' + redteamDeep(T) + '\nReturn ONE FIXLOG (file=pg) + residual_high {files, claim}.'].join('\n')
const rootsPrompt = () => [DOC2, '', 'TASK: CONSOLIDATE every package barrel + the CLI entry to the FINAL rebuilt internal API surface and topology (edit the .py source on disk). NOT a doctrine rebuild target; a focused seam-correctness consolidation across: ' + ADMIN + '/__init__.py, ' + ADMIN + '/__main__.py, ' + ADMIN + '/runtime/__init__.py, ' + ADMIN + '/rails/__init__.py (the cyclopts CLI mount barrel), ' + ADMIN + '/automation/__init__.py, ' + ADMIN + '/mcp/__init__.py.',
  '(1) fix every re-export to the new internal owners (the FILEMAP flattened core/->core.py, settings/->settings.py, infra/->infra.py, remote/->remote.py; the runtime package modules rails/resilience/lanes/receipts), dropping dead re-exports;',
  '(2) rewire ' + ADMIN + '/rails/__init__.py + ' + ADMIN + '/__main__.py so the cyclopts CLI binds the rebuilt rails/owners + the mcp/schema/extension-doctor verbs and every command resolves — the package must IMPORT cleanly and `python -m admin` must launch.',
  'Verify by reading the rebuilt modules for their actual public names; do not invent symbols. Return ONE FIXLOG (file=roots) + residual_high {files, claim}.'].join('\n')

// --- [OPERATIONS] -- category cycle (impl -> critique -> redteam ALWAYS -> multi-gate) -----
const realizeCategory = async (phaseTag, implP, critP, rtP) => {
  const impl = await agent(implP(), { label: 'impl:' + phaseTag.toLowerCase(), phase: phaseTag, schema: FIXLOG, effort: 'max', stallMs: 420000 })
  if (!impl) return { logs: [], gate: null }
  const crit = await agent(critP(), { label: 'crit:' + phaseTag.toLowerCase(), phase: phaseTag, schema: FIXLOG, effort: 'xhigh', stallMs: 420000 })
  const redteam = await agent(rtP(), { label: 'rt:' + phaseTag.toLowerCase(), phase: phaseTag, schema: FIXLOG, effort: 'max', stallMs: 420000 })
  const gate = await multiGateLoop(phaseTag.toLowerCase(), 'admin', phaseTag)
  return { logs: [impl, crit, redteam].filter(Boolean), gate }
}

// --- [COMPOSITION] -----------------------------------------------------------------------
const runAll = !SCOPE
const SCOPE_SUB = SUBSTRATE_DOMAINS.includes(SCOPE)
const SCOPE_CONS = CONSUMERS.includes(SCOPE)
const runSubstrate = runAll || SCOPE_SUB
const runConsumers = runAll || SCOPE_CONS
const runIaC = runAll || SCOPE === 'iac'
const runPG = runAll || SCOPE === 'pg'
const runRoots = runAll
const subInScope = (s) => !SCOPE_SUB ? true : (SCOPE === 'runtime' ? s.file.startsWith('admin/runtime/') : s.file === 'admin/' + SCOPE + '.py')
const substrateUnits = SUBSTRATE_FILES.filter(subInScope)
const consumerUnits = SCOPE_CONS ? CONSUMER_FILES.filter((c) => c.folder === SCOPE) : CONSUMER_FILES

const allLogs = []
let subGate = null
if (runSubstrate && substrateUnits.length) {
  phase('Substrate')
  const subResults = (await pool(substrateUnits, CAP, (s) => fileChain(s.file, s.pin, '', substrateImplPrompt(s), 'Substrate'))).filter(Boolean)
  for (const r of subResults) for (const l of r.logs) allLogs.push(l)
  subGate = await gateLoop('substrate', SCOPE_SUB ? scopePath(SCOPE) : SUBSTRATE_GATE, 'Substrate')
  log('Substrate: ' + subResults.length + '/' + substrateUnits.length + ' file(s) rebuilt per-file + ' + (subGate && subGate.green ? 'GATE GREEN' : 'gate NOT green'))
  if (COMMIT && subGate && subGate.green) await commitMaghz('substrate')
}

let consumerGateResults = []
if (runConsumers && consumerUnits.length) {
  phase('Consumers')
  const consResults = (await pool(consumerUnits, CAP, (c) => fileChain(c.file, '', c.extra, consumerImplPrompt(c), 'Consumers'))).filter(Boolean)
  for (const r of consResults) for (const l of r.logs) allLogs.push(l)
  const consumerFolders = [...new Set(consumerUnits.map((c) => c.folder))]
  consumerGateResults = (await parallel(consumerFolders.map((f) => () => gateLoop(f, consumerGate(f), 'Consumers').then((g) => ({ folder: f, gate: g }))))).filter(Boolean)
  log('Consumers: ' + consResults.length + '/' + consumerUnits.length + ' file(s) rebuilt per-file; folder gates green ' + consumerGateResults.filter((r) => r.gate && r.gate.green).length + '/' + consumerFolders.length)
}

let iacGate = null
if (runIaC) {
  phase('IaC')
  const r = await realizeCategory('IaC', iacImplPrompt, iacCritiquePrompt, iacRedteamPrompt)
  for (const l of r.logs) allLogs.push(l)
  iacGate = r.gate
  log('IaC: realized + ' + (iacGate && iacGate.green ? 'GREEN' : 'gate NOT green'))
}

let pgGate = null
if (runPG) {
  phase('PG')
  const r = await realizeCategory('PG', pgImplPrompt, pgCritiquePrompt, pgRedteamPrompt)
  for (const l of r.logs) allLogs.push(l)
  pgGate = r.gate
  log('PG: pushed + ' + (pgGate && pgGate.green ? 'GREEN' : 'gate NOT green'))
}

// --- [RECONCILE] -- cluster cross-file residuals -> fix -> verify, then a multi-language re-gate --
const normRes = (x) => typeof x === 'string' ? { files: [], claim: x } : { files: (x.files || []).filter(Boolean), claim: x.claim }
const seedRes = []
for (const lg of allLogs) if (lg && lg.residual_high) for (const x of lg.residual_high) seedRes.push(normRes(x))
let pending = [...new Map(seedRes.filter((r) => r.claim).map((r) => [r.files.slice().sort().join(',') + '|' + r.claim, r])).values()]
const dropped = []
let round = 0
if (pending.length) phase('Reconcile')
while (pending.length && round < MAX_RECONCILE_ROUNDS) {
  round++
  const clusters = clusterByFiles(pending)
  const out = (await pipeline(
    clusters,
    (cl) => agent(reconcileFixPrompt(cl), { label: 'recon-fix:r' + round, phase: 'Reconcile', schema: RECONCILE_FIX, effort: 'max', stallMs: 420000 }),
    (fix, cl) => fix ? agent(reconcileVerifyPrompt(cl, fix), { label: 'recon-verify:r' + round, phase: 'Reconcile', schema: RECONCILE_VERIFY, effort: 'xhigh', stallMs: 420000 }).then((v) => ({ cluster: cl, verify: v })) : null,
  )).filter(Boolean)
  const next = []
  for (const o of out) { const files = [...new Set(o.cluster.flatMap((x) => x.files || []))]; for (const c of ((o.verify && o.verify.claims) || [])) { if (c.status === 'open') next.push({ files, claim: c.claim }); else if (c.status === 'invalid') dropped.push({ files, claim: c.claim, evidence: c.evidence || '' }) } }
  const nextUniq = [...new Map(next.map((r) => [r.files.slice().sort().join(',') + '|' + r.claim, r])).values()]
  const priorClaims = new Set(pending.map((r) => r.claim))
  const stillOpenPrior = new Set(nextUniq.map((r) => r.claim).filter((cl) => priorClaims.has(cl)))
  log('Reconcile round ' + round + ': ' + clusters.length + ' cluster(s) -> ' + nextUniq.length + ' open (' + stillOpenPrior.size + '/' + priorClaims.size + ' prior unresolved)')
  if (stillOpenPrior.size >= priorClaims.size) { pending = nextUniq; break }
  pending = nextUniq
}
const hard_residual = pending
if (round > 0) await multiGateLoop('reconcile', 'admin', 'Reconcile')

let rootsLog = null
if (runRoots) {
  phase('Roots')
  rootsLog = await agent(rootsPrompt(), { label: 'roots:barrels-main', phase: 'Roots', schema: FIXLOG, effort: 'max', stallMs: 420000 })
  if (rootsLog) allLogs.push(rootsLog)
  log('Roots: barrels + __main__ consolidated (' + (rootsLog ? rootsLog.verdict : 'no log') + ')')
}

phase('Gate')
const finalGate = await multiGateLoop('whole-repo', 'admin', 'Gate')
if (COMMIT && finalGate && finalGate.green) await commitMaghz('final')

const collapses = allLogs.filter(Boolean).map((l) => l.collapsed).filter(Boolean)
return {
  scope: SCOPE || 'ALL',
  substrate_green: !!(subGate && subGate.green),
  consumers_green: Object.fromEntries(consumerGateResults.map((r) => [r.folder, !!(r.gate && r.gate.green)])),
  iac_green: !!(iacGate && iacGate.green),
  pg_green: !!(pgGate && pgGate.green),
  whole_repo_green: !!(finalGate && finalGate.green),
  collapses,
  hard_residual: hard_residual.map((r) => r.claim),
  dropped: dropped.map((r) => r.claim),
  final_gate_remaining: (finalGate && finalGate.remaining) || [],
  handoff: 'BOUNDARY: live behavioral proof (secrets into Forge, redeploy, bring up Postgres/Pulumi/n8n local + remote, exercise every CLI command + the doctor liveness assertions) is the live-proof runbook, OUT OF SCOPE for this workflow — it ends at a green multi-language gate.',
}
