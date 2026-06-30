# [PERSISTENCE]

A store is one declared profile and one operation rail. Engine, placement, and codec are orthogonal axes crossed by one profile row — provider admission, capability slots, write authority, naming policy, and converter admission are row columns — so a new deployment topology is rows with zero new store code. The context is a pooled unit-of-work capsule that never escapes its bracket, and every store interaction is a value in one closed op family whose arity is the input value's shape. Boot folds schema state to one typed verdict — a store whose schema is newer than the compiled model is a typed rejection carrying the unknown identifiers, never a best-effort open — and a schema change is a typed value classified physically, gated at generation, and split into expand and contract waves. Identity mints once at admission, every secondary key surface derives from one selector, and write mass self-emits its facts and its invalidation inside the statement that caused them. Growth lands as rows: a new engine is one profile row, a new operation one request case, a new aggregate one configuration block, a new hot query one compiled-delegate row.

## [01]-[STORE_CHOOSER]

This table routes a persistence concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]               | [OWNER]                                | [REJECTED_FORM]                 |
| :-----: | :---------------------- | :------------------------------------- | :------------------------------ |
|  [01]   | deployment topology     | profile row on three axes              | per-topology store code         |
|  [02]   | context lifetime        | pooled factory + per-acquisition stamp | injected long-lived context     |
|  [03]   | domain types in columns | one generated-converter admission      | hand-written converter per type |
|  [04]   | aggregate document      | complex-type mapping declaration       | owned-entity JSON               |
|  [05]   | save observation        | interceptor spine rows                 | service-layer try/catch         |
|  [06]   | schema state at boot    | migration verdict fold                 | best-effort open                |
|  [07]   | destructive change      | generation-time class gate + waves     | apply-time gating               |
|  [08]   | row identity            | identity policy row + one key selector | per-surface key respelling      |
|  [09]   | store operations        | one op family + one bracket            | repository per aggregate        |
|  [10]   | pagination              | keyset page op, `Option<Cursor>` input | offset paging                   |
|  [11]   | write mass              | set-based, copy, and merge lanes       | tracked-graph loops             |
|  [12]   | read-through cache      | port row + `MEMO_KEY` composite tag    | free-string invalidation        |

## [02]-[PROFILE_AXIS]

[AXIS_ROWS]:
- Law: a store is one profile row crossing three orthogonal axes, each a `[SmartEnum<string>]` item — engine carries the provider-admission delegate (a `[UseDelegateFromConstructor]` partial) plus capability columns, placement carries write, migrate, and read-ahead authority, codec carries the naming-and-converter framing delegate plus the tracking-posture column — so a new engine, placement, or codec is one item that lands every `Switch` arm at compile time, never a parallel record bag forfeiting totality; interior code never branches on the provider, and provider probes are test assertions only.
- Law: capability columns are option-typed lane slots — a lane the engine lacks is an absent slot that never composes for that profile, exclusion at composition with a typed explanation, never a runtime not-supported throw.
- Law: the relational base is the shared knob set every row inherits as data — `MaxBatchSize`, `CommandTimeout`, `MigrationsHistoryTable`, `UseQuerySplittingBehavior`, `UseParameterizedCollectionMode`, `ExecutionStrategy` — and the `ExecutionStrategy` slot is where store transaction retry lands as a profile row, the retry-owner split arriving settled.
- Law: the model cache keys on context type plus design-time flag, never provider — one context type against two engines silently serves the first-built model to the second; the escape trilemma is legislated at composition: per-profile context types, one compiled model per profile, or `IModelCacheKeyFactory`, which forecloses compiled models entirely.
- Law: naming is schema policy declared once — `UseSnakeCaseNamingConvention` rewrites every identifier at model build, migrations record the rewritten names as schema facts, and the compiled model carries them at zero runtime cost; changing the policy on a live schema is a full-rename migration, a day-zero decision.
- Law: generated domain types cross through one admission — `UseThinktectureValueConverters` installs the conventions plugin and every keyed smart enum, value object, and keyed union maps through its derived converter; `AddThinktectureValueConverters` and `HasThinktectureValueConverter` narrow scope and never widen, a hand-written converter for a generated type is the rejected form, and converter bridges stay public or internal because a private member fails only when the model compiles.
- Boundary: the embedded row admits its provider here; journal mode, pragmas, and cross-process file law are embedded-durability specialization composed beneath the row.

[CONTEXT_LIFECYCLE]:
- Law: the context is a unit-of-work capsule acquired from `PooledDbContextFactory<TContext>` inside one bracket, never a long-lived dependency; past the pool ceiling, acquisition silently degrades to transient construction — a cliff with no error — so the ceiling sizes to peak concurrent brackets.
- Law: a pooled context is frozen state — `OnConfiguring` runs once for the pool's lifetime — so per-acquisition discriminants stamp through a wrapping `IDbContextFactory<TContext>` that acquires from the pooled factory and stamps before handing out; pool return resets EF-owned state only, and driver session state leaks across acquisitions unless restored before the bracket closes.
- Law: tracking is the codec row's column, not a free knob — the read codec carries `QueryTrackingBehavior.NoTrackingWithIdentityResolution` as its model-wide default so projections that alias repeated entities resolve identities without the tracked path, the write codec carries `TrackAll`, and the per-query `AsNoTrackingWithIdentityResolution` operator is the single-statement override above either default; the tracked path exists only inside unit-of-work ops that end in a save.
- Law: model acquisition is a three-route fold per row — compiled (`UseModel` plus the fingerprint gate), cached-built under the shared memory governor, per-discriminant compiled instances; below hundreds of entity types the regeneration obligation costs more than the first-operation latency it buys.
- Law: `EnsureCreated` bypasses the history mechanism and a later migration apply fails — the ephemeral test row is its only admission.
- Exemption: the options-builder fold and the stamping body are the platform-forced statement seam.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class Placement {
    public static readonly Placement SingleWriter = new("<placement-a>", writes: true, appliesPending: true, readsAhead: false);
    public static readonly Placement FleetMember = new("<placement-b>", writes: true, appliesPending: false, readsAhead: false);
    public static readonly Placement Reader = new("<placement-c>", writes: false, appliesPending: false, readsAhead: true);
    public bool Writes { get; }
    public bool AppliesPending { get; }
    public bool ReadsAhead { get; }
}

public sealed class StoreContext(DbContextOptions<StoreContext> options) : DbContext(options) {
    public Placement Placement { get; internal set; } = Placement.Reader;
    protected override void OnModelCreating(ModelBuilder model) {
        ArgumentNullException.ThrowIfNull(model);
        model.ApplyConfigurationsFromAssembly(typeof(StoreContext).Assembly);
    }
}

[SmartEnum<string>]
public sealed partial class EngineRow {
    public static readonly EngineRow Embedded = new("<engine-a>", rebuildsAlters: true, nativeBulk: None, Sqlite);
    public static readonly EngineRow Server = new("<engine-b>", rebuildsAlters: false, nativeBulk: Some("<lane-a>"), Postgres);
    public bool RebuildsAlters { get; }
    public Option<string> NativeBulk { get; }

    [UseDelegateFromConstructor]
    public partial DbContextOptionsBuilder<StoreContext> Admit(DbContextOptionsBuilder<StoreContext> builder, string dsn);

    static DbContextOptionsBuilder<StoreContext> Sqlite(DbContextOptionsBuilder<StoreContext> builder, string dsn) =>
        builder.UseSqlite(dsn, static sqlite => sqlite.MigrationsHistoryTable("<history-a>"));
    static DbContextOptionsBuilder<StoreContext> Postgres(DbContextOptionsBuilder<StoreContext> builder, string dsn) =>
        builder.UseNpgsql(dsn, static npgsql => npgsql.EnableRetryOnFailure());
}

[SmartEnum<string>]
public sealed partial class Codec {
    public static readonly Codec WriteHead = new("<codec-a>", QueryTrackingBehavior.TrackAll);
    public static readonly Codec ReadAhead = new("<codec-b>", QueryTrackingBehavior.NoTrackingWithIdentityResolution);
    public QueryTrackingBehavior Tracking { get; }

    public DbContextOptionsBuilder<StoreContext> Frame(DbContextOptionsBuilder<StoreContext> builder) =>
        builder.UseSnakeCaseNamingConvention().UseThinktectureValueConverters(Configuration.Default).UseQueryTrackingBehavior(Tracking);
}

public sealed class StampedFactory(PooledDbContextFactory<StoreContext> pool, Placement placement) : IDbContextFactory<StoreContext> {
    public StoreContext CreateDbContext() {
        var store = pool.CreateDbContext();
        store.Placement = placement;
        return store;
    }
}

public sealed record StoreProfile(EngineRow Engine, Placement Placement, Codec Codec) {
    public IDbContextFactory<StoreContext> Pooled(string dsn, params ReadOnlySpan<IInterceptor> spine) =>
        new StampedFactory(new PooledDbContextFactory<StoreContext>(Options(dsn, spine)), Placement);

    public DbContextOptions<StoreContext> Options(string dsn, params ReadOnlySpan<IInterceptor> spine) =>
        Engine.Admit(Codec.Frame(new DbContextOptionsBuilder<StoreContext>()).AddInterceptors([.. spine]), dsn).Options;
}
```

## [03]-[MODEL_LAW]

[DOCUMENT_SHAPE]:
- Law: complex types are the document owner — value semantics end-to-end, so one value legally aliases into two slots and content equality translates in queries; one declaration chooses table splitting into prefixed columns or `ToJson` into a document column, and that declaration silently decides the write lane: complex document interiors are legal set-based targets, owned-entity JSON is foreclosed from that lane and rejected for new models.
- Law: `ComplexCollection` exists only in the JSON mapping and never table-splits; structs admit as complex types while struct collections do not, and an all-optional complex type is a model-validation rejection, so every complex type carries one required member.
- Law: migrating owned to complex is a model-shape change with an identical stored document when the column mapping holds — the set-based unlock is free.
- Law: a generated-type member inside a document rides converter-then-document — the converter mints the primitive, the document writer places it — so max-length policy and `HasJsonPropertyName` compose from two owners onto one property, declared at one model-building site.
- Law: `ConfigureConventions` is the model-wide admission seam for everything else — `Properties<T>()` conversions, `DefaultTypeMapping<TScalar>`, `ComplexProperties<TProperty>`, `IgnoreAny<T>` — and a per-property conversion declared outside it is the drift form: one type, one mapping, declared once.
- Law: primitive collections and parameterized query collections share one translation-mode axis — multi-parameter expansion with cardinality padding, one JSON-array parameter, inlined constants — declared by `UseParameterizedCollectionMode` and overridden per site with `EF.Constant`/`EF.Parameter`; padding buys cardinality buckets, one plan for eight values, and inlined constants redact from logs by default.
- Exemption: the configuration body is the model-declaration seam.

```csharp conceptual
[ValueObject<string>]
[KeyMemberEqualityComparer<ComparerAccessors.StringOrdinalIgnoreCase, string>]
[KeyMemberComparer<ComparerAccessors.StringOrdinalIgnoreCase, string>]
public readonly partial struct EntryKey;

public sealed record Window(int Start, int End);

public sealed record Mark(EntryKey Label, int Rank);

public sealed class Entry {
    public required EntryKey Key { get; init; }
    public required Window Active { get; set; }
    public required Window Archive { get; set; }
    public IReadOnlyList<Mark> Marks { get; set; } = [];
    public IReadOnlyList<int> Ranks { get; set; } = [];
}

public sealed class EntryShape : IEntityTypeConfiguration<Entry> {
    public void Configure(EntityTypeBuilder<Entry> entry) {
        ArgumentNullException.ThrowIfNull(entry);
        entry.HasKey(static e => e.Key);
        entry.ComplexProperty(static e => e.Active);
        entry.ComplexProperty(static e => e.Archive, static archive =>
            archive.ToJson("<column-a>").Property(static w => w.Start).HasJsonPropertyName("<name-a>"));
        entry.ComplexCollection(static e => e.Marks);
        entry.PrimitiveCollection(static e => e.Ranks);
    }
}
```

## [04]-[INTERCEPTOR_SPINE]

[SPINE_ALTITUDES]:
- Law: one spine, three altitudes, admitted through `AddInterceptors` as profile rows — singleton/compilation (`IMaterializationInterceptor`, `IQueryExpressionInterceptor`), unit-of-work (`ISaveChangesInterceptor` over the tracked graph), wire (`IDbCommandInterceptor` plus the connection and transaction pair); registration order is execution order, and per-contract aggregators compose registrations into one composite.
- Law: suppression is the gate lever — `InterceptionResult<T>.SuppressWithResult` turns an interceptor into a typed gate and later interceptors observe `HasResult` — and a suppressing save gate declares its tracker disposition (clear, detach, or hold) as a policy row or the next bracket inherits phantom dirty state.
- Law: every member carries a pass-through default, so a sync-only interceptor compiles and leaves the async path unintercepted — both modality twins are mandatory.
- Law: tracked-conflict policy is the built-in `IIdentityResolutionInterceptor` pair — ignoring or updating, selected as one row — never hand-rolled resolution.
- Law: `IQueryExpressionInterceptor` output caches with the query — the rewrite is a pure function of expression shape, and a per-execution rewrite replays its first execution forever.
- Law: set-based and bulk lanes bypass the unit-of-work altitude and surface only at the wire altitude — their fact emission is self-emitted by the op, never expected from the save spine.
- Law: the spine is provider-invariant and engine variance is observable only at the wire altitude — cross-engine assertions live in command-interceptor rows carried as engine-row columns — and `ConfigureWarnings` is the escalation seam turning chosen runtime warnings into typed failures at the options row.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class Disposition {
    public static readonly Disposition Clear = new("<disposition-a>", static tracker => fun(tracker.Clear)());
    public static readonly Disposition Detach = new("<disposition-b>",
        static tracker => toSeq(tracker.Entries()).Iter(static entry => entry.State = EntityState.Detached));
    public static readonly Disposition Hold = new("<disposition-c>", static _ => unit);

    [UseDelegateFromConstructor]
    public partial Unit Settle(ChangeTracker tracker);
}

public sealed class SaveGate(Disposition disposition) : ISaveChangesInterceptor {
    public InterceptionResult<int> SavingChanges(DbContextEventData eventData, InterceptionResult<int> result) =>
        Gate(eventData, result);

    public ValueTask<InterceptionResult<int>> SavingChangesAsync(DbContextEventData eventData, InterceptionResult<int> result, CancellationToken cancellationToken = default) =>
        ValueTask.FromResult(Gate(eventData, result));

    InterceptionResult<int> Gate(DbContextEventData? eventData, InterceptionResult<int> result) =>
        eventData?.Context is StoreContext { Placement.Writes: false } store
            ? (disposition.Settle(store.ChangeTracker), InterceptionResult<int>.SuppressWithResult(0)).Item2
            : result;
}
```

## [05]-[MIGRATION_ALGEBRA]

[MIGRATION_VALUE]:
- Law: a migration is data before action — `UpOperations` and `DownOperations` materialize without a store, `TargetModel` and `ActiveProvider` read from the artifact — so every audit folds over operations and parsing generated SQL is the rejected form; identifiers are timestamp-prefixed, so identifier order is application order and the applied maximum is the store's schema stamp.
- Law: each migration applies in its own transaction — a mid-set failure leaves an applied prefix, never a torn migration — and recovery is idempotent re-apply of the remainder, never rollback of the prefix; the applied-set receipt is monotone, cheap enough to fold on every boot.
- Law: rollback is a generation parameter, never a special tool — a `from` newer than `to` yields the rollback script, `Migrate(targetMigration)` applies `Down` bodies in reverse identifier order, and target `0` is full teardown, gated like any destructive operation.
- Law: `Migrate` holds a store-wide lock for the whole span and a hard kill abandons the embedded lock table — boot reclaims the stale lock (detect, verify no live holder, clear) before applying, because patience retries forever against a ghost; seeding rides the lock through `UseSeeding`/`UseAsyncSeeding`, single-writer by construction and idempotent by contract, the created flag its only freshness signal.
- Law: the vehicle is a placement column — bundle-per-release for fleets, idempotent script for operator-gated stores, runtime boot apply only on the single-writer row inside the gated lifecycle state; fleet boot apply is rejected even though the lock makes it safe, because it grants every instance DDL rights and couples rollout order to schema state.
- Law: `MigrationBuilder.Sql` is itself an operation and stays visible to the fold; `suppressTransaction: true` degrades the receipt unit from migration to operation, so a suppressed operation is idempotent in its own right, and hand-written DDL beside the migration set is invisible drift the next scaffold silently fights.

[BOOT_VERDICT]:
- Law: boot computes one total verdict from two identifier sets and a drift gate — applied minus assembly non-empty is schema-newer-than-model, a typed rejection carrying the unknown identifiers, because an older binary's model cannot describe columns it has never seen and a silent open corrupts on first write.
- Law: the pending arm routes by placement, the fresh store is its own provision arm, and equal sets run `HasPendingModelChanges` — the runtime half of the fingerprint gate, catching added-migration-without-regeneration; the inverse hole, a model edit with neither migration nor regeneration, closes only at build time by regenerate-and-diff.
- Law: read-ahead serving is legal only under a declared expand-only suite invariant — the unknown suffix is locally unclassifiable, so the sound default is hard rejection and the degradable row is a deployment invariant, never a runtime discovery.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record SchemaVerdict {
    private SchemaVerdict() { }
    public sealed record Serving : SchemaVerdict;
    public sealed record ServingBehind(Seq<string> Unknown) : SchemaVerdict;
    public sealed record Provisioned(Seq<string> Applied) : SchemaVerdict;
    public sealed record Advanced(Seq<string> Applied) : SchemaVerdict;
    public sealed record AwaitBundle(Seq<string> Pending, bool Fresh) : SchemaVerdict;
    public sealed record Drifted : SchemaVerdict;
}

public static class SchemaGate {
    public static Fin<SchemaVerdict> Admit(StoreContext store, Placement placement) {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(placement);
        var assembly = toSeq(store.Database.GetMigrations());
        var applied = toSeq(store.Database.GetAppliedMigrations());
        var unknown = applied.Filter(id => !assembly.Exists(held => held == id));
        var pending = assembly.Filter(id => !applied.Exists(held => held == id));
        return (unknown.IsEmpty, pending.IsEmpty) switch {
            (false, _) when placement.ReadsAhead => Fin.Succ<SchemaVerdict>(new SchemaVerdict.ServingBehind(unknown)),
            (false, _) => Fin.Fail<SchemaVerdict>(Error.New(8201, $"<schema-ahead:{unknown}>")),
            (_, false) when placement.AppliesPending => Try.lift(fun(() => store.Database.Migrate())).Run()
                .MapFail(error => Error.New(8202, $"<apply-failed:{error.Message}>"))
                .Map(_ => (SchemaVerdict)(applied.IsEmpty ? new SchemaVerdict.Provisioned(pending) : new SchemaVerdict.Advanced(pending))),
            (_, false) => Fin.Succ<SchemaVerdict>(new SchemaVerdict.AwaitBundle(pending, Fresh: applied.IsEmpty)),
            _ => Fin.Succ<SchemaVerdict>(store.Database.HasPendingModelChanges() ? new SchemaVerdict.Drifted() : new SchemaVerdict.Serving()),
        };
    }
}
```

[WAVE_GATE]:
- Law: every schema change decomposes into an expand wave and a contract wave with a deployment boundary between — expand strictly additive, contract removing only after every old-shape reader retires — and the gate runs at generation time over `UpOperations`, because apply-time gating leaves only skip-and-drift or apply-and-lose.
- Law: the fold classifies physically per the `ActiveProvider` the migration stamps, first match wins, and admits destructive classes only under a per-migration token; rename is the forbidden middle — expand plus backfill plus contract — and a migration mixing waves rejects whole.
- Law: the backfill between waves is bulk-rail data work, never schema-rail — a row-mass backfill squats on the fleet-wide lock past the health-probe window.
- Law: a destructive `Up` whose `Down` cannot restore data declares irreversibility — a fabricated lossy `Down` is a second destructive operation in disguise.

| [INDEX] | [UP_OPERATION]                                  | [PHYSICAL_CLASS] | [DISPOSITION]         |
| :-----: | :---------------------------------------------- | :--------------- | :-------------------- |
|  [01]   | `AddColumnOperation` nullable or defaulted      | additive         | expand                |
|  [02]   | `AddColumnOperation` required, no default       | destructive      | rejected expand       |
|  [03]   | `RenameTableOperation`, `RenameColumnOperation` | rename           | forbidden middle      |
|  [04]   | `AlterColumnOperation` on a rebuilding engine   | rebuild          | gated as full rewrite |
|  [05]   | `AlterColumnOperation` tightening nullability   | destructive      | contract              |
|  [06]   | `DropTableOperation`, `DropColumnOperation`     | destructive      | contract              |
|  [07]   | `SqlOperation` without a class token            | destructive      | worst-case default    |

## [06]-[IDENTITY_AXIS]

[IDENTITY_ROWS]:
- Law: identity is one closed three-row axis — time-ordered surrogate, content-hash, natural — and every row carries four columns: generator, transcription, ordering semantics, collision law; mixing rows per aggregate is normal, mixing rows per surface of one aggregate is the defect.
- Law: identity mints exactly once at admission — `Guid.CreateVersion7()` in the owner factory with `ValueGeneratedNever` as the transcription — so keys insert in bulk lanes, reference before save, and survive retries; `CreateVersion7(DateTimeOffset)` is the deterministic-backfill overload minting historical surrogates from original timestamps so index locality matches history.
- Law: ordering survives transcription only when the spelling preserves it — the canonical text form is lexically time-ordered, the default byte export is not — so `ToByteArray(bigEndian: true)` is the binary transcription law; without it a binary-keyed primary index degrades to random-insert fragmentation, the pathology the row exists to delete.
- Law: content-hash identity is encoding identity — the canonical encoding is a declared policy, the digest is the boundaries.md `BYTE_IDENTITY` codec injected as the row's `Mint` arrow, never a second hashing path, and the collision posture is a declared column whose idempotent row is the natural partner of conflict-tolerant bulk ingestion; this injected-digest factory row is why the axis is a delegate-bearing `record` of static rows rather than a `[SmartEnum]` of fixed items — the content-hash row mints from a runtime codec a fixed singleton cannot close over, the lone owner-shape exemption on this page.
- Law: natural keys ride the generated-converter seam on immutable owners — a mutable primary key is delete-insert wearing an update's clothes.
- Law: each aggregate declares one key selector once — `Expression<Func<TRow, TKey>>` — and every secondary surface derives mechanically: foreign keys, index orderings, changefeed keys, cache tags, pagination cursors; identity-row change is never `AlterColumn` — it is an expand-wave second key backfilled by the deterministic mint, a derivation flip, and a contract-wave drop, the only identity migration preserving foreign references, changefeed continuity, and cursor validity at once.

```csharp conceptual
public sealed class Fact {
    public Guid Key { get; init; }
    public required string Payload { get; set; }
    public int Rank { get; set; }
    public DateTimeOffset Observed { get; set; }
}

[SmartEnum<string>]
public sealed partial class Collision {
    public static readonly Collision Unmintable = new("<collision-a>");
    public static readonly Collision ContentIdempotent = new("<collision-b>");
    public static readonly Collision ForeignAuthority = new("<collision-c>");
}

public sealed record IdentityRow(string Axis, Collision Collision, bool Ordered, Func<TimeProvider, Fact, Guid> Mint) {
    public static readonly IdentityRow TimeOrdered = new("<axis-a>", Collision.Unmintable, Ordered: true,
        static (clock, _) => Guid.CreateVersion7(clock.GetUtcNow()));
    public static readonly IdentityRow Backfilled = new("<axis-a>", Collision.Unmintable, Ordered: true,
        static (_, fact) => Guid.CreateVersion7(fact.Observed));
    public static IdentityRow ContentHash(Func<string, Guid> digest) =>
        new("<axis-b>", Collision.ContentIdempotent, Ordered: false, (_, fact) => digest(fact.Payload));

    public static byte[] Spelled(Guid key) => key.ToByteArray(bigEndian: true);
}
```

## [07]-[OPERATION_RAIL]

[BRACKET_LAW]:
- Law: store operations form one closed request family dispatched by one rail — a repository per aggregate multiplies surfaces while every body repeats the same bracket; the bracket composes pool acquisition, execution strategy, transaction, tracking posture, provenance, and fault conversion as policy rows, so a new operation is a case plus an arm and a new cross-cutting concern is one bracket row touching zero ops.
- Law: the strategy composes the bracket state-threaded — inputs travel as `TState` through static lambdas so a retry re-runs a closed value, never a captured closure — and a transaction opened outside the strategy callback poisons every retry: begin, ops, and commit live inside it, with `verifySucceeded` mandatory for non-idempotent tails because an ambiguous commit double-applies delta-shaped work.
- Law: transaction posture is declared, never improvised — `AutoTransactionBehavior` selects when saves get implicit transactions, and `AutoSavepointsEnabled` nests a savepoint inside a caller-owned transaction so a failed save rolls back to the savepoint, never the whole bracket.
- Law: the bracket converts provider exceptions to typed rejections at its boundary and interior op bodies never see them; caller cancellation passes through untyped, never converted to a store rejection.
- Law: ops return value projections, never entities — entity egress couples consumers to the model and drags the tracker across the seam — and a stream arity folds inside the bracket or hands off through a lane, because a live enumerable returned after the context pools enumerates reclaimed state.
- Law: every op stamps provenance from its own symbol through `TagWith` and parameterizes every value — one cached plan per op; `EF.Constant` is a declared per-op row for provably low-cardinality hot filters, and proven hot ops graduate to `EF.CompileAsyncQuery` delegate rows by measurement, paying in proportion to expression depth.
- Law: the raw seam types by shape — `FromSql` parameterizes every interpolation hole, `FromSqlRaw` admits only sanitized fragments, `ExecuteSql` carries maintenance statements inside the same bracket — and `LeftJoin`/`RightJoin` are the outer-join spelling, deleting the `GroupJoin` scaffold.
- Law: read-through caching is one port row whose invalidation tag is the boundaries.md `MEMO_KEY` structural composite — the lane axis joined to the admitted owner key, a `(lane, key)` value the cache indexes by, so a write self-emits the exact tags its keys cut and a free-format string tag rejects at admission because it is uninvalidatable by construction; the content-key axis reuses that one canonical byte-codec verbatim, never a second hashing path, and logical tag-cut and physical delete are different lifetimes while the near-tier TTL is a per-lane staleness ceiling lanes that cannot tolerate bypass rather than shrink.

[ARITY_AND_PAGE]:
- Law: arity discriminates on the input value — a key resolves to an optional value, a key set to a batch, a predicate plus cursor to a page, a predicate alone to a stream — and pagination adds zero entrypoints because the page input is `Option<Cursor>`, absent meaning first page.
- Law: the page op is keyset-only — offset cost grows with depth and concurrent writes shift boundaries into duplicates and gaps; the ordering tuple ends in the unique key-selector tiebreaker, the predicate is the lexicographic expansion because tuple row-value comparison does not translate, and cursor values bind as parameters so page depth never changes the SQL shape.
- Law: the cursor is the projected ordering tuple of the last row, opaque to callers, expiring with the dual-key window as a typed stale-cursor rejection, never an empty page; descending lanes flip the ordering and every comparison together, and the ordering tuple is a contiguous index prefix — the page op and its covering index are one declaration reviewed together.
- Exemption: the bracket body — pooled acquisition and the catch arm — is the platform-forced statement seam.

```csharp conceptual
public readonly record struct Cursor(int Rank, Guid Key);

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record StoreOp {
    private StoreOp() { }
    public sealed record Point(Guid Key) : StoreOp;
    public sealed record Batch(Seq<Guid> Keys) : StoreOp;
    public sealed record Page(int Width, Option<Cursor> After) : StoreOp;
}

public readonly record struct FactView(Guid Key, int Rank);

public static class StoreRail {
    static readonly Func<StoreContext, int, CancellationToken, Task<int>> HotCount =
        EF.CompileAsyncQuery(static (StoreContext store, int floor, CancellationToken ct) =>
            store.Set<Fact>().Count(f => f.Rank > floor));

    public static async Task<Fin<Seq<FactView>>> Read(IDbContextFactory<StoreContext> factory, StoreOp op, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(factory);
        await using var store = await factory.CreateDbContextAsync(token).ConfigureAwait(false);
        try {
            return Fin.Succ(toSeq(await store.Database.CreateExecutionStrategy().ExecuteAsync(
                (Store: store, Op: op),
                static (state, ct) => state.Op.Shaped(state.Store.Set<Fact>()).TagWith(nameof(Read)).ToArrayAsync(ct),
                verifySucceeded: null,
                token).ConfigureAwait(false)));
        }
        catch (Exception ex) when (ex is not OperationCanceledException) {
            return Fin.Fail<Seq<FactView>>(Error.New(8231, $"<store-rejected:{ex.Message}>"));
        }
    }

    public static async Task<Fin<int>> Count(IDbContextFactory<StoreContext> factory, int floor, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(factory);
        await using var store = await factory.CreateDbContextAsync(token).ConfigureAwait(false);
        try { return Fin.Succ(await HotCount(store, floor, token).ConfigureAwait(false)); }
        catch (Exception ex) when (ex is not OperationCanceledException) {
            return Fin.Fail<int>(Error.New(8232, $"<store-rejected:{ex.Message}>"));
        }
    }

    extension(StoreOp op) {
        public IQueryable<FactView> Shaped(IQueryable<Fact> facts) => op.Switch(
                state: facts,
                point: static (rows, p) => rows.Where(f => f.Key == p.Key),
                batch: static (rows, b) => rows.Where(f => b.Keys.AsEnumerable().Contains(f.Key)),
                page: static (rows, pg) => (pg.After is { IsSome: true, Case: Cursor last }
                        ? rows.Where(f => f.Rank > last.Rank || (f.Rank == last.Rank && f.Key.CompareTo(last.Key) > 0))
                        : rows)
                    .OrderBy(static f => f.Rank).ThenBy(static f => f.Key).Take(pg.Width))
            .Select(static f => new FactView(f.Key, f.Rank));
    }
}
```

## [08]-[BULK_LANE]

[WRITE_MASS]:
- Law: high-volume mutation is one lane with three intensities — set-based statement for predicate-shaped work, bulk copy for collection-shaped ingestion, merge for source-against-target reconciliation — all enlisted in the rail's ambient transaction and all self-emitting: the statement that mutates produces the facts and the tag-cut before commit, deleting change-data capture, polled outboxes, and triggers in one move.
- Law: `LinqToDBForEFTools.Initialize()` once at composition activates the bridge, `ToLinqToDB()` deepens any rail queryable inside the same model and connection, the bridge connection enlists in `Database.CurrentTransaction` by default with `CreateLinqToDBConnectionDetached` as the explicit opt-out signature, and a bridged queryable materializes through the bare linq2db `ToListAsync`/`ToArrayAsync` while the unbridged EF queryable disambiguates through `ToListAsyncEF`/`ToArrayAsyncEF` — the `*EF` suffix names the EF lane where both surfaces import into one file; the bridge is a lane of the one rail, never a second public query surface.
- Law: the setter builder is statement-bodied by contract — a plain `if` adds a setter, deleting expression-tree surgery — setters reach inside document columns, and zero-affected where the predicate proved rows is a typed concurrency signal folded, never discarded.
- Law: merge clauses evaluate in declaration order — order is semantics, and a delete declared before an update deletes what the update would have claimed; `Using` admits client batches without staging, the by-source rows close two-sided reconciliation in one statement, and `MergeWithOutput`/`MergeWithOutputInto` land the action discriminant plus before and after images from the statement that caused them, zero roundtrips.
- Law: `BulkCopyAsync` receipts `RowsCopied` with `Abort` as the mid-stream rollback lever; `KeepIdentity` is mandatory under the time-ordered identity row or the store re-mints and admission identity is lost, `ConflictAction.Ignore` is doubly gated — `MultipleRows` plus an engine that spells it — and pairs with a rows-versus-source reconciliation receipt or losses are invisible, and `MaxDegreeOfParallelism` consumes the suite budget, never an independent pool.
- Law: every bulk composition renders without executing — `ToSqlQuery` returns the statement as a value, the audit receipt and dry-run spelling for gated destructive lanes.
- Exemption: the transaction bracket and the bridge lease are the platform-forced statement seam.

```csharp conceptual
public readonly record struct ChangeRow(string Action, Guid Before, Guid After);
public readonly record struct CutTag(string Lane, Guid Key);
public readonly record struct MassFact(string Lane, int Touched, Seq<Guid> Keys) {
    public Seq<CutTag> CutTags => Keys.Map(key => new CutTag(Lane, key));
}

public static class WriteMass {
    public static Task<Fin<MassFact>> Touch(StoreContext store, Guid key, int rank, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(store);
        return store.Set<Fact>().Where(f => f.Key == key)
            .ExecuteUpdateAsync(setters => {
                setters.SetProperty(static f => f.Rank, rank);
                if (rank > 8) { setters.SetProperty(static f => f.Payload, "<value-a>"); }
            }, token)
            .Map(affected => affected == 0
                ? Fin.Fail<MassFact>(Error.New(8241, $"<moved:{key:n}>"))
                : Fin.Succ(new MassFact("<lane-a>", affected, [key])));
    }

    public static async Task<Fin<MassFact>> Ingest(StoreContext store, Seq<Fact> rows, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(store);
        using var bridge = store.CreateLinqToDBConnection();
        var receipt = await bridge.GetTable<Fact>()
            .BulkCopyAsync(new BulkCopyOptions { BulkCopyType = BulkCopyType.MultipleRows, KeepIdentity = true }, rows, token)
            .ConfigureAwait(false);
        return (int)receipt.RowsCopied == rows.Count
            ? Fin.Succ(new MassFact("<lane-b>", rows.Count, rows.Map(static f => f.Key)))
            : Fin.Fail<MassFact>(Error.New(8243, $"<lost:{rows.Count - (int)receipt.RowsCopied}>"));
    }

    public static async Task<Fin<Seq<ChangeRow>>> Reconcile(StoreContext store, Seq<Fact> source, Func<Seq<CutTag>, CancellationToken, Task> cut, CancellationToken token) {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(cut);
        await using var tx = await store.Database.BeginTransactionAsync(token).ConfigureAwait(false);
        using var bridge = store.CreateLinqToDBConnection();
        try {
            var emitted = toSeq(await bridge.GetTable<Fact>()
                .Merge().Using(source).On(static held => held.Key, static next => next.Key)
                .UpdateWhenMatchedAnd(static (held, next) => held.Rank != next.Rank, static (held, next) => next)
                .InsertWhenNotMatched()
                .DeleteWhenNotMatchedBySource()
                .MergeWithOutputAsync(static (action, before, after) => new ChangeRow(action, before.Key, after.Key))
                .ToListAsync(token).ConfigureAwait(false));
            await cut(new MassFact("<lane-c>", emitted.Count, emitted.Map(static row => row.After)).CutTags, token).ConfigureAwait(false);
            await tx.CommitAsync(token).ConfigureAwait(false);
            return Fin.Succ(emitted);
        }
        catch (Exception ex) when (ex is not OperationCanceledException) {
            return Fin.Fail<Seq<ChangeRow>>(Error.New(8242, $"<merge-rejected:{ex.Message}>"));
        }
    }
}
```
