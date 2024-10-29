import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import Column, PreparedSelect, Table

TABLE_ACTIONS = Table(
    "actions_parts",
    [
        Column("project_id", "string"),
        Column("call_id", "string"),
        Column("id", "string"),
        Column("rule_matched", "string", nullable=True),
        Column("configured_action", "string", nullable=True),  # Updated column name
        Column("created_at", "datetime", nullable=True),
        Column("finished_at", "datetime", nullable=True),
        Column("failed_at", "datetime", nullable=True),
    ],
)

TABLE_ACTIONS_MERGED = Table(
    "actions_merged",
    [
        Column("project_id", "string"),
        Column("call_id", "string"),
        Column("id", "string"),
        Column("rule_matched", "string", nullable=True),
        Column("configured_action", "string", nullable=True),  # Updated column name
        Column("created_at", "datetime", nullable=True),
        Column("finished_at", "datetime", nullable=True),
        Column("failed_at", "datetime", nullable=True),
    ],
)


def get_stale_actions(older_than: datetime.datetime) -> PreparedSelect:
    where_filter = tsi.Query.model_validate(
        {
            "$expr": {
                "$and": [
                    {
                        "$lt": [
                            {"$getField": "created_at"},
                            {"$literal": older_than},  # TODO does this work?
                        ]
                    },
                    {"$eq": [{"$getField": "finished_at"}, None]},
                    {"$eq": [{"$getField": "failed_at"}, None]},
                ]
            }
        }
    )
    query = (
        TABLE_ACTIONS.select()
        .fields(
            [
                "project_id",
                "call_id",
                "id",
                "any(rule_matched) as rule_matched",
                "any(configured_action) as configured_action",
                "max(created_at) as created_at",
                "max(finished_at) as finished_at",
                "max(failed_at) as failed_at",
            ]
        )
        .where(where_filter)
        .group_by(["project_id", "call_id", "id"])
    )
    return query.prepare(database_type="clickhouse")
