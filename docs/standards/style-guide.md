# [STYLE_GUIDE]

This standard carries craft: the words inside a durable artifact, sentence mechanics, terminology, punctuation, links, and code-safe Markdown. It makes documentation direct, agent-facing, portable, and free of report framing.

## [01]-[USE_WHEN]

Apply this standard when writing or reviewing:
- prose, headings, captions, notes, warnings, and examples
- commands, paths, symbols, placeholders, and technical notation
- terminology, acronyms, UI labels, product names, and package names
- accessibility-sensitive wording and text equivalents.

Container form belongs to `information-structure.md`; marker shape belongs to `formatting.md`; claim confidence belongs to `proof.md`.

## [02]-[WORDING_PRECEDENCE]

Use the first owner that decides a naming or wording question:
1. Current repository material, manifests, generated contracts, API fields, and actual product or package names.
2. The active document-type standard for the document being written.
3. Maintained product names, UI labels, APIs, commands, and support status.
4. This guide for local prose and notation rules.
5. Established editorial style for unresolved general mechanics.

When owners conflict, choose the repo-local term only when a current route or contract proves it. Never alternate terms to avoid the conflict.

## [03]-[AGENT_PROSE]

Durable docs, prompts, standards, skills, examples, and templates are agent-facing law. State the rule, contract, route, or gap directly. Do not describe the artifact, the session, the source-mining process, or the reader's mental model.

[PROSE_LAW]:
- Treat agent-facing posture as implicit. Do not announce audience, authoring purpose, source provenance, process, or why the artifact exists.
- Lead with the controlling rule, constraint, or outcome.
- Keep one controlling idea per paragraph.
- Keep exceptions next to the rule they modify.
- Use active voice unless the result matters more than the actor.
- Use present tense for durable standards.
- Use target-sequence language for intended work, not schedule or deferral vocabulary.
- Use past tense only for a document whose purpose is historical record.
- State rules, contracts, routes, gaps, and required actions instead of explanatory narration.
- Name exact code symbols, functions, fields, commands, flags, package IDs, operators, and generated surfaces in backticks instead of paraphrasing behavior.

[NOISE_REMOVAL]:
- Remove leads that describe the artifact instead of stating the rule.
- Remove source-footnote blocks, outside-source blocks, provenance, source-mining history, freshness disclaimers, source-history commentary, and checklist-tail sections from ordinary docs.
- Remove hedges that carry no scope: `may`, `might`, `probably`, `generally`, `where possible`, and `if needed`.
- Preserve scope qualifiers that are part of the contract: `optional`, `if present`, `where supported`, and `when configured`.
- Replace negative wording with the direct action when meaning is unchanged.
- Prefer concrete routes, contracts, fields, commands, public symbols, failure modes, and artifacts over broad value claims.

[SELF_REFERENCE]:
- Do not write ordinary handoff boilerplate in ordinary docs.
- Do not mention loaded instructions, standards, skills, local prompts, prior passes, review labels, or agent workflow unless the artifact is an instruction route that owns that relationship.
- Use links only when they change the reader’s action.
- Route maps, relation records, README indexes, generated/reference handoff surfaces, and instruction files may name owner relationships because routing is their job.

## [04]-[SENTENCES]

Use a front-and-close paragraph shape. The first sentence states the rule, claim, scope, outcome, or transition. The final sentence closes on the consequence, boundary, confirmation, or route the reader should retain.

[KEEP_OR_CONVERT]:
- Keep a standalone sentence when it leads, transitions, captions, closes, states a consequence, names a route boundary, or marks a gap.
- Convert a sentence to `Label: value` only when the value is scanned, quoted, or updated independently.
- Convert local detail to a note, alert, or row-owned record only when its scope is local to one row, claim, risk, or artifact.
- Delete or fold a sentence that only repeats emphasis.

[MECHANICS]:
- Coordinating conjunctions join equal-rank ideas: `for`, `and`, `nor`, `but`, `or`, `yet`, and `so`.
- Use a comma before a coordinating conjunction joining two independent clauses.
- Omit the comma for imperative clauses sharing an implied subject unless contrast, length, or ambiguity requires it.
- Omit the comma before a coordinating conjunction that joins only a compound predicate.
- Use a semicolon before and a comma after a conjunctive adverb joining two independent clauses: `however`, `therefore`, `otherwise`.
- Do not join independent clauses with a comma alone.
- Use a semicolon only for closely related independent clauses or complex inline lists with internal commas.
- Use `that` for restrictive clauses and `which` for nonrestrictive clauses.
- Use sentence-initial conjunctions, split infinitives, and terminal prepositions when they produce the clearest technical sentence.
- Coordinate only equal ideas and subordinate unequal ones.
- Construct both arms of a correlative pair in parallel: `both ... and`, `either ... or`, `not only ... but also`.
- State conditions before the actions they control.
- Keep modifiers next to the terms they govern.
- Keep parallel items parallel in grammar and scope.

## [05]-[TERMINOLOGY]

Use one term for one concept inside a bounded context. Names are load-bearing: product names, package names, API members, commands, file paths, UI labels, and config keys must match the actual surface.

[TERM_LAW]:
- Preserve verified product, package, API, command, file, and UI names exactly.
- Define a domain term before relying on it unless the target reader already owns that domain.
- Introduce an acronym once per document unless the acronym is more recognizable than its expansion.
- Use singular `they` when gender is unknown, irrelevant, or intentionally unspecified.
- Do not invent reader-facing names for internal concepts.
- Do not name stale commands, removed tools, transient task labels, or removed skills.

## [06]-[PUNCTUATION]

[LOCAL_MECHANICS]:
- Use U.S. English spelling unless a product or proper name differs.
- Form singular possessives with `'s`.
- Use the serial comma.
- Use one space after terminal punctuation.
- Use ASCII hyphen-minus in commands, flags, paths, slugs, identifiers, code, config, tracker literals, and copyable text.

[COLONS_DASHES]:
- Use a colon after a complete sentence that introduces a list, table, example, consequence, or explanation.
- Capitalize the first word after a colon only when the following material is a complete sentence.
- Use parentheses for nonessential clarification; promote required conditions into the main sentence.
- If a parenthetical is a full sentence, put the period inside the closing parenthesis. If it is part of the enclosing sentence, put the period outside.
- Use spaced em dashes only for prose interruptions.
- Use en dashes for inclusive ranges and name-based compounds when the text is not copyable code or config.
- Hyphenate compound modifiers before nouns when needed for clarity.
- Omit needless hyphens after `-ly` adverbs, and use a suspended hyphen for shared compounds such as `short- and long-term`.
- Prefer sentence splits or vertical lists over semicolon-ended bullets.

[QUOTES_NUMBERS]:
- Use numerals for versions, measurements, commands, flags, identifiers, dates, editions, counts, thresholds, and compared values.
- Spell out isolated nontechnical counts from zero through nine only when the value is not a comparison, threshold, field value, or literal.
- Use backticks for UI labels, commands, code, exact strings, and copied literals.
- Place commas and periods inside closing quotation marks in ordinary prose quotations; preserve literal punctuation for UI labels, commands, code, exact strings, and copied text.
- Use straight quotes and ASCII-safe punctuation in copyable Markdown.

## [07]-[CODE_SAFE_MARKDOWN]

- Wrap commands, flags, paths, environment variables, package IDs, symbols, literal values, and placeholders in backticks.
- Name placeholders by route, such as `<scenario-glob>` or `<package-name>`.
- Use language-valid neutral identifiers in reusable code examples.
- Prefer `Shape`, `RefinedShape`, `Variant`, `PRIMARY`, `Field`, `KEY`, `Row`, `ROW_A`, `TABLE`, `SELECTED`, `"<value-a>"`, and `"<result-a>"`.
- Do not use repository, host, customer, pricing, deployment, or product nouns in reusable examples unless the documented concept is that domain.
- Omit shell prompts from copyable commands.
- Put sentence punctuation outside a code span unless it is part of the literal.
- When inline code contains a backtick, use a longer matching backtick delimiter rather than a backslash escape.

[PLACEHOLDER_LAW]:
- Structural examples use structural names.
- Literal placeholder values stay valid for the language.
- A reusable example must not introduce a business domain that the rule does not require.

[PLACEHOLDER_EXAMPLES]:
- Accepted: `Shape`, `RefinedShape`, and `OtherShape`. Near miss: `Customer`, `PremiumCustomer`, and `WebhookPayload`. Reason: the accepted names show type structure without importing a business domain.
- Accepted: `Variant`, `PRIMARY`, `SECONDARY`, `"<variant-a>"`, and `"<variant-b>"`. Near miss: `Mode`, `PROD`, `STAGING`, `"basic"`, and `"premium"`. Reason: the accepted names teach enum shape and placeholder data without deployment or pricing semantics.
- Accepted: `Field`, `KEY`, `VALUE`, `Row`, `ROW_A`, and `TABLE`. Near miss: `Header`, `Route`, `UserRow`, and `OrderMap`. Reason: the accepted names keep mapping examples structural unless the documented concept is headers, routes, users, or orders.
- Accepted: `SELECTED`, `SELECTED_RESULT`, `"<value-a>"`, and `"<result-a>"`. Near miss: `active_customer`, `invoice_total`, `"alice"`, and `"acme"`. Reason: the accepted names mark selection and data position without anchoring the sample to an identity or product.

## [08]-[LINKS]

Use link text that describes the destination. Avoid bare URLs unless the URL is the example value. Prefer stable local routes and generated contracts over deep external links when the local route carries the same action.

[LINK_LAW]:
- Ordinary docs link only where the link changes reader action.
- Reusable standards, skills, prompts, examples, and templates avoid outside-source references in produced content.
- README indexes and route maps may link because navigation is their job.
- Do not put links inside table cells unless the table is a routing table or the link is the cell value.

## [09]-[EXAMPLES]

Examples prove shape or prevent misuse. Place them beside the rule they clarify.

[EXAMPLE_LAW]:
- Use one positive example and one near miss only when the distinction is likely to be copied incorrectly.
- Keep example wording aligned with the terminology it teaches.
- Mark copyable, generated, conceptual, output-only, or rejected blocks with the correct fence intent.
- Use a ContrastRecord for short accepted/rejected prose or values.

[UNIT_ATTACHMENT]:
- Accepted: Attach the unit to its value.
- Rejected: It is probably best to try to avoid not stating the unit when you can.
- Reason: The accepted sentence names the action directly; the rejected sentence hedges, negates, and hides the unit rule.

## [10]-[ACCESSIBILITY]

- Carry meaning through text, not through color, position, shape, pointer movement, screenshots, or sound alone.
- Provide text equivalents for visual, audio, or screenshot-only information.
- Write text equivalents for diagrams, alerts, glyph-heavy graphics, progress bars, and monospace structures when the meaning is not already recoverable from adjacent fields.
- State the relation, state, or claim-confidence signal a visual encodes, not its appearance.
- Use input-neutral UI verbs when keyboard, pointer, touch, voice, or automation can perform the action.
- Preserve exact UI labels when the label is the action target.
- Prefer conventional grammar and punctuation for machine translation.

## [11]-[FINAL_PASS]

Review craft in 4 passes before publication:
1. Composition: scope, controlling idea, paragraph order, and section endings.
2. Mechanics: grammar, punctuation, capitalization, numbers, parallelism, code-safe Markdown, semicolon-ended bullets, prose slashes, ranges, and colon/list adjacency.
3. Terminology: names, commands, paths, links, and examples use exact surface wording.
4. Accessibility: sensory cues, UI labels, and text equivalents are direct and input-neutral.

## [12]-[BOUNDARIES]

- `information-structure.md` carries container form, example placement, and code-block intent labels.
- `proof.md` carries claim confidence and gap fields.
- `formatting.md` carries status and invocation markers, table styling, whitespace, and heading notation.
- `README.md` carries document-type routing and cross-standard links.
