# [SYSTEM_APIS]

Effect-ecosystem modules replace JS stdlib machinery whenever they own the concern. They do not replace `Schema` shapes, `Match` dispatch, `Layer` wiring, or the typed Effect rails. The default is the Effect data structure with structural equality, persistent update, and `Equal`/`Hash` integration; JS stdlib `Map`/`Set`/`Array`/`Object`/`Date`/`null` survive only at FFI and serialization boundaries marked `// BOUNDARY ADAPTER`. The selection axis is ownership of an invariant, not feature parity: a primitive is admitted because it carries structural equality, an `Option` failure mode, a testable seam, or persistent update that the stdlib shape silently drops.

## [01]-[SMELL_LOOKUP]

This table is a lookup by repeated local smell; the owner deletes the smell, never wraps it.

| [INDEX] | [SMELL]                                          | [OWNER]                              |
| :-----: | :----------------------------------------------- | :----------------------------------- |
|  [01]   | `new Map()`/`new Set()` mutated in domain        | `HashMap` / `HashSet`                |
|  [02]   | `new Set([...prior, x])` rebuild per event       | `HashMap.modifyAt` / `HashSet.add`   |
|  [03]   | `Array.push` accumulation in a fold              | `Chunk` / `Array.reduce`             |
|  [04]   | `Object.keys`/`entries`/`fromEntries`            | the `Record` module                  |
|  [05]   | manual object pick/omit/evolve                   | the `Struct` module                  |
|  [06]   | `null`/`undefined` for domain absence            | `Option`                             |
|  [07]   | `Date.parse`/`new Date(s).getTime()`             | `DateTime` / `Schema.DateTimeUtc`    |
|  [08]   | `a.physical >= b.physical` inline date compare   | `DateTime.Order` / `DateTime.max`    |
|  [09]   | `hi - lo` ad-hoc instant subtraction             | `DateTime.distanceDuration`          |
|  [10]   | raw millisecond literal for a duration           | `Duration`                           |
|  [11]   | hand-written multi-field comparator              | `Order.struct` / `Order.combineAll`  |
|  [12]   | delimiter-concatenated equality/cache key        | `Equivalence.struct`                 |
|  [13]   | inline boolean predicate composition             | the `Predicate` module               |
|  [14]   | `.filter(p).map(f)` two-pass                     | `Array.filterMap` / `Array.getSomes` |
|  [15]   | `a / b` producing `NaN`/`Infinity`               | `Number.divide` returning `Option`   |
|  [16]   | `JSON.parse(decode(bytes))` then `decodeUnknown` | `Schema.parseJson(inner)`            |
|  [17]   | `JSON.stringify`-then-compare equality           | `Equal.equals` / `Hash.hash`         |
|  [18]   | `node:crypto` hash inline in domain flow         | content-address boundary owner       |
|  [19]   | unbounded `new Map()` mutated as a cache         | `Cache` / `Effect.cachedFunction`    |
|  [20]   | `Math.random()` for a non-cosmetic identifier    | `node:crypto` boundary capture       |

## [02]-[COLLECTIONS]

[IMMUTABLE_STRUCTURES]:
- Owner: `HashMap<K,V>` for keyed lookup and accumulator state, `HashSet<T>` for membership, `Chunk<T>` for streaming and batching, the `Array` module (`Array.getSomes`, `Array.groupBy`, `Array.dedupeWith`, `Array.match`) for small fixed collections.
- Replace: `new Map()`/`new Set()` with `.set`/`.add`, `Array.push` accumulation, `[...arr]` spread-copy update, and the `new Set([...prior, key])` spread-rebuild that re-allocates the whole set per event.
- Law: `HashMap.modifyAt(m, k, f)` is the single keyed read-merge-write — `f: Option<V> => Option<V>` folds presence and absence in one arm and returns a persistent map with structural sharing; the `TryGetValue`-then-`set` double probe and the spread-rebuild are both retired by it.
- Law: `HashMap.mutate(m, draft => draft.set(...))` batches many writes inside one structural-sharing transaction at a boundary; outside that scope the persistent operators are the only mutation, and a `.set` on a foreign `Map` is `// BOUNDARY ADAPTER`-only.
- Rule: a keyed accumulator threaded through `Stream.mapAccum` or `Array.reduce` is a `HashMap` — mutation inside a fold breaks referential transparency under retry and reconnect-replay; `Equal`/`Hash` integration makes a `HashSet` of tagged values compare structurally with no comparator.

[RECORD_AND_STRUCT]:
- Owner: the `Record` module (`Record.map`, `Record.collect`, `Record.filterMap`, `Record.toEntries`) over `Object.keys`/`entries`/`fromEntries`; the `Struct` module (`Struct.pick`, `Struct.omit`, `Struct.evolve`, `Struct.get`) over manual object surgery.
- Replace: an `Object.entries(...).map(...)` round trip widened by an `as ReadonlyArray<[K, V]>` cast, a manual `{ ...obj, key: value }` projection, and a hand-written key-preserving fold.
- Law: `Record.map` is the key-preserving (structural) fold and `Record.collect(r, f)` projects to an array in one pass, so the `Object.entries` round trip plus the tuple-type cast collapse to one typed call; the cast that `noUncheckedIndexedAccess` would otherwise force is deleted, not suppressed.
- Law: `Record.keys(vocabulary)` returns the keys typed `Array<keyof typeof vocabulary & string>`, retiring the `Object.keys(v) as ReadonlyArray<K>` widening cast — the `as` that recovers a discriminant the value already proves is the defect; the wire enum derives from the same anchor that drives indexed-access dispatch through `S.Literal(...R.keys(V) as [keyof typeof V, ...Array<keyof typeof V>])`, where the lone surviving cast asserts cardinality (`R.keys` is `Array`, `S.Literal` demands `NonEmptyReadonlyArray`), never membership — a non-emptiness witness on a closed `as const` is a proof the empty-vocabulary case is unreachable, distinct from the banned identity recovery, and never a parallel key list beside the anchor.

```ts conceptual
import { Array as A, Data, HashMap, HashSet, Option } from "effect"

class Row extends Data.Class<{ readonly key: string; readonly count: number }> {} // Equal/Hash auto-derived: structural keying with zero comparator

const tally = (rows: ReadonlyArray<Row>): HashMap.HashMap<string, number> =>      // one structural-sharing transaction lands every write, not a persistent op per row
  HashMap.mutate(HashMap.empty<string, number>(), (draft) =>
    A.forEach(rows, ({ key, count }) =>
      HashMap.set(draft, key, count + Option.getOrElse(HashMap.get(draft, key), () => 0)))) // in-draft set mutates; modifyAt would discard its new map

const seen = (rows: ReadonlyArray<Row>): HashSet.HashSet<Row> => HashSet.fromIterable(rows) // dedupe rides Equal/Hash, never JSON.stringify

const project = (tallies: HashMap.HashMap<string, number>): ReadonlyArray<readonly [string, number]> =>
  A.map(HashMap.toEntries(tallies), ([key, count]) => [key, count] as const)
```

## [03]-[TIME_AND_IDENTITY]

[INSTANT_OWNER]:
- Owner: `DateTime` (`DateTime.unsafeMake`, `DateTime.make` returning `Option`, `DateTime.toEpochMillis`, `DateTime.distanceDuration`, `DateTime.Order`, `DateTime.Equivalence`, `DateTime.min`/`max`/`between`) for every event-time instant; `Schema.DateTimeUtc` admits an ISO-8601 string into a `DateTime.Utc` at the decode seam.
- Replace: `Date.parse(s)` and `new Date(s).getTime()` for instant comparison, an `a.physical >= b.physical` inline date comparator, and an ad-hoc `hi - lo` millisecond subtraction that re-derives a duration the type already carries.
- Law: an instant crossing the wire decodes once through `Schema.DateTimeUtc` — a malformed timestamp fails the rail instead of producing a silent `NaN` from `Date.parse`, and the interior holds a `DateTime` that never re-parses.
- Law: `DateTime.distanceDuration(later)(earlier)` yields a `Duration` directly, `DateTime.Order` and `DateTime.max` order two instants, and `DateTime.between({ minimum, maximum })` tests a horizon — the lateness, skew, and watermark comparisons read these operators, never raw epoch arithmetic.
- Law: a derived event-time ordinal is a `Duration` distance composed under `Order`, never a hand-scaled `epochMillis * 1_000_000n + logical` nanos literal — the magic multiplier is a `Duration.nanos`/`Order.combine` row, and a sub-millisecond tiebreak is a second `Order.mapInput` arm, not packed arithmetic.
- Boundary: a wall-clock read is `Clock`, not `DateTime.now` in domain flow; `DateTime.unsafeMake(epochMillis)` inside a decoded projection is admission of an already-validated field, not a fresh parse.

[STRUCTURAL_IDENTITY]:
- Owner: `Hash` (`Hash.hash`, `Hash.structure`) and the `Equal`/`Hash` integration on every Effect data structure for in-memory identity and `HashMap`/`HashSet` keying; `Equivalence` (`Equivalence.struct`, `Equivalence.mapInput`, `Equivalence.combine`) for a compound key compared field-wise.
- Replace: a `JSON.stringify`-then-`===` equality, an XOR/prime hash combine, and a `${a}:${b}` delimiter-joined cache key whose field collision is silent.
- Law: `Data.Class`, `Data.TaggedEnum`, and `Schema.Class` auto-derive `Equal`/`Hash`, so a `HashSet` of receipts or a `HashMap` keyed on a tagged value compares structurally with zero comparator; `Equal.equals(a, b)` replaces the stringify-compare end to end.
- Rule: `Hash`/`Equal` are process-local and non-stable — never persist a `Hash.hash` output or use it as a content address; a content address routes to the byte-identity owner in `[6]`.

[CACHE_AND_MEMO]:
- Owner: `Effect.cachedFunction(f, eq?)` for an unbounded memo keyed by `Equivalence`, `Effect.cachedInvalidateWithTTL(self, ttl)` for a single TTL-expiring cell, and `Cache.make({ capacity, timeToLive, lookup })` for a bounded effectful cache with eviction.
- Replace: an unbounded `new Map()` mutated as a memo, a hand-rolled `if (cache.has(k))` lookup-then-store, and a manual expiry timestamp compared against `Date.now()`.
- Law: the cache key is an `Equivalence` over every dimension that changes output — content, decode policy, and capability version feed one structured key, never a path-only or `${a}:${b}` key; `Cache.make`'s `capacity` is the eviction bound the unbounded `Map` lacks.
- Rule: `Effect.cachedFunction` memoizes the effect, so the lookup is replayed under retry without re-running the body, and concurrent callers on one key share one in-flight computation rather than racing duplicate work.

```ts conceptual
import { DateTime, Duration, Order, Schema as S } from "effect"

const Hlc = S.Struct({ at: S.DateTimeUtc, logical: S.BigInt })
type Hlc = typeof Hlc.Type

const byEventTime: Order.Order<Hlc> = Order.combine(
  Order.mapInput(DateTime.Order, (h: Hlc) => h.at),
  Order.mapInput(Order.bigint, (h: Hlc) => h.logical),
)

const skewRadius = (earliest: DateTime.Utc, latest: DateTime.Utc): Duration.Duration =>
  Duration.times(DateTime.distanceDuration(latest)(earliest), 0.5)

const isLate = (mark: DateTime.Utc, row: DateTime.Utc, allowed: Duration.Duration): boolean =>
  Order.lessThan(DateTime.Order)(row, DateTime.subtractDuration(mark, allowed))
```

## [04]-[VALUES_AND_PREDICATES]

[DURATION_AND_ABSENCE]:
- Owner: `Duration` for every timeout, delay, schedule interval, and vocabulary policy field; `Option<T>` for every domain absence with `Option.fromNullable` at the boundary.
- Replace: a raw millisecond literal (`5000`), a `null`/`undefined` domain return, and an `x ?? fallback` where `Option.getOrElse` carries the canonical default from a vocabulary row.
- Rule: `Duration.seconds(5)` over `5000`, `Duration.greaterThan`/`Duration.between` for comparison; `undefined` survives only as the decoded shape under `exactOptionalPropertyTypes`, projected to `Option` at admission via `Schema.optionalWith(field, { as: "Option" })`.

[ORDER_AND_PREDICATE]:
- Owner: `Order` (`Order.struct`, `Order.combineAll`, `Order.mapInput`, `Order.max`) and `Equivalence` over hand-written comparators; the `Predicate` module (`Predicate.and`, `Predicate.or`, `Predicate.not`) and the `Number` module (`Number.divide`, `Number.clamp`, `Number.sum`) over inline arithmetic on a fallible path.
- Replace: a multi-field `(a, b) => a.x - b.x || a.y - b.y` comparator, a chained `&&`/`||`/`!` predicate, and a bare `a / b` that can produce `NaN`/`Infinity`.
- Law: `Order.combineAll([o1, o2])` is the lexicographic chain and `Order.max` is the lattice join; `Number.divide` returns `Option<number>`, forcing an explicit `Option.getOrElse` at every zero-denominator site so no `NaN` propagates, and `Number.clamp({ minimum, maximum })` post-gates a normalized scalar.
- Rule: a predicate composed from `Predicate.and`/`Predicate.or` is a reusable value carried into `Array.filter` and `Effect.filterOrFail`, never re-inlined per call site.

```ts conceptual
import { Number as N, Option, Order, Predicate, pipe } from "effect"

const byRank = Order.combineAll<{ readonly priority: number; readonly weight: number }>([
  Order.mapInput(Order.reverse(Order.number), (r) => r.priority),
  Order.mapInput(Order.number, (r) => r.weight),
])

const admissible = Predicate.and(
  (r: { readonly active: boolean; readonly weight: number }) => r.active,
  (r: { readonly active: boolean; readonly weight: number }) => r.weight > 0,
)

const saturation = (k: number, cap: number): number =>
  pipe(N.divide(k, cap), Option.map((r) => 1 - N.min(r, 1)), Option.getOrElse(() => 1))
```

## [05]-[CODEC_AND_COMPOSITION]

[CODEC]:
- Owner: `Schema.parseJson(inner)` for a JSON wire string decoded straight into the domain shape, `Schema.transform(wire, domain, { decode, encode })` for a bidirectional wire-to-domain projection, and the layered codecs (`Schema.Uint8ArrayFromBase64` on the wire leg, `Schema.Uint8ArrayFromSelf` on the domain leg).
- Replace: a `JSON.parse(new TextDecoder().decode(bytes))` followed by a separate `Schema.decodeUnknown`, a `JSON.stringify` over an unvalidated shape, and a regex extraction from a rendered string where the structured form is available.
- Law: `Schema.parseJson(inner)` fuses the parse and the validation into one schema, so the byte decode and the domain admission are one `decodeUnknown` pass — the `JSON.parse` step plus a downstream validation is the rejected two-step seam.
- Rule: the codec is the single source for the shape; a derived field present in domain but absent from wire is intentional asymmetry the encode side drops, never a parallel parser-plus-serializer pair.

[COMPOSITION]:
- Owner: `Function.pipe`/`Function.flow` over manual composition; `Effect` over a `Promise` chain for async flow.
- Replace: a nested call composition `f(g(h(x)))`, a `let tmp = ...; tmp = ...` reassignment chain, and a `.then(...).catch(...)` Promise pipeline.
- Rule: `pipe(value, f, g)` threads a value, `flow(f, g)` composes point-free; a `Promise` enters domain flow only through `Effect.tryPromise` at the boundary.

```ts conceptual
import { Effect, ParseResult, Schema as S } from "effect"

const Frame = S.parseJson(S.Struct({ topic: S.NonEmptyString, payload: S.Uint8ArrayFromBase64, seq: S.BigInt, at: S.DateTimeUtc }))
type Frame = typeof Frame.Type

const decodeFrame = (bytes: Uint8Array): Effect.Effect<Frame, ParseResult.ParseError> =>
  S.decodeUnknown(Frame)(new TextDecoder().decode(bytes)) // BOUNDARY ADAPTER: byte-to-text, parse + validate fused in one schema

const Receipt = S.transform(Frame, S.typeSchema(S.Struct({ topic: S.NonEmptyString, at: S.DateTimeUtcFromSelf })), {
  strict: true,
  decode: ({ topic, at }) => ({ topic, at }),
  encode: ({ topic, at }) => ({ topic, payload: new Uint8Array(), seq: 0n, at }),
})
```

## [06]-[RUNTIME_AND_INTEGRITY]

[TIME]:
- Owner: `Clock` (`Clock.currentTimeMillis`, `Clock.currentTimeNanos`, `Clock.clockWith`) read through the ambient service, `Effect.sleep`/`Effect.timeout`/`Schedule` for delay and pacing, and `TestClock.adjust`/`setTime` as the deterministic test seam.
- Replace: a `Date.now()` delta, a raw `setTimeout`/`setInterval` in domain flow, a `performance.now()` benchmark threaded by hand, and a wall-clock comparison that cannot be advanced under test.
- Law: `Clock` is the single testable time seam — every time-accepting primitive (`Effect.sleep`, `Effect.timeout`, `Schedule.exponential`, `Effect.repeat`) reads the same provider, so `TestClock.adjust(Duration.seconds(n))` advances all of them at once.
- Reject: an ambient wall-clock read inside a retry predicate, a schedule, or any transform whose test must be deterministic; `Date.now()` survives only inside a `// BOUNDARY ADAPTER` wire timestamp.

[INTEGRITY]:
- Owner: `Hash`/`Equal` for in-memory structural identity (`[3]`); `node:crypto` (`createHash`, `timingSafeEqual`) behind a `// BOUNDARY ADAPTER` capture for content-addressed artifact bytes, signatures, and idempotency keys.
- Replace: a `===` on two secret buffers (timing-leaking), a `Math.random()` for any non-cosmetic identifier, and a `Hash.hash` output persisted as a content address.
- Law: a content-addressed artifact crosses as a `Uint8Array` plus its `node:crypto` digest captured once at the boundary, never parsed and re-serialized between verification and forwarding — the byte-identity law in `boundaries.md`.
- Gate: a checksum over a streamed artifact computes incrementally over the `Stream`'s `Chunk`s at the wire fence, not after a full-buffer materialization.

[BACKPRESSURE]:
- Owner: `Queue.bounded`/`Queue.dropping`/`Queue.sliding` and the matching `PubSub` constructors, drained through `Stream.fromQueue` with `Stream.groupedWithin` for batch pacing.
- Replace: a `new Map()`/array mutated as an unbounded in-flight buffer, a `Promise.all` over an open-ended producer that retains every pending result, and a hand-rolled semaphore loop.
- Rule: the carrier capacity and full-mode are the declared backpressure policy stated at construction — `bounded` suspends the producer fiber, `dropping` discards the newest offer, `sliding` evicts the oldest; the unbounded form is admitted only when the producer is provably finite.
- Boundary: the producer/consumer handoff topology — latest-value cell versus full log — is the `[HANDOFF_DRAIN]` decision owned by `boundaries.md`; this site owns the capacity-and-eviction policy.

```ts conceptual
import { Cause, Chunk, Clock, Duration, Effect, Number as N, Queue, Scope, Stream } from "effect"

const _staleness = (recordedAtMillis: number): Effect.Effect<Duration.Duration> =>
  Clock.currentTimeMillis.pipe(Effect.map((now) => Duration.millis(N.max(0, N.subtract(now, recordedAtMillis)))))

const _digest = (bytes: Uint8Array): Effect.Effect<string, Cause.UnknownException> =>
  Effect.tryPromise(async () => {
    const { createHash } = await import("node:crypto") // BOUNDARY ADAPTER: content-address capture
    return createHash("sha256").update(bytes).digest("hex")
  })

const _meter = <A>(source: Stream.Stream<A>): Effect.Effect<Queue.Dequeue<ReadonlyArray<A>>, never, Scope.Scope> =>
  Queue.sliding<ReadonlyArray<A>>(256).pipe(
    Effect.tap((q) =>
      source.pipe(
        Stream.groupedWithin(64, Duration.millis(100)),
        Stream.map(Chunk.toReadonlyArray),
        Stream.runForEach((batch) => Queue.offer(q, batch)),
        Effect.forkScoped,
      )),
  )
```
