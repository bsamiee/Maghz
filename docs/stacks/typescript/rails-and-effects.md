# [RAILS_AND_EFFECTS]

The Effect ecosystem owns result rails, effect execution, immutable traversal, schedule policy, transactional state, and boundary cells. A carrier is chosen once at decode and never re-chosen mid-pipeline: the narrowest carrier that states the real outcome carries the value, reusable transforms keep it, and collapse to a bare value happens only at the runtime edge through `Effect.runPromise`, `Effect.runFork`, or a `Match` terminal. Decoded domain values enter these surfaces; raw provider, `Promise`, and JS-stdlib shapes do not.

## [01]-[RAIL_CHOOSER]

Choose the narrowest carrier that preserves the real outcome. A wider rail is earned only by a capability the narrower one cannot carry: typed failure, accumulated faults, required context, resource lifetime, schedule, transactional state, or concurrency.

| [INDEX] | [SURFACE]                   | [OWNS]                          | [REJECT]                         |
| :-----: | :-------------------------- | :------------------------------ | :------------------------------- |
|  [01]   | `Option<T>`                 | absence, no cause               | hidden failure, `null` leak      |
|  [02]   | `Either<E, A>`              | pure synchronous branching      | `throw` for control flow         |
|  [03]   | `Effect.Effect<A, E>`       | typed fallibility, deferral     | `Promise`, eager side effect     |
|  [04]   | `Effect.Effect<A, E, R>`    | required context capability     | service location, ambient global |
|  [05]   | `Cause<E>`                  | full failure tree at a boundary | flat error after composition     |
|  [06]   | `Schedule`                  | retry, repeat, backoff policy   | ad-hoc delay loop                |
|  [07]   | `Chunk<T>` / `Array` module | immutable traversal             | mutable `Array.push` flow        |
|  [08]   | `HashMap<K,V>` / `HashSet`  | immutable keyed lookup          | `new Map()` `.set` mutation      |
|  [09]   | `Ref<T>` / `STM` / `TMap`   | managed and transactional state | `let` accumulator, shared `var`  |
|  [10]   | `Stream<A, E, R>`           | back-pressured async sequence   | unbounded buffered array         |

`Option<T>` carries absence with zero failure semantics; promote to a typed `Effect` error when the caller must know why; the error channel `E` accumulates only when `Effect.all({ mode: "validate" })` or `Effect.validateAll` is the seam, otherwise it short-circuits.

[REPRESENTATION_DEFAULT]:
- Law: `Option<T>` is the domain absence carrier — `Option.fromNullable` at the boundary, `Option.match`/`Option.getOrElse` at consumption, never a bare `null` or `undefined` past the seam.
- Law: `Either<E, A>` carries pure synchronous branching without Effect overhead — `Either.right`/`Either.left`, `Either.match` — and lifts into the Effect error channel through `Effect.fromEither`.
- Boundary: an absence-carrying slot is `Option.none`; a fallible operation is a typed `Effect` failure; cause-bearing absence is a tagged family, never `Option`.

[CARRIER_IDENTITY]:
- Law: a tagged fault carries no payload distinction at the rail's identity level — two `IngressFault` values with different `cause` fields are `Equal` only field-wise, so a `HashSet<Fault>` dedupes by structural payload while a coarser dedupe (one slot per `_tag`) is an `Equivalence.mapInput(Equivalence.string, (f) => f._tag)` projection chosen deliberately, never an accident of which fields the carrier happens to expose; `$is`/`$match` are the generated guards a `Predicate.isRecord(x) && "_tag" in x` probe is the rejected re-derivation of.
- Law: a fault's severity is a vocabulary ordinal, never an ambient rank — `Order.mapInput(Order.number, (f) => SEVERITY[f._tag])` lifts the row into an `Order` over the fault and `Order.max` is the lattice join folding a cause set to its dominant fault, so reduction is the `Order` algebra, never a manual `reduce` comparing tags.
- Law: a compound rail key is a field-wise `Equivalence` carried into `Effect.cachedFunction(f, eq)`, not a delimiter-joined string — `Equivalence.mapInput(Equivalence.tuple(...), (k) => [k.content, k.policy] as const)` keys the memo so two dimensions never collide the way `` `${a}:${b}` `` does, and the in-flight computation is shared across concurrent callers on one equivalent key rather than raced.

## [02]-[BOUNDARY_CONVERSION]

Every boundary converts once into the carrier that states the real outcome; reusable transforms keep that carrier and never re-project mid-pipeline.

[EXCEPTION_CAPTURE]:
- Use: `Effect.tryPromise({ try, catch })` to capture a throwing async host call, `Effect.try({ try, catch })` for the synchronous counterpart, mapping the unknown cause immediately into a bounded tagged error.
- Law: the object form of `tryPromise` threads the `AbortSignal` into the host call for fiber-interruption propagation; the thunk form runs to completion regardless of interruption.
- Law: `Schema.decodeUnknown(schema)(input)` is the one inbound funnel — it admits unknown material and its `ParseError` lifts into the error channel through `Effect.mapError` at a single entry, never a per-shape branch.
- Reject: discarding the captured cause; a bare `try`/`catch` wrapping a rail transform; `Promise` chaining where an Effect carries the boundary.

```ts conceptual
import { Data, Effect, Schema as S } from "effect"

class IngressFault extends Data.TaggedError("IngressFault")<{ readonly stage: "decode" | "upstream"; readonly cause: unknown }> {}

const admit = <A, I>(schema: S.Schema<A, I>, dispatch: (a: A, signal: AbortSignal) => Promise<Response>) =>
  (input: unknown): Effect.Effect<Response, IngressFault> =>
    S.decodeUnknown(schema)(input).pipe(
      Effect.mapError((cause) => new IngressFault({ stage: "decode", cause })),
      Effect.flatMap((a) => Effect.tryPromise({ try: (signal) => dispatch(a, signal), catch: (cause) => new IngressFault({ stage: "upstream", cause }) })),
    )
```

[CROSS_RAIL_PROJECTION]:
- Use: `Effect.either` to migrate a failure into an `Either<E, A>` data value inside a fold; `Effect.option` to discard the failure side into `Option<A>`; `Effect.fromEither`/`Effect.fromOption` to widen back into the carrier; `Effect.flip` when a recovery branch reasons on the error as the success.
- Law: widening supplies the missing structure exactly once — `Option → Effect` is `Effect.fromOption(o, { onNone })`, `Either → Effect` lifts the left into `E`, and the narrowing arrow (`Effect.option`/`Effect.either`) is the only legal inverse; a second widen-narrow round trip is the rejected churn.
- Reject: a round trip that stamps a generic error over the original — `Effect.option` then `Effect.fromOption(_, { onNone: () => new GenericFault() })` erases the typed cause the first projection still held; the diagnostic identity of a typed fault survives every projection.

[TERMINAL_COLLAPSE]:
- Use: `Effect.runPromise`, `Effect.runFork`, `Match`-terminal collapse, or `Effect.runSync` only at the runtime edge — the composition root, a test, or a host callback.
- Law: reusable domain transforms keep the carrier; an `Effect.runSync` inside a pure projection or an `Option.match` mid-pipeline that loses composition is the rejected exit.
- Reject: mid-pipeline collapse inside a transform; `Match.exhaustive` called mid-pipeline where `map`/`flatMap` keep the rail.

## [03]-[TRAVERSAL_FLOW]

Traversal is rail policy: the collection shape and the sequencing combinator together decide how failures, effects, strictness, and concurrency compose.

[COLLECTION_OWNER]:
- Law: `HashMap<K,V>` owns immutable keyed accumulator state threaded through `Stream.mapAccum` or `Array.reduce`; `Chunk<T>` owns `Stream` operations (`Sink`, batching, `mapAccum` emissions) with O(1)-amortized append; the `Array` module owns small fixed collections with richer combinators (`Array.getSomes`, `Array.match`, `Array.groupBy`, `Array.dedupeWith`).
- Law: a `HashMap.set` returns a new map — persistent update, structural sharing, `Equal`/`Hash` integration; `new Map().set` mutation breaks referential transparency and is a boundary-only form.
- Use: `Chunk.toReadonlyArray` at the boundary transfer where a downstream consumer needs an array; `Array.fromIterable` to admit a foreign iterable once.
- Reject: `new Map()`/`new Set()`/`Array.push` mutation in domain flow; lazy flow over a disposed or host-owned resource.

[RAIL_TRAVERSAL]:
- Use: `Effect.forEach(items, f)` to abort on the first failure; `Effect.all(struct, { mode: "validate" })` to accumulate every independent failure; `Effect.partition(items, f)` to collect both rejected and accepted with `E = never`.
- Law: `{ concurrency: "inherit" | number | "unbounded" }` is the parallelism policy, not a performance tweak; `Effect.all` over effects launches per the concurrency, `Effect.forEach` is sequential at `concurrency: 1`.
- Law: `Effect.mergeAll(effects, zero, f)` is the N-way concurrent fold with positional index — pre-wrap each effect with `Effect.either` to convert failures to data, or the first failure short-circuits.
- Use: `Effect.validateAll` for a `NonEmptyArray<E>` of every failure; `Effect.validateFirst` for the first success.
- Reject: `Effect.allSuccesses` where a discarded failure is a silent correctness loss; an index-threaded fold unless the fold carries algorithm state.

```ts conceptual
import { Array as A, Data, Effect, Equal, Schema as S } from "effect"

const Code = S.NonEmptyString.pipe(S.brand("Code"))
class Input extends S.Class<Input>("Input")({ code: Code, score: S.Positive }) {} // Schema.Class: Equal/Hash auto-derived for structural dedupe
class AdmitFault extends Data.TaggedError("AdmitFault")<{ readonly stage: "code" | "strict"; readonly at: number }> {}

const _admit = (value: string, at: number) => // decode-once: brand + position fused, ParseError lifts to the typed fault at one seam
  S.decodeUnknown(Input)({ code: value, score: at + 1 }).pipe(Effect.mapError(() => new AdmitFault({ stage: "code", at })))
const _strict = (input: Input) => // admitted owner in, typed receipt out; filterOrFail is the mid-pipeline guard, not a throwing branch
  Effect.succeed(input).pipe(Effect.filterOrFail((i) => i.score <= 64, (i) => new AdmitFault({ stage: "strict", at: i.score })))

const traverseRaw = (raw: ReadonlyArray<string>) => // forEach is the abort-on-first sequencing policy; concurrency is parallelism, not failure semantics
  Effect.forEach(raw, _admit, { concurrency: "inherit" }).pipe(
    Effect.flatMap((inputs) => Effect.forEach(inputs, _strict, { concurrency: "inherit" })),
    Effect.map((receipts) => A.dedupeWith(receipts, Equal.equals)), // structural dedupe over branded owners, never a delimiter-joined key
  )
```

[FILTER_MAP_AND_AGGREGATION]:
- Use: `Array.filterMap` / `Array.getSomes` for atomic single-pass filter-map into `Option`, replacing `.filter(p).map(f)`; `Array.reduce` for immutable aggregation; `Array.groupBy` for keyed partition.
- Law: `Number.divide` returns `Option<number>`, forcing an explicit `Option.getOrElse` at every zero-denominator site, so no `NaN`/`Infinity` propagates through an arithmetic pipeline.
- Reject: a mutable accumulator, an append-heavy fold, and a `zip` across unequal lengths without first equalizing from domain knowledge.

[GUARDS]:
- Use: `Effect.filterOrFail(predicate, onFalse)` for a mid-pipeline boolean invariant producing a typed failure; `Effect.liftPredicate(value, predicate, onFalse)` to lift a value at entry; `Option.fromNullable(x)` then `Effect.fromOption` at a nullable boundary.
- Law: `filterOrDie`/`Effect.orDie` elevate a guard to a defect only at a boundary where the failure is a non-recoverable invariant, never in domain flow.
- Reject: boolean success/failure factories duplicating `filterOrFail`; a guard that throws instead of failing the rail.

## [04]-[FAILURE_HANDLING]

Apply carrier-qualified failure transforms before collapse; a rail transform never throws.

| [INDEX] | [COMBINATOR]                 | [USE]                              |
| :-----: | :--------------------------- | :--------------------------------- |
|  [01]   | `Effect.mapError(f)`         | reshape the typed failure          |
|  [02]   | `Effect.catchTag(tag, f)`    | recover one tagged variant         |
|  [03]   | `Effect.catchTags({...})`    | recover several tags with coverage |
|  [04]   | `Effect.catchIf(refine, f)`  | recover by `$is` refinement        |
|  [05]   | `Effect.tapError(f)`         | observe without channel widening   |
|  [06]   | `Effect.catchAllCause(f)`    | fold the full cause at a boundary  |
|  [07]   | `Effect.matchEffect(...)`    | branch both channels into one rail |
|  [08]   | `Effect.either` / `option`   | project failure into data          |
|  [09]   | `Effect.sandbox`/`unsandbox` | lift `Cause<E>` and re-promote     |

[CAUSE_NORMALIZATION]:
- Law: parallel and sequential composition produce composite cause trees that `catchTag` cannot dispatch; `Cause.match` is the exhaustive catamorphism with `onEmpty`/`onFail`/`onDie`/`onInterrupt`/`onSequential`/`onParallel`, and `onSequential`/`onParallel` receive already-reduced children so a commutative combiner shares one callback across both composition modes.
- Law: `Cause.failures(cause)` is the `Chunk<E>` of every typed failure a `validate`/concurrent fold accumulated — the lattice-join over that chunk (`Order.max` under the severity `Order`) is the one dominant fault, never a first-wins `catchTag` that drops siblings; `Cause.stripFailures` retains defects and interrupts alone for a defect-only postmortem.
- Law: `Effect.sandbox` surfaces `Cause<E>` into the error channel for cause-aware retry impossible at the `E` level and `Effect.unsandbox` re-elevates losslessly; `Cause.isInterruptedOnly` is pure cancellation, `Cause.keepDefects` is `Some` iff a defect exists, and `Cause.pretty` preserves tree topology where `Cause.squash` collapses it.
- Reject: a hand-rolled `_tag` switch over a cause that drops nested children; `Cause.squash` where the tree must survive to a sink; `catchAll` absorbing a defect into the success channel.

[FAILURE_VS_DEFECT]:
- Law: a recoverable failure rides the typed `E` channel; an invariant violation is a defect through `Effect.die`/`Effect.dieMessage`, surfaced only by `sandbox` or `catchAllCause` — laundering a defect into a failure destroys postmortem fidelity.
- Law: only a boundary function translates a defect to a failure (`Cause.fail`) or a failure to a defect (`Effect.orDie`); domain code never catches a defect with `catchAll`.
- Boundary: `Schedule.whileInput` gates retry on a cause-level predicate — retry only on pure failures, never on interruption or a defect.

```ts conceptual
import { Cause, Data, Duration, Effect, Option, Schedule } from "effect"

class StoreFault extends Data.TaggedError("StoreFault")<{ readonly op: "append" | "compact"; readonly origin: "fail" | "defect" | "interrupt" }> {}

const boundaryClose = (op: StoreFault["op"]) =>
  <A, E, R>(self: Effect.Effect<A, E, R>): Effect.Effect<A, StoreFault, R> =>
    self.pipe(
      Effect.sandbox,
      Effect.retry(Schedule.exponential(Duration.millis(50)).pipe(
        Schedule.intersect(Schedule.recurs(2)),
        Schedule.whileInput((cause: Cause.Cause<E>) => !Cause.isInterruptedOnly(cause) && Option.isNone(Cause.keepDefects(cause))),
      )),
      Effect.mapError((cause) => new StoreFault({ op, origin: Cause.isInterruptedOnly(cause) ? "interrupt" : Option.isSome(Cause.keepDefects(cause)) ? "defect" : "fail" })),
      Effect.withSpan(`boundary.${op}`),
    )
```

## [05]-[EFFECT_RUNTIME]

An Effect carries its required context `R`; the runtime resolves it once at the composition edge.

[CONTEXT_ACCESS]:
- Law: the capability shape selects the access tier — an `Effect.Service` (with `dependencies` and `accessors`) owns a capability with construction, lifecycle, or a method family; a bare `Context.GenericTag` owns a value-only capability the layer supplies with no behavior; a `Context.Reference` with `defaultValue` owns ambient configuration that must resolve with zero `R` when unprovided (a request id, a feature flag, a `Clock` substitute) — promoting a `Reference` to a `Service` adds a phantom requirement edge, and demoting a `Service` to a `Reference` strands its finalizers.
- Use: `Effect.Service` accessors or a `yield*` inside the service constructor to read a capability; `Effect.serviceOption(Tag)` for an optional capability with zero `R`; `Context.Reference` with a `defaultValue` for the unprovided-resolves-to-default case.
- Access: a method closing over a yielded dependency inside the scoped constructor carries `R = never` for callers within scope; `accessors: true` generates static delegates observing `R = Self` for callers outside.
- Boundary: the layer graph constructs the context once at the root; context-derivation arithmetic (`Exclude<R, Tag>`) belongs to `boundaries.md`.
- Reject: a service-location wrapper, an ambient global, an `interface IService` beside an `Effect.Service` class (the class is both value and type), three parallel capability-access spellings for one capability, or a `R` tail threaded by hand where the constructor closure eliminates it.

[RESOURCE_BOUNDARY]:
- Use: `Effect.acquireRelease(acquire, release)` for paired lifetime, `Effect.acquireUseRelease` to seal the use phase against external interruption, `Effect.addFinalizer` for unpaired cleanup, and `Effect.ensuring`/`Effect.onExit` for exit-aware teardown.
- Law: finalizers run LIFO on success, failure, and interruption — the last-registered resource releases first; `acquireRelease` guarantees exactly-once release on every exit path.
- Law: `Effect.forkScoped` binds a drain fiber to the enclosing scope so scope closure interrupts it; `Effect.fork` inside a scoped generator leaks the fiber past teardown.
- Exemption: a `// BOUNDARY ADAPTER` callback inside a capsule that wires a foreign event handler is the named statement seam; it never appears in domain flow.
- Reject: resource lifetime hidden behind ordinary domain state; a finalizer running long token-aware work.

```ts conceptual
import { Data, Duration, Effect, Queue, Schedule } from "effect"
import { SqlClient } from "@effect/sql"

class _StoreFault extends Data.TaggedError("StoreFault")<{ readonly op: "query" }> {} // timeout collapses to a typed fault, never a bare rejection

class StoreService extends Effect.Service<StoreService>()("domain/Store", {
  scoped: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient
    yield* Effect.acquireRelease(sql`SELECT pg_advisory_lock(42)`, () => sql`SELECT pg_advisory_unlock(42)`.pipe(Effect.ignore))
    const channel = yield* Effect.acquireRelease(Queue.bounded<string>(512), Queue.shutdown)
    const read = Effect.fn("Store.read")(
      (key: string) => sql<{ readonly value: string }>`SELECT value FROM kv WHERE key = ${key}`,
      (effect) => effect.pipe(
        Effect.retry(Schedule.exponential(Duration.millis(50)).pipe(Schedule.intersect(Schedule.recurs(3)), Schedule.jittered)),
        Effect.timeoutFail({ duration: Duration.seconds(5), onTimeout: () => new _StoreFault({ op: "query" }) }),
      ))
    return { read, channel } as const
  }),
}) {}
```

[SCHEDULE_POLICY]:
- Use: `Schedule` with `Effect.retry(schedule)`, `Effect.repeat(schedule)`, and `Effect.schedule` for retry, repeat, delay, timeout, and backoff when the local owner admits retry.
- Law: `Schedule.intersect` runs to the tighter of two policies (terminates when either exhausts), `Schedule.union` to the looser; unioning a finite curve onto an infinite one does not bound it.
- Law: `Schedule.whileInput`/`untilInput` gate on the error or output value, `Schedule.jittered` decorrelates, `Schedule.resetAfter` is the circuit-breaker primitive halting after N failures within a window, and `Schedule.addDelay(f)` derives an error-driven delay.
- Builders: `recurs`, `spaced`, `fixed`, `exponential`, `fibonacci`, `jittered`, `compose`, `intersect`, `union`, `resetAfter`, `whileInput`, `addDelay`.
- Reject: an ad-hoc delay loop; trusting an infinite backoff to stop itself.

## [06]-[STATE_AND_RECEIPTS]

State belongs at a boundary or service owner, not inside pure domain accumulation.

[MANAGED_STATE]:
- Use: `Ref<T>` for single-fiber mutable state with `Ref.update`/`Ref.modify`/`Ref.get`; `SynchronizedRef` for an effectful update; `FiberRef` for fiber-local context threaded through a subtree without a parameter.
- Law: `Ref.modify(f)` returns a value and the new state in one atomic step; `Ref.update` re-runs `f` on contention, so the transition is idempotent.
- Law: a `HashMap` threaded through `Stream.mapAccum` is the immutable accumulator — never a `new Map()` with `.set` mutation, which breaks referential transparency under retry.
- Reject: a `let` accumulator, a shared `var`, or a hidden global cell disguised as functional flow.

[TRANSACTIONAL_STATE]:
- Use: `STM` with `TRef`, `TMap`, `TQueue`, `TSemaphore`, and `TDeferred` when two or more cells must transition atomically; `STM.commit` wraps the whole read-update-derive cycle as one linearizable transaction that retries on conflict, and `STM.retry`/`STM.check` block the transaction until a watched cell satisfies a guard rather than spinning a poll loop.
- Law: a multi-cell transition observing a consistent snapshot is STM, never a single `Ref`; `TMap.updateWith` is the atomic read-modify-write over one key — a `TMap.get → STM.tap(TMap.set)` pair reopens the read-write window STM exists to close, and a dedupe `Ref<ReadonlySet<string>>` rebuilt by `Ref.modify(s => new Set([...s, k]))` is the non-atomic, non-structural form `TSet`/`TMap.updateWith` retires.
- Boundary: contention admission — `Queue.bounded`/`dropping`/`sliding`, `Semaphore.withPermits`/`withPermitsIfAvailable` — is the same admit-or-shed algebra driven by one policy vocabulary; the queue strategy is the data-loss contract.
- Reject: a lock or a race window where STM composes the atomic commit; a poll loop where `STM.check` suspends until the predicate holds.

```ts conceptual
import { Option, STM, TMap, TQueue } from "effect"

const claim = (queue: TQueue.TQueue<string>, lease: TMap.TMap<string, number>, cap: number) =>
  STM.commit(
    TQueue.take(queue).pipe(
      STM.tap(() => TMap.size(lease).pipe(STM.flatMap((held) => STM.check(() => held < cap)))),
      STM.tap((id) => TMap.updateWith(lease, id, Option.match({ onNone: () => Option.some(1), onSome: (n) => Option.some(n + 1) }))),
      STM.flatMap((id) => STM.map(TMap.size(lease), (held) => ({ id, held }))),
    ),
  )
```

[RECEIPTS]:
- Law: the split is capability — a `Stream` answers what happened and when, a typed receipt answers how this computation resolved; collapsing a receipt into a stream, or a generic ledger over typed proof, erases the typed evidence.
- Law: one receipt `Data.Class` carries a kind discriminant, a slot identifier, and a payload; adds, updates, removals, and errors are tag variants over one `Ref<Chunk<Receipt>>`, never parallel record types, and projections are pure folds over that one stream.
- Law: keep a typed receipt when fields carry solver, sampling, route, status, metric, or proof evidence; `Ref<Receipt>` holds the latest, history escalates to `Ref<Chunk<Receipt>>`.

```ts conceptual
import { Chunk, Data, HashMap, Number as N, Option, Order, Ref } from "effect"

const KIND = { added: 1, updated: 1, removed: 1, errored: 3 } as const // one vocabulary row carries the dominance weight; no ambient rank
class Receipt extends Data.TaggedClass("Receipt")<{ // one fact stream; the kind+slot discriminant retires a parallel record per bucket
  readonly kind: keyof typeof KIND
  readonly slot: string
  readonly weight: number
}> {
  static readonly bySeverity: Order.Order<Receipt> = Order.mapInput(Order.number, (r) => KIND[r.kind]) // vocabulary ordinal lifted into an Order
  static readonly tally = (log: Chunk.Chunk<Receipt>): HashMap.HashMap<Receipt["kind"], number> => // one keyed fold retires four counters
    Chunk.reduce(log, HashMap.empty<Receipt["kind"], number>(), (acc, r) =>
      HashMap.modifyAt(acc, r.kind, Option.match({ onNone: () => Option.some(1), onSome: (n) => Option.some(n + 1) })))
  static readonly dominant = (log: Chunk.Chunk<Receipt>): Option.Option<Receipt> => // lattice-join is the Order.max fold, never a first-wins scan
    Chunk.reduce(log, Option.none<Receipt>(), (top, r) => Option.some(Option.match(top, { onNone: () => r, onSome: (m) => Order.max(Receipt.bySeverity)(m, r) })))
  static readonly mass = (log: Chunk.Chunk<Receipt>): number => Chunk.reduce(log, 0, (sum, r) => N.sum(sum, r.weight))
}

const _emit = (cell: Ref.Ref<Chunk.Chunk<Receipt>>, fact: Receipt) => Ref.update(cell, Chunk.append(fact)) // append-only history cell, one swap per fact
```

## [07]-[CARRIER_INTEROP]

One transform serves the whole carrier family through a generic signature; failure rises through the channel, never a concrete constructor that pins the carrier.

[POLYMORPHIC_ARROW]:
- Law: a reusable transform is generic in `<A, E, R>` so one body composes over every concrete `Effect` the call sites supply — duplicating a pipeline once for the success rail and once for the fallible rail is the rejected fork; the carrier is the parameter, not a copy.
- Law: failure inside a polymorphic body rises through the supplied `onX` thunk or the threaded `E`, never a literal `new SomeFault()` that fixes the error type — a boundary combinator typed `(self: Effect.Effect<A, E, R>) => Effect.Effect<A, E2, R>` reshapes the channel for any input carrier and stays composable under `.pipe`.
- Use: `dual(arity, body)` to publish one operator in both data-first (`f(self, a)`) and data-last (`self.pipe(f(a))`) form from a single definition, so the pipeable spelling and the eager spelling are never two functions.
- Reject: parallel `Effect`/`Either`/`Option` pipelines for one transform; a body that lifts through `Effect.fail(new Fault())` where `Effect.mapError` at the seam carries the caller's error type.

[VARIANCE_AND_CONTEXT]:
- Law: the three channels are variance-typed — `A` covariant, `E` covariant, `R` contravariant — so `Effect<A, never, never>` is assignable wherever `Effect<A, E, R>` is expected and a transform that widens `E` to `unknown` or `R` to `any` discards the proof the channels carry; a polymorphic body preserves all three by never annotating its result, letting inference union the failures and intersect the requirements its composed steps introduce.
- Law: a capability the body reads is a `yield* Tag` accumulating into `R`, not a parameter — the requirement is recoverable from the signature and resolves at the layer edge; a context object threaded as an argument hides the same edge behind a value the type no longer surfaces.
- Reject: a transform annotated `Effect<A, unknown, any>` that erases channel evidence; a hand-threaded context argument where the `R` channel carries the capability.

```ts conceptual
import { dual } from "effect/Function"
import { Effect } from "effect"

const traced: {
  (label: string): <A, E, R>(self: Effect.Effect<A, E, R>) => Effect.Effect<A, E, R>
  <A, E, R>(self: Effect.Effect<A, E, R>, label: string): Effect.Effect<A, E, R>
} = dual(2, <A, E, R>(self: Effect.Effect<A, E, R>, label: string) =>
  self.pipe(Effect.withSpan(label), Effect.tapErrorCause((cause) => Effect.annotateCurrentSpan("fault", cause._tag))),
)
```
