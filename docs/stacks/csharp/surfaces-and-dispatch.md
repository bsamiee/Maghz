# [SURFACES_AND_DISPATCH]

A concern with many features keeps one dense surface, never a family of shallow ones: one entrypoint absorbs every verb, arity, and modality — verbs collapse into a request `[Union]` under one total `Switch` so a new verb breaks every dispatch site instead of growing a sibling, arity collapses into `params ReadOnlySpan<T>` and one carrier, and the discriminant is the value's shape, never a mode flag beside it. Knob sets collapse into policy values that carry their own behavior, and optional context enters as `Option<T>` or one runtime record whose default derives from the policy owner. Seven dispatch forms are selected by where ownership lives — five resolve at the value (state-threaded `Switch`, behavior-on-the-vocabulary-item, frozen table, trait-derived operation family, the keyed declaration that is table, vocabulary, and admission factory at once) and two at the type (the `IObjectFactory<TOwner,TValue,TError>` constraint open over the owner family, the instance-interface floor a foreign assembly implements) — while the carrier stays orthogonal to the form and alone decides accumulate-versus-abort, one `K<F,A>` arrow dispatching `Fin`, `Eff`, `IO`, and `Validation` together. Aspects split at one seam: definition-time weaves below the admission boundary in the generator-owned order, composition-time transformers above it in a `Schedule`-and-rank-driven order that is itself a value. The defect this page refuses is surface spam — sibling `Create`/`Update`/`CreateMany` families, per-arity overload sets, `bool`/`mode`/`batch` knobs, `RunFin`/`RunEff` per-carrier copies, member-less marker interfaces read by `is`, and hand-spelled aspect towers re-written at every call site.

## [01]-[FORM_CHOOSER]

When a concern matches several rows, the most specific wins; the carrier axis is read after the form is fixed.

| [INDEX] | [CONCERN_SIGNATURE]                           | [FORM]                                            | [REJECTED_FORM]                   |
| :-----: | :-------------------------------------------- | :------------------------------------------------ | :-------------------------------- |
|  [01]   | verb family, shared preamble                  | request `[Union]` + total `Switch`                | sibling `Create`/`Update` methods |
|  [02]   | one verb, varying arity                       | `params ReadOnlySpan<T>` absorber                 | per-arity overload family         |
|  [03]   | consumer owns logic, vocabulary owns coverage | state-threaded `Switch`                           | distributed `_`-armed `switch`    |
|  [04]   | vocabulary item is the behavior               | `[UseDelegateFromConstructor]` row                | repeated full-coverage `Switch`   |
|  [05]   | key is a value, result is static data         | `Lazy<FrozenDictionary>` index                    | dictionary restating rows         |
|  [06]   | dependent dispatch loops to a fixpoint        | closed continue-or-done `[Union]` + `repeatWhile` | `Recur`/open recursion/`while`    |
|  [07]   | receiver is foreign, behavior is local        | extension block                                   | wrapper that renames receiver     |
|  [08]   | input shape, not nominal type, discriminates  | structural pattern                                | `is`-chain over open input        |
|  [09]   | one body serving every carrier                | `K<F,A>` trait-constrained arrow                  | `RunFin`/`RunEff` sibling family  |
|  [10]   | admit every present and future owner          | `IObjectFactory<TOwner,TValue,TError>` constraint | per-owner converter copy          |
|  [11]   | foreign assembly implements the strategy      | instance-interface floor + minting factory        | `[Union]` foreign code extends    |
|  [12]   | optional context with identity                | one `Option<ContextRecord>`                       | `T? a, T? b, bool x` flag tail    |

## [02]-[ENTRYPOINT_LAW]

[REQUEST_COLLAPSE]:
- Law: one concern exposes one entrypoint; a verb family is a `[Union]` with one case per verb under one total dispatch.
- Law: each sibling's preamble becomes its case constructor and the shared validation becomes the dispatch prologue.
- Law: full-coverage generated `Switch` is the totality proof; a new case breaks every dispatch site at compile time, never a runtime-silent `_` arm.
- Use: `[Union<T1,...>]` ad-hoc when the request is a positional sum of already-defined payloads extracted by `IsTi`/`AsTi`; regular `[Union]` named cases when cases carry distinct fields and `value is CaseName` extracts.
- Reject: a request-union-shaped success-or-failure carrier; rails own outcome transport.
- Boundary: programs that must be inspected or re-interpreted reify verbs as a closed instruction functor under one interpreter arrow; the request union with total dispatch is the form when they only run.

[SEALED_ADMISSION]:
- Law: a regular `[Union]` seals through reachability — the private owner constructor closes the case family, one hand-written `public static` factory is the validated ingress, the generated `Switch` the sole egress, and `ConversionFromValue = ConversionOperatorsGeneration.None` deletes the implicit-by-default value-to-union conversion that would bypass the factory; `ConstructorAccessModifier`/`FactoryMethodGeneration` are ad-hoc-only knobs and do not exist here.
- Law: `SwitchMapMethodsGeneration.None` deletes the generated dispatch so an extension-block dispatch algebra cannot be bypassed by a second, less-restrictive surface; `SwitchMethods` and `MapMethods` suppress independently.
- Use: a `private partial record` nested in the owning service when construction must scope to one owner; an internal factory opens the whole assembly, not the enclosing type.
- Boundary: input validates once at the factory and behavior is reached once through dispatch; positional cases stay constructible with already-admitted payloads, and construction scopes fully to one owner only in the nested form.

[SURFACE_ATTACHMENT]:
- Law: the module's public surface is the request union plus one dispatch entrypoint attached through an extension block, routing entirely over the public generated dispatch without touching the partial.
- Boundary: `[OverloadResolutionPriority]` steers only members co-declared in one static class; cross-class same-name extensions compare by ordinary betterness regardless of priority.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Request {
    private Request() { }
    public sealed record Open(CodeValue Code) : Request;
    public sealed record Amend(CodeValue Code, int Delta) : Request;
    public sealed record Close(CodeValue Code) : Request;
}

public static class RequestSurface {
    public static Fin<Request> Admit(ReadOnlySpan<char> verb, CodeValue code, int delta) =>
        verb switch {
            "<verb-open>"  => Fin.Succ<Request>(new Request.Open(code)),
            "<verb-amend>" => Fin.Succ<Request>(new Request.Amend(code, delta)),
            "<verb-close>" => Fin.Succ<Request>(new Request.Close(code)),
            _              => Fin.Fail<Request>(new Fault.Bounds($"<unknown-verb:{verb}>")),
        };

    extension(Request request) {
        public Fin<Receipt> Dispatch(Ledger ledger) => request.Switch(
            state: ledger,
            open:  static (l, o) => l.Open(o.Code),
            amend: static (l, a) => l.Amend(a.Code, a.Delta),
            close: static (l, c) => l.Close(c.Code));
    }
}
```

## [03]-[MODAL_ARITY]

[ARITY_ABSORPTION]:
- Law: singular, multi-item, and empty call sites collapse into one `params ReadOnlySpan<T>` signature; the compiler promotes constant primitive elements to the data segment and stack-allocates dynamic literals, so the allocation-free property is the target type's, not the call's.
- Law: a `params ReadOnlySpan<T>` parameter is implicitly `scoped`; the buffer cannot escape without `[UnscopedRef]`, and an override must restate `params` to preserve the bound.
- Use: a collection-expression builder on the carrier so `[a, b, c]` routes through one type-level span-fed builder, making arity a property of the literal.
- Reject: two collection-shaped entrypoints whose element types differ by a reference conversion — a covariant span beside a covariant array is a hard ambiguity; one span at the most-derived element type is the only ambiguity-free shape.
- Boundary: a zero-argument-capable entrypoint owns exactly one `params` element type; a second element-typed `params` overload forecloses the empty call.

[MODALITY_FOLD]:
- Law: singular, plural-preserving, and plural-reducing are call shapes over one arm — singular is `Map`/`Bind`, plural-preserving is `Traverse`/`Sequence` with container shape intact, plural-reducing is monoid-keyed `Fold`/`FoldMap` where the `Monoid` is the policy value selecting the reduction, total over the empty spread because the monoid supplies the identity.
- Law: `.TraverseM(f).As()` threads the carrier's short-circuit reusing the singular arm verbatim, and applicative `.Traverse(f).As()` over a `Validation`-shaped carrier is the accumulating sibling — same arm, the carrier alone switching the policy, and the `.As()` re-anchor is mandatory because the trait returns the erased `K<F,A>`.
- Use: the Prelude `foldWhile(f, predicate, seed, ta)`/`foldUntil(...)` whose predicate reads `(State, Value)` for the bounded-batch entrypoint with no count parameter, `foldWhileM`/`foldUntilM` when each step runs in the carrier and the halt predicate reads the element alone; `oneOf` over an `Alternative` carrier for first-success, total over the empty spread because `Empty` is the identity.
- Reject: a batch flag, a mode flag, or a count beside a span whose `Length` already answers it; counts and modes derive from `span.Length` or the dispatched case, never the signature; `Aggregate` with a mutable seed where `Fold` over the monoid fuses the reduction.
- Boundary: after traversal the container is uniformly in the carrier, never mixed admitted-and-raw, which keeps the next entrypoint's discriminant recoverable from shape alone.

```csharp conceptual
public static class BatchSurface {
    public static Fin<Iterable<Receipt>> Run(Ledger ledger, params ReadOnlySpan<Request> requests) =>
        Iterable<Request>.FromSpan(requests)
            .TraverseM(request => request.Dispatch(ledger))
            .As();

    public static Validation<Error, Tally> Reduce(Ledger ledger, params ReadOnlySpan<Request> requests) =>
        Iterable<Request>.FromSpan(requests)
            .Traverse(request => request.Dispatch(ledger).ToValidation().Map(static r => r.Tally))
            .As()
            .Map(static tallies => tallies.Fold(Tally.Empty, static (sum, next) => sum + next));
}
```

## [04]-[PARAMETER_ALGEBRA]

[POLICY_VALUES]:
- Law: a policy parameter arrives pre-constructed and carries its own behavior; the entrypoint invokes the value it was handed, and no `if`/`switch` reconstructs at dispatch what the value already encodes.
- Law: a stateless union case (`T1IsStateless = true`) is the shape for configuration-free policy entries; wrapping it in `Option<T>` stacks a second optionality on a discriminant that already models absence.
- Use: a frozen policy table whose projection comparer keyed on the request's discriminant declares which dimension governs selection, collapsing payload differences onto one row.
- Reject: a boolean parameter selecting between two bodies; a behavioral near-twin chosen by flag rather than by the value that encodes the boundary behavior.

[OPTIONAL_CONTEXT]:
- Law: `Option<T>` is the single optional-parameter form; declaration is `Option<T> x = default`, consumption is `IfNone(canonical)` where the canonical fallback is the policy owner's row, so the default derives once.
- Law: a nullable flag tail (`T? a = null, T? b = null, bool x = false`) fragments one context into parallel parameters; the collapse is one `Option<ContextRecord>` carrying the override bundle, with `T? ctx = null` the boundary-only spelling projected to `Option<T>` at admission.
- Law: skipping an expensive alternative is overload selection by the argument's static type — a `Memo` right branch binds the lazy `Choose`, a materialized value binds the eager one — never a flag.
- Boundary: a capability orthogonal to the discriminant — a cancellation token, an environment record — describes how work runs, not which case it is, and rides the carrier, never the signature.

[SUPPLIED_VERSUS_OMITTED]:
- Law: `Argument<T>` is the `readonly ref struct` carrying `Value` + `IsSet` that distinguishes "supplied a value equal to the default" from "omitted" — the distinction `Option<T>` cannot make; confined to one synchronous frame, never across `await`.
- Use: `Argument<TResult>` only on `MapPartially`'s per-case slots and on bespoke factory overloads; the generated `ValidateFactoryArguments` takes `ref T` and `Validate` takes raw `TValue?`, so `Argument<T>` in either generated seam is a compile-time mismatch.
- Boundary: a growing optional tail loses resolution to a tighter sibling whose every parameter received an argument, silently redirecting call sites; collapsing the tail to one `Option<ContextRecord>` deletes the parallel candidate.

[KNOB_TEST]:
- Law: the knob test is removal — delete the parameter, and if no information is lost that the value cannot reconstruct, the parameter was a knob and the value already discriminates.
- Reject: a timeout or deadline as an entrypoint parameter; the bound is an effect-layer aspect injected after dispatch, and the signature never grows a token tail for it.

```csharp conceptual
public sealed record Context(int Ceiling);

public sealed record Policy(Context Canonical, Func<Input, Context, Fin<Receipt>> Step) {
    public static readonly Policy Strict = new(
        new Context(Ceiling: 1),
        static (input, context) => input.Score <= context.Ceiling
            ? Fin.Succ(Receipt.Empty)
            : Fin.Fail<Receipt>(new Fault.Bounds($"<over:{input.Score}/{context.Ceiling}>")));

    public static readonly Policy Lenient = new(
        Strict.Canonical with { Ceiling = 8 },
        static (input, _) => Fin.Succ(Receipt.Degraded));
}

public static class PolicySurface {
    public static Fin<Receipt> Run(Policy policy, Input input, Option<Context> context = default) =>
        policy.Step(input, context.IfNone(policy.Canonical));
}
```

## [05]-[DISPATCH_FORMS]

[FORM_SELECTION]:
- Law: the five value-level forms are selected by where ownership lives — the chooser's ownership signatures are the selection law — and when two forms both fit, the one whose owner already holds the exhaustiveness obligation wins; the two type-level forms are `[07]`'s, selected when dispatch resolves at the type rather than the value.
- Reject: a frozen table restating a vocabulary's own delegate rows — a duplicate-entry burden with a silent missed-new-item failure; structural dispatch over a closed family, trading compile-time totality for a silent `_`.
- Boundary: mixing forms at one site signals an unresolved ownership boundary, except the two valid compositions — a `Switch` arm probing a frozen table is dispatch plus data retrieval; an extension block owns module-to-domain translation while its inner `Switch` owns per-case projection.

[TRAIT_DERIVATION]:
- Law: a carrier trait declares the smallest closed abstract core and derives the operation family as static-virtual defaults — two predicate-gated folds derive roughly fifty receiver operations, lift-plus-apply derives the effectful-sequencing surface, empty-plus-choose derives the repetition suite.
- Law: satisfying a trait costs only its abstract core; the derivation is the executable specification an override is verified against, and a carrier with no faster primitive correctly ships zero overrides.
- Use: an override only where a structurally cheaper primitive exists — an O(1) size field overrides count and inherits the other forty-nine — never altering the law the default encodes, only its cost.
- Boundary: the deferred-second-argument overloads on `choose` and `apply` are mandatory infrastructure; a carrier omitting the lazy overload silently loses the entire derived repetition surface.

[KEY_ADMISSION]:
- Law: one generated keyed declaration is three dispatch forms at once — the key-to-case lookup table, the all-items sweep, and the boundary-admission factory are static-abstract views of one type, so "table or vocabulary or admission" dissolves and a call site reaches for whichever member its problem names.
- Law: the generated `Validate(TKey?, IFormatProvider?, out TItem)` is the one-hop bridge from raw external key to dispatch-ready item — open on the way in, a typed error or a vocabulary item on the way out, the subsequent `Switch` compile-time-total.
- Use: the span-keyed `Validate(ReadOnlySpan<char>, ...)` overload so protocol text admits and dispatches without materializing a string.
- Boundary: the comparer accessor is the single arbiter of key equality everywhere, so every frozen table keyed on the owner resolves the same comparer and no call site supplies a divergent one.

```csharp conceptual
[SmartEnum<string>]
[ValidationError<Fault>]
public sealed partial class Marker {
    public static readonly Marker MarkA = new("<key-a>");
    public static readonly Marker MarkB = new("<key-b>");
}

public static class MarkerBoundary {
    public static Fin<int> Admit(ReadOnlySpan<char> raw, Input input) =>
        Marker.Validate(raw, null, out var marker) is { } fault
            ? Fin.Fail<int>(fault)
            : Fin.Succ(marker!.Switch(state: input,
                markA: static (value, _) => value.Score,
                markB: static (value, _) => value.Score * 2));

    public static ImmutableArray<string> Advertised() => [.. Marker.Items.Select(static item => item.Key)];
    public static Option<Marker> Probe(string key) => Marker.TryGet(key, out var marker) ? Optional(marker) : None;
}
```

## [06]-[CARRIER_POLYMORPHIC_DISPATCH]

[ONE_CARRIER_SURFACE]:
- Law: the form selects which arm runs, the carrier the arms return selects how results combine — orthogonal axes; an arm returning `K<F,A>` makes one entrypoint the `Fin`, `Eff`, `IO`, and `Validation` dispatcher, and the per-carrier sibling family is the rejected form.
- Law: the trait stack is the precise capability contract — `Monad` binds, `Fallible<E,F>` fails and catches, `Choice` falls back, `Alternative` adds `Empty`, `Traversable` sweeps — and over-constraining beyond what the body uses is dead surface narrowing the admitted carrier set for nothing.
- Use: `.As()` to recover the concrete carrier exactly once at the materialization boundary; capabilities ride the carrier through `Has`/`Stateful` accessors, never a trailing dependency tail.
- Boundary: pinning `Fallible<E,M>` to a domain error union makes the failure surface a closed family, and the named catch family generated once against the trait applies to every fallible carrier via `|` with no per-monad wiring.

[INDEPENDENT_JOIN]:
- Law: independent arms combine applicatively, dependent steps bind monadically, and the choice is load-bearing — a `Bind` chain over independent arms silently discards all failures after the first.
- Law: the tuple join `(K<F,A>, ..., K<F,J>).Apply(func)` runs each slot under the carrier's `Apply` — an accumulating carrier reports the union of failures, an effect carrier short-circuits; same call site, same join, the carrier alone switching semantics.
- Reject: a branch inside the join — its only legitimate content is total construction over already-dispatched values; a branch is a fourth dispatch smuggled into combination and lifts into its own arm.
- Boundary: all slots share one `F` by construction, so failure semantics decide once; an expensive slot enters as `Memo` and a short-circuiting carrier leaves it unforced.

[ITERATIVE_DISPATCH]:
- Law: looping dependent dispatch is a closed continue-or-done `[Union]` step driven by `repeatWhile` — the step returns `Advance` or one terminal case distinguishing the settled fixpoint from each divergence cause, the `Func<Step, bool>` predicate halts the moment the advanced state leaves the `Advance` arm, and the rail-owned driver carries the loop with no growing stack and no mutable index.
- Law: the iterative driver is the rail page's — `repeatWhile`/`RepeatWhile` over `MonadUnliftIO<M>` repeats a state-advancing effect until the advanced result fails the predicate, the optional `Schedule` bounding attempts — so this page chooses only the continue-or-done shape the step dispatches on and threads the advance through `Stateful.modify` plus `Stateful.get`, never a hand-spelled recursion or a `count` the terminal case already answers.
- Law: the state advance is one total `Switch` over the closed step family, so the same arms run under every `Stateful`-over-effect stack the carrier admits and a new divergence cause is one terminal case that breaks the terminal projection at compile time.
- Boundary: carrier changes are one structure-preserving `Natural.transform` arrow, never a match-and-rebuild bridge; mid-pipeline concretization defeats the polymorphism.

```csharp conceptual
public static class JoinSurface {
    public static K<F, Composite> Assemble<F>(Source source, Band band, Tag tag)
        where F : Applicative<F> =>
        (source.Switch(state: unit,
            primary:   static (_, p) => F.Pure(p.Code),
            secondary: static (_, s) => F.Pure(s.Code)),
         band.Switch(state: unit,
            upper: static (_, _) => F.Pure(2),
            lower: static (_, _) => F.Pure(1)),
         tag.Switch(state: unit,
            declared: static (_, d) => F.Pure(d.Key),
            derived:  static (_, d) => F.Pure($"{d.Source}:{d.Ordinal}")))
        .Apply(static (code, rank, key) => new Composite(code, rank, key));
}

[Union]
public abstract partial record Step {
    public sealed record Advance(int Seed) : Step;
    public sealed record Settled(int Fixpoint) : Step;
    public sealed record Diverged(int Cause) : Step;
}

public static class IterativeSurface {
    public static K<M, Fin<int>> Driven<M>(int seed, int ceiling)
        where M : Stateful<M, Step>, MonadUnliftIO<M> =>
        repeatWhile(
            Stateful.modify<M, Step>(state => state.Switch(
                advance:  s => Advanced(s, ceiling),
                settled:  static s => (Step)s,
                diverged: static d => d)).Bind(static _ => Stateful.get<M, Step>()),
            static step => step is Step.Advance)
        .Map(static step => step.Switch(
            advance:  static _ => Fin.Fail<int>(new Fault.Bounds("<unterminated>")),
            settled:  static s => Fin.Succ(s.Fixpoint),
            diverged: static d => Fin.Fail<int>(new Fault.Bounds($"<diverged:{d.Cause}>"))));

    static Step Advanced(Step.Advance a, int ceiling) =>
        a.Seed <= 1 ? new Step.Settled(a.Seed) : Next(a.Seed) switch {
            var folded when folded >= ceiling => new Step.Diverged(folded),
            var folded                        => new Step.Advance(folded),
        };

    static int Next(int seed) => (seed & 1) == 0 ? seed >> 1 : (3 * seed + 1) >> 1;
}
```

## [07]-[TYPE_LEVEL_DISPATCH]

[OPEN_OWNER_BOUNDARY]:
- Law: the self-constrained factory contract — `where TOwner : IObjectFactory<TOwner, TValue, TError>`, sole member a static abstract `Validate` — is the inversion of case dispatch: `Switch` is closed over one owner's cases, the constrained generic is open over the unbounded family of all owners, resolved by the JIT with no instance, no vtable, no reflection.
- Law: the error vocabulary stays owner-chosen because `TError` carries its own static abstract `Create`; bounding `TError` by the shared fault base keeps every owner's precise faults rail-liftable with no translation hop.
- Use: a span-keyed instantiation — the span is the `TValue` under `allows ref struct` — so protocol text decodes into the closed vocabulary with zero heap traffic on both legs.
- Reject: one shallow converter per owner; one deep parameterized surface owns conversion for the whole owner set.

[REACH_LIMIT]:
- Law: an unresolved static abstract member is not a first-class value — no open delegate, no method group, no expression tree — so type-level static dispatch serves boundaries whose owner is resolved at compile time at the call site.
- Use: the generated static-abstract metadata surface for runtime-discovered owners, folded by a generic codec over the metadata's own generated dispatch, keeping the runtime-discovered case reflection-free.
- Boundary: choosing the static-virtual form for runtime discovery reintroduces reflection through closed-generic invocation — the exact cost the contract exists to delete.

[OPEN_FLOOR_DISPATCH]:
- Law: when a foreign assembly supplies the implementation, the seam inverts again — an instance-interface floor (`IProjection<TIn,TOut>`, one member returning the rail) is the open extension point, a minting factory selects the concrete the consumer never names, and one polymorphic operation dispatches over the floor — distinct from the closed family the owner exhaustively `Switch`es and never publishes.
- Law: the discriminant between the two seams is direction of extension — an open point others plug into (a constraint, a projection, a store) is an instance-interface floor returning `Fin<T>` or `Validation<Error,T>`, a closed family the owner controls is a `[Union]`/`[SmartEnum]` + total `Switch`; an interface over the family the owner closes forfeits `Switch` totality, and a `[Union]` a foreign assembly must extend forfeits the seal.
- Law: the open constraint set and the owner's closed `Switch` co-exist on one owner — the shape switches internally, an `IConstraint<T>` floor folds independent violations at the edge — so a foreign-supplied constraint is the accumulating-`Validation` floor and never a case the owner closes; the fold mechanic and its monoid are the rail page's, composed here as the floor's consequence.
- Boundary: the floor's lifetime, minting, and the cross-stratum case — N sibling owners aligning through one floor hosted on the lowest shared stratum, each implementing it against its own shapes with zero peer references — are the boundary page's; this page owns only that the floor is the dispatch and the concrete is `internal` and swappable.
- Reject: a member-less marker read by `is` or reflection where a generic bound `where T : IFloor` or a generated conformance carries the capability; an instance default-interface-method where `static virtual` derives the default from a minimal core.

```csharp conceptual
public static class Boundary {
    public static Fin<TOwner> Admit<TOwner, TValue, TError>(TValue value, IFormatProvider? culture = null)
        where TOwner : IObjectFactory<TOwner, TValue, TError>
        where TValue : notnull, allows ref struct
        where TError : Expected, IValidationError<TError> =>
        TOwner.Validate(value, culture, out var item) is { } fault
            ? Fin.Fail<TOwner>(fault)
            : Fin.Succ(item!);

    public static Fin<TOwner> AdmitText<TOwner, TError>(ReadOnlySpan<char> text)
        where TOwner : IObjectFactory<TOwner, ReadOnlySpan<char>, TError>
        where TError : Expected, IValidationError<TError> =>
        Admit<TOwner, ReadOnlySpan<char>, TError>(text);
}

public interface IProjection<in TIn, TOut> {
    Fin<TOut> Project(TIn source);
}

file sealed record Widened(int Rank, string Tag);

file sealed class WidenProjection(int span) : IProjection<int, Widened> {
    public Fin<Widened> Project(int source) =>
        source <= span ? Fin.Succ(new Widened(source * span, "<widened>")) : Fin.Fail<Widened>(new Fault.Bounds($"<over:{source}>"));
}

public static class FloorDispatch {
    public static IProjection<int, Widened> Minted(int span) => new WidenProjection(span);

    public static Fin<Widened> Refined(IProjection<int, Widened> floor, int seed) =>
        floor.Project(seed).Bind(first => floor.Project(first.Rank));
}
```

## [08]-[ASPECTS]

[WEAVE_TAXONOMY]:
- Law: a definition-time aspect is a property of the type — declared by attribute, woven by the generator, present at every call site; a composition-time aspect is a property of one call site — attached as operators in the pipeline it modifies.
- Law: the classification test is per-site variance — a concern present at every use weaves at definition, a concern that varies per site composes at the site.
- Boundary: the two weaves meet at the one-expression hop this page's admission snippets show — a generated factory's typed fault lifting into the carrier; admission rules hoisted above that hop or effect policy sunk below it stop being recoverable from their declarations.

[CONSTRUCTION_ADVICE]:
- Law: the generated factory threads advice in a fixed generator-owned order — absence guards, error-slot init, the `ValidateFactoryArguments` normalizer, construction gated on a null error, the constructor hook, post-init — and the author opts into slots, never reorders.
- Law: a non-void `ValidateFactoryArguments` return threads into post-init as a typed side channel — computation done once during validation handed forward with no field, no closure, no second pass.
- Reject: rejection logic in the constructor hook or null/blank guards in the factory hook — the weave order fixes absence below both, so either placement is dead code, and a throwing hook breaks the rail bridge above the seam.

[STACKING_ORDER]:
- Law: composition-time aspects stack in operator order, and the same two aspects in two orders are two policies — retry around a bracket re-runs acquire-use-release per attempt, a bracket around a retry acquires once and retries only the use.
- Law: a named catch composes via `|` as handler wrapping, left-associative — inner handlers see errors first, so a broad predicate before a narrow one shadows it with no diagnostic; the finalizer is a transparent pass-through that runs on both exits, so a catch after it still fires.
- Law: generated dispatch collapses to a value before any transformer runs, so per-case policy is unspellable by wrapping the dispatch — each arm must produce its own policy-wrapped carrier, the granularity fixed by where the carrier is introduced.
- Reject: a constrained operator on a carrier defined anywhere but an extension block.
- Boundary: `extension<E, F, A>(K<F, A> _) where F : Fallible<E, F>` is the sole mechanism granting a local aspect an operator surface.

[PRECEDENCE_TABLE]:
- Law: when three or more composition-time aspects recur over one core, their order is a value — a closed `Concern` `[Union]` resolving each case to its transformer plus a `WeaveName` vocabulary whose `Rank` column is the canonical order, folded ascending so the lowest rank wraps innermost — never a fixed tower re-spelled at every owner, because the same stack written by hand at each call site is the inline-repeated-concern defect.
- Law: one correctness constraint fixes the floor and the rank column declares the rest — recovery is rank 0 so a retry above it re-drives the already-recovered body, retry is the highest rank so a transient re-runs the whole observed core, and the relative rank of bracket and catch is the policy the column states once; a new aspect is one `[Union]` case plus one `WeaveName` row with every call site untouched.
- Law: every transformer satisfies one shape — `Func<IO<Receipt>, IO<Receipt>>` — so the rank-ordered fold keeps the carrier and the rail intact through an arbitrary-depth stack, and the rank lives on the vocabulary item rather than a bent comparer so the order is recoverable from the declaration alone.
- Reject: the same bracket-retry-catch tower hand-spelled as sibling methods; a caller-supplied order where the `WeaveName` rank column already fixes it; a transformer typed `Func<IO<object>, IO<object>>` that erases the result.

```csharp conceptual
[SmartEnum]
public sealed partial class WeaveName {
    public static readonly WeaveName Recover = new(rank: 0);
    public static readonly WeaveName Bracket = new(rank: 1);
    public static readonly WeaveName Retry   = new(rank: 2);

    public int Rank { get; }
}

[Union]
public abstract partial record Concern {
    public sealed record Recovering(CatchM<Error, IO, Receipt> Handler) : Concern;
    public sealed record Bracketing(Func<Resource, IO<Receipt>> Use, Func<Resource, IO<Unit>> Fin) : Concern;
    public sealed record Retrying(Schedule Backoff) : Concern;

    public (WeaveName At, Func<IO<Receipt>, IO<Receipt>> Weave) Ranked(IO<Resource> acquire) => Switch(
        state: acquire,
        recovering: static (_, r) => (WeaveName.Recover, core => (core | r.Handler).As()),
        bracketing: static (a, b) => (WeaveName.Bracket, _ => a.Bracket(Use: b.Use, Fin: b.Fin)),
        retrying:   static (_, r) => (WeaveName.Retry, core => core.Retry(r.Backoff)));
}

public static class AspectFold {
    public static IO<Receipt> Woven(IO<Resource> acquire, IO<Receipt> core, params ReadOnlySpan<Concern> concerns) =>
        toSeq(Iterable<Concern>.FromSpan(concerns).Map(concern => concern.Ranked(acquire)).OrderBy(static row => row.At.Rank))
            .Fold(core, static (wrapped, row) => row.Weave(wrapped));
}
```
