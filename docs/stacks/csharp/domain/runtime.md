# [RUNTIME]

A process is one composed value. A closed modality row resolves boot, lifetime, signal, and drain variance through one fold; one sealed composition root folds module-contributed descriptor rows and makes post-seal drift a throw, not a review item; configuration admits once through derived keys into a validated frozen policy cell that consumers read as a value; lifecycle, drain, and degradation are total state machines over single cells whose every consumer is a projection; caches and pools bound rebuild cost under explicit validity and reset predicates and are never systems of record; and every temporal behavior derives from one clock seam and one schedule catalog. Growth lands as rows — a new process shape, module, policy record, drain band, rank, retention lane, or schedule is one declaration inside an existing owner, never new scaffolding beside it.

## [01]-[RUNTIME_CHOOSER]

This table routes a runtime concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                 | [OWNER]                                      | [REJECTED_FORM]                 |
| :-----: | :------------------------ | :------------------------------------------- | :------------------------------ |
|  [01]   | process-shape variance    | modality row + one boot fold                 | per-modality bootstrap files    |
|  [02]   | service registration      | module descriptor rows + sealed fold         | extension-call scatter          |
|  [03]   | configuration and options | derived keys + generated stack + frozen cell | monitor reads in consumers      |
|  [04]   | lifecycle and shutdown    | one phase cell + banded drain ledger         | parallel token reads, flat stop |
|  [05]   | capability state          | health rank fold                             | per-component degraded flags    |
|  [06]   | rebuild-cost bounding     | cache and pool retention rows                | hand-rolled caches and limiters |
|  [07]   | time and cadence          | one clock seam + schedule catalog            | ambient now, per-job timers     |

## [02]-[MODALITY_AXIS]

[MODALITY_FOLD]:
- Law: boot, lifetime, signal, and drain variance is one closed modality vocabulary — each row carries its `HostApplicationBuilderSettings` identity and its signal-ownership registrations, one fold consumes the row, and a new process shape is one row, never a bootstrap file.
- Law: `HostApplicationBuilderSettings` is the only identity admission — `ApplicationName`, `EnvironmentName`, and `ContentRootPath` freeze at builder construction and later writes throw `NotSupportedException`; a pre-populated `ConfigurationManager` seeds through `Configuration`, the one mutation the freeze permits.
- Law: `Host.CreateApplicationBuilder` is an eager constructor fold — `Environment`, `Configuration`, and `Services` are live when it returns, so modules read real values while contributing; `Host.CreateEmptyApplicationBuilder` is the explicit-everything boot for rows that must not inherit ambient machine state.
- Law: a hosted posture is values on the row, never a branch — the embedded row pairs the empty builder with a pass-through `IHostLifetime` because the surrounding process owns the signals; the plugin row's `Preboot` sets the `Microsoft.Extensions.DependencyInjection.DisableDynamicEngine` `AppContext` switch, a process-global mutation the fold runs before `BuildServiceProvider` rather than a service registration, because IL emission is hostile there and a switch set after the provider builds is read too late.
- Law: manager lifetimes register unconditionally — `AddSystemd()` and `AddWindowsService()` are probe-gated no-ops outside their manager — so at most one activates and application code never tests the modality; a manager row pins `ContentRootPath` to `AppContext.BaseDirectory` because the manager boots with a meaningless cwd.
- Law: lifetime ownership is closed and boot abort is typed — a substitute `IHostApplicationLifetime` registration throws `ArgumentException` at build because the host downcasts to its own lifetime, so lifetime variance lives only in `IHostLifetime` rows, and `HostAbortedException` is the one intentional boot-abort signal.
- Law: force `ValidateOnBuild` and `ValidateScopes` in every posture through one `ServiceProviderOptions` on the registered factory — both default to the development predicate, so production roots silently skip validation unless forced and singleton-over-scoped capture surfaces at traffic instead of boot; the fold owns the one host build, so the options are declared once here and never re-stated by a second provider construction.
- Boundary: the fold owns modality plus the single build and yields `Fin<IHost>`; the descriptor algebra it builds over arrives as one `Action<IServiceCollection>` contribution and the seal receipt reads the build outcome, both `[03]`'s, so this section never enumerates a descriptor row nor mints the `BuildFact`.
- Boundary: CLI rows parse before boot — the `SetAction` action is the only site that composes and runs the host, args flow into `Args`, the action's cancellation token is the run token, and boot failure maps to an exit code only here, so help, version, completion, and parse faults never construct the runtime.
- Exemption: the boot fold's builder-mutation body is the platform-forced statement seam.

```csharp conceptual
public sealed class HandedLifetime : IHostLifetime {
    public Task WaitForStartAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}

[SmartEnum<string>]
public sealed partial class Modality {
    public static readonly Modality Service = new("<modality-a>",
        static args => new HostApplicationBuilderSettings { Args = args, ContentRootPath = AppContext.BaseDirectory },
        static services => services.AddSystemd().AddWindowsService(),
        static () => unit);
    public static readonly Modality Embedded = new("<modality-b>",
        static args => new HostApplicationBuilderSettings { Args = args, DisableDefaults = true },
        static services => services.AddSingleton<IHostLifetime, HandedLifetime>(),
        static () => unit);
    public static readonly Modality Plugin = new("<modality-c>",
        static args => new HostApplicationBuilderSettings { Args = args, DisableDefaults = true, ContentRootPath = AppContext.BaseDirectory },
        static services => services.AddSingleton<IHostLifetime, HandedLifetime>(),
        static () => fun(() => AppContext.SetSwitch("Microsoft.Extensions.DependencyInjection.DisableDynamicEngine", true))());

    [UseDelegateFromConstructor]
    public partial HostApplicationBuilderSettings Identity(string[] args);
    [UseDelegateFromConstructor]
    public partial IServiceCollection Signals(IServiceCollection services);
    [UseDelegateFromConstructor]
    public partial Unit Preboot();
}

public static class Boot {
    static readonly ServiceProviderOptions Validated = new() { ValidateOnBuild = true, ValidateScopes = true };

    public static Fin<IHost> Compose(Modality modality, string[] args, Action<IServiceCollection> contribute) {
        ArgumentNullException.ThrowIfNull(modality);
        ArgumentNullException.ThrowIfNull(contribute);
        ignore(modality.Preboot());
        var settings = modality.Identity(args);
        var builder = settings.DisableDefaults ? Host.CreateEmptyApplicationBuilder(settings) : Host.CreateApplicationBuilder(settings);
        builder.ConfigureContainer(new DefaultServiceProviderFactory(Validated));
        contribute(modality.Signals(builder.Services));
        return Try.lift(builder.Build).Run();
    }
}
```

## [03]-[COMPOSITION_ROOT]

[DESCRIPTOR_FOLD]:
- Law: a module yields `ServiceDescriptor` rows — `Describe`/`DescribeKeyed` plus a lifetime value is the complete registration algebra — and the root is the only caller of any registration spelling; a planned-but-dormant module is a real key over an empty row set, so the capability inventory stays enumerable and activation is a one-row diff.
- Law: one `KeyedService.AnyKey` factory row serves an entire key family because the key arrives as a dispatch input; `[FromKeyedServices]` selects per constructor parameter and `[ServiceKey]` injects the resolved key, so one implementation self-discriminates and per-key subclasses collapse.
- Law: `TryAdd` dedupes on service type, `TryAddEnumerable` on (service, implementation) — a factory row whose delegate erases the implementation type defeats dedup and silently double-registers; hosted services are `TryAddEnumerable` singleton rows.
- Law: scan source is a composition row: bounded selectors such as `FromAssembliesOf(...)` name the admitted inventory, and dependency-context scans use explicit `FromDependencyContext(context, predicate)`; ambient `FromApplicationDependencies()` is rejected because its fallback walks entry-assembly dependencies when `DependencyContext.Default` is unavailable, silently changing the scan set.
- Law: the root provider owns singleton state and retains every disposable transient it materializes until process death; unit-of-work resolution rides `CreateAsyncScope`, whose `await using` disposal is chosen at creation because synchronous scope disposal throws on an async-only disposable.
- Law: the host `Build()` is the one provider construction — it is one-shot, applies the `[02]` `ValidateOnBuild`/`ValidateScopes` options through the registered factory, and calls `MakeReadOnly()` itself, so this section contributes descriptors and reads the outcome but never builds a second provider; `ValidateOnBuild` aggregates every defective row into one `AggregateException` inventory yet skips open-generic rows, so closed-generic smoke resolutions are that family's only build-time proof, and a standalone `BuildServiceProvider` beside the host build is the rejected duplicate the host build silently discards.
- Law: a scan is data folded under `RegistrationStrategy.Throw` — a collision with an explicit row is a boot failure, never shadowing; `Decorate` moves each original to a generated keyed slot, inherits its lifetime and position, stacks last-call-outermost, and throws on zero matches, and scan rows fold before any decoration pass runs; decoration mutates the collection, so it rides the pre-build contribution, never a second pass after the seal.
- Law: sealing folds the contribution table and the single build's outcome into one closed receipt family — the accepted case carries per-lifetime descriptor counts, dormant inventory, and decoration depth read off the `out DecoratedService<TService>` handle `TryDecorate` mints (the `Try` form keeps a zero-match decoration on the typed rail where the throwing `Decorate` would bypass the receipt), the rejected case carries the host build's `ValidateOnBuild` `AggregateException` inner list verbatim — so boot emits exactly one `[Union]` fact, the new failure cause lands as one case, and a record carrying only the accepted half is the rejected shape because it cannot name the build that failed.
- Reject: `Replace`/`RemoveAll` in module code, runtime `GetService` null-probes where `IServiceProviderIsService` answers at composition, and decorating enumerable marker families — the backwards walk wraps every matching row, so only single-contract seams decorate.
- Boundary: `Decorate` matches a descriptor only where its `ServiceKey` equals the request's, so the non-keyed pass sees only `ServiceKey == null` rows and silently skips the `KeyedService.AnyKey` factory and every keyed family — a keyed seam takes its wrapper by folding it into the factory through the key vocabulary, never `Decorate`.
- Boundary: this section owns the descriptor algebra and the seal receipt; the modality fold and the one host build that consumes the contribution are `[02]`'s, so the contribution crosses as one `Action<IServiceCollection>` into that build and the build's `Fin<IHost>` outcome crosses back into the receipt, the decoration count carried over the callback edge on one boundary cell.
- Exemption: the contribution's collection-mutation body is the platform-forced statement seam.

```csharp conceptual
public interface IPort { int Probe(); }
public interface IStage { int Order { get; } }
public sealed class CorePort : IPort { public int Probe() => 1; }
public sealed class MeteredPort(IPort inner, TimeProvider clock) : IPort { public int Probe() => inner.Probe() + (int)(clock.GetTimestamp() & 1); }
public sealed class Pump : BackgroundService { protected override Task ExecuteAsync(CancellationToken stoppingToken) => Task.CompletedTask; }

public sealed record Module(string Key, Seq<ServiceDescriptor> Rows);

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record BuildFact {
    private BuildFact() { }
    public sealed record Accepted(ServiceProvider Provider, HashMap<ServiceLifetime, int> Lifetimes, Seq<string> Dormant, int Decorated) : BuildFact;
    public sealed record Rejected(Seq<Error> Defects) : BuildFact;
}

public static class Root {
    public static Seq<Module> Table(TimeProvider clock) => [
        new(nameof(IPort), [
            ServiceDescriptor.Describe(typeof(IPort), typeof(CorePort), ServiceLifetime.Singleton),
            ServiceDescriptor.KeyedSingleton<IPort>(KeyedService.AnyKey, static (_, _) => new CorePort())]),
        new(nameof(TimeProvider), [ServiceDescriptor.Singleton(clock)]),
        new("<module-dormant>", []),
    ];

    public static Action<IServiceCollection> Contribute(Seq<Module> table, Atom<int> decorated) => services => {
        services.Add(table.Bind(static module => module.Rows));
        services.TryAddEnumerable(ServiceDescriptor.Singleton<IHostedService, Pump>());
        services.Scan(static scan => scan.FromAssembliesOf(typeof(IStage))
            .AddClasses(static classes => classes.AssignableTo<IStage>(), publicOnly: false)
            .UsingRegistrationStrategy(RegistrationStrategy.Throw).AsImplementedInterfaces().WithSingletonLifetime());
        ignore(decorated.Swap(_ => services.TryDecorate<IPort, MeteredPort>(out _) ? 1 : 0));
    };

    public static BuildFact Seal(Fin<IHost> built, Seq<Module> table, int decorated) => built.Match(
        Succ: host => new BuildFact.Accepted((ServiceProvider)host.Services,
            table.Bind(static module => module.Rows).Fold(HashMap<ServiceLifetime, int>(),
                static (counts, row) => counts.AddOrUpdate(row.Lifetime, static n => n + 1, 1)),
            table.Filter(static module => module.Rows.IsEmpty).Map(static module => module.Key),
            decorated),
        Fail: error => new BuildFact.Rejected(error.ToException() is AggregateException aggregate
            ? toSeq(aggregate.InnerExceptions).Map(static ex => Error.New(ex))
            : Seq1(error)));
}
```

## [04]-[OPTIONS_ADMISSION]

[ADMISSION_STACK]:
- Law: precedence is per-key last-source-wins, never per-file — absence is an explicit off-value in the record because upstream key deletion is impossible; complete the rank before the first typed read, since `ConfigurationManager` materializes each source at `Add`.
- Law: every section key derives from the policy type — `nameof`-rooted, member keys the property names the binder already matches — and external spellings map to canonical keys only on source rows (`SwitchMappings`, environment prefixes), so the inward key space holds zero application-authored literals and audits as an absence.
- Law: the trim-safe stack is generator-on-generator — `EnableConfigurationBindingGenerator` intercepts the bind into a constructor-bound immutable record, `[OptionsValidator]` emits shape law from annotations with `[ValidateObjectMembers]` recursion (without it nested members silently skip), hand `Validate` rows own relational law, and `ValidateOnStart` proves the chain before any service starts.
- Law: one record owns one `OptionsBuilder` chain in one residence; a bounded variant family is named registrations of one type, never sibling option types.
- Law: `ErrorOnUnknownConfiguration` and the startup sweep close complementary drift — stale keys survive without the throw, invalid values survive without the sweep; sweep failures aggregate into one typed inventory, while a configure-delegate throw escapes immediately as a composition defect.

[FROZEN_PUBLISH]:
- Law: consumers never read the monitor — cache invalidation precedes re-validation, so a bad edit turns every consumer read into a throw with the last-good value already evicted; the root publishes one cell where a valid candidate swaps and an invalid one retains the incumbent with a rejected-write fact.
- Law: a content-identical candidate is the no-op arm, erasing watcher double-fires with no debounce machinery; the cell swap is the only mutation, so torn reads are unrepresentable, and the same fold publishes every externally mutated policy surface — schedule catalogs, capability grants.
- Law: reload receipts carry derived facts — content hash, the changed-key diff `GetDebugView` renders under its redacting value processor, the validation inventory — never raw values, so secrets stay out of the receipt stream by construction.
- Law: a unit of work captures the cell once at entry and threads the record, so mid-flight swaps land on the next unit; coherence wider than one cell marks two sections that were one record wrongly split, and the umbrella record over both is the repair.

```csharp conceptual
public sealed record LanePolicy(
    [property: Range(1, 64)] int Width = 8,
    [property: Required] string Label = "<value-a>",
    int Burst = 0) {
    public static string Section { get; } = nameof(LanePolicy)[..^"Policy".Length];
}

[OptionsValidator]
public sealed partial class LanePolicyLaw : IValidateOptions<LanePolicy>;

public static class PolicyAdmission {
    public static OptionsBuilder<LanePolicy> Admit(IServiceCollection services) =>
        services.AddSingleton<IValidateOptions<LanePolicy>, LanePolicyLaw>().AddOptions<LanePolicy>()
            .BindConfiguration(LanePolicy.Section, static binder => binder.ErrorOnUnknownConfiguration = true)
            .Validate(static policy => policy.Burst <= policy.Width * 8, "<relational-law>")
            .ValidateOnStart();
}

public static class PolicyCell {
    public static readonly Atom<LanePolicy> Current = Atom(new LanePolicy());
    public static IDisposable Publish(IConfiguration root, IOptionsMonitor<LanePolicy> monitor, Atom<Seq<Error>> rejected) {
        ArgumentNullException.ThrowIfNull(root);
        return ChangeToken.OnChange(root.GetReloadToken, () => ignore(
            Try.lift(() => monitor.CurrentValue).Run().Match(
                Succ: candidate => candidate == Current.Value ? unit : ignore(Current.Swap(_ => candidate)),
                Fail: error => ignore(rejected.Swap(facts => facts.Add(error))))));
    }
}
```

## [05]-[LIFECYCLE_DRAIN]

[PHASE_SPINE]:
- Law: one closed phase family lives in one cell advanced only by lifecycle hooks, lifetime tokens, background-fault routing, the rank fold, and the band walk; every up/degraded/draining question is a cell projection, and phase-keyed behavior is a total fold whose new phase is one case plus the rows the compiler then demands.
- Law: stop ordering is two-path — signal-initiated stop fires the stopping token before the stopping phase, programmatic stop the reverse — and every stop source collapses into one idempotent stopping edge, so admission keys off the cell's normalized edge, never either input alone.
- Law: tokens carry edges, never work or success — lifetime callbacks run inline on the signaling thread, a never-started host still walks its stop edges, and the stopped edge fires on failed shutdowns too, so work lives in hosted phases and outcome reads the cell's ledger, not the token.
- Law: lifetime policy is rankable configuration — `HostOptions` binds `ShutdownTimeout` and `StartupTimeout` as `TimeSpan` durations plus `ServicesStartConcurrently` and `ServicesStopConcurrently` under invariant parsing, and sequential start aborts at the first failure while concurrent start aggregates every failure, so concurrency is declared only over a provably order-free start set.
- Law: pre/post hooks are phase barriers across all lifecycle services, never per-service wrappers — start runs in registration order, stop in reverse, so declaring participations in dependency order yields the drain order with zero extra mechanism.
- Law: `BackgroundService.StartAsync` queues the loop and returns complete — fail-fast checks live in the validation sweep or `StartingAsync`, never `ExecuteAsync` — and a faulted loop folds through `BackgroundServiceExceptionBehavior` without rethrowing on the run path, so exit evidence requires its own fold into the faulted phase.
- Law: one cancellation spine, two segments — start is caller, stopping edge, and a startup timeout spanning lifetime wait, validation sweep, and all three start phases, so per-service budgets are fractions of it; stop is caller and shutdown timeout — no component creates a root source, and a private deadline is a linked child so the spine always wins.
- Exemption: the hosted hook bodies and the band walk are the platform-forced Task seam.

[BANDED_DRAIN]:
- Law: drain is ordered bands — fence admission, settle in-flight, flush durable effects, emit receipts — each a cooperative await under a `Share` of `HostOptions.ShutdownTimeout` with a forced linked token at the band edge; stop never aborts early, so a hung band cancels its stragglers and the next band still runs, and the receipt flush pins to the last band by construction.
- Law: the forced edge of level k is the cooperative signal of level k+1 — operation, band, process, supervisor — and the host timeout sits strictly inside the manager's kill window, verified at boot as environment, never assumed.
- Law: the band walk is an async fold threading the ledger, never a mutable loop — `Task<Seq<BandFact>>` chains through `Task.Bind` so each band reduces the prior accumulation, and the terminal `Phase.Stopped` swap publishes the whole ledger in one transition; a `ledger.Add` re-assignment inside a `foreach` is the rejected imperative shape.
- Boundary: `band.Settle` is one lane's cooperative-then-forced drain owned whole by the concurrency surface's participation contract — the band walk composes it as an opaque callback and owns only the phase-cell advance, the `Share` budget split, and the last-band receipt pin; the per-lane token mechanics and the serialisable drain permit are settled law, never re-derived here.

```csharp conceptual
public readonly record struct BandFact(string Name, TimeSpan Budget, TimeSpan Elapsed, bool Forced);
public sealed record Band(string Name, double Share, Func<CancellationToken, Task> Settle);

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Phase {
    private Phase() { }
    public sealed record Composing : Phase;
    public sealed record Running : Phase;
    public sealed record Draining(string Band) : Phase;
    public sealed record Stopped(Seq<BandFact> Ledger) : Phase;
    public sealed record Faulted(Error Evidence) : Phase;
}

public sealed class LifecycleSpine(IHostApplicationLifetime lifetime, IOptions<HostOptions> options, TimeProvider clock, Seq<Band> bands) : IHostedLifecycleService {
    public static readonly Atom<Phase> Cell = Atom<Phase>(new Phase.Composing());
    public static bool Admits => Cell.Value is Phase.Running;
    public static Unit Fault(Error evidence) => ignore(Cell.Swap(_ => new Phase.Faulted(evidence)));
    public Task StartingAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task StartAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task StoppedAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task StartedAsync(CancellationToken cancellationToken) {
        lifetime.ApplicationStopping.Register(() =>
            ignore(Cell.Swap(phase => phase is Phase.Running ? new Phase.Draining(bands[0].Name) : phase)));
        ignore(Cell.Swap(static _ => new Phase.Running()));
        return Task.CompletedTask;
    }
    public async Task StoppingAsync(CancellationToken cancellationToken) {
        var ledger = await bands.Fold(
            Task.FromResult(Seq<BandFact>()),
            (acc, band) => acc.Bind(carried => Walk(carried, band, cancellationToken))).ConfigureAwait(false);
        ignore(Cell.Swap(_ => new Phase.Stopped(ledger)));
    }

    async Task<Seq<BandFact>> Walk(Seq<BandFact> ledger, Band band, CancellationToken cancellationToken) {
        ignore(Cell.Swap(_ => new Phase.Draining(band.Name)));
        var budget = options.Value.ShutdownTimeout * band.Share;
        using var forced = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        forced.CancelAfter(budget);
        var mark = clock.GetTimestamp();
        try { await band.Settle(forced.Token).ConfigureAwait(false); return ledger.Add(new BandFact(band.Name, budget, clock.GetElapsedTime(mark), Forced: false)); }
        catch (OperationCanceledException) { return ledger.Add(new BandFact(band.Name, budget, clock.GetElapsedTime(mark), Forced: true)); }
    }
}
```

## [06]-[DEGRADATION]

[RANK_ALGEBRA]:
- Law: severity is registration policy, never contributor code — `FailureStatus` grades one probe unhealthy or degraded, and registering one dependency twice under short and long timeouts turns latency bands into rank pressure with no contributor measuring time; per-row `Delay`/`Period` overrides group into one timer per cadence class.
- Law: evaluation is concurrent and total — every check runs in its own scope, contributor exceptions and per-registration timeouts become entries at the registration's `FailureStatus`, and report latency is the slowest check; aggregate status is worst-of and short-circuits, so partial-capability semantics live in the rank fold, never the report.
- Law: probes project capability and the runtime owns the consuming machine — a closed ordered rank family carries retained capability sets as data, and consumers ask whether a capability is retained, never which rank holds; diagnostics owns the signals and resource monitors feeding the report.
- Law: transitions are asymmetric by design — escalation jumps straight to the worst probed rank, recovery steps to `Recovered` (the next-less-severe rank read from a memoized predecessor index `Zip`-derived once over the `Items` key order, never a per-call `OrderByDescending` nor `Get(Key - 1)` arithmetic that a key gap would break) only after the current rank's window of consecutive calm evaluations, the window a rank-row column rather than a contributor constant — so a probe escalates past intermediate ranks but recovery walks the ladder one rung per window, making a mid-ladder rank a recovery waypoint rather than a reachable candidate, and flapping cannot oscillate the system.
- Law: provisioning is verification-only — a boot environment check is a contributor whose failure folds to an initial reduced rank with a receipt, and the same contributor at cadence recovers the rank through ordinary hysteresis, so no second re-provisioning path exists.

```csharp conceptual
[SmartEnum<int>]
public sealed partial class Rank {
    public static readonly Rank Full = new(0, window: 0, retained: ["<cap-a>", "<cap-b>", "<cap-c>"]);
    public static readonly Rank Reduced = new(1, window: 2, retained: ["<cap-a>", "<cap-b>"]);
    public static readonly Rank Essential = new(2, window: 3, retained: ["<cap-a>"]);
    public static readonly Rank DrainOnly = new(3, window: 4, retained: []);
    public int Window { get; }
    public Seq<string> Retained { get; }

    static readonly Lazy<FrozenDictionary<int, Rank>> Predecessor = new(static () =>
        Items.OrderBy(static rank => rank.Key)
            .Zip(Items.OrderBy(static rank => rank.Key).Skip(1), static (less, more) => KeyValuePair.Create(more.Key, less))
            .ToFrozenDictionary());

    public Rank Recovered => Predecessor.Value.TryGetValue(Key, out var milder) ? milder : this;
    public static Rank Worst(Rank left, Rank right) => left.Key >= right.Key ? left : right;
}

public sealed record RankState(Rank Current, int Calm);
public sealed class PeerProbe : IHealthCheck { public Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default) => Task.FromResult(HealthCheckResult.Healthy()); }

public static class HealthRows {
    public static IHealthChecksBuilder Contribute(IServiceCollection services) =>
        services.AddSingleton<PeerProbe>().AddSingleton<IHealthCheckPublisher, DegradationFold>()
            .AddHealthChecks()
            .Add(new HealthCheckRegistration("<probe-latency>", static sp => sp.GetRequiredService<PeerProbe>(),
                HealthStatus.Degraded, tags: ["<cap-b>"], timeout: TimeSpan.FromMilliseconds(250)) { Period = TimeSpan.FromSeconds(5) })
            .Add(new HealthCheckRegistration("<probe-alive>", static sp => sp.GetRequiredService<PeerProbe>(),
                HealthStatus.Unhealthy, tags: ["<cap-a>"], timeout: TimeSpan.FromSeconds(5)) { Delay = TimeSpan.FromSeconds(5) });
}

public sealed class DegradationFold : IHealthCheckPublisher {
    public static readonly Atom<RankState> Cell = Atom(new RankState(Rank.Full, Calm: 0));
    public static bool Retains(string capability) => Cell.Value.Current.Retained.Exists(held => held == capability);
    public Task PublishAsync(HealthReport report, CancellationToken cancellationToken) =>
        Task.FromResult(Cell.Swap(state => Advance(state, Candidate(report))));
    static Rank Candidate(HealthReport report) =>
        report.Entries.Values.Aggregate(Rank.Full, static (worst, entry) => Rank.Worst(worst,
            entry.Status switch { HealthStatus.Unhealthy => Rank.DrainOnly, HealthStatus.Degraded => Rank.Reduced, _ => Rank.Full }));
    static RankState Advance(RankState state, Rank candidate) =>
        (Delta: candidate.Key.CompareTo(state.Current.Key), state.Calm) switch {
            ( > 0, _) => new RankState(candidate, Calm: 0),
            ( < 0, var calm) when calm + 1 >= state.Current.Window => new RankState(state.Current.Recovered, Calm: 0),
            ( < 0, var calm) => state with { Calm = calm + 1 },
            _ => state with { Calm = 0 },
        };
}
```

## [07]-[RETENTION_LANES]

[CACHE_LAW]:
- Law: every cached read is `GetOrCreateAsync` over (derived key, explicit `TState`, static factory, options row, tags) — get-then-set pairs are stampede-unsafe by construction, a set is a read-through with a constant factory, and batch removal verbs fold the singular forms.
- Law: topology is a flags value ORing per-call entry flags onto profile hard flags — L1-only, write-through, and probe postures are policy rows, and `DisableUnderlyingData` turns a miss into a default return with no factory run, the read-without-work row.
- Law: L1 storage discriminates payload immutability — types proven immutable share instances while mutable payloads re-deserialize per read, so consumers can never alias a cached mutable and immutable records are the only performant payload shape.
- Law: single-flight keys on (key, flags) and joiner cancellation is reference-counted — an impatient caller detaches without killing shared work, so observability counts joins, never factory runs.
- Law: tags are validity predicates compared on every hit, never indexes — `RemoveByTagAsync` shadows by timestamp, `*` is the constant-cost global epoch, and shadowed entries free memory only at natural expiry — so the tag vocabulary stays small, closed, and declared beside the key derivation.
- Law: keyed profiles absorb deployment shape — `AddKeyedHybridCache` rows carry L2 selection, serializer set, guards, and default entry options, with effective L1 lifetime clamped to the lesser of `LocalCacheExpiration` and `Expiration` and guard breaches degrading to factory-direct execution, never a fault; the memory-shim L2 is silently elided, so L2 behavior proves only against a real out-of-process backend.

[POOL_RESET]:
- Law: a pool bounds retention, never allocation — `Get` never blocks and burst overflow allocates then drops at return, so a pool pressed into limiting duty fails silently by allocating; throughput limiting is the concurrency layer's jurisdiction.
- Law: `IResettable.TryReset` is the entire return protocol — cleanup and sanity gate as one predicate conjunction, false discards with provider-dispatched disposal, and repair-and-return-true launders bad state; pools track no leases, so a bracket-shaped lease owning the unconditional return is the only leak discipline.
- Law: pool versus cache is one retention law over two value classes — identity-reused mutables under a reset predicate, value-reused immutables under validity predicates — and any correctness dependency on retention disqualifies both.

```csharp conceptual
public sealed record Snapshot(string Key, int Count);
public sealed class ReadLane(HybridCache cache) {
    static readonly HybridCacheEntryOptions Populate = new() { Expiration = TimeSpan.FromMinutes(5), LocalCacheExpiration = TimeSpan.FromMinutes(1) };
    static readonly HybridCacheEntryOptions ProbeOnly = new() { Flags = HybridCacheEntryFlags.DisableUnderlyingData | HybridCacheEntryFlags.DisableLocalCacheWrite };

    public ValueTask<Snapshot> Read(Func<string, CancellationToken, ValueTask<Snapshot>> load, string key, CancellationToken token) =>
        cache.GetOrCreateAsync($"<lane-a>:{key}", (Load: load, Key: key),
            static (state, ct) => state.Load(state.Key, ct),
            Populate, tags: ["<family-a>"], cancellationToken: token);

    public ValueTask<Snapshot> Peek(string key, CancellationToken token) =>
        cache.GetOrCreateAsync($"<lane-a>:{key}", unit,
            static (_, _) => ValueTask.FromResult(new Snapshot("<value-a>", 0)),
            ProbeOnly, cancellationToken: token);

    public ValueTask Invalidate() => cache.RemoveByTagAsync("<family-a>");
}

public sealed class ScratchBuffer : IResettable {
    readonly List<int> items = new(capacity: 128);
    public void Stage(int value) => items.Add(value);
    public bool TryReset() => items.Count <= 4096 && fun(items.Clear)() == unit;
}

public static class Lanes {
    static readonly DefaultObjectPoolProvider Provider = new() { MaximumRetained = 2 * Environment.ProcessorCount };
    public static readonly ObjectPool<ScratchBuffer> Scratch = Provider.Create<ScratchBuffer>();
    public static IO<A> Leased<A>(Func<ScratchBuffer, A> use) =>
        IO.lift(Scratch.Get).Bracket(Use: item => IO.lift(() => use(item)), Fin: item => IO.lift(fun(() => Scratch.Return(item))));
}
```

## [08]-[TIME_CADENCE]

[CLOCK_SEAM]:
- Law: two authorities, one frozen seam record — `TimeProvider` owns elapsed time, timers, and timestamps; `IClock` owns the current instant — registered once at the root with the home zone, every temporal capability a derivation; an ambient now-read is the universal defect, and derivation purity audits as an absence.
- Law: the calendar vocabulary is type-per-meaning — instants for recorded facts, zoned values for display, offset values for export, local-plus-zone-id for policy values; persisted text rides invariant pattern singletons (`InstantPattern.ExtendedIso`, `OffsetDateTimePattern.Rfc3339`) and temporal text admission rides `ParseResult<T>`, never exceptions.
- Law: zone ids persist as strings and rehydrate through the tzdb provider, whose id inventory makes zone validation a boot set-membership check — a stale or renamed id folds to the degradation rail at boot, never a first-firing surprise; the nullable lookup is the admission verb, the throwing indexer post-admission only.
- Law: local-to-instant is a three-outcome `MapLocal` fold — gap, unique, overlap — so treating it as infallible is the canonical DST bug and is unrepresentable when the mapping value is the API; duration arithmetic is exact and zone-free, while period arithmetic runs in local space and re-maps.

[CADENCE_FOLD]:
- Law: a schedule entry is data — expression text parsed non-throwing at composition, jitter seed, zone id, misfire policy, drain band — and the catalog is a frozen-publish surface; one driver folds N rows by minimum next occurrence on one seam timer, so zone-rule changes and catalog swaps land at the next boundary with no per-job timers and no stale-timer cancellation choreography.
- Boundary: the zone admits once through the tzdb provider into the row's `DateTimeZone`, and the BCL `TimeZoneInfo` the occurrence engine consumes is a derived value off the admitted zone's `Id` at that one foreign-engine boundary, never a second zone vocabulary the catalog stores unadmitted.
- Law: the only durable state is the last-fire stamp — the occurrence window between stamp and now is the misfire inventory, one policy row absorbs suspension, clock jumps, and drain alike, and firing receipts carry planned-versus-actual skew as evidence, never error.
- Law: hash-jitter `H` fields parse only with an explicit `jitterSeed` — derive it from the schedule key for fleet-identical fires or from a node key for deliberate spread, and the `DailyWithJitter`-style seeded templates cover every macro cadence without literal expressions.
- Law: the DST contract follows expression shape — interval forms fire in both repeated hours, point forms once, and gap occurrences shift to the first valid post-transition moment — so choosing the form is choosing the contract.
- Law: calendar recurrence is vocabulary, never cadence — annual dates and period-stepped repeats resolve through calendar arithmetic in local space, and a cron row encoding them surrenders the leap and month-length semantics the calendar types own.
- Boundary: cadence owns when — a max-concurrent knob on a row is the trespass signature, because throughput belongs to concurrency; in-operation backoff is effect-rail `Schedule` policy, and a cron expression inside a retry loop is the inverse trespass.

```csharp conceptual
public sealed record ClockSeam(TimeProvider Timer, IClock Calendar, DateTimeZone Home) {
    public ZonedClock Zoned => Calendar.InZone(Home);
    public string Stamp() => InstantPattern.ExtendedIso.Format(Calendar.GetCurrentInstant());
    public Option<Instant> Unique(LocalDateTime at) =>
        Home.MapLocal(at) is { Count: 1 } mapping ? Some(mapping.Single().ToInstant()) : None;
}

[SmartEnum]
public sealed partial class Misfire {
    public static readonly Misfire SkipToNext = new();
    public static readonly Misfire CatchUpOnce = new();
    public static readonly Misfire FireAll = new();
}

public sealed record ScheduleRow(string Key, CronExpression Cron, DateTimeZone Zone, Misfire Policy, int Band) {
    public TimeZoneInfo Bcl => TimeZoneInfo.FindSystemTimeZoneById(Zone.Id);
    public Seq<DateTimeOffset> Owed(DateTimeOffset lastFire, DateTimeOffset now) =>
        Policy.Switch(
            state: toSeq(Cron.GetOccurrences(lastFire, now, Bcl, fromInclusive: false)),
            skipToNext: static _ => Seq<DateTimeOffset>(),
            catchUpOnce: static owed => owed.IsEmpty ? owed : Seq(owed[owed.Count - 1]),
            fireAll: static owed => owed);
}

public static class Cadence {
    public static Option<ScheduleRow> Row(string key, string expression, int jitterSeed, string zoneId, Misfire policy, int band) =>
        (DateTimeZoneProviders.Tzdb.GetZoneOrNull(zoneId),
         CronExpression.TryParse(expression, CronFormat.IncludeSeconds, jitterSeed, out var cron) ? Optional(cron) : None) switch {
            ({ } zone, { IsSome: true, Case: CronExpression parsed }) => new ScheduleRow(key, parsed, zone, policy, band),
            _ => None,
        };
    public static Option<(ScheduleRow Row, DateTimeOffset At)> Next(Seq<ScheduleRow> catalog, ClockSeam seam) =>
        catalog.Choose(row => Optional(row.Cron.GetNextOccurrence(seam.Timer.GetUtcNow(), row.Bcl)).Map(at => (Row: row, At: at)))
            .Fold(Option<(ScheduleRow Row, DateTimeOffset At)>.None, static (best, hit) => Some(best.Filter(held => held.At <= hit.At).IfNone(hit)));
}
```
