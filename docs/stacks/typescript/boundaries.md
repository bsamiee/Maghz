# [BOUNDARIES]

Foreign material crosses once: a boundary owner decodes bytes, sentinels, callbacks, promises, worker-affine work, state cells, and provider shapes into decoded values or typed Effect rails, and a Layer wires the capability graph so everything the interior receives — values, receipts, services, effects — is recoverable from declarations rather than from the foreign surface that produced it. The Layer graph is where requirement edges collapse to `never`; the Schema is where untyped input becomes domain material; the wire codec is the only site where protocol and interior schemas meet.

## [01]-[SEAM_CHOOSER]

This table selects the owner for a foreign signal; when a signal matches several rows, the most specific wins, and lifetime rows are read before transport rows.

| [INDEX] | [FOREIGN_SIGNAL]        | [SEAM_OWNER]                          | [INTERIOR_FORM]                       | [REJECT]                     |
| :-----: | :---------------------- | :------------------------------------ | :------------------------------------ | :--------------------------- |
|  [01]   | untyped input payload   | `Schema.decodeUnknown`                | decoded owner in the rail             | interior revalidation        |
|  [02]   | throwing async call     | `Effect.tryPromise`                   | typed `Effect` failure                | raw `Promise` in domain      |
|  [03]   | null or sentinel        | `Option.fromNullable`                 | `Option<T>` or tagged family          | nullable payload past seam   |
|  [04]   | cause-bearing absence   | tagged `Data.TaggedError`             | closed failure family                 | `Option.none` for a cause    |
|  [05]   | resource lifetime       | `Effect.acquireRelease`               | scoped value, LIFO finalizer          | manual cleanup, leaked fiber |
|  [06]   | worker/main-thread call | marshal `Effect`                      | `Effect` with captured runtime        | ambient main-thread read     |
|  [07]   | high-frequency callback | `Queue`/`PubSub` or `SubscriptionRef` | drained `Stream` or latest cell       | blocked/mutating callback    |
|  [08]   | event or subscription   | scoped `PubSub`/`Queue`               | drained `Stream` of decoded signals   | orphan handler               |
|  [09]   | isolated-axis lifetime  | derived `Scope`/`Layer.fresh`         | one-axis-isolated instance            | shared cancellation/registry |
|  [10]   | session/singleton state | `SubscriptionRef` state family        | committed `Data.TaggedEnum` cell      | boolean lifecycle flag       |
|  [11]   | keyed recomputation     | `Equivalence`-keyed memo / `RcMap`    | full-dimension cache key              | path-only/type-only cache    |
|  [12]   | capability dependency   | `Layer` + `Effect.Service`            | provided context, `R = never` at root | service location             |
|  [13]   | protocol payload        | `Schema.transform` codec              | decoded owner                         | codec-bearing domain owner   |
|  [14]   | signed byte field       | raw-bytes-then-hash capture           | canonical octets plus hash            | parse-reserialize            |

## [02]-[ADMISSION]

[DECODE_PROJECTION]:
- Use: any untyped ingress — request body, env, provider row, foreign JSON — decoded exactly once through `Schema.decodeUnknown(schema)(input)`, with `{ errors: "all" }` when every parse failure must accumulate.
- Law: the `ParseError` lifts into the error channel through `Effect.mapError` at the same seam; interior code receives the decoded owner and never re-validates.
- Law: a present branch never manufactures a meaningless value; a field that can become absent after decode is `Schema.optionalWith(..., { as: "Option" })` so the absence is `Option.none`, not a `null`.
- Reject: a sentinel check in interior flow; a nullable payload riding past the seam; `decode` where `decodeUnknown` is the untrusted-input form.

[ABSENCE_TAXONOMY]:
- Law: cause-bearing foreign state — unavailable, degraded, pending, faulted — is a closed `Data.TaggedEnum` or `Data.TaggedError` family, never `Option.none`; `Option<T>` is correct only when absence has no action-changing cause.
- Law: provision and state are different axes: a required capability is always present as a service whose value carries its own unavailable state, and `Effect.serviceOption(Tag)` is the one authorized optional-capability seam fusing read and projection.
- Reject: flattening nested absence before the layer carrying cause is consumed; a `null` service or a service lookup standing in for runtime absence.

[PROBE_SWEEP_POLICY]:
- Law: a probe sweep fixes its algebra once at the seam — `Effect.all({ mode: "validate" })` reports every absence, the fail-fast default reports one — selecting the mode selects whether the boundary reports one absence or all.
- Accept: `Effect.partition` for the survivor/casualty split when callers need both usable values and rejected facts with `E = never`.
- Reject: a later walk over the results that reinterprets why each probe disappeared.

```ts conceptual
import { Data, Effect, Match, Option, Schema as S } from "effect"

const Payload = S.NonEmptyString.pipe(S.brand("Payload")) // decoded owner; interior never re-validates
type Payload = typeof Payload.Type
class RowFault extends Data.TaggedError("RowFault")<{ readonly reason: "absent" | "unavailable"; readonly detail: string }> {} // cause carries its axis

const _Row = S.Struct({ state: S.Literal("missing", "detached", "ready"), value: S.OptionFromNullOr(Payload) })

const _route = (row: typeof _Row.Type): Effect.Effect<Option.Option<Payload>, RowFault> => // explicit channel pins E = RowFault; the curried matcher would widen it to unknown
  Match.value(row).pipe(
    Match.discriminatorsExhaustive("state")({ // closed wire discriminant folds total; a fourth state breaks here, never a silent default
      missing:  ()         => Effect.succeed(Option.none<Payload>()), // structural absence, no cause: rides Option
      detached: ()         => Effect.fail(new RowFault({ reason: "unavailable", detail: "detached" })), // cause-bearing: rides the fault
      ready:    ({ value }) => Option.match(value, {
        onNone: () => Effect.fail(new RowFault({ reason: "absent", detail: "value" })), // present-but-null is a fault, never Some(null)
        onSome: (v) => Effect.succeed(Option.some(v)),
      }),
    }),
  )

const admit = (raw: unknown): Effect.Effect<Option.Option<Payload>, RowFault> => // one inbound funnel admits every shape at one seam
  S.decodeUnknown(_Row)(raw).pipe(Effect.mapError((e) => new RowFault({ reason: "absent", detail: e.message })), Effect.flatMap(_route))
```

## [03]-[LIFETIME]

[CAPSULE_OWNER]:
- Use: connections, pools, file handles, sockets, leases, and external cursors.
- Law: one `Effect.acquireRelease(acquire, release)` acquires, projects, and releases inside the scoped service constructor; the release runs LIFO on success, failure, and interruption, exactly once on every exit path.
- Law: callers receive values or rails, never live handles; the capsule converts its own thrown exceptions through `Effect.tryPromise` at the acquire site.
- Law: `Effect.forkScoped` binds a drain fiber to the service scope so closure interrupts it; `Effect.fork` inside a scoped generator leaks the fiber past teardown.
- Exemption: a `// BOUNDARY ADAPTER` callback wiring a foreign event handler inside the capsule is the named platform-forced statement seam.
- Reject: scattered manual cleanup, a public handle field, a parallel borrowed/owned wrapper pair, or a second finalizer registry.

```ts conceptual
import { Chunk, Duration, Effect, PubSub, Stream } from "effect"
import { SqlClient } from "@effect/sql"

class EventDrain extends Effect.Service<EventDrain>()("domain/EventDrain", {
  scoped: Effect.gen(function* () {
    const sql = yield* SqlClient.SqlClient
    const hub = yield* Effect.acquireRelease(PubSub.bounded<{ readonly topic: string; readonly payload: string }>(2048), PubSub.shutdown)
    const sub = yield* PubSub.subscribe(hub)
    const persist = (batch: Chunk.Chunk<{ readonly topic: string; readonly payload: string }>) =>
      sql.withTransaction(Effect.forEach(Chunk.toReadonlyArray(batch), (e) => sql`INSERT INTO events (topic, payload) VALUES (${e.topic}, ${e.payload})`, { concurrency: 1 }))
    yield* Effect.forkScoped(Stream.fromQueue(sub).pipe(Stream.groupedWithin(100, Duration.millis(250)), Stream.mapEffect(persist), Stream.runDrain))
    return { publish: (topic: string, payload: string) => PubSub.publish(hub, { topic, payload }).pipe(Effect.asVoid) } as const
  }),
}) {}
```

[SUBSCRIPTION_VALUE]:
- Law: `PubSub.subscribe` executes inside the scoped generator before `Effect.forkScoped` — subscribing inside the forked fiber races the producer and silently drops messages published between constructor return and fork start.
- Law: `Stream.groupedWithin(count, window)` batches by whichever threshold hits first and flushes partial chunks on time expiry, so the drain observes every published message; an interrupted drain leaves unprocessed messages in the queue as back-pressure, never silent loss.
- Reject: an inline handler that cannot detach, a finalizer-owned unsubscribe split from its attach, and a foreign callback running arbitrary downstream domain logic.

## [04]-[MARSHAL_AND_HANDOFF]

[HOST_MARSHAL]:
- Use: worker-pool decode jobs, `postMessage`/`MessagePort` round trips, `requestAnimationFrame`/main-thread-affine reads, and any work pinned to a runtime that is not the calling fiber's.
- Law: a `Runtime`/`Scope` is captured once at the composition root and the marshal effect runs foreign-thread work through `Runtime.runPromiseExit(runtime)` — `postMessage` and worker `onmessage` swallow thrown errors and a missing port silently degrades to dropped work, so the seam reifies every foreign outcome into an `Exit` and lifts it through `Effect.mapError`, never trusting the host to propagate.
- Law: cancellation normalizes once into the seam's failure vocabulary — fiber interruption is structural and `Effect.retry` never re-runs it, while a local `Effect.timeout` and an external `AbortSignal` carry distinct typed evidence (a `reason: "aborted"` row) — and cancellation is never transient: the abort arm is the first predicate every `Effect.retry({ while })` refuses, so a retry policy can never resurrect cancelled work.
- Reject: a `self`/`globalThis`/`window` read inside a reusable transform, a fire-and-forget `port.postMessage` whose rejection is unobserved, and a worker callback that resolves a bare `Promise` no fiber awaits.

[HANDOFF_DRAIN]:
- Use: a high-frequency producer (a worker emitting decode progress, a pointer-move stream, a socket frame burst) handing off to a slower interior consumer.
- Law: a high-frequency callback submits intent and returns — a `SubscriptionRef<A>` is the latest-value cell for a per-tick consumer that needs only the current state, a `Queue`/`PubSub` is the log for a consumer that must observe every intermediate; the consumer's read contract selects the carrier, and producer back-pressure is independent of consumer pacing.
- Law: a bounded carrier's full-behavior is the seam's declared policy stated where the writer is constructed — `Queue.bounded` suspends the producer, `Queue.dropping` discards the newest, `Queue.sliding` evicts the oldest; the unbounded form is admitted only when the producer is provably finite.
- Reject: blocking inside the foreign callback, mutating interior state from it, a `SubscriptionRef` whose `changes` consumer re-enters the producer, and an unbounded `Queue` fed by an open-ended host event.

```ts conceptual
import { Cause, Data, Effect, Queue, Runtime, Schedule, Scope, Stream } from "effect"

class MarshalFault extends Data.TaggedError("MarshalFault")<{ readonly reason: "worker" | "aborted" }> {}

class DecodeWorkerPool extends Effect.Service<DecodeWorkerPool>()("domain/DecodeWorkerPool", {
  scoped: Effect.gen(function* () {
    const scope = yield* Effect.scope
    const inbox = yield* Effect.acquireRelease(Queue.dropping<{ readonly job: Uint8Array }>(1024), Queue.shutdown)
    const marshal = (worker: Worker, job: Uint8Array): Effect.Effect<Uint8Array, MarshalFault> =>
      Effect.async<Uint8Array, MarshalFault>((resume) => {
        const onMessage = (e: MessageEvent<Uint8Array>) => resume(Effect.succeed(e.data))
        const onError = () => resume(Effect.fail(new MarshalFault({ reason: "worker" })))
        worker.addEventListener("message", onMessage, { once: true }) // BOUNDARY ADAPTER: host event wiring
        worker.addEventListener("error", onError, { once: true })
        worker.postMessage(job, [job.buffer])
        return Effect.sync(() => { worker.removeEventListener("message", onMessage); worker.removeEventListener("error", onError) })
      }).pipe(Effect.retry({ while: (f) => f.reason !== "aborted", schedule: Schedule.recurs(2) }))
    const drainOn = (worker: Worker) =>
      Stream.fromQueue(inbox).pipe(Stream.mapEffect(({ job }) => marshal(worker, job)), Stream.runDrain, Effect.forkIn(scope))
    return { submit: (job: Uint8Array) => Queue.offer(inbox, { job }).pipe(Effect.asVoid), attach: drainOn } as const
  }),
}) {}

const _bridge = <A>(runtime: Runtime.Runtime<never>, scope: Scope.Scope, work: Effect.Effect<A>): Promise<A> =>
  Runtime.runPromise(runtime)(Effect.scoped(Scope.extend(work, scope))) // BOUNDARY ADAPTER: foreign-thread entry, interruption is never a retried fault
```

[SCOPE_AND_LEASE]:
- Law: a derived scope isolates exactly one named axis — a forked drain fiber, a per-key lease, a migration pool beside a read pool — and the wrong derivation silently shares the axis the caller meant to isolate; `Layer.fresh(dep)` forces an isolated instance under the default reference-memoized diamond, and `Effect.forkScoped` versus `Effect.forkIn(scope)` selects which scope owns the fiber lifetime.
- Law: a per-key resource family is `RcMap` (reference-counted, idle-TTL eviction) and a homogeneous fungible pool is `Pool.make`/`makeWithTTL` — `RcMap.get` acquires-or-shares inside a scope and the entry releases when the last borrower's scope closes, so a hand-kept `HashMap<K, Resource>` plus a manual refcount is the retired form; `RcRef` is the single-resource degenerate case.
- Law: a lease, rental, or pooled permit releases exactly once on every exit path — success, typed failure, and interruption — through `Effect.acquireRelease` keyed on the logical extent, and a throwing release is contained so it never aborts the remaining LIFO sweep.
- Reject: a parent and child scope both finalizing one connection, subscription set, or abort signal; a pooled buffer or rate permit escaping as public service state; a `Layer` default memoized where two consumers require independent state.

[MEMO_KEY]:
- Law: a memo key encodes every dimension that changes output — content, decode policy, capability version, and foreign identity feed one structured key compared by an `Equivalence`, never a `${a}:${b}` signature string nor a `${fault._tag}:${fault.code}:${digest}` dedupe key whose collision is silent.
- Law: `Effect.cachedFunction(f, eq?)` and `RcMap`/`Effect.cachedInvalidateWithTTL` are the memo owners — the `Equivalence` keys the structured value directly, so a key that is itself a `Data.Class` or tagged value compares by `Equal.equals` with no projection step.
- Reject: a path-only, type-only, or `Option`-partial cache key that omits a dimension the body reads; a `HashMap` keyed on a mutable foreign handle whose identity drifts under reconnection; a `Set<string>` dedupe ledger where `HashSet` of the tagged value coalesces structurally.

## [05]-[STATE_CELLS]

A boundary lifecycle is a closed state family in one cell, never a boolean ladder; the transition stays pure and replayable, and waiters wake only from committed state.

[TOKEN_LIFECYCLE]:
- Law: session, singleton, and cross-call boundary lifetime is one `Data.TaggedEnum` family — `Pending`/`Live`/`Failed` — held in a `SubscriptionRef` so every observer reads the committed state through `changes`, never a `boolean` open flag plus a nullable handle that can disagree; a `Ref.modify` returning the transition outcome is the atomic commit and the losing acquisition releases the resource it built.
- Law: a `Live` case carries the owning token, so a stale teardown succeeds only while its token still owns the cell (`current._tag === "Live" && current.token === mine`); re-opening replaces the whole cell because a `Failed` cell is escaped only by a fresh value carrying typed evidence, never by mutating a flag back.
- Law: `SubscriptionRef.set` publishes one immutable replacement so multi-field state never tears, and `changes` emits only after the commit — a per-tick consumer (a `ui` recovery fallback) reads the latest through `SubscriptionRef.get`, a must-see-every-transition consumer drains `changes`.
- Reject: a `boolean` lifecycle flag, a nullable handle beside a state enum, a teardown that can dispose a replacement session, and a waiter woken from an aborted transition.

[DRAIN_COORDINATION]:
- Law: a quiescence gate reads phase, in-flight count, and deadline as one `STM.commit` snapshot — admission is fenced (`STM.check(phase._tag === "Open")`) while mid-flight work reaches a typed terminal, so a flag-based close that still admits through a second cell is the torn form STM retires.
- Law: the in-flight counter transitions inside the same transaction that reads the phase, never a `Ref` incremented beside an independent phase `Ref`; settling decrements and a zero count under `Draining` is the drained signal a `TDeferred` publishes once.
- Reject: closing from one flag while another cell still admits; acting on a change fired from an aborted transition; a poll loop where `STM.check` suspends until the gate opens.

```ts conceptual
import { Data, Effect, Ref, SubscriptionRef } from "effect"

type Gate = Data.TaggedEnum<{
  readonly Pending: {}
  readonly Live: { readonly token: string; readonly session: { readonly close: Effect.Effect<void> } }
  readonly Failed: { readonly reason: string }
}>
const Gate = Data.taggedEnum<Gate>()

const open = (cell: SubscriptionRef.SubscriptionRef<Gate>, acquire: Effect.Effect<{ readonly close: Effect.Effect<void> }, string>) =>
  Effect.gen(function* () {
    const token = yield* Effect.sync(() => crypto.randomUUID())
    const claimed = yield* Ref.modify(cell, (g) => g._tag === "Pending" ? [true, Gate.Live({ token, session: { close: Effect.void } })] : [false, g])
    return claimed
      ? yield* acquire.pipe(
          Effect.matchEffect({
            onFailure: (reason) => SubscriptionRef.set(cell, Gate.Failed({ reason })).pipe(Effect.zipRight(Effect.fail(reason))),
            onSuccess: (session) => SubscriptionRef.set(cell, Gate.Live({ token, session })).pipe(Effect.as(session)),
          }))
      : yield* SubscriptionRef.get(cell).pipe(Effect.flatMap(Gate.$match({
          Pending: () => Effect.fail("regressed"),
          Live: ({ session }) => Effect.succeed(session),
          Failed: ({ reason }) => Effect.fail(reason),
        })))
  })
```

## [06]-[LAYER_COMPOSITION]

[REQUIREMENT_ELIMINATION]:
- Law: `Layer.provide(dep)` collapses a requirement edge retaining only consumer output — the provider vanishes; `Layer.provideMerge(dep)` collapses the edge and unions the provider output downstream; misclassifying an edge is a type error or a silent capability leak.
- Law: a diamond DAG deduplicates a shared provider by reference under default memoization; `Layer.fresh` forces an isolated instance where shared state would race (a migration pool beside a read pool).
- Law: `dependencies: [Dep.Default]` auto-provides upstream layers into a service's `Default`; `DefaultWithoutDependencies` preserves the raw `R` for test substitution through `Layer.provide(TestDep)`.
- Use: `Layer.scoped` to attach finalizers to the layer scope, `Layer.effect` for a no-lifecycle layer, `Layer.succeed` to enforce the full service shape at compile time (omitting a method is a type error), and `Layer.unwrapEffect`/`unwrapScoped` for deferred topology selection.
- Reject: relying on accidental exposure; a partial layer reaching the root; a second cache, retry, or correlation owner where one layer composes.

[OUTPUT_SHAPING]:
- Law: `Layer.project(From, To, f)` narrows a single-tag output to a consumer-facing subset (unions are rejected — collapse via `provide` first); `Layer.discard` zeros the output to initialization-only; `Layer.passthrough` re-exposes requirements as outputs for test introspection only.
- Law: `Layer.match`/`matchCause` rewrite the construction graph on a typed failure or a full cause — `Layer.match` receives the typed `E` and lets defects and interrupts propagate, `matchCause` receives `Cause<E>` for cause-level fallback.
- Boundary: the root assembly merges every subgraph at `RIn = never` through `Layer.mergeAll`, `Layer.launch` converts it to a long-running `Effect`, and the platform runtime (`NodeRuntime.runMain` / a browser runtime) owns signals, finalization, and exit codes — a one-time edge operation.
- Reject: exposing every internal node and creating accidental coupling; a build-phase `tap`/`annotateLogs` mistaken for a per-request operation.

```ts conceptual
import { Context, Duration, Effect, Layer } from "effect"

const _Transport = Context.GenericTag<{ readonly endpoint: string }>("Cmp/Transport")
const _Collector = Context.GenericTag<{ readonly endpoint: string; readonly window: Duration.Duration }>("Cmp/Collector")
const _Pool = Context.GenericTag<{ readonly endpoint: string; readonly slot: string }>("Cmp/Pool")

const _transport = (region: string) => Layer.succeed(_Transport, { endpoint: `otlp://${region}.collector:4317` })
const _collector = Layer.effect(_Collector, _Transport.pipe(Effect.map((t) => ({ endpoint: t.endpoint, window: Duration.seconds(30) }))))
const _pool = (slot: string) => Layer.effect(_Pool, _Transport.pipe(Effect.map((t) => ({ endpoint: t.endpoint, slot })))) // both consume _Transport: a diamond

const _root = (region: string): Layer.Layer<typeof _Collector.Identifier | typeof _Pool.Identifier> => // RIn = never proves the graph is closed
  _collector.pipe(
    Layer.provideMerge(_pool("read").pipe(Layer.fresh)), // provideMerge unions _Pool downstream; Layer.fresh forces an isolated instance the memoized diamond would otherwise share
    Layer.provide(_transport(region)), // provide collapses the _Transport edge: the provider vanishes from the output
  )
```

## [07]-[WIRE_CONTRACTS]

[PROTOCOL_EDGE]:
- Law: wire shapes stay protocol-shaped at the edge — one `Schema.transform(wire, domain, { decode, encode })` is the only site where protocol and interior schemas meet, and interior owners carry no codec attributes or transport objects.
- Law: a bidirectional transform preserves round-trip fidelity; a derived field present in domain but absent from wire is intentional asymmetry the encode side drops, and layered schemas (`Schema.Uint8ArrayFromBase64` on the wire leg, `Schema.Uint8ArrayFromSelf` on the domain leg) each own one concern.
- Law: an inner envelope rejects drift — unknown members, missing required keys, and depth excess fail before admission through `Schema` filters — while an outer wrapper tolerates only declared extension material.
- Reject: a separate parser and serializer pair; a last-write-wins or best-effort parse for an owned protocol shape; a post-decode mutation step.

[CONTRACT_SURFACE]:
- Law: one `HttpApi` graph sources server handlers, typed HTTP clients, and workflow proxies — `HttpApiClient.makeWith` for the full graph, `.group`/`.endpoint` for narrowed scopes — so capability is scoped statically and a caller cannot invoke an undeclared endpoint.
- Law: `HttpApiBuilder.group` is a total function — the type signature encodes which `handle` calls remain open and narrows with each handled endpoint until exhaustion is a compile-time proof; a handler body is a thin one-line delegation to a protocol-agnostic service method.
- Law: one `Schema.TaggedError` (an `HttpApi` error via `.addError`) propagates to every endpoint, with `HttpApiSchema.annotations` binding the default status and a computed getter overriding per reason; an auth failure reuses the same fault type, never a parallel one.
- Reject: a handler body exceeding a delegation (domain logic leaking past the service boundary); a per-endpoint error type where one fault with a `reason` row adds it.

```ts conceptual
import { HttpApi, HttpApiEndpoint, HttpApiGroup, HttpApiSchema } from "@effect/platform"
import { Effect, Record as R, Schema as S } from "effect"

const _Policy = {
  unauthorized: { status: 401, retryable: false, log: Effect.logWarning },
  notFound:     { status: 404, retryable: false, log: Effect.logInfo    },
  unavailable:  { status: 503, retryable: true,  log: Effect.logError   },
} as const satisfies Record<string, { status: number; retryable: boolean; log: (...a: ReadonlyArray<unknown>) => Effect.Effect<void> }>

class Fault extends S.TaggedError<Fault>()("Fault", { // wire enum derives from the policy anchor; the lone cast is the non-emptiness witness
  reason: S.Literal(...(R.keys(_Policy) as [keyof typeof _Policy, ...Array<keyof typeof _Policy>])),
}, HttpApiSchema.annotations({ status: 500 })) {
  get status()    { return _Policy[this.reason].status    }
  get retryable() { return _Policy[this.reason].retryable }
}

const _Api = HttpApi.make("tenants").addError(Fault).add(
  HttpApiGroup.make("tenant").add(HttpApiEndpoint.get("byId", "/tenants/:id").setPath(S.Struct({ id: S.UUID })).addSuccess(S.Struct({ id: S.UUID, name: S.String }))),
)
```

[BYTE_IDENTITY]:
- Law: semantic equality and byte equality are different contracts; raw octets are captured before decode, canonical octets are emitted once, and a content-addressed artifact crosses as a `Uint8Array` plus its hash — never parsed and reserialized between verification, signing, or forwarding.
- Law: a signed numeric or timestamp field survives only as raw token bytes because decode-then-encode re-spells floats and trims timestamps; the boundary forwards the original bytes through the streaming wire fence.
- Boundary: a receipt carries coordinates and a hash, never the payload bytes; an artifact frame consumes the server-streamed content-addressed bytes over the existing wire fence.
- Reject: parse-and-reserialize between two byte-identity operations; choosing the encoder per site where one encoder per byte-identity domain is a composition-time invariant.
