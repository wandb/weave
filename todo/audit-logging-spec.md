# Audit Logging Spec

## Goal

Track every authenticated user interaction with data in the Weave trace server. Both frontend and SDK clients are subject to auditing. The audit log must be able to answer:

- "Did user X look at call Y?"
- "Which users have ever viewed this version of this object?"
- "When was the last time feedback Z was viewed?"
- "What did user X do in project P?"
- "Did user X access call Y via a bulk query?"

## Design Principles

- Audit at the **handler layer**, not middleware. Log after the handler returns so we know the operation succeeded and have access to the resolved `wb_user_id`, typed request, and response data.
- **O(1) rows per request**. Use `Array(String)` for `action_ids` with a bloom filter index, not one row per entity.
- Fire-and-forget async inserts. Audit failures must never affect request processing.
- Reads are definitive data access events. Queries are activity events for metadata, or data access events when heavy columns are requested.

## ClickHouse Schema

### Table: `audit_log`

Migration: `027_audit_log.up.sql`

```sql
CREATE TABLE audit_log (
    timestamp        DateTime64(3),
    wb_user_id       String,
    project_id       String,
    action           LowCardinality(String),
    action_ids       Array(String),

    INDEX idx_action_ids action_ids TYPE bloom_filter GRANULARITY 3
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (project_id, wb_user_id, timestamp)
TTL timestamp + INTERVAL 180 DAY
```

### Column Semantics

| Column | Description |
|--------|-------------|
| `timestamp` | Server-side timestamp at time of audit emission (post-handler) |
| `wb_user_id` | Resolved user ID from `authentication.require_wb_user_id(auth_params)` |
| `project_id` | External project ID (entity/project format) |
| `action` | Action name derived from endpoint, e.g. `call_read`, `calls_query`, `obj_create` |
| `action_ids` | Array of entity IDs involved in the action. Single-element for reads, multi-element for bulk queries, empty for metadata-only queries. Capped at 1000 elements. |

### Sort Key Rationale

`ORDER BY (project_id, wb_user_id, timestamp)` optimizes for:
- "What did user X do in project Y?" — hits full key prefix
- "All activity in project Y" — hits first key column
- Entity lookups ("who accessed call Z?") are handled by the bloom filter index on `action_ids`

### Retention

180-day TTL with monthly partitions. Partitions older than 6 months are automatically dropped by ClickHouse.

## Action Catalog

### Reads (entity-level audit, `action_ids` populated)

| Endpoint | Action | action_ids |
|----------|--------|------------|
| `POST /call/read` | `call_read` | `[req.id]` |
| `POST /call/update` | `call_update` | `[req.call_id]` |
| `POST /calls/delete` | `calls_delete` | `req.call_ids` |
| `POST /obj/read` | `obj_read` | `["{req.object_id}:{req.digest}"]` |
| `POST /obj/create` | `obj_create` | `[req.obj.object_id]` |
| `POST /obj/delete` | `obj_delete` | `[req.object_id]` |
| `PUT /objs/{object_id}/versions/{digest}/tags` | `obj_add_tags` | `["{object_id}:{digest}"]` |
| `POST /objs/{object_id}/versions/{digest}/tags/remove` | `obj_remove_tags` | `["{object_id}:{digest}"]` |
| `PUT /objs/{object_id}/aliases` | `obj_set_aliases` | `[object_id]` |
| `POST /objs/{object_id}/aliases/remove` | `obj_remove_aliases` | `[object_id]` |
| `POST /feedback/create` | `feedback_create` | `[req.weave_ref]` |
| `POST /feedback/batch/create` | `feedback_create_batch` | `[r.weave_ref for r in req.batch]` |
| `POST /feedback/purge` | `feedback_purge` | `[]` (filter-based, no specific IDs) |
| `POST /feedback/replace` | `feedback_replace` | `[req.weave_ref]` |
| `POST /refs/read_batch` | `refs_read_batch` | `req.refs` |
| `POST /file/create` | `file_create` | `[]` (no entity ID at request time) |
| `POST /file/content` | `file_content_read` | `[req.digest]` |
| `POST /cost/create` | `cost_create` | `[]` |
| `POST /cost/purge` | `cost_purge` | `[]` |
| `POST /actions/execute_batch` | `actions_execute_batch` | `req.call_ids` (if available) |
| `POST /call/start` | `call_start` | `[req.start.id]` |
| `POST /call/end` | `call_end` | `[req.end.id]` |
| `POST /call/upsert_batch` | `call_upsert_batch` | extracted IDs from batch items |
| `POST /table/create` | `table_create` | `[]` |
| `POST /table/update` | `table_update` | `[req.table_ref]` (if available) |
| `POST /completions/create` | `completions_create` | `[]` |

### Queries (activity-level audit)

For query endpoints, `action_ids` behavior depends on whether heavy columns are requested:

| Endpoint | Action | action_ids |
|----------|--------|------------|
| `POST /calls/query` | `calls_query` | See "Heavy Column Detection" below |
| `POST /calls/stream_query` | `calls_stream_query` | See "Heavy Column Detection" below |
| `POST /calls/query_stats` | `calls_query_stats` | `[]` (aggregate only, no entity access) |
| `POST /objs/query` | `objs_query` | `[]` (metadata browsing) |
| `POST /table/query` | `table_query` | `[]` |
| `POST /table/query_stats` | `table_query_stats` | `[]` |
| `POST /feedback/query` | `feedback_query` | `[]` |
| `POST /feedback/stats` | `feedback_stats` | `[]` |
| `POST /cost/query` | `cost_query` | `[]` |
| `POST /trace/usage` | `trace_usage` | `req.call_ids` |
| `POST /calls/usage` | `calls_usage` | `req.call_ids` |
| `POST /project/stats` | `project_stats` | `[]` |

### Endpoints NOT Audited

| Endpoint | Reason |
|----------|--------|
| `GET /health` | No auth, no data access |
| `GET /version` | No auth, no data access |
| `GET /server_info` | No auth, no data access |
| `GET /geolocate` | No data access |
| `GET /` | Index page |
| `GET /inference/*` | Model listing, no project data |
| `POST /otel/v1/traces` | Ingestion path, high volume — audit via call_start/call_end instead |

### V2 / Object Router Endpoints

| Endpoint | Action | action_ids |
|----------|--------|------------|
| `POST /{entity}/{project}/calls/complete` | `calls_complete` | extracted IDs from batch |
| `POST /{entity}/{project}/call/start` | `call_start_v2` | `[body.call_id]` |
| `POST /{entity}/{project}/call/end` | `call_end_v2` | `[body.call_id]` |
| `POST /{entity}/{project}/ops` | `op_create` | `[body.op_id]` (if available) |
| `GET /{entity}/{project}/ops/{object_id}/versions/{digest}` | `op_read` | `["{object_id}:{digest}"]` |
| `GET /{entity}/{project}/ops` | `op_list` | `[]` |
| `DELETE /{entity}/{project}/ops/{object_id}` | `op_delete` | `[object_id]` |
| `POST /{entity}/{project}/datasets` | `dataset_create` | `[body.dataset_id]` (if available) |
| `GET /{entity}/{project}/datasets/{object_id}/versions/{digest}` | `dataset_read` | `["{object_id}:{digest}"]` |
| `GET /{entity}/{project}/datasets` | `dataset_list` | `[]` |
| `DELETE /{entity}/{project}/datasets/{object_id}` | `dataset_delete` | `[object_id]` |
| `POST /{entity}/{project}/scorers` | `scorer_create` | `[body.scorer_id]` (if available) |
| `GET /{entity}/{project}/scorers/{object_id}/versions/{digest}` | `scorer_read` | `["{object_id}:{digest}"]` |

## Heavy Column Detection

For `calls_query` and `calls_stream_query`, the presence of heavy columns determines whether we log per-entity `action_ids`:

```python
HEAVY_CALL_COLUMNS = {"inputs", "output", "attributes", "summary"}

def requests_heavy_columns(req: CallsQueryReq) -> bool:
    # No column filter = all columns = heavy
    if req.columns is None:
        return True
    # Check if any requested column is a heavy column
    # Column names may be dotted paths like "inputs.foo.bar"
    requested = {col.split(".")[0] for col in req.columns}
    return bool(requested & HEAVY_CALL_COLUMNS)
```

When heavy columns are detected:
- `action_ids` = list of call IDs from the response (capped at 1000)
- This means the audit log definitively records which calls' payload data was accessed

When only metadata columns:
- `action_ids` = `[]`
- Logs that the user was browsing/searching, not which specific calls appeared

## Implementation

### Files to Create

| File | Repo | Description |
|------|------|-------------|
| `weave/trace_server/migrations/027_audit_log.up.sql` | weave-python | CREATE TABLE |
| `weave/trace_server/migrations/027_audit_log.down.sql` | weave-python | DROP TABLE |
| `weave/trace_server/audit.py` | weave-python | AuditLogger class with batched CH inserts |

### Files to Modify

| File | Repo | Description |
|------|------|-------------|
| `src/trace_server.py` | weave-trace | Add `audit.log()` calls in each endpoint handler |

### `audit.py` Module Design

```python
from dataclasses import dataclass

MAX_ACTION_IDS = 1000

@dataclass
class AuditEvent:
    timestamp: datetime
    wb_user_id: str
    project_id: str
    action: str
    action_ids: list[str]

class AuditLogger:
    """Batched, fire-and-forget audit logger backed by ClickHouse."""

    def __init__(self, ch_client: ClickHouseClient):
        self._ch_client = ch_client
        self._batch: list[AuditEvent] = []
        self._lock = threading.Lock()

    def log(
        self,
        auth_params: AuthParams,
        project_id: str,
        action: str,
        action_ids: list[str] | None = None,
    ) -> None:
        """Emit an audit event. Never raises."""
        try:
            wb_user_id = authentication.require_wb_user_id(auth_params)
            event = AuditEvent(
                timestamp=datetime.now(UTC),
                wb_user_id=wb_user_id,
                project_id=project_id,
                action=action,
                action_ids=(action_ids or [])[:MAX_ACTION_IDS],
            )
            self._enqueue(event)
        except Exception:
            logger.warning("Failed to emit audit event", exc_info=True)
            # TODO: increment datadog counter for audit failures

    def _enqueue(self, event: AuditEvent) -> None:
        """Add event to batch, flush if batch is full."""
        ...

    def _flush(self) -> None:
        """Insert batch into ClickHouse."""
        ...
```

### Per-Endpoint Integration Pattern

Each endpoint gets a single `audit.log()` call after the successful handler return:

```python
@prefix_router.post("/call/read", tags=[CALLS_TAG_NAME])
def call_read(
    req: tsi.CallReadReq,
    auth_params: Annotated[AuthParams, Depends(universal_auth_params)],
) -> tsi.CallReadRes:
    authorization.can_read_project_scope(req.project_id, auth_params)
    api = get_adapting_server(auth_params)
    result = api.call_read(req)
    audit.log(auth_params, req.project_id, "call_read", action_ids=[req.id])
    return result
```

For query endpoints with heavy column detection:

```python
@prefix_router.post("/calls/query", tags=[CALLS_TAG_NAME])
def calls_query(
    req: tsi.CallsQueryReq,
    auth_params: Annotated[AuthParams, Depends(universal_auth_params)],
) -> tsi.CallsQueryRes:
    authorization.can_read_project_scope(req.project_id, auth_params)
    api = get_adapting_server(auth_params)
    res = api.calls_query(req)
    action_ids = (
        [c.id for c in res.calls]
        if requests_heavy_columns(req)
        else []
    )
    audit.log(auth_params, req.project_id, "calls_query", action_ids=action_ids)
    return res
```

### `wb_user_id` Resolution

The `wb_user_id` is resolved inside `audit.log()` via `authentication.require_wb_user_id(auth_params)`. This is the same call used by `enforce_and_set_server_side_user_id` for write endpoints. For read endpoints, this will be a new gorilla call per request. This should be acceptable because:

1. The gorilla call is already cached/fast (used on every write endpoint today)
2. Read endpoints are less frequent than write endpoints (ingestion is the hot path)
3. The call happens after the response is computed, so it doesn't affect perceived latency if done async

If this becomes a bottleneck, we can cache the resolved user ID in the `auth_params` object.

### Streaming Endpoint Handling

`calls_stream_query` is a streaming endpoint. For MVP, we log the audit event before streaming begins (we know the request, but not which results will be streamed). If heavy columns are requested, we cannot populate `action_ids` without buffering the entire stream. Options:

1. **MVP: Log with empty `action_ids`** for streaming endpoints, even with heavy columns
2. **Future: Tap the stream** to collect IDs as they flow through, emit audit event on stream completion

Recommend option 1 for MVP.

## Example Queries

```sql
-- "Did user X look at call Y?"
SELECT timestamp, action
FROM audit_log
WHERE project_id = 'entity/project'
  AND has(action_ids, 'call-uuid-here')
  AND wb_user_id = 'user-id'
ORDER BY timestamp DESC

-- "Which users have viewed this object version?"
SELECT DISTINCT wb_user_id,
       min(timestamp) AS first_viewed,
       max(timestamp) AS last_viewed
FROM audit_log
WHERE project_id = 'entity/project'
  AND action = 'obj_read'
  AND has(action_ids, 'my-object:sha256abc')
GROUP BY wb_user_id
ORDER BY last_viewed DESC

-- "When was feedback X last viewed?"
SELECT max(timestamp) AS last_viewed
FROM audit_log
WHERE project_id = 'entity/project'
  AND action = 'feedback_query'
  AND has(action_ids, 'feedback-uuid')

-- "Full activity timeline for user X in project Y"
SELECT timestamp, action, action_ids
FROM audit_log
WHERE project_id = 'entity/project'
  AND wb_user_id = 'user-id'
ORDER BY timestamp DESC
LIMIT 100

-- "Who bulk-exported call data from project Y in the last 7 days?"
SELECT wb_user_id, count() AS query_count, sum(length(action_ids)) AS total_calls_accessed
FROM audit_log
WHERE project_id = 'entity/project'
  AND action = 'calls_query'
  AND length(action_ids) > 0
  AND timestamp > now() - INTERVAL 7 DAY
GROUP BY wb_user_id
ORDER BY total_calls_accessed DESC
```

## Future Extensions (Not MVP)

- **User timeline materialized view**: `ORDER BY (project_id, wb_user_id, timestamp)` for fast user-centric queries (if the main table key changes)
- **Query API**: Dedicated endpoints for reading audit logs, with auth scoping
- **UI**: Audit log viewer in the Weave dashboard
- **Streaming audit**: Tap streaming responses to capture entity IDs
- **Frontend view tracking**: Client-side events for "user actually looked at row X in a table"
- **Retention policies**: Per-org configurable retention beyond the default 180 days
- **Alert/anomaly detection**: Unusual access patterns (e.g., user accessing many projects they don't normally touch)
