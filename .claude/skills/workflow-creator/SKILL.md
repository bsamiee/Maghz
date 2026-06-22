---
name: workflow-creator
description: >-
  Author runnable workflow scripts for Claude Code's Workflow tool — deterministic
  multi-agent orchestration files that fan out fresh-context subagents under plain
  JavaScript control flow. Use this skill whenever the user wants to create, write,
  build, scaffold, design, or fix a workflow: "make a workflow", "create a workflow
  for X", "write a workflow", "turn this into a workflow", "scaffold a multi-agent
  pipeline", "orchestrate this with subagents deterministically", or any request to
  author or edit a .js file under .claude/workflows/. Also use it when the user is
  confused about the workflow script format — the meta block, agent()/parallel()/
  pipeline()/phase(), schemas, the determinism rules — or when a workflow errors and
  needs debugging. Trigger this even when the user only describes a repeatable
  multi-step or parallel job and seems to want it packaged as a workflow, even if
  they never say the word "workflow". Do NOT use it to merely run an existing
  workflow, or for a one-off single-subagent task.
---

# Workflow Creator

Turn a goal into a **runnable workflow file** — a JavaScript orchestrator for
Claude Code's `Workflow` tool.

A workflow fans work out to fresh-context subagents under **deterministic
JavaScript** control flow: the loops, the conditionals, the fan-out are plain
code, and only the leaf `agent()` calls spend model tokens. This skill owns the
file format, the judgment calls, and the authoring procedure. Use it to write a
new workflow, convert a multi-step job into one, or fix a broken script.

The deep material lives in two reference files, read in this order:

- `references/api-reference.md` — read **first**, the correctness source: the
  complete manual (every global, every option, every cap and constant, what
  happens at each limit) and the deep owner of the `pipeline` vs `parallel`
  decision.
- `references/patterns.md` — read **second**, the composed-topology catalog
  (fan-out, pipeline, routing, orchestrator-workers, evaluator-optimizer,
  adversarial verify, judge panel, nested workflow). Copy the topology that fits
  Step 2's answers.

Starter files are in `assets/templates/` — three control-flow skeletons (fan-out,
pipeline, loop). Eight complete, runnable example workflows are in
`assets/examples/` — `assets/examples/README.md` maps each one to a topology and
to the model / structured-output techniques it shows. A linter is in `scripts/`.

---

## Step 0 — Where workflows live

Workflow files live in `.claude/workflows/<name>.js` (project-local) or
`~/.claude/workflows/<name>.js` (global). The filename is not the workflow name —
the `name` inside the `meta` block is. The tool is enabled by default — write the
file and it runs.

---

## Step 1 — Decide whether a workflow is even the right tool

Do not reach for a workflow by default — it is the heaviest option and it is
gated for a reason (it can spend a lot of tokens). Pick deliberately:

| The job | Right tool |
|---|---|
| One subagent, one task | The plain **`Agent`** tool — no workflow |
| A reusable procedure where **Claude** picks the steps each run | A **Skill** |
| Many subagents in a **fixed** shape (fan-out / pipeline / loop), same every run, worth resuming | A **Workflow** ✅ |

A workflow earns its cost when **all** of these are true: the work is parallel or
multi-stage; you want the orchestration deterministic and resumable; and
isolating each step in its own fresh context window is an advantage. If you are
unsure, say so and offer the lighter option instead.

---

## Step 2 — Find the shape of the job

Before writing a line of code, answer these. The answers pick the topology for you.

1. **What is the unit of work?** The thing one subagent does once — review one
   file, research one question, draft one platform. Name it concretely.
2. **How many units, and is the count known up front?** A known list → map over
   it. An unknown count (discovery, "find all the bugs") → a loop.
3. **What is the topology?**
   - Independent units, one pass each → **fan-out**.
   - Units flow through ordered stages (review → verify) → **pipeline**.
   - Keep going until a target count or a budget runs low → **loop**.
4. **Does any later step need *all* the earlier results at once** — to dedup,
   merge, count, or early-exit on a zero total? If yes, you need a **barrier**.
   If no, you do not — and you should prefer `pipeline`.
   - **The deferral case.** If a unit DEFERS work it cannot do alone (cross-item,
     cross-file, "report and move on"), a fan-out is not enough — add a terminal
     **reconcile** stage that consumes the collected deferrals, or they reach the
     conversation and nothing acts on them. Structure each deferral as DATA whose
     resource slot is a LIST (`{files: string[], claim}`) so a deferral spanning
     two files names BOTH — that is what lets you cluster deferrals by shared
     resource in plain JS, then fix-and-verify each cluster (pattern #13). A
     single-resource slot can only group same-resource items and silently cannot
     express a cross-item seam.
5. **Does a step need structured data back** (not free text)? Then that
   `agent()` call needs a `schema`.

Write these five answers down for the user before coding. They are the design.

---

## Step 3 — The decision that matters most: `pipeline` vs `parallel`

This is the call people get wrong, so make it explicitly.

- **`pipeline(items, stage1, stage2, …)` is the default for multi-stage work.**
  Each item flows through every stage on its own — **there is no barrier between
  stages**. Item A can be in stage 3 while item B is still in stage 1.
  Wall-clock = the slowest single item's whole chain, not the sum of the slowest
  stage at each step.

- **`parallel(thunks)` is a barrier.** It waits for every task before returning.
  Reach for it **only** when a stage genuinely needs the *entire* previous
  result set in hand — dedup across all findings, merge, a count-based
  early-exit. "It is cleaner code" or "the stages feel separate" are **not**
  reasons — a pipeline models separate stages fine.

Smell test: if you would write `const a = await parallel(...)`, then a plain
transform (`flat`/`map`/`filter`) with no cross-item dependency, then another
`parallel(...)` — that middle transform does not need the barrier. Make it a
pipeline stage instead. **When in doubt, `pipeline`.**

---

## Step 4 — Write the file

A workflow file has exactly two parts, in this order. The parser is strict.

### Part 1 — the `meta` block (must be the very first statement)

```js
export const meta = {
  name: 'review-changes',                         // required, non-empty
  description: 'Review changed files, verify each finding', // required — shown in the permission dialog
  whenToUse: 'Before shipping a branch',          // optional — shown in the workflow list
  phases: [                                       // optional — one entry per phase() call
    { title: 'Review' },
    { title: 'Verify', model: 'haiku' },
  ],
}
```

`meta` **must be a pure literal** — no variables, function calls, spreads, or
template strings inside it. Build dynamic values in the body, never in `meta`.
Use the same phase `title` strings in `meta.phases` as in your `phase()` calls.

### Part 2 — the body (async JavaScript)

Everything after `meta` is the body. It runs inside an `async` function, so you
`await` at the top level. These globals are injected — **do not import anything**:

| Global | Purpose |
|---|---|
| `agent(prompt, opts?)` | Spawn one fresh-context subagent. Returns its final text, or a validated object if `opts.schema` is set. Returns `null` if the user skips it. |
| `pipeline(items, s1, s2, …)` | Run each item through all stages, no barrier between stages. The default for multi-stage work. |
| `parallel(thunks)` | Run an array of **functions** `() => Promise` concurrently. A barrier. |
| `phase(title)` | Group the agents that follow under a heading in `/workflows`. |
| `log(msg)` | Emit a narrator line above the progress tree. |
| `console` | A standard-looking `console` — its output is routed into the workflow log. |
| `budget` | `{ total, spent(), remaining() }` — token target for budget-aware loops. |
| `args` | Whatever was passed as the Workflow tool's `args` input, exposed as **structured data** — an object/array/string you read directly (`args.minUsers`, `args.map(...)`). `undefined` if nothing was passed. Default the omitted case (see below). |
| `workflow(name, args?)` | Run another workflow inline. One level of nesting only. |

The body's `return` value becomes the tool result handed back to Claude.

> **`args` arrives as structured data — read it directly.** Whatever the caller
> passed is exposed live: an object stays an object, an array stays an array, a
> string stays a string. Call array and object methods on it without parsing —
> `args.minUsers`, `args.map(...)`, `args.filter(...)` all work. When nothing is
> passed, `args` is `undefined`. So the only handling a script needs is a default
> for the omitted case and, when the same workflow is sometimes driven by a free-text
> request and sometimes by a config object, a shape check:
>
> ```js
> const threshold = args?.minUsers ?? 20            // object input, with a default
> const items = Array.isArray(args) ? args : []     // array input
> const task = typeof args === 'string' ? args : 'the change described in TASK.md'
> ```
>
> Never `JSON.parse(args)` — it is already a live value, not JSON text. The
> `?? default` is what keeps the file runnable on a no-args run. `references/api-reference.md`
> §4 maps each caller input to the exact `args` value it produces.

### Setting a model, and getting structured data back — the two `agent()` opts you tune most

**Model — `agent(prompt, { model })`.** Each agent call runs on its own model.
Accepts `'haiku'`, `'sonnet'`, `'opus'`, `'inherit'`, or a full model ID; omit it
and the agent inherits the session's model. Drop **cheap, high-volume,
mechanical** leaf work (per-item summaries, refute-this checks, classification)
to `'haiku'`; leave judgement-heavy work on the inherited model. Two cautions:

- **There is no validation.** A typo (`'hauku'`) is not rejected — it is passed
  through and the agent fails later. Spell the alias exactly.
- **`model` on a `meta.phases[]` entry does nothing at runtime** — it is a label
  for the permission dialog only. The model is set *solely* by the `model` opt on
  the `agent()` call. For a Haiku phase, set `model` in *both* places: the phase
  entry (honest dialog) and every `agent()` call in it (actual effect).

**Reasoning effort — `agent(prompt, { effort })`.** Sets the reasoning-effort tier
for that call — `'low'` | `'medium'` | `'high'` | `'xhigh'` | `'max'` (mirrors
`/effort`); omit it to inherit the session tier. Match it to the stage's role:
`'max'`/`'xhigh'` for synthesis, authoring, and adversarial judgment; `'low'` for
mechanical discovery/classification leaf work. It is independent of `model` (tier
the *reasoning*, not the model) and is **not** part of the resume cache key, so
changing `effort` alone never re-runs a cached call.

**Structured output — `agent(prompt, { schema })`.** Without `schema` you get the
agent's final text as a **string**. Pass a JSON Schema and the agent is *forced*
to return a **validated object** matching it — the runtime builds a hidden
`StructuredOutput` tool from the schema, AJV-validates the result, and makes the
agent retry on a mismatch. `agent()` returns the parsed object directly — no
`JSON.parse`. Use `schema` for any result a later line of JavaScript reads a
field off of; keep schemas small and `required`-tight. To pass data *between*
stages, stringify it into the next prompt (`JSON.stringify`) — the orchestrator
shares no memory with the subagent, only the prompt text.

For full signatures, every option, and every cap, **read
`references/api-reference.md` now.** For ready-made orchestration shapes, **read
`references/patterns.md`** and copy the one that fits Step 2's answers. Or start
from a file in `assets/templates/`, or adapt a full worked example from
`assets/examples/` (its `README.md` says which one fits).

---

## Step 5 — Validate before running

Catch the parser's hard rules before you waste a run. Use the bundled linter:

```bash
node .claude/skills/workflow-creator/scripts/validate-workflow.mjs <path-to-file.js>
```

It flags: missing or non-first `meta`, a non-literal `meta`, a missing
`name`/`description`, banned non-deterministic calls, and an oversized script.
Fix every error it reports before invoking the workflow.

---

## Step 6 — Run, watch, iterate

Run a named workflow with `Workflow({ name: 'review-changes' })`, or a file with
`Workflow({ scriptPath: '…' })`. It runs in the **background** — the call returns
a run ID immediately and a `<task-notification>` arrives on completion. Watch it
live with the `/workflows` command, where you can also pause/resume the run and
stop, restart, or read a single agent mid-run.

A user reaches a workflow from their side in three ways: a saved or bundled command
(`/deep-research …`, or any workflow saved to `.claude/workflows/`); the `ultracode`
keyword in a prompt (or asking "use a workflow" in plain words), which makes Claude
write a one-off workflow for that task; or `/effort ultracode`, which lets Claude
plan a workflow for every substantive task in the session. Saving a good run is
`s` in `/workflows`, which writes the script to `.claude/workflows/` (project) or
`~/.claude/workflows/` (personal) as a reusable `/<name>` command.

To iterate: **edit the saved file**, then re-invoke with
`Workflow({ scriptPath, resumeFromRunId })`. Every `agent()` call before your
first edit replays instantly from cache; only the changed call and everything
after it re-runs. Same script + same args = a 100% cache hit. Never re-paste the
whole script after the first run — edit the file.

---

## Gotchas — check every one before you hand over the file

These are the mistakes that actually break workflows:

- **Determinism bans.** `Date.now()`, `Math.random()`, and argless `new Date()`
  **throw** inside a workflow — they would break resume. Pass timestamps in via
  `args` and stamp results *after* the workflow returns; vary "randomness" by
  loop index instead. `new Date(specificValue)` is fine.
- **No filesystem, no Node APIs** in the orchestrator. No `require`, `fs`,
  `process`. Any file read/write/Bash work belongs **inside an `agent()`** — the
  subagent has the normal tools; the orchestrator does not.
- **`parallel()` takes thunks, not promises.** It must be
  `[() => agent(...), () => agent(...)]`, never `[agent(...), agent(...)]`. Bare
  calls start immediately and defeat the concurrency limiter.
- **Always `.filter(Boolean)`.** `parallel()` and `pipeline()` put `null` in the
  slot of any item that threw, was skipped, or was dropped by the budget. The
  result arrays have holes by design.
- **`meta` is a pure literal and the first statement.** No dynamic values, no
  code before it.
- **Open-ended loops need a hard stop** — a counter (`while (found < 10)`) or a
  budget guard (`while (budget.total && budget.remaining() > 50_000)`). With no
  budget set, `budget.remaining()` is `Infinity`; an unguarded loop sprints into
  the 1000-agent lifetime cap and throws.
- **`isolation: 'worktree'` is expensive** (~200–500 ms + disk per agent). Use it
  only when parallel agents mutate files and would otherwise collide.
- **Grant permissions before a long parallel run.** Subagents run in `acceptEdits`
  mode and inherit the session tool allowlist; a non-allowlisted shell, web, or MCP
  call can still surface a mid-run permission prompt and stall the run.
- **The body is JavaScript only.** TypeScript syntax — type annotations,
  interfaces, `as` casts — is a parse error.

---

## Worked example — review a branch, verify each finding

The shape: fan out one reviewer per dimension; the moment a dimension's review
returns, fan out a verifier per finding. `pipeline`, because a finding should
verify as soon as *its* review is done — no waiting for the slowest dimension.

```js
export const meta = {
  name: 'review-branch',
  description: 'Review the branch across dimensions, adversarially verify each finding',
  phases: [{ title: 'Review' }, { title: 'Verify', model: 'haiku' }],
}

const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object', required: ['title', 'file'],
    properties: { title: { type: 'string' }, file: { type: 'string' } } } } } }
const VERDICT = { type: 'object', required: ['isReal'], properties: {
  isReal: { type: 'boolean' }, reason: { type: 'string' } } }

const DIMENSIONS = [
  { key: 'bugs', prompt: 'Find logic bugs in the changed files on this branch.' },
  { key: 'perf', prompt: 'Find performance regressions in the changed files.' },
  { key: 'tests', prompt: 'Find missing or weak test coverage in the changes.' },
]

const results = await pipeline(
  DIMENSIONS,
  d => agent(d.prompt, { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS }),
  review => parallel((review?.findings ?? []).map(f => () =>
    agent(`Adversarially verify this finding. Try to refute it. Finding: ${f.title} (${f.file})`,
          { label: `verify:${f.file}`, phase: 'Verify', model: 'haiku', effort: 'high', schema: VERDICT })
      .then(v => ({ ...f, verdict: v }))
  ))
)

const confirmed = results.flat().filter(Boolean).filter(f => f.verdict?.isReal)
return { confirmedCount: confirmed.length, confirmed }
```

Trace it: dimension `bugs` can be verifying its findings while `perf` is still
being reviewed. No wasted wall-clock. Each agent reasons from a clean context.
The orchestrator JavaScript spends zero model tokens. The verify stage tiers both
axes independently — `model: 'haiku'` (the per-finding refute is cheap, high-volume
leaf work) with `effort: 'high'` (it must still reason hard to break a plausible
finding) — and mirrors the `model` on its `phase` entry so the dialog stays honest.

---

## When the user wants to learn, not just get a file

If the request is "explain how workflows work" rather than "build me one", walk
them through `references/api-reference.md` — it is written to be read top to
bottom as the complete reference. Then offer to scaffold their first workflow from
a template so they have something runnable to poke at.
