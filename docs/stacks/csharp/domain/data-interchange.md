# [DATA_INTERCHANGE]

Interchange is one projection rail. Any store's rows leave as typed tabular, columnar, or geo artifacts carrying a schema stamp and a content hash, and re-enter only through admission — never as live state shared across processes. The analytical engine is a projection surface, not a system of record: one anchor session under a declared posture, operational stores mounted read-only, bulk movement in vector chunks with named commit points, engine-mediated egress as one `COPY` statement assembled from artifact-class policy rows while a zero-copy or direct-codec lane stays a sibling row. Delimited exchange derives reader, writer, and descriptor from one profile record so round-trip symmetry is structural; artifact identity is a descriptor stamp plus a hash, and schema evolution is one name-keyed lattice diff whose verdict gates every consumer. Geo data holds one interior vocabulary — NetTopologySuite geometry — with exactly two wire projections, text and blob, each a policy-frozen profile value. Growth lands as rows: a new artifact class is one declaration deriving emission, stamp, and gate; a new egress format, partition key, or codec is a policy row; a new delivery target is a union case that breaks dispatch at compile time.

## [01]-[INTERCHANGE_CHOOSER]

This table routes an interchange concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                      | [OWNER]                              | [REJECTED_FORM]                 |
| :-----: | :----------------------------- | :----------------------------------- | :------------------------------ |
|  [01]   | analytical session             | posture record + one anchor          | open-per-query connections      |
|  [02]   | in-process engine concurrency  | `Duplicate()` lanes over one handle  | command interleaving            |
|  [03]   | foreign store reads            | read-only `ATTACH`                   | export-import shuffle           |
|  [04]   | bulk ingest                    | mapped appender + explicit `Close()` | row-at-a-time `INSERT` loop     |
|  [05]   | large result reads             | streaming-mode reader                | `DataTable` materialization     |
|  [06]   | in-process sequence in a query | registered table function            | single-query staging table      |
|  [07]   | engine columnar egress         | one `COPY` rail + policy rows        | per-format export paths         |
|  [08]   | artifact generations           | name-keyed union reads               | in-place rewrites               |
|  [09]   | delimited exchange             | one profile record, derived triple   | per-site option drift           |
|  [10]   | artifact identity              | descriptor stamp + content hash      | filename-convention trust       |
|  [11]   | schema evolution               | lattice diff verdict                 | per-consumer compatibility code |
|  [12]   | geo vocabulary                 | NTS interior, two wire projections   | coordinate DTO forks            |
|  [13]   | geo text wire                  | one converter-factory row            | per-type converter registration |
|  [14]   | geo store blob                 | policy-frozen blob codec             | raw WKB columns                 |

## [02]-[ANALYTICAL_ENGINE]

[SESSION_POSTURE]:
- Law: one process holds one refcounted native handle per source path, and the last close evicts buffer pool and attached catalogs — a session is one anchor connection held for its lifetime, and in-process concurrency is `Duplicate()` over the same handle, because a streaming drain occupies its connection until disposed.
- Law: posture is four declared knobs — `memory_limit` (80 percent of RAM unset), `threads` (every core unset), `temp_directory` (`<database>.tmp` unset), `max_temp_directory_size` (90 percent of free disk unset) — sized for a dedicated machine, so an embedded lane declares all four with `threads` consumed from the host's parallelism budget; spill is silent by design — operators past the limit complete slowly instead of failing — so a loud-failure lane caps spill low and treats it as signal.
- Law: settings travel three routes by mutability — boot keys in the connection-string tail through the builder's indexer, session keys via `SET`, per-catalog keys as attach options — and `preserve_insertion_order` false is the memory lever for order-free export pipelines.
- Law: `:memory:?cache=shared` is the only in-memory shape with one-writer/N-readers; bare `:memory:` is a private engine per connection, and multi-process posture is binary — one read-write holder or any number of read-only mounts declared in the tail.
- Law: one writing transaction context exists per database — write lanes serialize at `BeginTransaction`, analytical reads run unwrapped; `Cancel()` routes to the native interrupt, one cancellable unit per connection, a negative `GetQueryProgress().Percentage` projects to absence, never a fabricated zero, and `DuckDBException.ErrorType` is the rejection discriminant — fault arms map the typed error class, never message substrings.
- Law: the engine is a projection surface — operational stores enter read-only, results leave as artifacts or typed reads, and the engine's own file is a rebuildable derived artifact; cross-catalog work is read-from-many, write-to-one by engine law, attached catalogs answer the same `GetSchema` metadata reads as the primary, so foreign-store pre-flight is a metadata query against the alias before any data moves, and the ephemeral topology — shared in-memory primary, durable stores mounted read-only — computes in scratch and exits leaving no engine state.
- Law: a sealed host pre-installs extensions and declares the `autoinstall_known_extensions`/`autoload_known_extensions` pair — both default true, so first use of a scanner extension otherwise downloads at runtime, the ambient-network dependency that fires only in production.
- Exemption: the session capsule's command bodies are the platform-forced ADO statement seam.

```csharp conceptual
public sealed record EnginePosture(string Source, int Threads, string MemoryCap, string SpillRoot, string SpillCap, bool PreserveOrder) {
    public static EnginePosture Mart(string path, int threads) => new(path, threads, "<cap-a>", "<dir-a>", "<cap-b>", PreserveOrder: true);
    public static EnginePosture Scratch(int threads) => new(":memory:?cache=shared", threads, "<cap-a>", "<dir-a>", "<cap-b>", PreserveOrder: false);

    public string Composed {
        get {
            var rows = new DuckDBConnectionStringBuilder { DataSource = Source };
            (rows["threads"], rows["memory_limit"], rows["temp_directory"], rows["max_temp_directory_size"], rows["preserve_insertion_order"]) =
                (Threads, MemoryCap, SpillRoot, SpillCap, PreserveOrder);
            return rows.ConnectionString;
        }
    }
}

public sealed class Session(EnginePosture posture) : IDisposable {
    readonly DuckDBConnection anchor = Opened(posture);

    public Fin<Unit> Mount(string alias, string store) => Run($"ATTACH IF NOT EXISTS '{store}' AS {alias} (READ_ONLY)");
    public Fin<Unit> Unmount(string alias) => Run($"DETACH {alias}");
    public DuckDBConnection Lane() => anchor.Duplicate();
    public Option<double> Progress() => anchor.GetQueryProgress() is { Percentage: >= 0 and var alive } ? Some(alive) : None;
    public void Dispose() => anchor.Dispose();

    Fin<Unit> Run(string sql) =>
        Try.lift(() => { using var command = anchor.CreateCommand(); command.CommandText = sql; return (command.ExecuteNonQuery(), unit).Item2; })
            .Run().MapFail(static error => Error.New(8101, $"<catalog-refused:{error.Message}>"));

    static DuckDBConnection Opened(EnginePosture posture) {
        var live = new DuckDBConnection(posture.Composed);
        live.Open();
        return live;
    }
}
```

[CHUNK_ALGEBRA]:
- Law: ingress and egress are one symmetric chunk algebra at the engine's vector quantum — the appender flushes per vector-size chunk as rows accumulate, the streaming reader holds one chunk at a time — so peak managed memory is one chunk wide regardless of batch size, budgets count chunks never rows, and backpressure is pull-shaped on both lanes.
- Law: error-late is the lane's failure mode — appender constraint violations defer to chunk boundaries and `Close()`, streaming plan failures surface at mid-drain `Read()` — so every bulk movement names its commit point and converts there; `Dispose()` calls `Close()` when unclosed, so an appender lifetime not wholly inside the capture lets construction refusals escape the rail and lets disposal flush a partial batch.
- Law: the mapped appender validates at construction — zero mappings, a count mismatch, or a per-column CLR-to-logical type mismatch throws before any row moves, making record-table drift a construction failure caught on the rail; `Clear()` on the raw appender is the abort lane, discarding pending rows with the lane still usable, and a `DefaultValue()` row in the `DuckDBAppenderMap<T>` is the only way to exercise a column default through the bulk lane — the default is a declared map row, never a per-record call.
- Law: streaming defaults off — an unconfigured command materializes the whole result in the native handle — so the streaming flag is profile policy, never a per-query choice, and concurrent work during a long drain rides a `Duplicate()` lane.
- Law: `DuckDBParameter` is one binding surface indexed by position and name; an explicit `DbType` pins the logical type wherever CLR inference would widen, mandatory for object-typed pipeline values; `RecordsAffected` is always −1 on the reader — mutation counts come from `ExecuteNonQuery`; `IsDBNull` is the validity-mask read that precedes every nullable column value, and `Prepare()` amortizes repeated parameterized reads through the prepared lane, never SQL-string caching.
- Law: UDFs are vector kernels invoked with a row count, never per-row delegates — scalar registration declares `IsPureFunction` and `HandlesNulls` as facts, a table function exposes a managed `IEnumerable` as a relation with `CardinalityHint` feeding the join planner, and a UDF exception resurfaces as a query error on the executing statement.
- Law: push rows through the appender when data must persist, expose a table function when it must only participate — the staging table for a single-query join is the foreclosed middle.
- Exemption: the drain loop over the chunk reader is the platform-forced ADO statement seam.

```csharp conceptual
public sealed record Sample(string Key, double Score, DateOnly Day);

public sealed class SampleMap : DuckDBAppenderMap<Sample> {
    public SampleMap() {
        Map(static sample => sample.Key);
        Map(static sample => sample.Score);
        Map(static sample => sample.Day);
    }
}

public static class BulkLane {
    public static Fin<int> Commit(DuckDBConnection lane, Seq<Sample> batch) {
        ArgumentNullException.ThrowIfNull(lane);
        return Try.lift(() => {
            using var bulk = lane.CreateAppender<Sample, SampleMap>("<table-a>");
            bulk.AppendRecords(batch);
            bulk.Close();
            return batch.Count;
        }).Run().MapFail(static error => Error.New(8102, $"<batch-refused:{error.Message}>"));
    }

    public static Fin<Seq<Sample>> Drain(DuckDBConnection lane, string projection) =>
        Try.lift(() => {
            using var command = lane.CreateCommand();
            (command.CommandText, command.UseStreamingMode) = (projection, true);
            using var stream = command.ExecuteReader();
            var drained = new List<Sample>();
            while (stream.Read()) {                                                // Exemption: the chunk drain fills a seam-local list frozen once by toSeq; per-row Seq.Add forcing is the rejected O(n²) form
                drained.Add(new Sample(
                    stream.GetFieldValue<string>(0), stream.GetFieldValue<double>(1), stream.GetFieldValue<DateOnly>(2)));
            }
            return toSeq(drained);
        }).Run().MapFail(static error => Error.New(8103, $"<drain-faulted:{error.Message}>"));
}
```

## [03]-[ARTIFACT_PROJECTION]

[EGRESS_ROWS]:
- Law: one `COPY (SELECT) TO` statement owns engine-mediated egress, and format, destination collision, and compression are closed `[SmartEnum<string>]` vocabularies whose `.Key` IS the COPY token — `Format.Parquet`/`Csv`/`Json`, `Collision.Overwrite`/`OverwriteOrIgnore`/`Append`, `Codec.Zstd`/`Snappy` interpolate beside the shared destination, the JSON case carrying its one `ARRAY` row selecting array-of-records versus newline-delimited — so a mistyped `OVERWRITE_OR_INGORE` is unrepresentable rather than a runtime SQL parse error, a second export path per format is the rejected form, a new format or posture is one static row, and a new flow is one instance of attach, read, project, copy.
- Law: the engine COPY rail is the SQL-mediated lane, not the egress monopoly — a zero-copy in-process columnar handoff and a direct managed file-codec are distinct lanes a COPY `FORMAT` token cannot express, so the lane is the artifact class's outer discriminant and a non-SQL egress lands as a sibling lane beside the COPY family, never as a `FORMAT` row; the rejected form is a `FORMAT` value stretched to name a transport the engine never performs.
- Law: row-group geometry is the unit of scan parallelism and zonemap pruning — `ROW_GROUP_SIZE` composes with `ROW_GROUP_SIZE_BYTES`, `ROW_GROUPS_PER_FILE`, and `FILE_SIZE_BYTES` as one geometry axis — groups near the default row count prune well, and tiny groups are the signature of append-per-batch exporters: batch through a staging table and export once.
- Law: partitioning is a pruning instrument, never a uniqueness scheme — `Append` writes new files beside existing generations, `PARTITION_BY` moves keys into hive directories with `FILENAME_PATTERN` naming the leaves, and the instrument prunes at cardinality in the tens to low thousands; partition columns are bare names, never expressions, so a derived partition key materializes as a projected column first.
- Law: `COPY ... TO` is a filesystem effect outside transaction rollback — publication composes the atomic-write protocol, never transactional cleanup.
- Law: the footer answers declared shape, per-row-group statistics, and caller stamps without decoding data — `parquet_schema`, `parquet_metadata`, `parquet_kv_metadata` — so artifact admission is a metadata-cost gate run on every delivery.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class Codec {
    public static readonly Codec Zstd = new("zstd");
    public static readonly Codec Snappy = new("snappy");
}

[SmartEnum<string>]
public sealed partial class Collision {
    public static readonly Collision Overwrite = new("OVERWRITE");
    public static readonly Collision OverwriteOrIgnore = new("OVERWRITE_OR_IGNORE");
    public static readonly Collision Append = new("APPEND");
}

[SmartEnum<string>]
public sealed partial class Format {
    public static readonly Format Parquet = new("parquet", None, grouped: true);
    public static readonly Format Csv = new("csv", None, grouped: false);
    public static readonly Format Json = new("json", Some("ARRAY true"), grouped: false);

    public Option<string> ArrayRow { get; }
    public bool Grouped { get; }
}

public sealed record ArtifactClass(string Name, Format Format, Codec Codec, int RowGroup, Option<string> PartitionKey, Collision Collision) {
    public static readonly ArtifactClass Ledger = new("<class-a>", Format.Parquet, Codec.Zstd, 122_880, None, Collision.Overwrite);
    public static readonly ArtifactClass Feed = new("<class-b>", Format.Json, Codec.Snappy, 122_880, Some("<key-a>"), Collision.Append);

    public string Egress(string projection, string destination, string stamp) =>
        $"COPY ({projection}) TO '{destination}' ({string.Join(", ",
            Seq(Some($"FORMAT {Format.Key}"), Some($"COMPRESSION {Codec.Key}"),
                Format.Grouped ? Some($"ROW_GROUP_SIZE {RowGroup}") : Option<string>.None, Format.ArrayRow,
                PartitionKey.Map(static key => $"PARTITION_BY ({key})"), Some(Collision.Key),
                Some($"KV_METADATA {{ stamp: '{stamp}' }}")).Somes())})";
}

public static class ProjectionRail {
    public static Fin<Unit> Publish(DuckDBConnection lane, ArtifactClass artifact, string projection, string destination, string stamp) =>
        Try.lift(() => {
            using var command = lane.CreateCommand();
            command.CommandText = artifact.Egress(projection, destination, stamp);
            return (command.ExecuteNonQuery(), unit).Item2;
        }).Run().MapFail(static error => Error.New(8104, $"<publish-refused:{error.Message}>"));

    public static Fin<string> StampOf(DuckDBConnection lane, string artifact) =>
        Try.lift(() => {
            using var command = lane.CreateCommand();
            command.CommandText = "SELECT decode(value) FROM parquet_kv_metadata($path) WHERE decode(key) = 'stamp'";
            command.Parameters.Add(new DuckDBParameter("path", artifact));
            return Optional(command.ExecuteScalar()).Map(static held => (string)held);
        }).Run().MapFail(static error => Error.New(8106, $"<footer-unreadable:{error.Message}>"))
          .Bind(static held => held.ToFin(Error.New(8105, "<unstamped-artifact>")));
}
```

[GENERATION_READS]:
- Law: ingest is `read_parquet` over a path, glob, or list — file enumeration is orthogonal to every read option, so one file growing into a generation directory changes the path argument and nothing else; `union_by_name` makes additive columns compatible by construction (absent reads NULL), `hive_partitioning` lifts directory keys, and `filename` plus `file_row_number` pin per-row provenance.
- Law: `FIELD_IDS` at export plus an id-keyed `schema` map at scan make renames non-breaking across generations — names absorb additions, ids absorb renames, and together they close the additive-evolution surface.
- Law: generations are immutable — compaction is a new artifact written beside the old with a new hash, never an in-place merge.
- Law: JSON shredding is admission, not manipulation — `read_json` inference is a development-time tool whose output freezes into an explicit `columns` struct, because sampling drift on sparse fields silently retypes columns between runs; `ignore_errors` applies only to newline-delimited layout, so NDJSON is the only fault-tolerant JSON ingest, and document collapse is engine vocabulary (`->`, `->>`, `json_transform`, `unnest`) — managed DOM walking plus re-insert is the rejected spelling.
- Law: shred to typed columns at admission when the document shape is settled; keep a JSON-typed column while the shape is still moving — the deciding question is shape motion, never preference.

## [04]-[DELIMITED_EXCHANGE]

[PROFILE_LAW]:
- Law: the default separator is the semicolon — comma exchange always declares `Sep.New(',')`; auto-detection counts candidates in row one only and is exploratory ingest, never a contract profile.
- Law: reader and writer harden as one pair — `Strict()` forces quotes-plus-unescape on the reader and escape on the writer, and one side hardened alone produces files the other cannot round-trip; the escape-off writer default writes separator-bearing values raw and corrupts silently, so any writer whose values are not provably separator-free declares `Escape` true.
- Law: the invariant-culture default is the round-trip guarantee — a culture row on one side without the other breaks numeric and temporal round-trips silently; temporal text crosses in the suite's settled invariant spelling, and `SepSpec` makes symmetry structural — a writer opened from a reader's `Spec` inherits the profile as a value pass.
- Law: ragged input is loud — column-count deviation throws at row advance carrying the physical line range, because a quoted column spans newlines and the row index diverges from lines exactly there; `DisableColCountCheck` is the explicit ragged opt-in moving absence to `TryGet`, and with a header `ColNotSetOption.Empty` is the absence spelling on write.
- Law: source and sink ownership is explicit — every stream arm carries `leaveOpen`, the default closes on dispose, so a shared stream passed bare is closed out from under its other consumers; the named-source arms thread a logical name into failure receipts without caller-side context.
- Law: header indices resolve once outside the loop from the same column rows the descriptor stamps — reader keys, writer emission, and the contract stamp share one declaration, and per-row name lookup re-pays hashing per row; name lookup is ordinal by default, so case-insensitive exchange declares `ColNameComparer` once for every lookup path, and a whole numeric block lifts in one `Cols` range `Parse<T>()` call, never a per-column loop.
- Exemption: the writer's row-commit block is the platform-forced disposable-row seam.

```csharp conceptual
public readonly record struct ColumnRow(string Name, string Type, bool Nullable);

public sealed record Measure(string Key, double Score);

public sealed record ExchangeProfile(char Separator, int PoolCap, Seq<ColumnRow> Columns) {
    public static readonly ExchangeProfile Partner = new(',', PoolCap: 64, [new("<col-a>", "VARCHAR", Nullable: false), new("<col-b>", "DOUBLE", Nullable: false)]);

    public Descriptor Stamp(string artifactClass, int revision) => new(artifactClass, revision, Columns);

    public SepReaderOptions Reader => Sep.Reader(o => o with {
        Sep = Sep.New(Separator),
        CultureInfo = CultureInfo.InvariantCulture,
        Unescape = true,
        Trim = SepTrim.AfterUnescape,
        CreateToString = SepToString.PoolPerColThreadSafe(maximumStringLength: PoolCap),
    });

    public SepWriterOptions Writer => Sep.Writer(o => o with {
        Sep = Sep.New(Separator),
        CultureInfo = CultureInfo.InvariantCulture,
        Escape = true,
        ColNotSetOption = SepColNotSetOption.Empty,
    });
}

public static class ExchangeSeam {
    public static Seq<Fin<Measure>> Sift(ExchangeProfile profile, string payload) {
        ArgumentNullException.ThrowIfNull(profile);
        using var reader = profile.Reader.FromText(payload);
        var keys = reader.Header.IndicesOf([.. profile.Columns.Map(static row => row.Name)]);
        return toSeq(reader.Enumerate(row =>
            row[keys[1]].TryParse<double>() is { } score
                ? Fin.Succ(new Measure(row[keys[0]].ToString(), score))
                : Fin.Fail<Measure>(Error.New(8201, $"<cell:{row.RowIndex}:{row.LineNumberFrom}-{row.LineNumberToExcl}>"))))
            .Strict();
    }

    public static string Emit(ExchangeProfile profile, Seq<Measure> admitted) {
        ArgumentNullException.ThrowIfNull(profile);
        using var writer = profile.Writer.ToText(capacity: 1024);
        admitted.Iter(measure => {
            using var line = writer.NewRow();
            line[profile.Columns[0].Name].Set(measure.Key);
            line[profile.Columns[1].Name].Format(measure.Score);
        });
        return writer.ToString();
    }
}
```

[ROW_AND_BUFFER]:
- Law: `Row`, `Col`, and `Cols` are ref-struct views over the reader's buffer — every escape attempt breaks at compile time — and `Enumerate` is lazy over the live reader, so projections materialize inside the reader's scope and reader-pooled `Parse<T>()` spans die at the next row advance; results that outlive the row take the caller-memory or array arms.
- Law: unescaping mutates the buffer in place — after any column access `Row.Span` holds garbage between columns — so raw-row reads happen before column access or the row materializes first; `Trim` is a two-phase flags axis (outer before unescape, after-unescape inside quotes), and only ASCII space trims, so tab-padded values survive verbatim.
- Law: strings are the pipeline's only allocation, routed once through `SepCreateToString` — low-cardinality columns approach zero steady-state allocation, `maximumStringLength` bounds pool eligibility as a memory cap, and parallel enumeration requires the thread-safe pool variants, a mismatch that surfaces only under parallel load.
- Law: `ParallelEnumerate` batches pooled row state into an ordered parallel projection — output order matches input by construction, parsing stays single-threaded so gains cap at the projection's share, and the degree overload consumes a budget row; the try-shape fuses parse-validate-filter in one pass — rejected rows do not emit, and receipts ride the row's own evidence identically in sequential and parallel runs.
- Law: one row-projection function per exchange profile serves all four modalities — sequential, async (`GetAsyncEnumerator` threads cancellation into row advance), parallel, try-filtered; modality-specific row handlers are the sprawl the profile deletes.
- Law: the reader-to-writer fusion threads the live reader row straight into the writer — `writerRow.Set(readerRow[range])` and `writerRow.Set(readerRow[colNames])` re-separate, re-escape, and reorder the source columns under the writer's own `Sep`, `Escape`, and culture policy through the `Set(SepReader.Cols)` overload, so the `Range`/name-indexer that views the source columns is the whole copy and parse-materialize-rebuild flows are the rejected spelling; `SepWriterHeader.Write` is the zero-row arm, producing the empty-but-valid artifact a delivery gate distinguishes from a missing one.

## [05]-[ARTIFACT_IDENTITY]

[STAMP_AND_DIFF]:
- Law: an artifact is payload plus two distinct identities — the byte-level content hash that the canonical octet codec mints once over stored bytes, and the descriptor-level `SchemaKey` that fingerprints column shape alone; identity placement follows the format's own metadata channel — columnar in the footer, delimited beside the file as a sidecar bound by content hash, never fake header rows — so a renamed artifact keeps its identity and a sidecar whose bytes no longer hash to its claim is corruption, not drift.
- Law: the descriptor is the one contract value — emission, stamping, and the admission gate all derive from one artifact-class declaration, so a column added to the projection updates writer, `SchemaKey`, and gate in one diff.
- Law: byte identity and descriptor equality are different contracts, never conflated — the supplied `ContentHash` is the one canonical octet codec the whole identity domain asserts once over stored bytes (never re-derived per call site, never recomputed from parsed-then-reserialized bytes), while `SchemaKey` fingerprints column shape so a newline convention or column reorder leaves it untouched as the content hash moves; the `SchemaKey` digest reuses that same `XxHash3` codec rather than opening a second hashing path, and re-keying by semantic equality requires canonical emission, never hash comparison of foreign bytes.
- Law: the diff is name-keyed set algebra under a declared compatibility lattice — additive columns are compatible by construction because consumers read by name and tolerate extras, a widening retype is a reviewed policy row, a narrowing retype never is, and removal or rename is a new artifact class; duplicate header names reject at the gate before any row is read.
- Law: revisions only increase — a consumer seeing an older revision than its compiled expectation distinguishes a stale producer from a corrupt artifact, two operational responses from one comparison.
- Law: delivery is a closed destination union whose every arm carries its own provenance — locator, stamp, hash — and a bundle member carries two identity levels, the container hash and its own; a string-typed destination parameter erases the per-arm obligation and reopens dispatch at runtime.
- Law: fidelity routes the format — columnar for typed exchange where types, nulls, and nesting survive; delimited only where a foreign consumer demands text, under the invariant strict profile that alone round-trips.

```csharp conceptual
public sealed record Descriptor(string ArtifactClass, int Revision, Seq<ColumnRow> Columns) {
    public ulong SchemaKey =>
        XxHash3.HashToUInt64(Encoding.UTF8.GetBytes(string.Join(';',
            Columns.Map(static row => $"{row.Name}:{row.Type}:{(row.Nullable ? "N" : "R")}"))));
}

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Verdict {
    private Verdict() { }
    public sealed record Compatible(Seq<string> Added) : Verdict;
    public sealed record StaleProducer(int Held, int Observed) : Verdict;
    public sealed record ContractBreak(Seq<string> Violations) : Verdict;
}

public sealed record Lattice(Seq<(string From, string To)> Retype, bool NullWiden) {
    public static readonly Lattice Canonical = new([("INTEGER", "BIGINT"), ("FLOAT", "DOUBLE")], NullWiden: true);

    public Verdict Diff(Descriptor held, Descriptor observed) =>
        observed.Revision < held.Revision
            ? new Verdict.StaleProducer(held.Revision, observed.Revision)
            : observed.Columns.Map(static row => row.Name).Distinct().Count != observed.Columns.Count
                ? new Verdict.ContractBreak(["<duplicate-header>"])
                : held.Columns.Choose(row =>
                    observed.Columns.Find(peer => peer.Name == row.Name) switch {
                        { IsSome: true, Case: ColumnRow peer } => Admits(row, peer)
                            ? None
                            : Some($"<retyped:{row.Name}:{row.Type}->{peer.Type}>"),
                        _ => Some($"<removed:{row.Name}>"),
                    }) is { IsEmpty: false } violations
                    ? new Verdict.ContractBreak(violations)
                    : new Verdict.Compatible(
                        observed.Columns.Filter(peer => !held.Columns.Exists(row => row.Name == peer.Name))
                            .Map(static peer => peer.Name));

    bool Admits(ColumnRow held, ColumnRow observed) =>
        (observed.Type == held.Type || Retype.Exists(step => step == (held.Type, observed.Type)))
        && (observed.Nullable == held.Nullable || (NullWiden && observed.Nullable && !held.Nullable));
}

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Delivery {
    private Delivery() { }
    public sealed record FileArtifact(string Path, Descriptor Stamp, string ContentHash) : Delivery;
    public sealed record ObjectArtifact(string Bucket, string Key, Descriptor Stamp, string ContentHash) : Delivery;
    public sealed record BundleMember(string Bundle, string Member, string BundleHash, Descriptor Stamp, string ContentHash) : Delivery;

    public (string Locator, Descriptor Stamp, string Identity) Provenance => this.Switch(
        fileArtifact:   static arm => (arm.Path, arm.Stamp, arm.ContentHash),
        objectArtifact: static arm => ($"{arm.Bucket}/{arm.Key}", arm.Stamp, arm.ContentHash),
        bundleMember:   static arm => ($"{arm.Bundle}#{arm.Member}", arm.Stamp, $"{arm.BundleHash}:{arm.ContentHash}"));

    public Fin<(string Locator, string Identity, Seq<string> Added)> Admit(Lattice lattice, Descriptor held) {
        ArgumentNullException.ThrowIfNull(lattice);
        var (locator, stamp, identity) = Provenance;
        return lattice.Diff(held, stamp).Switch(
            compatible:    static (s, arm) => Fin.Succ((s.Locator, s.Identity, arm.Added)),
            staleProducer: static (s, arm) => Fin.Fail<(string, string, Seq<string>)>(Error.New(8401, $"<stale-producer:{s.Identity}:{arm.Observed}<{arm.Held}>")),
            contractBreak: static (s, arm) => Fin.Fail<(string, string, Seq<string>)>(Error.New(8402, $"<contract-break:{s.Identity}:{string.Join(',', arm.Violations)}>")),
            state: (Locator: locator, Identity: identity));
    }
}
```

## [06]-[GEO_INTERCHANGE]

[TEXT_RAIL]:
- Law: NetTopologySuite geometry is the single interior geo vocabulary, and GeoJSON text and the GeoPackage blob are its only two wire projections — a store-to-feed flow is decode-blob, interior, encode-text, never a direct transcode — so coordinate DTOs, vendor geometry types, and raw coordinate arrays are rejected shapes.
- Law: the converter-factory row is the whole text wire profile — geometry, features, collections, and attribute tables all answer to one registration, and the factory composes beside generated strict contexts as a runtime-converter row in one options merge; a per-type converter registration scatters the five policies into independent drift, and two partner id conventions are two factory rows on two options instances, never post-read id patching.
- Law: precision is admission-side only — the reader applies the factory's `PrecisionModel` to X and Y as coordinates parse while writers emit stored doubles raw — so bounding wire precision and stabilizing emitted-text hashes means constructing under the fixed-precision factory before serialization; XY and XYZ round-trip while XYM and XYZM degrade silently, so measure-bearing data routes through the blob projection.
- Law: ring orientation enforcement is write-only — `EnforceRfc9746` reverses mis-oriented rings at emission while reads admit any orientation — so a kernel deriving sign from ring direction normalizes at admission, because the wire law will not have done it.
- Law: the rejection taxonomy rides `JsonException` with one escape — an unrecognized `type` literal throws an unpositioned argument fault — so the boundary capture admits both classes or malformed literals bypass the wire-fault rail; JSON null is null geometry, the rail's one null, projected to absence immediately, and unknown members and comments skip structurally.
- Law: CRS posture is fixed by the format — WGS84 longitude/latitude, no CRS member — so reprojection happens in the interior, and emitting projected coordinates is silent corruption no reader can detect.
- Law: feature properties stay element-backed until projected — `IPartiallyDeserializedAttributesTable.TryDeserializeJsonObject<T>(options, out var typed)` re-runs the passed `JsonSerializerOptions` over the deferred property object and a false return is absence — and walking the loose `IAttributesTable` in domain code is the rejected form; element-backed `Count` re-enumerates the object per call.

```csharp conceptual
public sealed record GeoProfile(double Precision, bool WriteBBox, string IdProperty) {
    public static readonly GeoProfile Wire = new(Precision: 1e6, WriteBBox: true, IdProperty: "id");

    public GeometryFactory Admission => new(new PrecisionModel(Precision), 4326);

    public JsonSerializerOptions Compose(IJsonTypeInfoResolver contracts) {
        var options = new JsonSerializerOptions { TypeInfoResolver = contracts };
        options.Converters.Add(new GeoJsonConverterFactory(Admission, WriteBBox, IdProperty,
            RingOrientationOption.EnforceRfc9746, allowModifyingAttributesTables: false));
        options.MakeReadOnly();
        return options;
    }
}

public static class GeoSeam {
    public static Fin<Option<Geometry>> Admit(JsonSerializerOptions wire, string payload) =>
        Try.lift(() => Optional(JsonSerializer.Deserialize<Geometry>(payload, wire))).Run()
            .MapFail(static error => error.Exception.Case switch {
                JsonException structural => Error.New(8301, $"<wire-fault:{structural.Path}:{structural.Message}>"),
                ArgumentException typeLiteral => Error.New(8302, $"<unknown-type-literal:{typeLiteral.Message}>"),
                _ => error,
            });

    public static string Emit(JsonSerializerOptions wire, Geometry admitted) =>
        JsonSerializer.Serialize(admitted, wire);
}
```

[BLOB_AND_CONTAINER]:
- Law: the blob is a header — `GP` magic, version, flags packing endianness, envelope kind, and the empty bit, SRID, optional envelope — followed by a WKB body; raw WKB readers cannot parse it, the magic at offset zero is the signature gate before any typed decode, and the header, never the WKB body, is the single SRID authority.
- Law: codec policy freezes per container profile — `HandleSRID` on, `RepairRings` a declared tolerance (a repaired blob re-emits different bytes, so byte-identity flows and repair are mutually exclusive rows), `HandleOrdinates` capped by the coordinate-sequence capability — and the writer's ordinate policy derives both body dimensionality and header envelope kind, so the two cannot disagree.
- Law: empty geometries are header-coded — the NaN-coded empty point remaps by flag at read, so consumers never see NaN coordinates and empty round-trips by contract.
- Law: the container is an embedded store with a three-table metadata spine binding each feature table to exactly one geometry column and SRID — a vector layer is spine rows plus a feature table, multi-geometry entities are multiple layers joined on the integer id key, and store mechanics arrive as settled embedded-store law.
- Law: spatial query is two-phase by construction — R-tree envelope candidates keyed on the integer primary key, then exact predicates on decoded geometries for the candidate set only — because envelope-only answers are wrong in proportion to shape elongation; header envelopes feed index maintenance without re-decoding WKB, and bulk loads drop and rebuild the index — trigger maintenance and bulk rebuild are mutually exclusive within one load, and the staleness gate catches protocol violations after the fact.
- Law: a layer write is one transaction over feature row, index row, and contents extent — a stale denormalized extent misleads every discovery consumer, so write paths maintain it or mark it unknown.
- Law: container admission gates cheapest-first — application identifier, spine presence, declared-versus-sampled SRID agreement, index staleness — so rejection cost is proportional to how wrong the artifact is, and a finished container is itself a delivery arm: single file, spine-described layers, path plus content hash as provenance.

```csharp conceptual
public sealed record BlobCodec(Ordinates Cap, bool RepairRings) {
    public static readonly BlobCodec Container = new(Ordinates.XYZ, RepairRings: false);

    public GeoPackageGeoReader Reader => new() { HandleSRID = true, RepairRings = RepairRings, HandleOrdinates = Cap };
    public GeoPackageGeoWriter Writer => new() { HandleOrdinates = Cap };
}

public static class BlobGate {
    static ReadOnlySpan<byte> Magic => "GP"u8;

    public static Fin<Geometry> Admit(BlobCodec codec, byte[] blob, int declaredSrid) =>
        blob.AsSpan().StartsWith(Magic)
            ? Try.lift(() => codec.Reader.Read(blob)).Run()
                .MapFail(static error => Error.New(8311, $"<blob-undecodable:{error.Message}>"))
                .Bind(decoded => decoded.SRID == declaredSrid
                    ? Fin.Succ(decoded)
                    : Fin.Fail<Geometry>(Error.New(8312, $"<srid-disagreement:{declaredSrid}:{decoded.SRID}>")))
            : Fin.Fail<Geometry>(Error.New(8313, "<not-a-geopackage-blob>"));

    public static Fin<byte[]> Emit(BlobCodec codec, Geometry admitted) =>
        Try.lift(() => {
            using var sink = new MemoryStream();
            codec.Writer.Write(admitted, sink);
            return sink.ToArray();
        }).Run().MapFail(static error => Error.New(8314, $"<blob-unwritable:{error.Message}>"));
}
```
