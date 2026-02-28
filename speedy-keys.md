# Speedy Keys: Design Report

## Problem Statement

Weave stores call inputs, outputs, attributes, and summaries as JSON-serialized strings (`inputs_dump`, `output_dump`, etc.) in Clickhouse. Queries against these fields use `JSON_VALUE(inputs_dump, '$.path')`, which parses the JSON string for every row in matching granules. The `tokenbf_v1` bloom filter indexes help skip entire granules, but within a matching granule the parse cost is unavoidable.

Users want fast filtering on specific nested keys within their JSON data. Clickhouse's native JSON column type would solve this, but its dynamic sub-column budget is global to the table — in a multi-tenant environment, one project's schema explosion can exhaust the budget for everyone.

**Speedy Keys** lets users promote a bounded set of keys to native typed columns for near-instant filtering, with per-project isolation and quotas.

## Design Overview

Three components:

1. **Slot columns** on `calls_complete` — a fixed set of typed columns (`sk_s1`, `sk_s2`, ... `sk_f1`, ...) shared by all projects. Each column has a DEFAULT so existing rows are unaffected.

2. **A registry table** — maps `(project_id, key_path) → (type, slot)`. Small, rarely written, heavily cached.

3. **Query rewriting** — when a filter targets a registered speedy key, the query builder emits a native column filter instead of `JSON_VALUE(...)`.

That's it. No hashing, no bloom filters, no dictionaries. The registry is a plain Clickhouse table read through an app-level cache.

### Shared Physical Columns

The slot columns are shared physical columns across all projects. The mapping is per-project.

```
Project 1 registry:
  "inputs.model_name"  → sk_s0
  "inputs.provider"    → sk_s1

Project 2 registry:
  "inputs.customer_id" → sk_s0    ← same physical column
  "inputs.region"      → sk_s1
```

Row from project 1: `sk_s0 = "gpt-4",      sk_s1 = "openai"`
Row from project 2: `sk_s0 = "cust_12345", sk_s1 = "us-east"`

This works because every query already filters by `project_id` (it's the first column in the `ORDER BY`). Clickhouse never mixes project 1 and project 2 rows in the same scan. So `sk_s0` meaning "model_name" for project 1 and "customer_id" for project 2 is totally fine — the query builder knows which mapping to use based on the project context.

Even if you have 10,000 projects each with 5 string keys, it's still just 5 `sk_s*` columns on the table. The registry has 50,000 rows, but each project only sees its own 5.

## Slot Columns

### Schema

Add columns to `calls_complete` via migration `025_add_speedy_keys.up.sql`:

```sql
-- String slots
sk_s0 String DEFAULT '',
sk_s1 String DEFAULT '',
sk_s2 String DEFAULT '',
sk_s3 String DEFAULT '',
sk_s4 String DEFAULT '',

-- Int slots
sk_i0 Int64 DEFAULT 0,
sk_i1 Int64 DEFAULT 0,
sk_i2 Int64 DEFAULT 0,
sk_i3 Int64 DEFAULT 0,
sk_i4 Int64 DEFAULT 0,

-- Float slots
sk_f0 Float64 DEFAULT 0,
sk_f1 Float64 DEFAULT 0,
sk_f2 Float64 DEFAULT 0,
sk_f3 Float64 DEFAULT 0,
sk_f4 Float64 DEFAULT 0,
```

**15 columns total** for the default config (5 string, 5 int, 5 float). All have defaults so they're zero-cost for rows that don't use them. Since `calls_complete` uses `min_bytes_for_wide_part=0` (wide format), each column is stored in its own file — unused columns are virtually free on disk and at query time.

### Why Not More Types?

Booleans can be encoded as `Int64` (0/1). Datetimes can be stored as epoch-seconds in `Int64` or ISO strings in `String`. Keeping the type set to {string, int, float} keeps the column count low and covers every practical use case.

### Configurable Slot Counts

The number of slots per type is controlled by environment variables, following the existing pattern in `environment.py`:

```python
# environment.py
def wf_speedy_keys_string_slots() -> int:
    return int(os.environ.get("WF_SPEEDY_KEYS_STRING_SLOTS", 5))

def wf_speedy_keys_int_slots() -> int:
    return int(os.environ.get("WF_SPEEDY_KEYS_INT_SLOTS", 5))

def wf_speedy_keys_float_slots() -> int:
    return int(os.environ.get("WF_SPEEDY_KEYS_FLOAT_SLOTS", 5))
```

The migration creates the **maximum** number of columns (e.g., 20 per type). The environment config controls how many are available for assignment. This means adding more slots for a customer is just a config change — no migration needed — as long as the physical columns already exist.

If you ever need columns beyond the migration's max, a new migration adds more. That's a one-time DDL and doesn't touch existing data.

### Per-Project Quotas

Each project has its own quota, independent of other projects. The default quota equals the env-var slot counts. For enterprise/paying customers who need more:

```python
# environment.py
def wf_speedy_keys_max_string_slots() -> int:
    """Hard ceiling — physical columns that exist in the table."""
    return int(os.environ.get("WF_SPEEDY_KEYS_MAX_STRING_SLOTS", 20))
```

The migration creates columns up to the max. The default quota is the lower `WF_SPEEDY_KEYS_STRING_SLOTS` value. A per-project override (stored in the registry table itself or a project settings table) can raise a project's quota up to the physical max. This keeps the common case simple while allowing exceptions.

For single-tenant deployments, set the default quota equal to the max — every project gets all 20 slots.

## The Registry

### Table

```sql
CREATE TABLE speedy_keys_registry (
    project_id      String,
    key_path        String,         -- e.g. 'inputs.model_name'
    source_dump     String,         -- 'inputs_dump', 'output_dump', 'summary_dump', 'attributes_dump'
    value_type      Enum8('string'=1, 'int'=2, 'float'=3),
    slot            UInt8,          -- 0-indexed slot number within the type
    created_at      DateTime64(3) DEFAULT now64(3),
    created_by      String DEFAULT '',
    deleted_at      DateTime64(3) DEFAULT toDateTime64(0, 3),
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, key_path)
```

A row means: "For project X, the key `inputs.model_name` is a string stored in column `sk_s3`."

`source_dump` records which JSON dump field the key comes from, so we know where to extract the value at insert time.

### Registration Flow

```
POST /api/projects/{project_id}/speedy_keys
{
    "key_path": "inputs.model_name",
    "value_type": "string"
}
```

Server-side logic:

1. Parse `key_path` to determine `source_dump`:
   - Starts with `inputs.` → `inputs_dump`, strip prefix
   - Starts with `output.` → `output_dump`, strip prefix
   - Starts with `summary.` → `summary_dump`, strip prefix
   - Starts with `attributes.` → `attributes_dump`, strip prefix
2. Count existing registrations for this project + type.
3. If under quota, assign `slot = next available slot number` (0-indexed, fill gaps from deletions).
4. Insert into `speedy_keys_registry`.
5. Invalidate the app-level cache for this project.
6. Return the registration.

**Deregistration:** Soft-delete by setting `deleted_at`. The slot becomes available for reuse. Old rows with stale data in that slot are harmless — queries for the new key in that slot won't match old values because the filter value will be different. If exact correctness is needed, a backfill can clear the slot.

### App-Level Cache

The registry changes extremely rarely (a user registers a key, then never touches it again for months). Cache it aggressively:

```python
# In ClickHouseTraceServer
_speedy_keys_cache: dict[str, list[SpeedyKeyRegistration]]  # project_id -> registrations
_speedy_keys_cache_ttl: int = 300  # seconds
```

On cache miss or expiry, query the registry table. This is a tiny query — at most a few dozen rows per project. The cache can be a simple TTL dict; no need for Redis or a Clickhouse Dictionary.

### Why Not a Clickhouse Dictionary?

A Clickhouse Dictionary would work, but it adds operational complexity (dictionary lifecycle, refresh configuration, monitoring). An app-level cache is simpler, already a pattern used throughout the codebase, and equally fast for our access pattern (lookup by project_id, which we always have).

## Insert Path

### Where to Hook In

The insert path converts API objects to `CallCompleteCHInsertable` in `_complete_call_to_ch_insertable()` (`clickhouse_trace_server_batched.py:6722`). This is where we extract speedy key values.

```python
def _complete_call_to_ch_insertable(
    complete_call: tsi.CompletedCallSchemaForInsert,
    speedy_keys: list[SpeedyKeyRegistration] | None = None,
) -> CallCompleteCHInsertable:
    inputs = complete_call.inputs
    # ... existing logic ...

    # Extract speedy key values
    sk_values = {}
    if speedy_keys:
        sk_values = _extract_speedy_key_values(
            speedy_keys,
            inputs=inputs,
            output=complete_call.output,
            summary=dict(complete_call.summary),
            attributes=complete_call.attributes,
        )

    return CallCompleteCHInsertable(
        # ... existing fields ...
        **sk_values,  # e.g. {"sk_s3": "gpt-4", "sk_f1": 0.7}
    )
```

The `_extract_speedy_key_values` function walks each registered key's path in the corresponding dict (inputs, output, etc.) and extracts the value. If the path doesn't exist in this particular call, the slot keeps its default.

### CallCompleteCHInsertable Changes

Add optional fields for each slot:

```python
class CallCompleteCHInsertable(CallBaseCHInsertable, ...):
    # ... existing fields ...

    # Speedy key slots — defaults match the Clickhouse column defaults
    sk_s0: str = ''
    sk_s1: str = ''
    # ... etc for all physical slots ...
    sk_i0: int = 0
    sk_f0: float = 0.0
    # ...
```

Since `ALL_CALL_COMPLETE_INSERT_COLUMNS = sorted(CallCompleteCHInsertable.model_fields.keys())`, these will automatically be included in batch inserts. The sentinel value system (`ch_sentinel_values.py`) doesn't need changes — the defaults are already the sentinels.

### Performance Impact on Insert

For a call that has 5 registered speedy keys: 5 dict lookups via dotted path traversal. This is negligible compared to the existing `extract_refs_from_values()` which recursively walks the entire JSON tree. No additional Clickhouse queries on the insert hot path — the registry is cached.

## Query Path

### Field Resolution Changes

In `get_field_by_name()` (`calls_query_builder.py:1722`), the current flow for `inputs.model_name`:

```
1. "inputs.model_name" not in ALLOWED_CALL_FIELDS
2. Split: ["inputs", "model_name"]
3. "inputs_dump" found in ALLOWED_CALL_FIELDS
4. Return CallsMergedDynamicField(field="inputs_dump").with_path(["model_name"])
5. Generates: JSON_VALUE(any(inputs_dump), '$."model_name"')
```

With speedy keys, insert a check before step 2:

```python
def get_field_by_name(
    name: str,
    speedy_keys: list[SpeedyKeyRegistration] | None = None,
) -> CallsMergedField:
    if name not in ALLOWED_CALL_FIELDS:
        # Check speedy keys first
        if speedy_keys:
            for sk in speedy_keys:
                if sk.key_path == name:
                    col = sk.column_name  # e.g. "sk_s3"
                    return CallsMergedAggField(field=col, agg_fn="any")

        # ... existing fallback logic (dynamic JSON fields) ...
```

That's it. If the key is registered, we return a simple `CallsMergedAggField` pointing at the slot column. The rest of the query builder works unchanged — it just sees a native column instead of a JSON extraction.

The generated SQL goes from:
```sql
WHERE JSON_VALUE(any(inputs_dump), '$."model_name"') = 'gpt-4'
```
to:
```sql
WHERE any(sk_s3) = 'gpt-4'
```

### Type-Aware Queries

Because int and float slots are natively typed, range queries work:

```sql
-- Before: JSON_VALUE returns a string, comparison is lexicographic (wrong!)
WHERE JSON_VALUE(any(inputs_dump), '$."temperature"') > '0.5'

-- After: native Float64 comparison (correct!)
WHERE any(sk_f1) > 0.5
```

This is a correctness improvement, not just performance.

### Casting

The query builder already has a `cast` parameter on `json_dump_field_as_sql()`. For speedy key columns, no cast is needed — the column is already the right type. If the query specifies a cast (e.g., `CastTo.FLOAT`), we can validate it matches the slot type and skip the cast or emit a `toFloat64()` if there's a mismatch.

## Migration

### `025_add_speedy_keys.up.sql`

```sql
-- Migration: Add speedy keys slot columns and registry table
--
-- Speedy keys allow per-project promotion of frequently-filtered JSON
-- fields to native typed columns for fast filtering.
--
-- Creates physical columns up to the maximum configurable limit.
-- Which slots are available per-project is controlled at the app layer.

-- Step 1: Add slot columns to calls_complete
-- String slots (max 20)
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_s0 String DEFAULT '';
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_s1 String DEFAULT '';
-- ... through sk_s19 ...

-- Int slots (max 20)
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_i0 Int64 DEFAULT 0;
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_i1 Int64 DEFAULT 0;
-- ... through sk_i19 ...

-- Float slots (max 20)
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_f0 Float64 DEFAULT 0;
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS sk_f1 Float64 DEFAULT 0;
-- ... through sk_f19 ...

-- Step 2: Create registry table
CREATE TABLE IF NOT EXISTS speedy_keys_registry (
    project_id      String,
    key_path        String,
    source_dump     String,
    value_type      Enum8('string'=1, 'int'=2, 'float'=3),
    slot            UInt8,
    created_at      DateTime64(3) DEFAULT now64(3),
    created_by      String DEFAULT '',
    deleted_at      DateTime64(3) DEFAULT toDateTime64(0, 3)
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, key_path);
```

The `ALTER TABLE ADD COLUMN ... DEFAULT` is online and non-blocking in Clickhouse. Existing rows get the default on read. No backfill needed for the column addition itself.

### `025_add_speedy_keys.down.sql`

```sql
-- Drop registry
DROP TABLE IF EXISTS speedy_keys_registry;

-- Drop slot columns (reverse order)
ALTER TABLE calls_complete DROP COLUMN IF EXISTS sk_f19;
-- ... all columns ...
ALTER TABLE calls_complete DROP COLUMN IF EXISTS sk_s0;
```

## Backfill Strategy

When a user registers a new speedy key, existing rows don't have the value populated. Two options:

**Option A: No backfill (simplest).** New rows get speedy key values. Old rows fall back to `JSON_VALUE()`. The query builder can emit a `UNION ALL` or `OR` that checks the speedy key column first and falls back to JSON for rows where the slot is empty. Over time, as old data ages out (TTL) and new data comes in, coverage approaches 100%.

**Option B: Background backfill.** After registration, enqueue an `ALTER TABLE UPDATE`:

```sql
ALTER TABLE calls_complete
UPDATE sk_s3 = JSON_VALUE(inputs_dump, '$."model_name"')
WHERE project_id = {project_id:String}
  AND sk_s3 = ''
  AND JSON_VALUE(inputs_dump, '$."model_name"') != ''
```

This is a mutation — it runs asynchronously in Clickhouse. For large projects this could take minutes to hours, but it doesn't block reads or writes. The registry can track backfill status (`backfill_status: pending|running|complete`).

**Recommendation:** Start with Option A. It's zero-risk. Add Option B later if customers want historical data to be fast-filterable immediately.

## Configuration Summary

| Env Var | Default | Description |
|---------|---------|-------------|
| `WF_SPEEDY_KEYS_STRING_SLOTS` | `5` | Default per-project string slot quota |
| `WF_SPEEDY_KEYS_INT_SLOTS` | `5` | Default per-project int slot quota |
| `WF_SPEEDY_KEYS_FLOAT_SLOTS` | `5` | Default per-project float slot quota |
| `WF_SPEEDY_KEYS_MAX_STRING_SLOTS` | `20` | Physical string columns in the table |
| `WF_SPEEDY_KEYS_MAX_INT_SLOTS` | `20` | Physical int columns in the table |
| `WF_SPEEDY_KEYS_MAX_FLOAT_SLOTS` | `20` | Physical float columns in the table |
| `WF_SPEEDY_KEYS_CACHE_TTL` | `300` | Registry cache TTL in seconds |

To expand a paying customer's quota: either bump the default env vars (affects all projects) or add a per-project override to the registry (a `quota_override` column on a project settings table, or a separate small table).

For single-tenant: set defaults equal to max.

## What Changes Where

| File | Change |
|------|--------|
| `migrations/025_add_speedy_keys.up.sql` | New migration: slot columns + registry table |
| `environment.py` | New env var accessors for slot counts and cache TTL |
| `clickhouse_schema.py` | Add `sk_*` fields to `CallCompleteCHInsertable` |
| `ch_sentinel_values.py` | Add `sk_*` int/float fields to sentinel sets |
| `clickhouse_trace_server_batched.py` | Registry cache + speedy key extraction in insert path |
| `calls_query_builder.py` | Check speedy keys in `get_field_by_name()` |
| API layer (new endpoint) | `POST/GET/DELETE /projects/{id}/speedy_keys` |

The query builder change is ~10 lines. The insert path change is ~30 lines. The registry CRUD is a standard resource following the `annotation_queues` pattern. The migration is mechanical.

## What This Doesn't Do

- **Auto-detection.** Users must explicitly register keys. This is intentional — it keeps the system predictable and avoids one user's workload affecting others.
- **Cross-project deduplication.** Each project gets its own slot assignments. If 1000 projects all register `inputs.model_name`, that's 1000 registry rows but they all map to the same physical columns. No waste.
- **Composite keys.** Each speedy key is a single scalar value at a JSON path. Filtering on `inputs.config` where config is an object doesn't make sense — you'd register `inputs.config.temperature` instead.
- **Full-text search.** Speedy keys are for equality and range filters. If users need full-text search on a JSON field, that's a different feature (and the existing `tokenbf_v1` indexes already help there).

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Slot columns add to table width | `min_bytes_for_wide_part=0` means wide format — unused columns are separate files with near-zero overhead |
| Registry cache goes stale | 5-min TTL is conservative. Registration is rare. Worst case: a newly registered key doesn't activate for 5 minutes |
| User registers wrong type | Validate at registration time. If `inputs.temperature` is actually a string in the JSON, the int slot extraction will produce 0 (the default). We can detect this and warn. |
| Schema migration on a huge table | `ALTER TABLE ADD COLUMN DEFAULT` is metadata-only in Clickhouse. No data rewrite. |
| Running out of physical slots | Migration creates 20 per type (60 total). That's the ceiling until a new migration. The env vars prevent over-assignment. |
