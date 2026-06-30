# [STACKS_TYPESCRIPT]

This folder is the TypeScript stack router. It routes language, shape, surface, rail, boundary, and system-API decisions to the concept page that owns the coding choice. The router builds one admission-first paradigm: raw input is decoded once through one Schema, decoded values travel typed Effect rails, behavior lives on tagged-union dispatch surfaces, and projections leave through encode at explicit Layer boundaries.

Pages carry no outside-source blocks, release narration, provenance, process state, project anchors, tool context, source-footnote blocks, or meta commentary. Pages name exact code, package, operator, combinator, and command spellings in code spans; verification happens before authoring, and the page states doctrine as fact.

## [01]-[ATLAS]

This table is the lookup by reader decision.

| [INDEX] | [DECISION]             | [READ]                                            | [STATE]   |
| :-----: | :--------------------- | :------------------------------------------------ | :-------- |
|  [01]   | language shape         | [language](language.md)                           | finalized |
|  [02]   | domain shape           | [shapes](shapes.md)                               | finalized |
|  [03]   | surface and dispatch   | [surfaces and dispatch](surfaces-and-dispatch.md) | finalized |
|  [04]   | result and effect flow | [rails and effects](rails-and-effects.md)         | finalized |
|  [05]   | host and wire boundary | [boundaries](boundaries.md)                       | finalized |
|  [06]   | system API replacement | [system APIs](system-apis.md)                     | finalized |

## [02]-[DOCTRINE]

Sixteen laws in five groups govern every TypeScript decision in this stack. Concept pages instantiate them; no page restates them. The laws exist so correctness is structural rather than disciplinary: decode-once makes the interior total over valid values; tagged unions plus exhaustive `Match` convert change into compile-time pressure; vocabulary-as-values makes behavior recoverable from declarations alone; Schema-derivation makes every secondary surface provably consistent with its single source. Density is the consequence, not the goal — when one Schema carries the family, every remaining declaration is load-bearing. The atlas is sized for large systems: total lines and public surface grow sublinearly with capability because every owner is declared with the capacity to absorb the family it anchors — growth lands as variants, vocabulary rows, and policy values inside existing owners, never as new surfaces beside them. Enforcement is doctrine-first: `tsconfig` strictness, the lint configuration, and the Nx module-boundary graph encode these laws — the doctrine authors the tool, never the reverse. Lint and type findings against these laws are architecture pressure: fix the shape, not the diagnostic.

[FLOW]:
- `EXPRESSION_SPINE` — all domain logic is expression-shaped; dependent steps compose monadically through `Effect.flatMap` and independent computations compose applicatively through `Effect.all` and `Effect.zipWith` — dependence licenses sequence, independence licenses accumulation, and the carrier, never a flag, selects the combination algebra. A `flatMap` chain over independent operands reports only the first failure and discards the rest, so abort-versus-accumulate is a correctness decision fixed once at the carrier. Statements survive only inside `BOUNDARY ADAPTER`-marked kernels and platform-forced callbacks, and any page that shows one names the exemption. Composition runs through `pipe`, `Function.flow`, monadic combinators, `Match.tagsExhaustive`, and `Data.taggedEnum().$match`.
- `BOUNDARY_ADMISSION` — raw material is decoded exactly once into an evidence-carrying owner; interior code never re-validates and never sees `null`, `undefined`, sentinels, or provider shapes. One Schema decodes or rejects through `Schema.decodeUnknown`; the `ParseError` lifts into the Effect error channel at the same seam; `Option<T>` carries absence, the tagged error channel carries fallibility, and a `Promise` or thrown exception converts at the owning boundary through `Effect.tryPromise` or `Effect.try`.

[SHAPE]:
- `SHAPE_BUDGET` — a concept owns exactly one runtime authority; variants are tags inside one closed family, never sibling schemas or parallel types. `Schema.Class`, `Model.Class`, and `Data.TaggedEnum` own the family; projections derive through `Schema.pick`, `Schema.omit`, `Schema.partial`, and `Schema.extend`. A fresh Schema per shape, a standalone `type`/`interface` mirroring a runtime shape, and a standalone branded-primitive export are the named collapse triggers, not style preferences.
- `DEEP_SURFACES` — prefer one rich polymorphic surface over many shallow ones; each module exports one or two symbols and keeps every other declaration `_`-prefixed and integrated into those exports. One deep owner that holds a full concern beats four fragments that scatter it across files.
- `MODAL_ARITY` — one entrypoint owns all call modalities; singular, plural, batch, and stream discriminate on the shape of the input value — tag, structural pattern, or arity — never on name suffixes or boolean knobs. A non-empty tuple `[T, ...ReadonlyArray<T>]`, `Effect.forEach`, and `Stream` absorb arity; a request `Data.TaggedEnum` plus one `$match` absorbs verb families. A parallel parameter that re-describes the input — a batch, many, or mode flag beside the value — is the rejected form, because the discriminant must be recoverable from the value itself.
- `ANTICIPATORY_COLLAPSE` — an owner is shaped for the family it will absorb, not the instance in hand: the moment a second variant, dimension, knob, or modality is conceivable, the shape generalizes so the next requirement lands as a tag, a vocabulary row, a policy value, or a carrier swap with zero new surface. The proof of a correct shape is the diff of the next feature — one declaration inside the owner, every consumer untouched or broken loudly at compile time. Sizing for the instance and widening later is the rejected order: widening after call sites exist multiplies surfaces, widening before they exist is one polymorphic dispatch.

[DERIVATION]:
- `VOCABULARY_VALUES` — configuration enters as one `as const satisfies Record<...>` vocabulary whose rows carry their own behavior — status, retry, schedule, log level, transport — never as flag sets whose combinations the implementation re-derives. `keyof typeof` projects the discriminant, indexed access projects each axis, and computed getters read the row; behavior rows live with the vocabulary that selects them.
- `DERIVED_LOGIC` — when variants share generative structure, the logic is derived — a vocabulary lookup, an `Array.reduce` fold, a `Match` over a closed family — never enumerated `if`/`switch` arms. One primary correspondence is declared and every secondary map derives from it; `Match` over a keyed domain that a vocabulary already maps is the rejected form — keyed domains dispatch through vocabulary lookup, `Match` owns structural and predicate dispatch on non-keyed shapes.
- `DERIVED_TYPES` — types are computed from runtime anchors so one declaration yields the family: `typeof schema.Type`, `keyof typeof vocabulary`, indexed access, mapped types with template-literal key remapping, and conditional return types replace per-shape or per-variant copies. A standalone `type X = { ... }` that `typeof` over a runtime anchor already gives is the rejected form.
- `SYMBOLIC_REFERENCE` — names, paths, discriminants, and correspondences travel as symbols and derived values — vocabulary keys, `keyof typeof`, `Record.keys` spreads into `Schema.Literal`, tagged `_tag` discriminants — never as string literals that restate something the program already knows.
- `SEMANTIC_NAMING` — every file, module, class, function, parameter, field, tag, test, and region name uses the bounded context's canonical term, grammatical role, and tense. One semantic word is the default; two words are allowed when owner plus action, result, axis, or boundary is load-bearing; three words are the ceiling unless an external API or ambiguity proof requires more. Operations use action verbs, values and receipts use result nouns, vocabularies use stable noun or adjective rows, and boundary adapters preserve foreign names only at the seam. Renaming for variety, tense drift, abbreviations, prefix or suffix families, and parallel file or member labels for one concept are rejected.

[MATERIAL]:
- `LIBRARY_DEPTH` — the Effect ecosystem is the standard library: `effect` owns rails, effects, schedules, immutable collections, `Schema`, and `Match`; the `@effect/*` set owns platform, SQL, RPC, cluster, workflow, AI, and telemetry. Effect data structures — `HashMap`, `HashSet`, `Chunk`, `Option`, `Either`, `Duration`, `Order`, `Predicate`, the `Array`/`Record`/`Struct` modules — are the default; JS stdlib `Map`/`Set`/`Array`/`Object`/`null` survive only at FFI and serialization boundaries. Use the deepest operator, combinator, or generated surface the package itself reaches for; wrappers, rename adapters, and stdlib-first reflexes are rejected.
- `DEFINITION_TIME_ASPECTS` — cross-cutting capability — decode, observability, retry, resource lifetime — attaches at the seam where it belongs. Decode and brand attach at the single Schema; observability attaches through `Effect.withSpan`, `Effect.annotateLogs`, and `Metric` composed onto the rail; composition-time policy — retry through `Schedule`, lifetime through `Effect.acquireRelease` and `Layer.scoped` — attaches as effect transformers. `Effect.fn("span")(body, pipeline)` is the one seam where the body runs once per attempt and the pipeline carries resilience; policy pushed inside the body, or admission hoisted above the decode seam, stops being recoverable from its declaration.

[INTEGRATION]:
- `ROOT_REBUILD` — new capability is woven into the owning Schema or service as if it had always existed; reshape the owner rather than appending beside it. No shims, compat aliases, deprecated layers, barrel re-exports, or migration surfaces — break the API when the collapse improves the system.
- `ONE_HOP_RESOLUTION` — a name resolves to its semantics in one hop: no alias-to-type-to-const chains, no forwarding helpers, no helper or util shells, no convenience wrappers that rename or forward an external API. A `_`-prefixed symbol that takes two jumps to trace, or a `const X = _X` re-export, marks a layer to delete.
- `COMPOSED_IMPLEMENTATION` — a feature of any complexity is implemented by composing the page owners — one Schema, typed Effect rails, `Match` dispatch surfaces, Layer boundaries, vocabulary policy — before any new scaffold is named. The pages are one body, and the same concern resolves identically wherever it appears. A need with no composed spelling marks a missing variant in an owning page's law: the law extends first, the feature lands second. Snippets show this composition at full operator depth. Flat code — logic below the operator depth the Effect ecosystem reaches — is surface sprawl in time: it re-derives, line by line, what a deeper composed form states once.

## [03]-[COLLAPSE_SCAN]

Run this scan on every edit. Any signal triggers the move; three or more instances make it mandatory.

| [INDEX] | [SIGNAL]                                              | [MOVE]                                             |
| :-----: | :---------------------------------------------------- | :------------------------------------------------- |
|  [01]   | sibling names share a prefix or suffix                | one modality-polymorphic entrypoint                |
|  [02]   | same return rail, signatures differ only by arity     | input-shape discrimination on a non-empty tuple    |
|  [03]   | functions differ only by a literal                    | parameterize; the literal becomes a vocabulary row |
|  [04]   | boolean parameter selects between two bodies          | one derived body or one vocabulary value           |
|  [05]   | function calls exactly one other function             | delete the hop                                     |
|  [06]   | parallel `Match.when`/`if` arms classify into tiers   | vocabulary lookup or threshold iteration           |
|  [07]   | several schemas or types model one concept            | one Schema plus `pick`/`omit`/`partial`/`extend`   |
|  [08]   | standalone `type`/`interface` mirrors a runtime shape | derive via `typeof anchor.Type`/`keyof typeof`     |
|  [09]   | standalone branded-primitive export                   | inline `Schema.brand` as a field modifier          |
|  [10]   | one-use module-level `const` that is not an anchor    | inline into the owning rail                        |
|  [11]   | wrapper renames or forwards a package API             | use the package surface directly                   |
|  [12]   | the same 2-4 combinators recur together               | one parameterized rail transformer                 |
|  [13]   | absence modeled as `null`/`undefined` in domain       | `Option<T>`, decoded by `Schema.optionalWith`      |

## [04]-[RULE_ENFORCEMENT]

TypeScript has a structural type system but no totality checker for open shapes, so the strict compiler, the lint configuration, and the Nx module-boundary graph are the doctrine's compiled form, legislated harder than a language with a closed-family checker needs. `tsconfig` strictness (`strict`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, `verbatimModuleSyntax`), the dual-compiler `tsgo`/`tsc` typecheck floor, the lint rule set, and the `@nx/enforce-module-boundaries` browser/node/neutral tag graph are the enforcement surfaces; the manifest owns every rule pin. The loop is one-directional — a doctrine page legislates, a gate enforces; a rule never introduces law of its own.

- Mapping law: every doctrine law maps to its enforcing gate. Exhaustiveness rides `Match.tagsExhaustive`, `Match.discriminatorsExhaustive`, and `Data.taggedEnum().$match` whose missing arm is a compile error; absence-leakage rides `noUncheckedIndexedAccess` and the `null`/`undefined`-ban lint rule routing to `Option`; shape proliferation rides the no-parallel-schema lint rule and `verbatimModuleSyntax`; surface sprawl rides the export-count and `_`-prefix lint rules; stdlib leakage rides the banned-import rule (`Map`/`Set`/`Object.entries` to the Effect equivalents); package boundary rides the Nx tag graph. A law with no mechanical gate is captured as a lint rule.
- Promotion law: a doctrine-breaking anti-pattern that no shipped compiler error or lint rule already rejects — schema spam, a standalone branded-type export, a fresh Schema per shape, a barrel re-export file, a thin rename wrapper, a `Match` chain duplicating a vocabulary — is captured as a lint rule and promoted to error. Style preferences and anything an existing gate already rejects are not new rules.
- Shape law: a rule describes the semantic shape of the anti-pattern — trigger, predicate, exemption — never a path or one-off symbol; every rule ships with positive spans that fire and valid dense code that must not.
- Finding law: a true positive is architecture pressure — fix the shape, never the diagnostic; a false positive or a fix that adds ceremony without improving the system is rule pressure — refine the rule. A `// @ts-expect-error`, a `// eslint-disable`, or an `as` cast that adds ceremony without improving correctness is itself the defect.

## [05]-[PAGE_CRAFT]

How pages in this folder are authored. The corpus is one body; these laws keep it coherent.

- Atlas law: this README owns doctrine and routing; each concept page owns one disjoint layer; a sibling concern is neither re-shown nor pointed to — cohesion comes from shared law, not linkage. The README is the only file that links.
- Zero meta: concept pages carry no provenance, source trace, release narration, process state, project, tool, or skill context.
- Page grammar: narrow index table, then family cards, then the snippet beside the rule it proves; the page ends at its last card section. Structure is identical across stack folders; content never is.
- Card fields are earned: `Use / Accept / Reject / Law / Boundary` lines appear on a card only where each one decides something; a field line that decides nothing is deleted, not filled.
- Snippet law: every snippet compiles under the active surface; identifiers are legal neutral names; placeholder strings such as `"<value-a>"` appear only inside literals; no project, host, or domain concept anchors a snippet.
- Snippet coverage: each snippet is doctrine-exemplary at full operator depth, roughly 3-4x denser than ordinary code, and exercises a surface region no other snippet in the corpus shows — variety within the doctrine, zero duplicated demonstrations. The region is the snippet's spotlight demonstration; finalized surfaces composed as supporting material occupy no region and duplicate nothing.
- Scale fidelity: a snippet shows the form at the shape it takes in a large system — decode, dispatch, rail, and vocabulary composed in one fence with the growth axis visible — never an isolated minimum; a statement-bearing snippet sits beside the Exemption line naming its platform-forced seam.
- Code names before prose: every member a card or snippet names — combinator, knob, schema constructor, Match terminal — is verified against the installed package implementation before it is written; an unconfirmable claim is not authored, and a nameable surface spelled as prose is a defect — the code span is the instruction.
- Card economy: cards are few, deep, and evidence-dense; near-peer cards merge until each retained card owns a decision cluster, and a card line carries exactly one decision. A thin card deciding one concept is a sibling line, not an owner.
- Snippet adherence: snippets obey the card they prove, compose finalized laws as supporting material, and reduce lines and surface through derivation, vocabulary dispatch, and package depth, never by deleting capability.
- Altitude routing: when two pages touch one fact, the ledger records the split — mechanics at the owning page, consequence at the consumer; prose re-teaching an owned mechanic is repaired by routing to the owner, while composing owned surfaces inside a snippet is supporting material and owns nothing.
- Reject columns are load-bearing: every `Use` names the spelling, wrapper, or local pattern it deletes.
- Tables enumerate, cards legislate: rows stay atomic and narrow — no prose cramming, no links inside cells; nuance moves to a card.
- Route scope is README-local: lookup rows and conflict rules live in README files; concept pages carry only the law they own.
- Manifest truth: package versions, admitted packages, the workspace catalog, tool settings, and the module-boundary tag graph live in `pnpm-workspace.yaml`, the per-package manifests, and tool configuration; no package-named pages; a package is named only where it changes the implementation choice.

## [06]-[CORPUS_LAW]

How the corpus accretes. The folder is one cohesive body, not isolated pages; atlas order is implementation order. The atlas `[STATE]` column is the law registry: a `finalized` page is binding law for every page authored after it; a `partial` page carries no authority and awaits rebuild; a `target` page exists only as roadmap scope. Finalization is a one-way gate — a context-free cold grade of the full page and every snippet, converging to a zero-edit pass, flips the state; the producer's grade admits, the cold grade decides.

- Three-layer inheritance: every page is authored under the doctrine, under every finalized page — adhered to, never restated, never referenced, never contradicted — and from its own source reservoir.
- Prose consumes earlier layers as given: vocabulary, owners, rails, and policy values arrive settled, never re-taught, and the page spends its lines only on its own layer.
- Reservoir residue: a page's source workspace deliberately holds more than the page prints, and it outlives the page — later enrichment and snippet work mine it without source-footnoting it; depth beyond one page's budget is corpus capital, never waste.
- Snippet stacking: code fully captures the card it proves, then composes on earlier layers' law at full doctrine depth — the new surface in the spotlight, established surfaces as supporting material, every touched concern built at the standard its owning finalized page legislates.
- Region ledger: the workspace root keeps one ledger of owned regions — page concerns at card altitude, snippet demonstrations at fence altitude. Snippet rows are written before code exists, page rows at finalization, and a duplicated region is repaired by routing to its owner, never by re-teaching — the ledger is what makes ownership checkable without re-reading the corpus.
- Purpose: the corpus is loaded as the operative standard in place of weaker context; zero-meta, zero-anchor, and stated-as-fact are absolute because any provenance, hedge, or stale claim poisons every downstream generation that loads the page.
