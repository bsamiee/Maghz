# [CSHARP_SHAPES]

Every concept takes exactly one owner, and five discriminants select it before any attribute is written: admission (raw material crossing a trust boundary), identity regime (key, structural, case, or reference), variant arity (one shape or N alternatives), payload timing (case data fixed at declaration or constructed per occurrence), and openness (closed vocabulary or foreign extension). The selection fixes where change detonates, what equality means, and which capabilities derive — every misplaced shape traces to one mis-answered discriminant.

## [01]-[OWNER_CHOOSER]

When a concept matches several signatures, the most specific row wins.

| [INDEX] | [CONCEPT_SIGNATURE]                             | [OWNER]                            | [IDENTITY]      |
| :-----: | :---------------------------------------------- | :--------------------------------- | :-------------- |
|  [01]   | invariant-bearing scalar                        | `[ValueObject<TKey>]`              | key             |
|  [02]   | N fields, one concept, no discriminator         | `[ComplexValueObject]`             | structural      |
|  [03]   | bounded vocabulary, wire-keyed identity         | `[SmartEnum<TKey>]`                | key             |
|  [04]   | bounded vocabulary, process-local behavior      | `[SmartEnum]` keyless              | reference       |
|  [05]   | closed alternatives, per-occurrence payload     | `[Union]`                          | case            |
|  [06]   | one value over 2-5 unrelated types              | `[Union<T1,...>]` ad-hoc           | slot then value |
|  [07]   | interior product, no invariant, no admission    | record or readonly record struct   | structural      |
|  [08]   | combinable capability set                       | vocabulary items in a frozen set   | key             |
|  [09]   | runtime-sourced vocabulary                      | keyed owner plus frozen registry   | key             |
|  [10]   | cross-product or externally sourced policy key  | frozen table                       | composite key   |
|  [11]   | foreign wire enum, ABI bits, or kernel ordinal  | language enum at the seam only     | ordinal         |
|  [12]   | foreign code must add cases                     | manual interface or hierarchy      | declared        |
|  [13]   | property-graph relation over a foreign taxonomy | neutral verb `[Union]` + `Generic` | case            |
|  [14]   | property-graph node over an entity family       | keyed `[Union]` over the entities  | case then key   |

## [02]-[DECISION_LAW]

[OWNER_SELECTION]:
- `SelectOwner(concept)`: choose by singleton-versus-instance, field coverage, relatedness, invariant, admission boundary, reads-of-evidence per write, payload timing, and openness; high-churn intermediate values stay plain until the seam where evidence becomes domain material.
- `UseSmartEnum(vocabulary)`: fixed named instances, identity dispatch, behavior columns, key lookup, and declared growth absorption.
- `UseUnion(family)`: per-occurrence payload, case dispatch, stored call modality, transport carrier under `SwitchMapMethodsGeneration.None`, and ad-hoc members meaningful outside the family.
- `UseComplexValueObject(product)`: require every field under every value; move discriminator-dependent fields to `UseUnion`; keep non-admitting, no-invariant, default-comparer products as `record`.

[COLLAPSE_FUNCTIONS]:
- `CollapseFamily(family)`: keep generated closure only when the owner absorbs admission, identity, dispatch, policy, boundary projection, or stored modality; delete sibling regrowth, nullable payload bags, enum-dictionary pairs, protocol shadows, owner wrappers, and overload-only modality.
- `MergeSamePayload(cases)`: collapse only passive, non-generic, non-fault cases with identical semantics; preserve marker, behavior, fault, and named-semantic cases.
- `ReplaceFlags(capability)`: model combinable capability as vocabulary items in a frozen set; keep behavior in columns, membership as set algebra, and policy as a fold.
- `UseLanguageEnum(seam)`: permit only foreign wire enum, ABI bit layout, or measured-kernel ordinal; re-close at seam conversion.

[BEHAVIOR_FUNCTIONS]:
- `PlaceBehavior(selector)`: use generated `Switch` for call-site variation, behavior columns or case members for family-owned policy, `Items`-derived frozen indexes for single-axis lookup, and generated-owner tables only for cross-products, startup-admitted external policy, or outside-family keys.
- `RejectExternalDictionary(key)`: collapse item-keyed dictionaries, sibling lookup helpers, and repeated full-coverage `Switch` arms to behavior columns, generated dispatch, or one `Items`-derived frozen index; cross-product tables survive only with generated-owner keys and startup totality against the `Items` product.

[CHANGE_FUNCTIONS]:
- `PlaceGrowthCost(owner)`: send new union cases to exhaustive `Switch`, smart-enum items to constructors, complex members to factories, and key migrations to conversion and wire seams.
- `TuneGrowthAbsorption(owner)`: let columns under `SwitchMapMethodsGeneration.None` absorb item growth; let generated `Switch` push additions to consumers.
- `TightenInvariant(owner)`: treat narrower factories as data migration plus tests because compile signal is zero.

[EXEMPTION_FUNCTIONS]:
- `UseManualFamily(axis)`: hand-roll only for foreign case extension, interface-required owners, unliftable generic payloads, ad-hoc arity past five, or runtime-sourced vocabulary admitted into keyed owner plus frozen registry.
- `ExtendForeignBase(vocabulary)`: keep generated vocabulary; thread key first and base parameters last; reject host base class as manual case-extension pressure.

[COMPOSITION_FUNCTIONS]:
- `ComposeOwners(graph)`: nest owners without revalidation; preserve admission, equality, comparer policy, default-safety, and totality; project wire shape through one object factory instead of flattening.
- `StackIdentity(owner)`: keep structural, key, case, equality, and ordering regimes local; declare identity-without-order at the layer that owns it.
- `KeyByGeneratedOwner(owner)`: use full generated-owner keying only across assembly boundaries; in same-compilation composition, carry raw key plus vocabulary owner and one two-hop admission expression.

## [03]-[VALUE_OBJECTS]

[ADMISSION_FACTORY]:
- Use: `Validate` as the admission factory; `Create` throws flattened fault text, `TryCreate` downgrades evidence, and culture-sensitive admission stays on `Validate`.
- Law: `ValidateFactoryArguments` canonicalizes by `ref` before storage and owns fresh-input rejection; `ValidateConstructorArguments` runs on every construction path, including rehydration, and owns invariant-of-record drift.
- Law: non-`void` hook returns carry admission evidence into `FactoryPostInit` only on genuine admission; rehydrated material must re-derive evidence-backed state.
- Reject: per-call-site error translation; static `Create(string)` receives rendered text only, raw-value evidence captures at the bridge, and the dual-contract fault family deletes translation hops.

[KEY_AND_IDENTITY_POLICY]:
- Law: the raw key stays private except conversion and explicit-interface egress; consumers compare and dispatch on the owner, and key-type migration breaks at the boundary.
- Law: comparer policy is a type argument; `IEqualityComparerAccessor<T>` and `IComparerAccessor<T>` swing equality, hashing, ordering, relational operators, and `CompareTo` together, with comparers cached in `static readonly` fields.
- Law: string keys default to ordinal-ignore-case across generated surfaces but never inherit policy; every string-bearing layer declares one accessor type, and divergence is the defect.
- Accept: `[MemberEqualityComparer<...>]` makes complex-owner equality opt-in; unmarked members remain materialized but leave equality, hashing, and diagnostic text.
- Boundary: collection members keep reference identity unless a sequence comparer accessor owns that member.

```csharp conceptual
public sealed class FieldKeyPolicy : IEqualityComparerAccessor<string>, IComparerAccessor<string> {
    private static readonly StringComparer Policy = StringComparer.OrdinalIgnoreCase;

    public static IEqualityComparer<string> EqualityComparer => Policy;

    public static IComparer<string> Comparer => Policy;
}

[ValueObject<string>(
    ComparisonOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads,
    EqualityComparisonOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads)]
[KeyMemberEqualityComparer<FieldKeyPolicy, string>]
[KeyMemberComparer<FieldKeyPolicy, string>]
public readonly partial struct FieldKey;

public static class FieldRanks {
    public static ImmutableSortedDictionary<FieldKey, int> From(string rawBound, IEnumerable<FieldKey> keys) =>
        keys.Where(key => key > rawBound).Distinct().Order().Select(static (key, rank) => (key, rank))
            .ToImmutableSortedDictionary(static row => row.key, static row => row.rank);
}
```

[OPERATOR_ALGEBRA]:
- Law: operator axes are algebra grants; enabled axes declare closure, generated operators stay homogeneous, and cross-dimension operations are hand-written against the foreign result type.
- Law: operator bodies re-enter admission through the throwing `Create` factory; `checked` adds key-math overflow trapping, so the call-site context selects the failure species.
- Law: no identity element is synthesized; seeds, zeros, bounds, and units are admitted values, `INumber<T>` kernels never see owners, and exact binary operator interfaces are the owner-compatible constraint form.
- Law: comparison grants are monotone; ordering accessors can synthesize comparison past key algebra, equality generation coerces upward, and impossible key axes emit nothing.
- Boundary: key-typed overloads accept unadmitted raw operands under owner comparer policy; narrow integral keys compute wide, narrow, and re-admit unchecked, while `checked` throws before narrowing.

```csharp conceptual
[ValueObject<double>(
    MultiplyOperators = OperatorsGeneration.None,
    DivisionOperators = OperatorsGeneration.None,
    ComparisonOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads,
    EqualityComparisonOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads)]
public readonly partial struct Shape {
    public static RefinedShape operator *(Shape left, Shape right) => RefinedShape.Create((double)left * (double)right);
}

[ValueObject<double>(MultiplyOperators = OperatorsGeneration.None, DivisionOperators = OperatorsGeneration.None)]
public readonly partial struct RefinedShape;

public static class ShapeOps {
    public static TQuantity Total<TQuantity>(IEnumerable<TQuantity> parts, TQuantity seed)
        where TQuantity : IAdditionOperators<TQuantity, TQuantity, TQuantity> =>
        parts.Aggregate(seed, static (sum, next) => sum + next);

    public static bool Exceeds(Shape shape, double rawBound) => shape > rawBound;
}
```

[VALUE_TRAIT_AXES]:
- Law: the LanguageExt `LanguageExt.Traits.Domain` value traits are the algebraic axis layer over generated admission, each a static-abstract self-constrained interface granting a fixed BCL operator-interface set the axis selects — `VectorSpace<TSelf,TScalar>` grants `IAdditionOperators<TSelf,TSelf,TSelf>`, `ISubtractionOperators<TSelf,TSelf,TSelf>`, scalar `IMultiplyOperators<TSelf,TScalar,TSelf>`/`IDivisionOperators<TSelf,TScalar,TSelf>`, and `IUnaryNegationOperators<TSelf,TSelf>`; `Amount<TSelf,TScalar>` is that fragment plus `IComparable<TSelf>` and `IComparisonOperators<TSelf,TSelf,bool>` ordering; `Locus<TSelf,TDist,TScalarDist>` is affine position over `where TDist : Amount<TDist,TScalarDist>`, granting `IAdditionOperators<TSelf,TDist,TSelf>`, `ISubtractionOperators<TSelf,TSelf,TDist>`, `IAdditiveIdentity<TSelf,TSelf>`, and negation but never `TSelf+TSelf`.
- Law: every axis inherits `DomainType<TSelf,TRepr>`, whose `static abstract Fin<TSelf> From(TRepr)` and instance `TRepr To()` are the trait's own admission and egress members — the generator emits neither (Thinktecture carries no LanguageExt reference), so the bridge is one expression each: `From` re-anchors the generated `Validate` so the trait's admission and the canonical `Validate` are one rule, not two, and `To()` returns the key the owner already holds; the inherited `static virtual FromUnsafe` rides `From().ThrowIfFail()` untouched. Re-validating inside `From` rather than delegating to `Validate` is the rejected second construction path.
- Law: the bridge currency forces the fault owner — the default `Thinktecture.ValidationError` is not a LanguageExt `Error`, so `Fin.Fail` refuses it and `From` cannot type-check until `[ValidationError<Fault>]` makes the generated `Validate` return the `[FAULT_FAMILIES]` `Fault` (an `Expected` subtype); the value-trait axis layer therefore composes that one fault family as its admission currency, never a second error type minted for the bridge.
- Law: position safety is two structural denials, not a guard — the `Locus` interface declares no `IAdditionOperators<TSelf,TSelf,TSelf>`, so position-plus-position resolves no operator, and the owner's `OperatorsGeneration.None` plus explicit `ConversionToKeyMemberType` deny the implicit key egress that would otherwise fold two positions to scalar key arithmetic and re-admit; both denials are compile failures, neither a runtime check.
- Law: an algorithm binds the weakest axis it consumes — a `VectorSpace` routine rejects a `Locus` position at the constraint because position is not in the vector-space fragment, ordered and affine reach are the cost of widening to `Amount` and `Locus`, and the unconsumed axis stays unreachable from the signature.

```csharp conceptual
[ValueObject<double>(
    MultiplyOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads,
    DivisionOperators = OperatorsGeneration.DefaultWithKeyTypeOverloads)]
[ValidationError<Fault>]
public readonly partial struct Offset : Amount<Offset, double> {
    public static Fin<Offset> From(double repr) => Validate(repr, null, out var value) is { } fault ? Fin.Fail<Offset>(fault) : value;
    public double To() => (double)this;
    public static Offset operator -(Offset value) => Create(-(double)value);
}

[ValueObject<double>(
    AdditionOperators = OperatorsGeneration.None,
    SubtractionOperators = OperatorsGeneration.None,
    MultiplyOperators = OperatorsGeneration.None,
    DivisionOperators = OperatorsGeneration.None,
    ConversionToKeyMemberType = ConversionOperatorsGeneration.Explicit)]
[ValidationError<Fault>]
public readonly partial struct Station : Locus<Station, Offset, double> {
    public static Fin<Station> From(double repr) => Validate(repr, null, out var value) is { } fault ? Fin.Fail<Station>(fault) : value;
    public double To() => (double)this;
    public static Station AdditiveIdentity => Create(0d);
    public static Offset operator -(Station head, Station tail) => Offset.Create((double)head - (double)tail);
    public static Station operator +(Station origin, Offset delta) => Create((double)origin + (double)delta);
    public static Station operator -(Station value) => Create(-(double)value);
}

public static class AxisAlgebra {
    public static T Lerp<T>(T from, T to, double t) where T : VectorSpace<T, double> => from + (to - from) * t;
    public static Station Midpoint(Station lo, Station hi) => lo + (hi - lo) / 2d;
}
```

[ABSENCE_AND_DEFAULT]:
- Law: null-yield modes turn blank input into success-with-null; only `EmptyStringInFactoryMethodsYieldsNull` removes `NotNullWhen`, so bridges audit generated attributes and project `Option<T>`.
- Law: struct owners reject `default`, but arrays, unconstrained generic `default`, and field zero-init still mint ghosts; one outer storage seam reads the key member and rejects them.
- Law: an owner-typed `= default` optional parameter is a ghost-minting seam, never absence — a class owner has no constant to default to, and a struct owner under `AllowDefaultStructs` defaults to the admission-bypassing zero, so absence enters as `Option<T>` or an overload, the canonical instance is named when a real zero exists, and `= default` never spells the absent owner.
- Boundary: default-hostility is transitive, `IDisallowDefaultValue` overrides `AllowDefaultStructs`, legitimate struct defaults are named canonical instances, and class-vs-struct choice selects named null policy versus layout poison.

[INGRESS_AND_EGRESS]:
- Law: conversion direction follows the trust gradient; owner-to-key conversion is implicit evidence erasure, key-to-owner conversion is explicit admission, and aggregate reconstruction climbs through explicit admissions.
- Boundary: key-to-owner casts are hidden throwing admission; keep them at boundaries, remove them with `ConversionFromKeyMemberType` or `SkipFactoryMethods`, and account for class reference-key null propagation before factory admission.
- Law: class-owner null contracts are operator-family local; equality tolerates null, comparison and arithmetic throw, unsafe egress faults, and no family lends null-safety to another.
- Law: one accessibility token gates constructors, conversions, and factories, with domain factory verbs on the owner; `SkipFactoryMethods` removes constructing surfaces and leaves only equality, comparison, and egress over already-admitted values.

## [04]-[SMART_ENUMS]

[VOCABULARY_DECLARATION]:
- Law: the declaration list is the vocabulary; `public static readonly` fields fix item membership, dispatch indices, callback order, and metadata identifiers, while static properties and case-typed fields vanish from `Items` and dispatch at warning severity.
- Law: keyed vocabularies carry two independent orders: `Items` by declaration and comparison by key comparer; one key policy swings lookup, hash, comparison, and operators.
- Law: domain rank is an item column, never a bent comparer; range dispatch needs numeric keys to keep future thresholds total, and later-row references defer behind delegates because initialization order can capture null before materialization protects it.
- Accept: keyless vocabularies only for behavior rows: items, dispatch, reference identity, no lookup, no conversions, no parsing; wire identity requires declared `[ObjectFactory<TValue>]`.

[LOOKUP_LIFECYCLE]:
- Law: validity belongs to keys, never instances; no invalid item is constructible, callers choose `Get`, `TryGet`, or `Validate`, and exception catching is the wrong verb.
- Law: startup probes force the `LazyThreadSafetyMode.ExecutionAndPublication` lazy, assign indices, build the frozen lookup, fail-fast duplicate keys, and cache one poisoning across metadata consumers walking `Items`.
- Law: derived indexes project from `Items` through accessors, never eager static initializers; the accessor read supplies the materialization edge, and string-keyed vocabularies use the zero-allocation span alternate lookup.
- Boundary: items are static per load context and generic instantiation; each closed type argument has its own materialization and poisoning, and values cross isolation seams as keys re-admitted on the far side.

[DISPATCH_AND_ROWS]:
- Law: `Switch` is the total dispatch surface: integer jump table, write-once index cell, one hot-path field read, state-threaded forms with span-shaped state and results, and `static` lambdas.
- Law: totality is method arity; new items add parameters to total overloads, stale exhaustive dispatch fails to compile, and named callback arguments are the reorder shield.
- Reject: language `switch`, key-pattern probes, and guard chains; items are singletons, not constants, and only generated `Switch` is total.
- Law: row-owned behavior wins when the vocabulary owns the policy or the same full-coverage `Switch` repeats; `[UseDelegateFromConstructor]` columns force every item to answer once, while generated `Switch` remains for single-consumer reactions.
- Boundary: partial dispatch is a presence test, not routing; `SwitchPartially` cannot distinguish omitted and null arms, omitted `@default` is no-op, `MapPartially` preserves legal defaults, and 1,000 items retain lookup but lose dispatch.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class Variant {
    public static readonly Variant RowA = new("<value-b>", rank: 2, ProjectA);
    public static readonly Variant RowB = new("<value-a>", rank: 1, ProjectB);

    public int Rank { get; }

    private static readonly Lazy<FrozenDictionary<int, Variant>> ByRank =
        new(static () => Items.ToFrozenDictionary(static row => row.Rank));

    [UseDelegateFromConstructor]
    public partial (double Primary, double Secondary) Project(double input);

    public static Option<Variant> Ranked(int rank) =>
        ByRank.Value.TryGetValue(rank, out var row) ? Optional(row) : None;

    private static (double, double) ProjectA(double input) => (input, input);
    private static (double, double) ProjectB(double input) => (input * 2d, input * 4d);
}

public static class VariantOps {
    extension(Variant row) {
        public bool Matches(double input) => row.Switch(
            state: input,
            rowA: static value => value >= 0d,
            rowB: static value => value > 1d);
    }

    public static ImmutableArray<double> Projected(params ReadOnlySpan<Variant> rows) =>
        [.. LanguageExt.Iterable<Variant>.FromSpan(rows).Map(static row => row.Project(row.Rank).Primary)];
}
```

## [05]-[UNIONS]

[FAMILY_SELECTION]:
- Law: the root declaration kind is family-global; record roots buy structural equality, cross-case comparison constant-false, and flatness, while class roots buy depth, intermediate cases, nested dispatch, and stop-at boundaries while surrendering generated equality.
- Law: closure is constructor reachability; private owner constructors, sealed or private-constructed cases, and class-kind recursion define discovery, while struct and interface intermediates become invisible phantom cases that fall to the default arm.
- Law: generic roots carry phantom typestate; cases close over root parameters, dispatch stays phase-total, and storage or transport pays invariance through erasing projections.
- Law: span alternatives are concrete only; `ref struct` type parameters are rejected, while a `ref struct` union keeps dispatch and stack-only state or results but surrenders generated equality.
- Law: cases admit their own payloads; the root carries no validation partial unless `[ObjectFactory<TValue>]` makes `Validate` the discriminating admission seam.
- Use: root-level dispatch stance; total `SwitchMethods` and `MapMethods` by default, sparse handling through `DefaultWithPartialOverloads`, and transport-only carriers through `SwitchMapMethodsGeneration.None` with arm-style consumption inexpressible.
- Reject: success-or-failure ad-hoc unions because rails own outcome transport; accept duplicate ad-hoc member types only when named slots model distinct ingress and equality discriminates slot before payload.

[DISPATCH_AND_GROWTH]:
- Law: `Map` evaluates every arm before dispatch; keep it to preallocated verdict tables and cold carriers, and move allocating or task-shaped arms to func-form `Switch`.
- Law: dispatch signatures own case lists; case addition is a binary break across consumers, lockstep across assembly boundaries, free inside one build graph.
- Law: blast radius partitions by axis; case rename breaks named arguments and embedded type names, while same-name payload changes break only arms touching the member.
- Law: `StopAt` overloads and intermediate `[Union]` receivers are growth-axis declarations: root consumers couple to sibling growth, branch consumers couple to within-branch growth, and the stopped handler is the fold re-entry seam.
- Law: operation families attach as extension members with total dispatch; conversions stay generated, ordering stays absent, and rank projects through `Map` to preallocated ordinals.
- Law: recursive owners declare recursion placement; case-owned recursion absorbs growth locally, dispatch-route recursion breaks call sites, and partial dispatch is rejected for routing or `K<F,B>` folds; new cases silently route to `@default` across every carrier specialization.

[AD_HOC_FORM]:
- Law: storage is computed: typed fields per stateful unique member until a second stateful reference member collapses references into one `object` slot; struct members stay inline, and `TxIsStateless` identity rides the discriminator.
- Law: struct ad-hoc `default` is poison; index zero throws on first observation, never minting, and only `Is{Name}` probes are total enough for rehydration, pooling, and array scans.
- Law: equality gates by discriminator, then member under `DefaultStringComparison`; hash omits discriminator mixing, `ToString` erases the active case, and identity-bearing rendering routes through generated case dispatch or `Is{Name}` and `As{Name}` probes.
- Boundary: implicit conversions make the union a parameter absorber, replacing overloads and lifting mixed collection expressions, until interface, `object`, type-parameter, or duplicate members require `Create{Name}` factories; closing ingress sets both non-public `ConstructorAccessModifier` and `ConversionFromValue = ConversionOperatorsGeneration.None`.

```csharp conceptual
[Union<string, int, Blank>(T1Name = "Text", T2Name = "Count", T3Name = "Blank", T3IsStateless = true)]
public readonly partial struct FieldValue;

public readonly record struct Blank;

public static class FieldValueOps {
    extension(FieldValue value) {
        public string Projected() => value.Switch(
            text: static text => text.Trim(),
            count: static count => $"<value-a>:{count}",
            blank: static _ => "<value-b>");

        public Option<string> TextOrNone() =>
            value.IsText ? Optional(value.AsText) : None;
    }

    public static ImmutableArray<string> ProjectAll(params ReadOnlySpan<FieldValue> values) =>
        [.. LanguageExt.Iterable<FieldValue>.FromSpan(values).Map(static value => value.Projected())];

    public static ImmutableArray<FieldValue> From(string text, int count, Blank blank) =>
        [text, count, blank];
}
```

[RECURSIVE_SHAPE]:
- Law: a recursive family is the class-kind `[Union]` whose cases nest the root — an `abstract partial record` root with self-nesting sealed cases declares recursion as a shape property, and class-kind reachability is what makes the nested case discoverable where a struct or interface intermediate would fall to the default arm as a phantom case.
- Law: recursion placement is the shape decision this card owns — case-owned recursion (a case field typed as the root) absorbs depth growth locally and keeps every consumer's dispatch total, while dispatch-route recursion couples each call site to the recursion and is the rejected placement; the choice is fixed at declaration, never at the fold.
- Boundary: the generated `Switch` is depth-honest recursion bounded by the runtime stack, so hostile or unbounded depth is a different shape — an explicit-stack kernel admitted at the boundary, never the generated traversal pushed past its depth budget.
- Boundary: the carrier-polymorphic catamorphism the snippet composes — the `K<F,B>` child folds combined under the carrier's own `Apply` so one fold specializes across every applicative carrier — is the surface and rail pages' mechanics, supporting material here; this card decides only that the family is a recursive class-`[Union]` and where the recursion lives.

```csharp conceptual
[Union]
public abstract partial record Node {
    public sealed record Leaf(double Value) : Node;
    public sealed record Branch(Node Left, Node Right) : Node;
}

public static class NodeOps {
    extension(Node source) {
        public K<F, B> Fold<F, B>(Func<Node.Leaf, K<F, B>> leaf, Func<B, B, B> merge)
            where F : Applicative<F> =>
            source.Switch<(Func<Node.Leaf, K<F, B>> Leaf, Func<B, B, B> Merge), K<F, B>>(
                (leaf, merge),
                leaf: static (s, n) => s.Leaf(n),
                branch: static (s, n) =>
                    (n.Left.Fold(s.Leaf, s.Merge), n.Right.Fold(s.Leaf, s.Merge)).Apply(s.Merge));
    }
}
```

[GRAPH_FAMILY]:
- Law: a domain graph is a property graph of two closed `[Union]` owners, never a per-relation class roster mirroring a foreign schema — the edge is one neutral verb `[Union]` over a small closed verb set (compose, assign, associate, connect, each carrying its own typed payload) plus exactly one `Generic(WireName, Relating, Related, Attributes)` passthrough case, so the foreign relationship taxonomy never leaks into the neutral owner and no foreign relation is dropped; N typed per-relation cases mirroring the foreign taxonomy is the `[03]-[COLLAPSE_SCAN]` foreign-taxonomy trigger, collapsed to this verb algebra.
- Law: the node is one keyed `[Union]` over the entity family — each case an entity kind, keyed in the working map by a neutral kernel id, and the foreign or wire id is a boundary attribute on the node, never the kernel key the map indexes.
- Law: the consumer-facing aggregate is a derived fold over the reachable subgraph, never a second stored record beside the graph — "has every property" is the `Switch`-driven fold the read snapshot computes, so adding an edge verb or a node kind is one case with the aggregate breaking loudly at compile time.
- Boundary: a class-root node or edge `[Union]` surrenders Thinktecture's record-root generated equality, so structural equality and the structured diff ride Generator.Equals `[Equatable]` — the one generated equality aspect for the shapes Thinktecture does not own — never a hand-written `Equals`/`GetHashCode`.
- Boundary: the two-phase working-versus-snapshot split, the memoized incidence index, traversal and topology, and the content-addressed graph id are the algorithm, system-API, and boundary pages' — this card owns only that the edge and node are two closed `[Union]` owners and that the verb set stays neutral with one `Generic` tail.

```csharp conceptual
[Union]
[Equatable]
public abstract partial class Relation {
    public sealed partial class Compose(FieldKey whole, FieldKey part) : Relation { public FieldKey Whole { get; } = whole; public FieldKey Part { get; } = part; }
    public sealed partial class Assign(FieldKey subject, FieldKey definition) : Relation { public FieldKey Subject { get; } = subject; public FieldKey Definition { get; } = definition; }
    public sealed partial class Associate(FieldKey owner, FieldKey associate, FieldValue role) : Relation { public FieldKey Owner { get; } = owner; public FieldKey Associated { get; } = associate; public FieldValue Role { get; } = role; }
    public sealed partial class Connect(FieldKey from, FieldKey to, double weight) : Relation { public FieldKey From { get; } = from; public FieldKey To { get; } = to; public double Weight { get; } = weight; }

    public sealed partial class Generic(string wireName, FieldKey relating, FieldKey related, ImmutableArray<KeyValuePair<string, string>> attributes) : Relation {
        public string WireName { get; } = wireName;
        public FieldKey Relating { get; } = relating;
        public FieldKey Related { get; } = related;
        [OrderedEquality] public ImmutableArray<KeyValuePair<string, string>> Attributes { get; } = attributes;
    }
}

[Union]
[Equatable]
public abstract partial class Entity {
    public sealed partial class Occurrence(FieldKey key, FieldKey type) : Entity { public FieldKey Key { get; } = key; public FieldKey Type { get; } = type; }
    public sealed partial class Aggregate(FieldKey key) : Entity { public FieldKey Key { get; } = key; }
    public sealed partial class Property(FieldKey key, FieldValue value) : Entity { public FieldKey Key { get; } = key; public FieldValue Value { get; } = value; }
}

public static class GraphOps {
    extension(Relation relation) {
        public (string Verb, FieldKey Relating, FieldKey Related) Endpoints() => relation.Switch(
            compose:   static c => ("<verb-a>", c.Whole, c.Part),
            assign:    static a => ("<verb-b>", a.Subject, a.Definition),
            associate: static a => ("<verb-c>", a.Owner, a.Associated),
            connect:   static n => ("<verb-d>", n.From, n.To),
            generic:   static g => (g.WireName, g.Relating, g.Related));
    }

    public static FrozenSet<string> Verbs(Seq<Relation> edges) =>
        edges.Map(static edge => edge.Endpoints().Verb).ToFrozenSet();
}
```

- Law: polymorphic JSON uses per-leaf `[JsonDerivedType]`, exact runtime type resolution, unregistered-leaf failure, `nameof` or published member-list discriminators, and boundary-pinned metadata ordering.
- Boundary: deserialization is admission; generated converters route through `Validate`, prevent half-built unions, and exist only when the framework integration assembly is present.
- Reject: wire exposure without converter gates; reflection serializers can empty-object private-keyed class owners or zero-init struct owners, bypassing admission without an exception.

## [06]-[ADMISSION_SHAPES]

The owner's admission surface is itself a closed family decision: the fault is a `[Union]`, the bridge an extension over the generated factory, the composite an admission-ordered nest of leaf owners, and the wire grammar an owner-local row set. Each card fixes the shape; the rail algebra that consumes it is the rail page's, the open-owner dispatch inversion the surface page's, and the converter the boundary page's.

[FAULT_FAMILIES]:
- Law: the fault is one `[Union]` deriving from `Expected`, so the same closed family is the validation-error shape, the rail-failure shape, and the exhaustive recovery vocabulary — a bare `Error`, an exception, or `Validation<Seq<Error>,T>` for a multi-cause domain is the rejected non-shape.
- Law: the family is two-tier by construction — the private base constructor seeds `Expected(detail, code, inner)`, `Create` mints the string-bearing case for generator text, and a structured case opting into `IValidationError<TCase>` publishes a precise generated `Create` so the generator targets the exact case.
- Law: the aggregate is a union case, not a string flatten — a `Semigroup<TFault>` `Combine` folds independents while preserving every typed member, so field-attributed faults stay addressable without positional reconstruction; the accumulation operator that drives the fold is the rail page's.
- Boundary: `StopAt` carves a smaller recovery surface where a boundary needs one, and only self-sufficient message and code cross the wire; code-keyed recovery identity (`Is`/`HasCode`/`IsType<E>`, never `==`) is the rail page's fault-identity law, composed over this shape.

```csharp conceptual
[Union]
public abstract partial record Fault : Expected, IValidationError<Fault>, Semigroup<Fault> {
    private Fault(string detail, int code) : base(detail, code, None) { }

    public static Fault Create(string message) => new Text(message);

    public sealed record Text : Fault { public Text(string detail) : base(detail, 4000) { } }
    public sealed record Bounds : Fault, IValidationError<Bounds> {
        public Bounds(string detail) : base(detail, 4001) { }
        public static new Bounds Create(string detail) => new(detail);
    }
    public sealed record Aggregate : Fault {
        public Aggregate(Seq<Fault> faults) : base($"{faults.Count} faults", 4099) => Faults = faults;
        public Seq<Fault> Faults { get; }
    }

    public Fault Combine(Fault rhs) => (this, rhs) switch {
        (Aggregate l, Aggregate r) => new Aggregate(l.Faults + r.Faults),
        (Aggregate l, _) => new Aggregate(l.Faults.Add(rhs)),
        (_, Aggregate r) => new Aggregate(this.Cons(r.Faults)),
        _ => new Aggregate(Seq(this, rhs)),
    };
}
```

[RAIL_BRIDGE]:
- Law: the admission seam is one generic extension over the generated factory contract — receiver inference binds `TOwner` so a single `Admission` block serves every owner, and the property-pattern projection (`Validate(...) is { } fault ? fault : owned!`) is the one expression admitting raw into the carrier.
- Law: the shape is null-yield-aware — a non-null-yield contract takes the success-arm `!`, a null-yield owner takes the three-valued projection (fault, absence as `Option<T>`, instance) so blank-yields-null never reaches the interior as `Some(null)`; the carrier algebra each arm lifts into is the rail page's.
- Boundary: the constraint `IObjectFactory<TOwner,TRaw,Fault>` with `TRaw : notnull, allows ref struct` is the closed-fault counterpart of the surface page's open-`TError` inversion — this seam pins the fault to one family for receiver-inferred reuse, that one opens `TError` for the unbounded owner set.
- Reject: bridging through `Create`, `TryCreate`, or `IParsable`; framework parsing and downgraded factory forms discard the evidence `Validate` already carries.

```csharp conceptual
public static class Admission {
    extension<TOwner, TRaw>(TOwner)
        where TOwner : class, IObjectFactory<TOwner, TRaw, Fault>
        where TRaw : notnull, allows ref struct {
        public static Validation<Error, TOwner> Admitted(TRaw raw, IFormatProvider? culture = null) =>
            TOwner.Validate(raw, culture, out var owned) is { } fault ? fault : owned!;

        public static Validation<Error, Option<TOwner>> AdmittedMaybe(TRaw raw) =>
            TOwner.Validate(raw, null, out var owned) is { } fault ? fault : Optional(owned);

        public static Fin<TOwner> AdmittedFin(TRaw raw) =>
            TOwner.Validate(raw, null, out var owned) is { } fault ? Fin.Fail<TOwner>(fault) : owned!;
    }
}
```

[COMPOSITE_ADMISSION]:
- Law: a composite owner admits its leaf owners first, then binds composite refinements after every leaf succeeds, so the dependency graph of the fields — not a flag — selects whether the shape accumulates leaf faults or short-circuits on the first cross-field refusal.
- Law: the generated factory spine never accumulates; an all-fault composite shape carries one `Semigroup` aggregate case (the `[FAULT_FAMILIES]` union), and a missing `Semigroup` is unmanufacturable, so the fault family is the prerequisite, not a downstream choice.
- Law: every generated owner conforms to `IObjectFactory<TSelf,TRaw,TFault>`, so the owner type is the zero-witness typeclass instance a constrained generic dispatches on without an instance — the open-owner inversion and the constraint-tier-selection mechanics are the surface page's, the conformance is the shape.
- Boundary: leaf admission composes through the rail page's accumulating carrier and the composite-refinement `guard`; this card owns only the leaf-before-composite order and the aggregate-case prerequisite, never the accumulation operator.

[WIRE_OWNERSHIP]:
- Law: a protocol DTO is a shape only on topology divergence — a scalar wire collapses into the owner's object factory, a string wire into a parse-format `[ObjectFactory<TValue>]` micro-grammar, and a keyed owner severs the DTO at declaration through `UseForSerialization`; a surviving DTO stays a raw disposable record that never grows `Validate`.
- Law: `[ObjectFactory<TValue>]` rows are owner-local admission grammars whose declaration order is behavior — the last matching row wins consumer resolution, and serialization, persistence, and binding each claim exactly one row, so the owner carries every wire dialect as a closed row set rather than a sibling DTO per protocol.
- Boundary: `HasCorrespondingConstructor` marks the persistence-only trusted-rehydration row for already-admitted truth; the converter, resolver, and metadata-plane mechanics that consume these rows are the boundary page's, named here only as the owner-shape decision they read.
