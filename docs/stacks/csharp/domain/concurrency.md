# [CONCURRENCY]

Throughput is one declared posture. Every producer in the process flows through a closed lane vocabulary — a channel row with declared capacity, full-mode backpressure, drop receipts, and a drain band — and every loss is receipted into one kind-tagged stream, so written = consumed + receipted loss closes from declarations alone with drop eviction and drain residue as kinds on that one stream; unreceipted loss is a rail rejection. One frozen budget record owns every degree, permit, capacity, and window and proves its own cross-axis inequalities at admission. Pacing is limiter policy rows whose verdicts carry typed evidence; identical concurrent intents collapse into one keyed flight; push streams admit only where time or combination algebra earns them and deliver through declared cadence edges; live collection state travels only as change-sets off two sources. Growth lands as rows: a new producer is a lane row, a new pacing class a limiter row, a new invalidation one resolution row, a rebalance one budget edit.

## [01]-[CONCURRENCY_CHOOSER]

This table routes a throughput concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                     | [OWNER]                                | [REJECTED_FORM]                 |
| :-----: | :---------------------------- | :------------------------------------- | :------------------------------ |
|  [01]   | producer hand-off             | lane row from the closed table         | inline channel options per site |
|  [02]   | async parallel consumption    | `Parallel.ForEachAsync` over a lane    | task spawn per item             |
|  [03]   | cpu associative aggregate     | total-spelling PLINQ                   | bare `AsParallel()`             |
|  [04]   | outbound pacing and admission | limiter row + typed verdict            | semaphore gate                  |
|  [05]   | identical concurrent intents  | keyed single-flight cell               | duplicate spend                 |
|  [06]   | time or combination logic     | one declared observable chain          | event-handler mesh              |
|  [07]   | cadence-bound delivery        | delivery-edge triple                   | raw push to a slow observer     |
|  [08]   | live collection state         | source + one change-set chain          | snapshot re-query               |
|  [09]   | global invalidation           | one of five resolution rows            | per-consumer root subscriptions |
|  [10]   | cross-process exclusivity     | heartbeat lease + staleness inequality | read-then-write claim           |
|  [11]   | shutdown loss accounting      | two-phase participation + `DrainFact`  | unreceipted teardown            |

## [02]-[CHANNEL_LANES]

[LANE_ROWS]:
- Law: a lane is one `[SmartEnum<string>]` row whose wire key is the lane name and whose columns carry capacity, full-mode, prioritization, reader arity, continuation inlining, and drain band — one vocabulary per process, producers dispatch the polymorphic `Open<T>` on the row, and inline `BoundedChannelOptions` at a call site makes the backpressure decision unrecoverable from declarations and forfeits the `Items` inventory the conservation audit walks.
- Law: six rows close the vocabulary; a producer fitting no row is a missing item, never a bespoke channel, and `LaneRow.Get(name)` admits an external lane selector through the one key seam.
- Law: the loss column is `Option<LossClass>` set by full-mode at declaration — the three drop modes carry their class, `Wait` and the rendezvous row carry `None`, so a `Wait` lane never manufactures a refused-write receipt and `Open<T>` selects the callback-bearing `CreateBounded` overload only where a loss class exists.
- Law: every bounded-lane operation serializes on one internal monitor, so the throughput ceiling is lock hand-off rate — a hot lane shards into budget-derived key-hash lanes, and widening capacity raises burst absorption, never throughput and never latency, because an empty-buffer write hands off directly to a parked reader.
- Law: capacity 0 is the rendezvous row — no buffer exists, a write completes only when a read consumed it, and timing-dependent hand-off assertions become sequential ones.
- Law: `SingleReader` on an unbounded lane selects the pooled single-consumer implementation and forfeits `Count` (`CanCount` is `false`); `SingleWriter` is consumed by nothing, and the prioritized row ignores both arity flags but reports `CanCount`/`CanPeek` true because its `PriorityQueue<bool,T>` backing is internally serialized regardless.
- Law: the prioritized backing is `PriorityQueue<bool,T>` keyed on the element itself, so `T` is the priority and `Comparer` is `IComparer<T>` over `T`; prioritization changes the element contract, so the prioritized row mints through `OpenRanked<T> where T : IRankedItem` while the value rows mint through `Open<T> where T : notnull`, the element-type contract the modality discriminant rather than a flag the body re-reads. `OpenRanked` wires `Comparer = Ranked.ByRankThenSequence<T>()` over a `[ComplexValueObject]` envelope carrying class rank plus a write-time sequence so equal-class items dequeue in arrival order; an unwired `Comparer` falls to `Comparer<T>.Default`, which throws for a non-comparable envelope, so the comparand is mandatory, never decorative, and the sequence is minted at admission, never the raw class rank alone.
- Law: `AllowSynchronousContinuations` runs the parked side's continuation on the completing thread — admissible only on same-affinity hot paths whose consumer neither marshals, takes locks, nor re-enters the producer.
- Law: declaring a single-reader row and materializing exactly one consumer loop makes exclusivity structural — the vocabulary is also an ownership table naming each row's one consumer.

| [INDEX] | [ROW]        | [SHAPE]                                   | [DELETES]                      |
| :-----: | :----------- | :---------------------------------------- | :----------------------------- |
|  [01]   | mailbox      | capacity 1, `DropOldest`                  | hand-rolled latest-value locks |
|  [02]   | ordered-work | bounded, `Wait`, single consumer          | semaphore-plus-queue pairs     |
|  [03]   | handshake    | capacity 0, `Wait`                        | completion-source ping-pong    |
|  [04]   | shed-ingest  | bounded, `DropWrite`                      | try-lock admission scatter     |
|  [05]   | control      | prioritized, `(priority, sequence)` order | parallel urgent/normal queues  |
|  [06]   | firehose     | unbounded, single reader                  | fire-and-forget task per event |

```csharp conceptual
[SmartEnum]
public sealed partial class LossClass {
    public static readonly LossClass EvictedOldest = new();
    public static readonly LossClass EvictedNewest = new();
    public static readonly LossClass RefusedWrite = new();
    public static readonly LossClass DrainResidue = new();
}

public readonly record struct LaneLoss(LaneRow Lane, LossClass Class);

[SmartEnum<string>]
public sealed partial class LaneRow {
    public static readonly LaneRow Mailbox = new("<lane-a>", Some(1), BoundedChannelFullMode.DropOldest, prioritized: false, single: true, inline: false, band: 2);
    public static readonly LaneRow Ordered = new("<lane-b>", Some(32), BoundedChannelFullMode.Wait, prioritized: false, single: true, inline: false, band: 1);
    public static readonly LaneRow Handshake = new("<lane-c>", Some(0), BoundedChannelFullMode.Wait, prioritized: false, single: true, inline: true, band: 0);
    public static readonly LaneRow Shed = new("<lane-d>", Some(64), BoundedChannelFullMode.DropWrite, prioritized: false, single: false, inline: false, band: 1);
    public static readonly LaneRow Control = new("<lane-e>", None, BoundedChannelFullMode.Wait, prioritized: true, single: false, inline: false, band: 0);
    public static readonly LaneRow Firehose = new("<lane-f>", None, BoundedChannelFullMode.Wait, prioritized: false, single: true, inline: false, band: 3);

    public Option<int> Capacity { get; }
    public BoundedChannelFullMode Mode { get; }
    public bool Prioritized { get; }
    public bool Single { get; }
    public bool Inline { get; }
    public int Band { get; }

    public Option<LossClass> Loss => Mode switch {
        BoundedChannelFullMode.DropOldest => LossClass.EvictedOldest,
        BoundedChannelFullMode.DropNewest => LossClass.EvictedNewest,
        BoundedChannelFullMode.DropWrite => LossClass.RefusedWrite,
        _ => Option<LossClass>.None,
    };

    public Channel<T> Open<T>(Atom<Seq<LaneLoss>> receipts) where T : notnull =>
        (Prioritized, Capacity, Loss) switch {
            (true, _, _) => throw new InvalidOperationException($"<prioritized-row-needs-OpenRanked:{Key}>"),
            (_, { IsSome: true, Case: int cap }, { IsSome: true, Case: LossClass cls }) => Channel.CreateBounded<T>(
                new BoundedChannelOptions(cap) { FullMode = Mode, SingleReader = Single, AllowSynchronousContinuations = Inline },
                _ => ignore(receipts.Swap(f => f.Add(new LaneLoss(this, cls))))),
            (_, { IsSome: true, Case: int cap }, _) => Channel.CreateBounded<T>(
                new BoundedChannelOptions(cap) { FullMode = Mode, SingleReader = Single, AllowSynchronousContinuations = Inline }),
            _ => Channel.CreateUnbounded<T>(new UnboundedChannelOptions { SingleReader = Single }),
        };

    public Channel<T> OpenRanked<T>() where T : IRankedItem =>
        Prioritized
            ? Channel.CreateUnboundedPrioritized(new UnboundedPrioritizedChannelOptions<T> { Comparer = Ranked.ByRankThenSequence<T>() })
            : throw new InvalidOperationException($"<non-prioritized-row-uses-Open:{Key}>");
}

public interface IRankedItem {
    int Rank { get; }
    long Sequence { get; }
}

public static class Ranked {
    public static IComparer<T> ByRankThenSequence<T>() where T : IRankedItem =>
        Comparer<T>.Create(static (l, r) => (l.Rank, l.Sequence).CompareTo((r.Rank, r.Sequence)));
}
```

[LANE_EVIDENCE]:
- Law: under the three drop modes `TryWrite` returns `true` on a live channel and `WaitToWriteAsync` is immediately `true` — drop modes structurally delete writer-side backpressure, so write success is not delivery evidence and the receipt is the only loss evidence; a drop lane without `itemDropped` is unreceipted loss.
- Law: `DropNewest` evicts the most recently buffered item, never the incoming one; the `itemDropped` callback runs synchronously on the writing thread outside the channel lock — fold it into a fact stream and never log, allocate heavily, or block inside it.
- Law: loss reasons are disjoint classes — evicted-oldest measures conflation lag, refused-write measures shed load — and one merged counter destroys the only signal separating consumer-slow from producer-hot; receipts key on the row's vocabulary symbol, never the channel instance, so they survive lane re-creation and aggregate across shards.
- Law: `Wait` rows put pressure evidence on the writer instead — stamped `WriteAsync` await durations and park counts; drop-mode `TryWrite` never allocates while a parked `Wait` write allocates per park, so shed lanes are allocation-free under overload by construction.
- Law: depth evidence is a sampled gauge where `CanCount` holds — the base reader defaults `CanCount`/`CanPeek` to `false` and `Completion` to a never-completing task, so generic lane instrumentation probes capability, never assumes it; write-path evidence is the receipt stream, read-path evidence the sampled gauge, and the two cadences never share an instrument.
- Law: completion splits by verb — `TryComplete(error)` is first-call-wins idempotent shutdown whose coded fault rethrows as the `ChannelClosedException` inner from residue reads; loops key on `WaitToReadAsync` folding clean completion to `false`, single reads accept the throw, and a writer that must not throw on shutdown polls `WaitToWriteAsync` and folds `false` to its own stop signal.
- Law: a dedicated consumer loop passes the default token on its read verbs and shuts down via completion — a cancelable token forfeits the pooled parked-operation fast path on every wait, and `ReadAllAsync` greedily drains between waits so cancellation lands only at the empty-buffer edge.
- Law: N workers on one shared lane distribute items by race with no per-worker fairness — a workload requiring per-consumer fairness shards into per-consumer lanes instead of fighting the race.

[BLOCK_ADMISSION]:
- Law: a dataflow block earns admission over a lane on exactly four capabilities — `LinkTo` with `PropagateCompletion` topology completion, `BatchBlock` grouping with `TriggerBatch` and non-greedy two-phase reservation, `BroadcastBlock` latest-value for N consumers (one consumer is the mailbox row, and a null cloning function shares references across consumers, silently reintroducing aliasing), and `TransformBlock` ordered parallel transform under `MaxDegreeOfParallelism` plus `EnsureOrdered`.
- Law: a bounded propagator's output is linked or pulled before the first `SendAsync` — bounded transform, undrained output, parked producer is the canonical zero-fault wedge, because the one bound covers input and output together; `LinkTo` without `PropagateCompletion` never completes downstream.
- Law: a faulted block discards its buffered input — loss without receipts — so residue extracts via `TryReceiveAll` before `Fault`, and the leaf's `Completion` fault folds into the receipt rail as attributed loss.
- Law: one offer verb per row — `Post` is the `TryWrite` analog, `SendAsync` parks one postponed message — and mixing them mixes two backpressure regimes on one hop; non-greedy reservation is the family's only multi-source atomic take, so hand-rolled cross-lane atomic consumption marks a missing join row.
- Law: `DataflowBlock.NullTarget<T>()` is the declared absorb row — receiptless discard admitted only behind a predicate-guarded `LinkTo`, so discard is a routing decision, never a default; `Encapsulate(target, source)` folds a multi-block segment into one propagator presentable as one row with one ingress and one egress.
- Reject: `BufferBlock` — a lane row is denser; `WriteOnceBlock` — a single-assignment cell owns publish-once; standalone `ActionBlock` — lane plus reader loop separates buffering policy from execution policy and keeps drain receipted.

## [03]-[PARALLELISM_BUDGET]

[BUDGET_RECORD]:
- Law: one frozen budget record owns every concurrency axis — cpu workers, io degree, partitions, permits, lane capacities, batch size, drain budgets, heartbeat, staleness — and every degree, permit, capacity, and window in the process derives arithmetically from it; a literal degree at a call site makes the posture unrebalanceable without a code hunt.
- Law: the record proves its own inequalities at admission — lane capacity ≥ workers × batch or hand-off starves; permits ≥ workers wherever permits gate lane writes or the limiter silently sets the real degree; partitions ≥ workers or the surplus idles; staleness > soft + hard + heartbeat, plus a skew bound across hosts, or a draining-but-alive lease owner is stealable.
- Law: platform defaults are pinned, never inherited — `Parallel.ForEachAsync` defaults to `Environment.ProcessorCount` (a negative degree means default, never unbounded) and PLINQ defaults to `min(ProcessorCount, 512)` under a hard 512 cap, so two unconfigured subsystems are 2x oversubscription no declaration shows.
- Law: each hop owns exactly one waiting room — a limiter queue in front of a bounded lane is two buffers with two policies whose pressure evidence splits; the record assigns one waiting axis per hop and zeroes the other.
- Law: cpu and io degrees never share one number — cpu is sized by local cores, io by the remote system's capacity, and collapsing them couples a remote slowdown to local starvation.
- Law: the budget is observable and the loop closes — limiter statistics and lane receipts fold into periodic budget evidence, sustained queue growth over a window is the undersized-axis signal, and rebalancing is one record edit with zero call-site edits; a budget without its evidence fold is set once and wrong forever.

```csharp conceptual
public sealed record Budget(
    int Workers, int IoDegree, int Partitions, int Permits, int LaneCapacity, int Batch,
    TimeSpan Soft, TimeSpan Hard, TimeSpan Heartbeat, TimeSpan Skew, TimeSpan Staleness) {
    public Validation<Error, Budget> Proven =>
        (Rule(LaneCapacity >= Workers * Batch, "<law-handoff>"),
         Rule(Permits >= Workers, "<law-permits>"),
         Rule(Partitions >= Workers, "<law-partitions>"),
         Rule(Staleness > Soft + Hard + Heartbeat + Skew, "<law-lease>"))
        .Apply((_, _, _, _) => this).As();

    public ParallelOptions Cpu(CancellationToken token) => new() { MaxDegreeOfParallelism = Workers, CancellationToken = token };
    public ParallelOptions Io(CancellationToken token) => new() { MaxDegreeOfParallelism = IoDegree, CancellationToken = token };

    static Validation<Error, Unit> Rule(bool holds, string law) => holds ? unit : Error.New(law);
}

public static class Budgeted {
    public static Task Consume<T>(ChannelReader<T> lane, Budget budget, Func<T, CancellationToken, ValueTask> step, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(lane);
        ArgumentNullException.ThrowIfNull(budget);
        return Parallel.ForEachAsync(lane.ReadAllAsync(token), budget.Io(token), step);
    }

    public static void Fold(IEnumerable<double> values, Budget budget, ChannelWriter<double> sink, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(budget);
        values.AsParallel()
            .WithDegreeOfParallelism(budget.Workers)
            .WithCancellation(token)
            .GroupBy(static value => double.IsNegative(value))
            .Select(static slot => slot.Aggregate(0d, static (sum, value) => sum + value))
            .ForAll(partial => ignore(sink.TryWrite(partial)));
    }
}
```

[PARALLEL_ADMISSION]:
- Law: `Parallel.ForEachAsync` is the default parallel iteration — the body token is the loop's internal token tripping on any sibling fault or the external token, all failures aggregate on the returned task, and the aggregate converts once at the rail boundary; per-iteration catch blocks forfeit the aggregation the primitive already performs.
- Law: source enumeration serializes under an internal lock — a slow producer serializes the whole loop, and the decoupled spelling is producer, lane, then `ForEachAsync` over `ReadAllAsync`; `ParallelOptions` pins degree, scheduler, and token together as one policy value.
- Law: PLINQ admits only cpu-bound, side-effect-free, associative work in the total spelling — degree, cancellation, and a declared egress: `WithMergeOptions(NotBuffered)` for a streaming enumerated consumer, `FullyBuffered` for a terminal materialized sink, or `ForAll` into a lane write that re-enters the receipted world; `ForAll` runs the sink action on the partition threads with no merge back to the caller, so a `WithMergeOptions` beside a `ForAll` is dead configuration the merge never reads. `AsOrdered` is scoped and closed by `AsUnordered`, and `AsSequential` exits before cheap projection tails buy merge cost for nothing.
- Law: `Parallel.ForAsync<T>` spans `IBinaryInteger<T>` for index kernels with no materialized range; synchronous `Parallel.For`/`ForEach` survive only inside measured kernels under the named kernel exemption.
- Law: partitioning is a declared input shape — `Partitioner.Create(0, n, rangeSize)` sizes index ranges to cache or work granularity, range partitioning serving cache locality on uniform work and chunk partitioning serving load balance on skewed work; `EnumerablePartitionerOptions.NoBuffering` serves latency-sensitive producers whose items must not sit invisible in chunk buffers.
- Law: the single-flight gate sits between intent and acquisition — the first entrant publishes its task handle into a keyed cell by compare-and-set and owns execution, losers await it and receive a coalesced receipt counting entrants served, so a coalesced intent consumes zero permits and zero lane capacity.
- Law: the flight owner clears by compare-exchanging its own handle out, because a blind clear tears a successor's flight; waiter cancellation bounds the wait, never the shared work, and the key derives from the admitted request value — one keyed gate per identity vocabulary, since caller-context keys defeat coalescing exactly where it pays.

[CROSS_PROCESS_LEASE]:
- Law: the lease record is owner id, claim stamp, heartbeat stamp at a shared medium — owner identity pairs the process identifier with a boot-instant stamp, so a reborn process never satisfies its predecessor's lease.
- Law: claim is the medium's own atomic create-if-absent — atomic file create, unique-key insert — never read-then-write; the steal is an atomic conditional swap on the observed stale stamp, so two contenders cannot both reclaim, and the winner emits a takeover receipt naming the previous owner and the observed staleness.
- Law: release-on-drain is a cooperative-phase step ordered before the owner's lanes force-drain — successors observe release while the owner is alive to complete it, and a release scheduled after forced teardown races process death, reproducing the stale-lease window the protocol exists to prevent.
- Law: a contender steals only when heartbeat staleness observed from the medium at decision time exceeds the budget's threshold — under the staleness inequality a draining-but-alive owner is structurally unstealable, because it either heartbeats or releases before the threshold can elapse.

## [04]-[RATE_LIMITING]

[LIMITER_ROWS]:
- Law: four limiters are four `[SmartEnum<string>]` rows over one `Partition` acquisition column — `ConcurrencyLimiter` gates in-flight work and returns permits on lease disposal; the token bucket prices sustained rate as `TokensPerPeriod` over `ReplenishmentPeriod` and burst as `TokenLimit`, and declaring one without deriving the other is half a policy; a fixed window admits 2x the rate across a boundary, which the `SlidingWindowRateLimiter` `SegmentsPerWindow` count amortizes.
- Law: the acquisition verb is itself policy — `AttemptAcquire` is shed-with-receipt at the edge where the caller owns retry cadence, `AcquireAsync` is queue-and-wait where the limiter owns ordering, and a zero `QueueLimit` degrades the awaited acquire to fail-fast, the declared no-waiting row.
- Law: queue order is policy — `OldestFirst` reserves freed permits for the head and fails the newcomer on overflow; `NewestFirst` barges and evicts the oldest queued waiter as the staleness receipt — interactive intent takes `NewestFirst`, fairness-bound throughput takes `OldestFirst`.
- Law: failed leases carry typed evidence — `MetadataName.RetryAfter` names the earliest useful retry instant and feeds schedule policy, so a fixed backoff beside a `RetryAfter`-bearing lease re-derives what the lease already states.
- Law: zero-permit calls are probes — `AttemptAcquire(0)` succeeds iff permits remain, `AcquireAsync(0)` parks to the next replenishment edge without consuming — deleting polling loops over `GetStatistics()`; a `permitCount` above `PermitLimit` throws synchronously, a construction defect that never becomes a queue entry.
- Law: `GetStatistics()` is an init-only snapshot record — available permits, queued count, total successful and failed leases — never a live view; a widening gap between successful leases and disposals is the permit-leak signal, and a successful zero-permit probe increments the success counter, so it counts verdicts, never permits consumed.
- Law: `AcquireAsync(weight)` prices heterogeneous work on one limiter — weight in cost units, cumulative queued weight counted against `QueueLimit`, the weight function a policy value beside the row — so one weighted limiter replaces N per-class limiters whose relative rates would otherwise be hand-derived.
- Reject: a semaphore as limiter — queue order, eviction receipts, typed metadata, and statistics deleted at once.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class LimitRow {
    public static readonly LimitRow Interactive = new("<row-a>", static key =>
        RateLimitPartition.GetConcurrencyLimiter(key, static _ => new ConcurrencyLimiterOptions {
            PermitLimit = 8, QueueLimit = 0, QueueProcessingOrder = QueueProcessingOrder.NewestFirst }));
    public static readonly LimitRow Sustained = new("<row-b>", static key =>
        RateLimitPartition.GetTokenBucketLimiter(key, static _ => new TokenBucketRateLimiterOptions {
            TokenLimit = 64, TokensPerPeriod = 16, ReplenishmentPeriod = TimeSpan.FromSeconds(1), QueueLimit = 32 }));
    public static readonly LimitRow Windowed = new("<row-c>", static key =>
        RateLimitPartition.GetSlidingWindowLimiter(key, static _ => new SlidingWindowRateLimiterOptions {
            PermitLimit = 600, SegmentsPerWindow = 6, Window = TimeSpan.FromMinutes(1), QueueLimit = 0 }));
    public static readonly LimitRow Exempt = new("<row-d>", static key => RateLimitPartition.GetNoLimiter<string>(key));

    [UseDelegateFromConstructor]
    public partial RateLimitPartition<string> Partition(string key);
}

public sealed record Intent(string Key, LimitRow Row);

public static class AdmissionGate {
    static readonly PartitionedRateLimiter<Intent> Gate =
        PartitionedRateLimiter.Create<Intent, string>(static intent => intent.Row.Partition(intent.Key));

    public static IO<A> Run<A>(Intent intent, Func<IO<A>> work) =>
        IO.lift(() => Gate.AttemptAcquire(intent)).Bracket(
            Use: lease => lease.IsAcquired
                ? work()
                : IO.fail<A>(lease.TryGetMetadata(MetadataName.RetryAfter, out var after)
                    ? Error.New(7401, $"<shed-after:{after}>")
                    : Error.New(7402, "<shed>")),
            Fin: static lease => IO.lift(fun(lease.Dispose)));
}
```

[PARTITIONED_COMPOSITION]:
- Law: `PartitionedRateLimiter.Create` evaluates the partitioner on every acquisition and caches one limiter per key — the partitioner stays allocation-light and never touches IO; idle partitions auto-dispose on the internal heartbeat, so a holder never caches the inner limiter and reads go through the partitioned surface per call.
- Law: the typed partition factories force `AutoReplenishment = false` so every partition rides the one heartbeat — a custom `RateLimitPartition.Get` leaving auto-replenishment on pays a silent timer per key, and replenishment granularity inside a partitioned limiter is the heartbeat cadence regardless of a shorter declared period.
- Law: `GetNoLimiter` is the declared exempt row — exemption lives in the partition table, never call-site branching; exempt partitions never idle-evict, so a high-cardinality exempt key space is a permanent-resident leak by construction.
- Law: `CreateChained` limiters acquire in declared order, coarsest first — a later failure disposes every earlier lease so partial holds cannot leak, the combined lease aggregates metadata first-wins per name, and combined statistics fold to minimum available permits.
- Law: `WithTranslatedKey(keyAdapter, leaveOpen)` re-keys one partitioned limiter at a boundary — one permit pool under two key vocabularies, every verb routed through the thread-safe adapter on every acquisition path, `leaveOpen` deciding whether disposing the translation disposes the inner limiter.
- Law: verdicts close into one family — admitted, queued, coalesced, shed with retry-after, evicted — each carrying its evidence, so backoff, telemetry, and drain dispatch on verdict shape, never on which subsystem said no.

## [05]-[REACTIVE_STREAMS]

[STREAM_ADMISSION]:
- Law: an observable chain earns admission only where time or combination algebra changes the design — two or more time or combination operators, one multicast lifetime, or time logic that must run under a virtual clock; a `Select`/`Where`-only chain buys push hazards while using none of the algebra and belongs on rails or lanes.
- Law: the grammar is `OnNext* (OnError|OnCompleted)?`, serialized — `Subject<T>.OnNext` is unsynchronized, so concurrent producers serialize through `Synchronize()`, never per-observer locks that leave the grammar violated for every other observer.
- Law: cold is the default — every subscription re-runs factory side effects, `Interval` and `Timer` are per-subscriber clocks (N raw subscriptions are N timers), and a side-effecting cold source fans out only behind a multicast row.
- Law: `Subscribe` appears only at edges — the mid-chain tap is `Do`, termination is `Finally`, subscription-scoped resources are `Using`; a mid-pipeline `Subscribe` severs the declarative chain into imperative halves.
- Law: `FromEventPattern` converts an add/remove handler pair into a stream where subscription is the attach and disposal is the detach — the event-leak class deleted structurally, with `EventPattern<TEventArgs>` carrying sender and args as one value.
- Law: flattening is a declared concurrency decision — `Concat` sequential, `Merge(maxConcurrent)` under the budget, `Switch` latest-wins unsubscribing superseded inners, the structural cancellation of stale work with no token plumbing.
- Law: `CombineLatest` fires on either leg and emits nothing until every source emits once — seed quiet legs with `StartWith`; `WithLatestFrom` fires only on the driver and samples the companion — choose by which side drives downstream effects, since only the driver leg re-emits.
- Law: every time-based operator names its `IScheduler` — the implicit default forecloses virtual-time substitution, and time evidence is stamped through `Timestamp(scheduler)` and `TimeInterval(scheduler)`, never read ambiently inside an operator lambda, which breaks the virtualizable clock plane.
- Law: `EventLoopScheduler` is the dedicated serial lane — one named thread, FIFO delivery, disposed at scope end — where a consumer requires affinity without a context; the immediate scheduler executes scheduled work inline and livelocks recursive operators, so recursive and time-based work takes the trampolining current-thread scheduler or a named one.
- Law: marshal exactly once — one `ObserveOn` per chain at the consumption edge, because it affects only downstream delivery, and at most one `SubscribeOn`, which moves only subscription side effects — its position never moves where `OnNext` runs; `ObserveOn` delivers one observer's notifications serially in order, so ordering defects after a hop indict the merge topology, never the hop.

[DELIVERY_EDGE]:
- Law: every delivery edge to a cadence-bound observer declares its triple — coalescing row, significance gate, scheduler — and raw push to such an observer is the rejected form, never the slow observer itself.
- Law: the coalescing rows — `Sample(period)` conflates to latest at fixed cadence; `Throttle(due)` commits on quiet gap and permanently starves under steady input, the silent-starvation chooser; `Buffer(span, count)` trips on whichever bound first; `Window` streams frames where `Buffer` materializes lists, so unbounded frames take `Window` with an in-window `Scan`.
- Law: `Sample` and `Throttle` drop silently — where loss must be receipted the spelling is lossless `Buffer` folded to a latest-plus-dropped-count value; bare `Sample` is admissible only where intermediates are semantically void.
- Law: both cadence rows generalize stream-driven — `Sample(sampler)` clocks from any pulse observable, `Throttle(value => IObservable<TGate>)` derives a per-value quiet window from the value itself — so dynamic cadence is a selector, never a rebuilt chain or a timer dictionary.
- Law: `DistinctUntilChanged` sits after coalescing — conflate time first, then suppress non-changes; keyed cadence composes as `GroupBy` then a per-group coalescing row, merged — per-key conflation with one declaration per axis.
- Law: published state crossing scheduler hops is rank-guarded — every update carries the source's own monotone, a CAS admits only ascending ranks, and stale arrivals fold to receipted skips, the reorder gauge; the guard earns admission only at genuine multi-writer convergence — a single-source chain threads its rank through `Scan` and writes plainly.

```csharp conceptual
public static class DeliveryEdge {
    public static IObservable<(T Latest, int Dropped)> Conflate<T>(IObservable<T> source, TimeSpan cadence, IScheduler clock) =>
        source.Synchronize()
            .Buffer(cadence, clock)
            .Where(static frame => frame.Count > 0)
            .Select(static frame => (Latest: frame[^1], Dropped: frame.Count - 1))
            .DistinctUntilChanged(static pair => pair.Latest);

    public static IDisposable Deliver<T>(IObservable<T> source, ChannelWriter<(T Latest, int Dropped)> sink,
        TimeSpan cadence, IScheduler clock, CancellationToken until) =>
        Conflate(source, cadence, clock)
            .TakeUntil(until)
            .ObserveOn(clock)
            .Subscribe(pair => ignore(sink.TryWrite(pair)));

    public static IObservable<T> Activated<T>(IObservable<T> source, IScheduler clock) =>
        source.Publish().RefCount(minObservers: 2, disconnectDelay: TimeSpan.FromSeconds(1), scheduler: clock);
}
```

[ACTIVATION_AND_CROSSINGS]:
- Law: `Publish().RefCount(minObservers, disconnectDelay, scheduler)` is the demand-driven lifetime vocabulary — quorum activation starts shared work at the Nth subscriber, linger deactivation lets a re-subscription inside the window reuse the live connection; `AutoConnect` is activation without symmetric deactivation, for lifetimes a scope owns through the escaping connection handle.
- Law: a terminated multicast is sticky — once upstream completes or errors, every later subscriber receives the terminal immediately; restart is a factory producing the chain plus a current-instance cell, never `Defer`, because a deferred multicast constructs per subscriber and shares nothing; unbounded `Replay` is a leak declared as policy.
- Law: subjects are state cells with declared semantics — `BehaviorSubject<T>` the observable property cell (current value plus replay-1), `AsyncSubject<T>` the future cell (terminal value only), `ReplaySubject<T>` the bounded catch-up cell (`bufferSize`, `window`, scheduler) — and a bare `Subject<T>` survives only inside a multicast operator.
- Law: disposal is a policy vocabulary — `CompositeDisposable` per scope, `SerialDisposable` replace-on-reconfigure disposing its predecessor, `SingleAssignmentDisposable` set-once wiring, `RefCountDisposable` shared teardown, `CancellationDisposable` the token bridge — and `TakeUntil` over a lifetime signal beats imperative disposal wherever the signal exists.
- Law: behind the stream-to-rail seam, schedule policy is the one retry owner — a stream `Retry` under a rail retry is the double-loop defect, and in-stream `Catch` rows (typed handler, fallback stream, `params` cascade) survive only before that seam.
- Reject: the double bridge — stream to lane to stream inside one hop launders backpressure evidence through a buffer; the relay subject — a hand-subscribed `Subject` re-spelling `Publish` without disposal symmetry.

The worlds cross at four canonical seams — `OnNext` has no park position, so the lane crossing never waits — each with one spelling and one evidence carrier; a fifth crossing is a missing row, never a bespoke bridge.

| [INDEX] | [CROSSING]     | [SPELLING]                                      | [EVIDENCE]                 |
| :-----: | :------------- | :---------------------------------------------- | :------------------------- |
|  [01]   | rail to stream | `FromAsync`/`Defer` over the effect             | the effect's typed failure |
|  [02]   | stream to rail | `Materialize()` folded once into typed outcomes | terminal verdict           |
|  [03]   | stream to lane | non-waiting `TryWrite` into a drop row          | drop receipts              |
|  [04]   | lane to stream | async `Observable.Create` over the read stream  | disposal cancels the pull  |

## [06]-[CHANGE_SETS]

[SOURCE_LAW]:
- Law: two sources own all live collection state — `SourceCache<TObject, TKey>` keyed, `SourceList<T>` ordered — and everything downstream is `IObservable<IChangeSet<...>>`; the change-set is the only state transport, and a materialized intermediate — snapshot, re-source, re-`Connect` — severs the incremental delta path.
- Law: all multi-item mutation rides one `Edit(updater)` — the batch boundary is the emission boundary, and N convenience calls emit N change-sets and N downstream recomputations; emission rides the editing thread inside the source lock, so a heavy chain bills its cost to every writer and cost defers through the batching windows `Batch`, `BatchIf`, and `BufferInitial`.
- Law: a key is immutable for the object's cache lifetime — identity change is remove-then-add inside one `Edit`, never an update under a new key; the key selector runs per mutation and stays pure and cheap.
- Law: `Connect(predicate)` emits current state then deltas with the predicate fixed at connection — dynamic membership belongs to the `Filter` rows downstream, because re-`Connect` discards every operator's accumulated state; `Preview` observes change-sets before the cache mutates, the veto window.
- Law: existing producer state joins the algebra by one operator — `ToObservableChangeSet` admits observable collections and plain value streams with expiry and size-limit knobs, never a hand-pumped copy — and `PopulateInto(destination)` is the staged-pipeline pump across ownership boundaries, returned as the disposable it is.
- Law: significance gates at the earliest altitude that can decide — the `EditDiff` comparer suppresses no-op updates before they exist, `IgnoreUpdateWhen` stops them mid-chain, value-level distinct gates the egress edge — and gating late bills every intermediate operator for noise.

```csharp conceptual
public sealed record Entry(string Key, int Rank, bool Live);

public sealed record Shaped(string Key, int Weight);

public static class LiveSet {
    public static IDisposable Track(SourceCache<Entry, string> cache, IObservable<Seq<Entry>> resolved) =>
        resolved.Subscribe(set => cache.EditDiff(set, static (held, next) => held.Rank == next.Rank && held.Live == next.Live));

    public static IObservable<IChangeSet<Shaped, string>> View(SourceCache<Entry, string> cache, IObservable<Func<Entry, bool>> gate) {
        ArgumentNullException.ThrowIfNull(cache);
        return cache.Connect()
            .Filter(gate)
            .IgnoreUpdateWhen(static (current, previous) => current.Rank == previous.Rank)
            .Transform(static entry => new Shaped(entry.Key, entry.Rank * 2), transformOnRefresh: true);
    }

    public static IObservable<IEnumerable<KeyValuePair<string, Entry>>> Bound(SourceCache<Entry, string> cache, IScheduler clock) =>
        cache.ExpireAfter(static entry => entry.Live ? null : TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(5), clock);
}
```

[RESOLUTION_AND_REFRESH]:
- Law: every global invalidation enters as exactly one of five rows — whole-set `EditDiff`, predicate-stream `Filter(IObservable<Func<T, bool>>)`, regrouped `Group(selector, regrouper)`, re-projected `Transform(factory, forceTransform)`, per-item `FilterOnObservable` — the taxonomy is a partition, and two rows for one invalidation double-fires the set.
- Law: above the five sits the source-swap row — `Switch` over `IObservable<IObservableCache<,>>` replaces the entire source while preserving the chain, the prior contribution retracting as removals; `Switch` is for a different store or scope, `EditDiff` for recomputed membership of the same logical set.
- Law: the stream forms close the swap family — `IObservable<IEnumerable<T>>.EditDiff(keySelector)` turns a re-resolved snapshot stream into a change-set stream with no intermediate source, and the `IObservable<Optional<T>>` overload turns a presence stream into a one-key live set — a poller or configuration reload becomes a live set by appending one operator.
- Law: the refresh matrix is the downstream law — `Filter` re-tests membership on `Refresh`, sorted consumers re-position, `Group` re-keys, and `Transform` ignores `Refresh` unless `transformOnRefresh: true`, the silently-stale default; `AutoRefresh` prices its noise with `propertyChangeThrottle` for one item's burst and `changeSetBuffer` for many items' refreshes, and `SuppressRefresh` is the declared opt-out for refresh-noisy upstreams — `WhereReasonsAreNot` and its inclusion dual scope any consumer to the reason classes it can act on.
- Law: receipted bounding lives on the source forms — `ExpireAfter` and `LimitSizeTo` return the removed and evicted pairs, closing the identity set ingress = membership + receipted expiry + receipted eviction; the chain forms drop the receipt stream and survive only where the identity need not close, and a null per-item expiry means never-expires — retention is per-item data, not a cache-wide constant.
- Law: membership bounds resources — `SubscribeMany` ties a subscription to membership with removal disposing it, `DisposeMany` disposes leavers, and the `AsyncDisposeMany` completion stream is the cache's drain hook.

[CHAIN_ECONOMY]:
- Law: any derived view is one declared chain off one `Connect` — share at the widest fan-out through `AsObservableCache`; chain cost is per-stateful-operator keyed state times set size — joins hold both sides, groups hold per-group state, merge-many holds one subscription per parent item — so chain length is a budgeted quantity, never free composition.
- Law: join identity follows the surviving key — `LeftJoin`/`FullJoin` keep the left key with `Optional` sides, `RightJoin` mirrors it, `InnerJoin` keys the composite `(leftKey, rightKey)` so relation-as-entity multiplies identity by design — the `*JoinMany` family aggregates the many side per left key without a nested cache, and `MergeManyChangeSets` adjudicates duplicate child keys through its declared comparer, never accidental first-writer-wins.
- Law: sorted change-sets are the required input shape for `Page` and `Virtualise` — request-driven windows whose scroll position is itself an observable, a moving window over a large live set with no per-frame re-query; set-level computation reads through `QueryWhenChanged` without copying, and `ToCollection` is the rejected spelling where a query suffices.
- Law: every time-taking operator — `ExpireAfter`, `Batch`, `BatchIf`, `AutoRefresh` — pins its scheduler, or its time logic silently escapes virtualization through the library-global default.
- Law: aggregation folds incrementally — `Count`, `Sum`, `Avg`, `Max`, `StdDev` adjust on deltas, and `TrueForAll`/`TrueForAny` fold per-item observables into live invariants without re-querying the set.
- Law: list-shaped membership composes as set algebra — `Or`, `And`, `Xor`, `Except` over live operand lists, where adding a source to the operand list extends the union with zero new wiring; `DeferUntilLoaded` and `StartWithEmpty` are the two startup rows preventing premature-empty rendering and combinator deadlock.

## [07]-[DRAIN_PARTICIPATION]

[PARTICIPATION_CONTRACT]:
- Law: a lane's drain participation is three verbs — stop accepting via clean `TryComplete`, cooperative flush bounded by the band's soft budget, forced residue sweep receipted as one `DrainFact` — composed under the runtime band walk, which owns ordering and budget shares; abort paths complete with the coded typed fault so every drain-side observation classifies without string matching.
- Law: the cooperative phase ends consumer loops through the read verb's own terminal grammar — `WaitToReadAsync` folding to `false` — and the token appears only in the forced phase; a batching consumer flushes its partial batch the moment the verb folds, so every batch loop's exit edge is a flush edge.
- Law: forced-phase residue reads come out FIFO on plain lanes and in comparer order on the prioritized row; post-completion write refusals are drain residue, never drop receipts — conflating the two double-counts loss, so residue receipts as `LaneLoss(DrainResidue)` into the same `Atom<Seq<LaneLoss>>` the drop modes feed and the loss vocabulary stays one stream with a kind column, never a parallel `int` beside the receipts.
- Law: limiters dispose in the forced phase after lanes complete — disposal fails all queued acquisitions, so cooperative work never observes synthetic limiter failures; stream scopes end cooperatively via `TakeUntil(softDeadline, scheduler)` and forcibly by scope disposal; a cache drains as stop-edits, release batching gates, close receipt streams, await `AsyncDisposeMany` completion.
- Law: the conservation identity is the audit — written = consumed + receipted loss per lane, summing to one process identity provable from declarations because drop loss and drain residue share the one receipt stream; a lane that cannot close the identity from its declared evidence is misconfigured by construction.
- Exemption: the cooperative flush loop and the forced residue sweep are the platform-forced `Task` seam.

```csharp conceptual
public readonly record struct DrainFact(LaneRow Lane, int Consumed, int Residue, bool Forced) {
    public bool Closes(int written, Seq<LaneLoss> receipts) =>
        written == Consumed + receipts.Count(loss => loss.Lane == Lane);
}

public static class LaneDrain {
    public static async Task<DrainFact> Participate<T>(
        LaneRow row, Channel<T> lane, Atom<Seq<LaneLoss>> receipts, Func<T, ValueTask> step, Option<Error> abort, TimeSpan soft, CancellationToken forced) {
        ArgumentNullException.ThrowIfNull(row);
        ArgumentNullException.ThrowIfNull(lane);
        ArgumentNullException.ThrowIfNull(step);
        _ = lane.Writer.TryComplete(abort.Match(Some: static fault => fault.ToException(), None: static () => null));
        using var budget = CancellationTokenSource.CreateLinkedTokenSource(forced);
        budget.CancelAfter(soft);
        var (consumed, residue) = (0, 0);
        try {
            await foreach (var item in lane.Reader.ReadAllAsync(budget.Token).ConfigureAwait(false)) {
                await step(item).ConfigureAwait(false);
                consumed++;
            }
        }
        catch (OperationCanceledException) { }
        while (lane.Reader.TryRead(out _)) { // Exemption: forced residue sweep — each undelivered item receipts DrainResidue so loss stays one stream
            residue++;
            ignore(receipts.Swap(f => f.Add(new LaneLoss(row, LossClass.DrainResidue))));
        }
        return new DrainFact(row, consumed, residue, Forced: budget.Token.IsCancellationRequested);
    }
}
```
