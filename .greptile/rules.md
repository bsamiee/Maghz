# Review context — Maghz

VPS second-brain repo: Python admin tooling, container topology, database schema, and workflow automation for the durable Hostinger VPS. Machine-level shell/PATH/tooling concerns belong to Parametric_Forge, never here.

## [01]-[DESIGN_PARADIGMS]

- Python rides the local docs/stacks/python law: typed rails, expression-shaped logic, dispatch surfaces over helper spam, uv-only custody. Version movement is forward-only; a downgrade or stale pin without a recorded reason is a defect.
- Infrastructure state is declarative: the Pulumi stack in admin/infra.py is the sole VPS topology owner — the image build and the db/ollama/n8n service rows behind StackOp. Imperative one-off scripts that mutate the VPS outside these owners are defects. Numbered migrations and up/down pairs are defects; canonical schema files replay to no-op.
- Ops rails per docs/standards/ops-doctrine.md: thin CLI lowerers, one settings owner, typed operation receipts, one scoped SSH rail for remote work.
- Doppler owns secrets end to end; the repo carries references, never values.
- Formatters and gates own mechanics (ruff, ty, sqlfluff, hadolint, shellcheck) — never restate their law as findings; flag suppressions and bypasses. A `noqa`, `type: ignore`, or shellcheck directive in a diff demands the ownership justification; suppression-as-fix is the defect.
- Fix-to-root completeness: a change that patches a symptom while its root cause stands, leaves a known defect unfixed because it sits outside the diff's scope, or defers a residual for a later pass is a defect — the root fix belongs in the same change, and a genuinely blocked item is an explicit unreachable naming its owner, never a silent residual.

## [02]-[UNIVERSAL_BAR]

Anticipate 10x functionality growth: surfaces absorb new modalities as rows, cases, or dispatch arms — never as new files, flags, or knobs. Defects: knob/param/flag spam, hardcoded values, fragile string plumbing, naive happy-path logic, hand-rolled reimplementations of capability already shipped by the ecosystem. External packages are first-class implementation material at full power, newest stable versions. Everything ships agent-first: composable, receipt-bearing, self-describing. Collapse spam relentlessly.

## [03]-[REVIEW_PRIORITIES]

1. Secret leakage and custody violations outrank everything.
2. Doctrine regressions (rails, receipts, dispatch, uv custody, declarative SQL) outrank style.
3. Cross-repo boundary breaches (machine config creeping in from Forge territory) are defects.

## [04]-[LOAD_BEARING_EXCEPTIONS]

Code that violates generic best practice on purpose — do not flag:

- Aggressive API breaks with every call site updated in the same change are the sanctioned rename path, not regressions.
- Dense single-expression bodies and heavy polymorphic dispatch are the bar, not obfuscation.
- Absent defensive guards inside domain logic reflect admission-once boundaries, not missing error handling.
- Sparse 1-2 line agent-facing comments are compliance with comment law, not missing documentation.
- Declarative schema files that drop and recreate objects on replay are the migration-free idiom, not destructive operations.
- A large file that owns one full concern is sanctioned; never recommend splitting by size.

## [05]-[DURABLE_PROSE_AND_SKILL_DETECTION]

Durable markdown — docs, standards, skills, prompts — is agent-facing law. Flag:

- No-op intensifiers: quality adjectives (careful, high-quality, robust, thorough) in a sentence with no owner, action, trigger, or gate.
- Filler lead-ins: "it is important to note", "note that", "make sure to", "be sure to", "remember to", "keep in mind".
- Restated harness obligations: telling an agent to follow CLAUDE.md/AGENTS.md, use available tools, or obey system instructions.
- Quality ladders (good/better/best, minimum/ideal) where a contract gate belongs.
- Command catalogs with no task trigger or acceptance signal per row.
- Generic lifecycle sequences (think, plan, implement, validate, summarize) and mandated reasoning shapes.
- Closing checklists with no machine-checkable gate.
- Process ledgers: ship-status markers, decision tags, freshness stamps, session narration in durable prose.
- Meta-commentary: sentences whose subject is the document itself (this skill, this file, this section) outside routing rows.
- Defensive caveats: hedging auxiliaries and frequency qualifiers softening settled rules; contract qualifiers (`optional`, `if present`, `where supported`, `unless`) survive.
- Bare abstractions: three or more abstract guidance bullets with no paired rejected/accepted example, template, or gate.
- Fixed output skeletons: one mandated report shape (summary, findings, recommendations, next steps) regardless of consumer.
- Skill bundles (`.claude/skills/**`): first/second-person frontmatter descriptions, over-broad trigger catalogs, `SKILL.md` over 500 lines, inline reference banks, references that only route onward, or scripted procedures narrated in prose.
- Skill execution: instructed network fetches or global installs inside skill bodies, except an owned install surface naming exact source, scope, and verification.
- Mirror sentences: prose a fresh agent regenerates from disk plus the document's stated invariants — restated topology, member rosters, tool inventories — is a stale copy, deleted or demoted to a regenerable fence.
- Table teardowns: a table converted to cards, lists, or prose when in-place relief (header hoists, lead-sentence relief, row splits) was available; conversion is earned only by rows sharing no comparison question or a type-standard-owned shape.
- File-kind drift: sibling files of one kind (a bundle's references, templates, doc pages) diverging in section vocabulary, card field sets, or marker tokens — consistency across the kind outranks local optimization.

## [06]-[COMMENT_DISCIPLINE]

A comment exists only for the in-situ constraint the code cannot show — the why, the invariant, the trap. One line is the target; a short comment inlines onto its statement; two lines is the usual ceiling, and three-plus survives only when truly irreplaceable. Flag: what-comments restating the adjacent code, narration and process residue, comments coupling to paths, sessions, or sibling docs, and multi-line blocks whose payload compresses to one line. Every pass that touches a file prunes its stale or drifted comments in the same pass — comment hygiene is a standing obligation, not a separate cleanup.
