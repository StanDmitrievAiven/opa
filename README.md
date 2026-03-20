# OPA for Trino + DataHub (Aiven-friendly)

Small **Docker image** that runs [Open Policy Agent](https://www.openpolicyagent.org/) with Trino [Rego policies](policies/trino.rego) and a **governance snapshot** [`data/catalog.json`](data/catalog.json). Intended for use with **[trinostate](https://github.com/StanDmitrievAiven/trinostate)** on Aiven (or any Trino that supports the [OPA access control plugin](https://trino.io/docs/current/security/opa-access-control.html)).

## Flow (simple)

1. **DataHub** holds tags, owners, column rules.  
2. A **sync loop** (optional **inside this image** or run elsewhere) calls DataHub GraphQL and writes `/data/catalog.json`.  
3. **OPA** loads Rego + JSON; **Trino** calls OPA on each decision.

The **OPA process** does not open connections to DataHub; a small **Python loop in the same container** does, when you set the env vars below.

## Deploy on Aiven App Runtime

1. Create an **App Runtime** app from this repository (Dockerfile at repo root).  
2. Open the **HTTP port** your platform uses (often `8080` or `8181`). If Aiven sets **`PORT`**, the container listens on that port automatically.  
3. Optional env: **`OPA_LOG_LEVEL`** (`info`, `debug`, …).

### DataHub sync **inside** the OPA container (recommended on Aiven)

If **`DATAHUB_GMS_URL`** is set (non-empty), the container starts a background job that polls GMS and overwrites **`/data/catalog.json`**; OPA’s **`--watch`** reloads it.

| Variable | Required | Purpose |
|----------|----------|---------|
| **`DATAHUB_GMS_URL`** | To enable sync | GMS **origin** only (e.g. `https://your-gms-host`) — **no** `/api/graphql` suffix. The container must **reach** this URL (VPC peering, public HTTPS, etc.). |
| **`DATAHUB_TOKEN`** | Often | Bearer token for GMS if auth is enabled. Store as an **Aiven secret**. |
| **`SYNC_INTERVAL_SECONDS`** | No | Default **120**. How often to refresh `catalog.json`. |

If **`DATAHUB_GMS_URL`** is **unset** or empty, no sync runs; OPA uses the `catalog.json` baked into the image at build time.

**Trino ([trinostate](https://github.com/StanDmitrievAiven/trinostate))** — set:

| Variable | Example value |
|----------|----------------|
| `OPA_POLICY_URI` | `https://<opa-app-host>/v1/data/trino/allow` |
| `OPA_POLICY_BATCHED_URI` | `https://<opa-app-host>/v1/data/trino/batch` |

Use **HTTPS** if your platform terminates TLS in front of the app (typical on Aiven). If Trino needs a custom trust store to call OPA, set **`OPA_ACCESS_CONTROL_EXTRAS`** in trinostate (see trinostate README).

### Updating `catalog.json` without built-in sync

If you **do not** set `DATAHUB_GMS_URL`:

- **Redeploy** after updating `data/catalog.json` in git, or  
- Run `scripts/sync_datahub_to_opa.py` on your laptop/CI and ship the file into the image.

## Local run (Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build
curl -sS "http://127.0.0.1:8181/v1/data/trino/allow" -d '{"input":{}}' -H 'Content-Type: application/json'
```

**With DataHub sync** (same container; set in `.env`):

```bash
# DATAHUB_GMS_URL=https://...   DATAHUB_TOKEN=...  in .env
docker compose up -d --build
```

## One-off sync (no compose)

**New to this?** Follow [docs/SYNC_STEP_BY_STEP.md](docs/SYNC_STEP_BY_STEP.md).

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
├── Dockerfile              # Multi-stage: official OPA binary + Debian (shell + PORT)
├── entrypoint.sh           # PORT, OPA_LOG_LEVEL, optional DATAHUB_* sync
├── policies/trino.rego     # Catalog-driven rules
├── data/catalog.json       # Initial snapshot; overwritten when sync enabled
├── scripts/                # sync_datahub_to_opa.py + container sync loop
└── docker-compose.yml      # Local / VM
```

## Policy & JSON shape

- Policies expect **`data.governance.tables`** keyed by `catalog.schema.table` (lowercase) for Trino datasets in DataHub.  
- Tags such as **`access:public`**, **owners**, and **`deny_user:<trino_username>`** on columns are documented in the [DataHub](https://datahubproject.io/) UI and exported by `sync_datahub_to_opa.py`.

## License

[MIT](LICENSE).
