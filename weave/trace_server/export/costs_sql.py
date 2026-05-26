"""Tier 2 cost-join SQL builder.

One Parquet row per `(call, model)`. The GROUP BY that `token_costs.py` uses
to collapse joined rows back into one-row-per-call is intentionally dropped:
the export's contract is flat per-model rows so consumers can filter / sum
in whatever tool they pull the file into.

Pricing-level ordering matches the calls UI:
    1. project-override row whose `pricing_level_id == {project_id:String}`
    2. default row whose `pricing_level_id IN ('default', '')`

Prices effective at or before the call's `started_at` rank ahead of prices
that took effect later, mirroring `token_costs.py`. Combined with the
(call, model) partition this means the export reflects the price that was
live when the call ran, not today's most-recent price. Calls with empty or
malformed `summary.usage` are filtered out so the Parquet is not polluted
with zero-cost rows.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from weave.trace_server.export.constants import (
    MAX_EXPORT_QUERY_SECONDS,
    PARQUET_COMPRESSION,
)
from weave.trace_server.export.escaping import named_collection_name
from weave.trace_server.export.schemas import ExportTable
from weave.trace_server.export.sql import PreparedSql
from weave.trace_server.export.table_registry import TABLE_REGISTRY

DUMMY_LLM_ID = "weave_dummy_llm_id"
LLM_TOKEN_PRICES_TABLE = "llm_token_prices"
DEFAULT_PRICING_LEVEL_ID = "default"

# Empty-string is the legacy "no level id" sentinel; the costs query filters
# the JOIN to (project_id, default, '') just like `token_costs.py` does.
PRICING_LEVEL_IDS = ("{project_id:String}", "'default'", "''")


USAGE_KV = (
    "arrayJoin(if(usage_raw != '' AND usage_raw != '{{}}', "
    "JSONExtractKeysAndValuesRaw(usage_raw), "
    f"[('{DUMMY_LLM_ID}', '{{}}')])) AS kv"
)


def build_cost_join_export_sql(
    *,
    job_id: UUID,
    table: ExportTable,
    project_id: str,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
) -> PreparedSql:
    """`INSERT INTO FUNCTION s3(<nc>, format='Parquet') SELECT ... LEFT JOIN llm_token_prices ...`.

    The inner subquery does `arrayJoin(JSONExtractKeysAndValuesRaw(summary.usage))`
    so one input call expands to one output row per model key. The LEFT JOIN
    attaches every candidate price; ROW_NUMBER picks the best one per
    `(call_id, model)` partition. Calls with no model in `summary.usage` are
    dropped via the dummy-llm filter.
    """
    spec = TABLE_REGISTRY[table]
    nc_name = named_collection_name(job_id)
    params: dict[str, Any] = {"project_id": project_id}

    predicates = [f"{spec.project_id_column} = {{project_id:String}}"]
    if time_start is not None:
        params["start_ts"] = time_start
        predicates.append(f"{spec.time_column} >= {{start_ts:DateTime64(3)}}")
    if time_end is not None:
        params["end_ts"] = time_end
        predicates.append(f"{spec.time_column} < {{end_ts:DateTime64(3)}}")
    where_clause = " AND ".join(predicates)

    pricing_in_clause = ", ".join(PRICING_LEVEL_IDS)

    # `lu.* EXCEPT (usage_raw, kv)` already projects every call column plus
    # the derived per-model columns (llm_id, requests, prompt_tokens, ...).
    # The outer SELECT only adds the `ltp.*` price columns to avoid the
    # duplicate-column emission that earlier versions of this query had.
    sql = f"""
INSERT INTO FUNCTION s3({nc_name}, format = 'Parquet')
SELECT
    ranked.* EXCEPT (usage_raw, kv, rnk)
FROM (
    SELECT
        lu.*,
        ltp.prompt_token_cost AS prompt_token_cost,
        ltp.completion_token_cost AS completion_token_cost,
        ltp.cache_read_input_token_cost AS cache_read_input_token_cost,
        ltp.cache_creation_input_token_cost AS cache_creation_input_token_cost,
        ltp.prompt_token_cost_unit AS prompt_token_cost_unit,
        ltp.completion_token_cost_unit AS completion_token_cost_unit,
        ltp.effective_date AS effective_date,
        ltp.pricing_level AS pricing_level,
        ROW_NUMBER() OVER (
            PARTITION BY lu.id, lu.llm_id
            ORDER BY
                CASE
                    WHEN lu.started_at >= ltp.effective_date THEN 1
                    ELSE 2
                END,
                CASE
                    WHEN ltp.pricing_level = 'project' AND ltp.pricing_level_id = {{project_id:String}} THEN 1
                    WHEN ltp.pricing_level = 'default' AND ltp.pricing_level_id = '{DEFAULT_PRICING_LEVEL_ID}' THEN 2
                    ELSE 3
                END,
                ltp.effective_date DESC
        ) AS rnk
    FROM (
        SELECT
            *,
            ifNull(JSONExtractRaw(summary_dump, 'usage'), '{{}}') AS usage_raw,
            {USAGE_KV},
            kv.1 AS llm_id,
            JSONExtractInt(kv.2, 'requests') AS requests,
            (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0)
                + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0))
                AS prompt_tokens,
            (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0)
                + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0))
                AS completion_tokens,
            JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
            JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
            JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
        FROM {spec.ch_table}
        WHERE {where_clause}
    ) AS lu
    LEFT JOIN {LLM_TOKEN_PRICES_TABLE} AS ltp
        ON lu.llm_id = ltp.llm_id
        AND ltp.pricing_level_id IN ({pricing_in_clause})
) AS ranked
WHERE ranked.rnk = 1 AND ranked.llm_id != '{DUMMY_LLM_ID}'
SETTINGS
    s3_truncate_on_insert = 1,
    max_execution_time = {MAX_EXPORT_QUERY_SECONDS},
    output_format_parquet_compression_method = '{PARQUET_COMPRESSION}'
"""
    return PreparedSql(sql=sql, params=params)
