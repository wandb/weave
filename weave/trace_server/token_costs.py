from . import trace_server_interface as tsi
from .orm import Column, PreparedSelect, Table

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
#     id,
#     started_at,
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
def get_llm_usage(table_alias: str) -> PreparedSelect:
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

    prepared_query = select_query.prepare(database_type="clickhouse")
    return prepared_query


# SELECT
#     lu.id,
#     lu.llm_id,
#     lu.started_at,
#     ltp.prompt_token_cost,
#     ltp.completion_token_cost,
#     ltp.effective_date,
#     ltp.pricing_level,
#     ltp.pricing_level_id,
#     ltp.provider_id,
#     lu.requests,
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
    project_id: str, llm_usage_table_alias: str = "llm_usage"
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
                -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_NAME THEN 1
                WHEN llm_token_prices.pricing_level = 'project' AND llm_token_prices.pricing_level_id = '{project_id}' THEN 2
                WHEN llm_token_prices.pricing_level = 'default' AND llm_token_prices.pricing_level_id = 'default' THEN 3
                ELSE 4
            END,
            llm_token_prices.effective_date DESC
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
                            {"$getField": "llm_token_prices.llm_id"},
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
                            {"$getField": "llm_token_prices.effective_date"},
                        ]
                    }
                }
            )
        )
    )

    prepared_query = select_query.prepare(database_type="clickhouse")
    return prepared_query


# SELECT
#     id,
#     llm_id,
#     prompt_token_cost,
#     completion_token_cost,
#     effective_date,
#     pricing_level,
#     pricing_level_id,
#     provider_id
# FROM
#     {table_alias}
# WHERE
#     rank = 1
# From the ranked prices, get the top ranked price for each llm_id
def get_top_ranked_prices(table_alias: str) -> PreparedSelect:
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

    prepared_query = select_query.prepare(database_type="clickhouse")
    return prepared_query


# SELECT
#     lu.id,
#     lu.llm_id,
#     lu.requests,
#     lu.prompt_tokens,
#     lu.completion_tokens,
#     lu.total_tokens,
#     lu.requests,
#     trp.effective_date,
#     trp.pricing_level,
#     trp.pricing_level_id,
#     trp.prompt_token_cost AS prompt_token_cost,
#     trp.completion_token_cost AS completion_token_cost,
#     trp.provider_id,
#     prompt_tokens * prompt_token_cost AS prompt_tokens_cost,
#     completion_tokens * completion_token_cost AS completion_tokens_cost
# FROM
#     {usage_table_alias} AS lu
# LEFT JOIN
#     {price_table_alias} AS trp
# ON
#     lu.id = trp.id AND lu.llm_id = trp.llm_id
# Join the call usage data with the top ranked prices to get the token costs
def join_usage_with_costs(
    usage_table_alias: str, price_table_alias: str
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

    prepared_select = select_query.prepare(database_type="clickhouse")
    return prepared_select
