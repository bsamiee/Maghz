# [COMPUTE]

Compute is one measured engine. A typed intent admits once — shape, dtype row, canonical units — routes through one benchmark-gated substrate fold whose caps derive from the settled budget record, executes on a budgeted lane, and exits as a typed route receipt carrying the taken row, every vetoed row with its reason, and dual evidence for every normalizing admission. Tensors are one owner with two view polarities over three memory gates; staging memory is a closed five-class allocation axis; byte payloads ride one process stream pool whose events fold to a conservation ledger; inference is a fingerprinted session plus a residency lattice where copies are legal at exactly two named points; physical numerics convert exactly once at admission. Growth lands as rows: a new memory source is a gate row, a new accelerator a residency row, a new fast path a claim row, a new op family an intent case.

## [01]-[COMPUTE_CHOOSER]

This table routes a compute concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                     | [OWNER]                            | [REJECTED_FORM]                |
| :-----: | :---------------------------- | :--------------------------------- | :----------------------------- |
|  [01]   | rank-N numeric payload        | `Tensor<T>` + span views           | local NDArray wrapper          |
|  [02]   | flat numeric kernel           | `TensorPrimitives` kernel row      | element loop                   |
|  [03]   | scratch and staging buffers   | five-class allocation row          | `new T[]` per request          |
|  [04]   | byte payloads across IO seams | one process stream pool            | raw growable `MemoryStream`    |
|  [05]   | model execution               | fingerprinted session + `OrtValue` | per-call dictionary marshal    |
|  [06]   | repeated same-shape inference | `OrtIoBinding` loop posture        | name-array re-marshal per call |
|  [07]   | route selection               | substrate fold + claim gate        | literal fast-path branch       |
|  [08]   | parallel kernel               | `ParallelHelper` behind a claim    | unbudgeted parallel loop       |
|  [09]   | compute evidence              | typed route receipt                | generic ledger                 |
|  [10]   | physical numerics             | quantity admission + dual evidence | literal conversion factor      |

## [02]-[TENSOR_LAW]

[VIEW_ALGEBRA]:
- Law: `Tensor<T>` is the sole rank-N owner, `TensorSpan<T>`/`ReadOnlyTensorSpan<T>` the two view polarities, `TensorDimensionSpan<T>` the per-dimension cursor — kernels take `in ReadOnlyTensorSpan<T>` and write `in TensorSpan<T>`, every composition member carries a destination overload beside its allocating form so owned-buffer pipelines never allocate, and an API that retains tensor data retains the owner and re-projects per use — a cached span is the foreclosed defect, so every interior surface is projection-blind to where memory came from.
- Law: three gates admit every memory class — `Tensor.CreateFromShape` owns allocation with residency decided there (`pinned: true` plus `GetPinnedHandle()` serves native seams, and `CreateFromShapeUninitialized` is legal only under a provable full-coverage write plan before first read), the `TensorSpan<T>` constructors and `AsTensorSpan` carry lengths and strides onto arrays and spans, and `TensorMarshal.CreateReadOnlyTensorSpan` admits ref-rooted foreign memory — pooled planes, model outputs — whose lifetime is the caller's proof obligation; a new memory source is one gate-row decision, zero new types.
- Law: `Slice` shares storage with adjusted strides and never copies; `NRange`/`NIndex` carry `^`/`..` addressing at native width, and shape extents are `nint` — `int`-typed shape plumbing silently truncates.
- Law: layout is a queryable class — `IsDense` reports it, `TryGetSpan` gates the dense fast path and fails across stride discontinuities, `FlattenTo` is the strided-to-linear bridge, and `ToDenseTensor()` returns `this` on dense input, so an independent buffer is `CreateFromShape` plus `CopyTo`, never a defensive copy.
- Law: broadcast materializes at the broadcast shape — `Tensor.Broadcast` validates, allocates, and copies — so scalar operands ride the scalar-position kernel overloads, never a manufactured constant tensor.
- Law: `==` on a view is view identity; content equality is `Tensor.SequenceEqual` (shape plus content) or `Tensor.EqualsAll` element-wise — `==` where content is meant compiles and compares the wrong thing.
- Reject: a local NDArray or matrix wrapper — it re-derives the shape math `TensorShape` already owns, however thin it is.
- Exemption: the dense-probe routing kernel is the named statement seam.

```csharp conceptual
public static class TensorGate {
    public static Fin<Tensor<double>> Admit(ReadOnlySpan<double> payload, params ReadOnlySpan<nint> shape) =>
        TensorPrimitives.Product(shape) is var volume && volume == payload.Length
            ? Fin.Succ(Covered(payload, shape))
            : Fin.Fail<Tensor<double>>(Error.New(8101, $"<cover-gap:{payload.Length}:{volume}>"));

    public static ReadOnlyTensorSpan<double> Mapped(Span<double> plane, params ReadOnlySpan<nint> shape) =>
        TensorMarshal.CreateReadOnlyTensorSpan(ref MemoryMarshal.GetReference(plane), plane.Length, shape, [], pinned: false);

    public static void Banded(in ReadOnlyTensorSpan<double> view, NRange rows, NRange columns, double gain, in TensorSpan<double> destination) =>
        Tensor.Multiply(view.Slice([rows, columns]), gain, destination);

    public static double Massed(scoped in ReadOnlyTensorSpan<double> view, Span<double> scratch) {
        if (view.TryGetSpan([0, 0], checked((int)view.FlattenedLength), out ReadOnlySpan<double> flat)) {
            return TensorPrimitives.Sum(flat);
        }

        view.FlattenTo(scratch);
        return TensorPrimitives.Sum(scratch[..checked((int)view.FlattenedLength)]);
    }

    static Tensor<double> Covered(ReadOnlySpan<double> payload, ReadOnlySpan<nint> shape) {
        var owner = Tensor.CreateFromShapeUninitialized<double>(shape, pinned: true);
        payload.CopyTo(owner.GetSpan(new nint[shape.Length], payload.Length));
        return owner;
    }
}
```

[KERNEL_ROWS]:
- Law: `TensorPrimitives` is one flat vocabulary whose generic-math constraint is the admission column — an inadmissible dtype-op pair is uncallable, so the dispatch table cannot hold an invalid row; arity is the only structural axis, and every binary and ternary position carries a scalar overload.
- Law: dtype rows carry acceleration classes — `Half` rides widen-to-float vector kernels, so the float proof plus one narrowing-boundary check certifies the half row, and the model-boundary brain-float carrier converts at the inference admission seam, never entering span kernels.
- Law: NaN policy is a declared column — `Min`/`Max` propagate NaN per IEEE 754:2019, `MinNumber`/`MaxNumber` treat NaN as missing data — and index searches return the first NaN's position; choosing the wrong column silently changes what a pipeline reports on dirty data.
- Law: the fused triad is a numeric contract, never a speed knob — `MultiplyAdd` permits double rounding, `FusedMultiplyAdd` guarantees single rounding including the scalar tail, `MultiplyAddEstimate` legitimately differs across machines and is inadmissible wherever cross-machine bit agreement is contractual.
- Law: in-place destinations may alias an input only at the same start — partial overlap throws — so shifting-window pipelines own a scratch span by construction; conversions are the `ConvertChecked`/`ConvertSaturating`/`ConvertTruncating` policy column.
- Law: tolerance classes close the equivalence vocabulary — exact (integer rows), ULP-banded (same-route transcendentals), accumulation-scaled (vectorized reductions reassociate, the bound scaling as N·ε·Σ|xᵢ|), platform-variant (estimate rows, no cross-machine bound exists), cross-platform-variant (C-runtime transcendentals, golden vectors banded never exact) — and the cancellation ratio |Σxᵢ|/Σ|xᵢ| decides when even the scaled bound is vacuous, so proof rows record the ratio class.
- Law: equivalence proofs sweep length classes straddling the vector width — empty, one, sub-width, exact multiple, multiple-plus-remainder — because the remainder tail executes scalar code; the empty edge is decided by its own arm before the finite gate, since `IsFiniteAll` on an empty span returns false, and integer rows skip the gate entirely.
- Law: a named kernel row is a policy value — method-group identity under `nameof` keys the proof row, the speed claim, and the receipt at once — and multi-statistic requests batch power sums: `Sum` plus `SumOfSquares` derive mean and variance in two passes, never N sweeps.
- Boundary: tensor-rank `Tensor` ops are the shape-checked composition route; a measured kernel flattens dense operands through the probe and calls the span kernel directly.
- Boundary: the `TensorPrimitives` element-kernel and `Vector<T>` mechanics are the numeric pages' substrate; this card owns the layer above them — the tolerance class, the acceleration class, and the named kernel as a claim-keying policy value — so a kernel-row table here certifies and routes element kernels it never re-derives.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class ToleranceClass {
    public static readonly ToleranceClass Exact = new("<class-a>", static (_, _) => 0.0);
    public static readonly ToleranceClass UlpBanded = new("<class-b>", static (_, mass) => Math.ScaleB(4.0, -52) * mass);
    public static readonly ToleranceClass AccumulationScaled = new("<class-c>", static (length, mass) => length * Math.ScaleB(1.0, -52) * mass);
    public static readonly ToleranceClass PlatformVariant = new("<class-d>", static (_, _) => double.PositiveInfinity);
    public static readonly ToleranceClass CrossPlatformVariant = new("<class-e>", static (_, mass) => Math.ScaleB(16.0, -52) * mass);

    [UseDelegateFromConstructor] public partial double Bound(int length, double mass);
}

[SmartEnum<string>]
public sealed partial class KernelRow {
    public static readonly KernelRow Mass = new(nameof(TensorPrimitives.Sum), ToleranceClass.AccumulationScaled, TensorPrimitives.Sum);
    public static readonly KernelRow Floor = new(nameof(TensorPrimitives.Min), ToleranceClass.Exact, TensorPrimitives.Min);
    public static readonly KernelRow DirtyFloor = new(nameof(TensorPrimitives.MinNumber), ToleranceClass.Exact, TensorPrimitives.MinNumber);
    public static readonly KernelRow Spread = new(nameof(TensorPrimitives.StdDev), ToleranceClass.AccumulationScaled, TensorPrimitives.StdDev);

    public ToleranceClass Tolerance { get; }

    [UseDelegateFromConstructor] public partial double Reduce(ReadOnlySpan<double> payload);

    public (double Bound, double CancellationRatio) Envelope(ReadOnlySpan<double> payload) =>
        TensorPrimitives.SumOfMagnitudes(payload) switch {
            var mass => (Tolerance.Bound(payload.Length, mass), Math.Abs(TensorPrimitives.Sum(payload)) / mass),
        };

    public static (double Mean, double Variance) Moments(ReadOnlySpan<double> payload) =>
        (TensorPrimitives.Sum(payload) / payload.Length) switch {
            var mean => (mean, TensorPrimitives.SumOfSquares(payload) / payload.Length - mean * mean),
        };
}
```

## [03]-[STAGING]

[CLASS_AXIS]:
- Law: five classes close the staging axis — `stackalloc` under one declared cap and never inside a loop, `SpanOwner<T>` for scoped rents of unbounded size (escape is a compile error and `Dispose` the guaranteed return), `MemoryOwner<T>` for storable rents that cross awaits, `ArrayPoolBufferWriter<T>` where the final size is unknown (`MemoryBufferWriter<T>` is the fixed-capacity sibling that fails past its window rather than renting), and the stream pool for byte payloads crossing IO and codec seams — a `new T[]` in a staging path is the unpooled, unreceipted sixth spelling.
- Law: `AllocationMode` is the rent-time reset column — pooled rents carry prior content, so trust-seam and partially-written payloads rent `Clear` while fully-overwritten payloads keep the bandwidth — and the `ArrayPool<T>` parameter isolates per-lane pools so one lane's size-class churn cannot evict another's.
- Law: `MemoryOwner<T>.Slice` is a consuming transfer — it nulls the source and exactly one owner ever returns the array; `AsStream()` transfers disposal identically, and holding both handles is the double-return defect.
- Law: the writer-then-owner handoff is the one legal two-stage lifetime — produce through `IBufferWriter<T>`, consume `WrittenMemory`, dispose after the consumer completes; `Clear()` resets the written window for reuse, and owners never reset — the pool is the reuse mechanism, so owner reuse is a new rent.
- Law: planes are projections, never reallocations — `AsMemory2D` carries (height, width) onto rented buffers, `Span2D<T>.TryGetSpan` probes contiguity routing dense planes into the tensor gate while pitched planes row-iterate `GetRowSpan`, and `Memory2D<T>.Pin()` keeps pin scope congruent with use; `AsBytes` reinterpretation demands a named codec owner at the calling rail.
- Law: `ParallelHelper.For` runs struct `IAction` rows — the action is the policy value, captured state explicit fields passed through the `in TAction` seeded overload — with `minimumActionsPerThread` flooring per-thread work off the budget record while the library clamps degree to `Environment.ProcessorCount`; parallel rows never nest (the inner floor derives as the whole length, collapsing the partition to one inline invocation), the partition pins to the pitch axis because column partitions false-share, and the parallel row stands behind the dispatch claim gate.
- Use: `ArrayPool<T>.Shared.Resize` as the one rent-copy-return verb, `DangerousGetArray()` as the one zero-copy bridge to array-demanding APIs (dead with its owner), and `StringPool.GetOrAdd` for staging labels — domain text still admits through owners; a content key over a flattened span is the `BYTE_IDENTITY` `XxHash3.HashToUInt64` codec, never a `HashCode<T>.Combine` second hash path that fragments the identity domain.
- Exemption: the rent-and-frame bodies are the platform-forced stack-discipline statement seam.

```csharp conceptual
public static class StagingAxis {
    public const int StackCap = 512;
    static readonly ArrayPool<byte> Lane = ArrayPool<byte>.Create(1 << 20, 64);

    public static TOut Framed<TOut>(int size, Func<Span<byte>, TOut> kernel) {
        ArgumentNullException.ThrowIfNull(kernel);
        using SpanOwner<byte> rent = size > StackCap ? SpanOwner<byte>.Allocate(size, Lane, AllocationMode.Clear) : SpanOwner<byte>.Empty;
        Span<byte> scratch = size > StackCap ? rent.Span : stackalloc byte[StackCap];
        return kernel(scratch[..size]);
    }

    public static MemoryOwner<byte> Admitted(int capacity, Func<Memory<byte>, int> fill) {
        ArgumentNullException.ThrowIfNull(fill);
        var staged = MemoryOwner<byte>.Allocate(capacity, AllocationMode.Clear);
        return staged.Slice(0, fill(staged.Memory));
    }

    public static IO<TOut> Produced<TOut>(Action<IBufferWriter<byte>> produce, Func<ReadOnlyMemory<byte>, TOut> consume) =>
        IO.lift(static () => new ArrayPoolBufferWriter<byte>(256)).Bracket(
            Use: writer => IO.lift(() => (fun(() => produce(writer))(), consume(writer.WrittenMemory)).Item2),
            Fin: static writer => IO.lift(fun(writer.Dispose)));
}
```

[STREAM_POOL]:
- Law: exactly one `RecyclableMemoryStreamManager` per process with `Options` frozen at construction — a second manager forks the block economy and doubles steady-state memory.
- Law: zero free-byte caps retain the high-water mark forever — bounded `MaximumSmallPoolFreeBytes`/`MaximumLargePoolFreeBytes` are the production posture, returns past the cap discard with a healthy `EnoughFree` reason, and `GenerateCallStacks`/`ZeroOutBuffer` flip only on the declared diagnostics row.
- Law: a stream lives in chained blocks until contiguity is demanded — `GetReadOnlySequence()` reads without migration and the stream is itself `IBufferWriter<byte>`, `GetBuffer()` is the contiguity cliff, `ToArray` pays migration plus copy and `ThrowExceptionOnToArray` converts that audit into a structural ban; `MaximumStreamCapacity` stops runaway producers by policy.
- Law: tags name lanes — a small closed vocabulary declared with the policy, never call sites — and the event stream folds to three projections: per-tag conservation (created = disposed + live + finalized), discard taxonomy (`EnoughFree` dominant means caps below workload, oversize discards mean payloads exceed `MaximumBufferSize` — opposite tuning moves), and lifetime-percentile early warning that predicts held-stream leaks before conservation breaks; double-dispose is data — the event carries both stacks as a protocol-violation receipt, and the posture poisons the offending lane until repaired.
- Use: `Capacity64` for long-range capacity, `SafeRead` threading position explicitly so concurrent readers never race the cursor, and `WriteTo` window copies over slicing detours.

```csharp conceptual
public readonly record struct PoolFact(string Tag, string Kind);

public sealed record PoolPolicy(int BlockSize, int LargeMultiple, int MaxBuffer, long SmallCap, long LargeCap, bool Diagnostics) {
    public static readonly PoolPolicy Production = new(131_072, 1_048_576, 134_217_728, 64L * 131_072, 8L * 1_048_576, Diagnostics: false);

    public RecyclableMemoryStreamManager.Options Frozen => new() {
        BlockSize = BlockSize, LargeBufferMultiple = LargeMultiple, MaximumBufferSize = MaxBuffer,
        MaximumSmallPoolFreeBytes = SmallCap, MaximumLargePoolFreeBytes = LargeCap,
        ThrowExceptionOnToArray = !Diagnostics, GenerateCallStacks = Diagnostics, ZeroOutBuffer = Diagnostics,
    };
}

public static class StreamPool {
    public static readonly Atom<Seq<PoolFact>> Ledger = Atom(Seq<PoolFact>());

    public static RecyclableMemoryStreamManager Open(PoolPolicy policy) {
        ArgumentNullException.ThrowIfNull(policy);
        var pool = new RecyclableMemoryStreamManager(policy.Frozen);
        pool.StreamCreated += static (_, fact) => Record(fact.Tag, "<created>");
        pool.StreamDisposed += static (_, fact) => Record(fact.Tag, "<disposed>");
        pool.StreamFinalized += static (_, fact) => Record(fact.Tag, "<finalized>");
        pool.StreamDoubleDisposed += static (_, fact) => Record(fact.Tag, "<double-return>");
        pool.BufferDiscarded += static (_, fact) => Record(fact.Tag, $"<discard:{fact.Reason}>");
        return pool;
    }

    public static bool Conserved(string tag, int live) =>
        Ledger.Value.Fold((C: 0, D: 0, F: 0), (acc, fact) => fact.Tag != tag ? acc : fact.Kind switch {
            "<created>" => (acc.C + 1, acc.D, acc.F),
            "<disposed>" => (acc.C, acc.D + 1, acc.F),
            "<finalized>" => (acc.C, acc.D, acc.F + 1),
            _ => acc,
        }) is var sum && sum.C == sum.D + live + sum.F;

    static void Record(string? tag, string kind) =>
        ignore(Ledger.Swap(facts => facts.Add(new PoolFact(tag ?? "<untagged>", kind))));
}
```

## [04]-[INFERENCE_LANE]

[VALUE_RESIDENCY]:
- Law: `OrtValue` is the sole model-boundary carrier and the lattice runs managed span → memory-backed value → device residency → output value → span view, with copies legal at exactly two points — string tensors and explicit edge export; per-call dictionary marshal and managed dense-tensor copies are the rejected rows, and a new accelerator is residency rows plus binding columns with zero loop edits.
- Law: zero-copy ingress wraps — `CreateTensorValueFromMemory` pins the backing for the value's lifetime and `CreateTensorValueFromSystemNumericsTensorObject` admits the tensor owner directly — so the backing must outlive the value and every run binding it; a pooled owner's return sequences after the value's dispose — the value's dispose IS the owner's release point, and freeing under a live value is a use-after-free in managed code.
- Law: egress is projection — `GetTensorDataAsSpan<T>`/`GetTensorMutableDataAsSpan<T>` view native buffers in place, the mutable view post-processes outputs under the same-start aliasing law before any copy, and destinations size from `GetTensorTypeAndShape().ElementCount`, never re-multiplied dimensions; result collections are deterministic-dispose native material invisible to GC heap heuristics — one dispose releases every element, and a leaked collection is a native leak no allocation profiler attributes.

[SESSION_AND_PROVIDERS]:
- Law: one session per model identity, cached process-wide; the fingerprint is the `MEMO_KEY` composite key over the `BYTE_IDENTITY` codec — the model-bytes content digest is the content axis and every behavior-bearing option column the policy axis: provider rows, optimization level, pinned free dimensions, registered assets, initializer overrides, config entries — so the model digest and the option projection ride the one canonical `XxHash3.HashToUInt64` the identity domain owns, never a second hashing path minted here; adapter variation is run-policy data (`OrtLoraAdapter` plus `RunOptions.AddActiveLoraAdapter` over one base session) whose active set joins the policy axis and every cache key, `PrePackedWeightsContainer` shares packed weights so option-variant sessions pay weight memory once, and a cache keyed on model path alone aliases behaviorally different sessions.
- Law: provider selection is policy rows in priority order through the uniform `AppendExecutionProvider(name, options)` shape; capability is probed via `OrtEnv.Instance().GetAvailableProviders()` and never assumed, a vetoed row degrades to the next with its reason in the receipt, and the CPU row is the implicit terminal.
- Law: symbolic dimensions bind at build — `AddFreeDimensionOverrideByName` plus `EnableMemoryPattern` is the fixed-shape posture, and genuinely varying shapes disable pattern reuse as a declared session column, never an accident.
- Law: warmup is admission — the golden run pays allocation and pattern cost, proves liveness, and mints the equivalence receipt; an equivalence breach refuses the session even on the terminal row, because correctness gates admission while capability only gates routing — a fast wrong model is the worst admitted object.
- Law: threading is suite policy — multi-session suites call `DisablePerSessionThreads()` and ride the global pool declared once at environment boot with counts derived from the budget record; `RunOptions.Terminate` is a one-way latch whose scope equals the instance's sharing scope, so per-run cancellation requires per-run `RunOptions`.
- Law: `ModelMetadata.CustomMetadataMap` is the artifact's self-description channel and `InputMetadata` the admission contract validated once — per-call re-validation re-derives what admission settled; deployment constants bind through `AddInitializer` against `OverridableInitializerMetadata`, never per-run inputs, and extension assets enter through `RegisterOrtExtensions()` with their hashes joining the fingerprint.
- Exemption: the admission choreography body is the platform-forced statement seam.

```csharp conceptual
public sealed record ProviderRow(string Name, Dictionary<string, string> Knobs);

public sealed record SessionPlan(ReadOnlyMemory<byte> Model, Seq<ProviderRow> Providers, Seq<(string Dim, long Extent)> Pinned, GraphOptimizationLevel Level) {
    public string Fingerprint(Seq<string> applied) =>                          // MEMO_KEY composite: model digest is the content axis seeding the policy-axis projection through the one BYTE_IDENTITY codec
        XxHash3.HashToUInt64(
            Encoding.UTF8.GetBytes(string.Join(';', applied + Pinned.Map(static pin => $"{pin.Dim}={pin.Extent}") + Seq($"level:{Level}"))),
            seed: (long)XxHash3.HashToUInt64(Model.Span))
        .ToString("x16", CultureInfo.InvariantCulture);
}

public sealed record AdmissionReceipt(string Fingerprint, Seq<string> Vetoed, Seq<string> Applied, float Defect);

public static class SessionAdmission {
    public static Fin<(InferenceSession Session, AdmissionReceipt Receipt)> Admit(SessionPlan plan, string input, string output, float[] golden, long[] shape, float[] reference, float tolerance) {
        ArgumentNullException.ThrowIfNull(plan);
        var capable = toSeq(OrtEnv.Instance().GetAvailableProviders());
        var applied = plan.Providers.Filter(row => capable.Exists(held => held == row.Name));
        var vetoed = plan.Providers.Filter(row => !capable.Exists(held => held == row.Name)).Map(static row => row.Name);
        using var options = new SessionOptions { GraphOptimizationLevel = plan.Level, EnableMemoryPattern = true };
        applied.Iter(row => options.AppendExecutionProvider(row.Name, row.Knobs));
        plan.Pinned.Iter(pin => options.AddFreeDimensionOverrideByName(pin.Dim, pin.Extent));
        InferenceSession? session = new(plan.Model.ToArray(), options);
        try {
            using var run = new RunOptions();
            using var probe = OrtValue.CreateTensorValueFromMemory(OrtMemoryInfo.DefaultInstance, golden.AsMemory(), shape);
            using var warm = session.Run(run, [input], [probe], [output]);
            var defect = TensorPrimitives.Distance<float>(warm[0].GetTensorDataAsSpan<float>(), reference);
            if (defect > tolerance) {
                return Fin.Fail<(InferenceSession, AdmissionReceipt)>(Error.New(8401, $"<warmup-defect:{defect}>"));
            }

            var receipt = new AdmissionReceipt(plan.Fingerprint(applied.Map(static row => row.Name)), vetoed, applied.Map(static row => row.Name), defect);
            var admitted = session;
            session = null;
            return Fin.Succ((admitted, receipt));
        }
        finally { session?.Dispose(); }
    }
}
```

[BINDING_AND_CACHE]:
- Law: `OrtIoBinding` is the steady-state row for repeated same-shape inference — `BindInput`/`BindOutput` once, `RunWithBinding` per call with zero marshal, `RunWithBoundResults` where outputs return as a collection — and the zero-allocation posture is four columns declared together: binding, pinned shapes, memory pattern, pre-allocated outputs (`CreateAllocatedTensorValue` sinks, inputs refreshed by span writes); any one missing reintroduces per-call cost, and the allocate-per-call spelling turns inference into a GC workload.
- Law: bound values carry shape — a shape-class transition rebinds through `ClearBoundInputs()`/`ClearBoundOutputs()`, and an unrebound transition throws or mis-executes.
- Law: `SynchronizeBoundInputs()`/`SynchronizeBoundOutputs()` bracket every run unconditionally — no-ops on CPU, stream fences on device — and `BindOutputToDevice` chains model stages device-resident with no host round trip.
- Law: result caching composes the settled cache seam — the key is (session fingerprint, input content hash over the already-flattened spans), determinism is declared at session admission and never discovered per call, and schema-invalid inputs cache their typed rejection under their own key class.
- Exemption: the bound-loop capsule body is the platform-forced statement seam.

```csharp conceptual
public sealed class BoundLoop : IDisposable {
    readonly InferenceSession session;
    readonly OrtIoBinding binding;
    readonly RunOptions run;
    readonly MemoryOwner<float> plane;
    readonly OrtValue bound, sink;

    public BoundLoop(InferenceSession session, string input, string output, long[] shape) {
        ArgumentNullException.ThrowIfNull(session);
        ArgumentNullException.ThrowIfNull(shape);
        this.session = session;
        plane = MemoryOwner<float>.Allocate(checked((int)shape.Aggregate(1L, static (acc, extent) => acc * extent)), AllocationMode.Clear);
        bound = OrtValue.CreateTensorValueFromMemory(OrtMemoryInfo.DefaultInstance, plane.Memory, shape);
        sink = OrtValue.CreateAllocatedTensorValue(OrtAllocator.DefaultInstance, TensorElementType.Float, shape);
        run = new RunOptions();
        binding = session.CreateIoBinding();
        binding.BindInput(input, bound);
        binding.BindOutput(output, sink);
    }

    public float Pulse(ReadOnlySpan<float> payload, float floor) {
        payload.CopyTo(plane.Span);
        binding.SynchronizeBoundInputs();
        session.RunWithBinding(run, binding);
        binding.SynchronizeBoundOutputs();
        var view = sink.GetTensorMutableDataAsSpan<float>();
        TensorPrimitives.Max(view, floor, view);
        return TensorPrimitives.Sum<float>(view);
    }

    public void Dispose() { run.Dispose(); binding.Dispose(); bound.Dispose(); sink.Dispose(); plane.Dispose(); }
}
```

## [05]-[MEASURED_DISPATCH]

[INTENT_AND_FOLD]:
- Law: a typed compute intent is the single solve-path entry — payload by staging class, kernel symbol, dtype and length class, canonical-unit parameters, budget reference — and the discriminant is recoverable from the value itself; a fast-flag or execution-hint parameter re-describing what the value encodes is the rejected arity form, and modalities are cases of one closed intent family under one total fold.
- Law: solve and lifecycle vocabularies are disjoint — admit, route, execute, receipt never share a signature with quiesce, drain, evict, dispose — so eviction can never share a lock with inference, and eviction itself is drain-gated deterministic disposal under budget-derived capacity, never a global pause; the review check is lexical, which is what makes it enforceable.
- Law: one total fold over the closed substrate-row table routes every admitted intent — columns are veto, cost, cap, fallback — and the scalar reference is the unvetoable terminal row, so all-rows-vetoed is unreachable and the fold needs no failure arm; the fold is deterministic data, reproducible offline from intent plus claims alone.
- Law: veto ordering is a cost gradient — static vetoes before probes before claim lookups — and the deadline is a cost-column input, so deadline-aware routing falls through expensive rows with no deadline-specific branch.
- Law: every cap derives arithmetically from the settled budget record — lane share × payload-class weight — and the same derivation feeds parallel floors and session thread counts, so one budget edit re-caps routing, re-floors parallelism, and stales claims coherently; a second budget-like record anywhere in compute is the foreclosed defect, exhaustion queues on the solve lane with a receipt rather than dropping, and intent stamps and receipt durations ride the settled clock seam — an ad-hoc stopwatch beside the fold is the foreclosed second clock.
- Law: batching is a fold output, never an intent property — queued intents sharing (kernel, dtype, row) coalesce into one execution whose receipt fans back out per intent; the remote row composes the transport substrate as an opaque executor arrow with serialization in its cost column and the payload cap in its veto column — compute never sees a wire type.
- Exemption: the scalar reference fold body is the named kernel statement seam.

[CLAIM_GATE]:
- Law: no fast path exists without a matching measured receipt — a non-reference row is admissible only when the claims table holds its (kernel symbol, dtype, length class, substrate row) identity under a live environment fingerprint; absence or mismatch demotes to vetoed-with-reason — correct-but-reference, never an exception — the demotion receipt is the re-measurement signal, and an empty claims table is the cold start: reference routes only, correct on day zero, fast through measurement, never the reverse.
- Law: the environment fingerprint is a closed column set — ISA and vector-width class, core topology, budget-record version, session fingerprint on model rows, asset hashes on native rows — compared structurally, so one environment change stales claims en masse with zero per-claim invalidation code; staleness is epoch algebra — prior-epoch claims demote but persist until re-measurement confirms or replaces — and the demotion-to-confirmation interval is the gauge separating slow-because-regressed from slow-because-unproven.
- Law: a displacing row clears a declared margin or the incumbent holds — the floor sits at or above the measurement's published variance class, so flapping cannot pass the gate it was built to stop; hysteresis is a column, never tuned behavior.
- Law: route admission is a conjunction — equivalence proof and speed claim — and the equivalence gate dominates: a fast wrong kernel is poisoned regardless of ratio; pipeline claims measure end-to-end because cache effects between stages break the independence that stage-ratio arithmetic assumes.
- Law: length-class boundaries derive from route mechanics — vector-width multiples, the parallel floor, cache footprints — never accumulated thresholds; a literal fast-path branch is the foreclosed spelling because every threshold is a claim row.
- Law: receipts carry route provenance — the taken row and every vetoed row with its reason — plus dual evidence for every normalizing admission: the canonical value used beside the original received, so disputes resolve from receipts rather than reproduction; a veto firing outside its declared reason column is a table-integrity defect the receipt fold surfaces, receipt combination is settled rail law, typed algorithm receipts never flatten into a generic ledger, and genericity lives in the one projection delegate that makes each receipt family a live data source.

```csharp conceptual
public sealed record Intent(string Kernel, ReadOnlyMemory<double> Payload, TimeSpan Remaining) {
    public static readonly int[] Edges = [4 * Vector<double>.Count, 512 * Vector<double>.Count];
    public string Dtype => nameof(Double);
    public int LengthClass => Edges.Count(edge => Payload.Length >= edge);
}

public readonly record struct LaneDerivation(int BudgetVersion, double LaneShare, ImmutableArray<double> ClassWeight) {
    public static LaneDerivation From(BudgetRecord budget) =>                  // projection off concurrency.md's one frozen budget owner; no local budget literal lives in compute
        new(budget.Version, budget.LaneShare(Lane.Solve), budget.ClassWeights);
    public TimeSpan Cap(int lengthClass) => TimeSpan.FromTicks((long)(LaneShare * ClassWeight[lengthClass] * TimeSpan.TicksPerMillisecond));
    public string Stamp(string isa) => $"{isa}|v{BudgetVersion}|w{Vector<double>.Count}";
}

public sealed record ClaimKey(string Kernel, string Dtype, string Substrate, int LengthClass);
public sealed record Claim(string Fingerprint, double Ratio);
public readonly record struct RouteReceipt(string Kernel, string Taken, Seq<(string Row, string Veto)> Trail, double Value);

[SmartEnum<string>]
public sealed partial class SubstrateRow {
    public static readonly SubstrateRow Vector = new("<row-vector>", terminal: false,
        static intent => intent.Payload.Length < Intent.Edges[0] ? Some("<below-floor>") : None,
        static intent => TimeSpan.FromTicks(intent.Payload.Length / 8),
        static payload => TensorPrimitives.Sum(payload.Span));
    public static readonly SubstrateRow Reference = new("<row-reference>", terminal: true,
        static _ => None, static intent => TimeSpan.FromTicks(intent.Payload.Length), ScalarFold);

    public bool Terminal { get; }

    [UseDelegateFromConstructor] public partial Option<string> Veto(Intent intent);
    [UseDelegateFromConstructor] public partial TimeSpan Cost(Intent intent);
    [UseDelegateFromConstructor] public partial double Arrow(ReadOnlyMemory<double> payload);

    static double ScalarFold(ReadOnlyMemory<double> payload) {
        var total = 0d;
        foreach (var value in payload.Span) { total += value; }     // Exemption: the scalar reference fold is the named kernel statement seam
        return total;
    }
}

public static class MassEngine {
    public const double Margin = 1.2;

    public static RouteReceipt Route(Intent intent, Seq<SubstrateRow> rows, HashMap<ClaimKey, Claim> claims, LaneDerivation lane, string isa) {
        ArgumentNullException.ThrowIfNull(intent);
        var live = lane.Stamp(isa);
        var routed = rows.Map(row => (Row: row, Veto: Vetoes(intent, row, claims, lane, live)))
            .Fold((Taken: Option<SubstrateRow>.None, Trail: Seq<(string, string)>()),
                static (state, slot) => state.Taken.IsSome ? state
                    : slot.Veto is { IsSome: true, Case: string reason } ? (state.Taken, state.Trail.Add((slot.Row.Key, reason)))
                    : (Some(slot.Row), state.Trail));
        var taken = routed.Taken.IfNone(SubstrateRow.Reference);
        return new RouteReceipt(intent.Kernel, taken.Key, routed.Trail, taken.Arrow(intent.Payload));
    }

    static Option<string> Vetoes(Intent intent, SubstrateRow row, HashMap<ClaimKey, Claim> claims, LaneDerivation lane, string live) =>
        row.Terminal ? None
            : row.Veto(intent)
            | (row.Cost(intent) > intent.Remaining ? Some("<over-deadline>") : None)
            | (row.Cost(intent) > lane.Cap(intent.LengthClass) ? Some("<over-cap>") : None)
            | (claims.Find(new ClaimKey(intent.Kernel, intent.Dtype, row.Key, intent.LengthClass)) switch {
                { IsSome: true, Case: Claim claim } => claim.Fingerprint != live ? Some($"<stale:{claim.Fingerprint}>")
                    : claim.Ratio < Margin ? Some($"<inside-margin:{claim.Ratio}>")
                    : None,
                _ => Some("<unclaimed>"),
            });
}
```

## [06]-[UNITS_BOUNDARY]

[CANONICAL_SEAM]:
- Law: unit families convert exactly once at admission — `As(unit)` to the family canonical, the interior computes on canonical scalars, display converts only at egress — and the boundary rows are non-throwing: `Quantity.TryParse`, `Quantity.TryFrom`, `Quantity.TryFromUnitAbbreviation`, `UnitConverter.TryConvert`, with throwing forms vetoed at boundaries and abbreviation parsing pinning its format provider because the overload is culture-sensitive by design.
- Law: cross-family algebra is operator-derived — length × length is area, length ÷ duration is speed, as typed operators on the quantity structs — and a literal conversion factor in interior code restates what the type owns.
- Law: aggregation rides owned folds — `UnitMath.Sum`/`UnitMath.Average` pin the result unit, every family's `Zero` seeds folds, `As(UnitSystem.SI)` is the declared system projection, and `Info.BaseDimensions` arithmetic admits dynamically-described quantities through dimension vectors, never name matching.
- Law: the admitted family table — quantities, canonical units, display units — is one frozen declaration per bounded context with converter extensions registered once at boot through `SetConversionFunction`, so the boundary's accepted grammar is enumerable at boot and a rejection names the admitted set rather than echoing a parser error.
- Law: a quantity-bearing tensor carries canonical scalars with the unit row on the intent, never per element — and canonicalizing before dispatch keeps measured claims unit-invariant, where converting inside the kernel would multiply the claim table by the unit enum.
- Law: dual evidence holds at the unit seam — the receipt carries the original (value, unit) pair beside the canonical scalar, so egress answers exactly what was received; the same law covers dtype narrowing and downsampling, because normalization without retained evidence is information destruction at the boundary.

[PERCEPTUAL_ROW]:
- Law: a tuning row stores M perceptual knobs and derives the N−M physical constants as computed members — response and damping fraction stored; angular frequency, stiffness, and damping rate derived — so co-varying constants cannot de-sync, and storing a derived member is the rejected form: the moment two stored members must co-vary, the type has hidden an invariant it should compute.
- Law: quantity-typing the row makes the derivation dimension-checked — a unit mistake in the derivation is a type error, never a runtime oscillation artifact.

```csharp conceptual
public readonly record struct AdmittedSpan(double CanonicalMeters, double Original, string OriginalUnit);

public static class UnitSeam {
    public static Fin<AdmittedSpan> Admit(string text) =>
        Quantity.TryParse(typeof(Length), text, out var parsed) && parsed is Length raw
            ? Fin.Succ(new AdmittedSpan(raw.As(LengthUnit.Meter), (double)raw.Value, raw.Unit.ToString()))
            : Fin.Fail<AdmittedSpan>(Error.New(8501, $"<unparsed:{text}>"));

    public static Length Folded(IEnumerable<Length> parts) => UnitMath.Sum(parts, LengthUnit.Meter);

    public static Speed Derived(Length span, Duration window) => span / window;
}

public sealed record MotionRow(Duration Response, double DampingFraction) {
    public Frequency Angular => Frequency.FromRadiansPerSecond(2 * Math.PI / Response.Seconds);
    public double Stiffness => Angular.RadiansPerSecond * Angular.RadiansPerSecond;
    public Frequency Damping => Frequency.FromRadiansPerSecond(2 * DampingFraction * Angular.RadiansPerSecond);
}
```
