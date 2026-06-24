# [FORMATTING]

This standard carries the presentation layer: markers, alignment, whitespace, and the heading idiom that render a chosen container. It does not choose containers, decompose tables, write prose, or judge claim confidence. Keep this layer minimal: markers and styling earn their place by aiding an agent or reader, never by decorating the page.

## [01]-[USE_WHEN]

Apply this standard when rendering a container that [information-structure.md](information-structure.md) has already chosen:
- status, result, and change markers in records, checklists, tables, and reports
- progress bars and other compact visual markers whose calculation or container has already been justified
- invocation markers (`IMPORTANT`, `CRITICAL`, `ALWAYS`, `NEVER`) in instruction files
- table column alignment, header case, empty-cell notation, escaping, and the stub column
- list marker characters, continuation indentation, and whitespace between structural elements
- the heading-label idiom, anchor stability, and hidden source-comment notation by document kind.

Container selection, table construction, and structured-record fields belong to the form standard; sentence mechanics, terminology, and `must`/`should`/`may` belong to the craft standard. Formatting renders lifecycle and status semantics after another standard defines them; it does not create new lifecycle meaning.

## [02]-[STATUS_RESULT_MARKERS]

Render an inline status, result, change, or compact state as a bracketed token so an agent can filter on an exact string. Use a closed set; do not invent tokens, emojis, checkmarks, crossmarks, or decorative alternates. By default, a record's `Status:` field carries the plain lifecycle value the form standard defines (`COMPLETE`, `BLOCKED`); a type standard may require the bracketed lifecycle marker in `Status:` when exact rendered filtering is part of that produced record's contract.

[TOKEN_FAMILIES]:

| [INDEX] | [FAMILY]         | [TOKENS]                                                                    |
| :-----: | :--------------- | :-------------------------------------------------------------------------- |
|  [01]   | Result           | `[PASS]`, `[FAIL]`, `[SKIP]`, `[PARTIAL]`, `[N/A]`                          |
|  [02]   | Change           | `[ADDED]`, `[REMOVED]`, `[CHANGED]`, `[UNCHANGED]`                          |
|  [03]   | Lifecycle marker | `[QUEUED]`, `[ACTIVE]`, `[BLOCKED]`, `[COMPLETE]`, `[DROPPED]`              |
|  [04]   | Compact glyph    | `[O]`, `[X]`, `[!]`, `[?]`, `[+]`, `[-]`, `[=]`, `[/]`, `[~]`, `[$]`        |
|  [05]   | Explicit state   | `[OK]`, `[ERROR]`, `[WARNING]`, `[CAUTION]`, `[PENDING]`, `[UNKNOWN]`       |
|  [06]   | Explicit state   | `[NEW]`, `[DELETED]`, `[SAME]`, `[NULL]`, `[APPROX]`, `[CACHED]`, `[SAVED]` |

Token use is separate from the closed set so the table remains scannable:

| [INDEX] | [FAMILY]         | [USE]                      | [REJECT]                             |
| :-----: | :--------------- | :------------------------- | :----------------------------------- |
|  [01]   | Result           | gate or check outcome      | lifecycle, boolean, or runtime state |
|  [02]   | Change           | delta reporting            | status or claim-confidence state     |
|  [03]   | Lifecycle marker | inline `Status` mirror     | result, check, or domain status      |
|  [04]   | Compact glyph    | dense cell marker          | boolean, lifecycle, or prose status  |
|  [05]   | Explicit state   | runtime or operation state | lifecycle unless locally declared    |

[COMPACT_GLYPH_MAP]:

| [INDEX] | [GLYPH] | [MEANING]                                        | [TEXT_EQUIVALENT]          | [REJECT]                     |
| :-----: | :------ | :----------------------------------------------- | :------------------------- | :--------------------------- |
|  [01]   | `[O]`   | passed, available, or affirmative compact result | `pass` or `available`      | lifecycle `COMPLETE`         |
|  [02]   | `[X]`   | failed, unavailable, or negative compact result  | `fail` or `unavailable`    | checkbox completion          |
|  [03]   | `[!]`   | attention, warning, or risk marker               | `attention`                | claim-confidence gap         |
|  [04]   | `[?]`   | input value unknown                              | `unknown`                  | missing claim detail         |
|  [05]   | `[+]`   | added, new, enabled, or increased                | `added`                    | positive sentiment           |
|  [06]   | `[-]`   | removed, deleted, disabled, or decreased         | `removed`                  | subtraction expression       |
|  [07]   | `[=]`   | unchanged, same, or matched                      | `unchanged`                | equality claim without basis |
|  [08]   | `[/]`   | skipped, bypassed, or intentionally not run      | `skipped`                  | partial completion           |
|  [09]   | `[~]`   | partial, approximate, or changed-in-progress     | `partial` or `approximate` | unsupported uncertainty      |
|  [10]   | `[$]`   | cached, saved, materialized, or stored result    | `cached` or `stored`       | cost or price                |

[ABSENCE_VALUES]:

| [INDEX] | [VALUE]     | [USE]                                            | [REJECT]                              |
| :-----: | :---------- | :----------------------------------------------- | :------------------------------------ |
|  [01]   | `—`         | empty or absent table value                      | not-applicable result or skipped gate |
|  [02]   | `n/a`       | domain vocabulary requires a not-applicable term | generic missing data                  |
|  [03]   | `[N/A]`     | result itself is not applicable                  | missing source value                  |
|  [04]   | `[SKIP]`    | gate intentionally did not run                   | unknown gate result                   |
|  [05]   | `[UNKNOWN]` | value should exist but is not known              | literal null                          |
|  [06]   | `[NULL]`    | literal null value is the fact                   | absent value                          |

[USE_RULES]:
- Prefer the most specific family. Do not use two tokens that mean the same thing in one column.
- Keep domain status vocabularies in their declared casing as field values; bracketed inline lifecycle markers uppercase the canonical token and replace spaces with hyphens. A type-local marker such as `[PROVISIONAL]` or `[DEPRECATED]` is valid only when the type standard declares that marker's closed vocabulary, meaning, and removal behavior before the first rendered example or production use.
- Suffix forms such as `[ACTIVE <ID>]` are allowed only as codemap or source-key projections where the suffix identifies a source route, milestone, task, path, or row key. The base token must still come from a declared vocabulary, and the suffix must not create lifecycle meaning.
- Use compact glyphs only where density matters, such as checked lists, delta summaries, or table cells, and only with the global meanings above.
- Use explicit states when clarity matters more than width.
- Reserve these tokens for status, result, change, and state reporting; do not scatter bracketed tokens through ordinary prose or duplicate a definition-block field or checkbox state.
- Use a checkbox when completion is asserted; use `[X]` only as a compact fail marker, never as a replacement for `- [X]`.

Bracketed tokens have distinct jobs. Invocation markers (`[IMPORTANT]`, `[CRITICAL]`, `[ALWAYS]`, `[NEVER]`) belong only to instruction surfaces. Group labels (`[FACTS]:`) introduce a list or table. GitHub alerts (`> [!WARNING]`) interrupt the rendered reading path. Compact glyphs (`[O]`, `[X]`) are dense table or list cells. Lifecycle tokens (`[ACTIVE]`) mirror the default record `Status` vocabulary inline. Do not use one family as a substitute for another.

Render progress as a bar only after [information-structure.md](information-structure.md) defines the maintained actor, numerator, denominator, closure rule, and basis surface. The rendered line is only the label, bracketed bar, and percentage.

[PROGRESS_BASIS]:
- Cells: exactly 20 cells inside `[...]`.
- Unicode alphabet: `█` marks completed cells; `░` marks remaining cells.
- ASCII fallback alphabet: `#` marks completed cells; `-` marks remaining cells.
- Percentage: integer plus `%`, immediately to the right of the bar.
- Percentage calculation: `floor(100 * numerator / denominator)`.
- Fill calculation: `floor(20 * numerator / denominator)`.
- Closure: show `100%` and fill all 20 cells only when numerator equals denominator.
- Roadmap records use the same 20-cell rule when they render progress; task and milestone completion basis stay in roadmap fields, not appended to the progress line.
- Roadmap milestone and phase progress use the same bar; milestone and phase status fields are rejected because progress derives from child task completion.

[PROGRESS_EDGE_CASES]:

| [INDEX] | [CASE]                                 | [PERCENT]       | [FILLED_CELLS]     |
| :-----: | :------------------------------------- | :-------------- | :----------------- |
|  [01]   | numerator is `0`                       | `0%`            | `0`                |
|  [02]   | nonzero incomplete value floors to `0` | `<1%`           | `0`                |
|  [03]   | numerator equals denominator           | `100%`          | `20`               |
|  [04]   | ordinary incomplete value              | floored integer | floored cell count |

Accepted Unicode example:

```text conceptual
Progress: [██████░░░░░░░░░░░░░░] 33%
```

Accepted ASCII fallback example:

```text conceptual
Progress: [############--------] 60%
```

Rejected appended-metadata example:

```text rejected
Progress: [############--------] 60% (12/20 docs, phase 2, ETA Friday)
```

Do not append the count, unit, phase name, date, ETA, or basis text to the progress line. Put those fields in the adjacent record that defines the progress basis.

The marker is not a decoration. Omit it when the document cannot define the numerator, denominator, closure rule, and basis surface, or when a checklist already carries the same completion state.

[GLYPH_RULES]:
- Allowed jobs: state, progress, hierarchy, alignment, or comparison that the surrounding container needs.
- Declaration: define the glyph alphabet before first use unless this section already defines it.
- Closure: keep the alphabet closed for the local surface.
- Accessibility: provide a text equivalent when meaning is not recoverable from adjacent text; provide a basis when the glyph claims a completed state or progress.
- Rejected forms: decorative glyphs, emojis, checkmark or crossmark substitution, FIGlet-style banners, ornamental frames, separator carpets, copied terminal animations, ANSI color output, photo-to-ASCII art, and standalone glyph legends that do not change reader action.

## [03]-[INVOCATION_MARKERS]

Reserve invocation markers for instruction files and prompt files where an agent must weight a constraint above surrounding text. Use them only for invariants that change agent behavior. Prefer `CRITICAL` and `NEVER` for hard boundaries, `IMPORTANT` and `ALWAYS` for load-bearing defaults.

Do not bring invocation markers into the prose standards or ordinary documentation. There, the craft standard's `must`, `should`, and `may` carry requirement strength, and a wall of bracketed directives is the notation spam this corpus rejects. One concept never carries both an invocation marker and a prose modal.

GitHub alerts use this surface grammar in ordinary rendered documentation. [information-structure.md](information-structure.md) owns when an alert is the right container.
- `> [!NOTE]`: neutral contextual note.
- `> [!TIP]`: user-facing efficiency payoff.
- `> [!IMPORTANT]`: load-bearing invariant or required interpretation.
- `> [!WARNING]`: risky condition that can cause incorrect action or failed work.
- `> [!CAUTION]`: safety, loss, destructive, security, or irreversible-risk boundary.

An alert is not an invocation marker. Do not write `[IMPORTANT]:` in ordinary documentation, and do not write `> [!IMPORTANT]` in instruction files when an invocation marker is the intended weighting surface.

## [04]-[TABLE_STYLING]

Once form chooses a table, style it for scanning.

Table styling uses these groups:

[ALIGNMENT]:
- Left-align text, identifiers, paths, commands, code spans, enum words, and prose phrases.
- Right-align numeric, measurement, count, and date columns.
- Center only `[INDEX]`, compact markers, booleans, tri-state values, and glyph-like cells.
- Treat numeric-looking identifiers as text. Left-align ADR numbers, version ranges, issue IDs, package names, endpoint paths, and code spans unless the column represents a quantity or date.
- Align a mixed column by semantic type, not by its shortest cell. If a column mixes compact tokens with longer words, code spans, or phrases, left-align it unless the whole column is numeric or date-like.

[SURFACE]:
- Every table column header is a bracketed uppercase rubric such as `[SOURCE_PATH]`, `[REQUIRED_GATE]`, or `[STATUS]`; compound rubrics use underscores and avoid spaces.
- Every enumerable Markdown table starts with `[INDEX]`, center-aligned, with body rows numbered `[01]` through `[NN]`. Use `[00]` only when the row is a real zero-indexed marker; `[O]` remains the compact affirmative glyph, not a zero marker.
- A non-enumerable matrix may use a short bracketed stub rubric instead only when row order or row identity is not enumerable.
- Align the first column left, or, when it is a pure index, center it; the form standard sets what the stub column may contain.
- A centered non-index cell must be a compact marker or a value whose visible text is three letters or fewer, such as `yes`, `no`, `n/a`, `—`, `[O]`, or `[X]`. Do not center whole words such as `accepted`, `Supported`, `Standard`, `Contract`, or `Required`.

[SAFETY]:

| [INDEX] | [TRIGGER]                   | [RENDER]                       | [REPAIR_CONTAINER]                              |
| :-----: | :-------------------------- | :----------------------------- | :---------------------------------------------- |
|  [01]   | absent value                | `—`                            | table cell                                      |
|  [02]   | not-applicable domain value | `n/a` or declared domain value | table cell                                      |
|  [03]   | literal pipe                | escaped `\|`                   | same cell                                       |
|  [04]   | nested or multiline facts   | short token in cell            | definition block or subsection-per-record block |
|  [05]   | reader-facing qualification | visible note after table       | prose, note block, or row-owned record          |
|  [06]   | source-only author hint     | hidden comment before block    | never table row or cell                         |

The GFM separator row encodes the four alignment classes — left-align with `:---`, right-align with `---:`, center with `:---:`. A template:

```markdown template
| [INDEX] | [ITEM] | [COUNT] | [RESULT] | [CHECK] |
| :-----: | :----- | ------: | :------- | :-----: |
|  [01]   | Mesh   |      42 | [PASS]   |   [O]   |
|  [02]   | Solver |       — | [N/A]    |    —    |
```

The index column is centered, the text column (`[ITEM]`) is left-aligned, the numeric column (`[COUNT]`) is right-aligned, full result tokens in `[RESULT]` are left-aligned, and the compact result/check column is centered. A column containing full lifecycle words, long code spans, or prose-like status text is text and stays left-aligned.

## [05]-[LIST_WHITESPACE_DISCIPLINE]

[LIST_MARKERS]:
- Use `-` for bullets; do not use `*` or `+`.
- Keep no blank line between items of one list; a blank line ends the list.
- Put one blank line after every H1, H2, and H3 heading before the next line, including when the next line is another heading. Put one blank line on each side of a table, fenced block, or diagram; a lead sentence may introduce the structure, but the blank line still separates the prose from the opening fence. Fence contents are example source, not surrounding document lines; the blank-line rule applies outside the opening and closing fences.
- When prose introduces a list, use a complete lead sentence ending in a colon, then start the list on the next line with no blank gap. A section may start directly with a list after the required heading blank line when that list is the section's primary rule set.
- Treat a complete sentence as a lead, never as a label. If the line reads as a sentence, keep it prose and let the following list carry the facts.

[GROUP_LABELS]:
- Use a bracketed set label only when the introducer is a category, set, key, or compact list name. The label format is `[X_Y_Z]:`: uppercase, underscores for compounds, 1–3 semantic words, and no surrounding bold or code span.
- Treat a bracketed set label as its own structural block. Put one blank line before it when prose, a list, a table, another label, or a fenced block introduces it; put the introduced list or table on the next line after the label with no blank gap.
- For a fenced example, use a complete colon lead instead of a bracketed set label, then obey the fence-spacing rule. Do not use a bracketed set label as a heading surrogate, and do not attach it directly to a heading or to an opening or closing fence; those boundaries still keep the structural blank line above.
- Use grouped sibling lists for a short series of lists that share one lead but are not nested under one parent item. Write a complete lead sentence ending in a colon, a blank line, the first bracketed set label, and that label's list on the following line. Keep one blank line between completed peer groups when useful. Promote a GroupedRecord to an AnchoredRecord H3 only when another document links to the record or a stable heading slug is required.
- Do not stack bracketed set labels. If a second label appears before the first label's list or table, remove the outer label or promote the outer category to prose or a heading.
- A bracketed `[RECORD_KEY]:` or `[CONTRAST_KEY]:` label must be followed by a bullet list on the next line; never bare indented `Field: value` lines after the label.
- Use a nested list only when every child item qualifies one parent item. Indent child bullets and ordered-list continuations with four spaces; field content under a group label is always a bullet, not a bare indented line.
- Roadmap active trees are the type-local nesting exception. Render phase rows with `- P-0010: <outcome>`, task rows with `- [ ] T-0010 [QUEUED] <title>` or `- [X] T-0010 [COMPLETE] <title>`, and task fields as nested `- Label: value` rows. Keep four-space indentation for every child level and no blank lines inside one milestone tree.

[FIELD_LINES]:
- Keep short checklist fields inline after an em dash. Promote larger checklist state to the record form defined by `information-structure.md`.
- GroupedRecord and AnchoredRecord fields use `- Field: value` bullets beneath a bracketed `[RECORD_KEY]:` label or H3 heading. Keep field labels in sentence case or verified field casing, followed by one colon and one space inside each bullet.
- A list-valued field uses one parent bullet, then one nested bullet tier beneath it.
- Keep item-scoped field labels raw by default inside bullets, checklist items, and record groups: `Label: value`. Use bracketed set labels only for standalone group labels. Use backticks only for literal fields, symbols, commands, paths, flags, exact tokens, or placeholders. Do not bold the label or the whole line.
- Render ContrastRecord examples as `[CONTRAST_KEY]:` followed by `- Accepted:`, `- Rejected:` or `- Near miss:`, and `- Reason:` bullets rather than adjacent fences or column-0 field lines. Use a table only when the contrast compares three or more attributes across two or more options.
- Let prose soft-wrap; the form standard carries the no-hard-wrap rule, and this whitespace discipline governs only the gaps between structural elements.

A conceptual list example:

```markdown conceptual
Use the container that matches the reader action:
- Prose: one concept, decision, caveat, or transition where a sentence is clearer than a list.
- Bullets: peer facts, requirements, or unordered options.
- Numbered lists: ordered actions, ranked choices, lifecycle steps, or gates.
- Checklists (`- [ ]`): actionable completion, acceptance, readiness, or status items whose completion is asserted and checked.
```

GroupedRecord is the normative field carrier for same-section record clusters. Section cardinality uses this shape:

[REQUIRED_UNIVERSAL]:
- Opening lead: required, single; states the support question, profile, and regime.
- Required sections: `Scope`, `Status vocabulary`, `Matrix`, `Exclusions`, `Boundaries`, and `Result check`.

[CONDITIONAL_PROFILE]:
- `Lifecycle dates`: required for product-lifecycle and deprecation profiles.
- `Reading rule`: required for two-axis, intersection, or derived cells.

```markdown conceptual
Section cardinality uses these groups:

[REQUIRED_UNIVERSAL]:
- Opening lead: required, single; states the support question, profile, and regime.
- Required sections: `Scope`, `Status vocabulary`, `Matrix`, `Exclusions`, `Boundaries`, and `Result check`.

[CONDITIONAL_PROFILE]:
- `Lifecycle dates`: required for product-lifecycle and deprecation profiles.
- `Reading rule`: required for two-axis, intersection, or derived cells.
```

## [06]-[HEADING_IDIOM]

Use one bracketed heading format throughout repo-internal standards-controlled documentation and instruction files. Public or registry README files may use plain reader-facing headings when [reference/readme.md](reference/readme.md) declares that exception:
- H1: `# [DOCUMENT_TITLE]`; the H1 carries only the semantic title label and never a heading-tier prefix.
- H2: `## [NN]-[SECTION_LABEL]`; `NN` is the zero-padded section number in document order, with single-digit sections rendered as `[01]` through `[09]` and the rare zero section rendered as `[00]`.
- H3: `### [NN.M]-[SUBSECTION_LABEL]`; `NN.M` is the zero-padded parent section number plus the subsection number.
- Extra qualifiers on the same line use the same concise bracket discipline: `## [NN]-[PRIMARY]-[EXTRA]`; never trailing prose after the label brackets.

Labels are uppercase, use underscores for compounds, and preferably contain 1 or 2 semantic words. Use at most 3 words for normal headings; go longer only when a verified source name, command family, or document type would lose meaning if shortened. Do not mix bracketed heading labels with sentence-style headings. Examples inside fenced templates use the same bracketed grammar with placeholders only where the author must replace the label.

Reject heading theater such as `# [H1][NAME]`, bracket tokens outside the allowed marker families, and decorative `<br>` spacing used to simulate layout. Allowed marker families are headings, standalone group labels, table rubrics, inline status/result/change/state/lifecycle markers, compact glyphs, invocation markers, and GitHub alert markers.

## [07]-[ANCHORS_COMMENTS]

Treat heading anchors and hidden Markdown comments as source-level notation. Anchor rules below are the local convention for in-repo links; external renderers may apply different duplicate-suffix or punctuation rules.

Use these source-notation rules:
- Anchor stability: a bracketed heading slug is the lowercased heading text with brackets, punctuation, dots, and underscores removed; `## [10]-[FOLDER_LAYOUT]` becomes `#10folderlayout`. When a heading number or label changes, update every in-repo link to that anchor in the same change.
- Duplicate headings: do not create duplicate bracket-heading anchors in one file. Rename the semantic label rather than relying on renderer-specific duplicate suffixes.
- Renumbering: renumber headings only when the document structure changes; cosmetic rewrites preserve existing heading numbers so links stay stable.
- Hidden comments: use HTML comments only for source-view authoring hints, generator hints, or maintenance notes that should not render: `<!-- source-only: <short reason> -->`.
- Comment placement: put a hidden comment immediately before the block it annotates, separated by the same blank-line rules as the surrounding block. Keep comments one line when possible; multi-line comments are allowed only for generated source-view notes that would be noisy when rendered.
- Comment limits: never use a hidden comment as the only carrier of safety, claim confidence, intent, current-data replacement, or required constraints. Do not put comments inside table rows or cells; use visible prose, a table note, or a definition block instead.

## [08]-[BOUNDARIES]

- [information-structure.md](information-structure.md) carries container choice, table construction, code-block intent labels, progress eligibility, and structured-record fields; this standard styles what it builds.
- [style-guide.md](style-guide.md) carries sentence mechanics, terminology, and requirement modals.
- [style-guide.md](style-guide.md) carries salience and where a marked constraint sits in a unit.
- [proof.md](proof.md) carries claim confidence, refresh triggers, and confidence label meanings; this standard renders the result and status markers that present confidence or status.
- [README.md](README.md) carries document-type routing and cross-standard links.
