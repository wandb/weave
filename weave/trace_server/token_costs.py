import base64
import re
from datetime import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import SelectableCHCallSchema
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.orm import (
    Column,
    ColumnType,
    ParamBuilder,
    PreparedSelect,
    Table,
)
from weave.trace_server.validation import (
    validate_purge_req_multiple,
    validate_purge_req_one,
)

DUMMY_LLM_ID = "weave_dummy_llm_id"
DUMMY_LLM_USAGE = (
    '{"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}'
)
ESCAPED_DUMMY_LLM_USAGE = DUMMY_LLM_USAGE.replace('"', '\\"')


# Org is currently not implemented
PRICING_LEVELS = {"ORG": "org", "PROJECT": "project", "DEFAULT": "default"}
DEFAULT_PRICING_LEVEL_ID = "default"
COST_OBJECT_NAME = "costs"

LLM_USAGE_COLUMNS = [
    Column(name="id", type="string"),
    Column(name="llm_id", type="string"),
    Column(name="requests", type="float"),
    Column(name="prompt_tokens", type="float"),
    Column(name="completion_tokens", type="float"),
    Column(name="total_tokens", type="float"),
]


LLM_TOKEN_PRICES_COLUMNS = [
    Column(name="id", type="string"),
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


def get_optional_join_field_columns() -> list[Column]:
    return [
        # These two columns are added here, because the ORM will validate that
        # the table contains those columns in case any of the storage size column
        # is included.
        Column(name="storage_size_bytes", type="float"),
        Column(name="total_storage_size_bytes", type="float"),
    ]


# SELECT
#     *,
#     Extracted Usage Fields
#     ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
#     arrayJoin(
#         if(usage_raw != '',
#         JSONExtractKeysAndValuesRaw(usage_raw),
#         [('nothing', '{"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}')])
#     ) AS kv,
#     kv.1 AS llm_id,
#     JSONExtractInt(kv.2, 'requests') AS requests,
#     if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
#     if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
#     JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
# FROM all_calls
# From a calls table alias, get the usage data for LLMs
"""
    Takes in something like the following:
    1 call row
        [ id, summary_dump: {usage: { llm_1, llm_2}} ]

    Returns something like the following:
    2 rows
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens ]
"""


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
    # This arrayJoin is used to split the usage data into rows each usage instance their own row
    # Here to handle the case where usage_raw is empty, we use a dummy tuple, to ensure that we always have a row
    # We wont return a cost object in the final select if we have a dummy llm_id
    # Note: The dummy tuple needs explicit string formatting for ClickHouse array literal syntax.
    # We escape the inner JSON quotes for the SQL string literal.
    kv = f"""arrayJoin(
                if(usage_raw != '' and usage_raw != '{{}}',
                JSONExtractKeysAndValuesRaw(usage_raw),
                [('{DUMMY_LLM_ID}', '{ESCAPED_DUMMY_LLM_USAGE}')])
            ) AS kv"""
    llm_id = "kv.1 AS llm_id"
    requests = "JSONExtractInt(kv.2, 'requests') AS requests"
    # Some libraries return prompt_tokens and completion_tokens, others prompt_tokens and completion_tokens
    # prompt_tokens is not present, we use input_tokens
    prompt_tokens = """if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens"""
    completion_tokens = """if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens"""
    total_tokens = "JSONExtractInt(kv.2, 'total_tokens') AS total_tokens"

    select_query = all_calls_table.select().fields(
        [
            "*",
            usage_raw,
            kv,
            llm_id,
            requests,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ]
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
# ON llm_usage.llm_id = llm_token_prices.llm_id
# From an llm usage query, get the ranked prices for each llm_id in the usage data
"""
    Takes in something like the following:
    2 rows
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens ]

    Returns something like the following:
    4 rows
         [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]

        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]
"""


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

    ltp_fields = [
        f"{LLM_TOKEN_PRICES_TABLE.name}.{col.name}" for col in LLM_TOKEN_PRICES_COLUMNS
    ]

    # Clickhouse does not allow parameters in the row_number() over function
    # This is a temporary workaround, to check the validity of the project_id, to prevent SQL injection
    is_project_id_sql_injection_safe(project_id)

    row_number_clause = f"""
        ROW_NUMBER() OVER (
        PARTITION BY {llm_usage_table_alias}.id, {llm_usage_table_alias}.llm_id
        ORDER BY
            CASE
                -- Order by effective_date
                WHEN {llm_usage_table_alias}.started_at >= {LLM_TOKEN_PRICES_TABLE_NAME}.effective_date THEN 1
                ELSE 2
            END,
            CASE
                -- Order by pricing level then by effective_date
                -- WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = '{PRICING_LEVELS['ORG']}' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = ORG_PARAM THEN 1
                WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = '{PRICING_LEVELS['PROJECT']}' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = '{project_id}' THEN 2
                WHEN {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level = '{PRICING_LEVELS['DEFAULT']}' AND {LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id = '{DEFAULT_PRICING_LEVEL_ID}' THEN 3
                ELSE 4
            END,
            {LLM_TOKEN_PRICES_TABLE_NAME}.effective_date DESC
    ) AS rank
    """

    select_query = (
        llm_usage_table.select()
        .fields(["*", *ltp_fields, row_number_clause])
        .where(
            tsi.Query(
                **{
                    "$expr": {
                        "$or": [
                            {
                                "$eq": [
                                    {
                                        "$getField": f"{LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id"
                                    },
                                    {"$literal": project_id},
                                ]
                            },
                            {
                                "$eq": [
                                    {
                                        "$getField": f"{LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id"
                                    },
                                    {"$literal": DEFAULT_PRICING_LEVEL_ID},
                                ]
                            },
                            {
                                "$eq": [
                                    {
                                        "$getField": f"{LLM_TOKEN_PRICES_TABLE_NAME}.pricing_level_id"
                                    },
                                    {"$literal": ""},
                                ]
                            },
                        ]
                    }
                }
            )
        )
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
    )

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


# SELECT
#   SELECT_FIELDS, (Passed in as a list)
#   CONSTRUCTED_SUMMARY_OBJECT AS summary_dump
# FROM ranked_prices
# The group by joins the rows that were split back together
# GROUP BY (all_calls.id, all_calls.project_id, all_calls.display_name)
# WHERE rank = 1
# From all the calls usage, group by and construct the costs object
"""
    Takes in something like the following:
    4 rows
         [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]

        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]

    Returns something like the following:
    1 row
        [ id, summary_dump: {usage: { llm_1, llm_2}, cost: { llm_1: { prompt_tokens_total_cost, completion_tokens_total_cost, ... }, llm_2: { prompt_tokens_total_cost, completion_tokens_total_cost, ... } } } ]
"""


def final_call_select_with_cost(
    param_builder: ParamBuilder,
    price_table_alias: str,
    select_fields: list[str],
    order_fields: list[tsi.SortBy],
) -> PreparedSelect:
    # We filter out summary_dump, because we add costs to summary dump in the select statement
    final_select_fields = [field for field in select_fields if field != "summary_dump"]

    # These two objects are used to construct the costs object
    # We add two more fields in addition to this
    # prompt_tokens_total_cost and completion_tokens_total_cost
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
        "prompt_tokens",
        "completion_tokens",
        "requests",
        "total_tokens",
    ]

    numeric_fields_str = " ".join(
        [
            *[
                f""" '"{field}":', toString({field}), ',', """
                for field in cost_numeric_fields
            ],
            # These numeric fields are derived or mapped to another name
            """
            '"prompt_token_cost":', toString(prompt_token_cost), ',',
            '"completion_token_cost":', toString(completion_token_cost), ',',
            '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',',
            '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
        """,
        ]
    )
    string_fields_str = """ '",', """.join(
        [f""" '"{field}":"', toString({field}), """ for field in cost_string_fields]
    )

    cost_snippet = f"""
    ',"weave":{{',
        '"{COST_OBJECT_NAME}":',
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
    if( any(llm_id) = '{DUMMY_LLM_ID}',
    any(summary_dump),
    concat(
        left(any(summary_dump), length(any(summary_dump)) - 1),
        {cost_snippet},
        '}}' )
    ) AS summary_dump
    """

    usage_with_costs_fields = [
        *[col for col in LLM_USAGE_COLUMNS if col.name != "llm_id"],
        *LLM_TOKEN_PRICES_COLUMNS,
        Column(name="rank", type="string"),
        Column(name="prompt_tokens_cost", type="float"),
        Column(name="completion_tokens_cost", type="float"),
    ]

    ranked_price_table = Table(
        price_table_alias,
        [
            *get_calls_merged_columns(),
            *get_optional_join_field_columns(),
            *usage_with_costs_fields,
        ],
    )

    final_query = (
        ranked_price_table.select()
        .fields([*final_select_fields, summary_dump_snippet])
        .where(
            tsi.Query(**{"$expr": {"$eq": [{"$getField": "rank"}, {"$literal": 1}]}})
        )
        .group_by(final_select_fields)
        .order_by(order_fields)
    )

    final_prepared_query = final_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return final_prepared_query


# From a calls query
# We get the usage data and split the rows so that each usage object is a row
# For each row we get matching price and rank them accordingly
# Finally we join all rows with rank 1 together based on call id and construct cost object
def cost_query(
    pb: ParamBuilder,
    call_table_alias: str,
    project_id: str,
    select_fields: list[str],
    order_fields: list[tsi.SortBy],
) -> str:
    """
    This function takes something like the following:
    1 call row
        [ id, summary_dump: {usage: { llm_1, llm_2}} ]
    splits it based on usage and extracts fields
    2 rows
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens ]
    Then for each row it gets the prices and ranks them for each price available in the project and as a default
    4 rows
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_1, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]

        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 1 ]
        [ id, summary_dump: {usage: { llm_1, llm_2}}, usage_raw, llm_id: llm_2, requests, prompt_tokens, completion_tokens, total_tokens,
            pricing_level, pricing_level_id, provider_id, effective_date, prompt_token_cost, completion_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at, rank: 2 ]
    Finally it joins the rows with rank 1 together and constructs the costs object
    1 row
        [ id, summary_dump: {usage: { llm_1, llm_2}, cost: { llm_1: { prompt_tokens_total_cost, completion_tokens_total_cost, ... }, llm_2: { prompt_tokens_total_cost, completion_tokens_total_cost, ... } } } ]
    """
    raw_sql = f"""
        -- From the all_calls we get the usage data for LLMs
        llm_usage AS ({get_llm_usage(pb, call_table_alias).sql}),

        -- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
        ranked_prices AS ({get_ranked_prices(pb, "llm_usage", project_id).sql})

        -- Final Select, which just selects the correct fields, and adds a costs object
        {final_call_select_with_cost(pb, 'ranked_prices', select_fields, order_fields).sql}
    """
    return raw_sql


# This is a temporary workaround for the issue of clickhouse not allowing the use of parametes in row_number() over function
# Use a parameter when this is fixed
# This checks that a project_id is a valid base64 encoded string, that follows the pattern "ProjectInternalId: <number>"
def is_project_id_sql_injection_safe(project_id: str) -> None:
    try:
        # Attempt to decode the id from Base64
        decoded_str = base64.b64decode(project_id).decode("utf-8")

        # Check if the decoded id matches the pattern "ProjectInternalId:" followed by a number
        match = (
            re.fullmatch(r"ProjectInternalId:\d+", decoded_str.strip())
            or decoded_str == "shawn/test-project"
        )

        if match:
            return

        raise ValueError("Invalid project_id", project_id)
    except Exception:
        raise ValueError("Invalid project_id", project_id)


MESSAGE_INVALID_COST_PURGE = "Can only purge costs by specifying one or more cost ids"


def validate_cost_purge_req(req: tsi.CostPurgeReq) -> None:
    """For safety, we currently only allow purging by cost id."""
    expr = req.query.expr_.model_dump()
    keys = list(expr.keys())
    if len(keys) != 1:
        raise InvalidRequest(MESSAGE_INVALID_COST_PURGE)
    if keys[0] in ["eq_", "in_"]:
        validate_purge_req_one(expr, MESSAGE_INVALID_COST_PURGE, keys[0])
    elif keys[0] == "or_":
        validate_purge_req_multiple(expr["or_"], MESSAGE_INVALID_COST_PURGE)
    else:
        raise InvalidRequest(MESSAGE_INVALID_COST_PURGE)
