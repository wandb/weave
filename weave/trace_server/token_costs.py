from . import trace_server_interface as tsi
from .orm import Column, ParamBuilder, PreparedSelect, Table

LLM_TOKEN_PRICES_COLUMNS = [
    Column(name="pricing_level", type="string"),
    Column(name="pricing_level_id", type="string"),
    Column(name="provider_id", type="string"),
    Column(name="llm_id", type="string"),
    Column(name="effective_date", type="datetime"),
    Column(name="prompt_token_cost", type="float"),
    Column(name="completion_token_cost", type="float"),
]
LLM_TOKEN_PRICES_TABLE_NAME = "llm_token_prices"
LLM_TOKEN_PRICES_TABLE = Table(
    name=LLM_TOKEN_PRICES_TABLE_NAME, cols=LLM_TOKEN_PRICES_COLUMNS
)

CALLS_MERGED_COLUMNS = [
    Column(name="project_id", type="string"),
    Column(name="id", type="string"),
    Column(name="trace_id", type="string"),
    Column(name="parent_id", type="string"),
    Column(name="op_name", type="string"),
    Column(name="started_at", type="datetime"),
    Column(name="attributes_dump", type="string"),
    Column(name="inputs_dump", type="string"),
    Column(name="ended_at", type="datetime"),
    Column(name="output_dump", type="string"),
    Column(name="summary_dump", type="string"),
    Column(name="exception", type="string"),
    Column(name="wb_user_id", type="string"),
    Column(name="wb_run_id", type="string"),
    Column(name="deleted_at", type="datetime"),
    Column(name="display_name", type="string"),
    # These are Array(String) in the original table
    Column(name="input_refs", type="json"),
    Column(name="output_refs", type="json"),
]


def calls_merged_table(table_alias: str) -> Table:
    return Table(table_alias, CALLS_MERGED_COLUMNS)


LLM_USAGE_COLUMNS = [
    Column(name="id", type="string"),
    Column(name="llm_id", type="string"),
    Column(name="requests", type="float"),
    Column(name="prompt_tokens", type="float"),
    Column(name="completion_tokens", type="float"),
    Column(name="total_tokens", type="float"),
]


# SELECT
#     id, started_at,
#     ifNull(JSONExtractRaw(summary_dump, 'usage'), '{{}}') AS usage_raw,
#     arrayJoin(
#         arrayMap(
#             kv -> (kv.1, kv.2),
#             JSONExtractKeysAndValuesRaw(usage_raw)
#         )
#     ) AS kv,
#     kv.1 AS llm_id,
#     JSONExtractInt(kv.2, 'requests') AS requests,
#     -- Some libraries return prompt_tokens and completion_tokens, others prompt_tokens and completion_tokens
#     if(
#         JSONHas(kv.2, 'prompt_tokens'),
#         JSONExtractInt(kv.2, 'prompt_tokens'),
#         JSONExtractInt(kv.2, 'input_tokens')
#     ) AS prompt_tokens,
#     if(
#         JSONHas(kv.2, 'completion_tokens'),
#         JSONExtractInt(kv.2, 'completion_tokens'),
#         JSONExtractInt(kv.2, 'output_tokens')
#     ) AS completion_tokens,
#     JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
# FROM
#     {table_alias}
# WHERE
#     JSONLength(usage_raw) > 0
# From a calls table alias, get the usage data for LLMs
def get_llm_usage(param_builder: ParamBuilder, table_alias: str) -> PreparedSelect:
    all_calls_table = calls_merged_table(table_alias)

    # Select fields
    usage_raw = "ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw"
    kv = "arrayJoin(arrayMap(kv -> (kv.1, kv.2), JSONExtractKeysAndValuesRaw(usage_raw))) AS kv"
    llm_id = "kv.1 AS llm_id"
    requests = "JSONExtractInt(kv.2, 'requests') AS requests"
    prompt_tokens = """if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens"""
    completion_tokens = """if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens"""
    total_tokens = "JSONExtractInt(kv.2, 'total_tokens') AS total_tokens"

    select_query = (
        all_calls_table.select()
        .fields(
            [
                "id",
                "started_at",
                usage_raw,
                kv,
                llm_id,
                requests,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ]
        )
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$not": [
                            {"$eq": [{"$getField": "usage_raw"}, {"$literal": "{}"}]},
                        ]
                    }
                }
            )
        )
    )

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


# SELECT
#     lu.id, lu.llm_id, lu.started_at, ltp.prompt_token_cost, ltp.completion_token_cost, ltp.effective_date, ltp.pricing_level, ltp.pricing_level_id, ltp.provider_id, lu.requests,
#     ROW_NUMBER() OVER (
#         PARTITION BY lu.id, lu.llm_id
#         ORDER BY
#             CASE
#                 -- Order by pricing level then by effective_date
#                 -- WHEN ltp.pricing_level = 'org' AND ltp.pricing_level_id = ORG_NAME THEN 1
#                 WHEN ltp.pricing_level = 'project' AND ltp.pricing_level_id = '{self.project_id}' THEN 2
#                 WHEN ltp.pricing_level = 'default' AND ltp.pricing_level_id = 'default' THEN 3
#                 ELSE 4
#             END,
#             ltp.effective_date DESC
#     ) AS rank
# FROM
#     {table_alias} AS lu
# LEFT JOIN
#     llm_token_prices AS ltp
# ON
#     lu.llm_id = ltp.llm_id
# WHERE
#     ltp.effective_date <= lu.started_at
# From an llm usage query, get the ranked prices for each llm_id in the usage data
def get_ranked_prices(
    param_builder: ParamBuilder, llm_usage_table_alias: str, project_id: str
) -> PreparedSelect:
    llm_usage_cols = [
        *LLM_USAGE_COLUMNS,
        Column(name="started_at", type="datetime"),
    ]

    llm_usage_table = Table(name=llm_usage_table_alias, cols=llm_usage_cols)

    # Select fields
    lu_fields = [f"{llm_usage_table_alias}.{col.name}" for col in llm_usage_table.cols]
    ltp_fields = [
        f"{LLM_TOKEN_PRICES_TABLE.name}.{col.name}" for col in LLM_TOKEN_PRICES_COLUMNS
    ]
    row_number_clause = f"""
        ROW_NUMBER() OVER (
        PARTITION BY {llm_usage_table_alias}.id, {llm_usage_table_alias}.llm_id
        ORDER BY
            CASE
                -- Order by pricing level then by effective_date
                -- WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = 'org' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = ORG_NAME THEN 1
                WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = 'project' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = '{project_id}' THEN 2
                WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = 'default' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = 'default' THEN 3
                ELSE 4
            END,
            {LLM_TOKEN_PRICES_TABLE_NAME}.effective_date DESC
    ) AS rank
    """

    select_query = (
        llm_usage_table.select()
        .fields([*lu_fields, *ltp_fields, row_number_clause])
        .join(
            "LEFT",
            LLM_TOKEN_PRICES_TABLE,
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": f"{llm_usage_table_alias}.llm_id"},
                            {"$getField": f"{LLM_TOKEN_PRICES_TABLE_NAME}.llm_id"},
                        ]
                    }
                }
            ),
        )
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$gte": [
                            {"$getField": f"{llm_usage_table_alias}.started_at"},
                            {
                                "$getField": f"{LLM_TOKEN_PRICES_TABLE_NAME}.effective_date"
                            },
                        ]
                    }
                }
            )
        )
    )

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


# SELECT
#     id, llm_id, prompt_token_cost, completion_token_cost, effective_date, pricing_level, pricing_level_id, provider_id
# FROM
#     {table_alias}
# WHERE
#     rank = 1
# From the ranked prices, get the top ranked price for each llm_id
def get_top_ranked_prices(
    param_builder: ParamBuilder, table_alias: str
) -> PreparedSelect:
    columns = [
        Column(name="id", type="string"),
        *LLM_TOKEN_PRICES_COLUMNS,
        Column(name="rank", type="string"),
    ]

    table = Table(name=table_alias, cols=columns)
    select_query = (
        table.select()
        .fields([col.name for col in table.cols])
        .where(
            tsi.Query(**{"$expr": {"$eq": [{"$getField": "rank"}, {"$literal": 1}]}})
        )
    )

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


# SELECT
#     lu.id, lu.llm_id, lu.requests, lu.prompt_tokens, lu.completion_tokens, lu.total_tokens, lu.requests, trp.effective_date, trp.pricing_level, trp.pricing_level_id, trp.prompt_token_cost AS prompt_token_cost, trp.completion_token_cost AS completion_token_cost, trp.provider_id, prompt_tokens * prompt_token_cost AS prompt_tokens_cost, completion_tokens * completion_token_cost AS completion_tokens_cost
# FROM
#     {usage_table_alias} AS lu
# LEFT JOIN
#     {price_table_alias} AS trp
# ON
#     lu.id = trp.id AND lu.llm_id = trp.llm_id


# Join the call usage data with the top ranked prices to get the token costs
def join_usage_with_costs(
    param_builder: ParamBuilder, usage_table_alias: str, price_table_alias: str
) -> PreparedSelect:
    price_columns = [
        Column(name="id", type="string"),
        *LLM_TOKEN_PRICES_COLUMNS,
    ]

    usage_table = Table(name=usage_table_alias, cols=LLM_USAGE_COLUMNS)
    price_table = Table(name=price_table_alias, cols=price_columns)

    join_condition = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": f"{usage_table_alias}.id"},
                            {"$getField": f"{price_table_alias}.id"},
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": f"{usage_table_alias}.llm_id"},
                            {"$getField": f"{price_table_alias}.llm_id"},
                        ]
                    },
                ]
            }
        }
    )

    usage_select_columns = [
        f"{usage_table_alias}.{col.name}" for col in usage_table.cols
    ]
    price_select_columns = [
        f"{price_table_alias}.{col.name}"
        for col in price_table.cols
        if col.name != "id"
    ]

    select_query = (
        usage_table.select()
        .fields(
            [
                *usage_select_columns,
                *price_select_columns,
                "prompt_tokens * prompt_token_cost AS prompt_tokens_cost",
                "completion_tokens * completion_token_cost AS completion_tokens_cost",
            ]
        )
        .join("LEFT", price_table, join_condition)
    )

    prepared_select = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_select


# SELECT
#       all_calls.project_id AS project_id, all_calls.id AS id, any(all_calls.op_name) AS op_name, all_calls.display_name, any(all_calls.trace_id) AS trace_id, any(all_calls.parent_id) AS parent_id, any(all_calls.started_at) AS started_at, any(all_calls.ended_at) AS ended_at, any(all_calls.exception) AS exception, array_concat_agg(all_calls.input_refs) AS input_refs, array_concat_agg(all_calls.output_refs) AS output_refs, any(all_calls.wb_user_id) AS wb_user_id, any(all_calls.wb_run_id) AS wb_run_id, any(all_calls.deleted_at) AS deleted_at, any(all_calls.attributes_dump) AS attributes_dump, any(all_calls.inputs_dump) AS inputs_dump, any(all_calls.output_dump) AS output_dump,
#       -- Creates the cost object as a JSON string
#       concat(
#           -- Remove the last closing brace
#           left(any(all_calls.summary_dump), length(any(all_calls.summary_dump)) - 1),
#           ',"costs":',
#           concat('{', arrayStringConcat(groupUniqArray(
#               concat('"', llm_id, '":{',
#                   '"prompt_tokens":', toString(prompt_tokens), ',',
#                   '"prompt_tokens_cost":', toString(prompt_tokens_cost), ',',
#                   '"completion_tokens_cost":', toString(completion_tokens_cost), ',',
#                   '"completion_tokens":', toString(completion_tokens), ',',
#                   '"prompt_token_cost":', toString(prompt_token_cost), ',',
#                   '"completion_token_cost":', toString(completion_token_cost), ',',
#                   '"total_tokens":', toString(total_tokens), ',',
#                   '"requests":', toString(requests), ',',
#                   '"effective_date":"', toString(effective_date), '",',
#                   '"provider_id":"', toString(provider_id), '",',
#                   '"pricing_level":"', toString(pricing_level), '",',
#                   '"pricing_level_id":"', toString(pricing_level_id), '"}')
#           ), ','), '}'),
#       '}'
#       ) AS summary_dump
# FROM all_calls
# JOIN usage_with_costs
#     ON all_calls.id = usage_with_costs.id
# GROUP BY (all_calls.id, all_calls.project_id, all_calls.display_name)


# From a calls like table, select all fields specified and add the cost object to the summary_dump
def final_call_select_with_cost(
    param_builder: ParamBuilder,
    call_table_alias: str,
    price_table_alias: str,
    select_fields: list[str],
) -> PreparedSelect:
    cost_snippet = """concat(
        '{',
        arrayStringConcat(groupUniqArray(
            concat(
                '"', llm_id, '":{',
                '"prompt_tokens":', toString(prompt_tokens), ',',
                '"prompt_tokens_cost":', toString(prompt_tokens_cost), ',',
                '"completion_tokens_cost":', toString(completion_tokens_cost), ',',
                '"completion_tokens":', toString(completion_tokens), ',',
                '"prompt_token_cost":', toString(prompt_token_cost), ',',
                '"completion_token_cost":', toString(completion_token_cost), ',',
                '"total_tokens":', toString(total_tokens), ',',
                '"requests":', toString(requests), ',',
                '"effective_date":"', toString(effective_date), '",',
                '"provider_id":"', toString(provider_id), '",',
                '"pricing_level":"', toString(pricing_level), '",',
                '"pricing_level_id":"', toString(pricing_level_id), '"}'
            )
        ), ','),
        '}'
    )"""
    summary_dump_snippet = f"""concat(
        left(any({call_table_alias}.summary_dump), length(any({call_table_alias}.summary_dump)) - 1),
        ',"costs":',
        {cost_snippet},
        '}}'
    ) AS summary_dump"""

    usage_with_costs_fields = [
        *[col for col in LLM_USAGE_COLUMNS if col.name != "llm_id"],
        *LLM_TOKEN_PRICES_COLUMNS,
        Column(name="prompt_tokens_cost", type="float"),
        Column(name="completion_tokens_cost", type="float"),
    ]

    usage_with_costs_table = Table(price_table_alias, usage_with_costs_fields)
    all_calls_table = calls_merged_table(call_table_alias)

    final_query = (
        all_calls_table.select()
        .fields([*select_fields, summary_dump_snippet])
        .join(
            "",
            usage_with_costs_table,
            tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": f"{call_table_alias}.id"},
                            {"$getField": f"{price_table_alias}.id"},
                        ]
                    }
                }
            ),
        )
        .group_by(
            [
                f"{call_table_alias}.id",
                f"{call_table_alias}.project_id",
                f"{call_table_alias}.display_name",
            ]
        )
    )

    final_prepared_query = final_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return final_prepared_query
