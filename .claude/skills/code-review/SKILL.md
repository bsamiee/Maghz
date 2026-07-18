---
name: code-review
description: >-
    Local code review through three engines — CodeRabbit (working tree), Greptile (committed
    commits vs base), Macroscope (in-place correctness streaming) — driven by one verb rail
    (`launch`, `status --follow`, `findings --normalize`, `slice`, `reconcile`, `harvest`,
    `round`, `verify`) through the COLLECT -> FIX -> DISPOSITION -> DISTILL cycle, with
    per-round `--focus` aiming, fixer-lane dispatch under a shipped lane law, and distillation
    into the `.coderabbit.yaml`, `.greptile/`, and `.macroscope/` reviewer-config surfaces.
    Trigger on any explicit review request, autonomously when a review is warranted (code,
    quality, security), on "run coderabbit", "run greptile", or "run macroscope", and when
    tuning any reviewer config. Hosted PR reviewer round-trips belong to pr-loop.
---

# [CODE_REVIEW]

Three local review engines feed one improvement machine: the rail launches and harvests every engine into one normalized finding schema, fixer lanes drain findings under the shipped lane law, and each round distills refuted classes and lessons into the reviewer configs so the next round runs harder.

## [01]-[ROUTING]

[REFERENCES]:
- [01]-[CODERABBIT](references/coderabbit.md): `.coderabbit.yaml` schema and limits, guidance channels, the rich finding store; open when landing a CodeRabbit fact or reading its store
- [02]-[GREPTILE](references/greptile.md): `.greptile/` cascade and `config.json` fields, the command surface, the ledger-to-MCP bridge; open when landing a Greptile fact or correlating a run
- [03]-[MACROSCOPE](references/macroscope.md): `.macroscope/` concern-file contract, ignore semantics, CLI base semantics; open when landing a Macroscope fact or shaping its scope

[SCRIPTS]:
- [01]-[REVIEW_RAIL](scripts/review_rail.py): verb rail printing one JSON receipt per verb; stream mechanics, scope enforcement, liveness verdicts, and id stamping live here

## [02]-[CYCLE]

Every round runs COLLECT -> FIX -> DISPOSITION -> DISTILL on two custody lanes: work under review rides its own lane — working tree or committed slice, as its engine's scope names — while distillation rides origin's default branch and pushes the moment it lands, so the next round runs under the hardened configs.

- [SELECTION]: scope need picks the engine — `coderabbit` sweeps working tree and commits at full depth every run (a retry re-spends quota), `greptile` reads committed commits against a base and size-caps the diff (slice commits are the review unit; a refusal splits the slice at the prior boundary), `macroscope` streams correctness over the working tree in place.
- [COLLECT]: `launch` detaches the run, `status --follow` watches to terminal, `findings --normalize` lands schema rows plus the severity histogram, and `slice` derives the per-lane grouping.
- [FIX]: `slice` manifests staff the wave — one fixer lane per manifest, prompt assembled fresh from the lane-law blocks; each lane returns only its report path, so report bodies never enter the orchestrator's context.
- [DISPOSITION]: `reconcile` proves id-bijection per lane and emits the verdict histogram; a dropped finding closes through one focused opus closer armed with the slice's stack doctrine, never a session resume.
- [DISTILL]: `harvest` assembles the feed from lane reports on disk, lessons land per [05], and `round` appends the `rounds.jsonl` row and prints the round-over-round delta; a zero-findings round skips FIX and DISPOSITION and closes clean through `round`.
- [ROTATION]: rounds serialize — one live engine at a time — and the ledger records the reviewer per round, so recurrence judges per engine; counts flattening under one engine rotate the next round to another, while `--focus` aims a round within an engine at a named surface or a recurring class.

## [03]-[USAGE]

```bash template
uv run ${CLAUDE_SKILL_DIR}/scripts/review_rail.py launch --reviewer <engine> --scope <scope> [--focus <text-or-file>]
```

Every verb accepts `--round N` and `--dir` and prints one JSON receipt. `launch` refuses an unsupported engine-scope pair and a live prior round loudly; `--focus` takes inline text or a file path — greptile rides `--instructions`, coderabbit a round-scoped `-c` instruction file, and macroscope refuses focus loudly because config files are its only steering.

- [CODERABBIT]: canonical round `--reviewer coderabbit --scope uncommitted`; full scope family `all|committed|uncommitted|base:<ref>|base-commit:<sha>`.
- [GREPTILE]: canonical round `--reviewer greptile --scope base:<prior-boundary>` after committing the slice; `committed` reviews against the default base; findings harvest from the captured `--json` stdout, with the ledger, `review status`, and MCP as operator retrieval.
- [MACROSCOPE]: canonical round `--reviewer macroscope --scope base:<default-branch>` spanning committed branch work plus uncommitted edits, `uncommitted` for tree-only; always in place — fixes land in the files the review read.

Waiting is one mechanic: run `status --follow` through Bash `run_in_background` — never foreground, never a per-turn `status` poll. Its loop prints a liveness line about every 60 s (phase, elapsed, pulse age, findings seen), self-exits at the terminal phase, and its exit re-invokes the agent. Long pulse gaps are normal — a coderabbit run holds ~17 minutes on heartbeat alone — and the terminal `stalled` and `timed-out` phases are the only hang verdicts, so a quiet run is never killed early; `last_pulse_age_s` on the status receipt is the liveness read.

`findings --normalize` gates on terminal phase `completed` — a `refused`, `failed`, or `stalled` round reports its phase reason, never a harvest fault — and `--dedup-against N` drops rows whose fingerprint already landed in round N, the cross-round and cross-engine dedup. `slice --lanes N --by folder --balance count|loc` clears stale lane files, stamps round-scoped ids, and emits per-lane manifests carrying the settled-rulings roster. `reconcile` covers all lanes bare (`--all` is the explicit synonym; a named lane plus `--all` refuses). `round` refuses a duplicate close, fails loud on findings without lane reports, and closes a zero-findings round clean. `verify --rule <text> [--path <file>]` proves a distilled greptile rule resolved into the effective config.

## [04]-[LANE_LAW]

Sol fleets run fix waves — up to 12 lanes sliced by folder ownership, balanced by finding count; fable runs the distill; opus runs focused closers for dropped findings and routed families. Each lane's prompt assembles fresh per wave from these blocks, the settled-rulings roster generated from the refuted-class registry:

- [ARMING]: each lane reads the owning `docs/stacks/<language>/` doctrine in full plus the settled system pages its slice composes — read each dispatch, never inherited from a prior wave.
- [REFUTE_FIRST]: every claim verifies against current disk and doctrine before any edit — the review snapshot may predate later edits; a finding contradicting a settled ruling is pushed back citing that ruling, never re-investigated; push-back and fix count equally, neither quota'd.
- [TRICHOTOMY]: value-check findings split three ways — interior re-validation of admitted values is pushed back (generated-enum instances and value-struct payloads are this class by construction), default-ghost struct storage seams keep their check, host-crossing reads admit it.
- [CAPABILITY]: findings are the floor — on files under edit, flat or repeated arms collapse into polymorphic owners, hardcoded shapes parameterize, and charter-implied capability lands sourced from one or two read-only `.api`-mining sub-agents; every added host member passes the truth rail first, and an ungrounded extension is a routed idea row, never code.
- [IMPRESSIVE]: measurable, never a mood — the defect class dissolves at its root so it cannot respell anywhere, the owning surface ends denser and more general than a local patch leaves it, and implied capability lands as rows or cases on existing owners, never parallel surfaces.
- [TERRITORY]: a lane writes exactly its sliced files and never stages or commits — git belongs to the orchestrator; a confirmed out-of-territory defect becomes a routing row, closed post-round by one focused opus agent per coherent family.
- [VERIFICATION]: host members prove against the truth rail; prose gate runs once, batched after the final edit; no build or test attempt ever — fences are design.
- [OUTPUT]: each lane writes `<round-dir>/<lane>-report.json` as its final act — `ledger` rows `{id, file, severity, verdict, note}` with `verdict` one of `fixed|upgraded|pushed-back|already_resolved`, plus `improvements[] {page, pattern, what}`, `refuted[] {claim, evidence}`, and `capability[]`/`routing[]`/`uncertain[]` — reconciles id-bijection, and returns only the path plus one status line.
- [SOL]: one `run_in_background` keeper per lane, spawn verified within a minute via the stderr banner; full user config with multi-agent depth 1 so the mining sub-agents can spawn — sub-agents mine, never author; stop rules ride an enumerated completion bar.

## [05]-[DISTILL]

Each surface receives a fact in its own idiom, one owner per fact per surface, the three mirrored at equal depth; per-surface grain lives in each reference's `[DISTILL_GRAIN]` section. Priority order: a recurred class hardens the existing owner's wording in place, a new refuted class lands as a do-not-flag guard citing its refuting ruling, and an improvement pattern extends the standing choreography, never a parallel list. Universal lessons land at global scope, language-bound lessons only in language-scoped rows or files.

`docs/` receives a rule only when refute-first proves no reviewer surface owns it; a universal pattern proven by fix-wave work may additionally strengthen the owning `docs/stacks/<language>/` fence — snippet-first, under that stack's page craft, never forced. A rail gap a round exposes lands on the rail's own script and data surfaces. `refuted-classes.yaml` in the rail's data dir carries one row per class — `{class_id, matchers, refuting_citation, landed_surfaces, rounds_seen}`: the classifier stamps `class_match` on incoming findings, `harvest` computes recurrence mechanically, and the settled-rulings roster generates from it. Format gates run before landing — each surface at its reference-owned validation rule, prose gate batched — and `verify` proves a landed greptile rule survived cascade precedence, where org rules always win.
