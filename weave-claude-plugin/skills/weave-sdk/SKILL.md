---
name: weave-sdk
description: Use when user asks about trace data, session analytics, tool usage stats, or wants to query Weave for call information. Provides context-aware access to the current session's trace data.
---

# Weave SDK - Trace Querying

Query trace data from the current Claude Code session using the Weave Python SDK.

## Current Session Context

The UserPromptSubmit hook provides the trace URL in system reminders:
```
Weave tracing active: https://wandb.ai/{entity}/{project}/r/call/{call_id}
```

To extract session context, parse this URL:
- **entity**: First path segment after wandb.ai (e.g., `wandb_fc`)
- **project**: Second path segment (e.g., `claude-code-plugin-test`)
- **call_id**: UUID after `/r/call/` - this is the **session root call**

All operations in this session share the same `trace_id` (same as the root call_id).

## Weave SDK Query API

### Initialize Client
```python
import weave
client = weave.init("{entity}/{project}")
```

### get_calls() - Query Multiple Calls
```python
calls = client.get_calls(
    filter={
        "trace_ids": ["<trace_id>"],       # Filter to specific trace
        "op_names": ["Bash", "Read"],      # Filter by operation names
        "call_ids": ["<call_id>"],         # Filter by specific call IDs
        "parent_ids": ["<parent_id>"],     # Filter by parent call
        "trace_roots_only": True,          # Only top-level calls (no children)
    },
    columns=["op_name", "started_at"],     # Only fetch these fields (faster!)
    limit=100,
    include_costs=True,
    sort_by=[{"field": "started_at", "direction": "desc"}],
)
```

### Performance: Column Selection
Specifying `columns` dramatically improves query speed:
```python
# Fast - only fetch what you need
calls = client.get_calls(columns=["op_name", "started_at", "ended_at"])

# Slow - fetches full inputs/outputs
calls = client.get_calls()  # all columns by default
```
Note: `id`, `trace_id`, `op_name`, `started_at` are always included.

### Filter Fields
- `trace_ids` - Filter to specific trace(s)
- `op_names` - Filter by operation name
- `call_ids` - Filter by specific call IDs
- `parent_ids` - Filter by parent call ID
- `trace_roots_only` - Only return root calls (no nested children)
- `input_refs`, `output_refs` - Filter by ref URIs

### get_call() - Get Single Call
```python
call = client.get_call("<call_id>", include_costs=True, columns=["inputs", "output"])
```

### Key Call Attributes
- `id`, `trace_id`, `parent_id` - Identity & hierarchy
- `op_name` - Operation name (e.g., "Bash", "Read", "Task")
- `inputs`, `output` - Call data
- `started_at`, `ended_at` - Timing
- `exception` - Error info if failed
- `summary` - Aggregated metrics (token usage when available)

## Common Query Patterns

### Count Tool Calls in Current Session
```python
calls = client.get_calls(
    filter={"trace_ids": ["<trace_id>"]},
    columns=["op_name"],
)
tool_calls = [c for c in calls if c.op_name in ["Bash", "Read", "Write", "Edit", "Grep", "Glob"]]
print(f"Tool calls: {len(tool_calls)}")
```

### List All Operations Used
```python
calls = client.get_calls(
    filter={"trace_ids": ["<trace_id>"]},
    columns=["op_name"],
)
op_names = set(c.op_name for c in calls)
```

### Get Token Usage
```python
calls = client.get_calls(
    filter={"trace_ids": ["<trace_id>"]},
    columns=["summary"],
    include_costs=True,
)
for call in calls:
    if call.summary and "usage" in call.summary:
        print(call.summary["usage"])
```

### Find Errors
```python
calls = client.get_calls(
    filter={"trace_ids": ["<trace_id>"]},
    columns=["op_name", "exception", "inputs"],
)
errors = [c for c in calls if c.exception]
```

### Timeline of Operations
```python
calls = client.get_calls(
    filter={"trace_ids": ["<trace_id>"]},
    columns=["op_name", "started_at", "ended_at"],
    sort_by=[{"field": "started_at", "direction": "asc"}],
)
```
