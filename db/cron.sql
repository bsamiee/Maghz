-- --- [RUNTIME_PRELUDE] ------------------------------------------------------------------
-- Maghz pg_cron job registration. This file runs against the `postgres` maintenance DB —
-- the ONLY database pg_cron may inhabit (the ParadeDB image creates it there at init and the
-- container runs with cron.database_name=postgres). The cron schema, the cron.job catalog,
-- and cron.schedule* all live here; the jobs themselves execute IN maghz via
-- cron.schedule_in_database(..., 'maghz'). The maghz CLI applies this immediately after
-- routines.sql, so the scheduled function bodies (maghz.embed_enqueue / embed_drain /
-- jobs_mark_stale) already exist in maghz when a job first fires.
--
-- Each invocation is its own transaction (no session state) and at most one run per job is
-- concurrent. The embed two-step shares the minute tick: enqueue posts and the pg_net
-- background worker fulfils after that txn commits, so the same-minute drain reads the PRIOR
-- tick's now-landed net._http_response rows — the one-tick lag is the async correctness, not
-- a defect. The IMMV maghz.concept_tally needs no refresh job (pg_ivm AFTER-triggers keep it
-- current on write). unschedule-then-(re)schedule makes replay idempotent with the current
-- command body.

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- --- [COMPOSITION] ----------------------------------------------------------------------
DO $cron$
DECLARE
    spec record;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('maghz_embed_enqueue', '* * * * *',   $job$ SELECT maghz.embed_enqueue(); $job$),
            ('maghz_embed_drain',   '* * * * *',   $job$ SELECT maghz.embed_drain();   $job$),
            ('maghz_jobs_stale',    '*/5 * * * *', $job$ SELECT maghz.jobs_mark_stale(); $job$)
        ) AS t(jobname, schedule, command)
    LOOP
        IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = spec.jobname) THEN
            PERFORM cron.unschedule(spec.jobname);
        END IF;
        PERFORM cron.schedule_in_database(spec.jobname, spec.schedule, spec.command, 'maghz');
    END LOOP;
END
$cron$;
