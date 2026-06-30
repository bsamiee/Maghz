# [RAILS_AND_EFFECTS]

LanguageExt owns result rails, effect execution, immutable traversal, schedule policy, and boundary state cells. A carrier is chosen once at admission and never re-chosen mid-pipeline: the narrowest carrier that states the real outcome carries the value, reusable transforms keep it, and collapse to a bare value happens only at host, UI, native, command, or wire edges. Admitted domain values enter these surfaces; raw host, native, wire, and generated shapes do not.

Four siblings own the shapes this algebra composes as settled material. The closed `Fault` `[Union]` over `Expected`, its `Semigroup` `Combine`, and the `Admission` bridge over the generated factory are `shapes.md`'s; the definition-time generator weave and the composition-time aspect fold that stack retry, bracket, and catch over one core, plus the continue-or-done iterative-dispatch step, are `surfaces-and-dispatch.md`'s; the native lifetime capsule, the serialized many-`Ref` state transaction, and the boundary memo key are `boundaries.md`'s; the span fold kernels a measured body names at the `EXPRESSION_SPINE` exemption are `algorithms.md`'s. This page composes each to legislate only which carrier states an outcome, how a boundary mints it, how a reusable transform threads it, how a collection sequences it, how the `Fault` family accumulates through `Validation`, where the carrier collapses, and how a cell or receipt carries evidence.

## [01]-[RAIL_CHOOSER]

Choose the narrowest carrier that preserves the real outcome. A wider rail is earned only by a capability the narrower one cannot carry: accumulated faults, runtime context, resource lifetime, schedule, state, or carrier polymorphism.

| [INDEX] | [SURFACE]             | [OWNS]                         | [REJECT]                    |
| :-----: | :-------------------- | :----------------------------- | :-------------------------- |
|  [01]   | `Option<T>`           | absence                        | hidden failure              |
|  [02]   | `Fin<T>`              | synchronous fallibility        | thrown control flow         |
|  [03]   | `Validation<E,T>`     | independent accumulated faults | early guard chain           |
|  [04]   | `Eff<RT,T>`           | runtime capability             | service location            |
|  [05]   | `IO<T>`               | deferred boundary work         | eager side effect           |
|  [06]   | `Schedule`            | retry or repeat policy         | ad-hoc delay loop           |
|  [07]   | `Seq<T>` and `Arr<T>` | immutable traversal            | mutable collection flow     |
|  [08]   | `HashMap<K,V>`        | immutable keyed lookup         | mutable dictionary policy   |
|  [09]   | `Atom<T>`             | boundary state cell            | domain accumulator          |
|  [10]   | `K<F,A>`              | carrier-polymorphic arrow      | duplicate carrier pipelines |

`Option<T>` carries absence with zero failure semantics; promote to `Fin<T>` when the caller must know why; promote to `Validation<E,T>` only when independent faults must accumulate before reporting. `Fin<T>` pins its fail side to `Error` — the narrowest carrier whose failure composes with effect lifts without a bridge; `Either<L,R>` is reserved for a left that is not `Error` and demands an explicit `L → Error` bridge before entering an effect chain.

[REPRESENTATION_DEFAULT]:
- Law: `Option<T>` is a `readonly struct` — value-copied, zero-allocation, total over `default` as `None`.
- Law: every class-shaped carrier — `Fin`, `Validation`, `Either`, the effect carriers — has a null reference as `default`, throwing before the rail ever sees it.
- Boundary: an absence-carrying slot defaults safely; a fallible field, array slot, or generic `default` is a latent null, never zero-init storage.

[CARRIER_IDENTITY]:
- Law: `Fin<T>` failure identity is a bare case test — every failure equals every other and hashes to one constant, so a set or dictionary keyed on `Fin` coalesces all failures into one bucket, where the accumulating carrier keeps each fault distinct; keying observability or dedup on a rail therefore projects a scalar discriminant first.
- Law: a payload-typed carrier's default `==` and `GetHashCode` route through a per-call reflective trait probe, not `EqualityComparer<T>.Default` — material in a hot set or dictionary probe.
- Use: the witness-form `CompareTo<OrdA>(other)` over an explicit `Ord<A>` or a projected scalar key to escape the reflective resolver on the hot path; the default comparer is the cold-path-only form.

## [02]-[BOUNDARY_CONVERSION]

Every boundary converts once into the carrier that states the real outcome; reusable transforms keep that carrier and never re-project mid-pipeline.

[EXCEPTION_CAPTURE]:
- Use: `Try.lift<Fin<T>>(f).Run().MapFail(...).Bind(static r => r)` to capture a throwing native or host call into one `Fin<T>`.
- Law: the self-flattening `Bind(static result => result)` collapses `Try`'s outer rail into the call's inner `Fin`; without it the captured error is discarded.
- Law: one inbound funnel admits a raw exception, a wrapped error-exception, a bare string, or an option at a single entry, never a per-shape branch.
- Reject: discarding the captured `Error.Message` after `Try.lift`; a bare `try`/`catch` wrapping a rail transform.

```csharp conceptual
public static Fin<Receipt> Capture(Func<Fin<Receipt>> native) {
    ArgumentNullException.ThrowIfNull(native);

    return Try.lift<Fin<Receipt>>(f: native)
        .Run()
        .MapFail(error => new Fault.NativeRejected(Detail: error.Message))
        .Bind(static result => result);
}
```

[CROSS_RAIL_PROJECTION]:
- Use: the instance matrix — `ToOption`, `ToFin`, `ToValidation`, `ToEither`, `ToEff` — to migrate a carrier once; every rail projects to `Option<T>` by discarding the failure side.
- Law: widening supplies the missing structure — `Option → Fin` needs an `Error`, `Either → Eff` needs an `L → Error` map.
- Law: the `Fin → Option → Fin` round trip stamps `Errors.None` over the original error and breaks every later `HasCode`/`Is` predicate; `option.ToFin(Error.New(...))` preserves diagnostic identity.
- Reject: natural-transformation round trips where an explicit projection carries the error through.

[TERMINAL_COLLAPSE]:
- Use: `Match`, `IfFail`, `Run`, `RunAsync`, or unsafe extraction only at host, UI, native, command, or wire edges.
- Law: reusable domain transforms keep the carrier; `.Value` and the `internal` `SuccValue`/`SuccessValue` accessors are never the exit.
- Reject: mid-pipeline collapse inside a pure projection; `Option.Match` inside an expression rail.

## [03]-[TRAVERSAL_FLOW]

Traversal is rail policy: the collection shape and the sequencing operator together decide how failures, effects, strictness, and resource boundaries compose.

[COLLECTION_OWNER]:
- Law: `Map<K,V>` over `HashMap<K,V>` only when key order is the operation; `BiMap<A,B>` when bidirectional lookup is the domain constraint, never a pair of maps; `Lst<T>` only for positional mid-sequence insert.
- Law: conversion arrows are outbound-only — `where F : Natural<F, Seq>` is satisfied by `Arr`, `Iterable`, and `Iterator` but never by `Seq` itself, so a `Seq`-typed input needs a direct branch.
- Law: `Count`, `AsSpan()`, and `Add` force complete evaluation of a lazy backing; incremental build is `Cons`-then-reverse, never repeated `Add`.
- Use: `.Strict()` before boundary transfer when lazy traversal would outlive its owner or re-pay O(n) per enumeration over a concat backing.
- Reject: lazy flow over disposed, borrowed, UI, native, or host-owned resources.

[RAIL_TRAVERSAL]:
- Use: `.TraverseM(f).As()` to abort on the first failure; `.Traverse(f).As()` to accumulate every failure — the operator is the sequencing policy, not a performance tuning.
- Law: `TraverseM`'s trait-default body delegates to applicative `traverse`, so an un-overridden foldable accumulates under a monadic name; assuming abort-on-first-failure from an arbitrary kind is a latent correctness bug.
- Law: over an effect carrier `Apply` launches both operands before awaiting while `Bind` is sequential, so `TraverseM` over independent effects serializes them.
- Use: `.TraverseM(identity).As()` when the collection already holds carriers; `PartitionFallible` when every effect must run and both outcomes collect.
- Use: indexed `Map((value, index) => ...)` before traversal when the algorithm needs the position; the `.As()` re-anchor is always mandatory.
- Reject: `.Map(f).TraverseM(identity)` where direct `.TraverseM(f)` fuses; index-threaded folds unless the fold carries algorithm state.

```csharp conceptual
public static Fin<Seq<Receipt>> TraverseRaw(Seq<string> raw) =>
    raw.Map((value, index) => AdmitCode(value).Map(code => new Input(Code: code, Score: index + 1)))
        .TraverseM(identity)
        .As()
        .Bind(inputs => inputs.TraverseM(input => Mode.Strict.Apply(input)).As())
        .Map(static receipts => receipts.Strict());
```

[FILTER_MAP_AND_AGGREGATION]:
- Use: `.Choose(f)` for atomic single-pass filter-map into `Option<T>`, replacing `.Filter(p).Map(f)`; the indexed and keyed-map overloads carry position or key through.
- Law: `Arr` and `Lst` own no `Choose` instance — the absence is structural, reached only through the `MonoidK`+`Monad` trait path, never wrapped around.
- Use: `.Fold(init, f)` for immutable aggregation; prepend-then-reverse or an owning builder when fold output preserves order.
- Reject: mutable accumulators, append-heavy fold state, and `Zip` across unequal lengths without first equalizing from domain knowledge.

[PRELUDE_GUARDS]:
- Use: `guard`/`guardnot` in a query expression as the idiomatic ingress for boolean invariants at pipeline head; the payload-free `guard<F>(bool)` form yields any alternative-capable carrier.
- Law: `guard` returns `Guard<Error,Unit>` bound through per-rail `SelectMany`, never a return type — it always exits as the destination monad.
- Use: `Optional(x).ToFin(error)` at a nullable boundary to admit absence as failure.
- Reject: boolean success/failure factories that duplicate `guard(...).ToFin()`.

## [04]-[FAILURE_HANDLING]

Apply carrier-qualified failure transforms before collapse; a rail transform never throws.

| [INDEX] | [COMBINATOR]            | [CARRIERS]                        | [USE]                  |
| :-----: | :---------------------- | :-------------------------------- | :--------------------- |
|  [01]   | `.MapFail(f)`           | `Fin`, `Validation`, `Eff`, `Try` | map failure            |
|  [02]   | `.BindFail(f)`          | `Fin`, `Validation`, `Try`        | recover rail           |
|  [03]   | `.IfFail(f)`            | `Validation`, `Try`, `Eff`        | terminal fallback      |
|  [04]   | `.BiBind(Succ:, Fail:)` | `Fin`, `Validation`               | branch both sides      |
|  [05]   | `.BiMap(succ, fail)`    | `Fin`, `Validation`, `Option`     | map both sides         |
|  [06]   | `.ToFin()`              | cross-rail                        | project to `Fin`       |
|  [07]   | `.ToValidation()`       | cross-rail                        | project to validation  |
|  [08]   | `.ToOption()`           | cross-rail                        | discard failure detail |
|  [09]   | `.Match(Succ:, Fail:)`  | `Fin`, `Option`, `Either`         | terminal collapse      |

[VALIDATION_MONOID]:
- Law: the failure type is itself the aggregate — `Error` is one error and a thousand at once through `ManyErrors`, so a rail's failure slot never widens to `Seq<Error>` and `Errors.None` is the monoid identity; the closed `Fault` `[Union]` over `Expected` carrying its own `Semigroup` `Combine` is the accumulation carrier shapes.md mints, composed here, never re-declared.
- Law: `Validation<E,T>` requires an error carrier with an owned combination law — the `Fault` family, `StringM`, or another `Monoid<E>` — never `Validation<Seq<Error>,T>` or `Validation<string,T>`; the missing monoid makes the accumulating shape unmanufacturable, so the carrier choice and the fault family are one decision.
- Law: the closed-field product accumulates through the tuple `.Apply` surfaces.md owns; this page's region is the open extension set — independent constraints foreign code supplies fold applicatively through `.Traverse`, so the `Validation` `Apply` runs every `Check` and `Error.Combine` unions every fault before the boundary reports, where a `.TraverseM`/`Bind` fold would surface only the first.
- Law: an `IConstraint<T>` conformance lifts its fault through the implicit `Error → Validation<Error,T>` widening — `value` on success, the bare `Fault` case on failure — so the triple-cast that spells the lift by hand is the deleted ceremony; the floor is held by the owner and minted downstream, the closed family the owner switches and the open set it folds co-existing on one owner.
- Law: `MapFail` on `Fin` is `Error → Error` pinned; on `Validation` it changes the failure type and requires `Monoid<F1>` — the asymmetry decides which carrier survives accumulation.
- Reject: building an independent-field product with `from`/`select` inside an accumulating carrier, which silently switches accumulation off; bridging a composite owner through `TryCreate` or a hand-built `out var` ternary where shapes.md's `Admitted` factory bridge plus the composite-refinement `guard` already admit leaf-then-composite; an interface over the closed family, which forfeits `Switch` totality; a `Switch` over the open set, which cannot admit a foreign conformance; a `Bind` fold over the open constraint set, which reports only the first violation where the applicative fold reports all.

```csharp conceptual
public interface IConstraint<T> {
    Validation<Error, T> Check(T candidate);
}

public sealed class WithinBound(int ceiling) : IConstraint<RangeValue> {
    public Validation<Error, RangeValue> Check(RangeValue value) =>
        value.Span <= ceiling ? value : new Fault.Bounds($"<span {value.Span} over {ceiling}>");
}

public sealed class Ordered : IConstraint<RangeValue> {
    public Validation<Error, RangeValue> Check(RangeValue value) =>
        value.Start <= value.End ? value : new Fault.InvalidRange(Start: value.Start, End: value.End);
}

public static class Constrained {
    public static Validation<Error, RangeValue> Admit(string raw, int start, int end, params ReadOnlySpan<IConstraint<RangeValue>> over) {
        var checks = Iterable.createRange(over);
        return RangeValue.Admitted((raw, start, end)).Bind(value =>
            checks.Traverse(constraint => constraint.Check(value)).As().Map(_ => value));
    }
}
```

[RECOVERY]:
- Use: `BindFail`, `IfFail`, `BiBind`, and `BiMap` to recover or branch a rail; bind the failure parameter when producing a replacement fault or fallback.
- Law: recovery preserves diagnostic context — losing an exception message, raw validation message, or failure category during conversion is the defect.
- Boundary: facet routing and code-keyed recovery are fault-family law; a carrier recovery transforms the rail, not the fault taxonomy.
- Reject: `.ToOption()` before recovery where the error must survive.

## [05]-[EFFECT_RUNTIME]

An effect carries the runtime; `Eff<RT,T>` and `IO<T>` defer boundary work until a single run at the composition edge.

[RUNTIME_RECORD]:
- Use: `Eff<RT,T>` when the operation needs host capability, cancellation, clock, filesystem, UI, native document, or another runtime dependency.
- Access: `Eff.runtime<RT>()` lifts the whole runtime as a bound value; `.Map(rt => rt.Slot)` projects one capability without an accessor protocol.
- Boundary: construct the runtime once at the composition edge; `Eff.local(f, inner)` runs an inner-runtime projection in a fresh cancel scope.
- Reject: service-location wrappers and ambient host globals inside reusable transforms.

```csharp conceptual
public sealed record Runtime(Mode Mode, TimeProvider Clock, Atom<HashMap<CodeValue, Receipt>> Cache, CancellationToken Cancel);

public static class Capability {
    public static readonly Eff<Runtime, Mode> AskMode =
        Eff.runtime<Runtime>().Map(static runtime => runtime.Mode).As();

    public static readonly Eff<Runtime, DateTimeOffset> Now =
        Eff.runtime<Runtime>().Map(static runtime => runtime.Clock.GetUtcNow()).As();

    public static Eff<Runtime, Receipt> InMode(Eff<Mode, Receipt> scoped) =>
        Eff.local<Runtime, Mode, Receipt>(static runtime => runtime.Mode, scoped);
}
```

[RESOURCE_BOUNDARY]:
- Use: `IO<T>.Bracket`, `BracketIO`, `Finally`, or an owner-local capsule when the effect owns acquisition; the owner that acquires disposes losing and failure branches.
- Law: bulk teardown runs in hash-derived order, not last-in-first-out — a dependent that must release before its dependency is one composite resource's release arrow, never two registrations.
- Law: a release arrow runs under a non-cancellable token; long token-aware work does not belong in a disposer.
- Exemption: `using` acquisition inside a boundary capsule is the named statement exemption; it never appears in domain flow.
- Reject: resource lifetime hidden behind ordinary domain state.

```csharp conceptual
public static IO<Receipt> Guarded(IO<Resource> acquire, Func<Resource, IO<Receipt>> use) {
    ArgumentNullException.ThrowIfNull(acquire);
    ArgumentNullException.ThrowIfNull(use);

    return acquire
        .Retry(Backoff)
        .Bracket(
            Use: use,
            Catch: static error => IO.fail<Receipt>(new Fault.NativeRejected(Detail: error.Message)),
            Fin: static resource => resource.ReleaseIO());
}
```

[EFFECT_RECOVERY]:
- Use: `Prelude.catch`, `@catch`, `catchOf`, `IfFailEff`, and a `CatchM` policy value from a factory at effect boundaries.
- Law: a recovery is a reified predicate-handler pair — the predicate chooses which failures, the combinator chooses single-fail versus visit-every-member multiplicity, and the first matching predicate consumes the failure.
- Law: a `CatchM` is a recovery value — a factory returns it and `K<M,A> | CatchM` composes a policy ladder over one `Fallible<Error,M>, Monad<M>` body, so recovery is selected from a table, never re-coded per call site.
- Law: catch is a stack frame — a handler cannot catch a failure arising after its protected region, and recovery re-enters the saved continuation rather than terminating the rail.
- Reject: bare `eff1 | eff2` as fallback or retry semantics; predicates written against exception types instead of codes and facets.

```csharp conceptual
public static CatchM<Error, M, Receipt> Transient<M>() where M : Fallible<Error, M>, Monad<M> =>
    @catch<M, Receipt>(static error => error.IsExceptional, static _ => pure<M, Receipt>(Receipt.Retried));

public static K<M, Receipt> Recover<M>(K<M, Receipt> work) where M : Fallible<Error, M>, Monad<M> =>
    work
      | Transient<M>()
      | expected<M, Receipt>(static _ => pure<M, Receipt>(Receipt.Degraded))
      | @catch<M, Receipt>(static _ => true, static _ => pure<M, Receipt>(Receipt.Empty));
```

[SCHEDULE_POLICY]:
- Use: `Schedule` with `IO<T>.Retry(Schedule)`, `Prelude.retry`, and `repeat` for retry, repeat, delay, timeout, and backoff when the local owner admits retry.
- Carrier split: `.Retry(Schedule)` is the `IO<T>` form; `Eff` retry is `Prelude.retry(schedule, eff)`, never a method on the effect.
- Law: retry wraps each attempt in a fail-only scope so the successful attempt's resources survive to the caller; repeat wraps every iteration unconditionally, so a repeated computation can never acquire and return a live resource.
- Law: `recurs(n)` is `Take(n)` for exactly n attempts; `repeat(n)` cycles the whole base n times.
- Law: union (`|`) runs to the longer operand, so unioning a finite curve onto an infinite one does not bound it; intersect (`&`) or a cumulative-delay gate does.
- Law: `RepeatWhile`/`RepeatUntil` over a state-advancing effect is the schedule-driven iteration that retires a `for`/`while` counter — a stop predicate on the advanced state converges, the bare `recurs(n)` bound alone samples.
- Builders split by return type and that split is the composition law: `spaced`, `linear`, `exponential`, `fibonacci`, `upto`, `windowed`, and `Forever` mint a `Schedule` curve, while `recurs`, `jitter`, `maxDelay`, `maxCumulativeDelay`, and `decorrelate` mint a `ScheduleTransformer` that reshapes a curve. The `Schedule | ScheduleTransformer` and `Schedule & ScheduleTransformer` operator overloads plus the implicit `ScheduleTransformer`-to-`Schedule` coercion fuse the two kinds in one chain, so a transformer-headed expression collapses to a `Schedule`; transformer-to-transformer composition is `+`, never `|`.
- Reject: ad-hoc delay loops; trusting an infinite backoff to stop itself; reading the union of a curve and a transformer as a curve-union choice when it is a reshape.

```csharp conceptual
public static readonly Schedule Backoff =
    (Schedule.recurs(times: 6)
   | Schedule.exponential(seed: 50 * ms)
   | Schedule.maxDelay(max: 2 * seconds)
   | Schedule.decorrelate(factor: 0.2, seed: 7)
   | Schedule.maxCumulativeDelay(max: 30 * seconds))
   & Schedule.spaced(space: 100 * ms);

public static IO<Receipt> Resilient(IO<Receipt> work) =>
    work.Retry(Backoff);
```

```csharp conceptual
public static IO<State> Converge(Atom<State> cell, Func<State, State> advance) =>
    IO.lift(() => cell.Swap(advance))
        .RepeatWhile(
            schedule: Schedule.recurs(times: 256) & Schedule.spaced(space: 1 * ms),
            predicate: static state => !state.Stable);
```

[OPERATOR_BOUNDARIES]:

| [INDEX] | [OPERATOR]            | [CARRIER]                | [OWNS]                            |
| :-----: | :-------------------- | :----------------------- | :-------------------------------- |
|  [01]   | `>>`                  | `K<F,A>`                 | Kleisli sequence, discard-first   |
|  [02]   | `>>>`                 | `K<F,A>`                 | applicative sequence              |
|  [03]   | `*`                   | `K<F,A>`                 | functor map, applicative apply    |
|  [04]   | `>> lower`, unary `+` | `K<F,A>`                 | downcast to the concrete rail     |
|  [05]   | `\|`                  | `Validation` choice      | first success wins                |
|  [06]   | `\|`                  | `Fallible` with `CatchM` | catch and recovery                |
|  [07]   | `\|`                  | `Eff` with `Finally`     | finally composition, not choice   |
|  [08]   | `\|`                  | `Schedule`               | schedule union                    |
|  [09]   | `&`                   | `Validation`             | applicative product, fault append |
|  [10]   | `+`                   | `Error`, monoidal `E`    | failure append                    |
|  [11]   | `+`                   | `ScheduleTransformer`    | transformer composition           |

- Rule: the same glyph is a different algebra per carrier, so a non-local type reaches for the named method (`union`/`intersect` on `Schedule` are Prelude functions, schedule intersect is not `&`); `|` on `Validation` is first-success choice while on `Fallible` it is catch-wrapping, so an ambiguous receiver is `.As()`-anchored before the operator.
- Reject: a `[Flags]` enum bitwise `|` standing in for combinable capability, which shapes.md replaces with frozen-set membership and a fold; a domain owner defining `+`/`|` whose algebra is not the rail's, which collides with the carrier overloads at one call site.

## [06]-[STATE_RECEIPTS]

State belongs at a boundary or session owner, not inside pure domain accumulation.

[CELL_AND_THREAD]:
- Law: one producer in one run threads the receipt through a state or writer transformer channel — pure, replayable, no atom, no contention; many producers or runs require a cell.
- Law: a threaded receipt dies at the run boundary; cross-run accumulation, cross-thread visibility, or observation outside the pipeline requires a cell.
- Use: layer both — thread per run, fold each run's final output into the cell once at the run edge, one swap per run.
- Reject: a cell where one run's thread suffices; a thread where another thread must observe.

[ATOM_STATE]:
- Use: `Atom<T>.Value` for point reads; `Swap(f)` for a synchronous transition returning the post-transition state; `SwapMaybe(f)` for an optional transition that aborts on `None`.
- Law: `Swap`'s `f` re-runs on every CAS retry under contention, so any side effect inside it repeats; the transition must be idempotent — `TryAdd` makes first-writer-wins explicit.
- Law: a validator sees only the proposed value and runs once; first-writer-wins cannot be a validator, it needs `SwapMaybe` inspecting the incoming value.
- Law: `Change` fires synchronously on the calling thread before `Swap` returns; a slow handler throttles the swapper.
- Reject: read-modify-write outside `Swap`; hiding native lifetime, host tree mutation, or domain aggregation behind `Atom<T>`.

```csharp conceptual
public static Fin<Receipt> Memoized(Runtime runtime, Input input) =>
    runtime.Cache.Value.Find(input.Code) is { IsSome: true, Case: Receipt cached }
        ? Fin.Succ(cached)
        : runtime.Mode.Apply(input).Map(receipt =>
            runtime.Cache
                .Swap(state => state.TryAdd(input.Code, receipt))
                .Find(input.Code)
                .IfNone(receipt));
```

[BOUNDARY_STATE_FAMILIES]:
- Use: `Atom<T>`, `AtomHashMap`, `AtomSeq`, and `AtomQue` at UI, session, memoization, or concurrent boundary owners.
- Law: `AtomHashMap<K,V>` beats `Atom<HashMap<K,V>>` when key-level concurrent mutation or typed change diffs drive observers — key-level swaps and a typed patch versus whole-value replacement.
- Law: batch through `Swap(s => s.Add(...))` to land multiple appends in one CAS; `AtomSeq.Add` runs an independent CAS per element.
- Boundary: two-or-more-`Ref` atomic transitions are STM, not a single-cell boundary.
- Reject: global mutable state disguised as functional flow.

[RECEIPTS]:
- Law: the split is capability — a stream answers what happened and when, a typed receipt answers how this computation resolved; collapsing a receipt into a stream, or a generic ledger over typed proof, erases the typed evidence.
- Law: one `FactRecord` carries a kind discriminant, a slot identifier, and a payload union; adds, updates, removals, and errors are kind cases over `Atom<Seq<FactRecord>>`, never parallel record types.
- Projection: filter-by-kind, group-by-slot-last-wins, and full chronology are pure folds over that one fact stream, never separate cells or parallel fields synced by hand.
- Law: keep a typed receipt when fields carry solver, sampling, route, status, metric, spectral, mesh, extraction, or proof evidence; `Atom<ReceiptRecord>` holds the latest, history escalates to `Atom<Seq<ReceiptRecord>>`.

```csharp conceptual
public readonly record struct Receipt(CodeValue Code, int Count) {
    public static readonly Receipt Empty = new(Code: CodeValue.Create(value: "SUM"), Count: 0);

    public static Receipt operator +(Receipt left, Receipt right) =>
        new(Code: left.Code, Count: left.Count + right.Count);

    public static Receipt Collapse(Seq<Receipt> receipts) =>
        receipts.Fold(Empty, static (sum, receipt) => sum + receipt);
}
```

## [07]-[INTEROP]

One implementation crosses carriers through `K<F,A>`; transformer stack order is a capability decision, and host values cross into rails at adapter edges.

[CARRIER_POLYMORPHIC]:
- Use: `K<F,A>` and trait-constrained arrows when one body genuinely serves `Fin`, `Eff`, `Option`, `IO`, and transformer stacks; the constraint set is the capability contract — functor maps, applicative adds pure and apply, monad adds bind.
- Law: failures raise through trait statics — `Fallible.fail<E,F,A>` — never a concrete `Fin.Fail` inside the body, which silently pins the carrier.
- Law: the caller re-anchors the erased kind with the carrier's own `.As()`; omitting the pin is the most common carrier-polymorphic error — the value stays existentially kinded and refuses concrete operators.
- Law: carrier migration is direction-typed — the static entry `Natural.transform<F,G,A>` constrains `where F : Natural<F,G>` so the obligation falls on the source and delegates to the `static abstract Transform<A>` member, `CoNatural.transform<F,G,A>` constrains `where F : CoNatural<F,G>` so it falls on the target and delegates to `CoTransform<A>`, and a transformer stack's downward hop is `CoNatural.transform<Outer,Inner,A>` against the upward `Natural.transform<Inner,Outer,A>`; `NaturalMono<F,G> : Natural<F,G>, CoNatural<G,F>` derives the co-direction default from the forward `Transform` with no second body, `NaturalEpi<F,G> : CoNatural<F,G>, Natural<G,F>` derives `Transform` from `CoTransform` with the variance inverted, and `NaturalIso<F,G> : Natural<F,G>, CoNatural<F,G>` is the invariant-both-ways isomorphism rejected wherever one leg loses failure information, because a narrowing such as `FinT<M>` into `OptionT<M>` has no inverse.
- Boundary: host arrays, lists, and trees convert at adapter edges, not as domain flow; rail policy never selects a BCL or numeric replacement.
- Reject: duplicated `Fin`, `Validation`, `Eff`, and `IO` pipelines for one transform.

[CAPABILITY_BY_STACK_ORDER]:
- Law: stack order is a capability decision — a layer needing retry, bracket, fork, or timeout must sit on the unliftable side of any product-shaped state layer; state placed outside the effect boundary makes the outer effect un-bracketable.
- Law: a lift enters the stack at one layer — a layer-lift wraps a value in that layer's constructor, the effect-lift cascade threads a real effect to the IO floor; conflating them substitutes a value where the floor effect was intended.
- Law: the whole composition-time surface — `fork`, `timeout`, `bracket`, `retry` — is one projection from the carrier to its bare effect, so a transformer that cannot project that effect forfeits the entire algebra.
- Law: unlift is a runtime contract — a stack whose innermost monad supplies no IO floor type-checks and then throws on first use, so a constraint set including unlift asserts a legal ordering.
- Reject: hand-recomposing `fork`-then-`await` over the trait's own `await` member, or `await` inside an effect-returning body where an effect lift expresses the boundary; a state layer buried under the effect-capable layer.

```csharp conceptual
public static K<M, Report> Pipeline<M>(Raw raw)
    where M : Stateful<M, Budget>, Readable<M, Config>, MonadUnliftIO<M>, Monad<M> =>
    from limit in Readable.asks<M, Config, double>(static config => config.Limit)
    from spent in Stateful.get<M, Budget>()
    from _     in Stateful.modify<M, Budget>(budget => budget.Charge(raw.Cost))
    from step  in MonadUnliftIO.mapIO<M, Raw, Raw>(
                      static io => io.Timeout(TimeSpan.FromSeconds(2)).Retry(Backoff),
                      Acquire<M>(raw))
    from done  in Readable.local<M, Config, Report>(
                      static config => config.Sandboxed(),
                      Finalize<M>(step, limit, spent))
    select done;
```
