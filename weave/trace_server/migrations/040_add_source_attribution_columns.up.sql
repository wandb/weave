-- Promote source/integration attribution to columns on every row-bearing table:
-- spans, call_parts -> calls_merged, and calls_complete.
--
-- source_name    the instrumentation that produced the row (openai, langchain,
--                codex, claude_code, ...), resolved server-side on ingest by
--                the ladder in weave/trace_server/source_attribution.py.
-- source_version version of that instrumentation.
-- source_sdk     the ingest surface it arrived on: 'weave' (trace-server call
--                API) or 'otlp' (OTel trace export).
--
-- Not to be confused with the existing calls_complete.source column, which
-- records the *write path* that produced the row (direct / dual / migration).
--
-- Forward-only: existing rows read '' (or NULL on the legacy nullable tables).
-- Backfilling from attributes_dump / custom_attrs_string would only recover the
-- slice that already stamps attributes["integration"] and is expensive on
-- calls_merged, so it is deliberately skipped.

-- ---------------------------------------------------------------------------
-- spans
-- ---------------------------------------------------------------------------
-- LowCardinality for name/sdk: bounded by the integration catalog, which makes
-- GROUP BY source_name and WHERE source_name = ... cheap. Plain String for
-- source_version -- a long tail of pinned versions would bloat the dictionary.
ALTER TABLE spans
    ADD COLUMN IF NOT EXISTS source_name    LowCardinality(String) DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_version String DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_sdk     LowCardinality(String) DEFAULT '';

-- No skip index, unlike idx_eval_run_id in migration 037. Every span has a
-- source_name and a project typically emits only a handful of distinct values,
-- interleaved in time -- so nearly every granule holds every value and an index
-- would skip almost nothing while still costing insert time and disk. The
-- queries this serves are either GROUP BY source_name (a full scan regardless)
-- or narrowed by project_id + started_at, which the ORDER BY already prunes.

-- ---------------------------------------------------------------------------
-- call_parts -> calls_merged
-- ---------------------------------------------------------------------------
-- Nullable here rather than LowCardinality-with-'' to match every other
-- call_parts column, and because NULL is load-bearing: only the call-start part
-- carries attribution, so the call-end part writes NULL and anySimpleState
-- skips it, exactly as it does for op_name and turn_id.
ALTER TABLE call_parts
    ADD COLUMN IF NOT EXISTS source_name    Nullable(String) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS source_version Nullable(String) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS source_sdk     Nullable(String) DEFAULT NULL;

ALTER TABLE calls_merged
    ADD COLUMN IF NOT EXISTS source_name    SimpleAggregateFunction(any, Nullable(String)),
    ADD COLUMN IF NOT EXISTS source_version SimpleAggregateFunction(any, Nullable(String)),
    ADD COLUMN IF NOT EXISTS source_sdk     SimpleAggregateFunction(any, Nullable(String));

ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleState(wb_run_step) as wb_run_step,
        anySimpleState(wb_run_step_end) as wb_run_step_end,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
        anySimpleState(thread_id) as thread_id,
        anySimpleState(turn_id) as turn_id,
        anySimpleState(op_name) as op_name,
        anySimpleState(started_at) as started_at,
        anySimpleState(attributes_dump) as attributes_dump,
        anySimpleState(inputs_dump) as inputs_dump,
        array_concat_aggSimpleState(input_refs) as input_refs,
        anySimpleState(ended_at) as ended_at,
        anySimpleState(output_dump) as output_dump,
        anySimpleState(summary_dump) as summary_dump,
        anySimpleState(exception) as exception,
        array_concat_aggSimpleState(output_refs) as output_refs,
        anySimpleState(deleted_at) as deleted_at,
        argMaxState(display_name, call_parts.created_at) as display_name,
        anySimpleState(coalesce(call_parts.started_at, call_parts.ended_at, call_parts.created_at)) as sortable_datetime,
        anySimpleState(otel_dump) as otel_dump,
        minSimpleState(expire_at) as expire_at,
        anySimpleState(source_name) as source_name,
        anySimpleState(source_version) as source_version,
        anySimpleState(source_sdk) as source_sdk
    FROM call_parts
    GROUP BY project_id,
        id;

-- ---------------------------------------------------------------------------
-- calls_complete
-- ---------------------------------------------------------------------------
-- Non-nullable with the '' sentinel, matching the rest of calls_complete; the
-- read path maps '' back to None via ch_sentinel_values.
ALTER TABLE calls_complete
    ADD COLUMN IF NOT EXISTS source_name    LowCardinality(String) DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_version String DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_sdk     LowCardinality(String) DEFAULT '';

-- calls_merged_stats / calls_complete_stats are deliberately untouched: they
-- exist for per-call size accounting and thread rollups, neither of which reads
-- attribution. Billing is unaffected on spans too -- spans_stats bills
-- length(raw_span_dump) alone (migration 034), and these columns are derived
-- from data already inside that dump.
