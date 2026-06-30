# [RESILIENCE]

Transport resilience is one topology declared at the composition root. Every outbound hop owns exactly one pipeline, held as one registry row keyed by hop identity, and the callable domain code receives is already resilient — call sites carry zero resilience vocabulary, which is what makes a second owner a visible anomaly instead of a habit. Inside a pipeline, declaration order is the policy and every strategy knob is a validated property derived from the hop's allotment class, never a call-site literal; execution is outcome-first, folding every termination once at the seam into a typed rail value carrying its rejection evidence. HTTP seams compose the standard and hedging handlers as slot-editable options records selected by the hop row's idempotency columns; operator-forced darkness is one multi-breaker control per capability group; chaos is ordered policy below the strategies it tests. Domain-internal retry stays `Schedule` policy on effect rails and store transaction retry stays the store's execution strategy — never either beside a hop pipeline on one seam. Growth lands as rows: a new hop is one row, a new posture one options edit, a new fault mix one weighted generator row, never a new code surface.

## [01]-[RESILIENCE_CHOOSER]

This table routes a resilience concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                | [OWNER]                                    | [REJECTED_FORM]                  |
| :-----: | :----------------------- | :----------------------------------------- | :------------------------------- |
|  [01]   | outbound hop protection  | hop row + root registry claim              | pipeline built inside the seam   |
|  [02]   | strategy arrangement     | canonical declaration order                | order-blind strategy bag         |
|  [03]   | transient classification | one predicate row per failure family       | per-site exception switch        |
|  [04]   | seam execution           | `ExecuteOutcomeAsync` + one outcome fold   | thrown control flow above seam   |
|  [05]   | HTTP seam posture        | `AddStandardResilienceHandler` slot record | hand-stacked delegating handlers |
|  [06]   | concurrent duplication   | hedging on idempotent + replayable rows    | hedging as a failure remedy      |
|  [07]   | per-target isolation     | `SelectPipelineByAuthority` instances      | per-target client registrations  |
|  [08]   | domain-internal retry    | `Schedule` policy on rails                 | pipeline around domain logic     |
|  [09]   | store transaction retry  | store execution strategy                   | pipeline around store calls      |
|  [10]   | operator-forced dark     | one manual control per capability group    | restore-previous toggle          |
|  [11]   | fault injection          | chaos block below tested strategies        | bolt-on test-only harness        |

## [02]-[PIPELINE_LAW]

[ORDER_ALGEBRA]:
- Law: strategies execute in declaration order with the first-added strategy outermost — two pipelines with identical strategies in different order are different policies, and the difference is recoverable only from the declaration sequence.
- Law: the canonical chain is a derivation, not a convention — admission counts logical calls, so the limiter sits outside retry and its one lease spans every attempt; the budget bounds the whole loop, so the total deadline sits outside retry; health statistics count attempts, so the breaker sits inside retry; each attempt earns a fresh deadline, so the attempt timeout is innermost.
- Law: every reorder violates exactly one constraint and names its failure mode — limiter inside retry converts retry storms into permit starvation, breaker outside retry reaches its `MinimumThroughput` floor N-times slower, total deadline inside retry re-arms the budget per attempt and unbounds the loop, attempt deadline outside retry lets one slow attempt consume the entire budget.
- Law: a predicate's vocabulary is defined by what sits below it — an outer retry observes `TimeoutRejectedException` from the inner attempt deadline and `BrokenCircuitException` from the inner breaker, so a predicate written before placement is fixed is correct in one order and dead code in another.
- Law: fallback placement is a polarity switch — above retry it substitutes after every attempt fails; below retry it substitutes per attempt, and the retry predicate then sees the substituted outcome and silently stops looping.
- Law: every `Add*` call validates its options eagerly and `Build` validates the builder again — an invalid policy value is unconstructible, never a first-request fault — and the builder is single-use; `ResiliencePipeline<T>.Empty` is the absent-policy row value, never a null slot.
- Law: `AddStrategy(factory, options)` is the custom-strategy admission — the factory receives `StrategyBuilderContext` carrying exactly `Telemetry` and `TimeProvider` — and a non-generic `ResilienceStrategy` admits into typed builders, so a cross-cutting strategy is written once and composes into every typed pipeline.
- Law: ownership follows construction — `AddPipeline` nests an existing pipeline as an external component whose disposal never transfers, builder-constructed strategies dispose with the pipeline, and a limiter supplied through `AddRateLimiter` is never disposed by it, which is what lets one shared limiter span N pipelines.
- Law: reload and disposal honor the declaration atomically — a reload swaps the entire composite, never one strategy, so in-flight executions finish under the old order, and composite disposal walks declaration order outermost-first, so a teardown that publishes state still observes live inner components.

[POLICY_ROWS]:
- Law: every strategy knob is a derived property on the allotment class, not a literal at the call site — the retry bound is the attempt count the budget admits, the breaker sampling window is twice the attempt deadline, the break duration is half the window, the backoff seed and hedge delay are attempt fractions, and the limiter permits and breaker throughput derive from one concurrency floor — so a posture edit is one row edit and an incoherent knob pair is unconstructible; a numeric literal inside `AddRetry`, `AddCircuitBreaker`, `AddConcurrencyLimiter`, or `.Hedging` is the rejected form, reconstructing what the column already carries.
- Law: the default predicate of retry, hedging, fallback, and breaker handles every exception except `OperationCanceledException` — caller cancellation is never transient unless a predicate opts in — and one `PredicateBuilder<T>` row converts implicitly into all four `ShouldHandle` slots, so a hop's transient class is declared once.
- Law: delay algebra is Constant = base, Linear = (n+1)·base, Exponential = 2ⁿ·base; `UseJitter` is ±25% uniform on the linear forms and switches the exponential curve to decorrelated jitter, which spreads correlated retry storms.
- Law: `MaxDelay` caps only the computed curve — a `DelayGenerator` return bypasses the cap entirely, so server-directed delays are uncapped by design and any operator ceiling is enforced inside the generator; a null or negative generator return falls back to the curve.
- Law: retry predicate arguments carry the attempt number, so the handled class tightens or widens by attempt without a custom strategy; after `OnRetry` the failed attempt's result object is disposed — event delegates copy what they need, and storing the result is a use-after-dispose.
- Law: `TimeoutGenerator` decides per execution — a non-positive or infinite return disables the deadline for that execution only, making the deadline a per-call policy value.
- Law: half-open is one probe — a handled failure re-opens for another break, a success closes and resets statistics — and escalating break length is a `BreakDurationGenerator` row, never a custom strategy.
- Law: hedging `Delay` extremes are one policy value apart — zero launches all attempts as a parallel race, infinite is strictly sequential failover, a small positive value is tail-latency hedging.
- Law: two strategies of one type need distinct `Name` values or their telemetry merges — `(pipeline.name, strategy.name)` is the deduplication key; builder `TimeProvider` drives every delay, deadline, and sampling window from one injection point, and `Randomizer` is the jitter determinism seam.
- Use: `ConfigureTelemetry` once on the builder — the listener wraps the whole composite, every rejection carries `TelemetrySource` stamped at throw, and unconfigured telemetry skips event construction entirely.
- Use: `SeverityProvider` to demote expected retry churn and promote breaker opens — severity `None` suppresses recording entirely — with `ResultFormatter`, `MeteringEnrichers`, and `TelemetryListeners` as observability projections that cannot mutate the outcome.

```csharp conceptual
public sealed record Reply(bool Faulted);

[SmartEnum<string>]
public sealed partial class AllotmentClass {
    public static readonly AllotmentClass Interactive = new("<class-a>", total: TimeSpan.FromSeconds(8), attempt: TimeSpan.FromSeconds(2), trip: 0.2, floor: 100);
    public static readonly AllotmentClass Bulk = new("<class-b>", total: TimeSpan.FromSeconds(45), attempt: TimeSpan.FromSeconds(10), trip: 0.5, floor: 32);

    public TimeSpan Total { get; }
    public TimeSpan Attempt { get; }
    public double Trip { get; }
    public int Floor { get; }
    public int Attempts => (int)(Total / Attempt) - 1;
    public TimeSpan Sampling => 2 * Attempt;
    public int Permits => Floor * 2;
    public int Throughput => Floor / 2;
    public TimeSpan Break => Sampling / 2;
    public TimeSpan Backoff => Attempt / 20;
    public int Hedges => Math.Min(Attempts, 2);
    public TimeSpan HedgeDelay => Attempt / 4;
    public CircuitBreakerStrategyOptions<Reply> Breaker(
        PredicateBuilder<Reply> transient, CircuitBreakerManualControl? control = null, CircuitBreakerStateProvider? evidence = null) => new() {
        Name = "<health>", FailureRatio = Trip, MinimumThroughput = Throughput,
        SamplingDuration = Sampling, BreakDuration = Break, ShouldHandle = transient,
        ManualControl = control, StateProvider = evidence,
    };
}

public static class HopPipeline {
    static readonly PredicateBuilder<Reply> Transient =
        new PredicateBuilder<Reply>().Handle<TimeoutRejectedException>().HandleResult(static reply => reply.Faulted);

    public static ResiliencePipeline<Reply> Compose(AllotmentClass allotment, TimeProvider clock, ILoggerFactory telemetry) {
        ArgumentNullException.ThrowIfNull(allotment);
        return new ResiliencePipelineBuilder<Reply> { Name = allotment.Key, TimeProvider = clock }
            .ConfigureTelemetry(telemetry)
            .AddConcurrencyLimiter(permitLimit: allotment.Permits, queueLimit: 0)
            .AddTimeout(new TimeoutStrategyOptions { Name = "<total>", Timeout = allotment.Total })
            .AddRetry(new RetryStrategyOptions<Reply> {
                Name = "<retry>", MaxRetryAttempts = allotment.Attempts, BackoffType = DelayBackoffType.Exponential, UseJitter = true,
                Delay = allotment.Backoff, MaxDelay = allotment.Attempt, ShouldHandle = Transient,
            })
            .AddCircuitBreaker(allotment.Breaker(Transient))
            .AddTimeout(new TimeoutStrategyOptions { Name = "<attempt>", Timeout = allotment.Attempt })
            .Build();
    }
}
```

## [03]-[SEAM_EXECUTION]

[OUTCOME_FOLD]:
- Law: the seam executes outcome-first — `ExecuteOutcomeAsync` with typed state keeps the hot path closure-free, strategies see outcomes and never in-flight exceptions, and the capture kernel folds everything except process-fatal faults into the outcome.
- Law: the context lease is strict — `ResilienceContextPool.Shared.Get` at entry, `Return` on every exit, never retained — and `OperationKey` fixes at lease as the idempotency key's transport: it reaches every attempt and lands as `operation.key` on every telemetry event, so key, attempts, and evidence correlate by construction rather than by joins.
- Law: `ContinueOnCapturedContext` rides the lease — one capture policy per execution, consumed by every strategy await — and a pre-cancelled lease short-circuits to a cancelled outcome before any strategy runs.
- Law: the total-outcome fold happens exactly once, at the seam — every `Outcome<T>` folds to a success or one case of the closed `Rejection` `[Union]` deriving from `Expected`, so the seam's failure currency is the rail's own `Error` widening with no bridge, and a second fold at a caller re-opens the vocabulary the seam retired.
- Law: the typed arms close the known rejection verbs while `Rejection.Foreign(Error)` is the open-tail passthrough lifting any unclassified fault as the rail `Error` and `Rejection.Empty` the no-exception-no-result sentinel — closed verbs plus one passthrough is the same totality shape the graph law mints, so the fold drops no fault and the wire-exception taxonomy never leaks into the neutral owner; a new typed verb is one case ahead of `Foreign`, not a wider catch.
- Law: cancelled-versus-rejected is structural — a cancellation while the caller token fired is `Rejection.CallerLeft`, the caller's intent; a child deadline firing while the caller token did not converts to `TimeoutRejectedException` and folds to `Rejection.Deadline(slow.Timeout)` — so "the caller left" and "the attempt was too slow" are distinguishable by case, never by inspecting message text.
- Law: the rejected arm is a closed taxonomy ordered child-before-parent — `IsolatedCircuitException` before its `BrokenCircuitException` base, so operator-forced darkness folds to `Rejection.ForcedDark` and never masquerades as the dependency `Rejection.Open` — and each case binds its evidence as a typed field: `Deadline.Span`, `Open.RetryAfter`, `Shed.RetryAfter`, `ForcedDark.Pipeline` read from `TelemetrySource.PipelineName`, so escalation pattern-matches the case and reads the field, never re-parses the detail string the `Expected` base carries only for the wire.
- Law: `ResilienceProperties` is the typed side channel between caller and strategies — `ResiliencePropertyKey<TValue>` rows, string-keyed at the wire, typed at every access point — and the idempotency window rides it as the allotment span, fixed before the pipeline runs.
- Law: `ResiliencePipeline<T>` execution constrains `TResult : T` — one typed pipeline serves an entire result hierarchy, with subtype executions riding the same strategy state.
- Exemption: the outcome-capture kernel and the lease `try`/`finally` are the platform-forced statement seam.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Rejection : Expected {
    protected Rejection(string detail, int code) : base(detail, code, None) { }
    public sealed record CallerLeft() : Rejection("<caller-left>", 7501);
    public sealed record Deadline(TimeSpan Span) : Rejection($"<deadline:{Span}>", 7502);
    public sealed record ForcedDark(string? Pipeline) : Rejection($"<forced-dark:{Pipeline}>", 7503);
    public sealed record Open(TimeSpan? RetryAfter) : Rejection($"<open:{RetryAfter}>", 7504);
    public sealed record Shed(TimeSpan? RetryAfter) : Rejection($"<shed:{RetryAfter}>", 7505);
    public sealed record Foreign(Error Cause) : Rejection(Cause.Message, 7510);
    public sealed record Empty() : Rejection("<empty>", 7500);
}

public static class HopSeam {
    public static readonly ResiliencePropertyKey<TimeSpan> Window = new("<window>");

    public static async Task<Fin<Reply>> Send(
        ResiliencePipeline<Reply> pipeline, AllotmentClass allotment, string operationKey,
        Func<CancellationToken, ValueTask<Reply>> hop, CancellationToken caller) {
        ArgumentNullException.ThrowIfNull(pipeline);
        ArgumentNullException.ThrowIfNull(allotment);
        var context = ResilienceContextPool.Shared.Get(operationKey, caller);
        context.Properties.Set(Window, allotment.Total);
        try {
            var outcome = await pipeline.ExecuteOutcomeAsync(
                static async (ctx, state) => {
                    try { return Outcome.FromResult(await state(ctx.CancellationToken).ConfigureAwait(false)); }
                    catch (Exception ex) when (ex is not OutOfMemoryException) { return Outcome.FromException<Reply>(ex); }
                },
                context, hop).ConfigureAwait(false);
            return Fold(outcome, caller);
        }
        finally { ResilienceContextPool.Shared.Return(context); }
    }

    static Fin<Reply> Fold(Outcome<Reply> outcome, CancellationToken caller) => outcome switch {
        { Exception: null, Result: { } reply } => Fin.Succ(reply),
        { Exception: OperationCanceledException } when caller.IsCancellationRequested => Fin.Fail<Reply>(new Rejection.CallerLeft()),
        { Exception: TimeoutRejectedException slow } => Fin.Fail<Reply>(new Rejection.Deadline(slow.Timeout)),
        { Exception: IsolatedCircuitException dark } => Fin.Fail<Reply>(new Rejection.ForcedDark(dark.TelemetrySource?.PipelineName)),
        { Exception: BrokenCircuitException open } => Fin.Fail<Reply>(new Rejection.Open(open.RetryAfter)),
        { Exception: RateLimiterRejectedException shed } => Fin.Fail<Reply>(new Rejection.Shed(shed.RetryAfter)),
        { Exception: { } foreign } => Fin.Fail<Reply>(new Rejection.Foreign(Error.New(foreign))),
        _ => Fin.Fail<Reply>(new Rejection.Empty()),
    };
}
```

## [04]-[HOP_TOPOLOGY]

[ONE_OWNER]:
- Law: exactly one retry owner exists per outbound hop, held at the composition root as one registry row keyed by normalized hop identity — the law is outbound-only, inbound admission is never a hop — and a pipeline built directly inside a seam escapes the claim cell, the conflict detection, and the disposal fence at once.
- Law: claim identity is the hop, not the policy and not the instance — per-authority instances are one owner with N isolated states, never a second owner, and un-normalized identity splinters one hop into fragments that each look singly owned and under-detect conflicts.
- Law: the hop row is one closed record and every law on this page is a column — key with two formatted axes, `nameof`-derived owner symbol, allotment class, two idempotency columns, policy reference, override group, routes — so a new hop is one row and a new resilience law is one column, never a new surface; the row set is the process's queryable resilience topology.
- Law: `TryAddBuilder` returns the claim verdict synchronously — a false verdict degrades the loser to the incumbent pipeline, single pass through full protection and never reduced coverage, and projects one conflict receipt carrying both declaration symbols and the discarded policy, the only place the losing policy survives for repair comparison.
- Law: a second claim never fails boot and is never silent — the duplicate declaration is latent attempt multiplication waiting for a configuration change, and receipts make fleet consolidation rankable by multiplication severity.
- Law: generic and non-generic pipelines are disjoint namespaces per result type — a hop registered generically and resolved non-generically misses silently — so the row fixes the result type at registration and resolution shape cannot drift.
- Law: registry disposal is the composition fence — every materialized pipeline force-disposes, stale references throw, and a rebuilt root re-derives rows from configuration; `OnPipelineDisposed` is the reclaim hook declared beside the claim at the row, and breaker statistics and limiter queues are process-local by construction, intentionally unrecoverable.
- Law: mid-life policy change is per-row reload — `AddReloadToken` rebuilds one hop's pipeline in place, in-flight executions finish on the old generation, and the discarded component disposes in the background after a bounded drain, so an execution outliving that bound races its own component's disposal.
- Law: a throwing reload keeps the old component and emits a reload-failure succession receipt — a configuration error degrades to the last good pipeline, never an unguarded seam — and reload versus root rebuild are distinguishable kind cases under a per-row generation counter, conflict and succession riding one kind-discriminated topology fact stream rather than parallel receipt types.
- Law: one registry exists per key type per container — the key type partitions the resilience namespace, so a process standardizes on one key shape or its claims fragment across invisible registries.
- Law: `AddResiliencePipeline` registers the keyed-service projection, the registry/provider pair, and container-wired telemetry at once, and `AddResiliencePipelines` defers key enumeration to startup so a configuration-derived hop set is one callback; a container `TimeProvider` flows into every registry pipeline while a base-builder `ContextPool` does not — pool policy re-applies where the typed builder is configured.
- Exemption: the registry configure body — reload token, dispose reclaim, builder mutation — is the platform-forced statement seam.

[LAYER_SPLIT]:

The retry-owner table is a decision procedure; rows overlap and first match wins.

| [INDEX] | [SEAM_FACT]                         | [RETRY_OWNER]                        |
| :-----: | :---------------------------------- | :----------------------------------- |
|  [01]   | callee owns transactional semantics | store execution strategy             |
|  [02]   | call crosses a process seam         | hop pipeline at the root             |
|  [03]   | typed fault on rails, in-process    | `Schedule` policy on the effect rail |

- Law: the split is exclusive per seam — schedule m × pipeline n multiplies attempts invisibly and inflates the idempotency window by m, and each layer is locally correct, so only seam exclusivity catches the stack; ambiguity after both questions means the seam is mis-factored, never that the table needs a fourth row.
- Law: pipeline predicates speak the wire's vocabulary — routing domain values through exceptions so a pipeline can retry them inverts the fault architecture; a pipeline around store work replays from the wrong boundary, the one misclassification that corrupts data, so the audit order is stores, then wire seams, then rails.
- Law: a durable handoff has no retry owner — persisted intent is the resilience, and retry above it duplicates enqueued work; readiness polling is schedule-driven convergence, not retry; each fan-out leg keeps its own owner and the aggregate gets no umbrella loop; a capsule that crosses a wire internally owns the hop at its own seam — ownership follows the seam, never the call stack.
- Law: ambient retry — interceptors, base-class hooks, middleware over all calls — has no hop identity and therefore no claim row; it is dismantled into one of the three layers before any other resilience work proceeds.
- Law: a hop owns one allotment — total and attempt spans co-validated as a named class, the attempt deadline a linked child of the total, single-pass rows collapsing the class to one span — and allotments inherit through nested seams as the minimum of the child's class and the inherited remainder; a break consumes allotment while rejecting fast, never pausing it.
- Law: the idempotency window equals the allotment — key lifetime derives from it and from no backoff parameter, the key mints above the owner and fixes in the context before the pipeline runs, because a key minted inside the retried callback changes per attempt and defeats itself; hedging widens the window to overlapping duplicates in flight.
- Boundary: transport seams compose these pipelines into their handler chains; wire contracts and handler mechanics are transport law.

```csharp conceptual
public sealed record HopKey(string Hop, string Instance);

public sealed record RouteWeight(Uri Endpoint, int Weight);

public sealed record HopRow(
    HopKey Key, string Owner, AllotmentClass Allotment, bool Idempotent, bool Replayable,
    string PolicyRef, string Group, Seq<RouteWeight> Routes);

public readonly record struct ClaimFact(string Hop, string Incumbent, string Loser, string DiscardedPolicy);

public sealed class HopTopology {
    readonly ResiliencePipelineRegistry<HopKey> registry = new(new ResiliencePipelineRegistryOptions<HopKey> {
        BuilderNameFormatter = static key => key.Hop,
        InstanceNameFormatter = static key => key.Instance,
    });
    readonly Atom<HashMap<HopKey, HopRow>> rows = Atom(HashMap<HopKey, HopRow>());

    public Atom<Seq<ClaimFact>> Conflicts { get; } = Atom(Seq<ClaimFact>());

    public Seq<HopRow> Topology => toSeq(rows.Value.Values);

    public Seq<ResiliencePipeline<Reply>> Materialize(
        Seq<HopRow> table, Func<HopRow, CancellationToken> reload, Action<ResiliencePipelineBuilder<Reply>, HopRow> policy) =>
        table.Map(row => Claim(row, reload, policy)).Strict();

    public ResiliencePipeline<Reply> Claim(HopRow row, Func<HopRow, CancellationToken> reload, Action<ResiliencePipelineBuilder<Reply>, HopRow> policy) {
        ArgumentNullException.ThrowIfNull(row);
        return registry.TryAddBuilder<Reply>(row.Key, (builder, context) => {
                context.AddReloadToken(reload(row));
                context.OnPipelineDisposed(() => ignore(rows.Swap(held => held.Remove(row.Key))));
                policy(builder, row);
            })
            ? (rows.Swap(held => held.TryAdd(row.Key, row)), Resolved(row.Key)).Item2
            : Conceded(row);
    }

    ResiliencePipeline<Reply> Resolved(HopKey key) =>
        registry.TryGetPipeline<Reply>(key, out var pipeline) ? pipeline : ResiliencePipeline<Reply>.Empty;

    ResiliencePipeline<Reply> Conceded(HopRow row) =>
        (Conflicts.Swap(facts => facts.Add(new ClaimFact(
            row.Key.Hop,
            rows.Value.Find(row.Key).Map(static held => held.Owner).IfNone("<unrowed>"),
            row.Owner,
            row.PolicyRef))),
         Resolved(row.Key)).Item2;
}
```

## [05]-[HTTP_SEAMS]

[STANDARD_POSTURE]:
- Law: `AddStandardResilienceHandler` composes exactly five strategies — rate limiter, total timeout, retry, circuit breaker, attempt timeout — from one `HttpStandardResilienceOptions` record bound to `"{clientName}-standard"`, reloadable and validated as a unit; configuration keys mirror the property names under strict binding, so the config schema is the options shape, never a parallel vocabulary.
- Law: the handler deletes the client's own deadline — `HttpClient.Timeout` becomes infinite so the pipeline is the seam's only deadline owner; restoring a finite client timeout creates a second untyped deadline that surfaces as bare cancellation instead of typed rejection.
- Law: cross-field coherence fails boot, not first request — attempt ≤ total, breaker sampling ≥ 2× attempt, the cumulative hedging plan inside its own budget — and per-name validation names the misconfigured client.
- Law: hardening is per-slot — swap the retry predicate, retune the breaker, point the limiter at a shared instance — and the chain order itself is not an options value: a different order is a custom `AddResilienceHandler` declaration that must re-satisfy the same validators.
- Law: the transient set is closed — 408, 429, status ≥ 500, `HttpRequestException`, `TimeoutRejectedException` — and a connect timeout classifies by structure, a core-runtime cancellation with an inner `TimeoutException` while the caller token has not fired; custom pipelines reuse `HttpClientResiliencePredicates.IsTransient`, one transient definition per process.
- Law: `ShouldRetryAfterHeader` installs the retry-after delay generator; a custom `DelayGenerator` silently replaces it, so keeping both means composing the header parse inside the custom generator.
- Law: handler-chain position decides per-attempt versus per-call — handlers registered after the resilience handler run once per attempt — and at most one resilience handler sits on one client seam, because two stack multiplicatively, `RemoveAllResilienceHandlers` then one declaration being the repair; the method filters `DisableForUnsafeHttpMethods` and `DisableFor` decorate the transient predicate under the one centrally pinned experimental acknowledgment.
- Law: `Configure(IConfigurationSection)` binds with unknown-key errors and rejects an empty section as a wiring defect; the hedging family binds its options under the client name itself with no suffix, so section paths are not portable between the two handler families.
- Law: the request and the context bridge bidirectionally under stable keys — `GetResilienceContext`/`SetResilienceContext` on the request, `GetRequestMessage`/`SetRequestMessage` on the context — and a pre-attached context is the sanctioned channel for threading caller properties through the seam and reading strategy-written properties afterward.

[SELECTION_AND_HEDGING]:
- Law: `SelectPipelineByAuthority` keys one pipeline instance per scheme, host, and port — N isolated breaker, limiter, and deadline states from one declaration, materialized lazily per instance with zero added registrations; keys compare ordinally, the authority provider requires an absolute request URI, and selector output becomes the `pipeline.instance` telemetry dimension, so a selector never projects secrets or unbounded cardinality.
- Law: the selector is touched eagerly at handler construction with a synthetic request, so a throwing selector fails at wiring time; the provider runs before context attachment, so instance selection depends only on the request — and registering any resilience handler installs the global HTTP metrics enricher stamping `error.type` with the status code, so status-class dashboards come from metric tags, not response logging.
- Law: hedging is concurrent duplication, strictly stronger than retry — admitted only where both row columns hold, semantic idempotency and body replayability; either column alone admits only retry, and the hedged/unhedged split happens at client registration, never inside one pipeline.
- Law: `AddStandardHedgingHandler` builds two chained pipelines — routing, request snapshot, total timeout, hedging above; rate limiter, circuit breaker, attempt timeout per endpoint below — and no retry slot exists below hedging: the options shape forecloses a second attempt loop, and both pipelines reload from one options name, never half.
- Law: the per-endpoint breaker pool is the hedging family's health memory — an open breaker is hedging-transient, fast-fail then route to the next endpoint, but not retry-transient, which would spend budget on the same dead endpoint; the same fault classifies differently because the remedies differ.
- Law: the total deadline sits above hedging, so one budget expiry cancels every concurrent attempt at once and losers cancel when a winner lands; routing and snapshotting run outside the budget — route resolution and clone cost are setup, never allotment spend.
- Law: the snapshot rejects stream bodies at construction and shares content across clones — hedged attempts must tolerate concurrent reads; route exhaustion stops hedging, ordered groups walk declaration order, weighted groups draw by weight, a tried group is never offered twice within one logical call, and route-table edits ride the options monitor onto new calls with no pipeline rebuild.
- Law: `WeightedGroupSelectionMode.EveryAttempt` draws every group by weight while `InitialAttempt` draws only the first and walks the rest in declaration order — load-spread versus primary-with-failover from one enum value; the `ActionGenerator` slot is handler-owned and overwrites user assignment, so custom action generation is a custom handler declaration.
- Exemption: the handler registration and options-mutation bodies are the platform-forced statement seam.

```csharp conceptual
public static class WireSeam {
    public static IServiceCollection Compose(IServiceCollection services, Seq<HopRow> topology) =>
        topology.Fold(services, static (svc, row) => row.Idempotent && row.Replayable ? Hedged(svc, row) : Standard(svc, row));

    static IServiceCollection Standard(IServiceCollection services, HopRow row) {
        _ = services.AddHttpClient(row.Key.Hop)
            .AddStandardResilienceHandler(options => {
                options.TotalRequestTimeout.Timeout = row.Allotment.Total;
                options.AttemptTimeout.Timeout = row.Allotment.Attempt;
                options.Retry.MaxRetryAttempts = row.Allotment.Attempts;
                options.CircuitBreaker.SamplingDuration = row.Allotment.Sampling;
            })
            .SelectPipelineByAuthority();
        return services;
    }

    static IServiceCollection Hedged(IServiceCollection services, HopRow row) {
        _ = services.AddHttpClient(row.Key.Hop)
            .AddStandardHedgingHandler(routing => routing.ConfigureWeightedGroups(groups => {
                groups.SelectionMode = row.Routes.Count > 1 ? WeightedGroupSelectionMode.EveryAttempt : WeightedGroupSelectionMode.InitialAttempt;
                row.Routes.Iter(route => groups.Groups.Add(new WeightedUriEndpointGroup {
                    Weight = route.Weight, Endpoints = { new WeightedUriEndpoint { Uri = route.Endpoint, Weight = route.Weight } },
                }));
            }))
            .Configure(options => {
                options.TotalRequestTimeout.Timeout = row.Allotment.Total;
                options.Hedging.MaxHedgedAttempts = row.Allotment.Hedges;
                options.Hedging.Delay = row.Allotment.HedgeDelay;
                options.Endpoint.Timeout.Timeout = row.Allotment.Attempt;
            });
        return services;
    }
}
```

## [06]-[OVERRIDE_CONTROL]

[DARK_CONTROL]:
- Law: forced darkness is one `CircuitBreakerManualControl` registered across every breaker in a capability group — isolate and close act on the set as one verb, and `isIsolated: true` at construction boots the group dark, so a degraded boot never serves a single undegraded call.
- Law: isolate is sticky until close, and close resets statistics — release re-derives health from live evidence, never restores the pre-force state; a restore-previous override surface resurrects decisions whose evidence has expired and is the rejected form.
- Law: a pinned control re-applies isolation to every breaker that registers while it is pinned — the override survives pipeline reloads and lazy instance materialization structurally, because the control instance lives outside pipeline generations.
- Law: both verbs are idempotent — re-forcing a pinned set and releasing an unpinned one are no-ops, so operator receipts deduplicate and repeated commands cannot stack.
- Law: `IsolatedCircuitException` derives from `BrokenCircuitException` and stays distinguishable by type — one catch arm covers organic and operator-forced opens while receipts attribute darkness to the operator, never the dependency.
- Law: `CircuitBreakerStateProvider` is single-attach — one provider per breaker, and a second pipeline reusing it throws at build — so health evidence reads are per-seat values by construction.
- Boundary: the capability-level fold consuming these seats — rank derivation, hysteresis, retained-capability sets — is runtime law; this page owns the breaker-set evidence and the force/release anchor it binds to.

```csharp conceptual
public sealed record DarkGroup(string Name, CircuitBreakerManualControl Control) {
    public static DarkGroup Boot(string name, bool dark) => new(name, new CircuitBreakerManualControl(isIsolated: dark));
    public Task Force() => Control.IsolateAsync();
    public Task Release() => Control.CloseAsync();
}

public sealed record BreakerSeat(CircuitBreakerStateProvider Evidence) {
    public bool Dark => Evidence.CircuitState is CircuitState.Isolated;
    public bool Refusing => Evidence.CircuitState is CircuitState.Open or CircuitState.Isolated;
}

public static class GroupBinding {
    static readonly PredicateBuilder<Reply> Transient =
        new PredicateBuilder<Reply>().Handle<TimeoutRejectedException>().HandleResult(static reply => reply.Faulted);

    public static Seq<(HopKey Key, ResiliencePipeline<Reply> Pipeline, BreakerSeat Seat)> Bind(
        DarkGroup group, Seq<HopRow> members, TimeProvider clock) =>
        members.Map(static row => (Row: row, Seat: new BreakerSeat(new CircuitBreakerStateProvider())))
            .Map(slot => (slot.Row.Key,
                new ResiliencePipelineBuilder<Reply> { Name = slot.Row.Key.Hop, TimeProvider = clock }
                    .AddCircuitBreaker(slot.Row.Allotment.Breaker(Transient, group.Control, slot.Seat.Evidence)).Build(),
                slot.Seat))
            .Strict();
}
```

## [07]-[CHAOS]

[INJECTION_LAW]:
- Law: four chaos strategies admit through the same builder grammar and partition the failure planes — fault injects the exception rail, outcome substitutes the result rail without invoking the callback, latency spends the time plane, behavior runs a side effect before the call — one concern per declaration, ordered like any strategy, with outcome injection a generic-builder surface because substitution needs the result type.
- Law: chaos sits below the strategies under test — injection above a breaker proves nothing because the breaker never observes it; the canonical arrangement is resilience chain, then chaos block, then the real callback.
- Law: the injection gate is a per-execution conjunction — the enabled decision, then the rate draw against the `Randomizer` — and generator presence makes the scalar ignored, so targeting one tenant, one environment, or one fraction is a generator row, never a build-time fork.
- Law: one process kill cell gates every chaos strategy and one posture record carries the rates — both stamped onto every chaos options row by one parameterized configurator — so the entire chaos posture is a runtime-operable dial that swaps as one value, never a deployment artifact.
- Law: fault mixes are weighted catalogues — `FaultGenerator` and `OutcomeGenerator<T>` rows convertible to the options delegate — so a realistic mix is declared as weights, not branching, and a null generator return skips injection for that execution, the per-execution opt-out channel.
- Law: latency chaos delays through the builder's `TimeProvider` — deterministic under a fake clock — and observes cancellation before invoking the real callback, so injected latency surfaces as a cancelled outcome, never a hang.
- Law: chaos events ride the same instruments and tag vocabulary as resilience events — injected-versus-organic ratios derive from `event.name` partitions with zero extra instrumentation, and drift between declared and observed injection rate detects chaos placed above short-circuiting strategies.

```csharp conceptual
public sealed record ChaosPosture(bool Enabled, double Rate) {
    public static readonly Atom<ChaosPosture> Cell = Atom(new ChaosPosture(Enabled: false, Rate: 0.02));
    public static readonly Atom<int> Injected = Atom(0);
}

public static class ChaosBlock {
    static TOptions Governed<TOptions>(TOptions chaos) where TOptions : ChaosStrategyOptions =>
        (chaos.EnabledGenerator = static _ => ValueTask.FromResult(ChaosPosture.Cell.Value.Enabled),
         chaos.InjectionRateGenerator = static _ => ValueTask.FromResult(ChaosPosture.Cell.Value.Rate),
         chaos).Item3;

    public static ResiliencePipelineBuilder<Reply> Inject(ResiliencePipelineBuilder<Reply> guarded) =>
        guarded
            .AddChaosLatency(Governed(new ChaosLatencyStrategyOptions { Latency = TimeSpan.FromSeconds(2) }))
            .AddChaosFault(Governed(new ChaosFaultStrategyOptions {
                FaultGenerator = new FaultGenerator()
                    .AddException<TimeoutException>(weight: 70)
                    .AddException(static () => new HttpRequestException("<injected>"), weight: 30),
            }))
            .AddChaosOutcome(Governed(new ChaosOutcomeStrategyOptions<Reply> {
                OutcomeGenerator = new OutcomeGenerator<Reply>().AddResult(static () => new Reply(Faulted: true)),
            }))
            .AddChaosBehavior(Governed(new ChaosBehaviorStrategyOptions {
                BehaviorGenerator = static _ => (ChaosPosture.Injected.Swap(static n => n + 1), ValueTask.CompletedTask).Item2,
            }));
}
```
