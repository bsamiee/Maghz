-- --- [RUNTIME_PRELUDE] ------------------------------------------------------------------
-- Idempotent declarative IaC for the Maghz second-brain ledger: the extension census, the
-- maghz schema, the kb_english text-search configuration, the closed enum vocabularies, the
-- tables, and the plain btree/unique indexes — the structural substrate routines.sql builds
-- its functions, triggers, exotic indexes, and views over.
--
-- Applied FIRST by `maghz schema apply`, after the two db/search/ dictionaries are docker-cp'd
-- into the container tsearch_data dir (the kb_english configuration below references them by
-- name): `psql -v ON_ERROR_STOP=1 -f db/schema.sql`, then db/routines.sql, then db/cron.sql.
-- The order is load-bearing: schema.sql creates vector/citext/pgcrypto and the kb_english
-- config that routines.sql binds its tables, triggers, and exotic indexes to.
--
-- Every statement is guarded for replay: CREATE EXTENSION IF NOT EXISTS; enum types and the
-- text-search objects under DO-block catalog probes (no IF NOT EXISTS form); tables and
-- indexes IF NOT EXISTS. A fresh-DB run creates everything; a replay is a clean no-op with
-- zero errors.

-- --- [EXTENSIONS] -----------------------------------------------------------------------
-- The full curated profile carried by the maghz-pg image. CASCADE resolves dependencies.
-- ParadeDB base ships pg_search + vector + pg_ivm + contrib; the rest are layered. pg_cron
-- is NOT created here: it can live only in the `postgres` maintenance DB (the image creates
-- it there at init), so this maghz-targeted file never references the cron schema; the job
-- registration lives in cron.sql, which runs against postgres and reaches maghz via
-- cron.schedule_in_database.

-- [CATALOG:extensions] -- generated from admin/profile.py `schema_prelude()` (target_db == maghz).
-- Edit the `_PROFILE` catalog and regenerate; do not hand-edit this block. The schema `doctor` verb
-- asserts the live pg_extension census equals this declared set (census_diff).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS pg_ivm;
CREATE EXTENSION IF NOT EXISTS pg_net;
CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_jsonschema;
CREATE EXTENSION IF NOT EXISTS hll;
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS hypopg;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS tablefunc;
-- [/CATALOG:extensions]

CREATE SCHEMA IF NOT EXISTS maghz;

-- --- [TEXT_SEARCH] ----------------------------------------------------------------------
-- kb_english text-search configuration: thesaurus (multi-word concept collapse) and synonym
-- dictionary (single-token acronym/variant unification) fire BEFORE the snowball stemmer, so
-- a concept indexed under different terminology resolves to one canonical lexeme. The .syn
-- and .ths files install to $SHAREDIR/tsearch_data/ (docker-cp'd by `maghz schema apply`
-- before this file runs); a missing file fails dictionary creation. CREATE ... guarded by a
-- DO block since text-search dictionaries/configs have no IF NOT EXISTS form.
--
-- Chain ORDER is load-bearing: the thesaurus must precede the synonym dict. A dictionary
-- list is first-match-wins — once a dict returns a result for a token, later dicts never see
-- it. A single-token synonym (similarity -> similar) that rewrites an interior word of a
-- thesaurus phrase (vector similarity search) would consume that token before the thesaurus
-- could complete the phrase. Thesaurus-first lets whole phrases collapse to one lexeme; the
-- tokens of unmatched phrases fall through (NULL) to the synonym dict, then to english_stem.

DO $bootstrap$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_dict WHERE dictname = 'maghz_synonym') THEN
        CREATE TEXT SEARCH DICTIONARY maghz_synonym (
            TEMPLATE  = synonym,
            SYNONYMS  = maghz_synonyms,
            CaseSensitive = false
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_ts_dict WHERE dictname = 'maghz_thesaurus') THEN
        CREATE TEXT SEARCH DICTIONARY maghz_thesaurus (
            TEMPLATE   = thesaurus,
            DictFile   = maghz_thesaurus,
            Dictionary = english_stem
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config c JOIN pg_namespace n ON n.oid = c.cfgnamespace
        WHERE c.cfgname = 'kb_english' AND n.nspname = 'public'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION public.kb_english (COPY = pg_catalog.english);
        -- Chain per token kind: unaccent -> thesaurus -> synonym -> snowball stemmer.
        ALTER TEXT SEARCH CONFIGURATION public.kb_english
            ALTER MAPPING FOR asciiword, asciihword, hword_asciipart,
                              word, hword, hword_part
            WITH unaccent, maghz_thesaurus, maghz_synonym, english_stem;
    END IF;
END
$bootstrap$;

-- --- [TYPES] ----------------------------------------------------------------------------
-- Closed vocabularies anchored as native enums, not inline CHECK literals. PostgreSQL has
-- no IF NOT EXISTS form for CREATE TYPE, so each is guarded by a DO-block catalog probe.
-- Evolving a vocabulary is an additive ALTER TYPE ... ADD VALUE; no guard is needed there.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evidence_kind') THEN
        CREATE TYPE evidence_kind AS ENUM (
            'paper', 'book', 'article', 'dataset', 'code', 'web', 'note'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'drift_status') THEN
        CREATE TYPE drift_status AS ENUM (
            'synced', 'drifted', 'orphaned', 'pending'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM (
            'running', 'failed', 'stale', 'awaiting_review', 'done'
        );
    END IF;
END $$;

-- --- [MODELS] ---------------------------------------------------------------------------

-- Knowledge domains — the coverage / centrality unit. parent_id self-FK forms the domain
-- tree; centrality and coverage are computed by routine-owned views over concept counts.
CREATE TABLE IF NOT EXISTS domain (
    id          uuid        NOT NULL DEFAULT uuidv7(),
    name        citext      NOT NULL,
    slug        citext      NOT NULL,
    parent_id   uuid,
    description text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at  timestamptz NOT NULL DEFAULT current_timestamp,
    CONSTRAINT domain_pkey PRIMARY KEY (id),
    CONSTRAINT domain_name_key UNIQUE (name),
    CONSTRAINT domain_slug_key UNIQUE (slug),
    CONSTRAINT domain_parent_fkey FOREIGN KEY (parent_id)
        REFERENCES domain (id) ON DELETE SET NULL,
    CONSTRAINT domain_no_self_parent CHECK (parent_id IS DISTINCT FROM id)
);

-- Canonical concept. canonical_name is the dedup key (citext UNIQUE — case-insensitive
-- terminology collision detection). embedding is nullable until the in-DB pg_net -> Ollama
-- sweep populates it; embedded_at gates the embed enqueue (NULL embedding OR stale hash).
-- fts and content_hash are maintained by routine-owned triggers (to_tsvector over the
-- routine-owned kb_english config, pgcrypto digest).
CREATE TABLE IF NOT EXISTS concept (
    id             uuid         NOT NULL DEFAULT uuidv7(),
    domain_id      uuid         NOT NULL,
    canonical_name citext       NOT NULL,
    title          text         NOT NULL,
    body           text         NOT NULL DEFAULT '',
    tags           text[]       NOT NULL DEFAULT '{}',
    embedding      vector(768),
    fts            tsvector,
    content_hash   bytea,
    embedded_at    timestamptz,
    created_at     timestamptz  NOT NULL DEFAULT current_timestamp,
    updated_at     timestamptz  NOT NULL DEFAULT current_timestamp,
    CONSTRAINT concept_pkey PRIMARY KEY (id),
    CONSTRAINT concept_canonical_name_key UNIQUE (canonical_name),
    CONSTRAINT concept_domain_fkey FOREIGN KEY (domain_id)
        REFERENCES domain (id) ON DELETE RESTRICT,
    CONSTRAINT concept_title_nonempty CHECK (length(btrim(title)) > 0)
);

-- Authoritative sources backing a concept. A concept with zero evidence rows is the
-- "claim lacks authoritative evidence" ledger signal (routine-owned view). kind is the
-- evidence_kind enum (closed source taxonomy); uri is the canonical source locator.
CREATE TABLE IF NOT EXISTS evidence (
    id          uuid          NOT NULL DEFAULT uuidv7(),
    concept_id  uuid          NOT NULL,
    kind        evidence_kind NOT NULL,
    uri         text          NOT NULL,
    title       text          NOT NULL DEFAULT '',
    excerpt     text          NOT NULL DEFAULT '',
    captured_at timestamptz   NOT NULL DEFAULT current_timestamp,
    CONSTRAINT evidence_pkey PRIMARY KEY (id),
    CONSTRAINT evidence_concept_fkey FOREIGN KEY (concept_id)
        REFERENCES concept (id) ON DELETE CASCADE,
    CONSTRAINT evidence_uri_per_concept_key UNIQUE (concept_id, uri)
);

-- Heptabase card mapping. content_md5 is the card's last-synced content fingerprint;
-- drift_status flags whether the card still matches canonical concept content. A card
-- in 'drifted' is the "Heptabase card no longer matches canonical content" ledger signal.
CREATE TABLE IF NOT EXISTS card (
    id           uuid         NOT NULL DEFAULT uuidv7(),
    card_id      text         NOT NULL,
    concept_id   uuid         NOT NULL,
    content_md5  text         NOT NULL,
    drift_status drift_status NOT NULL DEFAULT 'synced',
    synced_at    timestamptz  NOT NULL DEFAULT current_timestamp,
    CONSTRAINT card_pkey PRIMARY KEY (id),
    CONSTRAINT card_card_id_key UNIQUE (card_id),
    CONSTRAINT card_concept_fkey FOREIGN KEY (concept_id)
        REFERENCES concept (id) ON DELETE CASCADE
);

-- Registered automated workers. last_seen_at drives the stale-worker sweep; capabilities
-- is the worker's declared task-kind set. A worker is the owner of a job (job.worker_id).
CREATE TABLE IF NOT EXISTS worker (
    id           uuid        NOT NULL DEFAULT uuidv7(),
    name         citext      NOT NULL,
    kind         text        NOT NULL,
    capabilities text[]      NOT NULL DEFAULT '{}',
    last_seen_at timestamptz NOT NULL DEFAULT current_timestamp,
    created_at   timestamptz NOT NULL DEFAULT current_timestamp,
    CONSTRAINT worker_pkey PRIMARY KEY (id),
    CONSTRAINT worker_name_key UNIQUE (name)
);

-- Research jobs — the running / failed / stale / awaiting-review receipt. status is a
-- closed CHECK vocabulary answering "which research jobs are running/failed/stale/awaiting".
-- The actual work payload is also enqueued on a pgmq queue (routine-owned); this table is
-- the durable receipt joined to that queue by msg_id. worker_id answers "which worker owns
-- which task". concept_id is the target concept (nullable for discovery jobs that have no
-- concept yet). attempt + heartbeat_at drive the staleness sweep.
CREATE TABLE IF NOT EXISTS job (
    id           uuid        NOT NULL DEFAULT uuidv7(),
    worker_id    uuid,
    concept_id   uuid,
    msg_id       bigint,
    status       job_status  NOT NULL DEFAULT 'running',
    attempt      integer     NOT NULL DEFAULT 0,
    payload      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    result       jsonb,
    error        text,
    heartbeat_at timestamptz NOT NULL DEFAULT current_timestamp,
    created_at   timestamptz NOT NULL DEFAULT current_timestamp,
    updated_at   timestamptz NOT NULL DEFAULT current_timestamp,
    CONSTRAINT job_pkey PRIMARY KEY (id),
    CONSTRAINT job_worker_fkey FOREIGN KEY (worker_id)
        REFERENCES worker (id) ON DELETE SET NULL,
    CONSTRAINT job_concept_fkey FOREIGN KEY (concept_id)
        REFERENCES concept (id) ON DELETE CASCADE,
    CONSTRAINT job_attempt_nonneg CHECK (attempt >= 0)
);

-- --- [INDEXES] --------------------------------------------------------------------------
-- Plain btree / unique indexes ONLY. Exotic indexes (bm25 / hnsw / gin / gin_trgm_ops)
-- are routine-owned with the mz_ prefix. UNIQUE constraints above already create their
-- backing indexes; these cover the FK and ledger-predicate hot paths.

CREATE INDEX IF NOT EXISTS domain_parent_id_idx ON domain (parent_id);

CREATE INDEX IF NOT EXISTS concept_domain_id_idx ON concept (domain_id);
-- Embed-sweep selector: concepts needing (re)embedding — no embedding, or content moved on.
CREATE INDEX IF NOT EXISTS concept_embed_pending_idx ON concept (updated_at)
    WHERE embedding IS NULL OR embedded_at IS NULL OR embedded_at < updated_at;

CREATE INDEX IF NOT EXISTS evidence_concept_id_idx ON evidence (concept_id);

CREATE INDEX IF NOT EXISTS card_concept_id_idx ON card (concept_id);
-- Drift ledger selector: cards no longer matching canonical content.
CREATE INDEX IF NOT EXISTS card_drifted_idx ON card (concept_id) WHERE drift_status <> 'synced';

CREATE INDEX IF NOT EXISTS worker_last_seen_at_idx ON worker (last_seen_at);

CREATE INDEX IF NOT EXISTS job_worker_id_idx ON job (worker_id);
CREATE INDEX IF NOT EXISTS job_concept_id_idx ON job (concept_id);
-- Job ledger selector: open jobs by status (running / failed / stale / awaiting_review).
CREATE INDEX IF NOT EXISTS job_open_status_idx ON job (status, heartbeat_at) WHERE status <> 'done';
