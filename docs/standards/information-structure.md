# [INFORMATION_STRUCTURE]

Container choice decides how an agent reads, updates, and preserves a document. Pick the carrier from the reader action, then keep the section lean enough that the structure itself guides the next edit.

## [01]-[USE_WHEN]

Apply this standard when shaping:
- prose, bullets, numbered steps, checklists, completion lists, records, tables, matrices, examples, and diagrams
- page anatomy, section boundaries, route records, status records, literal blocks, command/output carriers, and generated artifact records
- Markdown tables, Mermaid, monospace topology, callouts, details blocks, footnotes, and machine-consumed Markdown.

This standard owns form. `style-guide.md` owns wording, `formatting.md` owns visual notation, and `proof.md` owns claim discipline.

## [02]-[CONTAINER_CHOOSER]

Use the smallest carrier that preserves the reader job. A carrier earns its place only when deleting it would remove a decision, lookup path, update route, or machine-readable shape.

| [INDEX] | [SIGNATURE]             | [READER_JOB]         | [CARRIER]                         |
| :-----: | :---------------------- | :------------------- | :-------------------------------- |
|  [01]   | one rule                | understand           | prose paragraph                   |
|  [02]   | peer rules              | scan equivalents     | bullet list                       |
|  [03]   | ordered actions         | execute sequence     | numbered steps or ordered records |
|  [04]   | actionable completion   | assert checked state | checklist                         |
|  [05]   | finite lifecycle        | filter by state      | status record set                 |
|  [06]   | one item, many fields   | scan fields          | definition record                 |
|  [07]   | closed vocabulary       | choose exact value   | vocabulary card                   |
|  [08]   | comparable rows         | compare attributes   | table                             |
|  [09]   | finite conditions       | resolve action       | decision table                    |
|  [10]   | row detail              | update one row       | row-owned record                  |
|  [11]   | command or output       | run or compare       | command/output carrier            |
|  [12]   | parser-owned shape      | preserve grammar     | machine-consumed record           |
|  [13]   | topology or flow        | see relation         | diagram or text topology          |
|  [14]   | interrupting constraint | interrupt            | callout                           |

[CARRIER_LAW]:
- A one-row table is a record.
- A long row is a record.
- A repeated paragraph pattern is a record set.
- A list item with asserted completion is a checkbox.
- A table with no shared comparison question is several records.
- A diagram that repeats a table is deleted.
- A command that has not run is an instruction, not a result.

[PACKET_PROMOTION]:
- Promote to a record, packet, or topology only when repeated decisions, independent field updates, parser consumption, failure reading, omission behavior, or claim confidence exceeds ordinary prose, lists, tables, or definition blocks.
- Collapse a packet to prose or a short field block when fewer than 3 fields are independently scanned, updated, closed, or omitted.
- Omit absent fields. Never fill a packet to satisfy a template.

## [03]-[TABLES]

Use a table only when row-and-column lookup is the reader job. Headers are load-bearing: every cell must make sense in the row/column matrix. Long cells, repeated columns, tautological values, and one-row tables move to prose, cards, or records.

[ELIGIBILITY]:
- Use comparison tables for comparable items across shared attributes.
- Use lookup tables for closed keys mapped to values, owners, or actions.
- Use decision tables for condition combinations mapped to resolved action.
- Use matrices for two meaningful axes.
- Avoid tables for sequences, heterogeneous records, narrative arguments, and field lists.

[FORMS]:

| [INDEX] | [FORM]            | [ROW_AXIS]             | [COLUMN_AXIS]          | [USE]                                           |
| :-----: | :---------------- | :--------------------- | :--------------------- | :---------------------------------------------- |
|  [01]   | Comparison table  | comparable items       | attributes             | compare options, commands, profiles, surfaces   |
|  [02]   | Lookup table      | keys                   | value or behavior      | map tokens, commands, codes, paths, owners      |
|  [03]   | Decision table    | condition combinations | inputs and action      | choose one rule from finite overlapping facts   |
|  [04]   | Matrix            | row category           | column category        | show intersections, support, dependency, access |
|  [05]   | Support matrix    | supported surface      | support fields         | state capability policy                         |
|  [06]   | Dependency matrix | producer or dependent  | consumer or dependency | show allowed, required, forbidden relations     |

[BOUNDS]:
- Keep tables under 15 columns and 20 rows.
- Use one trailing prose column at most.
- Keep each cell atomic: one value, marker, short phrase, inline code span, or permitted link value.
- Keep the stub column short, unique, and scannable: an identifier, command, proper noun, or status token, not a sentence.
- Use row-owned records when any row needs independent status, detail, omission, update, or retention behavior.

[TABLE_PRESSURE]:
- Evaluate each row as one cumulative unit: stub value, column headers, cells, and section-local prose together carry the row meaning.
- Every cell must be load-bearing inside its row. Delete, merge, or promote a cell when it repeats the header, repeats another cell, or adds no row-specific value.
- Use column headers as compression surfaces. Put shared category, condition, unit, or action semantics in the header so cells stay atomic.
- Do not duplicate header meaning into every cell. A column whose cells restate the header, share one invariant value, or differ only by prose padding moves to prose or a GroupedRecord before the table.
- Treat prose before and after a table in the same section as part of the table's information unit. Use that prose for cross-row scope, invariants, reading rules, and shared consequences instead of repeating them in cells.
- When rows widen, rethink row axis, column axis, lead prose, and row-owned records together. Do not extract text only to reduce width; preserve value by moving cross-row meaning to the section lead or adjacent record.
- Do not cram prose, reference links, link clusters, or citation trails into table cells. Use prose, a table note, a routing table, or row-owned records.
- A pre-table GroupedRecord may carry table-level invariants when the record key names the table concept and every field applies across rows.

[DECOMPOSITION]:
- Split wide or tall tables by the dominant axis.
- Pivot small wide tables when columns are really subjects.
- Replace heterogeneous rows with a summary table plus record sections.
- Move repeated cell text into a lead sentence before the table.
- Move row-specific qualifications into row-owned records after the table.

[DECISION_TABLES]:
- Put input conditions on the left and the resolved action on the right.
- Declare the hit policy before the table when rows overlap.
- Use `first match wins` only when row order is semantic.
- Use `most specific wins` only when wildcard count decides.
- Use `all matching actions apply` only when actions compose without conflict.
- Convert the rule to prose plus cases when no deterministic hit policy exists.

GFM tables are flat. They do not carry row spans, column spans, nested lists, multiline cells, or reliable embedded HTML. If a row needs nested facts, use records. Check table integrity before publication: every row has the same cell count after escaped pipes are accounted for, literal pipes inside cells are escaped, and tables over the row or column ceiling decompose by the dominant violation.

## [04]-[RECORDS_LISTS]

Render independently scanned items as records. A record earns fields only when an agent filters, updates, removes, confirms, or routes by that field.

[STATUS_VOCABULARY]:

| [INDEX] | [STATUS]   | [MEANING]                                               |
| :-----: | :--------- | :------------------------------------------------------ |
|  [01]   | `QUEUED`   | accepted for the target sequence                        |
|  [02]   | `ACTIVE`   | executing inside the record scope                       |
|  [03]   | `BLOCKED`  | held by a named dependency, decision, or access problem |
|  [04]   | `COMPLETE` | exit condition is met                                   |
|  [05]   | `DROPPED`  | removed, superseded, or closed without further action   |

Type standards may narrow this vocabulary only when they define exact casing, active states, blocked states, terminal states, and removal behavior before examples.

[RECORD_FIELDS]:
- `ID`: stable reference used by another item, artifact, or generated surface.
- `Status`: current lifecycle value.
- `Changed fact`: current behavior, contract, route, field, status, or public symbol behavior consumed by the record.
- `Consumed by`: section, artifact, or reader action that uses the fact.
- `Use in this document`: how the fact changes action.
- `Exit`: observable condition that closes the item.
- `Depends`: condition or item that must hold first.
- `Update when`: event that requires a change.
- `Close when`: condition that removes the relation.
- `Route-away`: work that remains in another owner.

[FIELD_ORDER]:
- Lifecycle records: `ID`, `Status`, `Changed fact`, `Consumed by`, `Use in this document`, `Exit`, `Depends`, `Update when`, `Close when`, `Route-away`, then domain fields.
- Relation records: `Changed fact`, `Consumed by`, `Use in this document`, `Update when`, `Close when`, `Route-away`.
- Keep shared fields contiguous once any shared field appears.
- Omit absent fields; never publish empty placeholders.

[RECORD_FORMS]:
- `GroupedRecord`: standalone `[RECORD_KEY]:` label followed by `- Field: value` bullets.
- `AnchoredRecord`: H3 record heading when another artifact links to the record.
- `ContrastRecord`: compact accepted/near-miss/reason pair when a common mistake is likely.
- `OrderedStep`: numbered task step with scanned fields.

[CONTRAST_RECORDS]:
- Use only for plausible near misses that protect a rule.
- Use `Accepted:`, `Rejected:` or `Near miss:`, and `Reason:` bullets.
- Do not publish standalone rejection-list sections.
- Prefer a positive rule when the rejected side is not likely.

[CHECKLISTS]:
- Use `- [ ]` and `- [x]` when an item carries an actionable completion, acceptance, readiness, or status assertion.
- Use bullets for unordered peer facts, requirements, options, and inventories whose completion is not asserted.
- Use numbered steps for sequence even when each step later gains a checklist child.
- Acceptance checklists carry an `Exit` condition for each item.
- Status checklists promote to records when any item needs `Status`, `Depends`, `Update when`, `Close when`, or multiline detail.
- Fields trail item text after an em dash and stay compact. Promote the item to a record when it needs more than 3 trailing fields or any field needs its own list.

[LISTS]:
- Bullets carry equivalent items.
- Numbered lists carry true sequence.
- Split lists past 7 items into named sets.
- Keep nesting to 2 levels.
- Do not mix ordered and unordered items in one logical block.
- Promote a step to an OrderedStep when it needs fields such as `Action`, `Command`, `Expected signal`, `Recovery`, or `Result`.

## [05]-[LITERAL_MACHINE_SURFACES]

Use literal and machine-consumed carriers only when exact shape matters.

[FENCE_RULES]:
- Ordinary code fences carry a language tag plus one intent label.
- Renderer-local fences use the exact renderer tag; Mermaid fences are `mermaid`.
- `copy-safe` blocks run or paste as written.
- Templates use neutral placeholders and `template`.
- Conceptual examples use `conceptual`.
- Generated examples use `generated`.
- Test-only examples use `test-only`.
- Output examples use `output-only`.
- Counterexamples use `rejected` only when a compact contrast record cannot carry the distinction.

[COMMAND_OUTPUT]:
- A copy-safe command is an instruction to run.
- An expected signal is the short output or state change to compare.
- Observed output belongs only beside the completed result it confirms.
- A command card carries command, purpose, precondition, effect, output, and refresh trigger only when those fields change the reader action.
- A CLI envelope record carries stdout, stderr, exit status, artifacts, side effects, and failure reading only when failure classification is the point.
- Do not paste terminal transcripts when a short result statement carries the fact.

[MACHINE_RECORD]:
- Consumer: parser, analyzer, generator, release ledger, or other named tool.
- Required shape: headings, fields, row order, or fence grammar consumed.
- Checked fields: fields or rows the local consumer checks.
- Unchecked convention: adjacent shape that remains human convention.
- Owner: manifest, generator, route, contract, or maintained tool.
- Refresh trigger: event that requires regeneration or review.

Machine-consumed Markdown may keep a narrower shape when a parser, generator, or ledger consumes exact headings, fields, rows, or fence grammar. Declare the exception before applying ordinary heading, table, field, or fence normalization.

## [06]-[VISUAL_TOPOLOGY]

Use visual topology only when arrangement, branch shape, relationship, hierarchy, state, progress, dependency, alignment, or comparison is the reader question.

[VISUAL_CARRIERS]:
- Codemap tree: path ownership, package shape, or artifact placement.
- Type-shape block: compact relation between interfaces, records, unions, carriers, or data flow.
- Edge list: directed relation where a full diagram adds no clarity.
- Matrix: capability, support, dependency, access, or gate intersections.
- Gate or risk map: gate, risk, signal, and action.
- Glyph legend: closed local alphabet for compact state, result, change, or risk.
- Progress bar: 20-cell completion marker backed by numerator, denominator, and closure rule.
- Mermaid: flow, state transition, sequence, relation, or topology.
- C4 or topology packet: runtime boundary, container, component, deployment, or resource topology.
- Review-only carriers: DOT-like shorthand, finite-state-machine grammar, sparklines, microplots, heatmaps, mini timelines, swimlane text grammar, and generated visual indexes.

[VISUAL_LAW]:
- One visual answers one reader question.
- A diagram carries topology; a table carries comparable fields.
- Publish both only when each representation changes a distinct reader action.
- Every visual has enough nearby text to be understood when the render is unavailable.
- Delete decorative diagrams, ornamental separators, banners, and repeated table renders.

Use monospace text when raw Markdown inspection matters more than a rendered image: file trees, repository layout, artifact placement, progress summaries, small stacks, tiny matrices, and tiny flows embedded in code comments. Alignment is the meaning; misaligned text topology is worse than prose.

```text conceptual
project/
├── README.md
└── reference/
    └── api.md
```

Define a text-graphic alphabet only when the reader needs it to decode the structure. A glyph legend is valid when it is closed, local, and changes reader action.

Use a tiny matrix only when the crossings matter:

```text conceptual
          state  route  update
Lifecycle yes    yes    yes
Note      no     no     no
```

Use Mermaid when rendering adds branch, state, sequence, dependency, or topology value beyond bullets. Keep diagrams small enough to review in source and use stable semantic node IDs.

[MERMAID_LAW]:
- Use the exact `mermaid` fence. State conceptual, template, generated, or rejected intent in the lead-in sentence.
- Prefer `flowchart` for branching workflow or data movement, `sequenceDiagram` for actor interaction over time, `stateDiagram-v2` for lifecycle transitions, `erDiagram` for entities, and `classDiagram` for type relationships.
- Keep hand-maintained diagrams near 5 to 9 nodes and no more than about 12 meaningful edges.
- Split a diagram when it has more than 2 decision nodes, more than 1 lifecycle, multiple unrelated subgraphs, or labels that repeat table cells.
- Use stable semantic node IDs such as `Request`, `Quota`, or `Recovery`; quote rendered labels that contain punctuation, parentheses, or reserved words.
- Edge labels add a condition, status, or action that is not obvious from the node names.

## [07]-[SECONDARY_CONTAINERS]

Secondary containers change reading path, salience, portability, or economy. They do not hide required constraints.

| [INDEX] | [FORM]   | [USE]                                                  |
| :-----: | :------- | :----------------------------------------------------- |
|  [01]   | Callout  | interrupting note, tip, invariant, warning, or caution |
|  [02]   | Details  | low-salience trace, option dump, or long output        |
|  [03]   | Footnote | short local qualification                              |

[SECONDARY_LAW]:
- Use one callout per concern.
- Do not stack callouts.
- Do not hide first-read constraints, safety notes, required commands, or owner routes in details.
- Use footnotes sparingly and never as the only carrier for a material claim.
- Hidden comments are source-only notation, never reader-facing intent labels.

Do not hard-wrap Markdown prose. Write each paragraph as one logical line and let the renderer soft-wrap. Insert manual line breaks only for structural boundaries: list items, table rows, definition fields, and fences.

## [08]-[PAGE_SHAPE]

A standard file has one H1, a short lead, use triggers, rules, boundaries only where they change ownership, and examples only where misuse is likely. Conditional sections appear only when their condition holds.

```markdown template
# [TITLE]

<Lead: scope and promise in one short paragraph.>

## [1]-[USE_WHEN]

## [2]-[<RULE_OWNER>]

## [3]-[BOUNDARIES]
```

[SECTION_CARDINALITY]:
- `Lead` and `Use when` are required.
- Rule sections are required and named by the concern they own.
- `Boundaries` appears only when an adjacent owner changes action.
- `Examples` appears only where misuse is likely.
- Closing checklist sections are not part of ordinary page shape.

[TYPE_STANDARD_OPENING]:
1. Purpose and boundary in the lead.
2. `Use when`.
3. Route-away rule.
4. Agent use.
5. Required produced-document shape.
6. Section cardinality.
7. Adjacent relation rule.
8. Maintenance triggers.

Headings form standalone retrievable H2 units. Use H3 only to refine one H2 concern. Avoid H4 and deeper unless a generated format requires them. Heading labels are 1 or 2 semantic words by default and 3 when needed.

Examples sit beside the rule they clarify. Use neutral placeholder values in reusable examples and language-valid neutral identifiers in code examples.

## [09]-[BOUNDARIES]

- `style-guide.md` carries prose, tone, hedging, examples, links, and agent-facing language.
- `formatting.md` carries table alignment, status markers, heading notation, whitespace, fences, and visual notation.
- `proof.md` carries claim discipline, artifact confidence, gaps, and preservation.
- `README.md` carries document-type routing and standards-library placement.
