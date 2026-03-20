#!/bin/sh
# In-container poll: GMS → /data/catalog.json (OPA --watch reloads).
set -eu
INTERVAL="${SYNC_INTERVAL_SECONDS:-120}"
PY="/opt/opa-sync/sync_datahub_to_opa.py"
OUT="/data/catalog.json"
echo "datahub-opa-sync: DATAHUB_GMS_URL=${DATAHUB_GMS_URL} interval=${INTERVAL}s"
while true; do
  if python3 "$PY" -o "$OUT"; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') sync ok"
  else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') sync failed (GMS URL / token / network?)" >&2
  fi
  sleep "$INTERVAL"
done
