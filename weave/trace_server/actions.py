from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import Column, Table

TABLE_ACTIONS = Table(
    "actions_parts",
    [
        Column("project_id", "string"),
        Column("call_id", "string"),
        Column("id", "string"),
        Column("rule_matched", "string", nullable=True),
        Column("effect", "string", nullable=True),
        Column("created_at", "datetime", nullable=True),
        Column("finished_at", "datetime", nullable=True),
        Column("failed_at", "datetime", nullable=True),
    ],
)


def get_actions_columns() -> list[Column]:
    return TABLE_ACTIONS.cols


def actions_table(table_alias: str) -> Table:
    return Table(table_alias, get_actions_columns())


def get_action(param_builder: tsi.ParamBuilder, table_alias: str) -> tsi.PreparedSelect:
    actions_table = actions_table(table_alias)

    select_query = actions_table.select().fields(["*"])

    prepared_query = select_query.prepare(
        database_type="clickhouse", param_builder=param_builder
    )
    return prepared_query


def action_query(
    pb: tsi.ParamBuilder,
    action_table_alias: str,
    select_fields: list[str],
    order_fields: list[tsi.SortBy],
) -> str:
    raw_sql = f"""
        {get_action(pb, action_table_alias).sql}
    """
    return raw_sql
