# [STACKS_CSHARP]

This folder is the C# stack router. It routes language, shape, surface, rail, boundary, algorithm, system-API, and domain decisions to the concept page that owns the coding choice. The router builds one admission-first paradigm: raw input is admitted once through generated owners, admitted values travel typed rails, behavior lives on generated dispatch surfaces, and projections leave at explicit boundaries.

Pages carry no outside-source blocks, release narration, provenance, process state, project anchors, tool context, source-footnote blocks, or meta commentary. Pages name exact code, package, operator, generated-surface, and command spellings in code spans; verification happens before authoring, and the page states doctrine as fact.

## [01]-[ATLAS]

This table is the lookup by reader decision.

| [INDEX] | [DECISION]              | [READ]                                            | [STATE]   |
| :-----: | :---------------------- | :------------------------------------------------ | :-------- |
|  [01]   | language shape          | [language](language.md)                           | finalized |
|  [02]   | domain shape            | [shapes](shapes.md)                               | finalized |
|  [03]   | surface and dispatch    | [surfaces and dispatch](surfaces-and-dispatch.md) | finalized |
|  [04]   | result and effect flow  | [rails and effects](rails-and-effects.md)         | finalized |
|  [05]   | host and wire boundary  | [boundaries](boundaries.md)                       | finalized |
|  [06]   | numeric approach        | [algorithms](algorithms.md)                       | finalized |
|  [07]   | system API replacement  | [system APIs](system-apis.md)                     | finalized |
|  [08]   | domain routing          | [domain](domain/README.md)                        | finalized |
|  [09]   | hosting and runtime     | [runtime](domain/runtime.md)                      | finalized |
|  [10]   | concurrency and streams | [concurrency](domain/concurrency.md)              | finalized |
|  [11]   | telemetry signal        | [diagnostics](domain/diagnostics.md)              | finalized |
|  [12]   | boundary validation     | [validation](domain/validation.md)                | finalized |
|  [13]   | resilience policy       | [resilience](domain/resilience.md)                | finalized |
|  [14]   | wire transport          | [transport](domain/transport.md)                  | finalized |
|  [15]   | data persistence        | [persistence](domain/persistence.md)              | finalized |
|  [16]   | embedded durability     | [durability](domain/durability.md)                | finalized |
|  [17]   | postgres surface        | [postgres](domain/postgres.md)                    | finalized |
|  [18]   | data interchange        | [data interchange](domain/data-interchange.md)    | finalized |
|  [19]   | compute lane            | [compute](domain/compute.md)                      | finalized |
|  [20]   | render and visuals      | [visuals](domain/visuals.md)                      | finalized |
|  [21]   | retained interaction    | [interaction](domain/interaction.md)              | finalized |

## [02]-[DOCTRINE]

Seventeen laws in five groups govern every C# decision in this stack. Concept pages instantiate them; no page restates them. The laws exist so correctness is structural rather than disciplinary: admission-once makes the interior total over valid values; closed families convert change into compile-time pressure; policy-as-values makes behavior recoverable from declarations alone; derivation makes every secondary surface provably consistent with its primary. Density is the consequence, not the goal — when one declaration carries the family, every remaining line is load-bearing. The atlas is sized for large systems: total lines and public surface grow sublinearly with capability because every owner is declared with the capacity to absorb the family it anchors — growth lands as cases, rows, and policy values inside existing owners, never as new surfaces beside them. Enforcement is doctrine-first: `.editorconfig` severities, build-injected analyzers, and the repository's own analyzer encode these laws — the doctrine authors the tool, never the reverse. Analyzer findings against these laws are architecture pressure: fix the shape, not the diagnostic.

[FLOW]:
- `EXPRESSION_SPINE` — all domain logic is expression-shaped; dependent steps compose monadically and independent computations compose applicatively — dependence licenses sequence, independence licenses accumulation, and the carrier, never a flag, selects the combination algebra. Statements survive only inside measured kernels and platform-forced boundaries, and any page that shows one names the exemption. Composition runs through `Bind`, `Map`, query expressions, switch expressions, and generated `Switch` dispatch; `ref struct` fold kernels and span loops are the named kernel exemption.
- `BOUNDARY_ADMISSION` — raw material is admitted exactly once into an evidence-carrying owner; interior code never re-validates and never sees nulls, sentinels, or provider shapes. Generated factories and validation partials admit or reject; one rail bridge converts the generated outcome into `Fin<T>` or `Validation<Error,T>`; `Option<T>` carries absence; exceptions convert at the owning boundary.

[SHAPE]:
- `SHAPE_BUDGET` — a concept owns exactly one type; variants are cases inside one closed family, never sibling types. `[Union]`, `[SmartEnum<TKey>]`, `[ValueObject<T>]`, and `[ComplexValueObject]` own the family; families are closed internally and open only where foreign code must extend without editing the owner. Three or more parallel shapes, sibling factories, repeated dispatch arms, or single-call helpers is the collapse trigger, not a style preference.
- `DEEP_SURFACES` — prefer one rich polymorphic surface over many shallow ones; each module exposes one entrypoint family and keeps internals private. One deep owner that holds a full concern beats four fragments that scatter it.
- `MODAL_ARITY` — one entrypoint owns all call modalities; singular, plural, batch, and stream discriminate on the shape of the input value — type, case, pattern, or arity — never on name suffixes or boolean knobs. `params` collections, collection expressions, and one `ReadOnlySpan<T>` boundary absorb arity; a request `[Union]` plus one total dispatch absorbs verb families. Collapsing arity must not smuggle the knob back in: a parallel parameter that re-describes the input — a batch, many, or mode flag beside the value — is the rejected form, because the discriminant must be recoverable from the value itself.
- `ANTICIPATORY_COLLAPSE` — an owner is shaped for the family it will absorb, not the instance in hand: the moment a second case, dimension, knob, or modality is conceivable, the shape generalizes so the next requirement lands as a case, a row, a policy value, or a carrier swap with zero new surface. The proof of a correct shape is the diff of the next feature — one declaration inside the owner, every consumer untouched or broken loudly at compile time. Sizing for the instance and widening later is the rejected order: widening after call sites exist multiplies surfaces, widening before they exist is one polymorphic dispatch.
- `INTERFACE_SEAM` — an interface is a load-bearing seam, never a loose tag. It is the compose face — a member-bearing strategy, store, codec, or BCL stream and lifetime contract (`IAsyncEnumerable<T>`, `IDisposable`, `IAsyncDisposable`) — paired with an abstract-base implement seam that owns the shared state and template behavior; or the static-abstract self-constrained contract a generic dispatches on, a `where TSelf : IObjectFactory<TSelf,TKey,TError>` factory or a generic-math `where T : INumber<T>` scalar. The owner-vehicle is chosen once: a closed value-shape family the owner controls is a `[Union]`, `[SmartEnum]`, or `[ValueObject]` with total generated dispatch; concretes that share state or a foreign base are an abstract class at the seam; a strategy, store, or generated-and-catalogued family that foreign code implements or that publishes across an assembly or wire boundary is an interface floor with a minting factory and one polymorphic operation over the floor, the concrete held `internal` and swappable. A member-less marker is admissible only as a generic bound, never read by `is` or reflection; a capability switch is an attribute or a generated-owner conformance. Variance is read-direction discipline — `out` on producers, `in` on consumer callbacks — and modality rides a type parameter or a keyed service, never parallel `IFooForBar` names. Defaults derive from a minimal core through `static virtual` members; an instance default-interface-method is the rejected form.

[DERIVATION]:
- `POLICY_VALUES` — configuration enters as one domain value that carries its own behavior — a smart-enum row with constructor delegates, a union case, or a frozen policy table — never as flag sets whose combinations the implementation must re-derive. Behavior rows live with the vocabulary that selects them.
- `DERIVED_LOGIC` — when cases share generative structure, the logic is derived — state-threaded `Switch`, a `Fold` algebra, or a table — never enumerated arms. One primary correspondence is declared and every secondary map derives from it; a derived form is replaced only where a structurally cheaper primitive exists, and the replacement preserves the law the derivation encodes — the derivation is the executable specification.
- `DERIVED_TYPES` — types are computed where the language allows so one declaration yields the family: generic math constraints, type parameters with semantic payload, `K<F,A>` carrier-polymorphic arrows, and source-generated owners replace rank-specific or per-carrier copies.
- `SYMBOLIC_REFERENCE` — names, paths, discriminants, and correspondences travel as symbols and derived values — `nameof` including unbound generics, smart-enum keys, vocabulary tables — never as string literals that restate something the program already knows.
- `SEMANTIC_NAMING` — every file, namespace, type, method, local function, parameter, field, property, case, test, artifact, and region name uses the bounded context's canonical term, grammatical role, and tense. One semantic word is the default; two words are allowed when owner plus action, result, axis, or boundary is load-bearing; three words are the ceiling unless a generated contract, external API, or ambiguity proof requires more. Operations use action verbs, values and receipts use result nouns, policies and vocabularies use stable noun or adjective rows, and boundary adapters preserve foreign names only at the seam. Renaming for variety, tense drift, abbreviations, prefix/suffix families, and parallel file/member/type labels for one concept are rejected.

[MATERIAL]:
- `LIBRARY_DEPTH` — admitted packages are the standard library: LanguageExt owns rails, effects, schedules, and immutable collections; Thinktecture owns generated domain shape; MathNet and CSparse own numeric algorithms; quality packages own their rails. Use the deepest operator, combinator, or generated surface the package itself reaches for; wrappers, rename adapters, and BCL-first reflexes are rejected. BCL primitives remain owners only when they carry the invariant directly.
- `DEFINITION_TIME_ASPECTS` — cross-cutting capability — admission, identity, dispatch, serialization, grammar, logging — attaches at definition time through attribute-directed source generation, and generated partial hooks are the advice points on construction. Composition-time policy — retry, recovery, resource lifetime — attaches as effect transformers: `Schedule`-driven retry, named catch combinators, and bracket. Aspects materialize policy and never hide control flow. The two weaves meet at exactly one seam — the admission boundary where generated outcomes lift into rails; policy pushed across that seam in either direction stops being recoverable from its declaration.

[INTEGRATION]:
- `ROOT_REBUILD` — new capability is woven into the owning shape as if it had always existed; reshape the owner rather than appending beside it. No shims, compat aliases, `[Obsolete]` layers, or migration surfaces — break the API when the collapse improves the system.
- `ONE_HOP_RESOLUTION` — a name resolves to its semantics in one hop: no alias-to-constant-to-enum-to-class chains, no forwarding helpers, no helper or util shells, no convenience wrappers. A value that takes two jumps to trace marks a layer to delete.
- `COMPOSED_IMPLEMENTATION` — a feature of any complexity is implemented by composing the page owners — admitted shapes, typed rails, dispatch surfaces, boundary projections, numeric routes — before any new scaffold is named. The pages are one body, and the same concern resolves identically wherever it appears. A need with no composed spelling marks a missing case in an owning page's law: the law extends first, the feature lands second. Cards and snippets show this composition at full operator depth. Flat code — logic below the operator depth the admitted packages reach — is surface sprawl in time: it re-derives, line by line, what a deeper composed form states once.

## [03]-[COLLAPSE_SCAN]

Run this scan on every edit. Any signal triggers the move; three or more instances make it mandatory.

| [INDEX] | [SIGNAL]                                          | [MOVE]                                   |
| :-----: | :------------------------------------------------ | :--------------------------------------- |
|  [01]   | sibling names share a prefix or suffix            | one modality-polymorphic entrypoint      |
|  [02]   | same return rail, signatures differ only by arity | input-shape discrimination               |
|  [03]   | functions differ only by a literal                | parameterize; the literal becomes policy |
|  [04]   | boolean parameter selects between two bodies      | one derived body or one policy value     |
|  [05]   | function calls exactly one other function         | delete the hop                           |
|  [06]   | parallel dispatch arms repeat structure           | table or fold algebra                    |
|  [07]   | several types share fields for one concept        | one closed family                        |
|  [08]   | wrapper renames a package API                     | use the package surface directly         |
|  [09]   | the same 2-4 wrappers recur together              | one parameterized aspect                 |

## [04]-[RULE_ENFORCEMENT]

The repository analyzer (`tools/cs-analyzer`) is the doctrine's compiled form: it turns doctrine violations into build errors. Its loop is one-directional — a doctrine page legislates, the analyzer enforces; a rule never introduces law of its own.

- Promotion law: when an anti-pattern is identified that is doctrine-breaking yet not inherently an error — nothing in the compiler, `.editorconfig`, or shipped analyzers rejects it — its logic is captured as an analyzer rule and promoted to error. Style preferences, one-off review notes, and anything an existing mechanical gate already rejects are not rules.
- Shape law: a rule describes the semantic shape of the anti-pattern — trigger, predicate, exemption routes — never namespaces, paths, or one-off symbols; every rule ships with positive spans that fire and valid compact code that must not.
- Register law: the rule inventory is the code — the catalog, the release ledger, and the `AdditionalFiles` vocabulary data. No prose catalog of rules exists anywhere; arguing a rule's gate or semantics happens at its row and tests.
- Finding law: a true positive is architecture pressure — fix the shape in the product; a false positive, or a fix that adds ceremony without improving the system, is rule pressure — refine the rule. Suppression is neither.

## [05]-[PAGE_CRAFT]

How pages in this folder are authored. The corpus is one body; these laws keep it coherent.

- Atlas law: this README owns doctrine and routing; each concept page owns one disjoint layer; a sibling concern is neither re-shown nor pointed to — cohesion comes from shared law, not linkage. The README is the only file that links.
- Zero meta: concept pages carry no provenance, source trace, release narration, process state, project, tool, or skill context.
- Page grammar: narrow index table, then family cards, then the snippet beside the rule it proves; the page ends at its last card section. Structure is identical across stack folders; content never is.
- Card fields are earned: `Use / Accept / Reject / Law / Boundary` lines appear on a card only where each one decides something; a field line that decides nothing is deleted, not filled.
- Snippet law: every snippet compiles under the active surface; identifiers are legal neutral names; placeholder strings such as `"<value-a>"` appear only inside literals; no project, host, or domain concept anchors a snippet.
- Snippet coverage: each snippet is doctrine-exemplary at full operator depth, roughly 3-4x denser than ordinary code, and exercises a surface region no other snippet in the corpus shows — variety within the doctrine, zero duplicated demonstrations. The region is the snippet's spotlight demonstration; finalized surfaces composed as supporting material occupy no region and duplicate nothing.
- Scale fidelity: a snippet shows the form at the shape it takes in a large system — admission, dispatch, rail, and policy composed in one fence with the growth axis visible — never an isolated minimum; a statement-bearing snippet sits beside the Exemption line naming its platform-forced seam.
- Code names before prose: every member a card or snippet names — attribute, knob, operator, generated surface — is verified against the installed package implementation before it is written; an unconfirmable claim is not authored, and a nameable surface spelled as prose is a defect — the code span is the instruction.
- Card economy: cards are few, deep, and evidence-dense; near-peer cards merge until each retained card owns a decision cluster, and a card line carries exactly one decision. A thin card deciding one concept is a sibling line, not an owner.
- Snippet adherence: snippets obey the card they prove, compose finalized laws as supporting material, and reduce lines and surface through parameterization, algorithmic structure, and package depth, never by deleting capability.
- Altitude routing: when two pages touch one fact, the ledger records the split — mechanics at the owning page, consequence at the consumer; prose re-teaching an owned mechanic is repaired by routing to the owner, while composing owned surfaces inside a snippet is supporting material and owns nothing.
- Reject columns are load-bearing: every `Use` names the spelling, wrapper, or local pattern it deletes.
- Tables enumerate, cards legislate: rows stay atomic and narrow — no prose cramming, no links inside cells; nuance moves to a card.
- Route scope is README-local: lookup rows and conflict rules live in README files; concept pages carry only the law they own.
- Manifest truth: package versions, references, injected globals, tools, and graph admission live in `Directory.Packages.props` and `Directory.Build.props`; no package-named pages; a package is named only where it changes the implementation choice.

## [06]-[CORPUS_LAW]

How the corpus accretes. The folder is one cohesive body, not isolated pages; atlas order is implementation order. The atlas `[STATE]` column is the law registry: a `finalized` page is binding law for every page authored after it; a `partial` page carries no authority and awaits rebuild; a `target` page exists only as roadmap scope. Finalization is a one-way gate — a context-free cold grade of the full page and every snippet, converging to a zero-edit pass, flips the state; the producer's grade admits, the cold grade decides.

- Three-layer inheritance: every page is authored under the doctrine, under every finalized page — adhered to, never restated, never referenced, never contradicted — and from its own source reservoir.
- Prose consumes earlier layers as given: vocabulary, owners, rails, and policy values arrive settled, never re-taught, and the page spends its lines only on its own layer.
- Reservoir residue: a page's source workspace deliberately holds more than the page prints, and it outlives the page — later enrichment and snippet work mine it without source-footnoting it; depth beyond one page's budget is corpus capital, never waste.
- Snippet stacking: code fully captures the card it proves, then composes on earlier layers' law at full doctrine depth — the new surface in the spotlight, established surfaces as supporting material, every touched concern built at the standard its owning finalized page legislates.
- Region ledger: the workspace root keeps one ledger of owned regions — page concerns at card altitude, snippet demonstrations at fence altitude. Snippet rows are written before code exists, page rows at finalization, and a duplicated region is repaired by routing to its owner, never by re-teaching — the ledger is what makes ownership checkable without re-reading the corpus.
- Purpose: the corpus is loaded as the operative standard in place of weaker context; zero-meta, zero-anchor, and stated-as-fact are absolute because any provenance, hedge, or stale claim poisons every downstream generation that loads the page.
