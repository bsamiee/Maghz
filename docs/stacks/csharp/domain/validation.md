# [VALIDATION]

External input crosses one seam in one order — raw shape materialized fail-closed, one boundary validator per shape, one rail projection, generated-owner admission — and every stage's output is a type, so the order is enforced by signatures, never discipline. One `AbstractValidator<T>` owns each boundary shape's whole rule graph as inspectable data: severity, applicability, variant membership, composition, order dependence, and abort policy are declared values, and the only executable fragments are predicates and providers. One generic bridge projects every outcome onto the typed rail through a severity partition and a three-tier fault mint; `ErrorCode` is one symbol serving rail dispatch, wire identity, and message lookup; accumulation is selected by the seam row's structure — independent facts accumulate, sequenced mounts abort — never by a framework flag. Every open registration surface — ruleset names, runtime-type tables, member coverage, row pairing, code maps — is proven total at composition by one fold whose failure is a typed rejection. Growth lands as rows: a new wire shape or options record is a validator row plus an admission expression, a new variant is a ruleset row, and a new fault is a code row plus a map row.

## [01]-[VALIDATION_CHOOSER]

This table routes a validation concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                 | [OWNER]                                       | [REJECTED_FORM]                  |
| :-----: | :------------------------ | :-------------------------------------------- | :------------------------------- |
|  [01]   | boundary shape rules      | one `AbstractValidator<T>` per shape          | per-variant subclass family      |
|  [02]   | seam governance           | matrix row: owner, carrier, trigger, override | ambient auto-validation          |
|  [03]   | recurring predicate       | named `PropertyValidator<T,TProperty>`        | repeated `Must` lambdas          |
|  [04]   | seam variant              | ruleset row on the one owner                  | sibling validator per surface    |
|  [05]   | abort versus accumulate   | cascade per chain, carrier per row            | boolean strict-mode flag         |
|  [06]   | outcome projection        | one severity-partition bridge                 | per-seam mapping switch          |
|  [07]   | fault identity            | pinned `ErrorCode` band                       | message-text dispatch            |
|  [08]   | options shape             | rule graph + `IValidateOptions<T>` projection | second validation path           |
|  [09]   | open registration surface | closure-proof fold at boot                    | runtime-discovery trust          |
|  [10]   | domain semantics          | generated-owner admission                     | boundary re-check of owner facts |

## [02]-[RULE_GRAPH]

[GRAPH_OWNER]:
- Law: one `AbstractValidator<T>` owns one boundary shape's rule graph, and the graph is data — the owner implements `IValidator<T>` and `IEnumerable<IValidationRule>` at once, so the declaration that validates also enumerates for proofs.
- Law: rules execute in declaration order and failures append in run order — reordering declarations is a behavior change, because class-level stop, dependent facts, and outcome order are all functions of source position.
- Law: rules validate, never reshape — value pre-shaping belongs to materialization and a mutating `Must` is a defect; `PreValidate` is the one whole-payload precondition seat, and `OnRuleAdded` applies one uniform policy across every derived declaration.
- Law: the validator never models root absence — a null root throws before any rule runs, so absence resolves at the seam and the graph's domain is always a present raw value.
- Accept: `InlineValidator<T>` as a `static readonly` collection-initializer owner for a dependency-free leaf shape — each `Add` lambda must return the attached chain, so a bare rule with no validator is unrepresentable in initializer form.
- Reject: hand `if` chains before mapping, per-variant subclasses, and boolean strict-mode parameters threaded into validators — conditions, rulesets, and severity providers are those axes as graph data.
- Exemption: the validator constructor is the rule-registration body — its declaration statements are the platform-forced seam.

[CASCADE_AND_CONDITIONS]:
- Law: cascade is a 2x2 policy matrix — `ClassLevelCascadeMode` between rules, `RuleLevelCascadeMode` within one chain — and `Continue` between rules beside `Stop` within chains is abort-versus-accumulate inside one validator with zero branching.
- Law: both cascade properties are delegate-backed reads resolved at validation time, `.Cascade(mode)` must be the first call in a chain, and class-level `Stop` samples the failure count around each whole rule, so a multi-failure rule completes its own accumulation before the break.
- Law: chain conditions default to `ApplyConditionTo.AllValidators` — the predicate guards every validator already attached, and guarding only the adjacent one requires `ApplyConditionTo.CurrentValidator`; this default is the most common silent-scope defect in rule graphs.
- Law: a validator-level `When` block predicate evaluates once per root instance and is memoized on the context across every rule in the block; every condition form has a `(T, ValidationContext<T>)` overload, so run policy reads `RootContextData`, never captured fields.
- Law: `DependentRules` runs nested rules only when the parent chain passed — the declaration-order spelling of no-cross-field-facts-over-broken-parts inside an accumulating validator; `RuleForEach(...).Where(predicate)` makes element applicability graph data, never an `if` inside `Must`.

[RULE_VOCABULARY]:
- Law: presence and shape are separately declared concerns — every built-in except `NotNull`/`NotEmpty` and the inverse pair passes a null value, so a shape rule on an optional field never doubles as a presence rule; the `Matches(Func<T, string>)` provider whose pattern resolves per instance guards only present values, so pattern-by-policy never doubles as presence, and `NotEmpty` rejecting `default(TProperty)` under default equality is a default-sentinel gate on value types, never a string rule.
- Law: a recurring predicate spelled as `Must` forfeits stable code, default message, and localization in one stroke — a named `PropertyValidator<T,TProperty>` derives all three from `Name` and joins the placeholder economy through `MessageFormatter.AppendArgument`; custom argument names carry a concern prefix because the namespace is flat per failure and a collision overwrites silently.
- Law: the context-arity `Must` overload reads run policy from `RootContextData`, comparison rules take member expressions so cross-field ordering is declared graph data rather than an `if`, and `Equal`/`InclusiveBetween` accept an injected comparer per rule.
- Law: severity, custom state, and code are per-component data — `WithSeverity` providers compute classification from instance, value, and run context, so one chain mints differently classified failures and a strict-mode knob is unrepresentable.
- Law: `Configure(rule => ...)` and static `Configurable(builder)` expose the underlying `IValidationRule<T,TProperty>` for policy the fluent surface cannot spell — the escape hatch closes every gap inside the graph, so no requirement justifies hand-rolled validation beside it.
- Boundary: `Custom` returns the conditions surface — message, severity, and code options do not chain after it, and everything sets on the emitted failure itself.

[VARIANTS_AND_SELECTORS]:
- Law: `RuleSet` names a seam variant and removes its rules from plain `Validate` silently — the default selector runs only rules whose set list is empty or contains `default`; `RuleSet("a,b; c", ...)` publishes one block into several variants, matched `OrdinalIgnoreCase`.
- Law: selector strategies compose as a union — properties plus rulesets widens, never narrows — and undotted `IncludeProperties` approves entire child validators; reaching into a child requires the dotted path.
- Law: `RuleSetsExecuted` is the run receipt recording selection, not success — an executed name means its rules were eligible and ran, pass/fail lives only in the failures, and merged results union receipts distinct.
- Reject: partial-as-admission — selectors exist for per-field feedback and variant routing, and only the seam row's full declared run admits.

```csharp conceptual
public sealed record RowEdit(string Key, int Rank, bool Live);
public sealed record ShapeEdit(string? Code, int Start, int End, string? Note, string? Etag, IReadOnlyList<RowEdit> Rows);

public sealed class RowLaw : AbstractValidator<RowEdit> {
    private const int RankCeiling = 9;

    public RowLaw() {
        RuleFor(row => row.Key).NotEmpty();
        RuleFor(row => row.Rank).InclusiveBetween(0, RankCeiling)
            .WithState(static (row, rank) => new Fault.Bounds(Detail: $"<{nameof(RowEdit.Rank)}:{rank}/{RankCeiling}>"));
    }
}

public sealed class KeyedPack : AbstractValidator<ShapeEdit> {
    public KeyedPack() => RuleFor(edit => edit.Code).NotEmpty().WithErrorCode("<code-key>")
        .WithState((edit, code) => new Fault.Absent(Detail: nameof(ShapeEdit.Code)));
}

public sealed class ShapeEditLaw : AbstractValidator<ShapeEdit> {
    public ShapeEditLaw() {
        ClassLevelCascadeMode = CascadeMode.Continue;
        RuleLevelCascadeMode = CascadeMode.Stop;
        Include(new KeyedPack());
        RuleFor(edit => edit.Start).GreaterThanOrEqualTo(0).WithErrorCode("<code-start>")
            .WithSeverity((edit, start, context) =>
                context.RootContextData.TryGetValue("<policy-override>", out var open) && open is true
                    ? Severity.Warning : Severity.Error)
            .LessThan(edit => edit.End).When(edit => edit.End > 0, ApplyConditionTo.CurrentValidator);
        RuleFor(edit => edit.End).Cascade(CascadeMode.Stop)
            .GreaterThan(0).WithErrorCode("<code-end>")
            .DependentRules(() => RuleFor(edit => edit.Note).MaximumLength(64));
        When(edit => edit.Rows is { Count: > 0 }, () =>
            RuleForEach(edit => edit.Rows).Where(row => row.Live)
                .OverrideIndexer((edit, rows, row, index) => $"[{row.Key}]")
                .SetValidator(new RowLaw()));
        RuleSet("<variant-submit>", () => RuleFor(edit => edit.End)
            .Must((edit, end, context) => !context.RootContextData.ContainsKey("<strict>") || end <= 256)
            .WithErrorCode("<code-strict>"));
    }
}
```

## [03]-[COMPOSITION_DISCOVERY]

[CHILD_AND_PACKS]:
- Law: `SetValidator` carries no implicit `NotNull` — the child adaptor skips silently on a null property and on a null resolved validator, so required children pair `NotNull().SetValidator(...)` explicitly and silence can only ever mean legally absent.
- Law: a failing child never trips rule-level cascade in the parent chain — child failures land in the shared list while the adaptor's own verdict is success, and the child run shares failure list, root data, and formatter while extending the property chain mechanically.
- Law: the `ruleSets` tail on `SetValidator` swaps the child's selector for exactly those names, `ChildRules` re-applies the parent's rulesets at any nesting depth, and `Include` splices a rule pack over the same `T` as a first-class rule under the including validator's cascade.
- Law: the `SetInheritanceValidator` table matches `value.GetType()` exactly — no hierarchy walk — so an unregistered leaf passes silently and the closure sweep over a closed enumerable family is the only barrier; polymorphic validation over an open hierarchy is rejected outright.
- Law: the polymorphic table populates as one fold over the closed family's case enumeration through the protected non-generic `Add(Type, IValidator, params string[])` guarded by `CanValidateInstancesOfType` — per-leaf registration lines are the rejected form.
- Law: graph lifetimes are uniform across instance edges — a singleton parent freezes a constructor-injected child — while the provider overloads re-resolve per validation and tolerate mixing.

[ASYNC_LAW]:
- Law: async capability is a graph property enforced at run time — synchronous `Validate` over any graph containing `MustAsync`, `CustomAsync`, an async child, or an async condition throws `AsyncValidatorInvokedSynchronouslyException` naming the validator; one async rule poisons the sync path permanently, and `WhenAsync` poisons every guarded rule even when those validators are sync.
- Law: the partition is per-validator, never per-ruleset — quarantining I/O rules in a ruleset does not lift the poison, so I/O-bearing rules live in validators that only ever run async.
- Law: the async run loop checks cancellation between rules and every async primitive takes the token at the rule site — a long accumulating run aborts between rules, never mid-validator.
- Law: structure first, I/O only over structurally sound input — async existence checks sit behind `DependentRules` ordering, and the seam sequences accumulate-then-abort across carriers; cross-message facts such as idempotency, replay, and quota are not validation, and a `MustAsync` reaching into message history is a boundary violation wearing a rule's clothes.

[DISCOVERY]:
- Law: exactly one assembly scan at the composition root with the `filter` predicate as the only exclusion — registration is dual and idempotent, one `TryAddEnumerable` interface row plus one `TryAdd` concrete row sharing one lifetime, so manual lines beside a scan are drift the dedup hides.
- Law: a validator with no scoped constructor dependency registers singleton — the graph is immutable after construction and accessors compile once; the scoped default exists for injected scoped dependencies, not per-request state.
- Law: one validator class per validated shape — the scanner takes the first closed `IValidator<>` interface, so a dual-shape validator registers under one interface by enumeration order; children enter parents by constructor injection plus `SetValidator`, and the DI graph mirrors the shape graph one-to-one.
- Law: multi-module packs for one `T` resolve as `IEnumerable<IValidator<T>>` and merge through the result-combining constructor with distinct receipts; same-ownership packs prefer the `Include` spelling.
- Law: `ValidatorOptions.Global` is write-once at the composition root before any validator constructs — `PropertyNameResolver` and `DisplayNameResolver` run at `RuleFor` declaration time, so a late write has already missed every constructed rule, and the four selector factories swap partial-run policy system-wide at the same seat.

## [04]-[OUTCOME_PROJECTION]

[BRIDGE_FOLD]:
- Law: the mint targets the one canonical `Fault` `[Union]` over `Expected` that `shapes.md` owns — the root, `Aggregate`, and `Semigroup` `Combine` arrive settled, the seam re-declares nothing, and its faults are canonical cases used the way every boundary uses `Fault.Absent`: the admission band keys `Arm` for a provider-exception throw and `Foreign` for a bridge-band foreign-origin mint, each an `IValidationError<TCase>` the generator targets, and `[ValidationError<Fault>]` on a generated owner routes its `Validate` into the same family with no second error type.
- Law: one generic bridge per system — never per boundary — and its input is `IEnumerable<ValidationFailure>`, not `ValidationResult`: validator results, foreign-adapter payloads, and hand-built arm failures enter one identical fold, so transport never forks the projection.
- Law: `IsValid` is severity-blind — `Errors.Count == 0` — so reading it in bridge code turns advisories into rejections; the `Severity` partition is the only verdict, the `Error` band gates, and the `Warning`/`Info` bands ride the success value as evidence.
- Law: the mint is a three-tier cascade — `CustomState` holding a fault-family case is taken as-is after a pattern test, so a foreign state value falls through rather than poisoning the rail; otherwise `ErrorCode` keys a frozen code-to-case map; otherwise the string tier preserves code, path, and message inside the reserved bridge band.
- Law: tier economics are monotone — tier 1 costs one provider per rule and zero bridge maintenance, tier 2 one frozen row plus one sweep entry, tier 3 nothing locally — so bridge-side mapping growth is the metric flagging rules that should mint their own faults, and a mature boundary converges tier-1-dominant.
- Law: a foreign validation source enters by mapping to the seven-field failure shape under three fail-closed defaults — unknown severity gates as `Error`, a missing code mints in the bridge band, a missing path maps to the root path, never an invented field name.
- Law: the gating partition folds through the fault family's own `Semigroup` `Combine`, never a flatten to bare `Error` — every minted case stays a typed, addressable member of one aggregate case, so the rail page's accumulation law lands at the projection seam with zero positional reconstruction; widening to `Error` happens once, at the carrier's failure slot, after the typed fold completes.
- Reject: throw-and-catch into the rail, message-text dispatch, dropping the riding bands at the bridge, `CustomState` as a grab-bag of strings and tuples (tier 1 works only when state is a fault-family case), and folding the gating partition through `+` on `Error` where the typed `Combine` preserves every member.

[EVIDENCE_RECORD]:
- Law: `ValidationFailure` is a seven-field evidence record with fixed projection roles — `ErrorCode` identity, `PropertyName` the machine path, `Severity` the band, `CustomState` the typed side channel, `FormattedMessagePlaceholderValues` the re-render capital, `ErrorMessage` display residue, `AttemptedValue` raw evidence under the classification obligation before any export-facing projection — and the departing wire fault is the four culture-invariant fields (code, path, severity, placeholder values), so `AttemptedValue`, `CustomState`, and rendered text never cross a process and the receiver re-renders from code plus placeholders under its own culture.
- Law: `OverridePropertyName` rewrites the projection key while `WithName` rewrites only the display name, and `{PropertyName}` renders the display name while the failure keeps the invariant path whose process-global `PropertyChainSeparator` freezes once any path persists — confusing the two surfaces is the canonical projection bug in both directions.
- Law: evidence rides forward only — a riding finding is never re-promoted into a gating fault downstream; blocking on a `Warning` is a different seam policy landing in the seam row or the severity selection, never a re-classification after admission.
- Law: gates are derived data — the validation-to-save verdict recomputes from the outcome value and carries its blocking faults, so explanation and enforcement cannot disagree, and multi-seam gates fold monoidally under a declared combine policy.
- Law: failure order is run order — deterministic for a given graph — so projected fault order reproduces without sorting; `ToDictionary()` and `ToString()` are terminal display projections that discard code, severity, and placeholders.

[CODE_AND_LOCALIZATION]:
- Law: `ErrorCode` is one symbol with three derived surfaces — tier-2 rail dispatch, wire identity, code-first message lookup — so one translation registered under a code re-messages every carrying rule, and any second naming axis is derived presentation reconstructible from code plus placeholders.
- Law: codes default to the failing validator's `Name` through `ValidatorOptions.Global.ErrorCodeResolver` — one process-wide mint that follows class renames silently, so any code that crosses a process or persists is pinned with `WithErrorCode` or a `Name` constant, and its template registers through `LanguageManager.AddTranslation(language, code, template)` — a pinned code without its template falls back to the validator-name lookup, half a registration.
- Law: bands allocate per bounded context and concern so band arithmetic locates the owner without lookup; one band is reserved for bridge minting so unknown-origin faults cannot masquerade as domain rejections, and an unrecognized code degrades losslessly to tier 3 with the code preserved.
- Law: `FormattedMessagePlaceholderValues` is the durable record — persisting `ErrorMessage` freezes one culture into storage, the placeholder dictionary exists to prevent exactly that drift, and placeholder format specifiers render under the ambient culture even when `LanguageManager.Culture` is pinned, so per-user rendering passes its culture to `GetString(key, culture)` at the display edge and `MessageFormatterFactory` is the system-wide repair for placeholder formatting.
- Law: unresolved placeholders pass through verbatim — a typo'd hole renders as literal braces instead of throwing, so template defects are invisible at run time and only rendered-output proofs catch them.

```csharp conceptual
public sealed record Admitted<TShape>(TShape Value, Seq<WireFault> Riding);

public sealed record WireFault(string Code, string Path, Severity Severity, IReadOnlyDictionary<string, object> Holes);

public static class Bridge {
    // tier 2 maps only codes a case recovers from code-plus-path alone; a payload-bearing fault rides tier-1 WithState, and the empty map row is the metric flagging a rule that should mint its own fault.
    private static readonly FrozenDictionary<string, Func<ValidationFailure, Fault>> Cases =
        new Dictionary<string, Func<ValidationFailure, Fault>>(StringComparer.Ordinal) {
            ["NotEmptyValidator"] = static failure => new Fault.Absent(Detail: failure.PropertyName),
            ["<code-start>"]      = static failure => new Fault.Absent(Detail: failure.PropertyName),
        }.ToFrozenDictionary(StringComparer.Ordinal);

    public static Seq<string> Codes => toSeq(Cases.Keys);

    public static Validation<Error, Admitted<TShape>> Project<TShape>(TShape value, IEnumerable<ValidationFailure> outcome) =>
        toSeq(outcome).Partition(static f => f.Severity is Severity.Error) is var (gating, riding) && gating.IsEmpty
            ? new Admitted<TShape>(value, riding.Map(Departing).Strict())
            : Minted(gating);

    public static Error Minted(Seq<ValidationFailure> gating) =>
        reduce(gating.Map(Mint), static (folded, fault) => folded.Combine(fault));

    public static WireFault Departing(ValidationFailure failure) =>
        new(failure.ErrorCode ?? "<uncoded>", failure.PropertyName, failure.Severity, failure.FormattedMessagePlaceholderValues);

    private static Fault Mint(ValidationFailure failure) => failure switch {
        { CustomState: Fault typed } => typed,
        { ErrorCode: { } code } when Cases.TryGetValue(code, out var mint) => mint(failure),
        _ => new Fault.Foreign(failure.ErrorCode ?? "<uncoded>", failure.PropertyName, failure.ErrorMessage),
    };
}
```

## [05]-[SEAM_LAW]

[ADMISSION_ORDER]:
- Law: one order at every seam — raw-shape materialization fail-closed, boundary validator, one rail projection, generated-owner admission — with each stage consuming the prior stage's success type, so a skipped stage is a type error.
- Law: stage responsibilities are exclusive — the boundary validator never constructs domain types and never duplicates a generated owner's invariant, the owner never re-checks structural facts, and the split rule is total: facts statable over the raw DTO alone are stage 2, facts defining the domain value are stage 4.
- Law: stage 2 is the last point raw input is observable — diagnostic capture happens there under the classification policy or not at all; stage 2 runs on raw optionals, so presence is declared where required and legal absence flows as success into option-typed stage-4 admission.
- Law: validation is an explicit pipeline step invoked by the seam's composition — ambient framework auto-validation hides the admission point, runs async graphs synchronously, and detaches the outcome from the rail.
- Law: any interior `IsValid` probe, defensive null test on an admitted value, or second validator invocation is proof the seam leaked — the repair moves the missed fact into stage 2 or stage 4, never adds a checkpoint; cross-process, admission-once is per trust boundary, and a shared compiled contract shrinks the order to stage 1, never bypasses it.
- Reject: validate-after-construct, dual admission of one fact in two stages, and `ValidateAndThrow` as a seam mechanism — the exception erases the accumulate/abort distinction, and its only legal seat is the final adapter to a foreign surface that speaks exceptions.

[SEAM_ROWS]:
- Law: one matrix at the composition root assigns every ingress exactly one owner, carrier, trigger, and override policy — a seam absent from the matrix is an unguarded ingress, a validator no row claims is dead admission code, and the driver is row-generic through the untyped `IValidator.Validate(IValidationContext)` contract with the payload type selecting the row.
- Law: triggers close at three — at-boot, per-message, per-batch; per-read and per-render are validate-on-read wearing a trigger's name.
- Law: carrier is selected by row structure — independent facts accumulate on the applicative carrier, sequenced mounts abort on the fail-fast carrier, and mixed seams accumulate structure fully before aborting into the I/O-or-domain step — so the row's bridge target makes failure semantics readable without opening a validator; a dependent chain deeper than two steps inside an accumulating validator is a mount sequence wearing validation's clothes.
- Law: per-field interactive runs and whole-shape admission are the same validator under different selectors — two rule graphs for one shape is the rejected form — and edit surfaces construct the same DTOs through the same fail-closed materialization; environmental leniency is a ruleset or severity variant on the one validator, never a swapped graph.
- Law: egress has no row — interior totality makes outputs valid by construction, and an egress validator is a symptom report routed to the leaking constructor; per-record skip under bulk import is a receipted outcome on the rail, with admitted, skipped, and aborted counts as one batch value.
- Law: the full declared run mints the admission record — seam identity, executed-variant receipt, override policy in force — so admission is a one-field query, and the record is an ordinary fact on the operational stream under telemetry governance.

[ARM_AND_OVERRIDE]:
- Law: each seam owns one provider-exception arm where deserializer, binder, and transport throws become the same fault stream stage 2 feeds — malformed syntax, unknown member, and type mismatch are one vocabulary distinguished by code, and arm faults carry the seam identity, so which provider failed where is recoverable from the fault alone.
- Law: the null-root `InvalidOperationException` and the sync-over-async throw are composition defects, never seam outcomes — converting them disguises a wiring bug as a data bug, and they fail fast at the seam's first exercise.
- Law: a forced override re-runs the same graph under a policy that downgrades the gating tier to a recorded tier — identical failures still mint, still cross the bridge, and no longer block — and permission is a conjunction of the row's override column and the code band's eligibility, so neither a permissive seam nor a permissive code alone opens the gate.
- Reject: skipping the validator under override, and post-hoc deletion of failures from an outcome — both are evidence tampering; the partition belongs to the projection, not the seam.
- Exemption: the context-preparation kernel — strategy construction, the `RootContextData` policy write, and the run — is the platform-forced mutable-context seam.

```csharp conceptual
[SmartEnum]
public sealed partial class Trigger {
    public static readonly Trigger AtBoot = new();
    public static readonly Trigger PerMessage = new();
    public static readonly Trigger PerBatch = new();
}

[ValueObject<string>]
[ValidationError<Fault>]
public readonly partial struct MarkValue;

public sealed record AdmissionRecord(string Row, Seq<string> Executed, bool OverrideOpen);
public sealed record SeamRow(string Name, Type Payload, IValidator Owner, Trigger Trigger, Seq<string> Variants, bool OverrideOpen);

public static class Seam {
    public static readonly Seq<SeamRow> Matrix =
        [new("<seam-edit>", typeof(ShapeEdit), new ShapeEditLaw(), Trigger.PerMessage, ["<variant-submit>"], OverrideOpen: false)];

    public static Validation<Error, (Admitted<TShape> Shape, AdmissionRecord Receipt)> Admit<TShape>(Func<TShape> decode) where TShape : notnull =>
        Matrix.Find(row => row.Payload == typeof(TShape) && row.Owner.CanValidateInstancesOfType(typeof(TShape)))
            .ToValidation((Error)new Fault.Arm("<matrix>", $"<unguarded:{typeof(TShape).Name}>"))
            .Bind(row => Try.lift(decode).Run().Match<Validation<Error, (Admitted<TShape>, AdmissionRecord)>>(
                Succ: shape => Projected(row, shape),
                Fail: error => Bridge.Minted([new ValidationFailure(propertyName: "", errorMessage: error.Message) {
                    ErrorCode = "<code-arm>", Severity = Severity.Error, CustomState = new Fault.Arm(row.Name, error.Message),
                }])));

    public static Validation<Error, MarkValue> Owned(Func<ShapeEdit> decode) =>
        Admit(decode).Bind(static pair =>
            MarkValue.Validate(pair.Shape.Value.Code, null, out var owned) is { } fault
                ? (Validation<Error, MarkValue>)fault
                : owned);

    private static Validation<Error, (Admitted<TShape>, AdmissionRecord)> Projected<TShape>(SeamRow row, TShape shape) where TShape : notnull {
        var context = ValidationContext<object>.CreateWithOptions(shape, strategy => strategy.IncludeRulesNotInRuleSet().IncludeRuleSets([.. row.Variants]));
        context.RootContextData["<policy-override>"] = row.OverrideOpen;
        var outcome = row.Owner.Validate(context);
        return Bridge.Project(shape, outcome.Errors)
            .Map(admitted => (admitted, new AdmissionRecord(row.Name, toSeq(outcome.RuleSetsExecuted), row.OverrideOpen)));
    }
}
```

[CLOSURE_PROOFS]:
- Law: every string-keyed or runtime-type-keyed registration surface at a validation seam is proven total at composition by one four-step fold — enumerate the source, enumerate the registration, assert bijection or declared exemption, reject typed — and a new proof candidate is a new instance row of the same fold.
- Law: the per-row proofs drive off the seam matrix through the non-generic `IValidatorDescriptor.Rules` and `GetMembersWithValidators()`, the variant axis read off each rule's `IValidationRule.RuleSets` — so heterogeneous rows prove under one spelling and a new seam row buys its variant and member proofs with zero proof edits.
- Law: the instances close the package's fail-open paths — the polymorphic table swept against the closed family's case enumeration, each row's graph rulesets against its variant column in both directions closing the default-selector hole, each row's payload members against rule coverage plus exemptions so shape growth cannot outrun rule growth, seam rows against scan results in both directions, and the bridge's code map against the declared code vocabulary.
- Law: proofs are deterministic folds over already-materialized metadata — one enumeration at boot, structurally incapable of scaling with traffic — and a proof failure is a typed fault in the capability band, so boot failures and message-time rejections fold into one stream.
- Law: the swept vocabularies, exemption lists, and matrix rows are the seam documentation — drift is structurally impossible because the document is the data the proof reads, and the opt-out registry is itself swept, so a permissive row whose seam no longer exists is dead policy caught at boot.
- Law: fail-closed is the one default across every admission surface — unknown configuration keys, unknown wire members, undefined enum bits including flag combinations, unregistered cases — and a permissive row is earned only where unknown input is provably non-actionable and the row is enumerable by the proofs.

```csharp conceptual
public sealed record SeamVocabulary(Seq<string> Codes, Seq<string> MemberExempt, Seq<string> PairingExempt);

public static class ClosureProofs {
    public static Validation<Error, Unit> Prove(Seq<SeamRow> matrix, SeamVocabulary declared) {
        ArgumentNullException.ThrowIfNull(declared);
        return (matrix.Traverse(row => RowClosed(row, declared.MemberExempt)).As().Map(static _ => unit),
            Closed("<pairing>", Gap(matrix.Map(static row => row.Payload.Name),
                toSeq(AssemblyScanner.FindValidatorsInAssembly(typeof(ShapeEditLaw).Assembly))
                    .Map(static hit => hit.InterfaceType.GenericTypeArguments[0].Name), declared.PairingExempt)),
            Closed("<codes>", Gap(declared.Codes, Bridge.Codes, [])))
            .Apply(static (_, _, _) => unit).As();
    }

    private static Validation<Error, Unit> RowClosed(SeamRow row, Seq<string> memberExempt) =>
        row.Owner.CreateDescriptor() switch {
            var graph => (
                Closed($"<variants:{row.Name}>", Gap(
                    toSeq(graph.Rules).Bind(static rule => toSeq(rule.RuleSets)).Distinct(), row.Variants, ["default"])),
                Closed($"<members:{row.Name}>", Gap(
                    toSeq(row.Payload.GetProperties()).Map(static member => member.Name),
                    toSeq(graph.GetMembersWithValidators()).Map(static group => group.Key), memberExempt)))
                .Apply(static (_, _) => unit).As(),
        };

    private static (Seq<string> Open, Seq<string> Phantom) Gap(Seq<string> source, Seq<string> registered, Seq<string> exempt) => (
        source.Filter(key => !registered.Exists(held => held == key) && !exempt.Exists(held => held == key)),
        registered.Filter(key => !source.Exists(held => held == key) && !exempt.Exists(held => held == key)));

    private static Validation<Error, Unit> Closed(string axis, (Seq<string> Open, Seq<string> Phantom) gap) =>
        gap is { Open.IsEmpty: true, Phantom.IsEmpty: true }
            ? unit
            : new Fault.Foreign("<closure>", axis, $"open={gap.Open} phantom={gap.Phantom}");
}
```

## [06]-[OPTIONS_SEAM]

[DUAL_PROJECTION]:
- Law: the options-shape rule graph is the single shape authority for facts beyond annotation reach, and the options-validation contract is a thin projection of it — the `IValidateOptions<T>` adapter projects gating messages into the host's start gate while the bridge projects the same outcome onto the rail; the adapter never becomes a second validation path.
- Law: the contract is synchronous, so options validators are sync-rule-only by law — an async rule throws at first resolution, self-enforcing under the eager gate.
- Law: named options validate per name through the contract's name parameter — one validator covers every named instance, and a name-specific fact is a context condition, never a second validator.
- Law: the options validator observes, never repairs — a rule that normalizes or defaults a bound value has smuggled configuration logic into validation, and the repair belongs to the binding or defaulting layer.
- Boundary: binder fail-closed policy, the eager-start trigger, and frozen publish are runtime law — this seam owns the rule graph and the two projections it feeds, and a changed source is a new admission, never a silent mutation of published policy.
- Exemption: the per-name context preparation is the platform-forced mutable-context seam.

```csharp conceptual
public sealed record OptionsShape {
    public int Width { get; init; } = 4;
    public int Span { get; init; }
    public string Label { get; init; } = "<value-a>";
}

public sealed class OptionsLaw : AbstractValidator<OptionsShape> {
    public OptionsLaw() {
        RuleFor(shape => shape.Span).LessThanOrEqualTo(shape => shape.Width * 8).WithErrorCode("<code-span>");
        RuleFor(shape => shape.Label).NotEmpty().Must(static (shape, label, context) =>
            context.RootContextData["<name>"] is not "<name-strict>" || label.Length <= 8);
    }
}

public sealed class OptionsGate(OptionsLaw law) : IValidateOptions<OptionsShape> {
    public ValidateOptionsResult Validate(string? name, OptionsShape options) =>
        Outcome(name, options).Filter(static failure => failure.Severity is Severity.Error) is { IsEmpty: false } gating
            ? ValidateOptionsResult.Fail(gating.Map(static f => $"{f.ErrorCode}:{f.PropertyName}:{f.ErrorMessage}"))
            : ValidateOptionsResult.Success;

    public Validation<Error, Admitted<OptionsShape>> Rail(OptionsShape options) =>
        Bridge.Project(options, Outcome(name: null, options));

    private Seq<ValidationFailure> Outcome(string? name, OptionsShape options) {
        var context = new ValidationContext<OptionsShape>(options);
        context.RootContextData["<name>"] = name ?? Options.DefaultName;
        return toSeq(law.Validate(context).Errors);
    }
}
```
