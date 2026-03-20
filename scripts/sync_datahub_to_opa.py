#!/usr/bin/env python3
"""
Export DataHub dataset metadata (Trino platform only) into OPA governance JSON
for policies/trino.rego (data.governance.tables).

Requires DataHub GMS GraphQL at {DATAHUB_GMS_URL}/api/graphql.
No auth by default; set DATAHUB_TOKEN for Bearer authorization.

Usage:
  export DATAHUB_GMS_URL=https://your-gms.example
  python3 sync_datahub_to_opa.py --output ../data/catalog.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

URN_DATASET = re.compile(
    r"^urn:li:dataset:\(urn:li:dataPlatform:([^,]+),([^,]+),([^)]+)\)$"
)


def graphql(url: str, token: str | None, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url.rstrip("/") + "/api/graphql", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GraphQL HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"GraphQL connection failed: {e}") from e
    if payload.get("errors"):
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    return payload.get("data") or {}


SEARCH_QUERY = """
query SearchDatasets($count: Int!, $start: Int!) {
  searchAcrossEntities(
    input: { query: "*", types: [DATASET], start: $start, count: $count }
  ) {
    count
    searchResults {
      entity {
        urn
      }
    }
  }
}
"""

DATASET_QUERY = """
query DatasetMeta($urn: String!) {
  dataset(urn: $urn) {
    urn
    tags {
      tags {
        tag {
          name
          properties {
            name
          }
        }
      }
    }
    globalTags {
      tags {
        tag {
          name
          properties {
            name
          }
        }
      }
    }
    domain {
      domain {
        urn
      }
    }
    ownership {
      owners {
        owner {
          ... on CorpUser {
            urn
          }
          ... on CorpGroup {
            urn
          }
        }
      }
    }
    schemaMetadata {
      fields {
        fieldPath
        tags {
          tags {
            tag {
              name
              properties {
                name
              }
            }
          }
        }
        globalTags {
          tags {
            tag {
              name
              properties {
                name
              }
            }
          }
        }
      }
    }
    editableSchemaMetadata {
      editableSchemaFieldInfo {
        fieldPath
        tags {
          tags {
            tag {
              name
              properties {
                name
              }
            }
          }
        }
        globalTags {
          tags {
            tag {
              name
              properties {
                name
              }
            }
          }
        }
      }
    }
  }
}
"""


def urn_to_trino_key(urn: str) -> str | None:
    m = URN_DATASET.match(urn)
    if not m:
        return None
    platform, fqn, _env = m.groups()
    if platform.lower() != "trino":
        return None
    return fqn.lower()


def corpuser_from_urn(urn: str) -> str | None:
    if ":corpuser:" in urn:
        return urn.split(":corpuser:")[-1]
    return None


def _tag_display_names(global_tags: dict[str, Any] | None) -> list[str]:
    """Resolve tag labels for OPA (matches Rego, e.g. access:public)."""
    out: list[str] = []
    for row in (global_tags or {}).get("tags") or []:
        tag = row.get("tag") or {}
        props = tag.get("properties") or {}
        name = props.get("name") or tag.get("name")
        if name:
            out.append(name)
    return out


def simplify_field_path(field_path: str) -> str:
    """Map DataHub schemaMetadata fieldPath to Trino column name (flat columns)."""
    fp = (field_path or "").strip()
    if not fp:
        return ""
    if "]." in fp:
        fp = fp.rsplit("].", 1)[-1]
    if "." in fp and not fp.startswith("["):
        return fp.split(".")[-1]
    return fp.strip("[]")


def _field_column_tags(field: dict[str, Any]) -> list[str]:
    t = _tag_display_names(field.get("tags")) + _tag_display_names(field.get("globalTags"))
    return list(dict.fromkeys(t))


def fetch_all_dataset_urns(gms: str, token: str | None, page_size: int) -> list[str]:
    urns: list[str] = []
    start = 0
    while True:
        data = graphql(gms, token, SEARCH_QUERY, {"count": page_size, "start": start})
        sac = data.get("searchAcrossEntities") or {}
        results = sac.get("searchResults") or []
        for row in results:
            ent = row.get("entity") or {}
            u = ent.get("urn")
            if u:
                urns.append(u)
        total = sac.get("count")
        start += len(results)
        if not results or (total is not None and start >= total):
            break
    return urns


def build_snapshot(gms: str, token: str | None, page_size: int) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for urn in fetch_all_dataset_urns(gms, token, page_size):
        key = urn_to_trino_key(urn)
        if not key:
            continue
        data = graphql(gms, token, DATASET_QUERY, {"urn": urn})
        ds = data.get("dataset")
        if not ds:
            continue
        tag_names = _tag_display_names(ds.get("tags")) + _tag_display_names(ds.get("globalTags"))
        tags = list(dict.fromkeys(tag_names))
        domain_urn = None
        dom = (ds.get("domain") or {}).get("domain")
        if dom:
            domain_urn = dom.get("urn")
        owners: list[str] = []
        for o in (ds.get("ownership") or {}).get("owners") or []:
            owner_obj = o.get("owner") or {}
            ou = owner_obj.get("urn") or ""
            cu = corpuser_from_urn(ou)
            if cu:
                owners.append(cu)
        column_tags: dict[str, list[str]] = {}

        def add_column_tags_from_field(field_path: str, fld: dict[str, Any]) -> None:
            col = simplify_field_path(str(field_path or ""))
            if not col:
                return
            for tn in _field_column_tags(fld):
                column_tags.setdefault(col, []).append(tn)

        sm = ds.get("schemaMetadata") or {}
        for fld in sm.get("fields") or []:
            add_column_tags_from_field(str(fld.get("fieldPath") or ""), fld)
        esm = ds.get("editableSchemaMetadata") or {}
        for fld in esm.get("editableSchemaFieldInfo") or []:
            add_column_tags_from_field(str(fld.get("fieldPath") or ""), fld)
        for col, tls in list(column_tags.items()):
            column_tags[col] = list(dict.fromkeys(tls))
        row: dict[str, Any] = {
            "urn": urn,
            "tags": tags,
            "domain_urn": domain_urn,
            "owners": owners,
        }
        if column_tags:
            row["columnTags"] = column_tags
        tables[key] = row
    return {
        "governance": {
            "version": 2,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
        }
    }


def main() -> None:
    _repo_data = os.path.join(os.path.dirname(__file__), "..", "data", "catalog.json")
    ap = argparse.ArgumentParser(description="Sync DataHub Trino datasets to OPA governance JSON")
    ap.add_argument(
        "--output",
        "-o",
        default=_repo_data,
        help="Path to catalog.json (OPA watches this file)",
    )
    ap.add_argument("--page-size", type=int, default=50)
    args = ap.parse_args()

    gms = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080").rstrip("/")
    token = os.environ.get("DATAHUB_TOKEN")

    snapshot = build_snapshot(gms, token, args.page_size)
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(snapshot['governance']['tables'])} Trino tables to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
