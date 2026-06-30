# [SYSTEM_APIS]

This page is the BCL-owner-replacement law: the high-churn surface where a yearly runtime delta retires a local helper, kept disjoint from the stable language-form law so `language.md` never churns with a BCL addition. A runtime API replaces local machinery only when it owns the concern; it never replaces a LanguageExt rail, a Thinktecture generated owner, or a downstream owner's law.

Each card names the owning runtime surface and the local loop, wrapper, or branch it deletes, and the snippet composes that surface under a `Fin<T>` rail behind one admitted owner. A surface whose body the BCL leaves statement-shaped — the span transcode, the offset-addressed fill, the ref-into-bucket probe — is named at its card Exemption and still leaves the result a rail value; the interior never sees the `OperationStatus`, the `out` triple, or the raw `null`.

Five concerns route to their owners and are never re-derived here: numerics, generic math, `Vector<T>`, and `TensorPrimitives` element kernels are `algorithms.md`'s; `TimeProvider`, the clock seam, caches, and pools are `runtime.md`'s `[08]`/`[07]`; channels, task composition, cancellation, rate limiters, and reactive streams are `concurrency.md`'s; `ActivitySource`, `Meter`, and `[LoggerMessage]` emission are `diagnostics.md`'s; content identity, the canonical byte-codec, the memo key, and the JSON contract are `boundaries.md`'s `BYTE_IDENTITY`/`MEMO_KEY`/`CONTRACT_SURFACE`. This page owns the in-process stdlib-surface selection only.

## [01]-[SMELL_LOOKUP]

This table is a lookup by repeated local smell; the owning card states the placement law and the spelling it deletes.

| [INDEX] | [SMELL]                                | [OWNER]                    |
| :-----: | :------------------------------------- | :------------------------- |
|  [01]   | hand-built static `Regex`              | `[GeneratedRegex]`         |
|  [02]   | regex count via `Matches().Count`      | `Regex.Count`              |
|  [03]   | regex used only as a character filter  | `SearchValues<T>`          |
|  [04]   | `string.Split` on a parse path         | `MemoryExtensions.Split`   |
|  [05]   | `StringBuilder` for fixed-length text  | `Utf8.TryWrite`            |
|  [06]   | `Encoding.UTF8.GetBytes` on a literal  | `u8` literal               |
|  [07]   | manual hex loop                        | `Convert.ToHexStringLower` |
|  [08]   | rebuilt static `Dictionary` per call   | `FrozenDictionary`         |
|  [09]   | `ToString` before a keyed probe        | `GetAlternateLookup`       |
|  [10]   | `TryGetValue`-then-`Add` double probe  | `GetValueRefOrAddDefault`  |
|  [11]   | repeated `GroupBy` for a count or fold | `CountBy`/`AggregateBy`    |
|  [12]   | seek/read loop on a parse path         | `RandomAccess`             |
|  [13]   | `BitConverter` for an endian frame     | `BinaryPrimitives`         |
|  [14]   | `new byte[n]` scratch buffer           | `ArrayPool<T>`             |
|  [15]   | constructed hash used once             | `CryptographicOperations`  |
|  [16]   | `SHA256` for a non-cryptographic key   | `XxHash3`                  |
|  [17]   | guard-block argument `throw`           | throw-helper statics       |
|  [18]   | `[DllImport]` runtime marshalling stub | `[LibraryImport]`          |

## [02]-[TEXT_AND_WIRE]

[REGEX_GRAMMAR]:
- Owner: `[GeneratedRegex]` for a fixed structural grammar; `Regex` with `RegexOptions.NonBacktracking` for a runtime-built grammar over untrusted input.
- Rule: a count routes to `Regex.Count` and a position scan to `Regex.EnumerateMatches`, whose `ValueMatch` carries index and length with no `Match` allocation; timeout and culture ride the `[GeneratedRegex]` attribute, never a per-call argument the body re-derives.
- Reject: a hand-built static `Regex`; `Matches().Count` for a count; an ad-hoc boolean match loop; expecting `[GeneratedRegex]` to emit `RegexOptions.Compiled` IL — the source generator already emits the explicit-state matcher.

[SEARCH_AND_SPLIT]:
- Owner: `SearchValues<char>`, `SearchValues<byte>`, and `SearchValues<string>` with `MemoryExtensions.ContainsAny`, `ContainsAnyExcept`, `IndexOfAny`, `IndexOfAnyExcept`, `Split`, and `SplitAny`.
- Rule: `SearchValues<T>` is constructed once as a `static readonly` field beside the policy it enforces, and `SearchValues.Create(ReadOnlySpan<string>, StringComparison)` requires an explicit ordinal-family comparison; `MemoryExtensions.Split(source, Span<Range>, separator)` writes `Range` values over the source span, so slicing replaces every substring materialization and the destination span is the fixed arity the field caps.
- Reject: a regex used only for an allow/deny character check; multi-substring scans chained through `IndexOf`; `string.Split` on a parse path; a per-call `SearchValues.Create` where one `static readonly` field is the policy.

[FORMAT_AND_PARSE]:
- Owner: `CompositeFormat`, `string.Create`, `Span<char>.TryWrite`, and `Utf8.TryWrite` over the `ISpanFormattable`/`ISpanParsable<T>` and `IUtf8SpanFormattable`/`IUtf8SpanParsable<T>` pairs, with `u8` literals, `Utf8.FromUtf16`/`ToUtf16`, and `Ascii.IsValid` for the fast-path admission gate.
- Gate: wire and persisted values fix `CultureInfo.InvariantCulture` at the seam, never an ambient culture; chunked transcoding flows through the `OperationStatus` forms with the residual carried forward.
- Rule: a domain type appearing in formatted output implements the span-formattable pair and composes into `TryWrite` holes with no allocation; `IUtf8SpanParsable<T>` is independent of `ISpanParsable<T>` and carries its own constraint, so a UTF-8 parse path states it explicitly.
- Reject: repeated format-string parsing where `CompositeFormat.Parse` caches the segments; `StringBuilder` for fixed-length construction; a culture-ambient persisted value; `Encoding.UTF8.GetBytes` on a literal where `u8` is the constant; a UTF-16 round trip on a UTF-8 path.

[ENCODING]:
- Owner: `Encoding`, `Rune`, `Ascii`, `Base64Url`, `Convert.ToHexString`, and `ToHexStringLower`.
- Rule: codepoint-level work routes through `Rune` and user-perceived characters through `StringInfo` text elements, so a `char` predicate never applies to a surrogate half; `Base64Url.EncodeToUtf8`/`DecodeFromUtf8` own the URL-safe alphabet end to end where a `Convert.ToBase64String` plus a character-replace pass re-spells it.
- Reject: a manual hex loop; an unsafe ASCII check where `Ascii.IsValid` is the gate; a URL-base64 replace pass; a code-point predicate scattered across call sites instead of one text policy.

```csharp conceptual
[SmartEnum<string>]
[ValidationError<Fault>]
public sealed partial class Variant {
    static readonly SearchValues<char> HexDash = SearchValues.Create("0123456789ABCDEFabcdef-");
    static readonly SearchValues<char> HexWord = SearchValues.Create("0123456789ABCDEFabcdef_");

    public static readonly Variant Wire = new("<frame-a>", Separator: (byte)':', Allowed: HexDash);
    public static readonly Variant Local = new("<frame-b>", Separator: (byte)'=', Allowed: HexWord);

    [GeneratedRegex(@"^[a-z]+(?=[:=])", RegexOptions.NonBacktracking, matchTimeoutMilliseconds: 50)]
    public static partial Regex Heading { get; }

    public byte Separator { get; }
    public SearchValues<char> Allowed { get; }
}

public static class FrameCodec {
    public static Fin<int> Frame<T>(Variant variant, ReadOnlySpan<char> raw, Span<byte> sink, T value)
        where T : IUtf8SpanFormattable =>
        raw.ContainsAnyExcept(variant.Allowed) || !Ascii.IsValid(raw)
            ? Fin.Fail<int>(new Fault.Malformed(Detail: nameof(raw)))
            : Utf8.TryWrite(sink, CultureInfo.InvariantCulture, $"{variant.Key}{(char)variant.Separator}{raw}{value}", out var written)
                ? Fin.Succ(written)
                : Fin.Fail<int>(new Fault.Capacity(Detail: $"<sink:{sink.Length}>"));

    public static Fin<T> Decode<T>(ReadOnlySpan<char> heading, ReadOnlySpan<byte> payload) where T : IUtf8SpanParsable<T> =>
        Variant.Heading.EnumerateMatches(heading) is var scan && scan.MoveNext() && scan.Current is { Length: > 0 } head && Variant.Validate(heading.Slice(head.Index, head.Length), null, out var variant) is null
            ? payload.IndexOf(variant!.Separator) is var at and >= 0 && T.TryParse(payload[(at + 1)..], CultureInfo.InvariantCulture, out var value)
                ? Fin.Succ(value)
                : Fin.Fail<T>(new Fault.Malformed(Detail: nameof(payload)))
            : Fin.Fail<T>(new Fault.Malformed(Detail: nameof(heading)));
}
```

## [03]-[COLLECTIONS]

[READ_MOSTLY_AND_PROBE]:
- Owner: `FrozenDictionary`, `FrozenSet`, and the `GetAlternateLookup<ReadOnlySpan<char>>` span-key probe on both the frozen and live forms.
- Rule: a frozen table passes an explicit comparer, an alternate lookup requires an ordinal-family comparer implementing `IAlternateEqualityComparer`, and `TryGetAlternateLookup` is the non-throwing acquisition; the live `Dictionary`/`HashSet` alternate lookups also expose `TryAdd` and `Remove`, so span-keyed mutation needs no interim string.
- Reject: a static `Dictionary` rebuilt per call where `FrozenDictionary` bakes once; a string-key lookup copied per call; a `ToString` materialization before a keyed probe where the span lookup reads the source directly.

[IMMUTABLE_BOUNDARY_PAYLOAD]:
- Owner: `ImmutableArray`, `ImmutableDictionary`, and `ImmutableHashSet` at boundary payloads outside LanguageExt rails.
- Rule: `default(ImmutableArray<T>)` is a distinct throwing state guarded by `IsDefaultOrEmpty`; an exact-capacity builder hands off through `MoveToImmutable` with zero copy; `AsSpan` reads the backing array without exposing it.
- Boundary: domain sequence identity travels on `Seq<T>`/`Arr<T>` per `rails-and-effects.md`, never a BCL immutable; `ImmutableList<T>` on an indexed read path is the rejected form.

[ORDERED_AND_SCHEDULED]:
- Owner: `OrderedDictionary<TKey,TValue>` with `GetAt`/`SetAt`/`IndexOf` for insertion order, and `PriorityQueue<TElement,TPriority>` for heap scheduling.
- Rule: `OrderedDictionary<TKey,TValue>` keeps insertion order with index access where a sort-then-pop re-derives it, and `PriorityQueue` pops the minimum where a manual insertion-order map plus sort restates the heap.
- Reject: a sort-then-pop loop; a manual insertion-order map; treating `OrderedDictionary<TKey,TValue>` as an LRU cache — eviction policy is `runtime.md`'s `CACHE_LAW`.

[SET_ALGEBRA_AND_INTERNALS]:
- Owner: the keyed LINQ operators `ToLookup`, `DistinctBy`, `CountBy`, `AggregateBy`, `ExceptBy`, `IntersectBy`, `UnionBy`, `Index`, `LeftJoin`, `RightJoin`; and `CollectionsMarshal.GetValueRefOrAddDefault`, `GetValueRefOrNullRef`, `AsSpan`, and `SetCount` at measured boundaries.
- Rule: `CountBy`/`AggregateBy` fold per key in one pass where a `GroupBy` then a per-group reduce materializes the groups; `LeftJoin`/`RightJoin` retire the `GroupJoin`-`SelectMany`-`DefaultIfEmpty` idiom; the same operator names transpose to `IAsyncEnumerable<T>` through the BCL `AsyncEnumerable` surface, and the `WhereAwait`-style spelling belongs to an external package and is the rejected form.
- Exemption: `GetValueRefOrAddDefault` returns a `ref TValue?` into the bucket plus the `out bool exists` first-write witness — the one statement seam this card forces — so a running multi-field accumulator threads through one hash probe per row where `AggregateBy` reallocates its accumulator each step and cannot expose a `ref` into the live bucket; a pure single-field per-key reduce is `AggregateBy`'s and never takes the seam. The list size is pinned before `AsSpan` because a resizing `Add` invalidates the span, and a `GetValueRefOrNullRef` result is tested with `Unsafe.IsNullRef`.
- Reject: a repeated `GroupBy` for a count or fold; a loop dedup where `DistinctBy` keys it; a manual index counter where `Index` carries position; a comparer-free keyed set operation where the domain rule is not default equality; a `TryGetValue`-then-`Add` double probe; domain public identity built from mutable dictionary internals.

```csharp conceptual
public static class Tally {
    static readonly FrozenDictionary<string, int> Ranks =
        new Dictionary<string, int> { ["<key-a>"] = 1, ["<key-b>"] = 2 }
            .ToFrozenDictionary(StringComparer.Ordinal);

    static readonly FrozenDictionary<string, int>.AlternateLookup<ReadOnlySpan<char>> Probe =
        Ranks.GetAlternateLookup<ReadOnlySpan<char>>();

    public readonly record struct Roll(int Count, int Peak, int FirstAt);

    public static Fin<int> RankOf(ReadOnlySpan<char> key) =>
        Probe.TryGetValue(key, out var rank) ? Fin.Succ(rank) : Fin.Fail<int>(new Fault.Unknown(Detail: key.ToString()));

    public static ImmutableArray<(int Rank, string Key, Roll Roll)> Fold(params ReadOnlySpan<(string Key, int Score)> rows) {
        var rolls = new Dictionary<string, Roll>(rows.Length, StringComparer.Ordinal);
        for (var i = 0; i < rows.Length; i++) {                              // Exemption: one ref probe threads count+peak+first-ordinal; AggregateBy reallocates per step and joins in a second pass
            ref var roll = ref CollectionsMarshal.GetValueRefOrAddDefault(rolls, rows[i].Key, out var exists);
            roll = new Roll(roll.Count + 1, Math.Max(roll.Peak, rows[i].Score), exists ? roll.FirstAt : i);
        }
        return [.. rolls.Select(row =>
            (Rank: Probe.TryGetValue(row.Key, out var r) ? r : int.MaxValue, row.Key, row.Value))];
    }
}
```

## [04]-[IO_AND_INTEGRITY]

[PATH_AND_FILE_IO]:
- Owner: `Path.Join`, `Path.Exists`, `File.OpenHandle`, `RandomAccess.Read`/`ReadAsync`/`Write`/`WriteAsync`/`GetLength`/`SetLength`, `FileStreamOptions`, and `File.ReadLinesAsync`.
- Rule: `RandomAccess` is stateless and offset-addressed — position is caller-owned, so concurrent readers on distinct offsets need no lock — and `Path.Exists` answers file-or-directory in one call where bifurcated `File.Exists`/`Directory.Exists` checks split it; a wire length validates against a bounded cap before allocation, and async handle IO requires `FileOptions.Asynchronous` at open or the async call silently degrades to pool emulation.
- Rule: `RandomAccess.ReadAsync` returns the bytes actually transferred and never guarantees a full fill, so read-exactly is the returned-count check against the requested window length (`Stream.ReadExactlyAsync`/`ReadAtLeastAsync` are the stream-shaped forms and have no `RandomAccess` peer), and a short return is a malformed-frame fault, never a silent partial.
- Reject: a seek/read loop where `RandomAccess.Read` is offset-addressed; ad-hoc `FileStream` construction; a `FileStream` opened only for `Length` or `Flush`; bifurcated existence checks; `Path.Combine` where a rooted right segment must not discard the left.

[BUFFERS_AND_PIPELINES]:
- Owner: `ArrayPool<T>`, `MemoryPool<T>`, `ReadOnlySequence<T>`, `SequenceReader<T>`, `BinaryPrimitives`, `PipeReader`, and `PipeWriter`.
- Rule: `BinaryPrimitives.TryReadUInt32BigEndian` reads an endian-fixed wire field where `BitConverter` leaks host endianness, and `SequenceReader<T>` walks a segmented `ReadOnlySequence<T>` where a copy-to-array flattens it; a rented array returns in `finally` and an `IMemoryOwner<T>` carries the lease across `await`.
- Exemption: the `Rent`/`try`/`finally`/`Return` pool-lease bracket inside an `async` boundary method is the named platform-forced statement seam — `IO<T>.BracketIO` is the domain-flow owner, but a localized async pool window the rail never observes returns deterministically in `finally`; the leased span never escapes and the method still yields a `Fin<T>`.
- Reject: an unbounded `MemoryStream`; a `new byte[n]` scratch buffer where `ArrayPool<T>` leases it; `BitConverter` for an endian wire frame.

[INTEGRITY]:
- Owner: `CryptographicOperations.HashData`/`HmacData` by `HashAlgorithmName`, the per-algorithm one-shots, `FixedTimeEquals`, `RandomNumberGenerator`, and the non-secret hash family `XxHash3`, `XxHash64`, and `Crc32`.
- Rule: `CryptographicOperations.HashData(HashAlgorithmName, ...)` selects the algorithm by name so the owning type is the entire security decision, and `Random.Shared` and `RandomNumberGenerator` expose the same `GetItems`/`GetString`/`Shuffle`/`Fill` surface so the choice between them is the only decision; `SHA3`/`SHAKE` one-shots are guarded behind their `IsSupported` statics, tag comparison is `FixedTimeEquals` never `==`.
- Rule: the non-secret family discriminates by width and intent, not preference — `XxHash3.HashToUInt64` is the in-memory cache and content key, `XxHash64` widens it only where a 64-bit collision floor is too low for the keyspace, and `Crc32.Append`/`GetCurrentHash` is the transmission-frame check a receiver recomputes, never a lookup key; one chosen width is a composition-time invariant, never a per-site coin-flip.
- Boundary: a cryptographic digest, signature, or persisted content key is `boundaries.md`'s `BYTE_IDENTITY` — one canonical byte-codec per identity domain, asserted once — so this card owns the in-process non-cryptographic key choice (`XxHash3.HashToUInt64` over `SHA256`) and the secure-random source, never the persisted-identity codec.
- Reject: a constructed hash or HMAC instance used once and discarded; `System.Random` for cryptographic bytes; `SHA256` for an in-process cache key; `Crc32` as a lookup key or `XxHash3` as a wire-integrity frame check; persisting any `GetHashCode` output — in-process hashes are process-randomized.

```csharp conceptual
public readonly record struct Extent(long Offset, int Length);

public readonly record struct Segment(ulong ContentKey, uint Frame, int Length);

public static class SegmentReader {
    public static Fin<SafeFileHandle> Open(string path) =>
        Path.Exists(path)
            ? Fin.Succ(File.OpenHandle(path, options: FileOptions.Asynchronous | FileOptions.RandomAccess))
            : Fin.Fail<SafeFileHandle>(new Fault.Missing(Detail: path));

    public static Fin<Extent> Bound(SafeFileHandle handle, long offset, int request, int cap) =>
        request <= 0 || request > cap
            ? Fin.Fail<Extent>(new Fault.Capacity(Detail: $"<request:{request}>"))
            : offset + request + sizeof(uint) > RandomAccess.GetLength(handle)
                ? Fin.Fail<Extent>(new Fault.Bounds(Detail: $"<extent@{offset}>"))
                : Fin.Succ(new Extent(offset, request));

    public static async Task<Fin<Segment>> Read(SafeFileHandle handle, Extent extent) {
        var rented = ArrayPool<byte>.Shared.Rent(extent.Length + sizeof(uint));
        try {
            var window = rented.AsMemory(0, extent.Length + sizeof(uint));
            return await RandomAccess.ReadAsync(handle, window, extent.Offset) != window.Length
                ? Fin.Fail<Segment>(new Fault.Malformed(Detail: $"<short-read@{extent.Offset}>"))
                : Verify(window.Span[..extent.Length], BinaryPrimitives.ReadUInt32BigEndian(window.Span[extent.Length..]));
        }
        finally { ArrayPool<byte>.Shared.Return(rented); }
    }

    static Fin<Segment> Verify(ReadOnlySpan<byte> body, uint stamped) =>
        Crc32.HashToUInt32(body) is var frame && frame == stamped
            ? Fin.Succ(new Segment(XxHash3.HashToUInt64(body), frame, body.Length))
            : Fin.Fail<Segment>(new Fault.Corrupt(Detail: $"<crc {frame:x8} != {stamped:x8}>"));
}
```

## [05]-[BOUNDARY_PRIMITIVES]

[SEAM_GUARDS]:
- Owner: `ArgumentNullException.ThrowIfNull`, `ArgumentException.ThrowIfNullOrEmpty`/`ThrowIfNullOrWhiteSpace`, the `ArgumentOutOfRangeException.ThrowIf` comparison family, `ObjectDisposedException.ThrowIf`, the nullable-flow annotations `NotNullWhen`/`NotNullIfNotNull`/`MemberNotNull`/`DoesNotReturn`/`StringSyntax`, and `[CallerArgumentExpression]`.
- Rule: `[CallerArgumentExpression]` captures the argument expression into the exception with no hand-formatted parameter-name string, and the `ThrowIfGreaterThanOrEqual`/`ThrowIfLessThan` comparison guards constrain on `where T : IComparable<T>` so signed, unsigned, and floating bounds share one spelling (`ThrowIfNegative`/`ThrowIfZero` widen to `INumberBase<T>`); these guard a host or library seam, and the nullable-flow annotations delete the null-forgiving scatter after a `Try*` or guard call.
- Boundary: domain admission stays on Thinktecture generated owners and typed rails per `BOUNDARY_ADMISSION`; a data annotation validates a wire DTO at the converter seam, never a domain value, so a guard here precedes the rail bridge and never stands in for it.
- Reject: a guard-block `if`-`throw` argument check; a hand-formatted parameter-name message; null-forgiving scatter after a guard API; a guard used as domain admission.

[COMPILER_AND_INTEROP]:
- Owner: `MethodImpl`, `CallerMemberName`, custom interpolated string handlers, `CollectionBuilder`, `StructLayout`, `MemoryMarshal`, `NativeMemory`, `SuppressGCTransition`, `[LibraryImport]` with `StringMarshalling`/`StringMarshallingCustomType`, and `[UnmanagedCallConv]`.
- Rule: `[LibraryImport]` source-generates the marshalling stub at compile time and is the trim-safe, NativeAOT-compatible P/Invoke seam; `StringMarshalling.Utf8` fixes the encoding at the attribute where a manual `Marshal.StringToHGlobalAnsi` round trip re-spells it, and `[UnmanagedCallConv(CallConvs = [typeof(CallConvSuppressGCTransition)])]` is the cooperative-GC fast call a blittable leaf invocation states once.
- Boundary: the native handle, the borrowed-memory window, and the callback are `boundaries.md`'s `CAPSULE_OWNER`/`REF_SAFE_PROJECTION`/`SUBSCRIPTION_VALUE` — the marshalling-stub-on-a-`SafeHandle` lives there; this card owns the marshalling-attribute selection only, and an `unsafe` interop body requires measured proof plus that boundary owner.
- Reject: a `[DllImport]` runtime marshalling stub under a trimming owner; a hand-marshalled string where `StringMarshalling` is declarative; an `unsafe` block with no measured proof and no boundary capsule.

```csharp conceptual
public static partial class HostSeam {
    [LibraryImport("<native>", EntryPoint = "probe_slot", StringMarshalling = StringMarshalling.Utf8)]
    [UnmanagedCallConv(CallConvs = [typeof(CallConvSuppressGCTransition)])]
    private static partial int Probe(string token, uint slot);

    public static Fin<int> Reserve(string token, uint slot, uint cap) {
        ArgumentException.ThrowIfNullOrWhiteSpace(token);
        ArgumentOutOfRangeException.ThrowIfGreaterThanOrEqual(slot, cap);
        return Probe(token, slot) is var code && Resolve(code, out var reserved)
            ? Fin.Succ(reserved.Value)
            : Fin.Fail<int>(new Fault.NativeRejected(Detail: $"<probe:{code}>"));
    }

    static bool Resolve(int code, [NotNullWhen(true)] out int? reserved) =>
        (reserved = code >= 0 ? code : null) is not null;
}
```
