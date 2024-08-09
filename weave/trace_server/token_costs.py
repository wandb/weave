from datetime import datetime

from . import trace_server_interface as tsi
from .clickhouse_schema import SelectableCHCallSchema
from .orm import Column, ColumnType, ParamBuilder, PreparedSelect, Table

cost_string_fields = [
    "prompt_token_cost_unit",
    "completion_token_cost_unit",
    "effective_date",
    "provider_id",
    "pricing_level",
    "pricing_level_id",
    "created_by",
    "created_at",
]

cost_numeric_fields = [
    "prompt_token_cost",
    "completion_token_cost",
    "prompt_tokens_cost",
    "completion_tokens_cost",
    "prompt_tokens",
    "completion_tokens",
    "requests",
    "total_tokens",
]

LLM_TOKEN_PRICES_COLUMNS = [
    Column(name="pricing_level", type="string"),
    Column(name="pricing_level_id", type="string"),
    Column(name="provider_id", type="string"),
    Column(name="llm_id", type="string"),
    Column(name="effective_date", type="datetime"),
    Column(name="prompt_token_cost", type="float"),
    Column(name="completion_token_cost", type="float"),
    Column(name="prompt_token_cost_unit", type="string"),
    Column(name="completion_token_cost_unit", type="string"),
    Column(name="created_by", type="string"),
    Column(name="created_at", type="datetime"),
]

LLM_TOKEN_PRICES_TABLE_NAME = "llm_token_prices"
LLM_TOKEN_PRICES_TABLE = Table(
    name=LLM_TOKEN_PRICES_TABLE_NAME, cols=LLM_TOKEN_PRICES_COLUMNS
)


def get_calls_merged_columns() -> list[Column]:
    fields = SelectableCHCallSchema.model_fields.items()
    columns = []
    for field_name, field_info in fields:
        field_type: ColumnType = "string"
        if field_info.annotation == datetime:
            field_type = "datetime"
        columns.append(Column(name=field_name, type=field_type))
    return columns


def calls_merged_table(table_alias: str) -> Table:
    return Table(table_alias, get_calls_merged_columns())


LLM_USAGE_COLUMNS = [
    Column(name="id", type="string"),
    Column(name="llm_id", type="string"),
    Column(name="requests", type="float"),
    Column(name="prompt_tokens", type="float"),
    Column(name="completion_tokens", type="float"),
    Column(name="total_tokens", type="float"),
]


# SELECT
#     Extracted Usage Fields
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
#     -- If prompt_tokens is not present, we use input_tokens
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
    cols = [
        *get_calls_merged_columns(),
        # Derived cols that we will select
        Column(name="usage_raw", type="string"),
        Column(name="kv", type="string"),
        Column(name="llm_id", type="string"),
        Column(name="requests", type="float"),
        Column(name="prompt_tokens", type="float"),
        Column(name="completion_tokens", type="float"),
        Column(name="total_tokens", type="float"),
    ]

    all_calls_table = Table(table_alias, cols)

    # Select fields
    usage_raw = "ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw"
    kv = "arrayJoin(JSONExtractKeysAndValuesRaw(usage_raw)) AS kv"
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
#     llm_usage_fields,
#     price_fields,
#     DERIVED_RANK_FIELD as rank
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

    derived_llm_usage_cols = [
        Column(name="rank", type="string"),
    ]

    llm_usage_table = Table(
        name=llm_usage_table_alias, cols=[*llm_usage_cols, *derived_llm_usage_cols]
    )

    # Select fields
    lu_fields = [f"{llm_usage_table_alias}.{col.name}" for col in llm_usage_cols]
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
            "LEFT",
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
#     price_fields
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
    ]

    derived_columns = [
        Column(name="rank", type="string"),
    ]

    table = Table(name=table_alias, cols=[*columns, *derived_columns])
    select_query = (
        table.select()
        .fields([col.name for col in columns])
        .where(
            tsi.Query(**{"$expr": {"$eq": [{"$getField": "rank"}, {"$literal": 1}]}})
        )
    )

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


# SELECT
#     llm_usage fields
#     price_fields
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

    derived_price_columns = [
        Column(name="prompt_tokens_cost", type="float"),
        Column(name="completion_tokens_cost", type="float"),
    ]

    usage_table = Table(name=usage_table_alias, cols=LLM_USAGE_COLUMNS)
    price_table = Table(
        name=price_table_alias, cols=[*price_columns, *derived_price_columns]
    )

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
        f"{price_table_alias}.{col.name}" for col in price_columns if col.name != "id"
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
        .join(price_table, join_condition, "LEFT")
    )

    prepared_select = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_select


# SELECT
#   SELECT_FIELDS, (Passed in as a list)
#   CONSTRUCTED_SUMMARY_OBJECT AS summary_dump
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
    numeric_fields_str = " ".join(
        [
            f""" '"{field}":', toString({field}), ',', """
            for field in cost_numeric_fields
        ]
    )
    string_fields_str = """ '",', """.join(
        [f""" '"{field}":"', toString({field}), """ for field in cost_string_fields]
    )

    cost_snippet = f"""
    ',"weave":{{',
        '"costs":',
        concat(
            '{{',
            arrayStringConcat(
                groupUniqArray(
                    concat(
                        '"', toString(llm_id), '":{{',
                        {numeric_fields_str}
                        {string_fields_str}
                    '"}}'
                    )
                ), ','
            ),
            '}} }}'
        )
    """

    summary_dump_snippet = f"""
    concat(
        left(any({call_table_alias}.summary_dump), length(any({call_table_alias}.summary_dump)) - 1),
        {cost_snippet},
        '}}'
    ) AS summary_dump
    """

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
        .group_by(select_fields)
    )

    final_prepared_query = final_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return final_prepared_query


# From a calls query we get the llm ids in the usage data
# Then the prices and rank them
# We get the top ranked prices and discard the rest
# We join the top ranked prices with the usage data to get the token costs
# Finally we pull all the data from the calls and add a costs object
def cost_query(
    pb: ParamBuilder,
    call_table_alias: str,
    project_id: str,
    select_fields: list[str],
) -> str:
    # because we are selecting from a subquery, we need to prefix the fields
    # We also filter out summary_dump, because we add costs to summary dump in the select statement
    final_select_fields = [
        call_table_alias + "." + field
        for field in select_fields
        if field != "summary_dump"
    ]

    raw_sql = f"""
        -- From the all_calls we get the usage data for LLMs
        llm_usage AS ({get_llm_usage(pb, call_table_alias).sql}),

        -- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
        ranked_prices AS ({get_ranked_prices(pb, "llm_usage", project_id).sql}),

        -- Discard all but the top-ranked prices for each llm_id and call id
        top_ranked_prices AS ({get_top_ranked_prices(pb, "ranked_prices").sql}),

        -- Join with the top-ranked prices to get the token costs
        usage_with_costs AS ({join_usage_with_costs(pb, "llm_usage", "top_ranked_prices").sql})

        -- Final Select, which just pulls all the data from all_calls, and adds a costs object
        {final_call_select_with_cost(pb, 'all_calls', 'usage_with_costs', final_select_fields).sql}
    """
    return raw_sql
