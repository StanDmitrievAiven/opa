#!/bin/sh
set -e
# Aiven App Runtime injects PORT; default 8181 for local/docker-compose.
LISTEN_PORT="${PORT:-8181}"
OPA_LOG_LEVEL="${OPA_LOG_LEVEL:-info}"
exec /usr/local/bin/opa run --server "--addr=0.0.0.0:${LISTEN_PORT}" "--log-level=${OPA_LOG_LEVEL}" --watch /policies /data
