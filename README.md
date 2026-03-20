# OPA for Trino + DataHub (Aiven-friendly)

Small **Docker image** that runs [Open Policy Agent](https://www.openpolicyagent.org/) with Trino [Rego policies](policies/trino.rego) and a **governance snapshot** [`data/catalog.json`](data/catalog.json). Intended for use with **[trinostate](https://github.com/StanDmitrievAiven/trinostate)** on Aiven (or any Trino that supports the [OPA access control plugin](https://trino.io/docs/current/security/opa-access-control.html)).

## Flow (simple)

1. **DataHub** holds tags, owners, column rules.  
2. A **sync job** (optional sidecar or cron) calls DataHub GraphQL and writes `data/catalog.json`.  
3. **OPA** loads Rego + JSON; **Trino** calls OPA on each decision.

OPA does **not** call DataHub or Trino.

## Deploy on Aiven App Runtime

1. Create an **App Runtime** app from this repository (Dockerfile at repo root).  
2. Open the **HTTP port** your platform uses (often `8080` or `8181`). If Aiven sets **`PORT`**, the container listens on that port automatically.  
3. Optional env: **`OPA_LOG_LEVEL`** (`info`, `debug`, …).  
4. After deploy, your OPA base URL is like `https://<app-host>:<port>`.

**Trino ([trinostate](https://github.com/StanDmitrievAiven/trinostate))** — set:

| Variable | Example value |
|----------|----------------|
| `OPA_POLICY_URI` | `https://<opa-app-host>/v1/data/trino/allow` |
| `OPA_POLICY_BATCHED_URI` | `https://<opa-app-host>/v1/data/trino/batch` |

Use **HTTPS** if your platform terminates TLS in front of the app (typical on Aiven). If OPA uses a private CA, set **`OPA_ACCESS_CONTROL_EXTRAS`** in trinostate (see trinostate README).

### Updating `catalog.json` on Aiven

The image **bakes in** `data/catalog.json` at build time. To refresh governance:

- **Redeploy** after updating the file in git (e.g. CI runs `scripts/sync_datahub_to_opa.py`, commits `data/catalog.json`, then build runs), or  
- Run **OPA + sync** on a VM using **Docker Compose** (`--profile sync`) below, or  
- Run the sync script anywhere that can reach GMS and then copy `catalog.json` into your deploy pipeline artifact.

## Local run (Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build
curl -sS "http://127.0.0.1:8181/v1/data/trino/allow" -d '{"input":{}}' -H 'Content-Type: application/json'
```

**With DataHub sync** (writes `./data/catalog.json`; compose mounts it into OPA):

```bash
# Set in .env: DATAHUB_GMS_URL=...  and optional DATAHUB_TOKEN
docker compose --profile sync up -d --build
```

## One-off sync (no compose)

```bash
export DATAHUB_GMS_URL=https://your-gms-host
export DATAHUB_TOKEN=...   # if required
python3 scripts/sync_datahub_to_opa.py -o data/catalog.json
```

## Endpoints

| Path | Purpose |
|------|---------|
| `/health` | Health check |
| `/v1/data/trino/allow` | Trino allow decision |
| `/v1/data/trino/batch` | Trino batch decision |

## Repo layout

```
├── Dockerfile              # OPA + baked policies + data/catalog.json
├── entrypoint.sh           # Honors PORT (Aiven) and OPA_LOG_LEVEL
├── policies/trino.rego     # Catalog-driven rules
├── data/catalog.json       # Governance snapshot (from DataHub sync)
├── scripts/                # DataHub → JSON exporter + sync loop
└── docker-compose.yml      # Local / VM: OPA + optional sync profile
```

## Policy & JSON shape

- Policies expect **`data.governance.tables`** keyed by `catalog.schema.table` (lowercase) for Trino datasets in DataHub.  
- Tags such as **`access:public`**, **owners**, and **`deny_user:<trino_username>`** on columns are documented in the [DataHub](https://datahubproject.io/) UI and exported by `sync_datahub_to_opa.py`.

## License

[MIT](LICENSE).
