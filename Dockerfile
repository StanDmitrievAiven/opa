# OPA for Trino + DataHub governance snapshot (catalog.json).
# Multi-stage: official OPA image is distroless (no shell); final stage uses Debian
# (glibc) so the copied /opa binary runs — Alpine/musl often breaks with "not found".
#
# Optional in-container DataHub sync: set DATAHUB_GMS_URL (+ optional DATAHUB_TOKEN) at runtime.

ARG OPA_VERSION=1.14.1
FROM openpolicyagent/opa:${OPA_VERSION} AS upstream

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=upstream /opa /usr/local/bin/opa

COPY policies /policies
COPY data /data
COPY scripts/sync_datahub_to_opa.py /opt/opa-sync/sync_datahub_to_opa.py
COPY scripts/sync_loop_container.sh /opt/opa-sync/sync_loop_container.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/opa /opt/opa-sync/sync_loop_container.sh

EXPOSE 8181
ENTRYPOINT ["/entrypoint.sh"]
