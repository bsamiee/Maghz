-- --- [RUNTIME_PRELUDE] ------------------------------------------------------------------
-- Routine-owned, function/view/trigger/exotic-index layer for the Maghz ledger.
--
-- Applied second by `maghz schema apply` (after schema.sql creates all tables). Every
-- statement is CREATE ... IF NOT EXISTS or CREATE OR REPLACE so a replay is a clean
-- no-op. Ordering is load-bearing: extensions, then the text-search configuration, then
-- triggers, then exotic indexes, then the pgmq queue and embed pipeline, then the hybrid
-- search function and views.
--
-- Verified external surfaces this file binds:
--   pg_net  : net.http_post(url,body jsonb,params jsonb,headers jsonb,timeout_milliseconds int)
--             -> bigint request_id; the response lands LATER in net._http_response
--             (columns id,status_code,content_type,headers,content text,timed_out,
--             error_msg,created); response.id == request_id; content is text -> ::jsonb.
--             Two cron ticks: enqueue (returns ids) then drain (reads net._http_response).
--   Ollama  : POST http://ollama:11434/api/embed  body {"model","input"} ; response
--             {"embeddings":[[...768 floats...]]} — embeddings is array-of-arrays, the
--             single vector is at ->'embeddings'->0. nomic-embed-text is 768-dim and needs
--             the "search_document: " task prefix prepended to indexed text.

-- --- [EXTENSIONS] -----------------------------------------------------------------------
-- The full curated profile carried by the maghz-pg image. CASCADE resolves dependencies.
-- ParadeDB base ships pg_search + vector + pg_ivm + contrib; the rest are layered. pg_cron
-- is NOT created here: it can live only in the `postgres` maintenance DB (the image creates
-- it there at init), so this maghz-targeted file never references the cron schema; the job
-- registration lives in cron.sql, which runs against postgres and reaches maghz via
-- cron.schedule_in_database.

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

CREATE SCHEMA IF NOT EXISTS maghz;

-- --- [TYPES] ----------------------------------------------------------------------------
-- kb_english text-search configuration: thesaurus (multi-word concept collapse) and synonym
-- dictionary (single-token acronym/variant unification) fire BEFORE the snowball stemmer, so
-- a concept indexed under different terminology resolves to one canonical lexeme. The .syn
-- and .ths files install to $SHAREDIR/tsearch_data/ (placed by the image / a bootstrap
-- step); a missing file fails dictionary creation. CREATE ... guarded by a DO block since
-- text-search dictionaries/configs have no IF NOT EXISTS form.
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

-- --- [OPERATIONS] -----------------------------------------------------------------------

-- [FTS_AND_HASH] -------------------------------------------------------------------------
-- Maintain concept.fts and concept.content_hash on write. fts weights title (A) over body
-- (B) over tags (C) so BM25-adjacent native ranking and the gin(fts) path agree on signal.
-- content_hash is the pgcrypto sha256 digest of the embed-relevant text; the embed sweep
-- compares it to detect when a concept's content moved and an embedding is stale.
CREATE OR REPLACE FUNCTION maghz.concept_maintain()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.fts :=
        setweight(to_tsvector('public.kb_english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('public.kb_english', coalesce(NEW.body, '')),  'B') ||
        setweight(to_tsvector('public.kb_english', array_to_string(NEW.tags, ' ')), 'C');

    NEW.content_hash := digest(
        coalesce(NEW.title, '') || E'\n' || coalesce(NEW.body, '') || E'\n'
            || array_to_string(NEW.tags, ' '),
        'sha256'
    );

    -- Touch updated_at so the embed-pending partial index re-selects on content change;
    -- if the hash is unchanged the embedding is NOT stale and embedded_at stays valid.
    IF TG_OP = 'UPDATE' AND NEW.content_hash IS DISTINCT FROM OLD.content_hash THEN
        NEW.updated_at := now();
    END IF;

    RETURN NEW;
END
$$;

CREATE OR REPLACE TRIGGER concept_maintain_trg
    BEFORE INSERT OR UPDATE OF title, body, tags ON concept
    FOR EACH ROW EXECUTE FUNCTION maghz.concept_maintain();

-- [EMBED_PIPELINE] -----------------------------------------------------------------------
-- pg_net is async: http_post returns a request id and the response lands LATER in
-- net._http_response. So embedding is two cron steps. The outbound receipt joins a posted
-- request id to its target concept and the content_hash captured at enqueue time, so the
-- drain only writes the embedding back if the concept has not moved since.

CREATE TABLE IF NOT EXISTS maghz.embed_request (
    request_id   bigint      PRIMARY KEY,
    concept_id   uuid        NOT NULL REFERENCES concept (id) ON DELETE CASCADE,
    content_hash bytea       NOT NULL,
    enqueued_at  timestamptz NOT NULL DEFAULT current_timestamp,
    drained_at   timestamptz
);

-- Fail-fast lock bound: a live-DB replay over a populated embed_request still acquires the
-- ShareLock; CONCURRENTLY is illegal in the script transaction, so bound the wait instead.
SET lock_timeout = '3s';
CREATE INDEX IF NOT EXISTS mz_embed_request_pending_idx
    ON maghz.embed_request (enqueued_at) WHERE drained_at IS NULL;
RESET lock_timeout;

-- Step 1 — ENQUEUE. Select concepts needing (re)embedding, POST each to Ollama, and record
-- the returned request id. The "search_document: " task prefix is prepended because the
-- Ollama HTTP API passes input verbatim and nomic-embed-text is trained on prefixed text.
-- A partial-unique guard via embed_request prevents double-posting a concept already in
-- flight this tick. Bounded by _batch to cap pg_net request fan-out per run.
CREATE OR REPLACE FUNCTION maghz.embed_enqueue(_batch integer DEFAULT 32)
RETURNS integer
LANGUAGE sql
AS $$
    WITH pending AS (
        SELECT c.id, c.content_hash,
               'search_document: ' || c.title ||
               CASE WHEN c.body <> '' THEN E'\n' || c.body ELSE '' END AS doc
        FROM concept c
        WHERE (c.embedding IS NULL
               OR c.embedded_at IS NULL
               OR c.embedded_at < c.updated_at)
          AND NOT EXISTS (
              SELECT 1 FROM maghz.embed_request r
              WHERE r.concept_id = c.id AND r.drained_at IS NULL
          )
        ORDER BY c.updated_at
        LIMIT _batch
    ),
    posted AS (
        SELECT p.id AS concept_id,
               p.content_hash,
               net.http_post(
                   url     => 'http://ollama:11434/api/embed',
                   body    => jsonb_build_object('model', 'nomic-embed-text',
                                                 'input', p.doc),
                   headers => '{"Content-Type": "application/json"}'::jsonb,
                   timeout_milliseconds => 20000
               ) AS request_id
        FROM pending p
    ),
    receipt AS (
        INSERT INTO maghz.embed_request (request_id, concept_id, content_hash)
        SELECT request_id, concept_id, content_hash FROM posted
        RETURNING request_id
    )
    SELECT count(*)::integer FROM receipt;
$$;

-- Step 2 — DRAIN, on a LATER tick (a request cannot read its own response in-txn). Join the
-- receipt to net._http_response on request_id, parse content::jsonb, and write embeddings[0]
-- back as vector(768) — but ONLY if the concept's content_hash still matches what was posted
-- (else the concept moved and this embedding is already stale; skip and let re-enqueue fire).
--
-- Liveness: pg_net reaps net._http_response after pg_net.ttl (default 6h). A receipt whose
-- response was reaped before any drain ran would never join `ready`, never close, and then
-- permanently block re-enqueue (the enqueue guard rejects a concept with a live drained_at IS
-- NULL receipt). The `expired` branch closes such receipts past a TTL-aligned horizon so the
-- concept re-enqueues on the next tick. The cron drain runs every minute, far inside the 6h
-- TTL, so the join path is the steady state and `expired` only fires after an outage.
CREATE OR REPLACE FUNCTION maghz.embed_drain(_ttl interval DEFAULT '6 hours')
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    _written integer;
BEGIN
    WITH ready AS (
        SELECT r.request_id, r.concept_id, r.content_hash,
               (resp.content::jsonb -> 'embeddings' -> 0) AS emb,
               resp.status_code, resp.timed_out
        FROM maghz.embed_request r
        JOIN net._http_response resp ON resp.id = r.request_id
        WHERE r.drained_at IS NULL
    ),
    applied AS (
        UPDATE concept c
        SET embedding   = (SELECT array_agg((e.v)::real)::vector(768)
                           FROM jsonb_array_elements_text(ready.emb) AS e(v)),
            embedded_at = now()
        FROM ready
        WHERE c.id = ready.concept_id
          AND c.content_hash = ready.content_hash
          AND ready.status_code = 200
          AND ready.timed_out IS NOT TRUE
          AND ready.emb IS NOT NULL
        RETURNING c.id
    ),
    closed AS (
        UPDATE maghz.embed_request r
        SET drained_at = now()
        FROM ready
        WHERE r.request_id = ready.request_id
        RETURNING r.request_id
    ),
    expired AS (
        UPDATE maghz.embed_request r
        SET drained_at = now()
        WHERE r.drained_at IS NULL
          AND r.enqueued_at < now() - _ttl
          AND NOT EXISTS (SELECT 1 FROM net._http_response resp
                          WHERE resp.id = r.request_id)
        RETURNING r.request_id
    )
    SELECT count(*) INTO _written FROM applied;
    RETURN _written;
END
$$;

-- [JOB_QUEUE] ----------------------------------------------------------------------------
-- pgmq owns the durable work queue; the job table (schema.sql) is the receipt. Creation is
-- idempotent via the catalog guard since pgmq.create raises on a pre-existing queue.
DO $q$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pgmq.list_queues() WHERE queue_name = 'research') THEN
        PERFORM pgmq.create('research');
    END IF;
END
$q$;

-- Staleness sweep: a running job whose owning worker stopped heart-beating, or whose own
-- heartbeat aged out, is reclassified 'stale' so the ledger surfaces it for re-dispatch.
CREATE OR REPLACE FUNCTION maghz.jobs_mark_stale(_max_silence interval DEFAULT '15 minutes')
RETURNS integer
LANGUAGE sql
AS $$
    WITH staled AS (
        UPDATE job j
        SET status = 'stale', updated_at = now()
        WHERE j.status = 'running'
          AND (j.heartbeat_at < now() - _max_silence
               OR EXISTS (SELECT 1 FROM worker w
                          WHERE w.id = j.worker_id
                            AND w.last_seen_at < now() - _max_silence))
        RETURNING j.id
    )
    SELECT count(*)::integer FROM staled;
$$;

-- --- [INDEXES] --------------------------------------------------------------------------
-- EXOTIC indexes — routine-owned, mz_ prefix, excluded from Atlas. The hybrid retrieval
-- triad: pg_search BM25 (lexical), pgvector HNSW cosine (dense semantic), and the native
-- gin(fts) + gin_trgm_ops paths (fuzzy / terminology dedup).
--
-- These build over the populated concept table and CANNOT use the CONCURRENTLY form: the
-- routines replay runs as one multi-statement script and CONCURRENTLY is illegal inside a
-- transaction block. A non-concurrent build holds a ShareLock (blocks writers) for its
-- duration. lock_timeout bounds the ShareLock ACQUISITION wait so a build behind a long
-- writer fails fast instead of stalling the replay; on a fresh DB the table is empty and the
-- builds are instant, so the bound is a guard, not a constraint. Each build is IF NOT
-- EXISTS: a name that already exists is a catalog no-op that never takes the heavy lock, so
-- replay against a live DB does not re-block writers. lock_timeout is a session GUC, reset
-- after the populated-table builds.
SET lock_timeout = '3s';

-- BM25 lexical index. key_field is the PK; title carries positions for phrase queries, body
-- is stemmed. paradedb.score(id) ranks against the @@@ operator.
CREATE INDEX IF NOT EXISTS mz_concept_bm25 ON concept
USING bm25 (id, title, body, canonical_name, tags)
WITH (
    key_field = 'id',
    text_fields = '{
        "title":          {"tokenizer": {"type": "default", "stemmer": "English"}, "record": "position"},
        "body":           {"tokenizer": {"type": "default", "stemmer": "English"}, "record": "position"},
        "canonical_name": {"tokenizer": {"type": "raw"}}
    }'
);

-- Dense semantic index. Cosine ops match the maghz.search() <=> distance and the RRF
-- semantic rank. Built over the nullable embedding column; rows pending embedding are
-- simply not yet indexed.
CREATE INDEX IF NOT EXISTS mz_concept_embedding_hnsw ON concept
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200);

-- Native FTS path (boolean / weighted @@ matching, complementary to BM25 ranking) and the
-- fuzzy terminology-dedup trigram paths over the dedup keys.
CREATE INDEX IF NOT EXISTS mz_concept_fts_gin ON concept USING gin (fts);
CREATE INDEX IF NOT EXISTS mz_concept_canonical_trgm
    ON concept USING gin (canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS mz_concept_title_trgm
    ON concept USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS mz_concept_tags_gin ON concept USING gin (tags);

RESET lock_timeout;

-- --- [SERVICES] -------------------------------------------------------------------------

-- [HYBRID_SEARCH] ------------------------------------------------------------------------
-- One polymorphic retrieval entry point fusing three rankers with Reciprocal Rank Fusion.
-- RRF operates on RANKS ONLY (BM25 scores and cosine distances are incomparable scales):
-- rrf = Σ w_i / (k + rank_i), k = 60. query_vec may be NULL (lexical+fuzzy only) so callers
-- can search before computing a query embedding; pass the "search_query: " task prefix into
-- query_text upstream when embedding the query. Each ranker is capped at _pool candidates.
CREATE OR REPLACE FUNCTION maghz.search(
    query_text text,
    query_vec  vector(768) DEFAULT NULL,
    _limit     integer     DEFAULT 20,
    _pool      integer     DEFAULT 100,
    _k         integer     DEFAULT 60,
    _w_lex     real        DEFAULT 1.0,
    _w_sem     real        DEFAULT 1.0,
    _w_fuzz    real        DEFAULT 0.5
)
RETURNS TABLE (
    concept_id     uuid,
    canonical_name citext,
    title          text,
    rrf_score      double precision,
    rank_lexical   integer,
    rank_semantic  integer,
    rank_fuzzy     integer
)
LANGUAGE sql
STABLE
AS $$
    WITH lexical AS (
        SELECT c.id, row_number() OVER (ORDER BY paradedb.score(c.id) DESC, c.id)::int AS r
        FROM concept c
        WHERE c.id @@@ paradedb.parse(query_text)
        ORDER BY paradedb.score(c.id) DESC, c.id
        LIMIT _pool
    ),
    semantic AS (
        SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> query_vec, c.id)::int AS r
        FROM concept c
        WHERE query_vec IS NOT NULL AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> query_vec, c.id
        LIMIT _pool
    ),
    fuzzy AS (
        SELECT c.id,
               row_number() OVER (
                   ORDER BY greatest(word_similarity(query_text, c.canonical_name::text),
                                     word_similarity(query_text, c.title)) DESC, c.id
               )::int AS r
        FROM concept c
        WHERE query_text <% c.canonical_name::text OR query_text <% c.title
        ORDER BY greatest(word_similarity(query_text, c.canonical_name::text),
                          word_similarity(query_text, c.title)) DESC, c.id
        LIMIT _pool
    ),
    fused AS (
        SELECT coalesce(l.id, s.id, f.id) AS id,
               coalesce(_w_lex  / (_k + l.r), 0.0) +
               coalesce(_w_sem  / (_k + s.r), 0.0) +
               coalesce(_w_fuzz / (_k + f.r), 0.0) AS rrf,
               l.r AS rl, s.r AS rs, f.r AS rf
        FROM lexical l
        FULL OUTER JOIN semantic s ON s.id = l.id
        FULL OUTER JOIN fuzzy    f ON f.id = coalesce(l.id, s.id)
    )
    SELECT fu.id, c.canonical_name, c.title, fu.rrf, fu.rl, fu.rs, fu.rf
    FROM fused fu
    JOIN concept c ON c.id = fu.id
    ORDER BY fu.rrf DESC, fu.id
    LIMIT _limit;
$$;

-- --- [COMPOSITION] ----------------------------------------------------------------------

-- [INCREMENTAL_VIEW] ---------------------------------------------------------------------
-- The per-domain concept tally is an incrementally-maintained materialized view (pg_ivm):
-- AFTER-triggers on concept keep it current on every write, so it is O(delta) hot at read
-- time with no cron refresh. pg_ivm forbids aggregates over OUTER JOIN and forbids FILTER,
-- so the IMMV is the inner-join count core only; the LEFT-JOIN / evidence-gap / centrality
-- enrichment composes on top of it in the plain coverage view below. Guarded for replay.
DO $immv$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class r JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE r.relname = 'concept_tally' AND n.nspname = 'maghz'
    ) THEN
        PERFORM pgivm.create_immv('maghz.concept_tally', $immv_q$
            SELECT c.domain_id,
                   count(*)          AS concept_count,
                   count(c.embedding) AS embedded_count
            FROM concept c
            GROUP BY c.domain_id
        $immv_q$);
    END IF;
END
$immv$;

-- [LEDGER_VIEWS] -------------------------------------------------------------------------
-- The ledger questions, as queryable views in the maghz schema. Real-time (not
-- materialized) so coverage / evidence-gap / drift signals are never stale; the count core
-- reads from the IMMV maghz.concept_tally.

-- Coverage + centrality: which domains are underdeveloped. concept_count is coverage (from
-- the IMMV); child_domains is structural centrality across the domain tree; embedded_ratio
-- flags domains whose concepts are not yet semantically indexed; unsupported_count is the
-- evidence gap. A domain with zero concepts has no tally row -> coalesce to 0.
CREATE OR REPLACE VIEW maghz.domain_coverage AS
SELECT d.id AS domain_id,
       d.name,
       d.slug,
       d.parent_id,
       coalesce(t.concept_count, 0)                            AS concept_count,
       coalesce(t.embedded_count, 0)                           AS embedded_count,
       round(coalesce(t.embedded_count, 0)::numeric
             / nullif(t.concept_count, 0), 3)                  AS embedded_ratio,
       (SELECT count(*) FROM concept c
        WHERE c.domain_id = d.id
          AND NOT EXISTS (SELECT 1 FROM evidence e
                          WHERE e.concept_id = c.id))          AS unsupported_count,
       (SELECT count(*) FROM domain ch WHERE ch.parent_id = d.id) AS child_domains
FROM domain d
LEFT JOIN maghz.concept_tally t ON t.domain_id = d.id;

-- Claims lacking authoritative evidence: concepts with zero evidence rows.
CREATE OR REPLACE VIEW maghz.unsupported_concept AS
SELECT c.id AS concept_id, c.canonical_name, c.title, c.domain_id, c.updated_at
FROM concept c
WHERE NOT EXISTS (SELECT 1 FROM evidence e WHERE e.concept_id = c.id);

-- Duplicate concepts under different terminology: trigram-similar canonical_name pairs
-- below the unique key but above the similarity floor. Ordered pair (a<b) avoids mirror rows.
CREATE OR REPLACE VIEW maghz.concept_dedup_candidate AS
SELECT a.id AS concept_a, b.id AS concept_b,
       a.canonical_name AS name_a, b.canonical_name AS name_b,
       similarity(a.canonical_name::text, b.canonical_name::text) AS name_sim
FROM concept a
JOIN concept b
  ON a.id < b.id
 AND a.canonical_name::text % b.canonical_name::text
WHERE similarity(a.canonical_name::text, b.canonical_name::text) >= 0.5;

-- Drifted Heptabase cards: cards whose mapping no longer matches canonical content.
CREATE OR REPLACE VIEW maghz.card_drift AS
SELECT cd.id AS card_pk, cd.card_id, cd.concept_id, cd.drift_status, cd.synced_at,
       c.canonical_name, c.updated_at AS concept_updated_at
FROM card cd
JOIN concept c ON c.id = cd.concept_id
WHERE cd.drift_status <> 'synced';

-- Job ledger: which jobs are running / failed / stale / awaiting-review and who owns them.
CREATE OR REPLACE VIEW maghz.job_ledger AS
SELECT j.id AS job_id, j.status, j.attempt, j.concept_id, j.worker_id,
       w.name AS worker_name, j.heartbeat_at, j.updated_at, j.error
FROM job j
LEFT JOIN worker w ON w.id = j.worker_id
WHERE j.status <> 'done';

-- Research queue: what to research next — domains ranked by under-development. Surfaces the
-- lowest-coverage, evidence-thin, leaf-heavy domains first.
CREATE OR REPLACE VIEW maghz.research_priority AS
SELECT dc.domain_id, dc.name, dc.concept_count, dc.unsupported_count,
       dc.embedded_ratio, dc.child_domains,
       (dc.unsupported_count * 2 + (10 - least(dc.concept_count, 10))) AS priority_score
FROM maghz.domain_coverage dc
ORDER BY priority_score DESC;
