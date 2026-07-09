# Review context — Maghz

VPS second-brain repo: Python admin tooling, container topology, database schema, and workflow automation for the durable Hostinger VPS. Machine-level shell/PATH/tooling concerns belong to Parametric_Forge, never here.

## Design paradigms

- Python rides the local docs/stacks/python law: typed rails, expression-shaped logic, dispatch surfaces over helper spam, uv-only custody.
- Infrastructure state is declarative: the Pulumi stack in admin/infra.py is the end-state topology owner and compose.yaml is its transitional declaration — drift between them is a defect, and imperative one-off scripts that mutate the VPS outside these owners are defects. Numbered migrations and up/down pairs are defects; canonical schema files replay to no-op.
- Ops rails per docs/standards/ops-doctrine.md: thin CLI lowerers, one settings owner, typed operation receipts, one scoped SSH rail for remote work.
- Doppler owns secrets end to end; the repo carries references, never values.
- Generated projections (.mcp.json, .codex/) re-render from their generator; hand edits are defects.

## Universal bar

Anticipate 10x functionality growth: surfaces absorb new modalities as rows, cases, or dispatch arms — never as new files, flags, or knobs. Defects: knob/param/flag spam, hardcoded values, fragile string plumbing, naive happy-path logic, hand-rolled reimplementations of capability the ecosystem already provides. External packages are first-class implementation material at full power, newest stable versions. Everything ships agent-first: composable, receipt-bearing, self-describing. Collapse spam relentlessly.

## Review priorities

1. Secret leakage and custody violations outrank everything.
2. Doctrine regressions (rails, receipts, dispatch, uv custody, declarative SQL) outrank style.
3. Cross-repo boundary breaches (machine config creeping in from Forge territory) are defects.

## Load-bearing exceptions

Code that violates generic best practice on purpose — do not flag:

- Aggressive API breaks with every call site updated in the same change are the sanctioned rename path, not regressions.
- Dense single-expression bodies and heavy polymorphic dispatch are the bar, not obfuscation.
- Absent defensive guards inside domain logic reflect admission-once boundaries, not missing error handling.
- Sparse 1-2 line agent-facing comments are compliance with comment law, not missing documentation.
- Declarative schema files that drop and recreate objects on replay are the migration-free idiom, not destructive operations.
- A large file that owns one full concern is sanctioned; never recommend splitting by size.

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
