package trino

import future.keywords.contains
import future.keywords.if
import future.keywords.in

default allow := false

allow if {
	not data_access_operation
}

data_access_operation if {
	input.action.operation == "SelectFromColumns"
}

data_access_operation if {
	input.action.operation == "FilterColumns"
}

# JSON snapshot only — do not name this `governance_tables` (conflicts under data.trino and breaks evaluation).
tables_map := object.get(data.governance, "tables", {})

# JDBC / metadata crawlers (e.g. DataHub ingestion) — no dataset governance.
allow if {
	data_access_operation
	metadata_table
}

metadata_table if {
	t := input.action.resource.table
	lower(t.schemaName) == "information_schema"
}

metadata_table if {
	t := input.action.resource.table
	lower(t.catalogName) == "system"
}

# Business tables: allowed at dataset level AND no column-level deny_user:<name> on selected columns.
allow if {
	data_access_operation
	not metadata_table
	governance_table_allowed
	not column_denied_for_user
}

governance_table_allowed if {
	t := input.action.resource.table
	key := sprintf("%s.%s.%s", [lower(t.catalogName), lower(t.schemaName), lower(t.tableName)])
	meta := object.get(tables_map, key, {})
	"access:public" in object.get(meta, "tags", [])
}

governance_table_allowed if {
	t := input.action.resource.table
	key := sprintf("%s.%s.%s", [lower(t.catalogName), lower(t.schemaName), lower(t.tableName)])
	meta := object.get(tables_map, key, {})
	input.context.identity.user in object.get(meta, "owners", [])
}

# DataHub: tag deny_user:alice on a schema field → user alice cannot read that column.
column_denied_for_user if {
	t := input.action.resource.table
	user := input.context.identity.user
	deny_tag := sprintf("deny_user:%s", [user])
	key := sprintf("%s.%s.%s", [lower(t.catalogName), lower(t.schemaName), lower(t.tableName)])
	meta := object.get(tables_map, key, {})
	colmap := object.get(meta, "columnTags", {})
	some cn
	cn = object.get(t, "columns", [])[_]
	deny_tag in object.get(colmap, cn, [])
}

batch contains i if {
	some i
	raw := input.action.filterResources[i]
	allow with input as object.union(input, {"action": object.union(input.action, {"resource": raw})})
}
