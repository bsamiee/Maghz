# [SURFACES_AND_DISPATCH]

A concern with many features keeps one dense surface, never a family of shallow ones: one entrypoint absorbs every verb, arity, and modality — verbs collapse into a request `Data.TaggedEnum` under one `$match` so a new verb breaks every site instead of growing a sibling, arity collapses into a non-empty tuple, `Effect.forEach`, and one carrier, and the discriminant is the value's shape, never a mode flag beside it. Knob sets collapse into `as const satisfies Record` vocabularies whose rows carry their own behavior, and optional context enters as `Option<T>` or one runtime record whose default derives from the vocabulary owner. Match terminals are selected by what unmatched input means — `exhaustive` when it is a compile error, `option` when it is absence, `either` when it is observable evidence — while the carrier stays orthogonal to the form and alone decides accumulate-versus-abort, one Effect pipeline dispatching success, typed failure, and context at once. Aspects split at one seam: decode and brand below the admission boundary on the single Schema, retry and lifetime above it as effect transformers.

## [01]-[FORM_CHOOSER]

When a concern matches several rows, the most specific wins; the carrier axis is read after the form is fixed.

| [INDEX] | [CONCERN_SIGNATURE]                          | [FORM]                                        | [REJECTED_FORM]                      |
| :-----: | :------------------------------------------- | :-------------------------------------------- | :----------------------------------- |
|  [01]   | verb family, shared preamble                 | request `Data.TaggedEnum` + `$match`          | sibling `create`/`update` methods    |
|  [02]   | one verb, varying arity                      | `[T, ...ReadonlyArray<T>]` + `Effect.forEach` | per-arity overload family            |
|  [03]   | closed tagged domain projection              | `Match.tagsExhaustive` / `$match`             | distributed `switch (x._tag)`        |
|  [04]   | keyed domain is the behavior                 | `as const satisfies Record` vocabulary lookup | repeated full-coverage `Match`       |
|  [05]   | non-`_tag` literal discriminant              | `Match.discriminatorsExhaustive(field)`       | hand-keyed `Record` + assert         |
|  [06]   | structural / multi-dimension predicate       | `Match.whenAnd`/`whenOr`/`not`                | nested boolean branching             |
|  [07]   | input shape, not nominal type, discriminates | `Match.type().pipe(Match.when, ...)`          | `if`-chain over open input           |
|  [08]   | one body over success / fail / context       | one Effect pipeline                           | per-channel sibling family           |
|  [09]   | optional context with identity               | one `Option<ContextRecord>`                   | `a?: T, b?: T, mode?: boolean` tail  |
|  [10]   | partial classification, absence is valid     | `Match.value(...).pipe(..., Match.option)`    | catch-all `orElse` masking a variant |
|  [11]   | typestate-carrying verb family               | `Data.TaggedEnum` `WithGenerics`              | per-state request union copy         |

## [02]-[ENTRYPOINT_LAW]

[REQUEST_COLLAPSE]:
- Law: one concern exposes one entrypoint; a verb family is a `Data.TaggedEnum` with one variant per verb under one `$match`.
- Law: each sibling's preamble becomes its variant payload and the shared validation becomes the decode prologue before dispatch.
- Law: exhaustive `$match` is the totality proof — a new variant breaks every dispatch site at compile time, never a runtime-silent fall-through.
- Law: a request family carrying typestate is one `Data.TaggedEnum<{...}>` declared through `TaggedEnum.WithGenerics`, so one generic owner threads the phase parameter across every verb rather than a per-state union copy; the constructor closes over the parameter and `$match` stays phase-total.
- Law: the dispatch is the `$match` arms themselves, never a parallel `Record<Verb, (payload) => Effect>` handler table selected by verb — the generated fold owns the verb list, so a handler `Record` that re-keys it is the same parallel-restatement defect as a per-tag constructor table.
- Use: the request union's constructors (`Request.Open({...})`) as the validated ingress and `$match` as the sole egress, deleting the `run`/`runSafe`/`runV2` family.
- Reject: a request union modeling success-or-failure (the Effect error channel owns outcome transport); a verb-keyed handler `Record` standing in for `$match`.
- Boundary: programs that must be inspected or re-interpreted reify verbs as a closed instruction `Data.TaggedEnum` under one interpreter `$match`; the request union with exhaustive dispatch is the form when they only run.

```ts conceptual
import { Data, Effect, Match, ParseResult, Schema as S } from "effect"

type Request = Data.TaggedEnum<{
  Open:  { readonly code: string }
  Amend: { readonly code: string; readonly delta: number }
  Close: { readonly code: string }
}>
const Request = Data.taggedEnum<Request>()

const dispatch = (ledger: _Ledger) => // $match is the sole egress; a new verb breaks every dispatch at compile time
  Request.$match({
    Open:  ({ code })        => ledger.open(code),
    Amend: ({ code, delta }) => ledger.amend(code, delta),
    Close: ({ code })        => ledger.close(code),
  })

const _Wire = S.Struct({ verb: S.Literal("open", "amend", "close"), code: S.NonEmptyString, delta: S.Number })
const _admit = Match.type<typeof _Wire.Type>().pipe( // reusable matcher built once; wire verb folds total into the union
  Match.discriminatorsExhaustive("verb")({ // a fourth verb breaks here, never an if-chain over open input
    open:  ({ code })        => Request.Open({ code }),
    amend: ({ code, delta }) => Request.Amend({ code, delta }),
    close: ({ code })        => Request.Close({ code }),
  }),
)

const admit = (raw: unknown): Effect.Effect<_Receipt, _Fault | ParseResult.ParseError> =>
  S.decodeUnknown(_Wire)(raw).pipe(Effect.map(_admit), Effect.flatMap(dispatch(_ledger))) // decode prologue, then one dispatch
```

## [03]-[MODAL_ARITY]

[ARITY_ABSORPTION]:
- Law: singular, multi-item, and empty call sites collapse into one signature; a non-empty tuple `readonly [T, ...ReadonlyArray<T>]` is the arity-polymorphic input that proves at least one element at the type level, and `Effect.forEach` carries the plural rail.
- Law: the discriminant is the input's length and shape, recoverable from the value; a `batch`, `many`, or `mode` flag beside the value is the rejected re-description.
- Use: `Effect.all` for a fixed heterogeneous struct or tuple, `Effect.forEach` for a homogeneous collection, and `Stream` when the source is unbounded or back-pressured.
- Reject: two collection-shaped entrypoints differing only by element conversion; one signature at the most-derived element type is the ambiguity-free shape.
- Boundary: after traversal the container is uniformly in the carrier, never mixed admitted-and-raw, which keeps the next entrypoint's discriminant recoverable from shape alone.

[MODALITY_FOLD]:
- Law: singular, plural-preserving, and plural-reducing are call shapes over one arm — singular is `Effect.map`/`flatMap`, plural-preserving is `Effect.forEach` with container shape intact, plural-reducing is `Effect.mergeAll` or `Effect.reduce` where the fold function is the policy selecting the reduction.
- Law: `Effect.all` with `{ mode: "either" }` yields `Either<A, E>` per branch and never fails; `{ mode: "validate" }` accumulates failures and discards successes; the default fails fast — the mode is the accumulate-versus-abort policy, fixed once.
- Use: `Effect.partition` for the survivor/casualty split returning `[rejected, accepted]` with `E = never`; `Effect.validateAll` when every failure must accumulate into a `NonEmptyArray<E>`.
- Reject: a count beside a collection whose `length` already answers it; counts and modes derive from the value or the chosen combinator, never the signature.
- Boundary: per-branch concurrency rides `{ concurrency: "inherit" | number | "unbounded" }`, a capability of how work runs, not which case it is.

```ts conceptual
import { Array as A, Data, Effect, Number as N, Option } from "effect"

class EntryFault extends Data.TaggedError("EntryFault")<{ readonly reason: "schema" | "quota" }> {}

const ingest = (entries: ReadonlyArray<_Raw>, step: (raw: _Raw) => Effect.Effect<_Receipt, EntryFault>, threshold: number) =>
  Effect.partition(entries, step, { concurrency: "inherit" }).pipe(
    Effect.map(([rejected, accepted]) => ({ rejected, accepted, histogram: A.groupBy(rejected, (e) => e.reason) })),
    Effect.filterOrFail(
      ({ rejected, accepted }) => N.divide(rejected.length, accepted.length + rejected.length).pipe(Option.getOrElse(() => 0)) <= threshold,
      ({ rejected }) => new EntryFault({ reason: A.head(rejected).pipe(Option.map((e) => e.reason), Option.getOrElse(() => "schema" as const)) }),
    ),
  )
```

## [04]-[PARAMETER_ALGEBRA]

[VOCABULARY_VALUES]:
- Law: a policy parameter arrives as one vocabulary row carrying its own behavior; the entrypoint reads the row through indexed access and invokes its columns, and no `if`/`Match` reconstructs at dispatch what the row already encodes.
- Law: `keyof typeof V` is the discriminant type gated through `satisfies` on the consuming error or request, so adding a row without its behavior column fails at compile time.
- Use: a vocabulary whose columns hold a `Schedule`, a `Duration`, an `Effect`-valued `log`, and a status, so retry, timeout, telemetry, and transport all read one row.
- Reject: a boolean parameter selecting between two bodies; a behavioral near-twin chosen by flag rather than by the row that encodes the boundary behavior; a `Match` chain re-deriving the row's thresholds.

[OPTIONAL_CONTEXT]:
- Law: `Option<T>` is the single optional form — `Option<T>` in domain with `Option.getOrElse(() => canonical)` at consumption, where the canonical fallback is the vocabulary owner's row, so the default derives once.
- Law: a nullable flag tail (`a?: T, b?: T, mode?: boolean`) fragments one context into parallel parameters; the collapse is one `Option<ContextRecord>` carrying the override bundle, with `T | undefined` the boundary-only spelling projected to `Option<T>` through `Option.fromNullable` at admission.
- Boundary: a capability orthogonal to the discriminant — a deadline, a tracing context — describes how work runs and rides the carrier through `Effect.timeout` and `Effect.withSpan`, never the signature.

[KNOB_TEST]:
- Law: the knob test is removal — delete the parameter, and if no information is lost that the value or the carrier cannot reconstruct, the parameter was a knob and the value already discriminates.
- Reject: a timeout or deadline as an entrypoint parameter; the bound is an effect-transformer aspect (`Effect.timeoutFail`) applied after dispatch, and the signature never grows a token tail for it.

```ts conceptual
import { Duration, Effect, Schedule } from "effect"

const _Channel = {
  email:   { retries: 5, delay: Duration.millis(500), timeout: Duration.seconds(10), log: Effect.logWarning },
  sms:     { retries: 0, delay: Duration.zero,        timeout: Duration.seconds(5),  log: Effect.logError   },
  webhook: { retries: 4, delay: Duration.seconds(1),  timeout: Duration.seconds(15), log: Effect.logError   },
} as const satisfies Record<string, { retries: number; delay: Duration.Duration; timeout: Duration.Duration; log: (...a: ReadonlyArray<unknown>) => Effect.Effect<void> }>

type _Via = keyof typeof _Channel

const _withPolicy = (via: _Via) => {
  const row = _Channel[via]
  return <A, R>(self: Effect.Effect<A, _DeliveryFault, R>) => self.pipe(
    Effect.retry(Schedule.exponential(row.delay).pipe(Schedule.intersect(Schedule.recurs(row.retries)), Schedule.whileInput((e: _DeliveryFault) => e.retryable))),
    Effect.timeoutFail({ duration: row.timeout, onTimeout: () => new _DeliveryFault({ via, reason: "timeout" }) }),
  )
}
```

## [05]-[MATCH_DISPATCH]

[TERMINAL_SELECTION]:
- Law: the completion operator is an explicit architectural decision — `Match.exhaustive` when an unmatched case is a compile error over a closed tagged domain, `Match.option` when it is valid absence yielding `Option<A>`, `Match.either` when it is observable evidence preserving `Left(Remaining)`.
- Law: the seed is the reuse decision — `Match.value(x)` seeds a one-shot match discharged inline, `Match.type<I>()` seeds a reusable matcher built once and applied across call sites; a `Match.value` rebuilt per call where one `Match.type` matcher serves every site is the rejected re-construction.
- Law: a fold that is solely a `_tag` table collapses to `Match.valueTags(cases)` (one-shot) or `Match.typeTags<I>()(cases)` (reusable) — no `Match.value(x).pipe(Match.tagsExhaustive(...))` scaffold around a pure-tag fold, and the generated `$match` on the owning `Data.TaggedEnum` is denser still when the family owns the value.
- Law: `Match.withReturnType<R>()` precedes every arm so a handler returning the wrong shape fails at the arm, not at consumption; placement after any `when` evaluates the constraint against a partial result type and permits heterogeneous widening.
- Use: `Match.tagsExhaustive` for a `_tag` domain and `Match.discriminatorsExhaustive(field)` for any string-literal discriminant — both are the terminal, no trailing `Match.exhaustive`.
- Reject: a catch-all `orElse` masking a new variant in a bounded union; an `if`/ternary chain for multi-dimension dispatch where `whenAnd`/`whenOr`/`not` compose additively.
- Boundary: `Match.instanceOf` returns a non-subtractive refinement, so `Remaining` never reaches `never` and the matcher demands an open terminal (`orElse`/`option`/`either`); `Match.string`/`number`/`bigint` are subtractive and compose with `exhaustive`.

```ts conceptual
import { Data, Match, Number as N, Option, Schedule, pipe } from "effect"

type Phase = Data.TaggedEnum<{
  Closed:   { readonly failures:  number; readonly ceiling: number }
  HalfOpen: { readonly successes: number; readonly window:  number }
  Open:     { readonly elapsed:   number; readonly backoff: number }
}>
const Phase = Data.taggedEnum<Phase>()

const projectPolicy = Match.type<Phase>().pipe(
  Match.withReturnType<{ readonly schedule: Schedule.Schedule<unknown>; readonly drain: boolean }>(),
  Match.tagsExhaustive({
    Closed:   ({ failures, ceiling }) => ({ schedule: Schedule.recurs(N.min(failures, ceiling)), drain: false }),
    HalfOpen: ({ successes, window }) => ({ schedule: Schedule.spaced(`50 millis`), drain: pipe(N.divide(successes, window), Option.map(N.lessThan(0.5)), Option.getOrElse(() => true)) }),
    Open:     ({ elapsed, backoff })  => ({ schedule: Schedule.exponential(`${backoff} millis`), drain: elapsed >= backoff }),
  }),
)
```

[PREDICATE_ALGEBRA]:
- Law: N independent dimensions dispatch through additive predicate composition — `Match.whenAnd` intersects guards, `Match.whenOr` unions them, `Match.not` captures the complement — each combinator extends the pipeline without restructuring existing arms.
- Law: a data-last predicate (`N.lessThanOrEqualTo(cap)`) plugs directly into an object-pattern slot, and a weighted projection over the matched fields produces a continuous scalar rather than a boolean pass/fail.
- Use: `Match.either` as the terminal when over-budget or unclassified input is capacity-planning evidence; numeric guards do not narrow `Remaining` to `never`, so `exhaustive` cannot terminate a predicate matcher.
- Reject: a `2^N` nested-conditional surface where predicate combinators collapse to linear composition.

[BRIDGE_CANONICALITY]:
- Law: a `Match` bridge to an Effect rail exists at exactly one canonical site per boundary type — `HttpClientResponse.matchStatus` for transport, `Cause.match` for concurrency topology — converging into one fault whose `Order`-derived lattice join reduces arbitrary cause trees through vocabulary ordinal comparison.
- Law: a foreign wire whose discriminant is a string literal rather than a `_tag` bridges through `Match.discriminatorsExhaustive(field)` over the decoded shape, with `discriminators(field)(...).pipe(Match.orElse(quarantine))` when the wire enumerates values the domain has not closed — the open terminal lands the typed quarantine case, so the wire→case hop is total at the boundary and an unmapped wire value is a declared fault, never a throw.
- Use: the bridge as a `static` method on the fault class so no per-caller projection exists; `Effect.sandbox` surfaces `Cause<unknown>`, `Cause.match` folds with the join, and `Effect.unsandbox` re-promotes to the typed error channel.
- Reject: a duplicated status-to-error or cause-to-error projection across call sites; a per-discriminant constructor `Record` standing in for the bridge fold; `catchAllCause` where re-promotion must preserve the typed rail for downstream retry.

## [06]-[CARRIER_POLYMORPHIC_DISPATCH]

[ONE_CARRIER_SURFACE]:
- Law: the form selects which arm runs, the Effect the arms return selects how results combine — orthogonal axes; one entrypoint returning `Effect.Effect<A, E, R>` dispatches success, typed failure, and context at once, and the per-channel sibling family is the rejected form.
- Law: the three channels are the precise capability contract — `A` the success, `E` the closed tagged-error family, `R` the required context — and a method whose `R = never` (because its constructor closed over yielded dependencies) carries no trailing dependency tail.
- Use: `Effect.either` to convert a failure to data inside a fold, `Effect.option` to project absence, and one `Schema.decodeUnknown` at the seam so the body never re-validates.
- Boundary: a fault pinned to one `Data.TaggedError` makes the failure surface a closed family, and `catchTag`/`catchTags` dispatch on the tag with compile-time coverage — adding a tag without a handler is a type error.

[INDEPENDENT_JOIN]:
- Law: independent operations combine through `Effect.all` and `Effect.zipWith`, dependent steps through `Effect.flatMap`, and the choice is load-bearing — a `flatMap` chain over independent operands reports only the first failure and discards the rest.
- Law: `Effect.all({ ... }, { mode: "validate" })` accumulates every independent failure as `{ [K]: Option<E_K> }`; `{ concurrency }` decides parallelism; same call site, the mode and concurrency alone switching semantics.
- Reject: a branch inside the join whose only legitimate content is total construction over already-resolved values; a branch is a fourth dispatch smuggled into combination and lifts into its own arm.
- Boundary: all branches share one error channel by construction, so failure semantics decide once; an expensive branch enters as a deferred `Effect` and a fail-fast mode leaves it unforced.

[ITERATIVE_DISPATCH]:
- Law: looping dependent dispatch is `Effect.iterate` or `Effect.loop` — the step returns the next state, the predicate decides continuation, and the stack never grows.
- Law: because the body is a description until the runtime interprets it, the same arms run under a deterministic test layer and the production layer — a totality proof under the test layer proves the production entrypoint.
- Boundary: layer changes are one `Layer.provide`, never a match-and-rebuild bridge; mid-pipeline concretization through `Effect.runSync` inside a transform defeats the polymorphism.

```ts conceptual
import { Array as A, Data, Effect, Order, Record as R } from "effect"

class Composite extends Data.Class<{ readonly code: string; readonly rank: number; readonly key: string }> {}

class JoinFault extends Data.TaggedError("JoinFault")<{ readonly slot: "code" | "rank" | "key" | "none"; readonly ord: number }> {
  static readonly clean = new JoinFault({ slot: "none", ord: -1 }) // identity seed: dominated by every real fault, so the fold is total
  static readonly join  = Order.max(Order.mapInput(Order.number, (f: JoinFault) => f.ord)) // pairwise lattice join over the ordinal column
  static readonly worst = (faults: ReadonlyArray<JoinFault>) => A.reduce(faults, JoinFault.clean, JoinFault.join) // dominant fault, no non-empty obligation
}

const assemble = (source: _Source, band: _Band, tag: _Tag): Effect.Effect<Composite, JoinFault> => // independent arms; one error channel decides failure semantics once
  Effect.all(
    { code: source.resolve, rank: band.rank, key: tag.key }, // a flatMap chain here would drop every failure after the first
    { concurrency: "unbounded", mode: "validate" },          // mode is the accumulate-vs-abort policy; concurrency is orthogonal capability
  ).pipe(
    Effect.mapError((slots) => JoinFault.worst(A.getSomes(R.values(slots)))), // {[K]: Option<E>} accumulates every independent failure; the join folds the set to its dominant fault, never a first-wins drop
    Effect.map(({ code, rank, key }) => new Composite({ code, rank, key })),  // total construction over already-resolved values, never a fourth dispatch
  )
```

## [07]-[ASPECTS]

[WEAVE_SEAM]:
- Law: a decode-time aspect is a property of the Schema — brand, filter, refinement woven into the single source; a composition-time aspect is a property of one call site — retry, timeout, telemetry attached as effect transformers in the pipeline.
- Law: the classification test is per-site variance — a concern present at every use weaves at the Schema or the service constructor, a concern that varies per site composes at the site through `.pipe(...)`.
- Law: `Effect.fn("span")(body, pipeline)` is the one seam — the body runs once per attempt, the pipeline operator receives the sealed effect and the original arguments, composing retry, timeout, and telemetry outside the body without re-entering it.
- Boundary: policy pushed inside the body, or admission hoisted above the single `Schema.decodeUnknown`, stops being recoverable from its declaration.

[STACKING_ORDER]:
- Law: composition-time aspects stack in author-written `.pipe(...)` order, and the same two aspects in two orders are two policies — `Effect.retry` around `Effect.acquireRelease` re-acquires per attempt, `acquireRelease` around `retry` acquires once and retries only the use.
- Law: `catchTag`/`catchTags` compose left-to-right and the first matching tag consumes the failure; a broad `catchAll` before a narrow `catchTag` shadows it, so the narrow handler precedes the broad one.
- Law: `Schedule.intersect` is the tighter of two policies (terminates when either exhausts), `Schedule.union` the looser; `Schedule.whileInput` gates on the error value and `Schedule.jittered` prevents a thundering herd.
- Reject: a bare alternation `eff1 | eff2` standing in for retry; a per-attempt resource acquired outside the retry scope.

```ts conceptual
import { Duration, Effect, Schedule } from "effect"

const _backoff = Schedule.exponential(Duration.millis(100)).pipe(
  Schedule.jittered,
  Schedule.intersect(Schedule.recurs(5)),
  Schedule.resetAfter(Duration.seconds(30)),
)

const guarded = (acquire: Effect.Effect<_Resource, _Fault>, use: (r: _Resource) => Effect.Effect<_Receipt, _Fault>) =>
  Effect.acquireUseRelease(acquire, (r) => use(r).pipe(Effect.retry(_backoff)), (r) => r.release)
```
