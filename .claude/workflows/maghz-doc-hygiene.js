export const meta = {
  name: 'maghz-doc-hygiene',
  description: 'Final comment + docstring hygiene pass over ALL Maghz code files: reform every comment and docstring to CLAUDE.md file-organization, the style-guide, and the code-documentation standard. One agent per sub-folder cuts comment litter (1-2 lines, agent-facing only), normalizes the section dividers, and reforms Google-style docstrings only where the declaration cannot carry the fact. Comments and docstrings only, never code logic. Runs from Rasm, edits Maghz by absolute path, directly on main, last in the pipeline.',
  whenToUse: 'After the Maghz code rebuilds settle, to bring every comment and docstring to the three governing standards across all code files',
  phases: [
    { title: 'Discover', detail: 'one sonnet mapper: enumerate every Maghz sub-folder holding in-scope code files (py/sql/sh/ts/lua/nix/Dockerfile), excluding pyproject.toml, lockfiles, json/md/yaml, and vendored dirs', model: 'sonnet' },
    { title: 'Clean', detail: 'one agent per sub-folder: read the three standards then reform every comment + docstring in place (cut litter, 1-2 line agent-facing comments, normalized dividers, Google docstrings only where needed); comments and docstrings only, no logic change' },
    { title: 'Verify', detail: 'one agent: ruff lint gate (docstring D-rules) + import smoke + a cross-folder consistency sweep of dividers/labels/docstring sizing, fixing regressions in place' },
  ],
}

// --- [TYPES] -- structured-output schemas (FIXLOG + GATE_RESULT reused from rebuild-code) ---
const DISCOVERY = { type: 'object', additionalProperties: false, required: ['folders'], properties: { folders: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['folder', 'files'], properties: { folder: { type: 'string' }, files: { type: 'number' } } } } } }
const FIXLOG = { type: 'object', additionalProperties: false, required: ['file', 'verdict', 'summary'], properties: { file: { type: 'string' }, verdict: { type: 'string', enum: ['rebuilt', 'refined', 'clean'] }, collapsed: { type: 'string' }, residual_high: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['files', 'claim'], properties: { files: { type: 'array', items: { type: 'string' } }, claim: { type: 'string' } } } }, summary: { type: 'string' } } }
const GATE_RESULT = { type: 'object', additionalProperties: false, required: ['green', 'ruff_clean', 'ty_clean'], properties: { green: { type: 'boolean' }, ruff_clean: { type: 'boolean' }, ty_clean: { type: 'boolean' }, rounds: { type: 'number' }, remaining: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['file', 'rule', 'message'], properties: { file: { type: 'string' }, rule: { type: 'string' }, message: { type: 'string' } } } }, advisory: { type: 'array', items: { type: 'string' } } } }

// --- [CONSTANTS] -- cross-repo paths + the bounded pool (reused from rebuild-code) ---------
const MAGHZ = '/Users/bardiasamiee/Documents/99.Github/Maghz'
const RASM = '/Users/bardiasamiee/Documents/99.Github/Rasm'
const CAP = 10
const STAGGER_MS = 1500
const pool = async (items, cap, worker) => {
  const out = new Array(items.length)
  let next = 0
  const run = async (slot) => {
    if (slot) await new Promise((res) => setTimeout(res, slot * STAGGER_MS))
    while (next < items.length) { const i = next++; out[i] = await worker(items[i], i) }
  }
  await Promise.all(Array.from({ length: Math.min(cap, items.length) }, (_, slot) => run(slot)))
  return out
}

// --- [MODELS] -- the embedded hygiene law (the three governing standards) -----------------
const LAW = [
  'COMMENT + DOCSTRING HYGIENE for the Maghz operator codebase — reform every comment and docstring IN PLACE to the three governing standards. Change comments, docstrings, and section-divider headers ONLY; NEVER alter code logic, signatures, imports, control flow, or behavior.',
  'READ THESE THREE STANDARDS FIRST and hold each as law: ' + RASM + '/CLAUDE.md (section [08]-[FILE_ORGANIZATION] + the [04] comment-narration bans), ' + RASM + '/docs/standards/style-guide.md, ' + RASM + '/docs/standards/reference/code-documentation.md.',
  'SECTION DIVIDERS (CLAUDE.md [08]): keep the canonical section-divider headers — language-comment marker + space + `---` + a bracketed `[UPPERCASE_LABEL]` (no internal spaces) + dash-fill to the established language width. Canonical order, omitting unused: RUNTIME_PRELUDE -> TYPES -> CONSTANTS -> MODELS -> ERRORS -> SERVICES -> OPERATIONS -> COMPOSITION -> EXPORTS, plus precise domain extensions ([TABLES], [BOUNDARIES], [REPOSITORIES], [GROUPS], [MIDDLEWARE], [INDEXES], [POLICIES], [ENTRY]). NESTED SUB-SECTION labels inside a large owner (e.g. [VECTOR_HEAT], [NORMAL_ESTIMATION]) use NO trailing dash-fill — just the comment marker + space + the bracketed label. Use canonical labels; never alias/drift labels (SCHEMA/FUNCTIONS/LAYERS/IMPORTS/INTERFACES/ENUMS/DTO/QUERIES/HELPERS/UTILS/COMMON/MISC).',
  'COMMENT LAW (CLAUDE.md [04] + style-guide NOISE_REMOVAL): comments are AGENT-FACING only. Default to ZERO comments on self-evident code; at most 1 line where a comment genuinely earns its place; 1-2 lines only for a truly subtle invariant, contract, or boundary. NO comment that restates the code, narrates a step, or carries task/session/subagent/review-label/proof/history/process content. Strip leads that describe the artifact, provenance, freshness disclaimers, report framing, and empty hedges (may/might/probably/generally/where possible/if needed); keep contract qualifiers (optional/if present/where supported/when configured). Backtick every symbol, type, field, function, path, command, flag, and literal. Densify names + types so comments are rarely needed; cut every low-value comment.',
  'DOCSTRING LAW (code-documentation.md DECISION_ROUTER): a docstring exists ONLY when the declaration cannot carry a caller-visible fact. REPAIR_FIRST — prefer stronger source shape (rename/retype/annotate/schema metadata) over prose. DOCUMENT_WHEN the declaration omits a caller obligation, result/failure semantics, side effect, resource/cancellation contract, or security/data-exposure fact. OMIT_WHEN the text echoes a symbol name, parameter type, return carrier, field/column name, branch, or implementation step. ROUTE_AWAY generated mirrors, folder architecture, and lifecycle facts. A docstring that names only the carrier (a bare `Returns: Result[T, E]`/`Promise<T>`/SQL return type without the failure variants) is INCOMPLETE.',
  'PYTHON (code-documentation.md [6.3]) — Google docstrings (Griffe/mkdocstrings): the Summary is ONE line that does NOT echo the function name; `Args:` carry obligation/unit/ownership/trusted-boundary, never the declared type; `Returns:` documents the `Ok` payload AND each meaningful error variant for a `Result[T, E]` rail; `Raises:` is for INTENTIONALLY-EXPOSED native exceptions ONLY — NEVER for a typed rail, confirmation data, warnings, or precondition violations. Module-header docstrings: 1-2 lines for a simple module, an extended summary only where the module genuinely needs it (invariants, lifecycle, resource, concurrency, security). Pydantic/msgspec metadata owns schema field descriptions — do not duplicate them in prose; never put secrets/personal-data/tenant-ids/credentials in any docstring or schema metadata.',
  'OTHER LANGUAGES: SQL (PostgreSQL 18.4) — `COMMENT ON` owns durable catalog meaning; SQL source comments own local migration/RLS/function-body rationale only (PostgreSQL treats source comments as whitespace, so do not put durable schema meaning there). Bash 5.3+ — contract comments only (script header: bash baseline, command surface, stdout/stderr role, exit-status vocabulary, traps/cleanup; command functions: purpose, args, globals read/written, exit status), no pseudo-docstring blocks, no comment-for-every-function, no source-echo of `local`/`readonly`. Dockerfile — only genuinely non-obvious rationale. TypeScript — TSDoc for exported APIs only, never JSDoc type-expression echo.',
  'ANTI-PATTERNS to delete (code-documentation.md [08]): a type-restating parameter entry, a throw-tag for a typed rail, a carrier-echo return, a hidden side-effect/cancellation omission, a name-echo summary, a manual profile label or line-narration leakage, generated/lifecycle preservation, and any comment that restates the next statement.',
  'WRITE-FULLY: make every edit NOW via Edit/Write directly in the file on disk. The FIXLOG you return REPORTS edits already made. If a file is already clean to the standards, return verdict=clean — never invent churn. Touch ONLY comments, docstrings, and section dividers; if you would need a logic/signature change, leave it and record a residual_high instead.',
].join('\n')

// --- [OPERATIONS] -- prompt builders ------------------------------------------------------
const discoverPrompt = 'TASK: ENUMERATE every sub-folder under ' + MAGHZ + ' that contains in-scope CODE files (READ-ONLY map). IN-SCOPE extensions: .py .sql .sh .bash .ts .tsx .lua .nix and the file named Dockerfile. EXCLUDE directories: .git .venv __pycache__ node_modules .cache .artifacts .claude/plugins . EXCLUDE files: pyproject.toml, uv.lock, any .json, .md, .yaml, .yml, .lock . Use find over ' + MAGHZ + ' (do NOT cd) to list every in-scope file, then group by the IMMEDIATE owning directory (relative to ' + MAGHZ + '). Return DISCOVERY {folders:[{folder, files}]} — one entry per distinct directory that holds at least one in-scope file, with files = the count of in-scope files in that directory.'
const cleanPrompt = (f) => [LAW, '', 'TASK: COMMENT + DOCSTRING HYGIENE of every in-scope code file in the Maghz sub-folder `' + f + '` (absolute: ' + MAGHZ + '/' + f + '). FIRST read the three standards named above, then reform every .py/.sql/.sh/.bash/.ts/.tsx/.lua/.nix/Dockerfile file in THIS folder IN PLACE: cut comment litter; hold comments to 1-2 lines and only where the declaration cannot carry the fact; normalize the section-divider headers to the CLAUDE.md form (main dividers dash-filled to language width, nested sub-section labels with NO trailing dashes); reform module-header and public-surface docstrings to Google style (1-2 line headers for simple files, an extended summary only where genuinely needed) per the DECISION_ROUTER. NEVER change code logic, signatures, imports, or behavior — comments, docstrings, and dividers ONLY. Do NOT touch pyproject.toml, lockfiles, .json/.md/.yaml, or any file outside ' + MAGHZ + '/' + f + '. Report the litter you cut and the docstrings you added/trimmed in `collapsed` and `summary`. Return ONE FIXLOG (set file to `' + f + '`) + residual_high {files, claim} for any cross-folder inconsistency or any place a real fix needs a logic/signature change you correctly left alone.'].join('\n')
const verifyPrompt = [LAW, '', 'TASK: VERIFY the comment/docstring hygiene pass across all of Maghz and FIX every regression in place (comments/docstrings only). (1) LINT GATE: run bash -lc "cd ' + MAGHZ + ' && uv run ruff check ." — ruff carries the docstring lints (the D-rules); fix every diagnostic in the SOURCE via a comment/docstring change, NEVER a logic change, NEVER a `# noqa`, NEVER a pyproject relaxation. (2) IMPORT SMOKE: run bash -lc "cd ' + MAGHZ + ' && uv run python -c \'import admin\'" — the package must still import (proves no docstring edit broke a module). (3) CONSISTENCY SWEEP: confirm the section-divider headers, the nested sub-section-label styling (no trailing dashes), the canonical-label usage, and the docstring sizing are UNIFORM across every folder per the embedded law; fix any drift in place. Re-run the lint + import after each fix until clean. Return GATE_RESULT with green (ruff clean AND import ok AND consistent), ruff_clean, ty_clean (set true and note in `advisory` that ty is not run for a comment-only pass), the internal fix-pass count in `rounds`, and any `remaining` diagnostics if not green.'].join('\n')

// --- [COMPOSITION] -----------------------------------------------------------------------
phase('Discover')
const inv = await agent(discoverPrompt, { label: 'discover', phase: 'Discover', schema: DISCOVERY, model: 'sonnet', effort: 'low', stallMs: 300000 })
const folders = ((inv && inv.folders) || []).filter((x) => x && x.folder).map((x) => x.folder)
log('Discover: ' + folders.length + ' sub-folder(s) with in-scope code files under ' + MAGHZ)

phase('Clean')
const cleaned = folders.length ? (await pool(folders, CAP, (f) => agent(cleanPrompt(f), { label: 'clean:' + f, phase: 'Clean', schema: FIXLOG, effort: 'high', stallMs: 420000 }))).filter(Boolean) : []
log('Clean: ' + cleaned.length + '/' + folders.length + ' folder(s) reformed')

phase('Verify')
const gate = await agent(verifyPrompt, { label: 'verify', phase: 'Verify', schema: GATE_RESULT, effort: 'high', stallMs: 600000 })
log('Verify: ' + (gate && gate.green ? 'GREEN' : 'gate NOT green'))

return {
  scope: 'maghz-all-code',
  folders: folders.length,
  reformed: cleaned.length,
  green: !!(gate && gate.green),
  verdicts: Object.fromEntries(cleaned.map((l) => [l.file, l.verdict])),
  collapses: cleaned.map((l) => l.collapsed).filter(Boolean),
  residual: cleaned.flatMap((l) => (l.residual_high || []).map((r) => r.claim)),
  remaining: (gate && gate.remaining) || [],
}
