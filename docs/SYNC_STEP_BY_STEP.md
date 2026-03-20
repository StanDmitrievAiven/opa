# Step 2 for beginners: DataHub → `catalog.json` → OPA

You already pointed **Trino** at OPA (step 1). Step 2 is only: **copy governance from DataHub into the JSON file OPA reads**, then **ship that file** to your running OPA app.

OPA does **not** log into DataHub by itself. A small script does that once per run.

---

## A. Checklist before you start

1. **DataHub shows your Trino data**  
   In the DataHub UI you can open datasets that come from Trino (catalog / schema / table names look right).  
   If nothing is there yet, you must **ingest Trino into DataHub first** (Aiven docs or DataHub “Sources”). Come back after that works.

2. **You know your GMS base URL**  
   This is the DataHub **Metadata Service** URL **without** `/api/graphql` on the end.  
   Examples (yours will differ):
   - `https://datahub-gms-myproject.a.aivencloud.com`
   - `http://localhost:8080` (only if GMS runs on your laptop)

   If unsure, ask whoever deployed DataHub or check Aiven’s service details for the GMS / API hostname.

3. **Token (maybe)**  
   If your GMS requires login for the API, create a **Personal Access Token** in DataHub (often under **Settings → Access Tokens** or similar) and keep it private.

---

## B. Run the sync on your laptop (easiest first time)

You need **Python 3** (`python3 --version`). No extra pip packages — the script uses only the standard library.

### 1. Clone the OPA repo (if you don’t have it)

```bash
git clone https://github.com/StanDmitrievAiven/opa.git
cd opa
```

### 2. Set the GMS address (and token if needed)

```bash
export DATAHUB_GMS_URL="https://YOUR-GMS-HOST"
# Only if your GMS requires auth:
export DATAHUB_TOKEN="paste-your-token-here"
```

Replace `YOUR-GMS-HOST` with the real host (no trailing slash, no `/api/graphql`).

### 3. Generate `data/catalog.json`

```bash
python3 scripts/sync_datahub_to_opa.py -o data/catalog.json
```

**Good sign:** you see something like `Wrote N Trino tables to .../data/catalog.json` and `N` is greater than 0.

**Bad signs:**

| What you see | What to try |
|--------------|-------------|
| Connection / timeout | Your laptop must reach GMS (VPN, correct URL, firewall). |
| HTTP 401 / 403 | Set `DATAHUB_TOKEN` or fix token permissions. |
| `Wrote 0 Trino tables` | No Trino datasets in DataHub, or they’re under another platform name — fix ingestion first. |

### 4. Peek at the file (optional)

Open `data/catalog.json`. You should see:

```json
"governance": {
  "tables": {
    "my_catalog.my_schema.my_table": { ... }
  }
}
```

Keys are **`catalog.schema.table`** in lowercase.

---

## C. Put the new file on your Aiven OPA app

Your OPA container was **built with** `data/catalog.json` inside the image. Updating governance means **shipping a new file + new deploy**:

1. **Commit and push** the updated `data/catalog.json` to the `opa` GitHub repo (same repo Aiven builds from).
2. In **Aiven**, **redeploy** the OPA application so it rebuilds the image (or runs your pipeline).

After deploy, OPA’s `--watch` will see the new JSON and reload.

**When to repeat:** whenever you change tags, owners, or column rules in DataHub — run the script again, commit, redeploy (or automate that in CI later).

---

## D. After step 2

- **DataHub** = where you edit governance in the UI.  
- **Sync script** = copies that into `catalog.json`.  
- **Git + redeploy** = how Aiven OPA gets the new snapshot.  
- **Trino** (step 1) = already calling OPA; it will start enforcing what’s in the new snapshot.

---

## E. Next level (later)

- Run the same commands on a schedule (**GitHub Actions**, cron on a VM) so you don’t do it by hand.  
- Or use `docker compose --profile sync` on a server so a sidecar refreshes `catalog.json` without rebuilding OPA (different hosting pattern than “single Aiven app from Dockerfile”).

See also the main [README](../README.md).
