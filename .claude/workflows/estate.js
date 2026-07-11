export const meta = {
    name: 'estate',
    description:
        'Per-surface estate tracks over the Maghz operator - two gpt-5.6-terra recon lanes per track (codex wrappers, split charges: the estate-scope dossier and the coupling dossier, both written to scratch) then initial/critique/redteam fable passes. The T-passes stay native fable because their acceptance gates run network-bound toolchains (uv sync, uv lock) a codex sandbox cannot reach. Every pass nominates generalizable findings and reports deliberately-left residuals; a terminal doctrine lander pools both across all tracks and adjudicates the nominations into docs/laws, the constitution, the READMEs, and the reviewer rules, while the pooled residuals ride the run return untouched - estate residuals are deliberate deferrals, not a drain backlog.',
    whenToUse:
        'Full estate improvement over the admin package, the SQL/schema surfaces, and the docs/skill mirrors; passes run on fable, then a terminal doctrine lander lands generalizable findings.',
    phases: [
        {
            title: 'Recon',
            detail: 'per track: two read-only gpt-5.6-terra lanes via codex wrappers (sonnet shells) with split charges - estate-scope facts and the cross-surface coupling map - each writing its dossier to scratch; CODEX=false restores native opus lanes',
            model: 'sonnet',
        },
        { title: 'Estate' },
        {
            title: 'Doctrine',
            detail: 'one fable lander pools harvest nominations and deliberately-left residuals across every track pass, then adjudicates the nominations against the live doctrine surfaces; residuals ride the return untouched; fires only when a nomination exists',
            model: 'fable',
        },
    ],
};

// --- [CONSTANTS] -----------------------------------------------------------------------

const SCRATCH = '.claude/scratch/estate';
const STALL = 300000;
const CODEX_STALL = 1500000; // wrapper stall sits above the xhigh blocking-call ceiling (1200s): a silent live MCP call is legal waiting, never a stall
const CODEX = true; // recon lanes run on gpt-5.6-terra via the codex wrapper; false restores native opus lanes

const TRACKS = {
    python: {
        doctrine:
            'CODE DOCTRINE: read docs/stacks/python/README.md IN FULL — its routing table orders the corpus; read IN FULL the first 4 pages that table ' +
            'lists and consult the remaining pages on demand while editing. Then read docs/standards/design-doctrine.md and docs/standards/ops-doctrine.md ' +
            'IN FULL — a design finding cites the doctrine card it breaks. ',
        scope:
            'The admin/ package as one estate: all eleven owners (core, db, infra, profile, rails, remote, runtime, settings, automation, __main__, ' +
            '__init__) pushed to the docs/stacks/python bar — typed Result rails, expression-shaped dispatch, one polymorphic entry per concern, every ' +
            'admitted dependency mined to operator depth, zero hand-rolled reimplementation of shipped capability. hook/server.py hardened as the ' +
            'container-standalone stdlib consumer it is. pyproject.toml coherence: dependency rows lean and unpinned with truthful one-line comments, ' +
            'ruff/ty/mypy sections aligned with the live tree, dependency admissions on merit through the admission procedure. Never mutate the stack or ' +
            'the VPS: no maghz up/down/exec, no stage-prd invocation, no docker against live services — schema and rail truth is proven statically and ' +
            'through import-time gates.',
        gates:
            'uv lock and uv sync clean; uv run ruff check clean; uv run ruff format --check clean; uv run ty check clean; uv run mypy clean; ' +
            'uv run python -c "import admin.rails" clean (ledger projections parse at import under ErrorLevel.RAISE); prose gate zero FAILs on every ' +
            'touched .md. Zero-error law: findings fixed correctly root/ground-up — never type-ignore, suppressions, or bandaids.',
    },
    sql: {
        doctrine:
            'CODE DOCTRINE: load the coding-pg skill via the Skill tool before editing any .sql; read docs/standards/ops-doctrine.md IN FULL (its [03] ' +
            'owns the SQL surfaces) plus docs/standards/design-doctrine.md IN FULL. ',
        scope:
            'The declarative SQL estate: db/schema.sql (extension census, maghz schema, kb_english configuration, enums, tables, plain indexes), ' +
            'db/routines.sql (function, trigger, exotic-index, view, and IMMV bodies), db/cron.sql (pg_cron registration), db/init/n8n.sql, and the ' +
            'db/search/ dictionaries — every object idempotent so replay is a clean no-op, hybrid-search (BM25 + pgvector + trigram RRF) and the ' +
            'in-database embed pipeline owned by routines, never application loops. admin/profile.py catalog alignment: the [CATALOG:<tag>] sentinel ' +
            'blocks in db/schema.sql, db/cron.sql, and image/Dockerfile regenerate only through admin.profile.regenerate() — a hand edit inside a block ' +
            'is drift fixed at the catalog. NEVER create migration files, numbered scripts, or up/down pairs; NEVER run maghz schema apply or any ' +
            'mutating rail against a live database — coherence is proven statically.',
        gates:
            'sqlfluff lint db clean under the pyproject [tool.sqlfluff] law; uv run python -c "from admin.profile import regenerate; regenerate()" then ' +
            'git diff --exit-code db image proves zero generated-block drift; uv run python -c "import admin.rails" clean (ledger projections parse ' +
            'against the schema spellings); hadolint image/Dockerfile clean when touched; prose gate zero FAILs on every touched .md. Zero-error law: ' +
            'fixed root/ground-up, never suppressed.',
    },
    docs: {
        doctrine:
            'PROSE DOCTRINE: load the docgen skill via the Skill tool before any durable edit; docs/standards/style-guide.md, formatting.md, and ' +
            'information-structure.md bind all prose. ',
        scope:
            'The documentation and mirror estate: root README.md, admin/README.md, and .claude/README.md truthful against the live tree (verb tables, ' +
            'owner tables, apply mechanics); docs/.api catalogs verified against current code — stale paths, phantom members, and drifted charters fixed ' +
            'at the truthful end; docs/laws rows re-proven against the live tree per the topology charter. Skill mirrors under .claude/skills/ are ' +
            'byte-identical copies of the Parametric_Forge harness masters and the Rasm methodology masters at ~/Documents/99.Github/ — detect drift ' +
            'with diff -r, sync FROM the master only, and route a defect found in mirror content to the master tree as a reported residual; never invent ' +
            'local skill edits.',
        gates:
            'prose gate zero FAILs on every touched .md; rg proof of zero stale references to relocated or deleted files in every touched doc; every ' +
            'touched skill mirror proven byte-identical to its master via diff -r. Zero-error law: fixed root/ground-up, never suppressed.',
    },
};

// --- [INPUTS] --------------------------------------------------------------------------

const NAMES = Array.isArray(args)
    ? args
    : typeof args === 'string' && args
      ? [args]
      : Array.isArray(args?.tracks)
        ? args.tracks
        : ['python', 'sql', 'docs'];
const ACTIVE = NAMES.filter((t) => TRACKS[t]);

// --- [MODELS] ----------------------------------------------------------------------------

const DOSSIER_RECEIPT = {
    type: 'object',
    additionalProperties: false,
    required: ['ok', 'report', 'entries', 'headline', 'failure'],
    properties: {
        ok: { type: 'boolean' },
        report: { type: 'string' },
        entries: { type: 'integer' },
        headline: { type: 'string' },
        failure: { type: 'string' },
    },
};

const HARVEST = {
    type: 'array',
    items: {
        type: 'object',
        additionalProperties: false,
        required: ['altitude', 'track', 'claim', 'anchors', 'existingClause'],
        properties: {
            altitude: { type: 'string', enum: ['stacks', 'reviewer', 'constitution', 'readme', 'laws'] },
            track: { type: 'string' },
            claim: { type: 'string' },
            anchors: { type: 'array', items: { type: 'string' } },
            existingClause: { type: 'string' },
        },
    },
}; // doctrine nominations — generalizable lessons only; the terminal doctrine lander adjudicates every row

const PASS_RECEIPT = {
    type: 'object',
    additionalProperties: false,
    required: ['ok', 'headline', 'filesChanged', 'gates', 'residuals', 'harvest'],
    properties: {
        ok: { type: 'boolean' },
        headline: { type: 'string' },
        filesChanged: { type: 'integer' },
        gates: { type: 'string' },
        residuals: { type: 'array', items: { type: 'string' } },
        harvest: HARVEST,
    },
};

const DOCTRINE_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['landed', 'refined', 'rejected', 'files', 'summary'],
    properties: {
        landed: { type: 'array', items: { type: 'string' } },
        refined: { type: 'array', items: { type: 'string' } },
        rejected: {
            type: 'array',
            items: {
                type: 'object',
                additionalProperties: false,
                required: ['claim', 'reason'],
                properties: { claim: { type: 'string' }, reason: { type: 'string' } },
            },
        },
        files: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
    },
};

// --- [DOCTRINE] --------------------------------------------------------------------------

const MODEL_LAW =
    'MODEL LAW: you execute every file write and every judgment yourself. Delegate read-only reconnaissance roughly 50/50 between codex ' +
    '(Bash: codex exec -s read-only --skip-git-repo-check --ignore-user-config -m gpt-5.6-terra -c model_reasoning_effort=xhigh ' +
    '"<self-contained scoped question>" </dev/null 2>/dev/null — synchronous, ' +
    'one bounded question per leg) and opus subagents (Agent tool, model opus, explicit READ-ONLY mandate; fall back to codex if Agent is unavailable). ' +
    'Recon returns facts, locations, inventories, and verified member lists — never instructions, prescriptions, or edits; recon agents use exa/tavily, ' +
    'Context7, PyPI, and fd/rg/loc/tree, with read-only shell probes only.';

const GUARDRAILS =
    'HARD GUARDRAILS: never git commit; never run a mutating rail — no maghz up/down/exec, no schema apply, no stage-prd invocation, no docker or pulumi ' +
    'against live services; the VPS operating system belongs to the Forge flake and never changes from this repo. Durable prose follows the docgen ' +
    'register (.claude/skills/docgen/SKILL.md + references/defects.md): no weak, defensive, or process prose, no context poisoning, no tombstones. Every ' +
    'touched .md passes uv run .claude/skills/docgen/scripts/prose_gate.py with zero FAILs.';

const ADMISSION =
    'ADMISSION PROCEDURE (any new package you add): the admission lands COMPLETE in this pass — the pyproject.toml row hand-edited with its truthful ' +
    'one-line comment, the uv lock/sync gate green, a docs/.api catalog at mined operator depth when the package joins the automation substrate ' +
    '(the automation-substrate coupling row in docs/laws/topology.md), and the owning README row where a registry carries it. ' +
    'Gather the catalog facts through ONE delegated read-only ' +
    'recon agent mining verified members (installed distribution, Context7, PyPI); author the file yourself per the docgen api-catalog template. ' +
    'Surgical prose updates only — touch the rows the admission changes, nothing else.';

const REVIEWER_LAW =
    'REVIEWER-CONFIG ENRICHMENT (opportunistic, never a mandated deliverable): .greptile/rules.md + config.json + files.json and .coderabbit.yaml are the ' +
    'standing reviewer doctrine. When your pass surfaces a high-signal implicit pattern those files do not already state — a quality shape, a rail or ' +
    'schema construction law, an agent-framed prose norm, or existing guidance now wrong or weaker than the estate practices — land it there in the same ' +
    'pass: harden or correct the owning instruction where one exists, add a new one only when no owner covers it, and mirror every ruling across both ' +
    'surfaces (the rules.md section and the matching .coderabbit.yaml path_instructions block move together). Admission bar: consistent across the ' +
    'estate, doctrine-derived (docs/stacks, docs/standards, docs/laws), and invisible to the machine gates — never restate what formatters/gates ' +
    'enforce, never duplicate an existing line, never add speculative or one-off rules. yamllint proves .coderabbit.yaml, jq proves the .greptile JSON ' +
    'files, and rules.md rides the prose gate like any touched .md.';

const TOPOLOGY_LAW =
    'COUPLING PRIMACY: the cross-surface couplings are the estate CENTER, never a side item. A pass touching any docs/laws/topology.md [SURFACE] lands ' +
    'its obligated counterparts in the SAME pass — the [CATALOG:<tag>] blocks regenerate only through admin.profile.regenerate(), schema spellings ' +
    'propagate into routines and the rails projections, verb-surface changes land at the README and AGENTS readers, and a host-side counterpart ' +
    '(a Forge vpsTunnels or nixosConfigurations.maghz row) is reported as a residual naming the Forge owner, never patched here. Build intelligent, ' +
    'universal, polymorphic owners that make future capability land as one row inside the existing surface; beyond alignment, improve outright — add ' +
    'the capability the estate is missing, admitting new packages through the admission procedure whenever they raise the bar.';

const TIER_LAW = {
    T1: 'PASS T1 (INITIAL): realize the whole mandate with full write authority — implement, extend, and collapse; this is build work, not cleanup.',
    T2:
        'PASS T2 (CRITIQUE): a cold pass with FULL, EQUAL write authority. Derive your own findings from disk first; every earlier pass output is suspect ' +
        'material to attack, never a boundary or a baseline to defer to. Run the mechanical line-by-line doctrinal-conformance and capability-completeness ' +
        'audit repaired in place — collapse scan, owner choice, knob test, rails, language modernity, capability and illusion — as a floor and hunt past it; ' +
        'every hit is a fix, never a note; extend, expand, and ripple wherever you find value.',
    T3:
        'PASS T3 (REDTEAM): everything critique does AND the terminal attack — counterfactual on core owners/algebras/dispatch, diff-of-the-next-feature ' +
        '(the next verb, trigger, extension, or service lands as one row with consumers untouched or loudly broken), long-tail and failure-mode attack, ' +
        'boundary and ownership integrity, surface sprawl and phantom members, domain completeness — plus a full cold re-review of every dimension. The ' +
        'estate ends objectively denser and more capable than the prior pass left it.',
};

const LAWS_READ =
    'LAWS: read docs/laws/ IN FULL (README + topology + patterns + scars; short registry pages) — a topology row whose [SURFACE] your pass touches binds ' +
    'its obligated counterparts into the SAME pass, and every patterns row binds each surface it names. ';

const HARVEST_LAW =
    'HARVEST (required key, usually empty): nominate ONLY findings that generalize beyond this pass — a construction law reusable across the estate, a ' +
    'rail/schema pattern no doctrine clause names, a review rule that would have caught a defect BEFORE review, a cross-surface coupling discovered the ' +
    'hard way. Each row: altitude (stacks|reviewer|constitution|readme|laws), track, claim (the generalized law, one sentence), anchors (file:line ' +
    'evidence), existingClause (the exact doctrine or reviewer clause it would harden, quoted with its path — or "absent" plus the surfaces searched). A ' +
    'pass-local fix never nominates; an empty array is the normal verdict — the terminal doctrine lander refutes weak rows, so nominate substance, never volume.';

// --- [OPERATIONS] ------------------------------------------------------------------------

const dossierPath = (name, lane) => SCRATCH + '/' + name + '-recon-' + lane + '-report.md';

// Split recon charges: the two lanes never duplicate a read — scope owns the estate facts, coupling owns the cross-surface map.
const LANE_CHARGE = {
    scope:
        'Build a factual dossier of the estate scope below: file inventories with one-line states, dependency/consumer matrices from ' +
        'pyproject.toml and the lockfile, config cross-references, upstream versions where staleness is suspected (PyPI, Context7), ' +
        'and exact file:line anchors for everything notable.',
    coupling:
        'Build the COUPLING dossier for the estate scope below: map every cross-surface seam the scope touches — the [CATALOG:<tag>] sentinel blocks ' +
        'and their admin/profile.py generator, schema spellings composed by db/routines.sql and the admin/rails.py projections, verb surfaces mirrored ' +
        'in admin/README.md and AGENTS.md, docs/.api charters versus live code, and skill-mirror drift versus the Forge/Rasm master trees — each with ' +
        'exact file:line anchors on BOTH ends.',
};

const reconPrompt = (t, name, lane) =>
    'RECON lane for the ' +
    name +
    ' estate of this repo (investigate only; your sole write is the dossier file). ' +
    LANE_CHARGE[lane] +
    ' FACTS AND LOCATIONS ONLY — no verdicts, no prescriptions, no recommendations. ' +
    'First act: rm -f ' +
    dossierPath(name, lane) +
    '. Write the complete dossier to ' +
    dossierPath(name, lane) +
    ' (mkdir -p the folder), then return ' +
    'the receipt: ok, report=that path, entries=count of dossier rows, headline=mechanical tally, failure="" (or the error). ' +
    'SCOPE: ' +
    t.scope;

// Codex dispatch: the sonnet wrapper makes one blocking Codex MCP call; the recon lane itself writes its
// dossier (workspace-write, that one file) and returns the receipt as its final message — the wrapper relays
// that receipt, no product write, no relay hop. Lane law rides developer-instructions; the prompt carries only the task.
const fileTag = (label) => label.replace(/[^A-Za-z0-9_.-]+/g, '-');
const laneLaw = (schema, o) =>
    '<context_gathering>\nTerritory: the exact files and directories the task names. Do not open files outside it, ' +
    'including skill or instruction files (.claude/, CLAUDE.md, AGENTS.md).\nBudget: at most ' +
    (o.calls || 60) +
    ' tool calls total. Read in small batches (a handful of files per command, line-capped); never concatenate the whole ' +
    'territory into one command - tool output truncates and the data is lost.\nStop as soon as the product is complete. ' +
    'If something is still uncertain at the budget, proceed and record the residue in the product gap/unverified field ' +
    'instead of re-reading.\n</context_gathering>\n\n<verification>\nBefore the final message, confirm every cited ' +
    'spelling appears verbatim in the cited file; anything unconfirmed is recorded as a gap, never asserted.\n' +
    '</verification>' +
    '\n\n<output_contract>\nYour final message is a single JSON object with exactly this shape: ' +
    JSON.stringify(schema) +
    '\n- JSON only: no prose before or after it, no code fences, no markdown.\n- Every key shown is required.\n' +
    '- Use null for a value you could not determine and [] for an empty list; never guess.\n</output_contract>';
const codexRecon = (task, o) => {
    const root = '/Users/bardiasamiee/Documents/99.Github/Maghz';
    const model = o.model || 'gpt-5.6-terra';
    return [
        'DISPATCH ROLE: ' +
            model +
            ' performs the complete TASK below through one blocking Codex MCP call. Follow exactly four steps; ' +
            'never perform, edit, judge, soften, summarize, or relay the task yourself.',
        '(1) Call ToolSearch with query "select:mcp__codex__codex". If one Bash probe shows command -v forge-fleet-emit ' +
            'resolving, run forge-fleet-emit --kind codex --model ' +
            model +
            ' --label ' +
            JSON.stringify(fileTag(o.label)) +
            ' --state start now and --state stop right after step (2); when the tool is absent skip both silently.',
        '(2) Call the loaded mcp__codex__codex tool ONCE with model="' +
            model +
            '", sandbox="workspace-write" (the task writes its one dossier file), cwd=' +
            JSON.stringify(root) +
            (o.codexEffort ? ', config={"model_reasoning_effort":"' + o.codexEffort + '"}' : '') +
            ', "developer-instructions" set to the LANE LAW block below VERBATIM, and prompt set to the TASK block below ' +
            'VERBATIM. If the call errors, retry the identical call ONCE; if the retry errors, skip step (3) and return the ' +
            'error through step (4).',
        'LANE LAW:\n\n' + laneLaw(o.schema, o),
        'TASK:\n\n' + task,
        '(3) The tool result is a JSON envelope {threadId, content} whose content field holds the final-message text — the ' +
            'receipt JSON the lane earns by writing its dossier to disk. Parse that content and return it VERBATIM as your ' +
            'structured output.',
        '(4) On a second tool error return ok=false, entries=0, report and headline empty, and failure equal to the error ' + 'text VERBATIM.',
    ].join('\n\n');
};
// QUOTA FALLBACK: a codex receipt whose failure matches usage/quota/limit re-dispatches the SAME task natively at the
// role's Claude twin (terra->opus); the caller owns the re-dispatch, the sonnet wrapper never executes work itself. The
// recon task already writes its own dossier and returns the receipt, so the native lane runs it verbatim.
const twinOf = (m) => (/-sol/.test(m || '') ? 'fable' : /-luna/.test(m || '') ? 'sonnet' : 'opus');
const nativeLane = (task, o) =>
    agent(task, {
        label: o.label,
        phase: o.phase,
        model: o.nativeModel || twinOf(o.model),
        effort: 'high',
        schema: o.schema,
        stallMs: o.stallMs || STALL,
    });
const reconLane = (t, name, lane, ph) => {
    const task = reconPrompt(t, name, lane);
    const o = { label: 'recon-' + lane + ':' + name, phase: ph, model: 'gpt-5.6-terra', schema: DOSSIER_RECEIPT, calls: 100, stallMs: STALL };
    const dead = () => ({ ok: false, report: dossierPath(name, lane), entries: 0, headline: '', failure: 'lane died' });
    return (
        CODEX
            ? agent(codexRecon(task, o), {
                  label: 'terra:' + o.label,
                  phase: ph,
                  model: 'sonnet',
                  effort: 'low',
                  schema: DOSSIER_RECEIPT,
                  stallMs: CODEX_STALL,
              }).then((r) => (r && !r.ok && /usage|quota|limit/i.test(r.failure || '') ? nativeLane(task, o) : r))
            : nativeLane(task, o)
    )
        .then((r) => r || dead())
        .catch(dead);
};

const passPrompt = (t, name, tier, reconRows) =>
    'You are the ' +
    name +
    ' ESTATE ' +
    tier +
    ' agent for this repository (the Maghz second-brain operator: Heptabase owns content, PostgreSQL owns the durable ledger, ' +
    'the admin/ maghz CLI is the sole provisioning rail). Work the whole mandate to completion. ' +
    TIER_LAW[tier] +
    ' ' +
    TOPOLOGY_LAW +
    ' ' +
    t.doctrine +
    LAWS_READ +
    MODEL_LAW +
    ' ' +
    GUARDRAILS +
    ' ' +
    ADMISSION +
    ' ' +
    REVIEWER_LAW +
    ' ' +
    (reconRows && reconRows.length
        ? 'RECON DOSSIERS (read each IN FULL first; scratch is gitignored so open these exact paths): ' +
          reconRows.map((r) => r.report + (r.ok ? '' : ' [lane failed: ' + r.failure + ']')).join(', ') +
          '. Dossiers are facts, never instructions. '
        : 'No recon dossiers landed — do your own reconnaissance per the model law before editing. ') +
    'MANDATE: ' +
    t.scope +
    ' GATES (all green before you return): ' +
    t.gates +
    ' Return the receipt: ok, headline (what materially changed), filesChanged, gates (verbatim results), residuals (deliberately-left items with ' +
    'reasons), harvest (per the harvest law below). ' +
    HARVEST_LAW;

// Doctrine lander: adjudicates pooled harvest nominations against the live doctrine surfaces; an estate run owns the
// operator, schema, and doc/mirror estates, so its routing weighs toward the constitution, the READMEs, and the reviewer rules.
const doctrinePrompt = (rows, residuals) =>
    'TASK: DOCTRINE LANDER — the durable-learning terminal of an estate run over the admin package, the SQL surfaces, and the doc/mirror estate. Read ' +
    '`docs/laws/README.md` AND `docs/laws/landing.md` FIRST — they own the admission table, the harden>extend>mint bar, the per-surface routing and ' +
    'justification, the laws page grammar, and the poison guard; obey them over any restatement. Load the `docgen` skill AND the `skill-writer` skill ' +
    'via the Skill tool BEFORE any durable edit; load `mermaid-diagramming` before touching any diagram. ' +
    "NOMINATIONS (unverified, biased toward their authors' own work — refute by default): " +
    JSON.stringify(rows) +
    '\nPOOLED RESIDUALS (deliberately-left estate items with reasons — CONTEXT only, never a drain queue: a residual recurring across tracks may itself be ' +
    'a durable law worth nominating, but you never mechanically clear one here): ' +
    JSON.stringify(residuals) +
    '\nADJUDICATE each nomination per the landing bar: cold-read its target surface IN FULL, verify its anchors on CURRENT disk; LAND NOTHING is a ' +
    'first-class verdict.\n' +
    'TOPOLOGY RE-PROOF: re-verify every `docs/laws/topology.md` row whose [SURFACE] this run touched — cull a row whose coupling no longer holds, land a ' +
    'coupling this run proved.\n' +
    'GATE: run `uv run .claude/skills/docgen/scripts/prose_gate.py <every touched .md>` and repair to zero FAILs before returning; yamllint proves ' +
    '`.coderabbit.yaml` and jq proves the `.greptile` JSON files if you touch them. Return landed/refined/rejected (each rejection with its reason)/files/summary.';

// --- [COMPOSITION] -------------------------------------------------------------------------

// --- [RECON_AND_TRACKS]
const trackRows = ACTIVE.map((name) => ({ name, ...TRACKS[name] }));
log('estate tracks: ' + (ACTIVE.join(', ') || 'none (no-op)'));

const results = await pipeline(
    trackRows,
    (t) => parallel([() => reconLane(t, t.name, 'scope', 'Recon'), () => reconLane(t, t.name, 'coupling', 'Recon')]),
    (recon, t) =>
        agent(passPrompt(t, t.name, 'T1', (recon || []).filter(Boolean)), {
            model: 'fable',
            effort: 'high',
            phase: 'Estate',
            label: 't1:' + t.name,
            schema: PASS_RECEIPT,
        }).then((r) => ({ t1: r })),
    (acc, t) =>
        agent(passPrompt(t, t.name, 'T2', null), {
            model: 'fable',
            effort: 'high',
            phase: 'Estate',
            label: 't2:' + t.name,
            schema: PASS_RECEIPT,
        }).then((r) => ({
            ...acc,
            t2: r,
        })),
    (acc, t) =>
        agent(passPrompt(t, t.name, 'T3', null), {
            model: 'fable',
            effort: 'high',
            phase: 'Estate',
            label: 't3:' + t.name,
            schema: PASS_RECEIPT,
        }).then((r) => ({
            ...acc,
            t3: r,
        })),
);

// --- [DOCTRINE]
// Pool harvest nominations and deliberately-left residuals across every track pass. RULING: estate residuals are
// string-shaped DELIBERATE deferrals with reasons, not a mechanical {files, claim} backlog, and each T-pass already
// holds full write authority behind network-bound gates a fresh drain pass cannot re-run — so NO drain loop fits;
// the pooled residuals ride the run return untouched and feed the lander only as recurrence signal.
const allPasses = results.flatMap((r) => [r && r.t1, r && r.t2, r && r.t3]).filter(Boolean);
const HARVEST_ROWS = allPasses.flatMap((p) => p.harvest || []);
const RESIDUALS = allPasses.flatMap((p) => p.residuals || []);
let doctrine = null;
if (HARVEST_ROWS.length) {
    phase('Doctrine');
    doctrine = await agent(doctrinePrompt(HARVEST_ROWS, RESIDUALS), {
        label: 'doctrine',
        phase: 'Doctrine',
        model: 'fable',
        effort: 'high',
        schema: DOCTRINE_SCHEMA,
        stallMs: STALL,
    });
}
log(
    'estate doctrine: ' +
        HARVEST_ROWS.length +
        ' harvest nomination(s), ' +
        RESIDUALS.length +
        ' residual(s) pooled' +
        (doctrine ? '; ' + (doctrine.landed || []).length + ' landing(s)' : HARVEST_ROWS.length ? '; lander died' : ''),
);

return {
    tracks: Object.fromEntries(trackRows.map((t, i) => [t.name, results[i]])),
    residuals: RESIDUALS,
    doctrine: doctrine && {
        nominated: HARVEST_ROWS.length,
        landed: (doctrine.landed || []).length,
        refined: (doctrine.refined || []).length,
        rejected: (doctrine.rejected || []).length,
        files: doctrine.files || [],
        summary: doctrine.summary,
    },
    note: 'Agents never commit; the orchestrator commits once after all estate tracks close, then after the doctrine lander.',
};
