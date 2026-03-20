# OPA for Trino + DataHub governance snapshot (catalog.json).
# Multi-stage: official OPA image is distroless (no shell); final stage uses Debian
# (glibc) so the copied /opa binary runs — Alpine/musl often breaks with "not found".

ARG OPA_VERSION=1.14.1
FROM openpolicyagent/opa:${OPA_VERSION} AS upstream

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=upstream /opa /usr/local/bin/opa

COPY policies /policies
COPY data /data
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/opa

EXPOSE 8181
ENTRYPOINT ["/entrypoint.sh"]
