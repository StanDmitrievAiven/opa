#!/bin/sh
# Poll DataHub GMS and refresh data/catalog.json (used with docker compose --profile sync).
set -eu
INTERVAL="${SYNC_INTERVAL_SECONDS:-120}"
echo "datahub-opa-sync: DATAHUB_GMS_URL=${DATAHUB_GMS_URL:-unset} interval=${INTERVAL}s"
while true; do
  if python3 /app/sync_datahub_to_opa.py -o /out/catalog.json; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') sync ok"
  else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') sync failed (check GMS URL / token / network)" >&2
  fi
  sleep "$INTERVAL"
done
