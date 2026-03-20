#!/bin/sh
set -e
# Aiven App Runtime injects PORT; default 8181 for local/docker-compose.
LISTEN_PORT="${PORT:-8181}"
OPA_LOG_LEVEL="${OPA_LOG_LEVEL:-info}"

# Optional: poll DataHub GMS and refresh /data/catalog.json (same env vars as standalone sync).
if [ -n "${DATAHUB_GMS_URL:-}" ]; then
  echo "DataHub sync enabled → /data/catalog.json (interval ${SYNC_INTERVAL_SECONDS:-120}s)"
  /opt/opa-sync/sync_loop_container.sh &
fi

exec /usr/local/bin/opa run --server "--addr=0.0.0.0:${LISTEN_PORT}" "--log-level=${OPA_LOG_LEVEL}" --watch /policies /data
