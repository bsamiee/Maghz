# [DIAGNOSTICS]

Telemetry is one spine declared at process roots and joined across the suite by one identity envelope. Emission is a compile-checked contract — generated log methods, registered instruments, natively emitted spans — and every governing behavior is a declared row: level floors, sampler verdicts, view shapes, batch squares, redactor maps, baggage keys. One sampling verdict at the trace root derives log and exemplar volume; one classification taxonomy meets one redaction seam before any provider observes a record; one stamp cell per process makes cross-process order producer-stamped evidence instead of consumer inference; loss and skew are kind cases on the one receipts fact stream — never parallel cells — and the shed verdict folds in from its rate-limit owner, so every operational view is a projection over one `Atom<Seq<FactRecord>>`. Growth lands as rows — a new event family is one partial method in its band, a new subsystem one source admission, a new sensitivity one taxonomy row plus one redactor row, a new transport one carrier adapter.

## [01]-[SIGNAL_CHOOSER]

This table routes a telemetry concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]             | [OWNER]                                   | [REJECTED_FORM]                  |
| :-----: | :-------------------- | :---------------------------------------- | :------------------------------- |
|  [01]   | event emission        | `[LoggerMessage]` partial in the owner    | interpolated calls, name switch  |
|  [02]   | log projection        | one `LoggerConfiguration` policy table    | per-module logger configuration  |
|  [03]   | signal admission      | `AddSource`/`AddMeter` rows at one root   | per-library provider scaffolding |
|  [04]   | telemetry volume      | one root sampler, derived thrice          | per-signal probabilities         |
|  [05]   | metric shaping        | view rows + cardinality limits            | call-site meter gating           |
|  [06]   | export                | `UseOtlpExporter` once                    | per-signal exporter scatter      |
|  [07]   | cross-process context | versioned envelope + one propagator pair  | ad-hoc baggage writes            |
|  [08]   | event ordering        | one stamp cell per process                | consumer-inferred timestamps     |
|  [09]   | sensitive data        | classification taxonomy + redactor map    | sink scrubbing, regex masking    |
|  [10]   | resource signals      | governed meter admission + publisher rows | counter polling loops            |
|  [11]   | operational views     | folds over one `FactRecord` stream        | parallel typed loss/skew cells   |

## [02]-[EMISSION]

[GENERATED_GRAMMAR]:
- Law: every production event family is one `[LoggerMessage]` partial co-located with the concern it evidences; `EventId` allocates from the owner's declared const band and `EventName` is the human-stable half — dashboards key on names, the wire keys on ids, and neither alone suffices.
- Law: template text is constant — identity caches by template, so dynamic data is always a property hole; an `Exception`-typed parameter binds the exception channel, never a hole, making a `ToString`-ed exception unrepresentable through the generated path.
- Law: severity decided by data is one verb with a `LogLevel` parameter and the `Level` row omitted, never a switch over seven named methods.
- Law: the generated body opens with an `ILogger.IsEnabled` guard so a disabled level never formats — `SkipEnabledCheck = true` elides it for an audit-grade event a sampler-and-buffer exclusion already cleared, so the always-recorded path drops the redundant level branch; setting it on a sampleable event is the silent volume leak.
- Law: six is the template arity ceiling — past it the payload is one `[LogProperties]` object whose expansion knobs are declaration facts, and a tag-name collision between expansion and a template hole is a build error, never wire drift.
- Use: `[TagProvider(type, method)]` as the projection row for foreign types that cannot carry annotations; `[TagName]` renames at the declaration so a vocabulary edit breaks loudly at rebuild.
- Reject: interpolated log calls and the boxing severity-extension family in production emission; string-named categories outside boundary material.

[SEAM_AND_VOLUME]:
- Law: emission rides `ILogger<T>` category identity and providers attach behind the seam, each with a disjoint delivery mandate — one wire exporter, one operator-local projection; the same record arriving twice with two shapes is the split-mandate defect.
- Law: a composition that may run logger-less takes `NullLogger<T>.Instance`, never a nullable logger.
- Law: volume is head-of-pipeline policy — `AddTraceBasedSampler` slaves log volume to the trace verdict so logs and spans rise and fall as one population; rule-row samplers select by maximum level, thinning the chatty floor and never the error ceiling.
- Law: the global buffer inverts severity economics — `AddGlobalBuffer` rules hold the verbose tiers and `GlobalLogBuffer.Flush` replays them when an incident makes them valuable; the volume ladder is delete before defer before coalesce, and an oversize record bypasses the buffer and emits live.
- Boundary: audit-grade categories are excluded from sampler and buffer rules by rule construction, never by runtime check.

```csharp conceptual
public sealed record StepFact(string Stage, int Attempts, TimeSpan Elapsed, string? Detail);

internal static class HostTags {
    public static void Collect(ITagCollector collector, Version value) =>
        collector.Add("host.generation", value.Major);
}

public static partial class StepLog {
    private const int Band = 4200;

    [LoggerMessage(EventId = Band + 1, EventName = "StepSettled", Level = LogLevel.Information,
        Message = "step {Key} settled")]
    public static partial void Settled(ILogger logger, string key,
        [LogProperties(OmitReferenceName = true, SkipNullProperties = true)] StepFact fact);

    [LoggerMessage(EventId = Band + 2, EventName = "StepFaulted", Level = LogLevel.Error,
        Message = "step {Key} faulted")]
    public static partial void Faulted(ILogger logger, string key, Exception cause,
        [TagProvider(typeof(HostTags), nameof(HostTags.Collect))] Version host);

    [LoggerMessage(EventId = Band + 3, EventName = "StepDrained", SkipEnabledCheck = true,
        Message = "step {Key} drained {Residue} residue")]
    public static partial void Drained(ILogger logger, LogLevel level, string key, int residue);
}
```

## [03]-[PROJECTION]

[POLICY_TABLE]:
- Law: one `LoggerConfiguration` per process composes the six rails — minimum level, enrichment, destructuring, filters, sinks, audit sinks — and `CreateLogger()` freezes them; a second configuration below the root forks level governance, failure listening, and flush ownership.
- Law: severity floors are held `LoggingLevelSwitch` rows — a raw level literal forecloses live control; `MinimumLevel.Override` keys per-source floors on `SourceContext`, matches only events carrying it, and is root-pipeline law unsupported in sub-loggers.
- Law: routing is identity-keyed `Matching` predicates on `Conditional` and sub-logger rows, never call-site flags; sub-pipelines derive — parent filters constrain, parent enrichers stamp, and a branch only narrows.
- Law: destructuring caps are admission against payload bombs — depth defaults to 10 while string and collection caps default unbounded, so both pin at the root of any pipeline accepting foreign graphs.
- Law: flush ownership is singular — the root that called `CreateLogger` calls `CloseAndFlush`, and the static facade is bootstrap-only surface.
- Law: the boot window logs through `CreateBootstrapLogger()` — a reloadable pipeline capturing pre-host faults, frozen into the host-built configuration when `AddSerilog` registers the provider — so no startup fault predates the pipeline and host shutdown owns the drain.

[DELIVERY_AND_LOSS]:
- Law: the two delivery classes are contracts — `WriteTo` swallows sink failure into the typed rail, `AuditTo` propagates it to the logging caller — and batched sinks are structurally incompatible with audit guarantees.
- Law: the `BatchingOptions` square is one declared latency/throughput budget — `EagerlyEmitFirstEvent` and `BufferingTimeLimit` bound worst-case visibility, `BatchSizeLimit` and `QueueLimit` bound throughput cost — tuned together or not at all.
- Law: batch implementers let exceptions propagate — the batching infrastructure owns retry and failure reporting, and a `try`/`catch` inside `EmitBatchAsync` amputates the rail silently; `OnEmptyBatchAsync` is the sanctioned heartbeat hook.
- Law: `WriteTo.Fallible` wires the suite's listener onto its sinks; `LoggingFailureKind` plus the retry ceiling, queue overflow, and oversize bypass form the complete loss taxonomy, and the listener projects each failure into one `FactRecord` loss case on the shared receipts stream `rails-and-effects.md` owns — a private `Atom<Seq<SinkLoss>>` beside it is the parallel-cell defect, and `WriteTo` without a listener is unobserved best-effort.
- Law: fallback is declared topology — `WriteTo.FallbackChain` reroutes to the next sink on synchronous throw or listener-reported failure, and a fire-and-forget sink that neither throws nor reports defeats the chain silently, so fallback eligibility is a per-sink failure-surface audit.
- Law: `SelfLog` is the floor beneath the rail — a bounded never-throwing writer, never a pipeline sink, because it runs exactly when the pipeline is the casualty.

```csharp conceptual
[Union]
public abstract partial record FactRecord {
    private FactRecord(Stamp at) => At = at;
    public Stamp At { get; }
    public sealed record Loss(Stamp When, string Sink, LoggingFailureKind Kind, int Dropped) : FactRecord(When);
    public sealed record Skew(Stamp When, string Peer, TimeSpan Offset, TimeSpan Bound) : FactRecord(When);
    public sealed record Shed(Stamp When, string Subsystem, TimeSpan RetryAfter) : FactRecord(When);
}

public sealed class WireSink : IBatchedLogEventSink {
    public Task EmitBatchAsync(IReadOnlyCollection<LogEvent> batch) => Task.CompletedTask;
    public Task OnEmptyBatchAsync() => Task.CompletedTask;
}

public sealed class LossFold(Atom<Seq<FactRecord>> facts, StampCell stamps) : ILoggingFailureListener {
    public void OnLoggingFailed(object sender, LoggingFailureKind kind, string message,
        IReadOnlyCollection<LogEvent>? events, Exception? exception) =>
        ignore(facts.Swap(seen => seen.Add(new FactRecord.Loss(stamps.Now(), sender.GetType().Name, kind, events?.Count ?? 0))));
}

public sealed record LevelRows(LoggingLevelSwitch Floor, Seq<(string Source, LoggingLevelSwitch Override)> Overrides) {
    public static readonly LevelRows Live = new(new(LogEventLevel.Information),
        [("<source-chatty>", new(LogEventLevel.Warning)), ("<source-noise>", new(LogEventLevel.Error))]);
}

public static class Projection {
    public static Logger Build(LevelRows rows, WireSink wire, ILogEventSink ledger, Atom<Seq<FactRecord>> facts, StampCell stamps) {
        ArgumentNullException.ThrowIfNull(rows);
        return rows.Overrides
            .Fold(new LoggerConfiguration().MinimumLevel.ControlledBy(rows.Floor),
                static (table, row) => table.MinimumLevel.Override(row.Source, row.Override))
            .Enrich.FromLogContext()
            .Destructure.ToMaximumDepth(8)
            .Destructure.ToMaximumStringLength(1024)
            .Destructure.ToMaximumCollectionCount(64)
            .WriteTo.Fallible(into => into.Sink(wire, new BatchingOptions {
                EagerlyEmitFirstEvent = true, BatchSizeLimit = 500,
                BufferingTimeLimit = TimeSpan.FromSeconds(2), QueueLimit = 10_000,
            }), new LossFold(facts, stamps))
            .WriteTo.Conditional(Matching.FromSource("<source-hot>"),
                static into => into.Console(formatProvider: CultureInfo.InvariantCulture))
            .AuditTo.Sink(ledger)
            .CreateLogger();
    }
}
```

## [04]-[SIGNAL_ROOT]

[ROOT_COMPOSITION]:
- Law: one `AddOpenTelemetry()` per process admits all three signals; `ConfigureResource` is the only resource verb reaching all three providers, and provider lifetime — construction, flush, shutdown — rides the host.
- Law: `serviceInstanceId` pins from the suite's boot mint — auto-generation is a fresh GUID per start that anonymizes restart lineage; `SetResourceBuilder` replaces and silently discards earlier identity, so augmentation is the only default verb.
- Law: emit natively, admit by name — an instrumentation package enters only where it owns a foreign library's emission, and its shim instrument names are a standing renaming migration; processor order is registration order, and an exporter's own I/O runs inside `Sdk.SuppressInstrumentation`.
- Law: `ActivityKind` declares boundary semantics and `SetStatus` is the typed verdict — error facts in tags are invisible to every backend error filter; span events die with the sampling verdict while log records survive it, so a fact that must outlive an unsampled trace is a log record, and one exception class has exactly one owning channel.
- Law: admission evidence enters at creation — `StartActivity` tags and links participate in the sampling verdict while post-start mutation does not, and `HasListeners()` gates expensive tag computation ahead of the call.
- Law: typed receipts project to span attributes through their own formatting surfaces — the projection adapts per receipt type, and a generic receipt interface as the telemetry carrier erases the route and status evidence worth exporting.
- Exemption: the signal root's builder-mutation body is the platform-forced statement seam.

[VOLUME_AND_SHAPE]:
- Law: the sampler matrix is one root row — `ParentBasedSampler` over the deterministic `TraceIdRatioBasedSampler`, same verdict at every hop for the same trace — and the recorded bit derives log sampling and `TraceBased` exemplars: declare once, derive thrice; independent per-signal probabilities destroy joinability.
- Law: views are declaration-time stream surgery — `MetricStreamConfiguration.Drop` is the kill switch, `TagKeys` the projection, `CardinalityLimit` a pre-allocated memory commitment; breach folds into the reserved point tagged `otel.metric.overflow`, and the cardinality alarm binds to that tag.
- Law: latency families default to the exponential histogram because boundary guessing is what it deletes; cumulative readers hold every seen tag combination for process life, so churning tag values lean `Delta` where the backend permits.
- Law: every instrument declares once in one registry owner — dot-separated names, units on the instrument never encoded in the name, tag keys a closed per-instrument vocabulary the views enforce; instrument identity de-duplicates by name, so an inline creation with a drifted unit or description forks the stream.
- Law: instrument polarity follows the fact shape — synchronous instruments record event-shaped facts at the call site, observable instruments pull level-shaped facts at collection cadence on the collecting thread; a polled level through a synchronous gauge aliases, and an observable callback that blocks turns collection into a stall injector.
- Law: the cost levers are asymmetric — thin spans by root admission and sampling, thin metrics by `Drop` views; dropping spans in a processor or gating meters at call sites pays the maximum cost for the minimum control.

[EXPORT_AND_DRAIN]:
- Law: `UseOtlpExporter()` is called exactly once and throws when mixed with per-signal exporter registration — one export owner per process, detected at build; endpoint, headers, and protocol bind from configuration, never source.
- Law: the batch square is config-time arithmetic — peak rate times batch delay must fit the queue — and the durability budget is three declared windows (batch, retry, drain), each with a named loss mode an incident review must be able to cite.
- Law: shutdown drains traces and metrics before the log provider, because logs evidence the drain itself.

[RESOURCE_ROWS]:
- Law: resource monitoring is a governed source, never a decision-maker — `AddResourceMonitoring()` registers the source, the root admits its meter by name, and the runtime's health machines consume the signal; the signals are owned here, the machines there.
- Law: limit-utilization and request-utilization are different alarms — throttling-imminent versus under-provisioned — and one collapsed percentage loses exactly the distinction the orchestrator acts on; the fleet pins the utilization range explicitly.
- Law: publishers are cadence-coupled consumers — they record and return; the sampling interval bounds every derived signal's reaction time, and a publisher window wider than the consuming policy's period aliases.

```csharp conceptual
public sealed record SignalCatalog(Seq<string> Sources, Seq<string> Meters, double Ratio,
    Seq<(string Instrument, MetricStreamConfiguration Shape)> Views) {
    public static readonly SignalCatalog Suite = new(
        ["<source-a>", "<source-b>"],
        ["<meter-a>", "System.Runtime", "Microsoft.Extensions.Diagnostics.ResourceMonitoring"],
        Ratio: 0.25,
        [("<instrument-latency>", new Base2ExponentialBucketHistogramConfiguration { MaxSize = 160 }),
         ("<instrument-chatty>", MetricStreamConfiguration.Drop),
         ("<instrument-wide>", new MetricStreamConfiguration { TagKeys = ["<tag-a>", "<tag-b>"], CardinalityLimit = 4000 })]);
}

public static class SignalRoot {
    public static IServiceCollection Compose(IServiceCollection services, SignalCatalog catalog, string suite, string instanceId) {
        ArgumentNullException.ThrowIfNull(catalog);
        services.AddResourceMonitoring();
        services.AddOpenTelemetry()
            .ConfigureResource(resource => resource
                .AddService(suite, serviceNamespace: "<suite-a>", serviceVersion: "1.0.0",
                    autoGenerateServiceInstanceId: false, serviceInstanceId: instanceId)
                .AddTelemetrySdk()
                .AddEnvironmentVariableDetector())
            .WithTracing(tracing => tracing
                .AddSource([.. catalog.Sources])
                .AddHttpClientInstrumentation(static http => http.RecordException = true)
                .SetSampler(new ParentBasedSampler(new TraceIdRatioBasedSampler(catalog.Ratio))))
            .WithMetrics(metrics => catalog.Views.Fold(
                metrics.AddMeter([.. catalog.Meters]).SetExemplarFilter(ExemplarFilterType.TraceBased),
                static (admitted, view) => admitted.AddView(view.Instrument, view.Shape)))
            .WithLogging(configureBuilder: null, configureOptions: static capture => capture.IncludeScopes = true)
            .UseOtlpExporter();
        return services;
    }
}
```

## [05]-[CORRELATION_SPINE]

[IDENTITY_LAYERS]:
- Law: four identity layers, each minted by one owner, none derivable from another — correlation root at boot scope, trace id at request scope, span id at hop scope, causal stamp at event-order scope — and every exported surface answers same-process, same-request, same-hop, what-order; an unanswerable question is the gap an incident finds first.
- Law: one boot mint, three projections — the stamp envelope's origin, the pinned resource instance id, and the root tag on a static enricher row — and the equality of the three is a boot assertion.
- Law: log records carry trace and span ids natively as typed fields — a hand-written trace-id enricher marks a stale design; metrics join through exemplars and resource identity, never per-point correlation tags, which are one-series-per-request cardinality.
- Law: the three ambient breaks — pooled callbacks, native callbacks, manual threads — share one repair: capture context as a value, restore at entry; deferred work starts children from the captured `ActivityContext`, never the ambient current at execution time.
- Law: new roots mint random trace ids — the ratio sampler's verdict is a deterministic function of the id bytes, so a biased or derived id generator silently reshapes sampling.
- Law: the spine is provable in one assertion — one synthetic request yields a log record, a span, and an evidence fact joining on every declared layer; the single-request join test catches enricher, propagator, and stamp regressions together.

[ENRICHMENT_ROWS]:
- Law: enrichment splits by cost class — `IStaticLogEnricher` once per provider for process constants, `ILogEnricher` per record for request-scoped dimensions, `EnableEnrichment` activating both; a constant in a per-record row is waste, a per-request value in a static row is a bug.
- Law: an enricher is a pure projection to bounded tags sharing the record's flat namespace with generated tags — one registry owns the prefixes, and a dimension that needs I/O is a design error at the row; per-record byte cost times kept-record rate is the declared telemetry weight.
- Law: one fact has one enrichment seat per signal kind — logs through the row system, spans through options-bound enrich delegates at the instrumented seam, metrics never per-point — so "add it everywhere" is three declared rows, never one helper that scatters.
- Law: exception detail is one enrichment decision on `EnableEnrichment` — `CaptureStackTraces` trades the per-fault stack cost for the frame, `UseFileInfoForStackTraces` adds the leak-bearing file and line, and `IncludeExceptionMessage` admits the message body — so a captured stack is a prevention row reviewed against the taxonomy, never raw text appended outside the redaction seam.
- Law: the latency context is the explicit in-flight ledger — vocabulary registered at composition, recorded through resolved tokens, cheaper than child spans and free of sampling coupling — joining the suite through its registered root tag; durations never derive from stamp differences.

[STAMP_ALGEBRA]:
- Law: the stamp is one packed word — 48 bits wall milliseconds, 16 bits counter — so numeric order on the word is causal-consistent order, total under the origin tiebreak; one cell per process stamps every signal, receipt, and op-log entry, and a second cell is the named defect: each internally monotone, their merge not.
- Law: one `Advance` serves local tick and receive — the wall component takes the maximum of held, inbound, and now, the counter follows whichever component matched — so the stamp never trails the wall and runs ahead only by observed peer skew; counter saturation spins to the next millisecond, because silent wraparound is the one unrecoverable corruption.
- Law: `CompareTo` is the only ordering verb — the type hides the wall component because raw wall comparison is wrong by up to the skew bound — and serialization is fixed-width hex so lexicographic order equals numeric order in any store or log line.
- Law: the boot epoch rides the origin, so a reborn process is a new origin and high-water persistence is deleted; stamps order and never identify — canonical event identity is the `(stamp, origin)` pair.
- Boundary: durability composes already-stamped versions and owns only last-writer-wins adjudication; every other ordering construct in the suite composes this one type, and a second timestamp-ordering primitive anywhere is the collapse trigger.

```csharp conceptual
public readonly record struct Stamp(ulong Word) : IComparable<Stamp> {
    private const int CounterBits = 16;
    private const ulong CounterMask = (1UL << CounterBits) - 1;
    private long Millis => (long)(Word >> CounterBits);
    private int Count => (int)(Word & CounterMask);

    public static Stamp Genesis(long nowMillis) => new((ulong)nowMillis << CounterBits);
    public static Option<Stamp> Parse(ReadOnlySpan<char> hex) =>
        hex.Length == 16 && ulong.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var word)
            ? Some(new Stamp(word)) : None;

    public string Serialized => Word.ToString("x16", CultureInfo.InvariantCulture);
    public int CompareTo(Stamp other) => Word.CompareTo(other.Word);
    public TimeSpan OffsetFrom(long nowMillis) => TimeSpan.FromMilliseconds(Millis - nowMillis);

    public Stamp Advance(Stamp inbound, long now) {
        var l = Math.Max(Math.Max(Millis, inbound.Millis), now);
        var c = (l == Millis, l == inbound.Millis) switch {
            (true, true) => Math.Max(Count, inbound.Count) + 1,
            (true, _) => Count + 1,
            (_, true) => inbound.Count + 1,
            _ => 0,
        };
        return (ulong)c > CounterMask ? Genesis(l + 1) : new(((ulong)l << CounterBits) | (uint)c);
    }
}

public sealed record StampCell(Atom<Stamp> Cell, string Origin, TimeProvider Clock, TimeSpan Bound, Atom<Seq<FactRecord>> Facts) {
    public static StampCell Boot(string origin, Guid epoch, TimeProvider clock, TimeSpan bound, Atom<Seq<FactRecord>> facts) {
        ArgumentNullException.ThrowIfNull(clock);
        return new(Atom(Stamp.Genesis(clock.GetUtcNow().ToUnixTimeMilliseconds())), $"{origin}:{epoch:N}", clock, bound, facts);
    }

    public Stamp Now() => Cell.Swap(held => held.Advance(held, Clock.GetUtcNow().ToUnixTimeMilliseconds()));

    public Stamp Receive(Stamp inbound, string peer) {
        var now = Clock.GetUtcNow().ToUnixTimeMilliseconds();
        var advanced = Cell.Swap(held => held.Advance(inbound, now));
        return inbound.OffsetFrom(now) is var offset && offset > Bound
            ? (ignore(Facts.Swap(seen => seen.Add(new FactRecord.Skew(advanced, peer, offset, Bound)))), advanced).Item2
            : advanced;
    }
}
```

[SKEW_EVIDENCE]:
- Law: receive consumes the inbound wall component unconditionally — causal order never depends on whether skew is acceptable; an offset past the bound becomes one `FactRecord.Skew` case on the shared receipts stream and the stamp still advances, and rejection is a policy a consumer may layer above the envelope.
- Law: the bound derives from the skew cases on that stream — worst observed offset plus margin — a measured, revisable policy value; the per-peer fold over those cases, not the raw stream, is what health consumes.
- Law: span clocks carry duration truth and stamps carry order truth — a cross-process waterfall may show negative gaps up to the bound by design, and ordering is producer-stamped evidence, never consumer inference.

## [06]-[ENVELOPE_SEAM]

[ENVELOPE_SCHEMA]:
- Law: cross-process context is one versioned envelope — declared baggage keys, each with an owner, a classification verdict of identifiers-only, and a byte budget — and the seam owner holds the keys behind typed verbs; an ad-hoc baggage write bypasses classification review and erodes the budget invisibly.
- Law: baggage broadcasts to every downstream hop and instrumented client — identifiers only, never payload, never classified material; the stamp rides baggage rather than `tracestate`, because evidence seams are not always trace-aware.
- Law: two baggage stores live in one process and never synchronize — `Baggage.Current` is the SDK store and the one write surface, `Activity.Baggage` is read-only foreign material — and `Baggage` is an immutable value, so a discarded `SetBaggage` return changes nothing and compiles cleanly.
- Law: the platform and SDK propagator seams agree by boot assertion — before SDK initialization the SDK seam is a no-op that injects nothing, silently; `TraceStateString` mutation is read-modify-write by law, because overwrite clobbers foreign vendors.
- Law: a new transport writes one getter/setter adapter pair and delegates to the propagator — hand-rolled headers are the rejected form; a relay clears propagator-owned `Fields` before re-injecting or extraction becomes carrier-order-dependent.

[ADMISSION_VERDICTS]:
- Law: the receive-advance executes once at the transport admission seam where extraction already happens, never per handler; departure stamps the post-advance value, so the wire never carries stale time forward.
- Law: arrival resolves across the `Fin<Arrival>` rail — refusal where context is contractual rides the fail side, the success side joins a present trace context or adopts a context-less frame as a countable foreign root, and quarantine is a consumer policy layered above the seam — so a child started from the zero trace id never mints, because a plausible-looking tree from a zero id corrupts every downstream join.
- Law: the envelope version key turns mixed-fleet schema drift into a typed fault at extract, never a renamed key misread as absence; the version is numeric and compared as a number, because ordinal text comparison inverts past one digit.
- Exemption: the propagator's carrier inject body is the platform-forced statement seam.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Arrival {
    private Arrival() { }
    public sealed record Joined(ActivityContext Parent, Stamp Stamp) : Arrival;
    public sealed record ForeignRoot(Stamp Stamp) : Arrival;
}

public static class EnvelopeSeam {
    private const int Version = 1;
    private const string VersionKey = "ctx.v";
    private const string OriginKey = "ctx.origin";
    private const string StampKey = "ctx.stamp";

    private static readonly TextMapPropagator Wire =
        new CompositeTextMapPropagator([new TraceContextPropagator(), new BaggagePropagator()]);
    private static readonly Action<Dictionary<string, string>, string, string> Put =
        static (frame, key, value) => frame[key] = value;
    private static readonly Func<Dictionary<string, string>, string, IEnumerable<string>> Take =
        static (frame, key) => frame.TryGetValue(key, out var held) ? [held] : [];

    public static Dictionary<string, string> Depart(StampCell cell, ActivityContext current) {
        ArgumentNullException.ThrowIfNull(cell);
        var frame = new Dictionary<string, string>(StringComparer.Ordinal);
        Wire.Inject(new PropagationContext(current, Baggage.Create(new Dictionary<string, string>(StringComparer.Ordinal) {
            [VersionKey] = Version.ToString(CultureInfo.InvariantCulture), [OriginKey] = cell.Origin, [StampKey] = cell.Now().Serialized,
        })), frame, Put);
        return frame;
    }

    public static Fin<Arrival> Admit(StampCell cell, Dictionary<string, string> frame, string peer) {
        var inbound = Wire.Extract(default, frame, Take);
        return Optional(inbound.Baggage.GetBaggage(VersionKey))
            .Bind(static held => int.TryParse(held, NumberStyles.None, CultureInfo.InvariantCulture, out var minted) && minted <= Version
                ? Some(minted) : None)
            .ToFin(Error.New(7301, "<envelope-version-ahead>"))
            .Bind(_ => Optional(inbound.Baggage.GetBaggage(StampKey)).Bind(static text => Stamp.Parse(text))
                .ToFin(Error.New(7302, "<unstamped-frame>")))
            .Map(stamp => cell.Receive(stamp, peer))
            .Map(stamp => inbound.ActivityContext.TraceId != default
                ? (Arrival)new Arrival.Joined(inbound.ActivityContext, stamp)
                : new Arrival.ForeignRoot(stamp));
    }
}
```

## [07]-[REDACTION_SEAM]

[TAXONOMY]:
- Law: one taxonomy per suite — sealed attribute rows each binding one `(taxonomy, value)` pair; classes partition by disclosure consequence, not data type, and the count stays single-digit because every class is a redactor row and an audit row.
- Law: `None` is an affirmative reviewed-public verdict and `Unknown` is never-reviewed — unannotated data is `Unknown`-shaped and falls to the erasing fallback; a default that maps absence to `None` is the seam's most dangerous misconfiguration.
- Law: classification sets are the redaction key under exact-set match — `{A, B}` does not resolve `{A}`'s row — so every producible union is a declared row, and a missing one is silent erasure: an availability bug with a compliance-shaped cause, caught by the reachable-set diff at the commit that creates it.
- Law: a generic carrier classified at its type parameter propagates sensitivity to every payload that flows through it; secrets are not a classification — credential material is barred from the emission grammar entirely, because a redacted secret still transited the pipeline buffers.

[ENFORCEMENT]:
- Law: enforcement has exactly one seam — annotations on contract types, the generator separating classified tags at compile time, `EnableRedaction` activating before any provider observes a record; everything downstream receives post-redaction data and never re-redacts — stores verify classification admission as a typed rejection, and a second masking pass anywhere is the named defect.
- Law: redaction applies only where classification metadata exists — a payload bypassing the generated path carries no classification and therefore no redaction, which is the structural argument for the generated-emission monopoly; foreign-process data arrives unclassified regardless of origin posture and re-classifies onto the local taxonomy before re-emission.
- Law: redaction precedes every volume policy by construction — buffered records hold redacted values, and the exporter serializes post-seam arrays, so no codec or transport choice can weaken the posture.
- Law: three shipped rows partition disclosure — erase what nobody joins on, HMAC what operations must correlate, pass what review cleared — and the fallback stays erasure; HMAC keys bind from configuration sections, `KeyId` epochs partition pseudonym spaces, and rotation cadence is the declared joinability horizon.
- Law: `ApplyDiscriminator` folds the tag name into the token so cross-tag correlation is opt-in, and flipping it mid-retention is a key-rotation event, never a toggle.
- Law: the seam covers the log path only — spans, instrument tags, latency tags, and baggage are prevention rows reviewed at their declared roots, and an enforcement design stopping at the log seam governs a fraction of the exfiltration surface.
- Law: the posture folds to taxonomy rows, the per-process redactor map, the rotation registry, and the prevention inventory — proven both ways at boot: a canary value per row asserted redacted in export, store admission rejecting unclassified payloads.
- Exemption: the redaction root's builder-mutation body is the platform-forced statement seam.

```csharp conceptual
public static class Sensitivity {
    public static readonly DataClassification Identifier = new(nameof(Sensitivity), nameof(Identifier));
    public static readonly DataClassification Payload = new(nameof(Sensitivity), nameof(Payload));
}

public sealed class IdentifierAttribute() : DataClassificationAttribute(Sensitivity.Identifier);

public sealed class PayloadAttribute() : DataClassificationAttribute(Sensitivity.Payload);

public sealed record Account([property: Identifier] string Key, [property: Payload] string Note, int Rank);

public static partial class AccountLog {
    [LoggerMessage(EventId = 7601, EventName = "AccountAdmitted", Level = LogLevel.Information,
        Message = "account admitted at rank {Rank}")]
    public static partial void Admitted(ILogger logger, int rank, [LogProperties] Account account);
}

public static class RedactionRoot {
    public static ILoggingBuilder Compose(ILoggingBuilder logging, IConfigurationSection hmacKeys) {
        ArgumentNullException.ThrowIfNull(logging);
        logging.Services.AddRedaction(redaction => redaction
            .SetHmacRedactor(hmacKeys, Sensitivity.Identifier)
            .SetRedactor<ErasingRedactor>(Sensitivity.Payload, new DataClassificationSet(Sensitivity.Identifier, Sensitivity.Payload))
            .SetFallbackRedactor<ErasingRedactor>());
        return logging.EnableRedaction(static seam => seam.ApplyDiscriminator = true);
    }
}
```
