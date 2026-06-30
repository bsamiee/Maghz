# [CSHARP_LANGUAGE]

C# 14 on `net10.0` is the active language surface, and this page is the language-form law: which declaration, member, pattern, construction, conversion, and literal form carries a concept before any generated owner, rail, or boundary is reached. The value lifecycle is shed by kind — generated-owner shape rides `shapes.md`, dispatch and arity ownership ride `surfaces-and-dispatch.md`, the result rail rides `rails-and-effects.md`, foreign admission rides `boundaries.md`, and BCL API replacement rides `system-apis.md`. A form-contract snippet composes those owners as settled material and demonstrates only the syntactic shape that precedes them.

`Directory.Build.props` owns `TargetFramework`, `LangVersion`, `Nullable`, `ImplicitUsings`, and `CheckForOverflowUnderflow`; this page names those facts only where they change the form a source file may assume.

## [01]-[ACTIVE_SURFACE]

[ACTIVE_SURFACE]:
- Target framework: `net10.0`
- Language version: `14.0` explicit; floating `latest`/`preview` is rejected so a form lands only when the pinned compiler owns it
- Nullable: `enable` with warnings-as-errors, so a nullable annotation is a checked contract, never advisory
- Implicit usings: `enable`; `LanguageExt.Prelude` enters `static`, so `Optional`, `guard`, `Some`, and `None` are unqualified
- Overflow: `CheckForOverflowUnderflow` is on, so an unchecked numeric body is the deliberate `unchecked(...)` exception, and a key-math operator traps by default

Treat source as modern C#, not a compatibility layer. Replace an overload family, a wrapper type, a backing-field accessor, or a guarded null-check the moment the active surface carries the concept in one form.

## [02]-[FORM_CHOOSER]

Each table routes a concept to the C# 14 form that owns it; the most specific row wins, and every `[USE]` names the spelling it deletes. Rows a competent reader already reaches for are omitted — the chooser legislates the opinionated form, never the language census.

[DECLARATION_AND_MEMBER_FORMS]: which declaration, member, or callable form carries the concept.

| [INDEX] | [CONCERN]                        | [USE]                                            | [REPLACE]                                      |
| :-----: | :------------------------------- | :----------------------------------------------- | :--------------------------------------------- |
|  [01]   | behavior on a foreign receiver   | `extension(Receiver)` block, members + operators | static helper class, `this`-parameter method   |
|  [02]   | property-local invariant         | `field` keyword accessor                         | manual backing field beside one accessor       |
|  [03]   | mutate-in-place accumulation     | instance `operator +=` / `operator ++`           | static binary operator plus a fresh allocation |
|  [04]   | mandatory initialization         | `required` members with `init`                   | constructor telescoping, factory-only set      |
|  [05]   | generated and hand-written split | `partial` members, constructors, events          | wrapper-forwarding split, hook indirection     |
|  [06]   | attribute payload type           | generic attribute `[Attr<T>]`                    | `typeof` constructor argument                  |
|  [07]   | construction abstraction         | static-abstract interface member                 | reflection factory, activator switch           |
|  [08]   | dense signature alias            | `using` alias for a constructed or tuple type    | a parallel domain type name for one shape      |

[PATTERN_AND_DISPATCH_FORMS]: value decisions and shape probes stated as one total expression.

| [INDEX] | [CONCERN]                     | [USE]                                        | [REPLACE]                                 |
| :-----: | :---------------------------- | :------------------------------------------- | :---------------------------------------- |
|  [01]   | value-returning decision      | switch expression over the closed owner      | `if`/`else` ladder, statement switch      |
|  [02]   | sequence head/tail/length law | list and slice patterns with `var` binding   | count guards plus index arithmetic        |
|  [03]   | range and sign law            | relational and logical patterns              | a comparison-chain boolean block          |
|  [04]   | span text dispatch            | constant string patterns over a `char` span  | `ToString()` then `==` comparison         |
|  [05]   | shape probe with binding      | property and positional patterns, `out var`  | `as` plus null check, pre-declared locals |
|  [06]   | exhaustiveness                | total switch, no `_` arm over a closed owner | a `_` default arm hiding a missing case   |

[CONSTRUCTION_AND_CONVERSION_FORMS]: how values are composed, how arity and span boundaries are crossed, and how C# 14 span conversions remove copies.

| [INDEX] | [CONCERN]                        | [USE]                                              | [REPLACE]                              |
| :-----: | :------------------------------- | :------------------------------------------------- | :------------------------------------- |
|  [01]   | literal composition with spread  | collection expression `[.. head, x, .. tail]`      | `new[]` plus `Concat`, list-add chains |
|  [02]   | end-relative initialization      | implicit `[^1]` index in an object initializer     | post-construction assignment loop      |
|  [03]   | call-site arity                  | one `params ReadOnlySpan<T>` parameter             | per-arity overload family              |
|  [04]   | array-to-span at the call site   | C# 14 first-class `Span`/`ReadOnlySpan` conversion | a manual `.AsSpan()` adapter overload  |
|  [05]   | residual span-overload ambiguity | `[OverloadResolutionPriority]` during a collapse   | a breaking rename or a dummy parameter |

[KERNEL_AND_LITERAL_FORMS]: stack-only layout in a measured kernel, and structured text stated as a literal.

| [INDEX] | [CONCERN]                         | [USE]                                         | [REPLACE]                                |
| :-----: | :-------------------------------- | :-------------------------------------------- | :--------------------------------------- |
|  [01]   | stack-only contract conformance   | `ref struct` implementing an interface        | boxing the stack value to the interface  |
|  [02]   | span-capable generic              | `allows ref struct` type parameter            | a boxed or duplicated non-span path      |
|  [03]   | by-reference field                | `ref` field with `scoped` lifetime            | a raw pointer carrier, an index pair     |
|  [04]   | ref state inside a coroutine      | `ref`/`unsafe` in an iterator or `async` body | an extracted helper duplicating the body |
|  [05]   | embedded structured text          | raw string literal `"""..."""`                | escape-laden concatenation               |
|  [06]   | terminal escape in processed text | `\e`                                          | the `\x1b` magic literal                 |

## [03]-[LANGUAGE_FORM_CONTRACTS]

Each contract fixes the placement rule the chooser row cannot state. The form-contract snippets compose the finalized owners — generated shapes, rails, dispatch surfaces — as supporting material; the spotlight is the language form itself, and each contract closes on the one boundary that hands the value off to its owning page.

[EXTENSION_SURFACE_SITE]:
- Use when: behavior belongs to a receiver the declaring assembly does not own, or a forwarding wrapper type would only decorate an existing receiver.
- Accept: one `extension(Receiver)` block per receiver shape holding instance members, computed properties, indexers, and static members; an open-generic receiver `extension<T>(ReadOnlySpan<T> source) where T : ...` so one block serves a whole receiver family; a parameterless `extension<T>(ReadOnlySpan<T>)` block declaring `static operator` members that take the receiver type and return a value — a scalar, an `Option<T>`, or a detached owned result — the C# 14 form that attaches operators to a foreign type the assembly cannot edit.
- Reject: a static helper class with a receiver-first `this`-parameter method, a wrapper type that renames receiver behavior, an extension conversion operator (`implicit`/`explicit` is forbidden in an extension block, `CS9282`), a span-typed `extension` operator returning a stack-allocated `ReadOnlySpan<T>`/`Span<T>` collection expression (`CS9203` — the result escapes the receiver scope), and a member whose body admits, validates, or dispatches domain state — that graduates to the owning generated shape.
- Boundary: the block adds receiver-local computation over an already-admitted value; closed-family dispatch, admission, and the operator algebra over a domain key live on the `shapes.md` owner the block composes, never inside the block.

The form spotlight: one instance-member `extension<T>(ReadOnlySpan<T> source)` block and one operator-only `extension<T>(ReadOnlySpan<T>)` block attach a whole probe-and-compose surface to a `ref struct` the assembly cannot edit, each member a list or slice pattern over the receiver and the `|` operator rail-lifting the longer span's head — the deleted form is a `SpanExtensions.First<T>(this ReadOnlySpan<T>, ...)` helper class whose receiver-first parameter the block replaces with direct receiver reach, and a free `Longer(a, b)[0]` length-branch-then-index pair the operator collapses into one `Option<T>`. An operator over a span returns a value, never a `[.. head, .. tail]` collection expression, which cannot escape the receiver's stack scope; the family grows by one member inside the existing block, never a new static method beside it.

```csharp conceptual
public static class SpanSurface {
    extension<T>(ReadOnlySpan<T> source) {
        public bool Single => source is [_];

        public Option<T> First => source is [var head, ..] ? Optional(head) : None;

        public Option<(T Head, T Last)> Ends =>
            source is [var head, .., var last] ? Optional((head, last)) : None;

        public Option<int> Interior => source is [_, .. var trunk, _] ? Optional(trunk.Length) : None;
    }

    extension<T>(ReadOnlySpan<T>) {
        public static Option<T> operator |(ReadOnlySpan<T> head, ReadOnlySpan<T> tail) =>
            (head.Length >= tail.Length ? head : tail) is [var lead, ..] ? Optional(lead) : None;
    }
}
```

[PATTERN_DISPATCH_SITE]:
- Use when: a value-returning decision states its whole law as one total pattern expression over sequence shape, range, or a closed owner.
- Accept: a switch expression composing list and slice patterns, relational and logical patterns, property and positional patterns, constant string patterns over a `char` span, and `var` bindings inside arms; a `when` guard only to relate two pattern-bound values an arm cannot otherwise express (`head.Key == tail.Key`); the closed owner's generated `Switch` when the discriminant is a `[Union]` or `[SmartEnum]` case.
- Reject: an `if`/`else` ladder, a statement switch for a value decision, an `as`-plus-null-check probe, a `when` guard carrying the structural narrowing a list, slice, relational, or property pattern already expresses, and a `_` arm hiding a missing case of a closed owner — the `_` over an open span shape is the documented exhaustiveness floor, never a swallowed case.
- Boundary: closed-family ownership, generated dispatch, and case exhaustiveness belong to the `shapes.md` owner; this site owns the structural-pattern grammar that probes raw or open shapes before that owner reaches them.

The form spotlight: one switch expression states a span's whole banding law — `[]` empty, head and tail property probes `[{ Rank: < 0 }, ..]` and `[.., { Rank: >= 9, Key: var key }]`, the single-element capture `[{ ... } only]`, and the cross-binding `when` that relates the bound head and tail no single pattern can — collapsing an `if`/`else` ladder over `marks.Length` and `marks[0].Rank` into one total expression; the sibling `Routed` shows constant-string and `['<', .. var body, '>']` slice patterns dispatching protocol text over a `char` span with no `ToString` allocation. Both prove the `_` floor sits over an open shape, not a closed owner whose missing case must break the build instead.

```csharp conceptual
public readonly record struct Mark(string Key, int Rank);

public static class MarkPolicy {
    public static string Banded(ReadOnlySpan<Mark> marks) =>
        marks switch {
            [] => "<band-empty>",
            [{ Rank: < 0 }, ..] => "<band-negative>",
            [.., { Rank: >= 9, Key: var key }] => $"<band-peak>:{key}",
            [{ Rank: >= 0 and < 9 } only] => $"<band-single>:{only.Key}",
            [var head, .., var tail] when head.Key == tail.Key => $"<band-wrap>:{head.Key}",
            _ => "<band-mixed>",
        };

    public static int Routed(ReadOnlySpan<char> token) =>
        token switch {
            "<token-a>" or "<token-b>" => 0,
            ['<', .. var body, '>'] => body.Length,
            ['/', ..] or [.., '/'] => -1,
            { Length: > 16 } => -2,
            _ => token.Length,
        };
}
```

[IMMUTABLE_CARRIER_SITE]:
- Use when: an inert carrier needs identity, mandatory initialization, or a property-local invariant, and has no admission, vocabulary, or dispatch pressure that would graduate it to a generated owner.
- Accept: `record` and `readonly record struct` for structural identity; `required` plus `init` for mandatory members so a missing field is a construction-site compile error, not a runtime null; the `field` keyword to attach a one-property clamp without a named backing field; `with` for nondestructive update; `partial` members and constructors where a generator co-owns the type.
- Reject: a manual backing field serving one accessor, constructor telescoping for mandatory members, a `Create`/`With`/copy-constructor factory beside `with`, an optional-parameter constructor that re-admits a value the `init` already gates, and a hand-written `Equals`/`GetHashCode` on inert data — structural equality is the record's and the content key is the `boundaries.md` byte-identity owner's.
- Boundary: the moment a carrier admits raw input, carries a closed vocabulary, or dispatches, it becomes a `[ValueObject]`, `[ComplexValueObject]`, `[SmartEnum]`, or `[Union]` chosen by `shapes.md` `OWNER_CHOOSER`; the `field` clamp here is a layout convenience over trusted data, not the admission factory that owner's `Validate` is.

The form spotlight: a `readonly record struct Patch` and a `sealed record Profile` carry identity and a one-property `Weight` clamp through `init => field = int.Max(value, 0)` with no second field declared, and `Shifted` threads two coupled `with` updates in one expression — the deleted forms are a `_weight` backing field beside the accessor, a four-argument telescoping constructor for the `required` members, and a `Profile WithWeight(int)`/`WithWindow(Patch)` pair that `with` subsumes. The clamp guards a trusted in-process update; the instant `Weight` must reject raw external input with a typed fault, the struct graduates to a `[ValueObject<int>]` and the `field` accessor is deleted.

```csharp conceptual
public readonly record struct Patch(int Offset, int Length);

public sealed record Profile {
    public required string Key { get; init; }

    public required Patch Window { get; init; }

    public int Weight {
        get;
        init => field = int.Max(value, 0);
    } = 1;

    public Profile Shifted(int delta) => this with {
        Weight = Weight + delta,
        Window = Window with { Offset = Window.Offset + delta },
    };
}
```

[SPAN_AND_CONVERSION_SITE]:
- Use when: a value is composed from a literal, an entrypoint absorbs every call arity, or an array crosses into a span boundary the C# 14 first-class span conversions now bridge implicitly.
- Accept: a collection expression with spread for literal composition; an implicit `[^1]` index inside an object initializer over an indexable member; one `params ReadOnlySpan<T>` parameter where the buffer is implicitly `scoped`; the C# 14 implicit `T[]`-to-`ReadOnlySpan<T>`/`Span<T>` conversion so a span receiver, a span argument, and generic inference compose without an `.AsSpan()` hop.
- Reject: a `new[]` plus `Concat` chain, list-add ceremony, an overload family differing only by collection kind, and a manual `.AsSpan()` adapter the implicit conversion subsumes; the implicit conversion's own resolution hazard — a span overload now competing with an array overload — is the arity-collapse decision `surfaces-and-dispatch.md` owns, not re-derived here.
- Boundary: arity, modality, overload-priority resolution, and the request-union dispatch that an absorbed call routes into are `surfaces-and-dispatch.md`'s; this site owns the literal, the index, and the C# 14 span-conversion forms that feed them, never the dispatch.

The form spotlight: one `params ReadOnlySpan<int>` entrypoint collapses the empty, singular, and plural call into a stack-allocated buffer with no per-arity overload, the collection expression `[.. head, 0, .. tail]` fuses two spreads where a `head.Concat([0]).Concat(tail).ToArray()` chain allocated twice, the implicit `int[]`-to-`ReadOnlySpan<int>` conversion lets `body` reach the spread with no `.AsSpan()` adapter, and the `[^1]` initializer writes the last seat end-relative without a post-construction index loop. Arity is a property of the literal; the page never grows a `bool batch` knob beside the value.

```csharp conceptual
public sealed record Board {
    public required ImmutableArray<int> Cells { get; init; }

    public int[] Seats { get; init; } = new int[4];

    public static Board Of(params ReadOnlySpan<int> cells) => new() { Cells = [.. cells] };

    public static Board Capped(int lead) => new() { Cells = [lead], Seats = { [0] = lead, [^1] = -lead } };
}

public static class BoardOps {
    public static ImmutableArray<int> Merged(ReadOnlySpan<int> head, params ReadOnlySpan<int> tail) =>
        [.. head, 0, .. tail];

    public static Board Framed(int lead, int[] body, int trail) => new() {
        Cells = [lead, .. body, trail],
    };

    public static Option<int> Lead(int[] cells) => cells is [var head, ..] ? Optional(head) : None;
}
```

[STACK_KERNEL_SITE]:
- Use when: a measured algorithm needs stack-only values, by-reference state, or span traversal that a rail combinator cannot carry without allocation, and the kernel returns ordinary values or rails at its public edge.
- Accept: a `ref struct` owner with a primary constructor; a `ref` field with a `scoped` lifetime; the C# 14 instance `void operator +=` that mutates that `ref` field in place, so accumulation is one member call, not a static binary operator returning a fresh value; an `allows ref struct` type parameter so one fold body admits a stack-only step; a `ref struct` implementing an interface so the contract binds without boxing; `ref` and `unsafe` inside an iterator or `async` body; statement loops confined to the kernel body.
- Reject: boxing a stack-only value through an interface conversion, carrying a `ref struct` across `await` or `yield`, a pointer carrier where a `ref` field expresses the lifetime, and a kernel-style statement leaking into domain flow.
- Boundary: this is the named statement exemption for the language type-system layer; the numeric route that consumes the kernel and the foreign memory the span borrows are `algorithms.md`'s and `boundaries.md`'s, never re-derived here.

The form spotlight: a `ref struct PeakStep` implements `IStep<double>` so the contract binds with no box, its C# 14 instance `operator +=` folds each value into the `ref double` field in place where a static `operator +` would return a fresh value the loop discards, and `Frame.Fold` admits the step through an `allows ref struct` type parameter so one stack-only fold body runs without heap traffic — the `foreach` loop and the operator's two-statement body are the named statement exemption, confined to the kernel and never reached by domain flow, which receives the kernel's ordinary return value. The deleted form is a boxed `IStep<double>` argument and a heap `Func<double,double,double>` accumulator on a measured hot path.

```csharp conceptual
public interface IStep<TState> {
    TState Folded(TState state, double value);
}

public ref struct PeakStep : IStep<double> {
    private readonly ref double peak;

    public PeakStep(ref double peak) => this.peak = ref peak;

    public void operator +=(double value) => peak = double.Max(peak, value);

    public double Folded(double state, double value) { this += value; return peak; }
}

public readonly ref struct Frame(ReadOnlySpan<double> values) {
    private readonly ReadOnlySpan<double> values = values;

    public TState Fold<TState, TStep>(TState seed, scoped ref TStep step)
        where TStep : IStep<TState>, allows ref struct {
        var current = seed;
        foreach (var value in values) {
            current = step.Folded(current, value);
        }
        return current;
    }
}
```

[TEXT_LITERAL_SITE]:
- Use when: structured text or a terminal sequence is stated as a literal instead of assembled at runtime.
- Accept: a raw string literal for embedded structure and an interpolated raw literal `$$"""..."""` whose doubled `{{` braces let the embedded grammar keep its own single braces; `\e` for a terminal escape in a processed string; full expression grammar inside an interpolation hole — a method call `{{int.Max(count, 0)}}` in a doubled-brace raw hole, an alignment-plus-format specifier `{weight,-8:F2}` in a single-brace processed hole.
- Reject: an escape-laden `+` concatenation, `string.Format` with positional `{0}` holes for a local interpolation, a `StringBuilder` for a fixed-shape literal, and the `\x1b` magic literal where `\e` names the escape.
- Boundary: UTF-8 wire constants (`u8`), span and `IFormattable` formatting, and grammar compilation are `system-apis.md`'s; a raw string literal does not process escapes, so a terminal sequence stays in a processed (non-raw) string and never inside the `"""..."""` fence.

The form spotlight: a processed interpolated string carries the `\e` terminal escape — illegal in a raw literal, which would emit the backslash verbatim — beside its `{weight,-8:F2}` alignment-plus-format hole, while the sibling `$$"""..."""` raw literal embeds JSON whose own single braces survive because the interpolation marker is doubled, its `{{int.Max(count, 0)}}` hole running full expression grammar with no quote juggling. The deleted forms are a `"[1m" + body + "[0m"` concatenation and a `string.Format("{{ \"key\": \"{0}\" }}", key)` whose escaped braces and positional holes the two literal forms replace.

```csharp conceptual
public static class Manifest {
    public static string Highlighted(string body, double weight) => $"\e[1m{body.Trim()}\e[0m {weight,-8:F2}";

    public static string Of(string key, int count) => $$"""
        {
          "key": "{{key}}",
          "count": {{int.Max(count, 0)}}
        }
        """;
}
```

## [04]-[FORM_COLLAPSE_TESTS]

Run each test before keeping a local construct beside the language form that subsumes it; the chooser names the form, these name the smell that proves the form was missed.

[FORWARDING_REPAIR]:
- Smell: a wrapper type, a static helper class with a receiver-first parameter, a backing field serving one accessor, or a hand-written `Equals`/`GetHashCode` exists only to attach behavior or identity to a shape the language already carries.
- Collapse: move the behavior into an `extension(Receiver)` block, the invariant into a `field` accessor, and the identity into the `record`'s structural equality or the `boundaries.md` content key.
- Done when: callers reach the member on the receiver directly, the accessor owns its invariant with no second field, and no equality method is hand-written on inert data.

[BRANCH_REPAIR]:
- Smell: an `if`/`else` ladder, a statement switch, a comparison chain, or an `as`-plus-null-check decides a value or probes a shape the structural patterns express as one total expression.
- Collapse: state the decision as one switch expression over list, slice, relational, logical, property, and positional patterns; route a closed-owner discriminant through its generated `Switch`.
- Done when: the decision is one expression, every arm binds with `var`, and a missing case of a closed owner breaks the build rather than falling to a `_` arm.

[COPY_REPAIR]:
- Smell: a `new[]` plus `Concat` chain, a list-add sequence, a manual `.AsSpan()` adapter, or a per-arity overload family composes a value the collection-expression and C# 14 span-conversion forms compose in one literal.
- Collapse: build the value with a collection expression and spread, absorb arity with one `params ReadOnlySpan<T>`, and let the implicit array-to-span conversion feed the span receiver.
- Done when: composition is one bracketed literal, one signature serves every call arity, and no adapter overload survives the implicit conversion.

[KERNEL_REPAIR]:
- Smell: a measured loop boxes a stack-only value through an interface conversion, threads a heap `Func<,>` accumulator, or duplicates a span path into a boxed one because the type parameter forbids a `ref struct`.
- Collapse: bind the contract with a `ref struct` implementing the interface, admit the step through an `allows ref struct` type parameter, and carry running state in a `scoped ref` field so the fold runs allocation-free.
- Done when: the kernel allocates nothing per element, the `foreach` is confined to the kernel body, and the public edge returns an ordinary value or rail with no `ref struct` crossing `await` or `yield`.
