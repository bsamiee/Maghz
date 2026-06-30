# [BOUNDARIES]

Foreign material crosses once: a boundary owner projects handles, sentinels, callbacks, thread-affine work, state cells, and protocol bytes into admitted values or typed rails, so everything the interior receives — values, receipts, policies, effects — is recoverable from declarations rather than from the foreign surface that produced it. The seam is the only site that names a provider type, catches a provider exception, or holds a native lifetime; the interior is total over admitted owners, and every native crossing mints a closed fault family so the cause stays structurally addressable instead of flattening to one provider token.

## [01]-[SEAM_CHOOSER]

This table selects the owner for a foreign signal; when a signal matches several rows, the most specific wins, and lifetime rows are read before transport rows.

| [INDEX] | [FOREIGN_SIGNAL]     | [SEAM_OWNER]        | [INTERIOR_FORM]                   | [REJECT]                   |
| :-----: | :------------------- | :------------------ | :-------------------------------- | :------------------------- |
|  [01]   | native resource      | capsule owner       | `Fin<T>` value projection         | raw handle field           |
|  [02]   | borrowed live memory | scoped view         | detached value copy               | escaping span              |
|  [03]   | null or sentinel     | admission projector | `Option<T>` or closed family      | nullable-as-failure        |
|  [04]   | callback or event    | subscription value  | channel-fed admitted signal       | orphan handler             |
|  [05]   | thread-affine call   | marshal effect      | `Eff<RT,T>` with captured context | ambient thread check       |
|  [06]   | session or singleton | token-gated cell    | committed state family            | boolean lifecycle flag     |
|  [07]   | protocol payload     | wire contract       | admitted owner                    | codec-bearing domain owner |
|  [08]   | signed byte field    | byte contract       | canonical octets plus hash        | parse-reserialize          |

## [02]-[ADMISSION]

[SENTINEL_PROJECTION]:
- Use: any foreign null, invalid handle, detached row, missing key, default struct, or not-found code.
- Law: project at the single read site that first sees the foreign value into `Option<T>`, `Fin<T>`, or a closed `[Union]` state family — that line is the last one in the program naming the sentinel, the projector owns the absence vocabulary, and no sentinel survives into an interior or persisted shape.
- Law: a sentinel that re-appears after the seam — a transform that can itself return null, a nested field erasing late, a provider default surfacing on a second call — is a second admission site, not a leaked first one, so it projects where it appears; the present branch never manufactures `Some(null!)`, because a carrier wrapping a foreign sentinel re-leaks it one hop later and breaks the interior totality the first admission promised.
- Reject: a sentinel admitted once then trusted forever where a later transform re-mints it; sentinel checks in interior flow; nullable payloads riding past the seam; `Option<T>.Case` read without an `IsSome` proof.

[ABSENCE_TAXONOMY]:
- Law: cause-bearing foreign state — unavailable, degraded, pending, faulted — is a closed `[Union]` family, never `None`; `Option<T>` is correct only when absence has no action-changing cause.
- Law: provision and state are different axes: a required capability is always present as a port whose value carries its own unavailable state, and the environment read is the one authorized sentinel-projection seam, fusing read, projection, and rail lift into one bound step.
- Reject: flattening nested absence before the layer carrying cause or evidence is consumed; conditional capability constraints, null ports, or service lookup standing in for runtime absence.

[PROBE_SWEEP_POLICY]:
- Law: a probe sweep fixes its algebra once at the seam, and the carrier's `Apply` owns accumulate-versus-abort — selecting the carrier selects whether the boundary reports one absence or all of them.
- Law: traversal never guarantees the element function runs; a per-probe boundary obligation attaches at the probe itself, never inside the traverse.
- Accept: survivor/casualty partition when callers need both usable values and rejected facts.
- Reject: a later list walk that reinterprets why each probe disappeared.

```csharp conceptual
public enum RawState { Missing, Detached, Ready }

public sealed record RawRow(RawState State, string? Value);

public static class ForeignAdmission {
    public static Fin<Option<Payload>> Admit(RawRow row) =>
        (row.State, row.Value) switch {
            (RawState.Missing, _) => Fin.Succ<Option<Payload>>(None),
            (RawState.Ready, { } value) => Payload.AdmittedFin(value).Map(Optional),
            (RawState.Ready, null) => Fin.Fail<Option<Payload>>(new Fault.Absent(Detail: nameof(RawRow.Value))),
            (RawState.Detached, _) => Fin.Fail<Option<Payload>>(new Fault.Unavailable(Detail: nameof(RawState.Detached))),
            var (state, _) => Fin.Fail<Option<Payload>>(new Fault.Unavailable(Detail: $"<unmapped:{state}>")),
        };
}
```

## [03]-[LIFETIME]

[CAPSULE_OWNER]:
- Use: native handles, foreign objects, pinned buffers, leases, pooled values, and external cursors.
- Law: one capsule acquires, projects, and releases — borrowed, owned, and the owned-mutable window are cases of one `[Union]` surface; the owned case constructs its `SafeHandle` with `ownsHandle: true` and releases, the borrowed case constructs with `ownsHandle: false` and projects without disposal, and the measured case is the owned window a multi-edit kernel revises in place. The handle is minted only through the `[LibraryImport]` open that `SetHandle` populates; a `SafeHandle` whose `handle` field is never set is invalid forever and `ReleaseHandle` never fires.
- Law: a native borrow spans the full operation that observes the handle — `DangerousAddRef`/`DangerousRelease` bracket the projection, and liveness is never tested apart from the consumption it guards.
- Law: the native crossing splits into the closed `Fault` cases the projector already owns — the syscall `Host`, the marshalling `Marshal`, the refused mutation `Refused` — so the cause stays addressable, never a bare `Error.New(ex)` flattening a multi-cause domain to one token; the same borrow window the lifetime owns is where the discrimination rides, so no provider exception escapes unconverted.
- Law: the measured window is the disposition's structural property, not a runtime flag — `Revise` threads one owned span through the edit `Seq` as an in-place kernel and refuses the read-only cases with the `Refused` fault; the per-edit rebind that recopies the whole buffer is the rejected quadratic form the platform makes prohibitive.
- Law: callers receive values or rails, never live handles; deterministic close is the capsule's contract, and a handle left for finalization where close must precede the backing free is rejected.
- Exemption: the `SetHandle` populate, the add-ref/release window, and the in-place slice write inside the capsule kernel are the named platform-forced statement seam.
- Reject: scattered `using`, public handle fields, parallel borrowed/owned/measured wrapper types, a second disposer registry, a bare `Error.New(ex)` where the closed family states the cause, or a per-edit buffer rebind where the measured window is revised in place.

```csharp conceptual
public sealed partial class ResourceHandle : SafeHandleZeroOrMinusOneIsInvalid {
    private ResourceHandle() : base(ownsHandle: true) { }
    public ResourceHandle(bool ownsHandle) : base(ownsHandle) { }

    [LibraryImport("<native>", EntryPoint = "open_resource")]
    private static partial ResourceHandle NativeOpen(uint slot);

    public static Fin<ResourceHandle> Open(uint slot) =>
        NativeOpen(slot) is { IsInvalid: false } owned
            ? Fin.Succ(owned)
            : Fin.Fail<ResourceHandle>(new Fault.Marshal(Detail: $"<open-failed:{slot}>"));

    protected override bool ReleaseHandle() => NativeRelease(handle);
}

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Lease {
    private Lease() { }
    public sealed record Borrowed(ResourceHandle Handle) : Lease;
    public sealed record Owned(ResourceHandle Handle) : Lease;
    public sealed record Measured(ResourceHandle Handle, int Extent) : Lease;

    public Fin<TResult> Use<TResult>(Func<nint, TResult> copy) => Switch(
        borrowed: static (c, b) => Borrow(b.Handle, c),
        owned:    static (c, o) => Borrow(o.Handle, c),
        measured: static (c, m) => Borrow(m.Handle, c),
        state: copy);

    public Fin<int> Revise(Seq<(int Offset, ReadOnlyMemory<byte> Patch)> edits) => Switch(
        measured: static (e, m) => Within(m.Handle, Fin<int> (h) => Patch(h, m.Extent, e)),
        borrowed: static (_, _) => Fin.Fail<int>(new Fault.Refused()),
        owned:    static (_, _) => Fin.Fail<int>(new Fault.Refused()),
        state: edits);

    public Unit Release() => Switch(
        borrowed: static (_, _) => unit,
        owned:    static (_, o) => fun(o.Handle.Dispose)(),
        measured: static (_, m) => fun(m.Handle.Dispose)(),
        state: unit);

    static unsafe Fin<int> Patch(nint address, int extent, Seq<(int Offset, ReadOnlyMemory<byte> Patch)> edits) {
        var window = MemoryMarshal.CreateSpan(ref Unsafe.AsRef<byte>((void*)address), extent);
        var written = 0;
        foreach (var (offset, patch) in edits) {                          // Exemption: the borrow kernel mutates one owned window in place; per-edit rebind is the rejected O(n·size) recopy
            patch.Span.CopyTo(window[offset..]);
            written += patch.Length;
        }
        return Fin.Succ(written);
    }

    static Fin<TResult> Within<TResult>(ResourceHandle handle, Func<nint, Fin<TResult>> body) {
        var added = false;
        try { handle.DangerousAddRef(ref added); return body(handle.DangerousGetHandle()); }
        catch (SEHException seh) { return new Fault.Host(Code: seh.ErrorCode); }
        catch (Exception ex) { return new Fault.Marshal(Detail: ex.Message); }
        finally { if (added) handle.DangerousRelease(); }
    }

    static Fin<TResult> Borrow<TResult>(ResourceHandle handle, Func<nint, TResult> copy) =>
        Within(handle, Fin<TResult> (h) => Fin.Succ(copy(h)));
}
```

[REF_SAFE_PROJECTION]:
- Law: live memory crosses as a scoped view whose result is a value copy; any value returned from the projector is detached from the foreign lifetime, and the `scoped` parameter is the type-level proof — the projector cannot store, return, or box the view, so escape is a compile error, not a review note.
- Law: the projection reads inside the window and emits owned material before the window closes — an `ImmutableArray<byte>` snapshot, an admitted scalar, or a digest — never the view; a value reconstructed from a typed read inside the borrow is detached, a span handed outward is dangling.
- Accept: `readonly ref struct` views and `scoped` delegates for synchronous projection.
- Reject: storing spans, boxing live views, returning views, returning a `Span<T>` field through a property, or crossing `await` with foreign memory.

```csharp conceptual
public readonly ref struct BoundaryView(ReadOnlySpan<byte> bytes) {
    public int Length => bytes.Length;
    public Option<int> Leading => bytes is [var lo, var hi, ..] ? Optional(lo | hi << 8) : None;
    public ImmutableArray<byte> Detached(Range slice) => [.. bytes[slice]];
}

public delegate TResult ViewProjector<TResult>(scoped BoundaryView view);

public static class ViewBoundary {
    public static TResult Project<TResult>(ReadOnlyMemory<byte> memory, ViewProjector<TResult> projector) =>
        projector(new BoundaryView(memory.Span));

    public static Fin<Digest> Capture(ReadOnlyMemory<byte> memory) =>
        Project(memory, static Fin<Digest> (view) => (view.Length, view.Leading, view.Detached(..view.Length)) switch {
            (var length, { IsSome: true, Case: int head }, var owned) => new Digest(length, head, owned),
            (_, _, _) => new Fault.Absent(Detail: nameof(BoundaryView)),
        });
}
```

[SCOPE_AND_LEASE]:
- Law: a derived scope isolates exactly one named axis — resources, cancellation, or environment — and the wrong derivation silently shares the axis the caller meant to isolate; swapping the runtime never isolates the registry.
- Law: scope registration keys on object identity, release is idempotent and per-key, and one throwing release never aborts the remaining sweep.
- Law: leases, rentals, and pools expose logical extents, not pool vocabulary; return or release occurs exactly once on every exit path, including rejected and cancelled acquisitions.
- Reject: parent and child scopes both disposing one cancellation source, handle, or subscription set; pooled arrays or rate permits escaping as public state.

## [04]-[EVENTS_THREADS]

[SUBSCRIPTION_VALUE]:
- Use: events, callbacks, observers, waits, notifications, and foreign lifecycle hooks.
- Law: a subscription is the disposable detacher returned by attach, holding the exact delegate identity attach used; the callback borrows every touched handle for the whole subscription window, and detach completes before any borrowed handle can be disposed.
- Law: the borrow taken before wiring rides every exit — a throwing attach releases the ref it took before re-raising, because the detacher that would release it never reaches the caller, so the success path alone defers release to detach.
- Law: the subscription set is the scope — reactivation constructs a fresh set, never appends to a retained one, and the set dies with the live state that owns it.
- Exemption: the add-ref open, the throwing-attach release, the attach/detach `+=`/`-=` wiring, and the posted-callback body are the named platform-forced statement seam.
- Reject: inline lambdas that cannot detach, finalizer-owned unsubscribe, split attach/detach owners, or host-bus deregistration assumed rather than probed.

[HOST_MARSHAL]:
- Law: thread-affine work crosses through an explicit effect carrying a `SynchronizationContext` or scheduler captured once at the composition root — host post primitives swallow exceptions and a null context silently degrades posting to inline execution, so the seam verifies the capture and routes failure through the effect.
- Law: the crossing's outcome is a closed crossing-fault `[Union]` the seam mints — the dead-context post, the refused capture handshake, the converted worker raise are distinct cases, never one stringified provider message — so a recovery predicate sends the dead-context and handshake arms to rebuild a fresh capture (a closed context never re-posts, so reusing it re-faults) while the converted worker raise returns railed to the transient weave; cancellation never enters this family.
- Law: cancellation normalizes once into that vocabulary — caller shutdown, local deadline, and external timeout carry distinct evidence when behavior differs — and cancellation is never transient: it is the first arm every retry predicate refuses, re-raised on its own carrier rather than collapsed into a crossing case.
- Law: `ExecutionContext` flow and `SynchronizationContext` affinity are separate decisions; a context-free callback takes the unsafe registration form only when it reads no ambient state, and an interior transform never reads ambient thread state to recover evidence the crossing already carried as an admitted value.
- Reject: `Thread.CurrentThread` tests, ambient context reads inside reusable transforms, fire-and-forget posts, a stringified provider message standing in for the closed crossing fault.

[HANDOFF_DRAIN]:
- Law: a high-frequency callback submits intent and returns — a committed cell is the latest-value register for a per-tick consumer, a `Channel<T>` is the log for a consumer that must see every intermediate; the consumer's need selects the carrier, and producer back-pressure is independent of consumer pacing.
- Law: promises completed from a foreign thread queue continuations — `TaskCompletionSource<T>` constructed with `TaskCreationOptions.RunContinuationsAsynchronously` — and a cell-change handler that blocks or re-enters routes through a channel.
- Accept: a bounded channel's full-behavior — drop or wait — is the seam's declared policy, stated where the writer is discarded.
- Reject: blocking the foreign callback, mutating interior state from it, or a foreign thread running arbitrary downstream logic.

```csharp conceptual
public readonly record struct Subscription(Action Detach, Task<Signal> FirstSignal) : IDisposable {
    public void Dispose() => Detach();
}

public static class SignalBoundary {
    public static Subscription Attach(Emitter emitter, ResourceHandle handle, ChannelWriter<Signal> sink) {
        var added = false;
        handle.DangerousAddRef(ref added);
        try {
            var gate = new TaskCompletionSource<Signal>(TaskCreationOptions.RunContinuationsAsynchronously);
            EventHandler<SignalArgs> handler = (_, args) => {
                var signal = Signal.From(handle.DangerousGetHandle(), args);
                _ = sink.TryWrite(signal);
                gate.TrySetResult(signal);
            };
            emitter.Changed += handler;
            return new Subscription(
                Detach: () => { emitter.Changed -= handler; if (added) handle.DangerousRelease(); },
                FirstSignal: gate.Task);
        }
        catch { if (added) handle.DangerousRelease(); throw; }
    }
}
```

## [05]-[STATE_CELLS]

[TOKEN_LIFECYCLE]:
- Use: session, singleton, wake, and cross-call boundary lifetime.
- Law: boundary lifecycle is a closed state family in one cell — pending, live, failed; never booleans — and the transition stays pure and replayable: acquisition runs outside the CAS, commits under a token, and the losing acquisition releases itself.
- Law: a stale teardown succeeds only while its token still owns the live state; re-opening replaces the whole cancellation pair, because a cancelled source never resets; a faulted cell is escaped only by a fresh instance carrying typed evidence.
- Law: waiters wake only after committed state publishes — try-set forms after the winning transition, never from attempted or aborted transitions — and multi-field state publishes as one immutable reference replacement, so tearing is structurally impossible.
- Reject: factories, disposers, waits, or external calls inside a replayable swap body; shutdown booleans; teardown that can dispose a replacement session.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Gate {
    private Gate() { }
    public sealed record Pending : Gate;
    public sealed record Live(Guid Token, Session Session) : Gate;
    public sealed record Failed(Error Reason) : Gate;
}

public static class SessionCell {
    static readonly Atom<Gate> Cell = Atom<Gate>(new Gate.Pending());

    public static Fin<Session> Open(Func<Fin<Session>> acquire) =>
        Cell.Value.Switch(
            pending: static (a, _) => a().MapFail(Poison).Bind(static session => Commit(Guid.NewGuid(), session)),
            live:    static (_, l) => Fin.Succ(l.Session),
            failed:  static (_, f) => Fin.Fail<Session>(f.Reason),
            state: acquire);

    public static Unit Close(Guid token) =>
        ignore(Cell.Swap(current => current is Gate.Live live && live.Token == token ? new Gate.Pending() : current));

    static Fin<Session> Commit(Guid token, Session session) =>
        Cell.Swap(current => current is Gate.Pending ? new Gate.Live(token, session) : current).Switch(
            pending: static (s, _) => Fin.Fail<Session>(Fault.Create($"<gate-regressed:{s.Token}>")),
            live:    static (s, l) => l.Token == s.Token
                ? Fin.Succ(s.Session)
                : (fun(s.Session.Dispose)(), Fin.Succ(l.Session)).Item2,
            failed:  static (s, f) => (fun(s.Session.Dispose)(), Fin.Fail<Session>(f.Reason)).Item2,
            state: (Token: token, Session: session));

    static Error Poison(Error reason) =>
        (Cell.Swap(current => current is Gate.Pending ? new Gate.Failed(reason) : current), reason).Item2;
}
```

[DRAIN_COORDINATION]:
- Law: a permit of the form "the set I observed did not change while I decided" requires `Isolation.Serialisable` — the bare `atomic` entrypoint validates only written cells under snapshot isolation, so merely-read state tears invisibly; the isolation argument is spelled at every permit site.
- Law: drain reads phase, in-flight count, and deadline as one transaction; admission is fenced while mid-flight work reaches a typed terminal, and effects ride the transaction's return value into one post-commit continuation.
- Reject: closing a session from one flag while another cell still admits; acting on change events fired from aborted attempts — they signal intent, not commitment.

```csharp conceptual
[SmartEnum]
public sealed partial class Phase {
    public static readonly Phase Open = new();
    public static readonly Phase Draining = new();
}

public static class DrainBoundary {
    static readonly Ref<Phase> Lifecycle = Ref(Phase.Open);
    static readonly Ref<int> InFlight = Ref(0);
    static readonly Ref<DateTimeOffset> Deadline = Ref(DateTimeOffset.MaxValue);

    public static Fin<int> Admit(TimeProvider clock) =>
        atomic(() =>
            Lifecycle.Value == Phase.Open && clock.GetUtcNow() <= Deadline.Value
                ? Fin.Succ(InFlight.Swap(static n => n + 1))
                : Fin.Fail<int>(Fault.Create($"<fenced:{InFlight.Value}>")),
            Isolation.Serialisable);

    public static Phase BeginDrain(DateTimeOffset by) =>
        atomic(() => (Deadline.Swap(_ => by), Lifecycle.Swap(static _ => Phase.Draining)).Item2);

    public static Unit Settle() =>
        ignore(atomic(() => InFlight.Swap(static n => n - 1)));
}
```

[MEMO_KEY]:
- Law: a boundary memo key binds the foreign identity content alone cannot recover — a native handle's absolute path plus file length plus last-write stamp, a session token, or a capability fingerprint joins the content and policy axes into one composite key, so two payloads byte-identical yet sourced from distinct foreign owners never collide, and in-place file replacement invisible to a path-only cache is caught.
- Law: a structural index or graph diff binds the discriminant content alone cannot recover — a node's path-vector or sibling ordinal joins the `BYTE_IDENTITY` content digest so two identical-content siblings under one parent key distinctly, the structural axis riding the same composite the foreign-identity axis does; the content digest is that one canonical byte-codec reused verbatim, never a second hashing path.
- Boundary: the fixed-arity axis set rides a value tuple or `[ComplexValueObject]` composite key, a dynamic one a `FrozenDictionary`; the rooted graph id is a neutral kernel value while any foreign or wire id is a boundary attribute, never the kernel key.
- Reject: a content-only, path-only, type-only, or option-partial cache dropping the foreign or structural axis; an order-sensitive tree keyed on content alone that collapses identical-content siblings and loses the move; a process-randomized `GetHashCode` persisted as stable identity.

## [06]-[WIRE_CONTRACTS]

[PROTOCOL_EDGE]:
- Use: payload records, envelopes, serializer contracts, persisted packets, and remote frames.
- Law: wire shapes stay protocol-shaped at the edge — the converter is the only site where protocol and interior schemas meet, and interior owners carry no codec attributes, serializer options, or transport objects.
- Law: a pure owner↔DTO field rename is a generated `[Mapper]` partial with `[MapProperty]` rows, never a hand-written field-by-field projection; only a discriminant-resolving or value-transforming crossing earns the hand-written `JsonConverter<T>`, so the rename path stays a definition-time aspect and the codec path owns the irreducible transform.
- Law: inner envelopes reject drift — duplicate keys, unknown inner members, null-token drift, and depth excess fail before admission — while outer wrappers tolerate only declared extension material; read and write depth limits differ, so a tree that writes cleanly can fail its own round-trip.
- Reject: last-write-wins or best-effort parse for owned protocol shapes; a hand-rolled rename mapper where `[Mapper]` generates it.

[CONTRACT_SURFACE]:
- Law: generation mode is contract coverage, not tuning — `Default` covers read and write, `Metadata` emits shapes with no fast path, `Serialization` emits write-only with no `Populate` — and `JsonTypeInfo<T>` coordinates carry name, requiredness, converter, order, and discriminant as breaking-change axes of equal gravity; resolver, converter, and options instances are stable contract identities, so policy variance travels through values the converter reads, never fresh option graphs that cold-miss the per-type metadata cache.
- Law: `SerializeHandler != null` swept across every envelope type at startup is the compile-adjacent proof the write path stays generated and allocation-free — a null handler inside a source-generated context is the silent reflection fallback the contract claims it deleted.
- Law: modifier fusion is ordered policy — rename before redaction is a different contract than redaction before rename — and a captured resolution fault replays on every request: sticky, non-transient, classified expected-non-retriable at the seam.
- Reject: reflection fallback where the contract claims generated coverage; per-call resolver construction, reordered converter lists, or post-seal mutation; a fresh closured resolver per options forcing a cold metadata cache.

[CONVERTER_OWNER]:
- Law: one `JsonConverter<T>` owns a closed wire family — read resolves the discriminant once and write emits it with the selected case — and the converter consumes exactly the value it owns, throwing `JsonException` for wire-shape rejection so token displacement, depth balance, and path evidence stay boundary facts.
- Law: the converter owns only the irreducible work — discriminant resolution and a value transform no mapper can express — and delegates the name-only owner↔DTO correspondence to the generated `[Mapper]` it calls, so the read arm wraps the deserialized wire DTO through the generated inverse and the write arm projects the case through the generated forward, and no field assignment is hand-written on either leg.
- Exemption: the converter's reader statements and `JsonException` throw channel are the named platform-forced seam.
- Reject: converter-per-case sprawl, case converters bypassing the family owner, sentinels returned from converters, unanchored interior exceptions, or a hand-written field-by-field projection where `[Mapper]` generates the rename.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Frame {
    public const string KindA = "<kind-a>";
    public const string KindB = "<kind-b>";
    private Frame() { }
    public sealed record Single(int At) : Frame { public string Kind => KindA; }
    public sealed record Block(int Start, int End) : Frame { public string Kind => KindB; }
}

public sealed record BlockWire(int Lo, int Hi, string Kind);

[Mapper]
public static partial class FrameMap {
    [MapProperty(nameof(Frame.Block.Start), nameof(BlockWire.Lo))]
    [MapProperty(nameof(Frame.Block.End), nameof(BlockWire.Hi))]
    public static partial BlockWire ToWire(Frame.Block block);

    [MapProperty(nameof(BlockWire.Lo), nameof(Frame.Block.Start))]
    [MapProperty(nameof(BlockWire.Hi), nameof(Frame.Block.End))]
    [MapperIgnoreSource(nameof(BlockWire.Kind))]
    public static partial Frame.Block ToDomain(BlockWire wire);
}

public sealed class FrameConverter : JsonConverter<Frame> {
    public override Frame Read(ref Utf8JsonReader reader, Type type, JsonSerializerOptions options) {
        using var buffered = JsonDocument.ParseValue(ref reader);
        return buffered.RootElement.GetProperty(nameof(Frame.Single.Kind)).GetString() switch {
            Frame.KindA => buffered.RootElement.Deserialize(WireContext.Default.FrameSingle) ?? throw new JsonException("<null-frame>"),
            Frame.KindB => FrameMap.ToDomain(buffered.RootElement.Deserialize(WireContext.Default.BlockWire) ?? throw new JsonException("<null-frame>")),
            var kind => throw new JsonException($"<unknown-kind:{kind}>"),
        };
    }

    public override void Write(Utf8JsonWriter writer, Frame value, JsonSerializerOptions options) =>
        value.Switch(
            single: static (w, s) => JsonSerializer.Serialize(w, s, WireContext.Default.FrameSingle),
            block:  static (w, b) => JsonSerializer.Serialize(w, FrameMap.ToWire(b), WireContext.Default.BlockWire),
            state: writer);
}
```

[BYTE_IDENTITY]:
- Use: signatures, hashes, idempotency keys, checksums, and byte-stable forwarding.
- Law: semantic equality and byte equality are different contracts; raw octets are captured before parse, canonical octets are emitted once, and one encoder per byte-identity domain is a composition-time invariant asserted once, never chosen per site.
- Law: signed numeric and timestamp fields survive only as raw token bytes — runtime normalization re-spells floats, trims timestamps, and re-kinds non-finite values.
- Exemption: the parse-probe `using` inside the admission kernel is the named platform-forced statement seam.
- Boundary: receipts carry coordinates and hashes, never payload bytes.
- Reject: parse-and-reserialize between verification, signing, or forwarding.

```csharp conceptual
public sealed record CanonicalForm(string Encoder, string NumberShape, string MemberOrder);

public readonly record struct SignedBytes(ReadOnlyMemory<byte> Octets, string Hash, CanonicalForm Form);

public static class SignedBoundary {
    public static Fin<SignedBytes> Admit(ReadOnlyMemory<byte> octets, CanonicalForm form) =>
        Try.lift(() => Probed(octets, form)).Run()
            .MapFail(static error => Fault.Create($"<malformed-payload:{error.Message}>"));

    public static void Forward(Utf8JsonWriter writer, SignedBytes bytes) =>
        writer.WriteRawValue(bytes.Octets.Span, skipInputValidation: false);

    public static bool SameBytes(SignedBytes left, SignedBytes right) =>
        left.Form == right.Form && left.Hash == right.Hash;

    static SignedBytes Probed(ReadOnlyMemory<byte> octets, CanonicalForm form) {
        using var probe = JsonDocument.Parse(octets);
        return new SignedBytes(octets, Convert.ToHexString(SHA256.HashData(octets.Span)), form);
    }
}
```
