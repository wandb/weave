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
