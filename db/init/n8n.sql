-- --- [RUNTIME_PRELUDE] ------------------------------------------------------------------
-- The dedicated n8n database, created on first cluster init. The maghz-pg container mounts this
-- file into /docker-entrypoint-initdb.d/, so the Postgres entrypoint runs it exactly once when
-- PGDATA is empty (the same pass that creates POSTGRES_DB=maghz). n8n connects with
-- DB_POSTGRESDB_DATABASE=n8n and creates its own tables; it never creates the database itself, so a
-- missing n8n database aborts the n8n container at boot. Run-once-on-empty-PGDATA is the idempotency:
-- the entrypoint never re-runs initdb scripts against a populated cluster, so no guard is needed.

CREATE DATABASE n8n OWNER maghz;
