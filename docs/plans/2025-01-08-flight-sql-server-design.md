# Weave Flight SQL Server Design

## Overview

A Go-based Apache Arrow Flight SQL server that provides a pleasant SQL interface to Weave trace data, optimized for data science workflows (pandas, polars, DuckDB).

### Goals

- Stream `calls_merged` data efficiently via Arrow Flight SQL protocol
- Support JSON path extraction (`inputs.prompt`, `output.choices[0].text`)
- Expose pre-defined virtual columns for common LLM and tracing fields
- Enforce tenancy via `project_id` with W&B API key validation
- Design for future expansion to datasets, objects, and refs

### Non-goals for v1

- Write operations
- ClickHouse JSON type migration (future experiment)
- Multiple table joins across weave tables

### Why Flight SQL

- **Streaming**: Data flows as Arrow record batches, no buffering entire result
- **SQL interface**: Engineers write familiar SQL, not custom APIs
- **Pushdown**: Filters/projections can be pushed to ClickHouse
- **Ecosystem**: Works with pandas, polars, DuckDB, JDBC/ODBC bridges

## Architecture

```
┌─────────────────┐     Flight SQL      ┌──────────────────────┐
│  Python/Pandas  │◄──────────────────►│                      │
│  Polars/DuckDB  │   (Arrow batches)   │  Weave Flight SQL    │
│  Any Arrow      │                     │  Server (Go)         │
│  Client         │                     │                      │
└─────────────────┘                     │  ┌────────────────┐  │
                                        │  │ Auth Layer     │  │
                                        │  │ (W&B API key)  │  │
                                        │  └───────┬────────┘  │
                                        │          │           │
                                        │  ┌───────▼────────┐  │
                                        │  │ SQL Parser &   │  │
                                        │  │ Query Planner  │  │
                                        │  └───────┬────────┘  │
                                        │          │           │
                                        │  ┌───────▼────────┐  │
                                        │  │ Virtual Column │  │
                                        │  │ Transformer    │  │
                                        │  └───────┬────────┘  │
                                        │          │           │
                                        │  ┌───────▼────────┐  │
                                        │  │ ClickHouse     │  │
                                        │  │ Query Executor │  │
                                        │  └───────┬────────┘  │
                                        │          │           │
                                        │  ┌───────▼────────┐  │
                                        │  │ Arrow Builder  │  │
                                        │  │ (JSON parsing) │  │
                                        │  └────────────────┘  │
                                        └──────────┬───────────┘
                                                   │ Native TCP
                                                   ▼
                                        ┌──────────────────────┐
                                        │     ClickHouse       │
                                        │   (calls_merged)     │
                                        └──────────────────────┘
```

### Components

1. **Auth Layer** - Validates W&B API key from Flight auth header, extracts allowed project access
2. **SQL Parser & Query Planner** - Parses incoming SQL, rewrites virtual column references, injects `project_id` filter for tenancy
3. **Virtual Column Transformer** - Maps virtual columns (e.g., `input_model`) to JSON paths, tracks which raw columns are needed
4. **ClickHouse Query Executor** - Generates ClickHouse SQL, streams results via native protocol
5. **Arrow Builder** - Converts ClickHouse rows to Arrow record batches, parses JSON and populates virtual columns

### Key Design Decisions

- Native ClickHouse protocol (port 9440) for streaming - avoids buffering issues seen in HTTP
- JSON parsing happens in Go as rows stream through - memory-efficient, no full materialization
- `project_id` always injected into WHERE clause - tenancy enforced at query level
- Project ID must be explicitly specified by client (required for MVP)

## Virtual Columns Schema

The Flight server exposes a `calls` table with these columns:

### Core columns (pass-through from ClickHouse)

| Column | Type | Source |
|--------|------|--------|
| `id` | `STRING` | `calls_merged.id` |
| `project_id` | `STRING` | `calls_merged.project_id` |
| `trace_id` | `STRING` | `calls_merged.trace_id` |
| `parent_id` | `STRING` | `calls_merged.parent_id` |
| `op_name` | `STRING` | `calls_merged.op_name` |
| `started_at` | `TIMESTAMP` | `calls_merged.started_at` |
| `ended_at` | `TIMESTAMP` | `calls_merged.ended_at` |
| `exception` | `STRING` | `calls_merged.exception` |

### General tracing virtual columns

| Column | Type | JSON Path | Description |
|--------|------|-----------|-------------|
| `latency_ms` | `FLOAT64` | computed | `ended_at - started_at` in milliseconds |
| `status` | `STRING` | computed | `'error'` if exception, else `'success'` |
| `error_message` | `STRING` | `exception` (first line) | Truncated exception message |

### LLM-focused virtual columns

| Column | Type | JSON Path |
|--------|------|-----------|
| `input_model` | `STRING` | `inputs.model` |
| `input_messages` | `STRING` (JSON array) | `inputs.messages` |
| `input_prompt` | `STRING` | `inputs.prompt` |
| `output_content` | `STRING` | `output.choices[0].message.content` |
| `output_text` | `STRING` | `output.choices[0].text` (completions API) |
| `input_tokens` | `INT64` | `summary.usage.prompt_tokens` or `output.usage.prompt_tokens` |
| `output_tokens` | `INT64` | `summary.usage.completion_tokens` or `output.usage.completion_tokens` |
| `total_tokens` | `INT64` | `summary.usage.total_tokens` or `output.usage.total_tokens` |

### Raw JSON access (always available)

| Column | Type | Source |
|--------|------|--------|
| `inputs_json` | `STRING` | `calls_merged.inputs_dump` |
| `output_json` | `STRING` | `calls_merged.output_dump` |
| `summary_json` | `STRING` | `calls_merged.summary_dump` |
| `attributes_json` | `STRING` | `calls_merged.attributes_dump` |

### Dynamic JSON path extraction

Users can query arbitrary paths using a function syntax:

```sql
SELECT json_extract(inputs_json, '$.my.custom.path') FROM calls
```

## Query Flow & Tenancy

### Example query transformation

**User writes:**
```sql
SELECT op_name, input_model, output_tokens, latency_ms
FROM calls
WHERE started_at > '2024-01-01'
  AND input_model = 'gpt-4'
ORDER BY latency_ms DESC
LIMIT 100
```

**Server rewrites to ClickHouse:**
```sql
SELECT
  op_name,
  inputs_dump,      -- needed for input_model extraction
  summary_dump,     -- needed for output_tokens extraction
  started_at,       -- needed for latency_ms
  ended_at          -- needed for latency_ms
FROM calls_merged
WHERE project_id = 'BASE64_PROJECT_ID'  -- injected for tenancy
  AND started_at > '2024-01-01'
  AND deleted_at IS NULL
ORDER BY (ended_at - started_at) DESC
LIMIT 100
```

### Stream & transform

As rows stream from ClickHouse:

1. Parse `inputs_dump` JSON, extract `model` → `input_model` column
2. Parse `summary_dump` JSON, extract `usage.completion_tokens` → `output_tokens`
3. Compute `ended_at - started_at` → `latency_ms`
4. Build Arrow record batch (e.g., 1000 rows per batch)
5. Stream batch to client

### Tenancy enforcement

- Every query gets `project_id = ?` injected into WHERE clause
- Project ID comes from session parameter (required)
- Client must specify project via session option before querying
- W&B API key validated at connection time

## Client Usage Examples

### Python with PyArrow Flight

```python
from pyarrow import flight

# Connect with auth
client = flight.connect("grpc://flight.weave.example.com:8815")
client.authenticate(flight.BasicAuthClientMiddleware(
    username="api",
    password="wandb_api_key_here"
))

# Set project context (required)
client.set_session_options([("project_id", "vanpelt/openui-hosted")])

# Execute query
query = """
    SELECT op_name, input_model, output_tokens, latency_ms
    FROM calls
    WHERE started_at > '2024-01-01'
    LIMIT 1000
"""
info = client.execute(query)
reader = client.do_get(info.endpoints[0].ticket)

# Stream to pandas
df = reader.read_pandas()
```

### Python with ADBC (Arrow Database Connectivity)

```python
import adbc_driver_flightsql.dbapi as flight_sql

conn = flight_sql.connect(
    "grpc://flight.weave.example.com:8815",
    db_kwargs={
        "username": "api",
        "password": "wandb_api_key_here",
        "adbc.flight.sql.session.options": "project_id=vanpelt/openui-hosted"
    }
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM calls WHERE input_model = 'gpt-4' LIMIT 100")
df = cursor.fetch_arrow_table().to_pandas()
```

### DuckDB (via Arrow Flight SQL extension)

```sql
INSTALL arrow_flight_sql;
LOAD arrow_flight_sql;

ATTACH 'grpc://flight.weave.example.com:8815' AS weave (
    TYPE arrow_flight_sql,
    USER 'api',
    PASSWORD 'wandb_api_key_here',
    OPTION 'project_id=vanpelt/openui-hosted'
);

SELECT op_name, avg(latency_ms), sum(total_tokens)
FROM weave.calls
WHERE started_at > '2024-01-01'
GROUP BY op_name;
```

## Implementation Plan

### Directory structure

```
scripts/flight_server/
├── main.go                 # Entry point, server setup
├── auth.go                 # W&B API key validation
├── handler.go              # Flight SQL handler implementation
├── schema.go               # Table/column definitions
├── virtual_columns.go      # JSON path extraction, computed columns
├── clickhouse.go           # ClickHouse query execution
├── query_rewriter.go       # SQL parsing and rewrite logic
├── go.mod
├── go.sum
└── README.md
```

### Dependencies

- `github.com/apache/arrow/go/v15/arrow/flight/flightsql` - Flight SQL server
- `github.com/ClickHouse/clickhouse-go/v2` - ClickHouse native client
- `github.com/tidwall/gjson` - Fast JSON path extraction
- `github.com/xwb1989/sqlparser` or similar - SQL parsing for query rewrite

### Phases

#### Phase 1: Minimal Flight SQL server

- Basic Flight SQL server that responds to `GetTables`, `GetSchema`
- Hardcoded `calls` table schema
- Auth stub (accept any key for local testing)

#### Phase 2: ClickHouse integration

- Connect to ClickHouse via native protocol
- Execute simple queries, stream results as Arrow batches
- Inject `project_id` filter

#### Phase 3: Virtual columns

- Parse JSON in Go as rows stream
- Populate LLM and tracing virtual columns
- Support `json_extract()` function for arbitrary paths

#### Phase 4: Auth integration

- Validate W&B API key against API
- Cache auth results per session
- Enforce project access

#### Phase 5: Polish

- Error handling and logging
- Connection pooling
- Metrics/observability
- Documentation and examples

## Future Considerations

### ClickHouse JSON type

ClickHouse's new JSON type stores JSON in columnar format, making path extraction much faster than `JSONExtract*` on strings. A future optimization could:

1. Create a materialized table with JSON-typed columns for `inputs_dump`, `output_dump`
2. Update the Flight server to query the JSON columns directly
3. Push more filtering down to ClickHouse

### Additional tables

The architecture supports adding more tables:

- `objects` - Object versions (ops, models, datasets)
- `tables` - Dataset table metadata
- `table_rows` - Dataset row data

### Ref resolution

Could support automatic ref resolution in queries, e.g.:

```sql
SELECT resolve_ref(input_refs[1]) as input_dataset FROM calls
```
