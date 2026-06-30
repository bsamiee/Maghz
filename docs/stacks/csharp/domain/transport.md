# [TRANSPORT]

Wire transport is one axis declared at composition roots. Every cross-package call travels a typed port record — call arrows plus policy values, zero provider types — materialized from a closed transport-row vocabulary, so in-process hand-off, UDS companion, remote TLS, and browser translation are rows of one axis and a call site can neither see nor select the byte mover. One generated message per concept is the wire vocabulary, and evolution is one descriptor-diff classifier whose verdict gates peer attach, store open, and replay decode alike; temporal values cross as well-known types through one dual-codec bridge; server exposure is one record folded at the app root; local endpoints live behind a discovery manifest whose publish-last ordering makes liveness a single observable bit; raw corridors admit frames under one four-gate invariant; suite JSON is one frozen resolver merge whose schema export rides the same evolution gate; partial updates are recorded intent applied once and re-admitted whole. Hop resilience arrives composed — the channel's retry row or the seam's pipeline owns each hop, declared as one row column, never both. Growth lands as rows: a new peer is a route row, a new service an exposure row, a new wire family one contract context, a new frame kind one cap row.

## [01]-[TRANSPORT_CHOOSER]

This table routes a wire concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]            | [OWNER]                                   | [REJECTED_FORM]                |
| :-----: | :------------------- | :---------------------------------------- | :----------------------------- |
|  [01]   | peer channel         | one channel row per authority at the root | per-call `ForAddress` scatter  |
|  [02]   | cross-package calls  | port record + transport-row column        | `if (remote)` call-site branch |
|  [03]   | wire retry           | per-row owner column: channel or seam     | stacked double owner           |
|  [04]   | contract evolution   | descriptor-diff classifier verdict        | per-seam compatibility checks  |
|  [05]   | temporal wire values | well-known types + converter slots        | serialized temporal text       |
|  [06]   | server exposure      | one exposure record fold at the app root  | per-service options scatter    |
|  [07]   | wire faults          | structured detail in `-bin` trailers      | code-plus-string parsing       |
|  [08]   | browser access       | translation row + endpoint consent        | second browser client          |
|  [09]   | local endpoint       | manifest-gated UDS lifecycle              | ad-hoc socket paths            |
|  [10]   | peer identity        | connection-level kernel credentials       | call-context peer read         |
|  [11]   | artifact corridor    | framed-corridor invariant                 | unframed stream writes         |
|  [12]   | suite JSON contracts | resolver merge + frozen options           | reflection-fallback chain      |
|  [13]   | partial updates      | recorded-intent patch, apply-only         | state-diff endpoint            |

## [02]-[CONTRACT_AXIS]

[PORT_LAW]:
- Law: the only cross-package transport seam is a fixed small set of typed port records — call arrows plus policy values, zero interfaces, zero inheritance, zero provider types in the signature — and a consumer binds the record, never channel, invoker, or handler types; the aggregate port bundling every operation a package exposes and the provider-branded port are the two named defect forms.
- Law: the contract is a value — `Method<TReq,TRes>` built once from `MethodType`, service and verb symbols, and `Marshallers.Create` over the generated message's `ToByteArray`/`Parser.ParseFrom` — and generated clients are edge adapters materialized at the root from `CreateCallInvoker()`; the generated client type never crosses a package boundary.
- Law: stream shape is carrier dispatch — a value case maps to unary, a subscription case to a server-stream drained by `ResponseStream.ReadAllAsync`, a sequence case to a client-stream whose response materializes only after `RequestStream.CompleteAsync()`, a duplex case to independent sides — every call object is `IDisposable` with disposal of an undrained call as the cancellation idiom, one write at a time per `IAsyncStreamWriter<T>` serialized through a lane upstream, and the only backpressure primitives are await-on-`WriteAsync` and pull-on-`ReadAllAsync`; shape-suffixed verb families are the foreclosed spelling.
- Exemption: the stream-drain iterator — call disposal held open across `yield` — is the platform-forced statement seam.

[ROW_AXIS]:
- Law: one `GrpcChannel` per remote authority per process, created once and held for process life — it owns connection pooling, retry buffers, balancer state, and the compression registry; channel policy is one `GrpcChannelOptions` site whose defaults are restated as row values — receive cap 4_194_304, send cap absent, retry buffer 1_048_576 per call — and per-call variance is `CallOptions` only.
- Law: connectivity is a held state machine — `ConnectAsync` warms the channel before the first deadline-bearing call, `WaitForStateChangedAsync` parks the watch loop as state, wait, re-read, never polling, and both are unavailable when the channel wraps a caller-supplied `HttpClient`; `Dispose` closes connections only when the channel owns its handler, so one shared `SocketsHttpHandler` across rows keeps handler lifetime at the root.
- Law: address resolution is a scheme row — `dns:///` re-resolves periodically, `static:///` plus a registered `StaticResolverFactory` serves manifest-published address sets, and `LoadBalancingConfigs` selects `PickFirstConfig` failover or `RoundRobinConfig` rotation, activated by `ServiceProvider` on the channel options; `Resolver.Refresh()` is the manifest-change hook, and `DisableResolverServiceConfig` pins root-declared policy against resolver override.
- Law: long-lived stream columns require keep-alive rows — `KeepAlivePingDelay`, `KeepAlivePingTimeout`, `KeepAlivePingPolicy` (`WithActiveRequests` versus `Always` for idle push streams) — or an idle middlebox kills the connection and the next write surfaces as `Unavailable` minutes later; fan-out past the server's max-concurrent-streams queues invisibly until `EnableMultipleHttp2Connections` is set.
- Law: the browser row is a handler wrap, not a different client — `GrpcWebHandler(GrpcWebMode.GrpcWebText, inner)`; text mode is mandatory for server-streaming to stream, binary buffers, and the client-stream and duplex columns are structurally absent on this row — route those calls to an HTTP/2 row or reshape the contract.
- Law: trust is a closed row set — `ChannelCredentials.Insecure` for UDS and loopback, `SecureSsl`, `Create(channel, call)` for TLS plus identity — mutual-TLS identity rides `SslOptions` on the handler row, and `UnsafeUseInsecureChannelCallCredentials` is legal only where the transport itself is the perimeter.

```csharp conceptual
public sealed record PeerRoute(Uri Authority, string SocketPath);
public sealed record Port<TReq, TRes>(
    Func<TReq, CallOptions, Task<TRes>> Ask, Func<TReq, CallOptions, IAsyncEnumerable<TRes>> Watch, TimeSpan Budget, bool ChannelRetry);

[SmartEnum<string>]
public sealed partial class TransportRow {
    public static readonly TransportRow InProcess = new("<row-a>", channelRetry: false, static _ => Option<GrpcChannel>.None);
    public static readonly TransportRow Companion = new("<row-b>", channelRetry: false, static route => Some(GrpcChannel.ForAddress(route.Authority,
        new GrpcChannelOptions {
            Credentials = ChannelCredentials.Insecure,
            HttpHandler = new SocketsHttpHandler { ConnectCallback = async (_, token) => {
                var socket = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.IP);
                await socket.ConnectAsync(new UnixDomainSocketEndPoint(route.SocketPath), token).ConfigureAwait(false);
                return new NetworkStream(socket, ownsSocket: true);
            } },
        })));
    public static readonly TransportRow Remote = new("<row-c>", channelRetry: true, static route => Some(GrpcChannel.ForAddress(route.Authority,
        new GrpcChannelOptions {
            Credentials = ChannelCredentials.SecureSsl,
            MaxReceiveMessageSize = 4_194_304,
            HttpHandler = new SocketsHttpHandler { EnableMultipleHttp2Connections = true, KeepAlivePingDelay = TimeSpan.FromSeconds(30) },
            ServiceConfig = new ServiceConfig { MethodConfigs = { new MethodConfig { Names = { MethodName.Default },
                RetryPolicy = new RetryPolicy { MaxAttempts = 4, InitialBackoff = TimeSpan.FromMilliseconds(100), MaxBackoff = TimeSpan.FromSeconds(2), BackoffMultiplier = 2, RetryableStatusCodes = { StatusCode.Unavailable } } } } },
        })));
    public static readonly TransportRow Browser = new("<row-d>", channelRetry: false, static route => Some(GrpcChannel.ForAddress(route.Authority,
        new GrpcChannelOptions { HttpHandler = new GrpcWebHandler(GrpcWebMode.GrpcWebText, new HttpClientHandler()) })));
    public bool ChannelRetry { get; }

    [UseDelegateFromConstructor]
    public partial Option<GrpcChannel> Channel(PeerRoute route);
}

public static class ContractAxis {
    public static Port<TReq, TRes> Materialize<TReq, TRes>(TransportRow row, PeerRoute route, TimeSpan budget,
        Method<TReq, TRes> ask, Method<TReq, TRes> watch, Port<TReq, TRes> local) where TReq : class where TRes : class {
        ArgumentNullException.ThrowIfNull(row);
        return row.Channel(route).Map(static channel => channel.CreateCallInvoker()) is { IsSome: true, Case: CallInvoker invoker }
            ? new Port<TReq, TRes>(
                (request, options) => invoker.AsyncUnaryCall(ask, host: null, options, request).ResponseAsync,
                (request, options) => Drained(invoker.AsyncServerStreamingCall(watch, host: null, options, request), options.CancellationToken),
                budget, row.ChannelRetry)
            : local;
    }

    private static async IAsyncEnumerable<TRes> Drained<TRes>(AsyncServerStreamingCall<TRes> call, [EnumeratorCancellation] CancellationToken token) {
        using var owned = call;
        await foreach (var item in call.ResponseStream.ReadAllAsync(token).ConfigureAwait(false)) { yield return item; }
    }
}
```

## [03]-[CALL_SEAM]

[CALL_LAW]:
- Law: `CallOptions(headers, deadline, cancellationToken)` is the per-call policy triple, minted inside the port delegate from the hop row — the deadline is one absolute UTC instant computed from the row's budget at the outermost site, transmitted as the wire timeout header so the server observes remaining budget, and inner hops only shrink it; a deadline already in the past fails locally with `DeadlineExceeded`, zero latency, and no trailers — the signature separating budget exhaustion from server slowness.
- Law: the foreign `StatusCode` enum folds once at the boundary into the closed `TransportFault` `[Union]` deriving from `Expected` — `DeadlineExceeded` to `Deadline`, `Cancelled` to `Cancelled`, `Unavailable` to `Unreachable`, `ResourceExhausted` to `Exhausted`, `Unimplemented` to `Drift`, every other code to `Wire(StatusCode, Detail)` — so recovery dispatches on the typed case through `HasCode`/`IsType`, never a bare coded `Error.New` and never interior dispatch on status strings; `RpcException.Trailers` carries the structured fault decoded at the same fold, and `ThrowOperationCanceledOnCancellation = true` re-rails termination onto the cancellation rail only where a surrounding pipeline owns cancellation unification — where the port fold is the seam it stays false so one typed fold serves every termination.
- Law: exactly one stamping interceptor per channel, installed at invoker creation — `Intercept(Func<Metadata,Metadata>)` covers all five call shapes from one delegate, a full `Interceptor` subclass is earned only by response-side inspection, and `Intercept(params Interceptor[])` applies first-element-outermost while chained `Intercept` calls make the last outermost, so a second stamper is a merge conflict, never a layer; the stamped envelope content arrives settled from the correlation spine.
- Law: binary metadata requires the `-bin` suffix (`Metadata.BinaryHeaderSuffix`) — the entry constructor enforces the byte/string split and lowercases keys, `GetValueBytes` is the read verb, and `Metadata.Empty` is frozen, so stamping always allocates.
- Law: transport retry is data — `MethodConfig` rows pair `MethodName` selectors with exactly one of `RetryPolicy` or `HedgingPolicy`; a present row makes the channel the hop's one retry owner and a seam pipeline beside it the second-owner conflict, so the choice is a per-row owner column auditable without reading code; hedging duplicates the call in flight after each `HedgingDelay`, admissible for idempotent methods only, and its receipt records attempt cardinality or the diagnostics fold under-counts wire traffic.
- Law: retry commitment is structural — observed response data or buffered request bytes past `MaxRetryBufferPerCallSize` commit the in-flight attempt, so large payloads silently exit retry protection at the 1_048_576 default; `RetryThrottlingPolicy` is the channel-wide brake converting downstream brownout into reduced retry pressure, and `MaxRetryAttempts` caps whatever the config requests.
- Law: per-call identity is `CallCredentials.FromInterceptor` with token refresh inside the delegate and `CallCredentials.Compose` stacking identities — composed call credentials transmit only over TLS unless the unsafe channel row names the perimeter.
- Law: request compression is a per-call metadata opt-in — the `grpc-internal-encoding-request` entry names a registered `CompressionProviders` row, response decompression is automatic from the registry, and `WriteOptions` with `WriteFlags.NoCompress` exempts individual messages inside a compressed stream — the mixed-entropy row.
- Exemption: the awaited capture kernel — the `RpcException` catch arm — and the `Metadata` stamping sweep over the mutable host collection the interceptor contract returns are the platform-forced statement seam.

```csharp conceptual
[Union]
public abstract partial record TransportFault : Expected {
    private TransportFault(string detail, int code) : base(detail, code, None) { }
    // --- [CALL_SEAM] 761x
    public sealed record Wire(StatusCode Status, string Detail) : TransportFault($"<status:{Status}:{Detail}>", 7610);
    public sealed record Deadline : TransportFault { public Deadline() : base("<budget-spent>", 7611) { } }
    public sealed record Cancelled : TransportFault { public Cancelled() : base("<caller-left>", 7612) { } }
    public sealed record Unreachable : TransportFault { public Unreachable() : base("<unreachable-or-draining>", 7613) { } }
    public sealed record Exhausted : TransportFault { public Exhausted() : base("<cap-breach>", 7614) { } }
    public sealed record Drift(string Detail) : TransportFault($"<contract-drift:{Detail}>", 7615);
    // --- [SUITE_CONTRACTS] 762x
    public sealed record Fork(string Detail) : TransportFault($"<contract-fork:{Detail}>", 7620);
    // --- [ENDPOINT_LIFECYCLE] 763x
    public sealed record Publish(string Detail) : TransportFault($"<publish:{Detail}>", 7630);
    public sealed record Unpublished(string Detail) : TransportFault($"<unpublished:{Detail}>", 7631);
    public sealed record Stale(long Epoch) : TransportFault($"<stale-listener:{Epoch}>", 7632);
    // --- [CORRIDOR] 764x
    public sealed record Oversize(int Size, int Cap) : TransportFault($"<oversize:{Size}:{Cap}>", 7640);
    public sealed record Truncated(string At) : TransportFault($"<truncated:{At}>", 7641);
    public sealed record Corrupt : TransportFault { public Corrupt() : base("<corrupt-frame>", 7642) { } }
    public sealed record Misframed(string Detail) : TransportFault($"<misframed:{Detail}>", 7643);
}

public static class CallSeam {
    private const string FaultKey = "fault-detail-bin";

    public static CallInvoker Stamped(GrpcChannel channel, Func<Seq<(string Key, string Value)>> departure) {
        ArgumentNullException.ThrowIfNull(channel);
        return channel.CreateCallInvoker().Intercept(headers => {
            var stamped = headers ?? [];                                   // Exemption: Metadata is the mutable host collection the Func<Metadata,Metadata> seam returns; the pair sweep is the platform-forced statement seam, never a fold-costume over in-place mutation
            departure().Iter(pair => stamped.Add(pair.Key, pair.Value));
            return stamped;
        });
    }
    public static async Task<Fin<TRes>> Ask<TReq, TRes>(CallInvoker invoker, Method<TReq, TRes> contract, TReq request,
        TimeSpan budget, TimeProvider clock, CancellationToken caller, Func<byte[], Error> decode) where TReq : class where TRes : class {
        ArgumentNullException.ThrowIfNull(invoker);
        ArgumentNullException.ThrowIfNull(clock);
        var options = new CallOptions(deadline: clock.GetUtcNow().UtcDateTime + budget, cancellationToken: caller);
        try { return Fin.Succ(await invoker.AsyncUnaryCall(contract, host: null, options, request).ResponseAsync.ConfigureAwait(false)); }
        catch (RpcException wire) { return Fin.Fail<TRes>(Fold(wire, decode)); }
    }

    private static Error Fold(RpcException wire, Func<byte[], Error> decode) => wire.StatusCode switch {
        StatusCode.DeadlineExceeded => new TransportFault.Deadline(),
        StatusCode.Cancelled => new TransportFault.Cancelled(),
        StatusCode.Unavailable => new TransportFault.Unreachable(),
        StatusCode.ResourceExhausted => new TransportFault.Exhausted(),
        StatusCode.Unimplemented => new TransportFault.Drift(wire.Status.Detail),
        _ => Optional(wire.Trailers.GetValueBytes(FaultKey)).Map(decode).IfNone(new TransportFault.Wire(wire.StatusCode, wire.Status.Detail)),
    };
}
```

## [04]-[CONTRACT_EVOLUTION]

[MESSAGE_LAW]:
- Law: the generated message IS the wire vocabulary — one concept owns one message, every transport surface is a boundary projection of it, and parallel DTOs per surface are the foreclosed form; `RepeatedField<T>` and `MapField<K,V>` mutate only during construction and project to immutable collections at admission.
- Law: absence-bearing fields are declared `optional` at authoring so `HasPresence` projects absent-versus-default into the option carrier; `Any.Pack`/`Is`/`Unpack` serves only slots foreign packages must extend — an owned case family is a oneof — and `FieldMask` is the binary-native sparse-update vocabulary.
- Law: `MergeFrom` is merge, not replace — scalars overwrite, singular messages merge recursively, repeated fields APPEND, map entries overwrite per key — so parsing into a reused message accumulates repeated content; `Parser.ParseFrom` allocates fresh and is the default read spelling, the `ReadOnlySequence<byte>` overload parses fragmented frames without coalescing, and `CodedInputStream.CreateWithLimits` binds size and recursion bounds (default 100) as declared policy per contract family.
- Law: `UnknownFieldSet` preserves unrecognized fields through parse-mutate-serialize round-trips — the structural mechanism that makes additive evolution safe across mixed-version processes; protobuf-JSON round-trips strip unknown fields and silently defeat it, so the `JsonFormatter.Settings`/`JsonParser.Settings` rows with `TypeRegistry` are edge inspection, never relay.
- Law: `ByteString` is the zero-copy carrier — `Span` and `Memory` read allocation-free, `UnsafeByteOperations.UnsafeWrap` wraps large one-shot payloads under the obligation that the wrapped memory outlives the message, discharged by scoping serialize-and-send inside the buffer lease; `CopyFrom` is the safe default, and exact `CalculateSize` contribution makes corridor cap pre-checks precise with no serialization probe.

[DESCRIPTOR_GATE]:
- Law: every generated contract self-describes — `FileDescriptor.SerializedData` and `ToProto()` — so the running process publishes descriptors per contract file and the gate rebuilds both generations and diffs structurally; runtime descriptors are exactly what the binary carries, and no build-step plumbing exists or is wanted.
- Law: the diff algebra is closed — additive: new message, new field on an unused number, new enum value, new method; breaking: number reuse, `FieldType` change, singular-repeated flip, packed flip, oneof membership change, and field rename on a live number wherever a JSON projection exists, because `JsonName` is contract; removal demands ceremony — the number enters `ReservedRange` or the removal classifies as breaking, since the number is re-claimable.
- Law: one classifier verdict gates three seams — peer attach, store open, replay decode — so evolution is legislated once and consumed as a verdict value; enum renames are binary-additive but JSON-breaking, and reflection tooling reads descriptor names, never CLR names.
- Law: the gate owns the diff-relevant projection — field number, type, cardinality, packing, oneof membership, `JsonName`, reserved ranges, and method set in `InDeclarationOrder()` — and feeds it to the one canonical byte-identity codec, never a second hashing path: the projection is the transport-owned region, the digest is `boundaries.md` `BYTE_IDENTITY` and `system-apis.md` `INTEGRITY` composed (`XxHash3.HashToUInt64`), and the suite-JSON schema hash reuses that same codec over its own schema-node projection. Hashing raw `SerializedData` is the rejected form because descriptor bytes are not canonical across generator versions, and re-spelling the hash recipe per surface is the rejected duplication the shared codec deletes.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Verdict {
    private Verdict() { }
    public sealed record Identical : Verdict;
    public sealed record Additive : Verdict;
    public sealed record Breaking(Seq<string> Violations) : Verdict;
}

public static class DescriptorGate {
    public static string Checksum(FileDescriptor contract) {
        ArgumentNullException.ThrowIfNull(contract);
        return XxHash3.HashToUInt64(Encoding.UTF8.GetBytes(string.Join(';', Projection(contract)))).ToString("x16", CultureInfo.InvariantCulture);
    }

    public static Verdict Classify(FileDescriptor held, FileDescriptor observed) {
        ArgumentNullException.ThrowIfNull(held);
        ArgumentNullException.ThrowIfNull(observed);
        return toSeq(held.MessageTypes).Bind(message =>
                Optional(observed.FindTypeByName<MessageDescriptor>(message.Name))
                    .Map(peer => FieldViolations(message, peer)).IfNone(() => [$"<removed-message:{message.Name}>"]))
            .Append(toSeq(held.Services).Bind(service =>
                observed.Services.FirstOrDefault(peer => peer.Name == service.Name) is { } peer
                    ? toSeq(service.Methods).Choose(method =>
                        peer.FindMethodByName(method.Name) is null ? Some($"<removed-method:{service.Name}/{method.Name}>") : None)
                    : [$"<removed-service:{service.Name}>"])) is { IsEmpty: false } violations
            ? new Verdict.Breaking(violations)
            : Checksum(held) == Checksum(observed) ? new Verdict.Identical() : new Verdict.Additive();
    }

    private static Seq<string> Projection(FileDescriptor contract) =>
        toSeq(contract.MessageTypes).Bind(static message =>
            toSeq(message.Fields.InDeclarationOrder())
                .Map(field => $"{message.Name}.{field.FieldNumber}:{field.FieldType}:{(field.IsRepeated ? "R" : "S")}:{(field.IsPacked ? "P" : "-")}:{field.ContainingOneof?.Name}:{field.JsonName}")
                .Append(toSeq(message.ToProto().ReservedRange).Map(range => $"{message.Name}.reserved:{range.Start}-{range.End}")))
            .Append(toSeq(contract.Services).Bind(static service => toSeq(service.Methods).Map(method => $"{service.Name}/{method.Name}")));

    private static Seq<string> FieldViolations(MessageDescriptor held, MessageDescriptor observed) =>
        toSeq(held.Fields.InDeclarationOrder()).Choose(field =>
            observed.FindFieldByNumber(field.FieldNumber) is { } peer
                ? peer.FieldType != field.FieldType || peer.IsRepeated != field.IsRepeated || peer.IsPacked != field.IsPacked || peer.ContainingOneof?.Name != field.ContainingOneof?.Name || peer.JsonName != field.JsonName
                    ? Some($"<retyped:{held.Name}.{field.FieldNumber}>") : None
                : toSeq(observed.ToProto().ReservedRange).Exists(range => field.FieldNumber >= range.Start && field.FieldNumber < range.End)
                    ? None : Some($"<reclaimable:{held.Name}.{field.FieldNumber}>"));
}
```

[TEMPORAL_BRIDGE]:
- Law: domain time crosses wire contracts as well-known types, never as serialized temporal text — both directions are `NodaTime.Serialization.Protobuf` extension projections at the bridge, never a hand-rolled BCL round-trip through `DateTime`: inward is `ProtobufExtensions` on the wire type (`Timestamp.ToInstant`, `Duration.ToNodaDuration`, `Date.ToLocalDate`, `TimeOfDay.ToLocalTime`, `DayOfWeek.ToIsoDayOfWeek`), outward is `NodaExtensions` on the domain type (`Instant.ToTimestamp`, `NodaTime.Duration.ToProtobufDuration`, `LocalDate.ToDate`, `LocalTime.ToTimeOfDay`, `IsoDayOfWeek.ToProtobufDayOfWeek`), and no temporal value exists between seams in wire shape; the `Timestamp.FromDateTime`-over-`Instant.ToDateTimeUtc()` detour is the rejected re-spelling of `ToTimestamp` the package already owns. The calendar `Date`, `TimeOfDay`, and `DayOfWeek` projections need the `google.type` common-proto contracts admitted, so a suite carrying calendar wire values declares that package before the law reaches them.
- Law: the range contracts throw and project onto one coded fault band at the seam — `Timestamp.ToInstant` rejects pre-`0001-01-01T00:00:00Z` instants, `Duration.ToNodaDuration` and `ToProtobufDuration` reject spans outside the protobuf ±315_576_000_000 s window, leap-second and 24:00 time-of-day payloads reject, the unspecified day-of-week wire value maps to the none case as the family's one sentinel-to-vocabulary projection, and a range rejection reads identically at binary and JSON edges because both codecs feed one fault family.
- Law: the STJ bridge is one options mutation at suite-contract composition — `ConfigureForNodaTime(options, IDateTimeZoneProvider)` or `ConfigureForNodaTime(options, NodaJsonSettings)` whose sixteen converter slots make per-suite overrides slot writes, with `WithIsoIntervalConverter`/`WithIsoDateIntervalConverter` swapping the interval representation — the default interval converter's `Start`/`End` names pass through the naming policy and its instants delegate to the registered instant slot, so interval JSON shape pins in golden bytes; zone-bearing types require the explicit provider, non-ISO calendars reject at write, and the `NodaTimeDefaultJsonConverterAttribute` per-property route hard-pins defaults and serves isolated DTOs only.

```csharp conceptual
using ProtoDuration = Google.Protobuf.WellKnownTypes.Duration;
using NodaDuration = NodaTime.Duration;

public readonly record struct WireWindow(Timestamp Start, ProtoDuration Span);

public readonly record struct Window(Instant Start, NodaDuration Span, IsoDayOfWeek Anchor) {
    public WireWindow ToWire() => new(Start.ToTimestamp(), Span.ToProtobufDuration());
}

public static class TemporalBridge {
    public static Validation<Error, Window> Admit(WireWindow wire, DayOfWeek anchor) =>
        (Ranged(7621, () => wire.Start.ToInstant()), Ranged(7622, () => wire.Span.ToNodaDuration()), Day(anchor))
            .Apply(static (instant, length, day) => new Window(instant, length, day)).As();

    private static Validation<Error, IsoDayOfWeek> Day(DayOfWeek wire) =>
        wire is DayOfWeek.Unspecified ? new Fault.Absent(Detail: nameof(DayOfWeek)) : wire.ToIsoDayOfWeek();

    private static Validation<Error, T> Ranged<T>(int code, Func<T> read) =>
        Try.lift(read).Run().MapFail(error => (Error)new Fault.Bounds(Detail: $"<temporal-range:{code}:{error.Message}>")).ToValidation();
}
```

## [05]-[SERVER_EXPOSURE]

[EXPOSURE_FOLD]:
- Law: exposure is one record folded at the app root — `AddGrpc` settles global policy once, `MapGrpcService` binds each row with the `ServerServiceDefinition` overloads as the runtime-assembled ingress, the returned `GrpcServiceEndpointConventionBuilder` is the per-endpoint convention seam, and the endpoint row owns the protocol prerequisite (`HttpProtocols.Http2` on plaintext trusted lanes, ALPN under TLS) — so nothing outside the record reaches the options and the second-configuration-site defect is structurally impossible; stub generation is one `GrpcServices` item row per contract file — `Both`, `Client`, `Server`, `None` — never post-build pruning.
- Law: interceptors are option rows with constructor args as data — global rows always run before per-service rows, so a per-service row can never wrap a global one, and a stateful interceptor demands container registration or its state resets every call.
- Law: per-service override is inherit-unless-specified — `AddServiceOptions<TService>` carries paired `MaxReceiveMessageSizeSpecified`/`MaxSendMessageSizeSpecified` flags, so assigning null explicitly LIFTS a global cap and clearing the flag restores inheritance; copying global values by hand re-derives what the flags encode.
- Law: an empty compression-provider list pre-seeds gzip and deflate; supplying any provider row suppresses both, so a custom-codec root re-adds gzip explicitly or older peers lose a negotiable encoding; `ResponseCompressionAlgorithm` names the negotiated row, `EnableDetailedErrors` is a trusted-lane row only, and `IgnoreUnknownServices` stays false so contract drift surfaces as the unimplemented status the client taxonomy expects.
- Law: `ServerCallContext` is the one per-call capability — `Deadline` arrives client-budgeted, `CancellationToken` fires on disconnect, cancel, and expiry and is the only token to thread, `WriteResponseHeadersAsync` is the one-shot early flush, and `GetHttpContext()` bridges to connection evidence; a streaming handler observing the token is the drain contract — writing on past it sends into a dead call.
- Exemption: the exposure fold's builder-mutation body is the platform-forced statement seam.

[FAULT_HEALTH_WEB]:
- Law: the fault contract is two-tier — the wire tier is a generated fault-detail message family per suite evolving under descriptor law, serialized into a `-bin` trailer and raised as `RpcException(new Status(code, brief), trailers)` in one expression; the local tier is the closed `TransportFault` `[Union]` deriving from `Expected` that the boundary fold mints, so `Status.Detail` is human summary only, machine discriminants in detail text are the named defect, and the decode arrow bridges the wire message into a `TransportFault` case rather than a bare coded `Error.New`.
- Law: health is two rows — `AddGrpcHealthChecks` plus `MapGrpcHealthChecksService` — with the empty-string service pre-mapped to all checks and per-service rows as name-keyed predicate maps; the wire fold is fixed — any unhealthy entry folds NOT_SERVING, degraded still SERVES because degradation visibility is a diagnostics signal, zero matches fold UNKNOWN — and the surfaces disagree on an unmapped name by design: Check fails not-found while Watch reports SERVICE_UNKNOWN, so probes tolerate both spellings.
- Law: `UseHealthChecksCache` false executes mapped checks inline per Check; the Watch stream's first write is freshly computed with later writes on the runtime-owned publisher cadence, and stopping completes watchers with a final NOT_SERVING — the drain edge attach choreography consumes — while polling Check races listener teardown.
- Law: browser translation is one middleware plus per-endpoint consent — `UseGrpcWeb(new GrpcWebOptions { DefaultEnabled })` with `EnableGrpcWeb`/`DisableGrpcWeb` conventions — and a grpc-web request without consent falls through as a non-gRPC request, the signature of a missing enable row; detection is structural, the response mode negotiates independently from the Accept header, the middleware spoofs the protocol so no service code can detect translation, and browser callers additionally need a CORS policy exposing `Grpc-Status`, `Grpc-Message`, and the encoding headers.

```csharp conceptual
public sealed class RelayService;
public sealed record ExposureRow(string Service, Func<IEndpointRouteBuilder, GrpcServiceEndpointConventionBuilder> Bind, Option<string> HealthTag, bool Web);
public sealed record Exposure(Seq<ExposureRow> Rows, int ReceiveCap, bool DetailedErrors);

public static class ServerRoot {
    private const string FaultKey = "fault-detail-bin";

    public static WebApplication Compose(WebApplicationBuilder builder, Exposure exposure) {
        ArgumentNullException.ThrowIfNull(builder);
        ArgumentNullException.ThrowIfNull(exposure);
        builder.Services.AddGrpc(options => (options.MaxReceiveMessageSize, options.EnableDetailedErrors) = (exposure.ReceiveCap, exposure.DetailedErrors))
            .AddServiceOptions<RelayService>(static options => options.MaxReceiveMessageSize = null);
        builder.Services.AddGrpcHealthChecks(options => exposure.Rows.Iter(row => row.HealthTag.Iter(tag =>
            options.Services.Map(row.Service, registration => registration.Tags.Contains(tag)))));
        var app = builder.Build();
        app.UseGrpcWeb(new GrpcWebOptions { DefaultEnabled = false });
        exposure.Rows.Iter(row => ignore(row.Web ? row.Bind(app).EnableGrpcWeb() : row.Bind(app)));
        _ = app.MapGrpcHealthChecksService();
        return app;
    }

    public static RpcException Fault(StatusCode code, string brief, IMessage detail) =>
        new(new Status(code, brief), new Metadata { { FaultKey, detail.ToByteArray() } });
}
```

## [06]-[IPC_TOPOLOGY]

[ENDPOINT_LIFECYCLE]:
- Law: `UnixDomainSocketEndPoint` validates the platform path budget in bytes at construction — ~104 on BSD-derived systems, ~108 on Linux — so endpoint directories stay short and ASCII; the abstract namespace is the rejected row for credential-gated seams because no directory mode exists to enforce, and the Windows column of the same row axis is the named pipe via `ListenNamedPipe` — platform variance is one column value.
- Law: `ListenUnixSocket` binds an absolute path without unlinking an existing file, so a stale file surfaces as address-in-use and the bind failure IS the mutual-exclusion primitive — a racing claimant loses at bind and re-reads the manifest; unlink-on-dispose is asymmetric: the listener socket recorded its bound path and best-effort deletes it, accepted sockets never unlink, so clean shutdown self-cleans and a killed process leaves the stale file the probe ladder owns.
- Law: the manifest is the single attach contract — socket path, publisher pid plus process-start stamp, epoch, contract checksum set, cap pair, codec id; every field either routes the dial or gates it — and publication is atomic-by-rename in the same directory: a temp file in a different directory silently downgrades the move to copy-plus-delete and forfeits atomicity, `File.Replace` is the variant retaining the displaced generation as evidence, and the owner-only directory mode is set atomically at creation because create-then-chmod leaves a window — `File.GetUnixFileMode` is the audit read.
- Law: attach choreography orders the manifest last — directory, bind-and-serve, publish — and detach inverts it, so manifest presence implies a listener existed at publish time and every alternative ordering admits an observable lie costing a bespoke probe; the staleness ladder covers the one uncovered history, death after publish — the pid/start-stamp probe is advisory, the socket connect probe is authoritative, and only connect licenses reclamation; post-dial readiness is the peer's health stream, never a parallel readiness ping.
- Exemption: the staged-write protocol and the socket connect probe are the platform-forced statement seam.

[PEER_EVIDENCE]:
- Law: peer identity on local transports is connection-level kernel evidence, never a call-context read — the call context's peer string degrades to `"unknown"` off IP; the accepted socket surfaces through `IConnectionSocketFeature`, a connection middleware verifies once per connection before protocol negotiation, and the probe is `GetRawSocketOption` with platform rows — Linux `SOL_SOCKET(1)`/`SO_PEERCRED(17)` into a 12-byte ucred captured at connect time so a later exec cannot launder identity, macOS `SOL_LOCAL(0)`/`LOCAL_PEERCRED(1)` into a 76-byte xucred plus `LOCAL_PEERPID(2)` for the peer pid.
- Law: enforcement and verification are two layers — the endpoint directory's traversal mode is the kernel perimeter denying foreign uids before any byte flows, and the credential read is the verification receipt compared against the manifest's publisher uid; socket-FILE mode alone is the rejected form, and a failed check tears down before the protocol layer with a typed rejection distinguishable from every wire failure by the absence of any HTTP/2 evidence.

[EPOCH_REDIAL]:
- Law: the epoch is a monotonic generation counter suffixed into the socket path — a successor never contends with its predecessor's file or lingering connections — and redial discriminates on the re-read manifest: same epoch is transient and the hop's one retry owner handles it while the topology does nothing; an advanced epoch disposes the old channel, re-runs the contract gate, re-verifies credentials, and dials fresh — skipping the re-gate assumes binary identity across restarts, which is exactly what epochs deny.
- Law: manifest watching is pull-on-failure — epoch change is only actionable to a peer that just observed a failure, and filesystem-event subscriptions add a liveness dependency on event delivery for nothing; an unchanged checksum makes the bounce cheap, a moved checksum pays the full rehandshake.
- Law: in-flight work at epoch advance resolves by receipt — completed-and-receipted survives, unreceipted re-issues as intent, never bytes, because remote commands, deep-links, and journal replay enter one invocation surface sealing one receipt family under an origin discriminant plus an idempotency key, so replay is re-presentation through the same gate; the message bus is the named rejected form — delivery-order ambiguity, at-least-once duplication, an independent retry owner, and an ungated path around the checksum gate.

```csharp conceptual
public sealed record Manifest(string SocketPath, int Pid, long StartStamp, long Epoch, string Checksum, int ControlCap, int ArtifactCap);

[JsonSerializable(typeof(Manifest))]
public sealed partial class ManifestContext : JsonSerializerContext;

public static class Endpoint {
    private const string Name = "manifest.json";

    public static Fin<Unit> Publish(Manifest manifest, string directory) =>
        Try.lift(() => {
            _ = Directory.CreateDirectory(directory, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            var staged = Path.Join(directory, $"{Name}.{manifest.Epoch}.staged");
            File.WriteAllBytes(staged, JsonSerializer.SerializeToUtf8Bytes(manifest, ManifestContext.Default.Manifest));
            File.Move(staged, Path.Join(directory, Name), overwrite: true);
            return unit;
        }).Run().MapFail(static error => (Error)new TransportFault.Publish(error.Message));

    public static Fin<Manifest> Attach(string directory) =>
        Try.lift(() => JsonSerializer.Deserialize(File.ReadAllBytes(Path.Join(directory, Name)), ManifestContext.Default.Manifest))
            .Run().MapFail(static error => (Error)new TransportFault.Unpublished(error.Message)).Bind(static held => Optional(held).ToFin(new Fault.Absent(Detail: nameof(Manifest))))
            .Bind(static manifest => AdvisoryDead(manifest) && ConnectRefused(manifest.SocketPath)
                ? Fin.Fail<Manifest>(new TransportFault.Stale(manifest.Epoch))
                : Fin.Succ(manifest));

    private static bool AdvisoryDead(Manifest manifest) =>
        Try.lift(() => Process.GetProcessById(manifest.Pid).StartTime.ToUniversalTime().Ticks != manifest.StartStamp)
            .Run().IfFail(static _ => true);

    private static bool ConnectRefused(string socketPath) {
        using var probe = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.IP);
        return Try.lift(() => (fun(() => probe.Connect(new UnixDomainSocketEndPoint(socketPath)))(), false).Item2)
            .Run().IfFail(static _ => true);
    }
}
```

[CORRIDOR]:
- Law: a raw-stream lane frames as version byte, frame-kind byte, 32-bit little-endian length, 32-bit `Crc32` of the body, then body — frame integrity is the recomputed transmission check `system-apis.md` `INTEGRITY` legislates (`Crc32.HashToUInt32`, recomputed by the receiver), never `XxHash3`, which that owner reserves for the in-process content key; binary field access rides `BinaryPrimitives` little-endian readers, never manual shifts.
- Law: receive order is the memory-amplification guard — read the fixed header exactly, reject version or frame-kind drift, validate the declared length against the kind's manifest cap BEFORE any body allocation, read the body exactly, recompute the `Crc32` BEFORE parsing — so a malicious length costs a header read and a comparison, the exact-read plus cap gate catches the length lie, and a corrupt body never reaches the parser.
- Law: the producer pre-checks — exact `CalculateSize` against the cap before serializing, because post-serialization detection has already paid allocation and encoding for an unsendable payload; the cap pair is negotiated manifest data consumed through one frame-kind row column — control frames cap small, artifact frames at the corridor budget — making asymmetric caps unrepresentable.
- Law: the content key over the framed body is the `boundaries.md` `BYTE_IDENTITY` codec reused verbatim — the same `XxHash3.HashToUInt64` content key the artifact index addresses by — so a corridor body and its persisted artifact share one identity and the frame check and the content key never collapse into one hash serving two contracts.
- Law: the four failures are disjoint by construction and each maps to exactly one remediation — oversize re-chunks, truncated re-reads, corrupt redials, misframed re-gates — and a corridor implementing any subset re-discovers the missing class in production as the ambiguous one.
- Exemption: the receive-order kernel — exact reads, the rented-buffer lease, and the catch arms — is the platform-forced stream statement seam.

```csharp conceptual
[SmartEnum<byte>]
public sealed partial class FrameKind {
    public static readonly FrameKind Control = new(1, static manifest => manifest.ControlCap);
    public static readonly FrameKind Artifact = new(2, static manifest => manifest.ArtifactCap);
    [UseDelegateFromConstructor]
    public partial int Cap(Manifest manifest);
}

public readonly record struct Admitted<T>(T Payload, ulong ContentKey);

public static class Corridor {
    private const byte Version = 1;
    private const int HeaderSize = 10;

    public static Fin<byte[]> Stage(IMessage payload, FrameKind kind, Manifest manifest) {
        ArgumentNullException.ThrowIfNull(payload);
        ArgumentNullException.ThrowIfNull(kind);
        var (cap, size) = (kind.Cap(manifest), payload.CalculateSize());
        if (size > cap) { return Fin.Fail<byte[]>(new TransportFault.Oversize(size, cap)); }
        var frame = new byte[HeaderSize + size];
        payload.WriteTo(frame.AsSpan(HeaderSize));
        (frame[0], frame[1]) = (Version, kind.Key);
        BinaryPrimitives.WriteInt32LittleEndian(frame.AsSpan(2), size);
        BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(6), Crc32.HashToUInt32(frame.AsSpan(HeaderSize)));
        return frame;
    }

    public static async Task<Fin<Admitted<T>>> Admit<T>(Stream lane, MessageParser<T> contract, Manifest manifest, CancellationToken token) where T : class, IMessage<T> {
        ArgumentNullException.ThrowIfNull(lane);
        var header = new byte[HeaderSize];
        try { await lane.ReadExactlyAsync(header, token).ConfigureAwait(false); }
        catch (EndOfStreamException) { return Fin.Fail<Admitted<T>>(new TransportFault.Truncated("header")); }
        if (header[0] != Version || FrameKind.Validate(header[1], null, out var kind) is not null) { return Fin.Fail<Admitted<T>>(new TransportFault.Misframed($"frame:{header[0]}:{header[1]}")); }
        var (cap, length) = (kind!.Cap(manifest), BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(2)));
        if (length > cap || length < 0) { return Fin.Fail<Admitted<T>>(new TransportFault.Oversize(length, cap)); }
        var body = ArrayPool<byte>.Shared.Rent(length);
        try {
            await lane.ReadExactlyAsync(body.AsMemory(0, length), token).ConfigureAwait(false);
            return Crc32.HashToUInt32(body.AsSpan(0, length)) != BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(6))
                ? Fin.Fail<Admitted<T>>(new TransportFault.Corrupt())
                : Try.lift(() => contract.ParseFrom(new ReadOnlySequence<byte>(body, 0, length))).Run()
                    .Map(payload => new Admitted<T>(payload, XxHash3.HashToUInt64(body.AsSpan(0, length))))
                    .MapFail(static error => (Error)new TransportFault.Misframed($"payload:{error.Message}"));
        }
        catch (EndOfStreamException) { return Fin.Fail<Admitted<T>>(new TransportFault.Truncated("body")); }
        finally { ArrayPool<byte>.Shared.Return(body); }
    }
}
```

## [07]-[SUITE_CONTRACTS]

[RESOLVER_MERGE]:
- Law: each package ships one source-generated contract context owning its wire family, and app roots merge per-package contexts once — `JsonTypeInfoResolver.Combine` flattens nested combinations into one ordered chain with `TypeInfoResolverChain` as the options-bound mutable view; routing envelopes carry foreign payloads as opaque JSON decoded only by the owning context at the consuming edge, so the root merges resolver ownership, never payload shapes.
- Law: a type resolvable by two contexts is a conflict, never a fallback — order-dependent resolution that works is a latent contract fork where reordering re-decides another package's wire format — and the disjointness probe doubles as the defense against a smuggled reflection resolver, caught by its over-breadth rather than by name; after the probe, `MakeReadOnly()` freezes the suite options and `IsReadOnly` is the audit bit; the same conflict law covers the codec axis — every wire surface declares exactly one codec (binary contract, suite JSON, or a framing row), and a second observed codec is a composition conflict receipt, never a runtime fallback that masks drift by re-encoding what the primary rejected.
- Law: `WithAddedModifier` is the cross-cutting seam over the merged chain — one modifier enforcing suite invariants across every package's contract without touching any generator, and modifiers stack without re-wrapping.
- Law: schema export is contract publication from the frozen options — `GetJsonSchemaAsNode` with `TreatNullObliviousAsNonNullable` tightening unannotated references and `TransformSchemaNode` injecting vocabulary stamps during export, never after — and the schema node set hashes into the suite's contract checksum, judged by the same classifier verdict as binary surfaces: one evolution gate, two projections.
- Exemption: the merge root's options-mutation body is the platform-forced statement seam.

```csharp conceptual
public sealed record PackageContract(string Package, IJsonTypeInfoResolver Context, Seq<Type> Advertised);

public static class SuiteContracts {
    private static readonly JsonSchemaExporterOptions Export = new() { TreatNullObliviousAsNonNullable = true };

    public static Validation<Error, (JsonSerializerOptions Wire, string SchemaHash)> Merge(Seq<PackageContract> packages) =>
        packages.Traverse(package => Disjoint(packages, package).ToValidation()).As()
            .Map(_ => Frozen(packages)).Map(wire => (wire, SchemaHash(wire, packages)));

    private static Fin<Unit> Disjoint(Seq<PackageContract> packages, PackageContract package) =>
        packages.Filter(other => other.Package != package.Package)
            .Bind(other => package.Advertised.Filter(advertised => other.Context.GetTypeInfo(advertised, JsonSerializerOptions.Default) is not null)
                .Map(advertised => $"{advertised.Name}:{package.Package}+{other.Package}")) is { IsEmpty: false } forks
            ? Fin.Fail<Unit>(new TransportFault.Fork(string.Join(',', forks)))
            : Fin.Succ(unit);

    private static JsonSerializerOptions Frozen(Seq<PackageContract> packages) {
        var wire = new JsonSerializerOptions {
            TypeInfoResolver = JsonTypeInfoResolver.Combine([.. packages.Map(static package => package.Context)])
                .WithAddedModifier(static info => info.UnmappedMemberHandling = info.Kind is JsonTypeInfoKind.Object ? JsonUnmappedMemberHandling.Disallow : info.UnmappedMemberHandling),
        };
        wire.MakeReadOnly();
        return wire;
    }

    private static string SchemaHash(JsonSerializerOptions wire, Seq<PackageContract> packages) =>
        XxHash3.HashToUInt64(Encoding.UTF8.GetBytes(string.Join(';',
            packages.Bind(static package => package.Advertised)
                .Map(advertised => wire.GetJsonSchemaAsNode(advertised, Export).ToJsonString())))).ToString("x16", CultureInfo.InvariantCulture);
}
```

[PATCH_LAW]:
- Law: a patch is recorded intent — operations constructed by the typed expression builders (`Add`/`Remove`/`Replace`/`Move`/`Copy`/`Test`) at the moment the mutation is decided, so a renamed property breaks construction at compile time; delta generation is structurally absent from the surface, and the state-diff endpoint is the rejected form — it loses `Move`/`Copy`/`Test` semantics, explodes list reorders into per-index replaces, and re-derives at the consumer what the producer already knew.
- Law: `JsonPatchDocument<TModel>` self-binds as a minimal-API parameter — the type carries its converter and emits accepts metadata for `application/json-patch+json` from the declaration alone — relayed foreign patches ride the untyped string-path document through the same accumulating overload, and `SerializerOptions` is the codec coupling point: assign the frozen suite options or patch value conversion diverges from the suite codec on every converter-bearing type, the trap that applies cleanly in tests and corrupts temporal properties in production.
- Law: apply is a boundary act — the `ApplyTo(target, Action<JsonPatchError>)` overload projects the first failed operation into one `JsonPatchError` row routed to the rail and then halts (the overload catches one `JsonPatchException` and breaks), so application is fail-fast by construction, never accumulating, because a patch is an ordered sequence where a later operation observes earlier mutations and replaying past a failed precondition corrupts the target; `Test` carries optimistic concurrency inside the document so a stale-precondition replay aborts the whole patch at its first `Test`, and the mutated wire projection re-enters domain admission as a whole value; the accumulating spelling — letting every operation run and collecting all faults — is the rejected form here, since it is the inverse of the open-constraint fold, and applying patches to admitted owners bypasses admission and is the rejected form.
