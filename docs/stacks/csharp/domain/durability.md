# [DURABILITY]

Embedded durability is one store law with four layers under one epoch fence. Every process reaches a store file through one idempotent open ritual whose rows are declared data; every durable artifact seals under one fixed-offset header that is the artifact's entire trust boundary; every durable mutation is one op-log row adjudicated by a last-writer-wins lattice inside the store's own transaction; every stored byte's lifecycle is a class row swept by one receipted fold. MessagePack and its generated formatters are legislated here for the whole suite; causal stamps and classification verdicts arrive settled and are compared, never re-derived; the sync wire is composed, never owned. Restore is the capstone choreography — fence, verify, materialize, sidecar-clear, atomic-rename, epoch-bump, reopen — every step receipted, never best-effort, and the one epoch token fences the open ritual, the sync cursors, and the artifact headers, so recovery anywhere is the normal path with a wider range. Growth lands as rows: a new pragma is a ritual row, a new entity family one kind row plus one formatter case, a new artifact type one class row, a new codec posture one profile selection.

## [01]-[DURABILITY_CHOOSER]

This table routes a durability concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]                 | [OWNER]                                | [REJECTED_FORM]                         |
| :-----: | :------------------------ | :------------------------------------- | :-------------------------------------- |
|  [01]   | store open and migration  | one idempotent ritual fold             | per-process bootstrap branches          |
|  [02]   | write transactions        | IMMEDIATE begin + savepoint units      | deferred-then-write                     |
|  [03]   | cross-process change      | `data_version` register probe          | notification bus, table polling         |
|  [04]   | store maintenance         | receipted schedule verb table          | ad-hoc vacuum, best-effort backup       |
|  [05]   | binary contract           | dense keys + generated resolver        | typeless payloads, map-mode insurance   |
|  [06]   | codec policy              | one frozen profile row per store class | call-site serializer options            |
|  [07]   | artifact commit           | sealed header + atomic rename          | in-place write, verify-by-success       |
|  [08]   | restore                   | seven-step receipted choreography      | best-effort file copy                   |
|  [09]   | durable mutation and sync | one op-log + guarded set adjudication  | per-kind logs, local fast path          |
|  [10]   | deletion and preservation | class rows + hold-first sweep fold     | unreceipted cleanup, export-to-preserve |

## [02]-[EMBEDDED_STORE]

[RITUAL_LAW]:
- Law: every connection in every process folds the same declared sequence — identity check, per-connection rows, hardening, capability registration, IMMEDIATE migration gate, epoch read — idempotent end-to-end, so bootstrap, crash-recovery reopen, and steady-state open are one fold with no first-process special case, and the ritual table is the audit surface: diffing two processes' rituals is diffing two declarations.
- Law: pragma rows carry residency — file-persistent rows (`journal_mode`, `page_size`, `auto_vacuum`, `application_id`, `user_version`) belong to provisioning and the ritual folds only per-connection rows; `synchronous=NORMAL` is the WAL throughput row whose loss boundary is the last commits and never corruption, and FULL stays the row for store classes whose single commit is the artifact of record.
- Law: first-opener-migrates — the register check and the DDL share one IMMEDIATE transaction, losers blocked on the lock observe the bumped register on acquisition and no-op, and a register ahead of the compiled expectation is a typed rejection; correctness needs no leader election.
- Law: capability registration is connection-instance-scoped and never persisted — schema-resident functions, aggregates, and collations register before the first statement or the file is unreadable, and the schema-resident flag sorts the rows mechanically; `isDeterministic: true` is a capability grant admitting the function into expression indexes and generated columns, a seeded `CreateAggregate` ships a domain fold to the rows, and hybrid text, spatial, and document predicates compose as rowid joins where each virtual-table index prunes its own dimension.
- Reject: a nonzero `busy_timeout` (the provider already retries BUSY and LOCKED at 150 ms quanta until `DefaultTimeout`, so a native sleep beneath the managed loop multiplies budgets), `locking_mode=EXCLUSIVE`, shared-cache, network-filesystem hosts, cross-ATTACH invariants under WAL, double-quoted string literals (`DQS=0` makes them prepare-time syntax errors — identifiers quote with `"`, strings with `'`), the `Password` row (the admitted bundle has no cipher — it fails at open), and any file replacement without `SqliteConnection.ClearPool` first — an open pooled handle pins the deleted inode and its readers silently continue against the dead store.
- Exemption: the ritual's command kernel is the platform-forced ADO statement seam.

```csharp conceptual
public readonly record struct RitualFact(string Row, long Applied);

public sealed record StoreRitual(long Identity, long CompiledEpoch,
    Seq<(string Row, string Sql)> ConnectionRows, Seq<(string Row, Action<SqliteConnection> Grant)> Capabilities) {
    public static readonly StoreRitual Canonical = new(Identity: 0x5241_5731, CompiledEpoch: 3,
        ConnectionRows: [("<row-throughput>", "PRAGMA synchronous=NORMAL"), ("<row-wal-bound>", "PRAGMA journal_size_limit=8388608"),
            ("<row-spill>", "PRAGMA temp_store=MEMORY"), ("<row-budget>", "PRAGMA cache_size=-32768")],
        Capabilities: [
            ("<fn-rank>", static store => store.CreateFunction("<fn-rank>", (string key) => key.Length, isDeterministic: true)),
            ("<agg-peak>", static store => store.CreateAggregate("<agg-peak>", 0L, (long held, long next) => Math.Max(held, next), isDeterministic: true))]);
}

public static class StoreOpen {
    const int Defensive = 1010;

    public static SqliteConnection Dialed(string path) => new(new SqliteConnectionStringBuilder {
        DataSource = path, Mode = SqliteOpenMode.ReadWriteCreate, Pooling = true, ForeignKeys = true,
    }.ConnectionString);

    public static Fin<Seq<RitualFact>> Fold(SqliteConnection store, StoreRitual ritual, Action<SqliteConnection, SqliteTransaction, long> step) {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(ritual);
        ArgumentNullException.ThrowIfNull(step);
        store.Open();
        var identity = Scalar(store, null, "PRAGMA application_id");
        if (identity != ritual.Identity && identity != 0L) { return Refused(store, 7701, $"<foreign-store:{identity:x8}>"); }
        var facts = ritual.ConnectionRows.Map(row => new RitualFact(row.Row, Execute(store, null, row.Sql)));
        _ = raw.sqlite3_db_config(store.Handle, Defensive, 1, out var hardened);
        facts += ritual.Capabilities.Map(row => (fun(() => row.Grant(store))(), new RitualFact(row.Row, 1)).Item2);
        using var gate = store.BeginTransaction(IsolationLevel.Serializable, deferred: false);
        var held = Scalar(store, gate, "PRAGMA user_version");
        if (held > ritual.CompiledEpoch) { return Refused(store, 7702, $"<epoch-ahead:{held}:{ritual.CompiledEpoch}>"); }
        if (held < ritual.CompiledEpoch) {
            step(store, gate, held);
            _ = Execute(store, gate, $"PRAGMA application_id={ritual.Identity}");
            _ = Execute(store, gate, $"PRAGMA user_version={ritual.CompiledEpoch}");
        }
        gate.Commit();
        return Fin.Succ(facts.Add(new RitualFact("<row-defensive>", hardened))
            .Add(new RitualFact("<row-epoch>", Math.Max(held, ritual.CompiledEpoch))));
    }

    static Fin<Seq<RitualFact>> Refused(SqliteConnection store, int code, string detail) =>
        (fun(store.Dispose)(), Fin.Fail<Seq<RitualFact>>(Error.New(code, detail))).Item2;

    static long Execute(SqliteConnection store, SqliteTransaction? gate, string sql) {
        using var command = store.CreateCommand();
        return ((command.Transaction, command.CommandText) = (gate, sql), command.ExecuteNonQuery()).Item2;
    }

    static long Scalar(SqliteConnection store, SqliteTransaction? gate, string sql) {
        using var command = store.CreateCommand();
        return ((command.Transaction, command.CommandText) = (gate, sql), Convert.ToInt64(command.ExecuteScalar(), CultureInfo.InvariantCulture)).Item2;
    }
}
```

[WAL_AND_VERBS]:
- Law: any transaction that may write begins IMMEDIATE — `BeginTransaction(IsolationLevel.Serializable, deferred: false)` — because a deferred read transaction attempting its first write after another writer committed holds a stale snapshot whose BUSY_SNAPSHOT surfaces as plain BUSY at default code granularity, burning the whole busy budget on a retry that cannot succeed; the retry partition is BUSY retry-correct, LOCKED waits on nothing external, and CORRUPT or NOTADB is terminal and routes to restore, with `raw.sqlite3_extended_result_codes` upgrading the running taxonomy where receipts must discriminate.
- Law: WAL coordination rides same-host shared memory, and the `-wal`/`-shm` sidecar set — never the bare file — is the unit of copy, replace, and deletion; a main file separated from its sidecars is page-level silent corruption recovery cannot detect.
- Law: readers never block the writer and exactly one writer commits — multi-process write topology is contention-managed serialization, so BUSY is a steady-state signal; continuously overlapping readers starve checkpoints and the WAL grows unbounded, the countermeasure is a scheduled TRUNCATE row plus short read transactions by construction, and `raw.sqlite3_wal_checkpoint_v2`'s out-parameters are the typed checkpoint receipt whose BUSY refusal the schedule retries rather than escalates.
- Law: `PRAGMA data_version` moves only when another connection commits — the polling-free cross-process change probe; an unchanged register proves cache validity without touching tables and short-circuits all downstream invalidation.
- Law: STRICT tables are the typed admission gate — mismatched writes are statement errors, `ANY` is the declared per-column escape; `WITHOUT ROWID` clusters storage on the key but forecloses incremental blob streaming — the large-payload lane is `SqliteBlob` over a `zeroblob(N)` preallocation, fixed-size once written, its handle aborting when any writer mutates the row — so the two storage forms are chosen per table by access pattern, and `RETURNING` supersedes write-then-read identity round trips.
- Law: maintenance is one receipted schedule table — TRUNCATE checkpoint, `PRAGMA optimize`, `incremental_vacuum(N)`, integrity tiers, backup route — each row carrying cadence, budget, and receipt shape, with receipts as the verbs' native out-channels lifted onto the fact stream; the integrity ladder orders boot `quick_check`, cycle `integrity_check` plus `foreign_key_check` (FK violations never surface from integrity checks), and a deeper tier failing routes to restore, never retry; WAL snapshot pins and TRUNCATE checkpoints are adversaries — a pinned read window blocks truncation and truncation kills pins — so one schedule owns both rows and interleaves them, and a lost pin is a receipted failure, never a silent rewind.
- Law: the backup chooser is policy rows on one verb — `BackupDatabase` restarts under other-connection writes so hot stores back up on the writing connection, the paced raw backup yields bounded latency and progress receipts, `VACUUM INTO` produces a compacted point-in-time copy through one read transaction without blocking writers — and a copy is admitted only after `quick_check` on the copy itself plus content identity, because the verb succeeding is never the proof.

## [03]-[CODEC_PROFILES]

[CONTRACT_LAW]:
- Law: the integer `[Key]` sequence IS the wire schema — dense and append-only, a retired key never reassigned because reuse silently re-types history; `[MessagePack.Union]` tags obey the same retirement law, sparse keys buy nothing while costing a nil slot per record, and a written nil is byte-identical to a retired-key gap, so absence never rides key gaps — it is an explicit option-shaped member.
- Law: `[GeneratedMessagePackResolver]` derives the module's formatter closure at compile time — AOT-true, reflection-free — and the analyzer gates unkeyed members, colliding formatters, and missing union declarations at build, so contract drift is a build diagnostic, never a first-restore discovery; generated domain owners cross the binary codec through `ThinktectureMessageFormatterResolver.Instance` as bare key values, `[SerializationConstructor]` pins admission among constructors, and `[IgnoreMember]` excludes derivable state — contract declarations, not conveniences.
- Reject: the typeless lane (payloads carrying type names are a deserialization gadget surface coupling stored bytes to assembly identity), the wrapper-object encoding of keyed owners (double payload, leaked owner internals), per-type formatter registration beside the resolver chain, and map mode as evolution insurance — the sealed header owns evolution, so self-describing payloads are redundant weight.

[PROFILE_LAW]:
- Law: `CompositeResolver.Create` resolves first-match-wins and caches per closed generic type — resolver order is a boot-time declaration and late registration is unrepresentable; specificity decreases monotonically down the chain: explicit formatters, generated-domain, generated-contract, standard fallback.
- Law: options are immutable and each store profile freezes one value — a call-site `With*` forks codec policy invisibly; a profile is one row each from the codec, compression, and hash axes — the codec axis closing at three rows, text, binary, and raw pass-through, where the raw row is never re-framed because double-framing destroys the identity its content key hashed — so a new posture is row selection, never code.
- Law: the restore lane always reads under `WithSecurity(MessagePackSecurity.UntrustedData)` plus two independent ceilings — a restored blob's provenance is unprovable even for bytes the same process wrote, because they crossed a rest boundary, and the write lane keeps the trusted default so hardening restore costs writes nothing; `WithMaximumObjectGraphDepth` catches the deep-narrow recursion a byte budget cannot see, while `WithMaximumDecompressedSize` is the decompression-bomb ceiling the depth cap is blind to — a kilobyte of `Lz4BlockArray` inflating to gigabytes — so the size ceiling is the class's own `MaxBytes` retention budget reused as the inflation bound, not a second constant, and `UntrustedData`'s 64 MB default is a ceiling to declare against the class, never a default to inherit silently.
- Law: `Lz4BlockArray` is the binary default — independently compressed blocks, streaming-decompressible; `CompressionMinLength` makes observed encoding diverge from requested policy, so receipts read the payload and never the policy, and decompression is extension-header-driven — the compression row is write-side policy only and segment files mix compressed and plain documents freely.
- Law: `MessagePackStreamReader.ReadAsync` yields one complete message per read with framing invariant under compression, so append streams and log segments need no custom framing; every serializer entry point threads cancellation, so artifact encode and decode participate in drain without a kill switch.
- Exemption: the segment reader loop is the platform-forced stream statement seam.

```csharp conceptual
[ValueObject<string>]
public readonly partial struct SlotKey;

[Union]
[MessagePack.Union(0, typeof(Artifact.Full))]
[MessagePack.Union(1, typeof(Artifact.Delta))]
public abstract partial record Artifact {
    private Artifact() { }

    [MessagePackObject]
    public sealed record Full([property: Key(0)] SlotKey Slot, [property: Key(1)] long Stamp, [property: Key(2)] ReadOnlyMemory<byte> Image) : Artifact;

    [MessagePackObject]
    public sealed record Delta([property: Key(0)] SlotKey Slot, [property: Key(1)] long Stamp, [property: Key(2)] ReadOnlyMemory<byte> Patch, [property: Key(3)] long Basis) : Artifact;
}

[GeneratedMessagePackResolver]
public sealed partial class ContractResolver;

[SmartEnum<string>]
public sealed partial class CodecProfile {
    static readonly MessagePackSerializerOptions Binary = MessagePackSerializerOptions.Standard
        .WithResolver(CompositeResolver.Create(
            ThinktectureMessageFormatterResolver.Instance,
            ContractResolver.Instance,
            StandardResolver.Instance))
        .WithCompression(MessagePackCompression.Lz4BlockArray);

    public static readonly CodecProfile Document = new("<profile-binary>", Binary, framed: true);
    public static readonly CodecProfile Passthrough = new("<profile-raw>", Binary, framed: false);

    MessagePackSerializerOptions Write { get; }
    bool Framed { get; }

    MessagePackSerializerOptions Restore(long maxBytes) =>
        Write.WithSecurity(MessagePackSecurity.UntrustedData
            .WithMaximumObjectGraphDepth(64)
            .WithMaximumDecompressedSize((int)Math.Min(maxBytes, int.MaxValue)));

    public Unit Encode(IBufferWriter<byte> sink, Artifact artifact, CancellationToken token) =>
        Framed ? fun(() => MessagePackSerializer.Serialize(sink, artifact, Write, token))()
               : fun(() => sink.Write(artifact.Switch(
                     full:  static f => f.Image,
                     delta: static d => d.Patch).Span))();

    public Fin<Artifact> Decode(ReadOnlySequence<byte> stored, long maxBytes, CancellationToken token) =>
        Framed
            ? Try.lift(() => MessagePackSerializer.Deserialize<Artifact>(stored, Restore(maxBytes), token))
                .Run()
                .MapFail(static error => Error.New(7748, $"<tier-8:contract-drift:{error.Message}>"))
            : Fin.Fail<Artifact>(Error.New(7749, $"<raw-passthrough-never-reframed:{Key}>"));

    public async IAsyncEnumerable<Fin<Artifact>> Segments(Stream lane, long maxBytes, [EnumeratorCancellation] CancellationToken token = default) {
        using var reader = new MessagePackStreamReader(lane, leaveOpen: true);
        while (await reader.ReadAsync(token).ConfigureAwait(false) is { } frame) {
            yield return Decode(frame, maxBytes, token);
        }
    }
}
```

## [04]-[SEALED_ARTIFACTS]

[SEAL_LAW]:
- Law: the header is a fixed-width little-endian prologue outside any codec — magic, header version, codec row, observed compression, hash domain, contract stamp, plain and stored lengths, content hash, epoch, header checksum — read by offset under failure conditions; a variable-length header re-introduces a parser exactly where the design removes one, and the header's own checksum separates header corruption (terminal for the copy) from payload corruption (replica and salvage routes).
- Law: the header records what WAS done, never what was requested — the incompressible `Encode` fallback and the minimum-length skip both split policy from outcome; the content hash covers stored bytes by default so verification strictly precedes any decoder, and the class seed partitions identity space so one flat content-addressed store serves every class with no class column — a seed change is identity migration, epoch-gated, never casual.
- Law: the content hash is the persisted-artifact identity domain — the seeded `XxHash3.HashToUInt64` the integrity card owns reused verbatim as the one codec, the class seed its domain partition, never a second hashing path beside the in-memory cache key or the wire frame check; the header records the hash domain so a reader knows which codec verified it, and the seed is the only artifact-class discriminant the flat store carries.
- Law: the single-pass seal — placeholder header, payload, seek to zero, final header, flush-to-disk, rename — leaves the artifact invalid (zeroed magic) at every instant before the final header lands, so partial writes self-reject with no tombstone or lock file; the temp is a same-directory sibling because cross-volume moves degrade to copy-plus-delete, and flush strength is a protocol row — flush-once-before-rename or write-through — with the same rename commit point either way.
- Law: sealed artifacts are write-once — amendment is a new artifact plus identity change, since in-place patching invalidates the hash, the header, and every manifest citation; directory-entry durability is unreachable from managed code, the one named accepted residual, and `File.Replace` is the row retaining the displaced incumbent as its own rollback.
- Exemption: the seal kernel — the rented-buffer lease, the stream writes, and the catch arm — is the platform-forced stream statement seam.

```csharp conceptual
public readonly record struct SealReceipt(string Path, long PlainLength, long StoredLength, bool Compressed, ulong ContentKey);

public static class Seal {
    public const int HeaderSize = 56;
    public const ulong Magic = 0x3153_4C41_4553_5253;
    public const byte HeaderVersion = 1, CodecBinary = 1, CompressionNone = 0, CompressionLz4 = 1, HashStoredDomain = 0, Contract = 2;

    public static Fin<SealReceipt> Commit(string path, ReadOnlySpan<byte> plain, long epoch, LZ4Level level, long classSeed) {
        var staged = $"{path}.{epoch}.staged";
        var target = ArrayPool<byte>.Shared.Rent(LZ4Codec.MaximumOutputSize(plain.Length));
        try {
            var encoded = LZ4Codec.Encode(plain, target, level);
            ReadOnlySpan<byte> stored = encoded > 0 && encoded < plain.Length ? target.AsSpan(0, encoded) : plain;
            var content = XxHash3.HashToUInt64(stored, classSeed);
            Span<byte> header = stackalloc byte[HeaderSize];
            using (var sink = new FileStream(staged, FileMode.Create, FileAccess.Write, FileShare.None)) {
                sink.Write(header);
                sink.Write(stored);
                Pack(header, plain.Length, stored.Length, stored.Length != plain.Length, content, epoch);
                sink.Position = 0;
                sink.Write(header);
                sink.Flush(flushToDisk: true);
            }
            File.Move(staged, path, overwrite: true);
            return Fin.Succ(new SealReceipt(path, plain.Length, stored.Length, stored.Length != plain.Length, content));
        }
        catch (Exception ex) when (ex is not OperationCanceledException) {
            return Fin.Fail<SealReceipt>(Error.New(7712, $"<seal:{ex.Message}>"));
        }
        finally { ArrayPool<byte>.Shared.Return(target); }
    }

    static void Pack(Span<byte> header, long plain, long stored, bool compressed, ulong content, long epoch) {
        BinaryPrimitives.WriteUInt64LittleEndian(header, Magic);
        (header[8], header[9], header[10], header[11], header[12]) =
            (HeaderVersion, CodecBinary, compressed ? CompressionLz4 : CompressionNone, HashStoredDomain, Contract);
        BinaryPrimitives.WriteInt64LittleEndian(header[16..], plain);
        BinaryPrimitives.WriteInt64LittleEndian(header[24..], stored);
        BinaryPrimitives.WriteUInt64LittleEndian(header[32..], content);
        BinaryPrimitives.WriteInt64LittleEndian(header[40..], epoch);
        BinaryPrimitives.WriteUInt64LittleEndian(header[48..], XxHash3.HashToUInt64(header[..48]));
    }
}
```

[LADDER_AND_RESTORE]:
- Law: the rejection ladder is ordered so each tier verifies before the next runs and restore never best-efforts past any tier — magic and identity, header version, header checksum, stored-length truncation with byte counts, and content hash all run on raw bytes with zero decoding; codec and compression capability, the contract-stamp ratchet, and untrusted decode gate the codec machinery only after — the order is the threat model, because corrupted input rejects before any parser with attack surface runs, and every rejection is a typed receipt naming tier, artifact identity, and the evidence pair the tier compared; version and contract are one-way ratchets — readers admit at or below their compiled ceiling, writers emit exactly theirs — so tier-2 future layouts, tier-6 capability gaps, and tier-7 contract skew are deployment evidence, not data errors: rejected by one process and restored by a newer sibling, they localize a rollout fault without touching the artifact.
- Law: the crash matrix is total — before flush an orphan temp (swept), after flush a complete-but-unclaimed orphan (a receipted salvage candidate, because the sealed header makes completeness provable), after rename the open ritual's epoch reconcile re-runs verification, after the bump committed; the orphan sweep keys on the deterministic epoch-bearing temp suffix, and ladder receipts from sweeps land on the boot fact stream with the same routing as any fault; the boot identity manifest of per-asset content keys is itself a sealed artifact verified first — the verifier of everything is the one thing the ladder alone proves.
- Law: restore composes the write protocol in reverse — one protocol vocabulary, one receipt taxonomy, the only asymmetry who supplies the bytes; the writer's commit point is the rename, the restorer's is the epoch bump, and everything before either commit point is repeatable garbage by construction.
- Law: the sidecar fence precedes the payload rename — a fresh payload paired with a stale `-wal` is a corruption mode, not a recoverable state — and every step is receipted with the ledger flushed on failure, so a half-restored store classifies unambiguously at the next open instead of being inspected ad hoc.
- Exemption: the choreography's step kernels — the pool fence, file materialization, and register bump — are the platform-forced ADO and stream statement seam.

```csharp conceptual
public readonly record struct StepFact(string Step, string Evidence);

public static class Restore {
    public static (Seq<StepFact> Ledger, Fin<long> Outcome) Run(
        string storePath, byte[] artifact, long successor, long classSeed, Func<string, Fin<Seq<RitualFact>>> reopen) {
        ArgumentNullException.ThrowIfNull(artifact);
        ArgumentNullException.ThrowIfNull(reopen);
        var staged = $"{storePath}.{successor}.staged";
        Seq<(string Step, Func<Fin<string>> Act)> steps = [
            ("<fence>", () => Guarded(7751, () => { using var pinned = StoreOpen.Dialed(storePath); SqliteConnection.ClearPool(pinned); return "<pool-cleared>"; })),
            ("<verify>", () => Ladder(artifact, classSeed)),
            ("<materialize>", () => Guarded(7752, () => Materialized(staged, artifact))),
            ("<sidecar>", () => Guarded(7753, () => { File.Delete($"{storePath}-wal"); File.Delete($"{storePath}-shm"); return "<sidecars-cleared>"; })),
            ("<rename>", () => Guarded(7754, () => { File.Move(staged, storePath, overwrite: true); return storePath; })),
            ("<epoch-bump>", () => Guarded(7755, () => Bumped(storePath, successor))),
            ("<reopen>", () => reopen(storePath).Map(static receipt => $"<ritual-rows:{receipt.Count}>")),
        ];
        return steps.Fold((Ledger: Seq<StepFact>(), Outcome: Fin.Succ(successor)), (state, step) =>
            state.Outcome.IsFail ? state
            : step.Act().Match(
                Succ: evidence => (state.Ledger.Add(new StepFact(step.Step, evidence)), state.Outcome),
                Fail: refusal => (state.Ledger.Add(new StepFact(step.Step, refusal.Message)), Fin.Fail<long>(refusal))));
    }

    static Fin<string> Ladder(byte[] artifact, long classSeed) =>
        artifact.Length < Seal.HeaderSize || BinaryPrimitives.ReadUInt64LittleEndian(artifact) != Seal.Magic ? Refusal(1, "<foreign-or-headerless>")
        : artifact[8] > Seal.HeaderVersion ? Refusal(2, $"<future-layout:{artifact[8]}>")
        : BinaryPrimitives.ReadUInt64LittleEndian(artifact.AsSpan(48)) != XxHash3.HashToUInt64(artifact.AsSpan(0, 48)) ? Refusal(3, "<header-corrupt>")
        : BinaryPrimitives.ReadInt64LittleEndian(artifact.AsSpan(24)) != artifact.Length - Seal.HeaderSize ? Refusal(4, $"<truncated:{artifact.Length - Seal.HeaderSize}>")
        : BinaryPrimitives.ReadUInt64LittleEndian(artifact.AsSpan(32)) != XxHash3.HashToUInt64(artifact.AsSpan(Seal.HeaderSize), classSeed) ? Refusal(5, "<payload-corrupt>")
        : artifact[9] != Seal.CodecBinary || artifact[10] > Seal.CompressionLz4 ? Refusal(6, $"<capability-gap:{artifact[9]}:{artifact[10]}>")
        : artifact[12] > Seal.Contract ? Refusal(7, $"<contract-ahead:{artifact[12]}:{Seal.Contract}>")
        : Fin.Succ($"<verified:{artifact.Length}>");

    static string Materialized(string staged, byte[] artifact) {
        var plain = new byte[BinaryPrimitives.ReadInt64LittleEndian(artifact.AsSpan(16))];
        if (artifact[10] == Seal.CompressionLz4 && LZ4Codec.Decode(artifact.AsSpan(Seal.HeaderSize), plain) != plain.Length) { throw new InvalidDataException("<plain-length-drift>"); }
        if (artifact[10] == Seal.CompressionNone) { artifact.AsSpan(Seal.HeaderSize).CopyTo(plain); }
        using var sink = new FileStream(staged, FileMode.Create, FileAccess.Write, FileShare.None);
        sink.Write(plain);
        sink.Flush(flushToDisk: true);
        return staged;
    }

    static string Bumped(string storePath, long successor) {
        using var store = StoreOpen.Dialed(storePath);
        using var bump = (fun(store.Open)(), store.CreateCommand()).Item2;
        bump.CommandText = $"PRAGMA user_version={successor}";
        return (bump.ExecuteNonQuery(), $"<epoch:{successor}>").Item2;
    }

    static Fin<string> Guarded(int code, Func<string> act) =>
        Try.lift(act).Run().MapFail(error => Error.New(code, $"<{error.Message}>"));

    static Fin<string> Refusal(int tier, string evidence) => Fin.Fail<string>(Error.New(7740 + tier, $"<tier-{tier}>{evidence}"));
}
```

## [05]-[OP_LOG_SYNC]

[LOG_SHAPE]:
- Law: one append-only table serves every entity family — local seq as the rowid-aliased key so appends land at the b-tree right edge, origin, a closed kind vocabulary, a globally unique entity id (two origins minting one id silently merge registers), a closed two-verb vocabulary where a tombstone carries empty payload because the verb is the semantics, the already-stamped causal version as one packed integer, the state-based full post-write row image (materialization reconstructs from any single op; op-based payloads demand ordered full replay and are rejected under LWW), and the codec-owned content key; a new family is one kind row plus one formatter case, zero schema change.
- Law: three indexes total is a law — the dedup unique key, the materialization pair, the primary-key cursor range; a fourth index pays append cost on every durable mutation for a read the shape already serves, and a read pattern wanting one wants a projection, which is a watermark consumer, never a log index.
- Law: the stored stamp column preserves the stamp's own order under integer comparison — stamping mechanics arrive settled from the signal layer, this lane stores and compares only, and a lane-local stamp generator is the rejected form.
- Law: the log IS the outbox, the audit artifact, the change feed, and the sync feed — four folds over one structure inside the store's own transactions; per-entity-kind log tables and a separate outbox re-derive what the transaction law already grants, and reads of current state hit the materialized registers only.

[ADJUDICATION_LAW]:
- Law: one IMMEDIATE transaction holds the whole effect set — a local write holds register mutation plus op insert, a remote batch holds dedup inserts, adjudication, and cursor advance — so crash recovery is re-delivery and read-your-writes holds by construction; local and remote writes are one rail, because a local fast path bypassing adjudication lets a stale local write overwrite newer synced state.
- Law: adjudication is one guarded set statement — the row-value comparison `(excluded.stamp, excluded.origin) > (stamp, origin)` executes inside the write lock with no compare-write window, `RETURNING` is the applied set so outcome accounting costs zero extra reads, and the same guard is the optimistic-concurrency check for stale local edits — offline reconciliation and live conflict control are one mechanism, not two; an undo, an offline edit replay, a remote batch, and a restore-then-catch-up are all this one statement against the same registers, the system's only way to change durable state.
- Law: the outcome union is closed — Applied, Superseded, Duplicate, TombstoneSuppressed — each derived from statement results, and the conservation identity batch = applied + superseded + duplicates + suppressed is the merge audit whose breach is itself a typed merge fault; outcome receipts ride the operational fact stream, never the log, because receipts about merging are not ops.
- Law: LWW over causal stamps never loses a causally-later write to an earlier one — the loss class is concurrency only, resolved deterministically by origin tiebreak, and ties are impossible because equal (stamp, origin) is the same op, caught by the dedup key; per-field LWW manufactures a row no writer wrote and is admitted per kind only as a declared class priced at per-field stamps.
- Law: the batch travels as one bound JSON document shredded by `json_each` — constant statement shape, cached plans, the bound-parameter ceiling out of the sizing decision, leaving lock-hold as the binding constraint with sibling busy receipts as its feedback; the in-batch fold takes each entity's lattice max before the register comparison, so intra-batch losers partition as superseded, and savepoint-per-unit isolates poison ops into receipted quarantine re-examined on capability upgrades.
- Law: future-looking stamps adjudicate normally — skew is signal-layer evidence, and refusing them holds merge availability hostage to clock quality; a detected fork — same (origin, seq), different content keys — is an epoch-class event emitting a typed fork receipt and halting merge with that peer.
- Exemption: the apply transaction's command kernel is the platform-forced ADO statement seam.

```csharp conceptual
public readonly record struct MergeReceipt(int Batch, int Applied, int Superseded, int Duplicate, int Suppressed) {
    public bool Conserves => Batch == Applied + Superseded + Duplicate + Suppressed;
}

public static class OpLog {
    public const string Schema = """
        CREATE TABLE IF NOT EXISTS op_log(seq INTEGER PRIMARY KEY, origin TEXT NOT NULL, origin_seq INTEGER NOT NULL, kind TEXT NOT NULL, entity TEXT NOT NULL, verb TEXT NOT NULL, stamp INTEGER NOT NULL, payload BLOB, content_key INTEGER NOT NULL, UNIQUE(origin, origin_seq)) STRICT;
        CREATE INDEX IF NOT EXISTS op_log_register ON op_log(kind, entity);
        CREATE TABLE IF NOT EXISTS register(entity TEXT PRIMARY KEY, kind TEXT NOT NULL, verb TEXT NOT NULL, stamp INTEGER NOT NULL, origin TEXT NOT NULL, payload BLOB) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS cursor(peer TEXT NOT NULL, origin TEXT NOT NULL, epoch INTEGER NOT NULL, seq INTEGER NOT NULL, stamp INTEGER NOT NULL, PRIMARY KEY(peer, origin)) STRICT;
        """;

    const string Dedup = """
        INSERT INTO op_log(origin, origin_seq, kind, entity, verb, stamp, payload, content_key)
        SELECT e.value->>'origin', e.value->>'seq', e.value->>'kind', e.value->>'entity', e.value->>'verb',
               e.value->>'stamp', jsonb(e.value->'payload'), e.value->>'key'
        FROM json_each($batch) AS e WHERE true ON CONFLICT(origin, origin_seq) DO NOTHING RETURNING seq
        """;

    const string Adjudicate = """
        WITH ranked AS (SELECT l.*, row_number() OVER (PARTITION BY l.entity ORDER BY l.stamp DESC, l.origin DESC) AS slot
                        FROM op_log AS l JOIN json_each($fresh) AS e ON l.seq = e.value)
        INSERT INTO register(entity, kind, verb, stamp, origin, payload)
        SELECT entity, kind, verb, stamp, origin, payload FROM ranked WHERE slot = 1
        ON CONFLICT(entity) DO UPDATE SET kind = excluded.kind, verb = excluded.verb,
            stamp = excluded.stamp, origin = excluded.origin, payload = excluded.payload
        WHERE (excluded.stamp, excluded.origin) > (register.stamp, register.origin) RETURNING 1
        """;

    const string Losses = """
        SELECT coalesce(sum(NOT (r.verb = 'tombstone' AND l.verb = 'upsert')), 0) AS superseded,
               coalesce(sum(r.verb = 'tombstone' AND l.verb = 'upsert'), 0) AS suppressed
        FROM op_log AS l JOIN json_each($fresh) AS e ON l.seq = e.value JOIN register AS r ON r.entity = l.entity
        WHERE (l.stamp, l.origin) < (r.stamp, r.origin)
        """;

    const string Advance = """
        INSERT INTO cursor(peer, origin, epoch, seq, stamp)
        SELECT $peer, l.origin, $epoch, max(l.origin_seq), max(l.stamp)
        FROM op_log AS l JOIN json_each($fresh) AS e ON l.seq = e.value WHERE true GROUP BY l.origin
        ON CONFLICT(peer, origin) DO UPDATE SET seq = max(seq, excluded.seq), stamp = max(stamp, excluded.stamp)
        """;

    public static Fin<MergeReceipt> Apply(SqliteConnection store, string peer, long storeEpoch, long cursorEpoch, string batch, int batchSize) {
        ArgumentNullException.ThrowIfNull(store);
        if (storeEpoch != cursorEpoch) { return Fin.Fail<MergeReceipt>(Error.New(7721, $"<epoch-mismatch:{cursorEpoch}:{storeEpoch}>")); }
        using var apply = store.BeginTransaction(IsolationLevel.Serializable, deferred: false);
        var fresh = Keys(store, apply, Dedup, [("$batch", batch)]);
        var freshDoc = $"[{string.Join(',', fresh)}]";
        var applied = Keys(store, apply, Adjudicate, [("$fresh", freshDoc)]).Count;
        var (superseded, suppressed) = Pair(store, apply, Losses, [("$fresh", freshDoc)]);
        _ = NonQuery(store, apply, Advance, [("$fresh", freshDoc), ("$peer", peer), ("$epoch", storeEpoch)]);
        apply.Commit();
        var receipt = new MergeReceipt(batchSize, applied, (int)superseded, batchSize - fresh.Count, (int)suppressed);
        return receipt.Conserves ? Fin.Succ(receipt) : Fin.Fail<MergeReceipt>(Error.New(7722, $"<unconserved:{receipt}>"));
    }

    static Seq<long> Keys(SqliteConnection store, SqliteTransaction apply, string sql, ReadOnlySpan<(string Name, object Value)> binds) {
        using var command = Bound(store, apply, sql, binds);
        using var rows = command.ExecuteReader();
        var ids = new List<long>();
        while (rows.Read()) { ids.Add(rows.GetInt64(0)); }                        // Exemption: ADO read loop fills a seam-local list frozen once by toSeq; repeated Seq.Add forcing is the rejected form
        return toSeq(ids);
    }

    static (long Superseded, long Suppressed) Pair(SqliteConnection store, SqliteTransaction apply, string sql, ReadOnlySpan<(string Name, object Value)> binds) {
        using var command = Bound(store, apply, sql, binds);
        using var rows = command.ExecuteReader();
        return rows.Read() ? (rows.GetInt64(0), rows.GetInt64(1)) : (0L, 0L);
    }

    static long NonQuery(SqliteConnection store, SqliteTransaction apply, string sql, ReadOnlySpan<(string Name, object Value)> binds) {
        using var command = Bound(store, apply, sql, binds);
        return command.ExecuteNonQuery();
    }

    static SqliteCommand Bound(SqliteConnection store, SqliteTransaction apply, string sql, ReadOnlySpan<(string Name, object Value)> binds) {
        var command = store.CreateCommand();
        (command.Transaction, command.CommandText) = (apply, sql);
        foreach (var (name, value) in binds) { _ = command.Parameters.AddWithValue(name, value); }
        return command;
    }
}
```

[CONVERGENCE_LAW]:
- Law: the adjudication relation is a join-semilattice over (stamp, origin) — applying any partition of any permutation of the op multiset any number of times yields identical materialized state; that one sentence subsumes idempotency, commutativity, reorder tolerance, and crash replay, and it is the property-test specification verbatim.
- Law: per-peer cursors are version vectors persisted in the same store and advanced inside the apply transaction — no reconciliation job exists because nothing can diverge; gapped arrivals hold back receipted under a bounded budget, never skip, and the same watermark structure serves in-process projections, which register as consumers.
- Law: merge(snapshot) ≡ merge(ops) — a snapshot is the compressed log prefix carrying registers, watermark vector, and epoch, so bootstrap, file-drop import, and catastrophic recovery are the normal merge with a wider range; snapshot cadence is one growth-ratio row bounding bootstrap cost and truncation eligibility together, and the truncation floor is the minimum over peer cursors and projection watermarks.
- Law: manifests are commutative-monoid summaries chosen by identity space — seq vectors for ordered log identity, content-key sets for unordered blob identity, cross-use rejected in both directions; acknowledgment IS the cursor echo, so no separate ack protocol exists beside the sequence the log already owns.
- Law: every cursor pairs (epoch, vector) and epoch comparison is equality-only — any mismatch routes to full resync, because reasoning about epoch recency re-trusts exactly the rewound counters the token exists to deny; one epoch token serves the open ritual, the sync cursors, and the artifact headers, and a second epoch-like counter anywhere re-splits the fence.
- Law: tombstone collection is cursor-fenced, never time-fenced — a time window resurrects through any peer offline longer than it; a departed peer retires by receipted administrative op, pinning is the deliberate failure direction because it is observable where early collection is silent resurrection, and this lane supplies the fence predicate while retention owns sweep execution; presence rides the same table as an ephemeral class — TTL expiry IS the delete, excluded from cursors, manifests, and snapshots, so liveness chatter cannot inflate sync state.

## [06]-[RETENTION_CLASSES]

[CLASS_LAW]:
- Law: every stored thing belongs to exactly one class row carrying five decisions — storage lane, retention record, classification ceiling, loss policy (receipted-evict or declared-expiry), identity scheme (content key or name-plus-epoch); an artifact fitting no class is an admission rejection, never a default — the canonical set closes at six rows: sealed snapshot, log segment, evidence bundle, export, cache blob, ephemeral — class membership is immutable, reclassification is export-then-readmit so every lived lifecycle stays receipted, and one catalog inventories every lane, with byte counts recorded from the artifact's own sealed length fields, never a later filesystem stat.
- Law: admission is one fold — classify-check, identity-derive, race-admit, budget-check, lane-write — and the identity scheme alone yields two complete behavioral families: content-keyed classes get dedup and race-loser disposal free, name-plus-epoch classes get versioned replacement free, zero conditional code.
- Law: classification stamps arrive settled — admission compares stamp against the class ceiling and rejects typed, an unstamped artifact rejects identically because absence of evidence is not clearance, the store never re-redacts or downgrades, ceilings are build-invariant where budgets may widen in debug, and import re-verifies stamps so export round-trips cannot launder.
- Law: a budget breach truncates with an embedded receipt — capture must succeed degraded — while a ceiling breach rejects outright — security never degrades; the two overflow responses are never interchangeable, depth budgets catch the deep narrow structures byte budgets miss, and a drop-oldest ring builds only with an on-drop receipt delegate receiving identity and stamp, never the dropped entry.
- Law: the two-tier cache is a lane value, not a feature — the process-retained content-keyed registry, then the class's durable lane, lookup falling tier one, tier two, produce, with produce admitting into both; the registry keys on (epoch, content key) so the restore fence invalidates wholesale with no per-item protocol, racing producers resolve by compare-exchange with the loser disposing its candidate as a receipted fact, and a third cache anywhere forks invalidation and identity.

[SWEEP_LAW]:
- Law: the sweep is a pure three-stage fold — holds exit first and short-circuit every rule, each survivor takes the first deciding verdict in declared order age, count, size, and the size stage evicts oldest-first until under budget; the verdict union closes at Kept, Held, HeldOverBudget, EvictAge, EvictCount, EvictSize, and held bytes count against the budget but cannot evict, so preservation pressure surfaces as `HeldOverBudget` instead of displacing onto unheld artifacts.
- Law: verdicts are a pure function of inventory snapshot, policy snapshot, and hold rows under one clock instant with identity tiebreak after stamp — decision and execution split, so the verdict list is a testable value, every receipt cites the policy snapshot stamp, and a partial sweep resumes by re-folding with no journal.
- Law: holds are first-class rows — whole-class, identity-set, and stamp-range selectors composing by union, bound late at sweep time so a hold placed today protects artifacts admitted tomorrow; release deletes the row with no eviction side effect, and every run emits an active-hold inventory with hold age, because forgotten holds are the dominant retention failure.
- Law: every removed artifact emits (class, identity, deciding rule, policy stamp, bytes) and the run summary proves inventory = kept + held + evicted; unreceipted deletion anywhere is a rail rejection — operator deletion routes through an administrative verdict kind — and the receipt stream is itself a count-and-age-bounded class, closing meta-retention at depth one.
- Law: blob bytes delete after the row commit — the crash window produces collectible orphans, never dangling rows — and the age-gated orphan pass closes the loop with its volume as the crash-loop signal; the deletion budget bounds lock-hold because the sweep is a writer like any other, and cross-class pressure is one allocation pass over declared weight rows, never a second sweeper.
- Law: eligibility predicates inject — sync fences, projection floors, export pins, the orphan age gate — so the sweep stays the single deletion executor owning zero domain-safety rules, and every refusal names the predicate that held it: the receipt stream is the system's complete deletion and non-deletion ledger at once.
- Law: evidence windows freeze [t − Δ, t] from the trigger's stamp so capture is idempotent per incident identity, with Δ a per-trigger-kind row; contributors fan in as declared (name, order, budget, deadline) rows — over budget truncates, missed deadline lands absent, over ceiling refuses, each with receipt — the bundle always seals because incidents are precisely when processes die, and the ordered-bounded fold is one algebra shared with drain-band walks, so a bespoke gatherer is the rejected form.
- Law: export reuses the sweep's verdict machinery read-only, so export and sweep can never disagree about one artifact at one instant; the proof manifest carries identity, content key, classification stamp, retention verdict, and policy stamp per artifact, destination clearance compares exactly like an admission ceiling, partial exports stay explicit with refused rows as load-bearing as included ones, export creates no hold, and re-import is ordinary admission.
- Exemption: none — the sweep is total expression flow; decision is a pure fold over the inventory snapshot and the platform never forces a statement here.

```csharp conceptual
[ComplexValueObject]
public sealed partial class Budget {
    public TimeSpan MaxAge { get; }
    public int MaxCount { get; }
    public long MaxBytes { get; }
}

public readonly record struct Item(ulong Identity, long Stamp, long Bytes);

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Hold {
    private Hold() { }
    public sealed record WholeClass : Hold;
    public sealed record IdentitySet(FrozenSet<ulong> Members) : Hold;
    public sealed record StampRange(long From, long Until) : Hold;

    public bool Covers(Item item) => Switch(
        state: item,
        wholeClass:  static (_, _) => true,
        identitySet: static (held, set) => set.Members.Contains(held.Identity),
        stampRange:  static (held, range) => held.Stamp >= range.From && held.Stamp <= range.Until);
}

[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Verdict {
    private Verdict() { }
    public sealed record Kept : Verdict;
    public sealed record Held : Verdict;
    public sealed record HeldOverBudget : Verdict;
    public sealed record EvictAge : Verdict;
    public sealed record EvictCount : Verdict;
    public sealed record EvictSize : Verdict;

    public bool Frees => this is EvictAge or EvictCount or EvictSize;
    public bool Retains => this is Held or HeldOverBudget;
}

public readonly record struct SweepReceipt(int Inventory, int Kept, int Retained, int Evicted, long FreedBytes, long PolicyStamp) {
    public bool Conserves => Inventory == Kept + Retained + Evicted;
}

public static class Sweep {
    public static (Seq<(Item Item, Verdict Verdict)> Ledger, Fin<SweepReceipt> Outcome) Decide(
        Seq<Item> inventory, Budget budget, Seq<Hold> holds, long now, long policyStamp, Func<Item, bool> eligible) {
        var scan = toSeq(inventory.OrderBy(static i => i.Stamp).ThenBy(static i => i.Identity))
            .Fold((Ledger: Seq<(Item, Verdict)>(), Live: 0, Bytes: 0L),
                (state, item) => Advance(state, item, Adjudicate(state, item, budget, holds, now, eligible)));
        var ledger = scan.Ledger.Rev();
        var receipt = ledger.Fold(new SweepReceipt(inventory.Count, 0, 0, 0, 0L, policyStamp), static (sum, row) =>
            row.Verdict.Frees ? sum with { Evicted = sum.Evicted + 1, FreedBytes = sum.FreedBytes + row.Item.Bytes }
            : row.Verdict.Retains ? sum with { Retained = sum.Retained + 1 }
            : sum with { Kept = sum.Kept + 1 });
        return (ledger, receipt.Conserves ? Fin.Succ(receipt) : Fin.Fail<SweepReceipt>(Error.New(7761, $"<unconserved:{receipt}>")));
    }

    static Verdict Adjudicate((Seq<(Item, Verdict)> Ledger, int Live, long Bytes) state, Item item, Budget budget, Seq<Hold> holds, long now, Func<Item, bool> eligible) =>
        holds.Exists(hold => hold.Covers(item)) || !eligible(item) ? (state.Bytes + item.Bytes > budget.MaxBytes ? (Verdict)new Verdict.HeldOverBudget() : new Verdict.Held())
        : now - item.Stamp > budget.MaxAge.Ticks ? new Verdict.EvictAge()
        : state.Live >= budget.MaxCount ? new Verdict.EvictCount()
        : state.Bytes + item.Bytes > budget.MaxBytes ? new Verdict.EvictSize()
        : new Verdict.Kept();

    static (Seq<(Item, Verdict)> Ledger, int Live, long Bytes) Advance((Seq<(Item, Verdict)> Ledger, int Live, long Bytes) state, Item item, Verdict verdict) =>
        state with {
            Ledger = (item, verdict).Cons(state.Ledger),
            Live = state.Live + (verdict is Verdict.Kept ? 1 : 0),
            Bytes = state.Bytes + (verdict.Frees ? 0L : item.Bytes),
        };
}
```
