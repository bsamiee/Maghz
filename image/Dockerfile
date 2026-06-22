# syntax=docker/dockerfile:1
# --- [BASE] -----------------------------------------------------------------------------
# ParadeDB pg18 bundles pg_search (BM25) + pgvector + pg_ivm + pg_cron + all contrib.
# This image layers ONLY the six extensions ParadeDB does not ship.
ARG PARADEDB_TAG=0.24.1-pg18
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
ARG IMAGE_VERSION=0.1.0

FROM paradedb/paradedb:${PARADEDB_TAG}

ARG GIT_SHA
ARG BUILD_DATE
ARG IMAGE_VERSION
LABEL org.opencontainers.image.title="maghz-pg" \
      org.opencontainers.image.description="Maghz second-brain PostgreSQL 18 — ParadeDB base + curated extension profile" \
      org.opencontainers.image.source="https://github.com/bsamiee/Maghz" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

# The postgres entrypoint starts as root and gosu-drops to the postgres user; extension
# layering is a root-only apt step, so the image's last USER is intentionally root.
# hadolint ignore=DL3002
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# --- [EXTENSIONS] -----------------------------------------------------------------------
# PGDG (the base already carries apt.postgresql.org trixie-pgdg): partman, hll, hypopg.
# PIGSTY (pgrx prebuilt .deb): pg_net (the embedding HTTP egress), pgmq, pg_jsonschema.
# Extension versions track the rolling PGDG/PIGSTY repos; pinning would break on upstream bumps.
# hadolint ignore=DL3008
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<'EOF'
set -euo pipefail
rm -f /etc/apt/apt.conf.d/docker-clean
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -d -m 0755 /usr/share/keyrings
curl -fsSL https://repo.pigsty.io/key | gpg --dearmor -o /usr/share/keyrings/pigsty.gpg
test -s /usr/share/keyrings/pigsty.gpg
. /etc/os-release
echo "deb [signed-by=/usr/share/keyrings/pigsty.gpg] https://repo.pigsty.io/apt/pgsql/${VERSION_CODENAME} ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/pigsty.list
apt-get update
apt-get install -y --no-install-recommends \
  postgresql-18-partman \
  postgresql-18-hll \
  postgresql-18-hypopg \
  postgresql-18-pg-net \
  postgresql-18-pgmq \
  postgresql-18-pg-jsonschema
EOF

EXPOSE 5432
STOPSIGNAL SIGINT
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --start-interval=2s --retries=3 \
    CMD ["pg_isready", "-q"]
