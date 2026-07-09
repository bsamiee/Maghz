# Review context — Maghz

VPS second-brain repo: Python admin tooling, container topology (compose.yaml), database schema, and workflow automation for the durable Hostinger VPS. Machine-level shell/PATH/tooling concerns belong to Parametric_Forge, never here.

## Design paradigms

- Python rides the Rasm doctrine: typed rails, expression-shaped logic, dispatch surfaces over helper spam, uv-only custody.
- Infrastructure state is declarative: compose rows, schema migrations, and admin verbs — imperative one-off scripts that mutate the VPS outside these owners are defects.
- Doppler owns secrets end to end; the repo carries references, never values.

## Universal bar

Anticipate 10x functionality growth: surfaces absorb new modalities as rows, cases, or dispatch arms — never as new files, flags, or knobs. Defects: knob/param/flag spam, hardcoded values, fragile string plumbing, naive happy-path logic, hand-rolled reimplementations of capability the ecosystem already provides. External packages are first-class implementation material at full power, newest stable versions. Everything ships agent-first: composable, receipt-bearing, self-describing. Collapse spam relentlessly.

## Review priorities

1. Secret leakage and custody violations outrank everything.
2. Doctrine regressions (rails, dispatch, uv custody) outrank style.
3. Cross-repo boundary breaches (machine config creeping in from Forge territory) are defects.
