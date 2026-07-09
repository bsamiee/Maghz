# Review context — Maghz

VPS second-brain repo: Python admin tooling, container topology (compose.yaml), database schema, and workflow automation for the durable Hostinger VPS. Machine-level shell/PATH/tooling concerns belong to Parametric_Forge, never here.

## Design paradigms

- Python rides the Rasm doctrine: typed rails, expression-shaped logic, dispatch surfaces over helper spam, uv-only custody.
- Infrastructure state is declarative: compose rows, the declarative schema ledger, and admin verbs — imperative one-off scripts that mutate the VPS outside these owners are defects. Numbered migrations and up/down pairs are defects; canonical schema files replay to no-op.
- Doppler owns secrets end to end; the repo carries references, never values.

## Universal bar

Anticipate 10x functionality growth: surfaces absorb new modalities as rows, cases, or dispatch arms — never as new files, flags, or knobs. Defects: knob/param/flag spam, hardcoded values, fragile string plumbing, naive happy-path logic, hand-rolled reimplementations of capability the ecosystem already provides. External packages are first-class implementation material at full power, newest stable versions. Everything ships agent-first: composable, receipt-bearing, self-describing. Collapse spam relentlessly.

## Review priorities

1. Secret leakage and custody violations outrank everything.
2. Doctrine regressions (rails, dispatch, uv custody) outrank style.
3. Cross-repo boundary breaches (machine config creeping in from Forge territory) are defects.

## Durable prose and skill detection

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
- Defensive caveats: hedges (may, might, generally, usually, when possible) softening settled rules; contract qualifiers (optional, if present, where supported, unless) survive.
- Bare abstractions: three or more abstract guidance bullets with no paired rejected/accepted example, template, or gate.
- Fixed output skeletons: one mandated report shape (summary, findings, recommendations, next steps) regardless of consumer.
- Skill bundles (.claude/skills/**): first/second-person frontmatter descriptions — quoted user-utterance trigger phrases are not voice; over-broad or keyword-stuffed trigger descriptions; SKILL.md over 500 lines or carrying reference banks inline; references that only route to other references; deterministic multi-step procedures narrated in prose where a bundled script belongs; instructed network fetches or global installs inside skill bodies, except an owned install surface naming exact source, scope, and verification.
