# Cost query payload hydration

`WF_CLICKHOUSE_COMPACT_COST_QUERIES=true` opts a trace-server deployment into
compact cost enrichment; it defaults to false until rollout verification.
`calls_query_stream` uses the compact query when its read produces
one row per call key: aggregated `calls_merged` uses `(id)`; `calls_complete`
with the existing `latest_only=True`/`FINAL` setting uses `(id, started_at)`. The internal
`costs_have_unique_call_keys` flag records that guarantee; other builder callers
retain the existing query by default.

The selected page remains upstream of cost enrichment. `llm_usage` projects
only `id`, `started_at`, and extracted usage; price joins and windows therefore
cannot carry inputs, outputs, attributes, raw spans, full summaries, or storage columns. Costs
are aggregated by call key into a JSON fragment. The requested payload and
original summary are joined back afterwards and the cost fragment is appended.
Final output column order still follows `get_cost_result_columns`, and final
ordering is applied after hydration. Pricing precedence and cost formulas use
the existing implementation.

The join is project scoped on both sides. Do not enable it for physical
`calls_complete` reads without `FINAL`: multiple versions can share an ID.
Feedback ordering retains the existing path because the feedback join's
aggregation can affect row multiplicity and ordering. Object-reference expansion
and distributed-server mode also retain the existing query until their joins
and topology have equivalent coverage. Pages without a complete call-key tie-breaker retain
the existing query because repeated CTE evaluation can pick different pages.

The server enables this path only when its cached ClickHouse capability map
contains `enable_shared_storage_snapshot_in_query` and allows setting it to 1.
It explicitly sends that setting for the request. Missing capabilities or an
immutable disabled setting fall back to the existing query. Shared snapshots
keep repeated table reads consistent under concurrent writes; this setting was
introduced in ClickHouse 25.6. See the [release documentation](https://clickhouse.com/blog/clickhouse-release-25-06).

ClickHouse expands ordinary CTEs at each reference. This design trades a second
evaluation of the selected call relation for a smaller price window and
aggregation. Column pruning can avoid reading payload columns in the cost
branch, but base filters, ordering, and storage calculations can still be
expensive. It does not bound unpaged queries, eliminate large usage objects, or
provide admission/concurrency control.

Before deploying, compare complete responses, `EXPLAIN`/column pruning,
`system.query_log` peak memory, rows/bytes read, and elapsed time on representative
wide and narrow calls, with storage and object expansion enabled. Measure both
single-node and distributed topologies, including version races and price ties.
The local differential tests are synthetic correctness checks, not evidence of
customer recovery.

## Local synthetic measurement

ClickHouse 26.6.8.7, four threads, 64 calls with 128 KiB of combined input/output
payload and 64 KiB of non-usage summary per call, two usage models per call and
24 price-history rows per model:
two alternating baseline/compact runs returned identical complete results.
Baseline tracked peak memory was 1150.2 and 1502.2 MiB; compact peak memory was
43.7 MiB in both runs. Query durations were 292/324 ms versus 37/32 ms. Read rows
increased from 112 to 176, and bytes read increased from 12.0 to 16.0 MiB.
This measures the cost stage over a simple selected-call relation; it does not
measure the full request, customer schema, distributed mode, or concurrency.

With a local ClickHouse instance listening on port 18129, reproduce with:

```bash
uv run --python 3.12 --group test --extra trace_server python scripts/benchmark_compact_cost_query.py --port 18129 --rows 64
```

The script creates and drops its own UUID-named database on localhost. It prints
measurements and saves SQL, explain plans, and JSON evidence in a temporary
directory, or in the requested `--output-dir`.
