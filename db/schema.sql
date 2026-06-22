-- --- [RUNTIME_PRELUDE] ------------------------------------------------------------------
-- Idempotent declarative IaC for the Maghz second-brain ledger (public schema only).
--
-- Applied via `psql -v ON_ERROR_STOP=1 -f db/schema.sql` immediately after routines.sql
-- loads extensions (vector, citext). Every statement is guarded for replay: tables and
-- indexes use IF NOT EXISTS; enum types use DO-block catalog guards (no IF NOT EXISTS form
-- in PostgreSQL). A fresh-DB run creates everything; a replay is a clean no-op with zero
-- errors. Same tables, columns, types, constraints, indexes — only the DDL form changed.
--
-- Load-ordering dependency: routines.sql must run first (or be co-applied in the same
-- session) to ensure vector, citext, and pgcrypto extensions exist before this file
-- references those types. The `maghz schema apply` rail enforces this order: psql
-- schema.sql runs AFTER psql routines.sql (which loads all extensions via CREATE
-- EXTENSION IF NOT EXISTS).

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
