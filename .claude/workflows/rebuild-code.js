export const meta = {
  name: 'rebuild-code',
  description: 'Total greenfield ground-up rebuild of ALL Python source under the Maghz admin/ package to the Rasm Python bar: substrate-first (core+runtime+settings+db locked once), then per-folder implement-critique-redteam with a ruff+ty gate fix-loop, then cross-file reconcile, then a single init/main consolidation pass, then a whole-admin gate. Aggressive polymorphic collapse (30-50pct LOC cut) with capability preserved and enhanced; free to restructure files within the domain skeleton. Runs from Rasm, reads the Rasm bar by absolute path, edits Maghz by absolute path, directly on main.',
  whenToUse: 'Rebuilding the Maghz admin operator codebase to world-class py3.15 against the Rasm planning corpus and .api catalogs',
  phases: [
    { title: 'Scout', detail: 'single mapper over the whole admin package: import graph, current topology, canonical cross-cutting shapes, domain-intent inferred from code behavior, Maghz-domain to Rasm .planning/.api mapping', model: 'sonnet' },
    { title: 'Topology-Plan', detail: 'planner + 2-agent adversarial panel + reconciler: the ONE target file layout, the LOCKED canonical-shapes contract, the dependency tiers' },
    { title: 'Substrate', detail: 'rebuild core+runtime+settings+db, LOCK canonical shapes; implement-critique-redteam then ruff+ty gate fix-loop' },
    { title: 'Consumers', detail: 'per consumer folder against the locked substrate: implement-critique-redteam (fix-in-place, log cross-file residuals) then per-folder ruff+ty gate fix-loop' },
    { title: 'Reconcile', detail: 'bounded loop: cross-file residuals union-find clustered, fix(max) then adversarial verify(xhigh), then a gate re-run over touched dirs' },
    { title: 'Roots', detail: 'single consolidation agent: rewrite ALL __init__.py + __main__.py to the final API surface + CLI wiring so the package imports and python -m admin launches' },
    { title: 'Gate', detail: 'final whole-admin ruff+ty gate fix-loop to green; return the summary and the live-proof handoff boundary' },
  ],
}

// --- [TYPES] -- structured-output schemas ------------------------------------------------
const SCOUTMAP = { type: 'object', additionalProperties: false, required: ['domain', 'files', 'intent'], properties: { domain: { type: 'string' }, tier: { type: 'string', enum: ['substrate', 'consumer', 'root'] }, files: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['path', 'loc', 'role'], properties: { path: { type: 'string' }, loc: { type: 'number' }, role: { type: 'string' }, imports_admin: { type: 'array', items: { type: 'string' } }, imports_pkg: { type: 'array', items: { type: 'string' } }, owners: { type: 'array', items: { type: 'string' } } } } }, intent: { type: 'string' }, cross_cutting: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['shape', 'file'], properties: { shape: { type: 'string' }, file: { type: 'string' }, used_by: { type: 'array', items: { type: 'string' } } } } }, collapse_targets: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['claim', 'files'], properties: { claim: { type: 'string' }, files: { type: 'array', items: { type: 'string' } } } } }, bar_map: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['ref'], properties: { ref: { type: 'string' }, why: { type: 'string' } } } }, uncatalogued_pkgs: { type: 'array', items: { type: 'string' } } } }
const SCOUTBOOK = { type: 'object', additionalProperties: false, required: ['domains'], properties: { domains: { type: 'array', items: SCOUTMAP } } }
const TOPOLOGY_PLAN = { type: 'object', additionalProperties: false, required: ['layout', 'shapes', 'tiers'], properties: { layout: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['path', 'owns'], properties: { path: { type: 'string' }, owns: { type: 'string' }, from: { type: 'array', items: { type: 'string' } } } } }, shapes: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['name', 'file', 'signature', 'kind'], properties: { name: { type: 'string' }, file: { type: 'string' }, signature: { type: 'string' }, kind: { type: 'string' } } } }, tiers: { type: 'object', additionalProperties: false, required: ['substrate', 'consumers'], properties: { substrate: { type: 'array', items: { type: 'string' } }, consumers: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['folder', 'files'], properties: { folder: { type: 'string' }, files: { type: 'array', items: { type: 'string' } } } } } } }, restructure_notes: { type: 'string' } } }
const PANEL = { type: 'object', additionalProperties: false, required: ['verdict', 'attacks'], properties: { verdict: { type: 'string' }, attacks: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['target', 'fix'], properties: { target: { type: 'string' }, fix: { type: 'string' } } } } } }
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
const DOMAINS = ['core', 'runtime', 'settings', 'db', 'automation', 'mcp', 'rails', 'infra', 'remote', 'root']
const SUBSTRATE_DOMAINS = ['core', 'runtime', 'settings', 'db']
const CONSUMERS = ['automation', 'mcp', 'rails', 'infra', 'remote']
const SUBSTRATE_GATE = 'admin/core admin/runtime admin/settings admin/db.py'
const domainPath = (d) => d === 'db' ? ADMIN + '/db.py' : d === 'root' ? (ADMIN + '/__init__.py ' + ADMIN + '/__main__.py') : ADMIN + '/' + d
const scopePath = (s) => s === 'db' ? 'admin/db.py' : s === 'root' ? 'admin/__init__.py admin/__main__.py' : 'admin/' + s

// --- [INPUT] -- args = optional single-domain scope (narrow run) | empty/ALL = whole tree --
const SCOPE = (typeof args === 'string' && args.trim() && args.trim().toUpperCase() !== 'ALL') ? args.trim() : (args && typeof args === 'object' && args.scope ? String(args.scope).trim() : '')
const COMMIT = !!(args && typeof args === 'object' && args.commit === true)

// --- [HARNESS] -- steady bounded worker pool (<=cap concurrent, staggered start) ----------
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

// --- [MODELS] -- the doctrine preamble: lifted from implement.js LANG.python with the four --
// --- [MODELS] -- code-adaptation edits (executable .py, greenfield-over-strong, raw research) -
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
const COLLAPSEVOCAB = 'a closed `@tagged_union`/discriminated-Pydantic family, a `frozendict` dispatch-or-policy table (primary correspondence + derived maps), a fold/comprehension algebra, a signature+rail-preserving aspect factory, and value objects with behavior'
const DOC = [LAW, '', ULTRA, '', PATLAW, '', BOUNDARIES, '', CODESTRUCT, '', COMMENTS].join('\n')

// --- the rebuild-python critique/redteam SPEC, parameterized on the python idiom tokens ----
const T = {
  getFamily: '`get`/`get_many`/`get_by_id`', table: 'a `frozendict` table or fold algebra', collapse: 'one closed `@tagged_union`/discriminated-Pydantic family', constTable: 'one `frozendict`/`StrEnum`', aspectFactory: 'one parameterized aspect factory',
  owners: '`TypedDict`/Pydantic/`msgspec.Struct`/frozen dataclass/rich class/`StrEnum`/`Literal`/`sentinel`/`Option`/`Result`/`frozendict`/`Map`/`tuple`/`Protocol`', nullFail: '`None`-as-failure', receipt: '',
  flags: '`strict: bool`/`mode`/`batch` flag', knobScope: 'an aspect or `anyio` scope', aspectForm: 'a SIGNATURE- and RAIL-PRESERVING stacked decorator (inline `**P` + `functools.wraps`)', unit: 'functions',
  rails: 'the narrowest carrier that states the outcome — `Option[T]` non-failing absence, `Result[T, E]` typed fallibility, `effect.result` do-notation, an `anyio` task group as the failure boundary (NEVER `asyncio.gather`), `stamina.retry` as the decorator (never a sleep-loop)', faultVocab: '`Literal` set / `StrEnum` / `@tagged_union` family', looseFault: 'a bare `str` fault', accumulate: '`map2`/accumulating-fold for independents, `bind` short-circuit for dependents', dispatch: '`match`', foldForm: 'fold/comprehension',
  check6: 'PAYLOADS/FROZENDICT/PEP — payloads are `closed=`/`extra_items=` `TypedDict` via a module-level `TypeAdapter` with `Unpack[TypedDict]` at root entrypoints; `frozendict` (builtin) owns tables/evidence (no `MappingProxyType`/dict-table/tuple-pairs); PEP 585/604/695 only, no `from __future__ import annotations`, no legacy typing; total `match` + `assert_never`.',
  doctrine: 'the Rasm libs/python/.planning/ exemplar pages and the .api catalogs', compileWord: 'type-check', boundaryExtra: '', memberVerify: 'verify the member exists in the `.api` catalog or by reading the installed package', coldDims: 'payload/`frozendict`/PEP conformance, both-tier `.api` maximization, py3.15-modern typing',
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

// --- [OPERATIONS] -- prompt builders -----------------------------------------------------
const scoutPrompt = (d) => [LAW, '', 'TASK: MAP the Maghz admin domain `' + d + '` READ-ONLY (edit NOTHING). The files are under ' + domainPath(d) + ' (enumerate every .py there with find). For this domain:',
  '(1) Read every .py file. Build its slice of the IMPORT GRAPH: per file, intra-admin module deps (imports_admin), the third-party packages it composes (imports_pkg), and the canonical owners/types it declares (owners).',
  '(2) Classify the tier: substrate (core/runtime/settings/db), consumer (automation/mcp/rails/infra/remote), or root (__main__/__init__).',
  '(3) Infer the DOMAIN INTENT from the code BEHAVIOR and module docstrings ONLY — Maghz docs/design/ is IGNORED, never read it.',
  '(4) CROSS_CUTTING: every substrate shape (Envelope/Detail/Status/BoundaryFault/RuntimeRail/RetryClass/Admit/DrainReceipt/Receipt/MaghzSettings/QueryResult and successors) this domain DEFINES or CONSUMES, and which files use it.',
  '(5) COLLAPSE_TARGETS: candidate polymorphic-collapse sites that SPAN files (3 sibling fault families across rails one BoundaryFault subsumes; parallel verb tables; repeated aspect stacks) — each a {claim, files} pair.',
  '(6) BAR_MAP: the Rasm bar refs that govern this domain — the relevant ' + RASM_BAR + '/<folder>/.planning/*.md exemplar page(s) and .api catalog(s) (shared + runtime folder) — each {ref (absolute path), why}.',
  '(7) UNCATALOGUED_PKGS: any package this domain uses with NO Rasm .api catalog (expected: pulumi, pulumi-docker, pulumi-docker-build, pg8000, sqlglot).',
  'Return the SCOUTMAP.'].join('\n')
const scoutAllPrompt = () => [LAW, '', 'TASK: MAP THE ENTIRE Maghz admin package READ-ONLY (edit NOTHING). Enumerate every .py under ' + ADMIN + ' (find ' + ADMIN + ' -name "*.py"). Produce ONE entry per domain (' + DOMAINS.join(', ') + '): db is ' + ADMIN + '/db.py, root is __init__.py + __main__.py, the rest are the same-named folders. For EACH domain do (1)-(7):',
  '(1) import graph slice per file (imports_admin = intra-admin module deps, imports_pkg = third-party packages, owners = canonical types it declares).',
  '(2) tier: substrate (core/runtime/settings/db) | consumer (automation/mcp/rails/infra/remote) | root (__main__/__init__).',
  '(3) intent inferred from the code BEHAVIOR + module docstrings ONLY — Maghz docs/design/ is IGNORED, never read it.',
  '(4) cross_cutting: every substrate shape (Envelope/Detail/Status/BoundaryFault/RuntimeRail/RetryClass/Admit/DrainReceipt/Receipt/MaghzSettings/QueryResult and successors) the domain DEFINES or CONSUMES + which files use it.',
  '(5) collapse_targets: candidate polymorphic-collapse sites that SPAN files (sibling fault families one BoundaryFault subsumes; parallel verb tables; repeated aspect stacks) — each {claim, files}.',
  '(6) bar_map: the governing Rasm bar refs — the relevant ' + RASM_BAR + '/<folder>/.planning/*.md exemplar page(s) and .api catalog(s) (shared + runtime folder) — each {ref (absolute path), why}.',
  '(7) uncatalogued_pkgs: any package with NO Rasm .api catalog (expected: pulumi, pulumi-docker, pulumi-docker-build, pg8000, sqlglot).',
  'Return SCOUTBOOK {domains:[...]} with one SCOUTMAP entry per domain.'].join('\n')
const topologyPlanPrompt = (corpus) => [DOC, '', 'TASK: DECIDE THE ONE TARGET FILE LAYOUT, THE LOCKED CANONICAL-SHAPES CONTRACT, AND THE DEPENDENCY TIERS for the greenfield rebuild of Maghz admin/ (READ-ONLY — produce the plan, edit NOTHING). You see the full per-domain SCOUTMAP corpus below. This codebase is already strong; your plan must drive a 30-50pct LOC reduction via polymorphic collapse while PRESERVING AND ENHANCING capability.',
  'SKELETON CONSTRAINT: keep the top-level domain folders fixed (core, runtime, settings, db.py, automation, mcp, rails, infra, remote, plus the __init__.py/__main__.py roots) so the substrate-first tiering and the gate scoping hold. You are FREE to restructure FILES within and BETWEEN these domain folders (collapse two thin modules into one denser owner, move a file to a better domain, fold a re-export into its owner), but do NOT rename or invent top-level folders.',
  'Order is SUBSTRATE-FIRST: the substrate (core + runtime + settings + db) and its canonical shapes are locked FIRST; consumers (automation/mcp/rails/infra/remote) and the roots are rebuilt against the locked substrate.',
  'Produce TOPOLOGY_PLAN: layout[] (the FINAL target file set; each {path (absolute), owns, from[] — the current file(s) whose capability folds in; name every many->one collapse; never drop a capability — every from file behavior must land somewhere); shapes[] (the LOCKED canonical-shapes contract — every cross-cutting substrate type a consumer binds against; each {name (FINAL, may be renamed), file (absolute substrate path), signature (the exact py3.15 declaration consumers import), kind}; FROZEN once the substrate phase realizes them; choose each by the OWNER_CHOOSER discriminants — this contract is the single anti-collision mechanism for the parallel consumer phase, so it must be complete and decision-complete); tiers ({substrate: [ordered leaf-first file list], consumers: [{folder, files[]}]}); restructure_notes (the rationale for every file move).',
  'Decision-complete: a downstream agent realizes each file with zero further layout or shape decisions. SCOUTMAP CORPUS:\n' + JSON.stringify(corpus, null, 1)].join('\n')
const panelLayoutPrompt = (draft) => [DOC, '', 'TASK: ADVERSARIALLY ATTACK THE LAYOUT of this draft TOPOLOGY_PLAN (READ-ONLY — produce attacks, edit NOTHING). Is this the densest restructure the doctrine admits? Does any target file mix concerns? Does any many->one collapse silently DROP a capability (check every from[] is accounted for)? Does the skeleton constraint hold? For each defect return {target (the layout entry), fix (the concrete reshape)}. DRAFT:\n' + JSON.stringify(draft, null, 1)].join('\n')
const panelShapesPrompt = (draft) => [DOC, '', 'TASK: ADVERSARIALLY ATTACK THE LOCKED-SHAPES CONTRACT of this draft TOPOLOGY_PLAN (READ-ONLY — produce attacks, edit NOTHING). Is each locked shape the OWNER_CHOOSER-correct owner? Does the next-feature DIFF land as ONE declaration (ANTICIPATORY_COLLAPSE)? Is any consumer forced to redefine a shape because the contract is incomplete? Is any signature wrong against the .api capability? For each defect return {target (the shape name), fix (the corrected owner/signature)}. DRAFT:\n' + JSON.stringify(draft, null, 1)].join('\n')
const topologyReconcilePrompt = (draft, attacks) => [DOC, '', 'TASK: EMIT THE FINAL TOPOLOGY_PLAN (READ-ONLY — produce the plan, edit NOTHING). Fold every valid attack from the layout + shapes panels into the draft; reject an attack only if you can show it is wrong. The result is the FROZEN contract the substrate + consumer phases realize verbatim. DRAFT:\n' + JSON.stringify(draft, null, 1) + '\nPANEL ATTACKS:\n' + JSON.stringify(attacks, null, 1)].join('\n')
const substrateRealizePrompt = (shapesJson) => [DOC, '', 'TASK: REBUILD THE MAGHZ SUBSTRATE — the files under ' + ADMIN + '/core, ' + ADMIN + '/runtime, ' + ADMIN + '/settings, and ' + ADMIN + '/db.py, in leaf-first order — to the locked canonical-shapes contract, at the FULL Rasm Python bar. You author the ACTUAL .py source on disk.',
  'You MUST realize EVERY shape in the LOCKED CONTRACT below with the EXACT name, file, and signature given — this is the frozen interface every consumer folder imports. Do not rename, move, or re-sign a locked shape; if the plan signature is genuinely wrong, fix the source AND note it in residual_high so the lock stays coherent, but never silently diverge.',
  'Construct in LIFECYCLE order. Collapse aggressively across the substrate (one BoundaryFault family subsuming sibling faults; one frozendict policy/dispatch table per concept with derived secondary maps; one parameterized aspect factory per recurring wrapper stack; one polymorphic drain over the Admit family). Compose the admitted packages to depth (expression rails, msgspec frozen structs, frozendict tables, anyio NEVER asyncio.gather, stamina retry decorator, structlog + Receipt/Signals spine, beartype at the boundary). For pg8000 do RAW research of the installed driver surface in the Maghz env — no catalog. py3.15-modern only. Capability is PRESERVED AND ENHANCED — every current substrate behavior survives, denser.',
  'Fix-in-place; report what you collapsed (count before->after in `collapsed`). Return ONE FIXLOG (set file=substrate) + residual_high {files, claim} for any genuine cross-file item.',
  'LOCKED CANONICAL-SHAPES CONTRACT:\n' + shapesJson].join('\n')
const substrateCritiquePrompt = (shapesJson) => [DOC, '', 'TASK: DOCTRINAL-CONFORMANCE AUDIT + FIX IN PLACE of the rebuilt Maghz substrate source files (core/runtime/settings/db.py). The locked shapes contract is frozen — verify every shape matches its locked signature and is the discriminant-correct owner; do NOT change a locked name/signature. ' + critiqueTemplate(T) + '\nAlso enforce both-tier .api maximization (cite only real members), capability preservation+enhancement, and code + comment hygiene. EDIT the .py files to fix every hit. Return ONE FIXLOG (set file=substrate) + residual_high {files, claim}.\nLOCKED CANONICAL-SHAPES CONTRACT:\n' + shapesJson].join('\n')
const substrateRedteamPrompt = (shapesJson) => [DOC, '', 'TASK: ADVERSARIAL ARCHITECT RED-TEAM + FIX IN PLACE of the rebuilt Maghz substrate source files (core/runtime/settings/db.py). The locked shapes contract is frozen — do NOT change a locked name/signature; a substrate-shape defect you cannot fix without breaking the lock is a residual. ' + redteamTemplate(T) + '\nHold the highest bar; repair every defect in place. Return ONE FIXLOG (set file=substrate) + residual_high {files, claim}.\nLOCKED CANONICAL-SHAPES CONTRACT:\n' + shapesJson].join('\n')
const consumerRealizePrompt = (folder, shapesJson) => [DOC, '', 'TASK: REBUILD the Maghz consumer folder `' + folder + '` (every .py under ' + ADMIN + '/' + folder + ') to the FULL Rasm Python bar, against the ALREADY-LOCKED substrate on disk. You author the ACTUAL .py source.',
  'The substrate is LOCKED and GREEN: import and consume the locked canonical shapes below VERBATIM (their exact names/signatures, already realized in their substrate files). NEVER redefine a substrate shape, NEVER declare a parallel fault family/rail/table a substrate shape already owns, and NEVER edit a substrate file — if you believe a substrate shape is wrong, do NOT touch it; record it as a residual_high {files:[the substrate file + this file], claim} and the reconcile phase owns it.',
  'This folder code is already dense; COLLAPSE harder (fold sibling verbs into one polymorphic entrypoint discriminating on a closed op vocabulary + one frozendict verb table; one match/assert_never per closed family; stack cross-cutting concerns as the substrate aspects, never inline), ENHANCE capability (richer owners, more features per the bar — never fewer), and follow the locked target LAYOUT for where each owner lives. Compose the admitted packages to depth (the runtime substrate rails ON TOP OF the domain packages: cyclopts/httpx/asyncssh/keyring/watchfiles/apscheduler from the Rasm runtime .api; pulumi/pulumi-docker/pulumi-docker-build/sqlglot via RAW ephemeral research of the installed package in the Maghz env + docs — author NO catalog). Every contract (CLI surface, .mcp.json shape, DB schema, wire JSON) is open to total redesign, but every current capability SURVIVES and is enhanced. py3.15-modern only.',
  'NOTE for infra: if you rebuild stack.py, FIX the n8n encryption-key gap — the stack must actually provide N8N_ENCRYPTION_KEY to the n8n container (mount a real key file or let n8n self-generate a stable key), not reference a /run/secrets path that does not exist on Colima/macOS.',
  'Fix-in-place; FIX every cross-file issue you can from these owned files; defer ONLY a genuine item spanning a file OUTSIDE this folder as residual_high {files, claim}. Report collapses (count before->after). Return ONE FIXLOG (set file=`' + folder + '`) + residual_high.',
  'LOCKED CANONICAL-SHAPES CONTRACT (consume verbatim, never redefine, never edit the substrate):\n' + shapesJson].join('\n')
const consumerCritiquePrompt = (folder, shapesJson) => [DOC, '', 'TASK: DOCTRINAL-CONFORMANCE AUDIT + FIX IN PLACE of the rebuilt Maghz consumer folder `' + folder + '` (' + ADMIN + '/' + folder + '). The substrate is LOCKED — never edit a substrate file; a substrate-spanning issue is a residual. ' + critiqueTemplate(T) + '\nAlso enforce both-tier .api maximization and code + comment hygiene; consume the locked shapes verbatim. EDIT the folder .py files to fix every hit. Return ONE FIXLOG (set file=`' + folder + '`) + residual_high {files, claim}.\nLOCKED CANONICAL-SHAPES CONTRACT:\n' + shapesJson].join('\n')
const consumerRedteamPrompt = (folder, shapesJson) => [DOC, '', 'TASK: ADVERSARIAL ARCHITECT RED-TEAM + FIX IN PLACE of the rebuilt Maghz consumer folder `' + folder + '` (' + ADMIN + '/' + folder + '). The substrate is LOCKED — never edit a substrate file; a substrate-spanning issue is a residual. ' + redteamTemplate(T) + '\nHold the highest bar; repair every defect in place; consume the locked shapes verbatim. Return ONE FIXLOG (set file=`' + folder + '`) + residual_high {files, claim}.\nLOCKED CANONICAL-SHAPES CONTRACT:\n' + shapesJson].join('\n')
const reconcileFixPrompt = (cl) => [DOC, '', 'TASK: RECONCILE these cross-FILE residuals deferred by the realize + review passes (edit the .py source on disk). NO severity — treat EVERY residual as must-address. Read EVERY listed file. For each: if it is a real cross-file defect, FIX it in place (unify the shared type/seam/rail, repair the boundary issue), preserving all capability and regressing no file; if a residual is FACTUALLY INCORRECT or not a real defect, leave it and say why in the summary — never silently skip a real one. A locked substrate file may be edited HERE only when a residual names the substrate as the defect site. Residuals:\n' + JSON.stringify(cl, null, 1)].join('\n')
const reconcileVerifyPrompt = (cl, fix) => [DOC, '', 'TASK: ADVERSARIAL VERIFY, one verdict per claim. Read the named .py files from disk and classify each residual: "fixed" (real defect, now genuinely resolved), "invalid" (the claim is factually wrong / not a real defect — cite why), or "open" (real defect still NOT resolved). Default to "open" on any doubt for a real-looking defect; mark "invalid" ONLY when you can show the claim is wrong. Claims:\n' + JSON.stringify(cl, null, 1) + '\nFiles the fixer touched: ' + JSON.stringify((fix && fix.files) || [])].join('\n')
const rootsPrompt = () => [DOC, '', 'TASK: CONSOLIDATE the package roots — ' + ADMIN + '/__init__.py and ' + ADMIN + '/__main__.py — to the FINAL rebuilt internal API surface and topology (edit the .py source on disk). These are NOT a doctrine rebuild target; this is a focused consolidation: (1) fix every re-export in __init__.py to the new internal owners (names/paths the rebuild settled), dropping dead re-exports and exposing the real public surface; (2) rewire __main__.py so the cyclopts CLI binds the rebuilt rails/owners and every command resolves — the package must IMPORT cleanly and `python -m admin` must launch. Verify by reading the rebuilt modules for their actual public names; do not invent symbols. You MAY modernize these two files in passing (py3.15 typing, dead-code removal) but the job is correctness of the seam, not a from-scratch redesign. Return ONE FIXLOG (set file=roots) + residual_high {files, claim} for any genuine cross-file mismatch you cannot resolve here.'].join('\n')
const gateFixPrompt = (paths) => [DOC, '', 'TASK: RUN THE MAGHZ GATE on the rebuilt files and FIX every diagnostic IN PLACE until green — loop ENTIRELY WITHIN THIS ONE TASK (run, fix, re-run, repeat; never stop at the first pass). Run it yourself, exactly this (the bash -lc cd form avoids a cd permission prompt):',
  '  bash -lc "cd ' + MAGHZ + ' && uv run ruff check ' + paths + ' && uv run ty check ' + paths + '"',
  'ty is the BINDING gate ([tool.ty.rules] all=error, error-on-warning=true; respect-type-ignore-comments=false so a `# type: ignore` does NOTHING); ruff must also be clean. mypy/basedpyright are ADVISORY — note them in `advisory`, do not loop on them. Read each diagnostic, fix the SOURCE: never add a type-ignore, never weaken a type to silence ty, never edit pyproject to relax a rule, never delete capability to pass. Re-run the gate after EACH fix and KEEP GOING until both ruff and ty are clean, or you can prove a diagnostic is a real cross-file residual outside these paths. Return GATE_RESULT with green, ruff_clean, ty_clean, the number of internal fix passes in `rounds`, and any `remaining` diagnostics if not green.',
  'PATHS: ' + paths].join('\n')

// --- [OPERATIONS] -- the gate fix-loop + reconcile clustering ----------------------------
const gateLoop = async (label, paths, phaseTag) => agent(gateFixPrompt(paths), { label: 'gate:' + label, phase: phaseTag, schema: GATE_RESULT, effort: 'high', stallMs: 600000 })
const clusterByFiles = (items) => {
  const parent = new Map(); const find = (f) => { let p = f; while (parent.get(p) !== p) p = parent.get(p); return p }; const add = (f) => { if (!parent.has(f)) parent.set(f, f) }
  for (const it of items) { (it.files || []).forEach(add); for (let i = 1; i < (it.files || []).length; i++) parent.set(find(it.files[i]), find(it.files[0])) }
  const by = new Map()
  for (const it of items) { const root = (it.files && it.files.length) ? find(it.files[0]) : '__none__'; (by.get(root) || by.set(root, []).get(root)).push(it) }
  return [...by.values()]
}
const realizeConsumerFolder = async (folder, shapesJson) => {
  const impl = await agent(consumerRealizePrompt(folder, shapesJson), { label: 'impl:' + folder, phase: 'Consumers', schema: FIXLOG, effort: 'max', stallMs: 420000 })
  if (!impl) return null
  const crit = await agent(consumerCritiquePrompt(folder, shapesJson), { label: 'crit:' + folder, phase: 'Consumers', schema: FIXLOG, effort: 'xhigh', stallMs: 420000 })
  const redteam = crit ? await agent(consumerRedteamPrompt(folder, shapesJson), { label: 'rt:' + folder, phase: 'Consumers', schema: FIXLOG, effort: 'max', stallMs: 420000 }) : null
  const gate = await gateLoop(folder, 'admin/' + folder, 'Consumers')
  return { folder, logs: [impl, crit, redteam].filter(Boolean), gate }
}
const commitMaghz = (tag) => agent('TASK: run exactly `bash -lc "cd ' + MAGHZ + ' && git add -A && git commit -m \'rebuild-code: ' + tag + ' green\'"` and report the commit short-hash. If there is nothing to commit, say so. Make no other change.', { label: 'commit:' + tag, phase: 'Gate', model: 'haiku', effort: 'low', stallMs: 120000 })

// --- [COMPOSITION] -----------------------------------------------------------------------
phase('Scout')
let corpus = []
if (SCOPE) {
  const one = await agent(scoutPrompt(SCOPE), { label: 'scout:' + SCOPE, phase: 'Scout', schema: SCOUTMAP, model: 'sonnet', effort: 'low', stallMs: 300000 })
  if (one) corpus = [one]
} else {
  const book = await agent(scoutAllPrompt(), { label: 'scout:all', phase: 'Scout', schema: SCOUTBOOK, model: 'sonnet', effort: 'medium', stallMs: 480000 })
  corpus = (book && book.domains) || []
}
log('Scout: ' + corpus.length + ' domain map(s) under ' + ADMIN)

let plan = null
let SHAPES_JSON = '(narrow run: read the locked canonical shapes from the substrate files already on disk under ' + ADMIN + ')'
if (!SCOPE) {
  phase('Topology-Plan')
  const draft = await agent(topologyPlanPrompt(corpus), { label: 'topology:draft', phase: 'Topology-Plan', schema: TOPOLOGY_PLAN, effort: 'max', stallMs: 420000 })
  const attacks = draft ? (await parallel([
    () => agent(panelLayoutPrompt(draft), { label: 'topology:attack-layout', phase: 'Topology-Plan', schema: PANEL, effort: 'xhigh', stallMs: 360000 }),
    () => agent(panelShapesPrompt(draft), { label: 'topology:attack-shapes', phase: 'Topology-Plan', schema: PANEL, effort: 'xhigh', stallMs: 360000 }),
  ])).filter(Boolean) : []
  plan = (draft ? await agent(topologyReconcilePrompt(draft, attacks), { label: 'topology:final', phase: 'Topology-Plan', schema: TOPOLOGY_PLAN, effort: 'max', stallMs: 420000 }) : null) || draft
  if (plan && plan.shapes && plan.shapes.length) SHAPES_JSON = JSON.stringify(plan.shapes, null, 1)
  log('Topology-Plan: ' + (plan && plan.shapes ? plan.shapes.length : 0) + ' locked shape(s); ' + (plan && plan.layout ? plan.layout.length : 0) + ' target file(s)')
}

const runSubstrate = !SCOPE || SUBSTRATE_DOMAINS.includes(SCOPE)
const substrateLogs = []
let subGate = null
if (runSubstrate) {
  phase('Substrate')
  const subImpl = await agent(substrateRealizePrompt(SHAPES_JSON), { label: 'impl:substrate', phase: 'Substrate', schema: FIXLOG, effort: 'max', stallMs: 420000 })
  const subCrit = subImpl ? await agent(substrateCritiquePrompt(SHAPES_JSON), { label: 'crit:substrate', phase: 'Substrate', schema: FIXLOG, effort: 'xhigh', stallMs: 420000 }) : null
  const subRt = subCrit ? await agent(substrateRedteamPrompt(SHAPES_JSON), { label: 'rt:substrate', phase: 'Substrate', schema: FIXLOG, effort: 'max', stallMs: 420000 }) : null
  for (const l of [subImpl, subCrit, subRt]) if (l) substrateLogs.push(l)
  subGate = await gateLoop('substrate', SCOPE ? scopePath(SCOPE) : SUBSTRATE_GATE, 'Substrate')
  log('Substrate: rebuilt + ' + (subGate && subGate.green ? 'GREEN' : 'gate NOT green'))
  if (COMMIT && subGate && subGate.green) await commitMaghz('substrate')
}

const consumersToRun = SCOPE ? CONSUMERS.filter((c) => c === SCOPE) : CONSUMERS
let consumerResults = []
if (consumersToRun.length) {
  phase('Consumers')
  consumerResults = (await pool(consumersToRun, CAP, (f) => realizeConsumerFolder(f, SHAPES_JSON))).filter(Boolean)
  log('Consumers: ' + consumerResults.length + '/' + consumersToRun.length + ' folder(s) rebuilt; green ' + consumerResults.filter((r) => r.gate && r.gate.green).length)
}

// --- [RECONCILE] -- cluster cross-file residuals -> fix -> verify, then re-gate touched dirs --
const normRes = (x) => typeof x === 'string' ? { files: [], claim: x } : { files: (x.files || []).filter(Boolean), claim: x.claim }
const seedRes = []
for (const lg of substrateLogs) if (lg && lg.residual_high) for (const x of lg.residual_high) seedRes.push(normRes(x))
for (const r of consumerResults) for (const lg of r.logs) if (lg && lg.residual_high) for (const x of lg.residual_high) seedRes.push(normRes(x))
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
if (round > 0) await gateLoop('reconcile', SCOPE ? scopePath(SCOPE) : 'admin', 'Reconcile')

let rootsLog = null
if (!SCOPE) {
  phase('Roots')
  rootsLog = await agent(rootsPrompt(), { label: 'roots:init-main', phase: 'Roots', schema: FIXLOG, effort: 'max', stallMs: 420000 })
  log('Roots: __init__/__main__ consolidated (' + (rootsLog ? rootsLog.verdict : 'no log') + ')')
}

phase('Gate')
const finalGate = await gateLoop('whole-admin', SCOPE ? scopePath(SCOPE) : 'admin', 'Gate')
if (COMMIT && finalGate && finalGate.green) await commitMaghz('final')

const collapses = [...substrateLogs, ...consumerResults.flatMap((r) => r.logs), rootsLog].filter(Boolean).map((l) => l.collapsed).filter(Boolean)
return {
  scope: SCOPE || 'ALL',
  locked_shapes: plan && plan.shapes ? plan.shapes.length : 0,
  substrate_green: !!(subGate && subGate.green),
  consumers_green: Object.fromEntries(consumerResults.map((r) => [r.folder, !!(r.gate && r.gate.green)])),
  whole_admin_green: !!(finalGate && finalGate.green),
  collapses,
  hard_residual: hard_residual.map((r) => r.claim),
  dropped: dropped.map((r) => r.claim),
  final_gate_remaining: (finalGate && finalGate.remaining) || [],
  handoff: 'BOUNDARY: live behavioral proof (wiring secrets into Forge, redeploying, bringing up Postgres/Pulumi/n8n local + remote, exercising every CLI command) is the live-proof runbook, OUT OF SCOPE for this workflow — it ends at a green ruff+ty gate. Hand the rebuilt admin/ to the live-proof pass next.',
}
