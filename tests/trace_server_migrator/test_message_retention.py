import uuid
from datetime import datetime, timezone

import pytest

from weave.trace_server.clickhouse_trace_server_migrator import (
    get_clickhouse_trace_server_migrator,
)

_BEFORE_RETENTION = 46
_RETENTION = 47
_NO_EXPIRY = datetime(2100, 1, 1, tzinfo=timezone.utc)
_EXPIRY = datetime(2099, 1, 1, tzinfo=timezone.utc)
_MESSAGES = [
    ("assistant", "answer"),
    ("system", "instructions"),
    ("tool_call", "arguments"),
    ("tool_result", "result"),
    ("user", "question"),
]


@pytest.mark.parametrize(
    ("replicated", "distributed", "legacy"),
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, True, True),
    ],
    ids=["cloud", "replicated", "distributed", "distributed-legacy"],
)
def test_message_retention_upgrade_and_rollback(
    ch_client, replicated: bool, distributed: bool, legacy: bool
):
    """All message sources inherit expiry after upgrade and survive rollback."""
    database = f"retention_{uuid.uuid4().hex[:8]}"
    management_db = f"{database}_management"
    ch_client.track_db(management_db)
    ch_client.track_db(database)
    parameters = {"db": database}

    if legacy:
        ch_client.command(
            "CREATE DATABASE {db:Identifier} ON CLUSTER weave_cluster "
            "ENGINE = Replicated({path:String}, '{shard}', '{replica}')",
            parameters={**parameters, "path": f"/clickhouse/databases/{database}"},
        )

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=replicated,
        use_distributed=distributed,
        management_db=management_db,
        post_migration_hook=None,
    )
    migrator.apply_migrations(database, target_version=_BEFORE_RETENTION)
    _insert_messages(ch_client, database, "before")
    migrator.apply_migrations(database, target_version=_RETENTION)
    _insert_messages(ch_client, database, "after")

    rows = ch_client.query(
        "SELECT span_id, role, content, toUnixTimestamp(expire_at) FROM {db:Identifier}.messages "
        "ORDER BY span_id, role",
        parameters=parameters,
    ).result_rows
    assert rows == [
        (span_id, role, content, int(expiry.timestamp()))
        for span_id, expiry in [("after", _EXPIRY), ("before", _NO_EXPIRY)]
        for role, content in _MESSAGES
    ]

    migrator.apply_migrations(database, target_version=_BEFORE_RETENTION)
    _insert_messages(ch_client, database, "rollback")
    rows = ch_client.query(
        "SELECT span_id, role, content FROM {db:Identifier}.messages "
        "ORDER BY span_id, role",
        parameters=parameters,
    ).result_rows
    assert rows == [
        (span_id, role, content)
        for span_id in ["after", "before", "rollback"]
        for role, content in _MESSAGES
    ]

    migrator.apply_migrations(database, target_version=_RETENTION)
    _insert_messages(ch_client, database, "reupgrade")
    rows = ch_client.query(
        "SELECT role, content, toUnixTimestamp(expire_at) FROM {db:Identifier}.messages "
        "WHERE span_id = {span:String} ORDER BY role",
        parameters={**parameters, "span": "reupgrade"},
    ).result_rows
    assert rows == [
        (role, content, int(_EXPIRY.timestamp())) for role, content in _MESSAGES
    ]


def _insert_messages(ch_client, database: str, span_id: str) -> None:
    ch_client.insert(
        "spans",
        [
            [
                "test",
                "trace",
                span_id,
                [("user", "question", "")],
                [("assistant", "answer", "")],
                ["instructions"],
                "arguments",
                "result",
                _EXPIRY,
            ]
        ],
        column_names=[
            "project_id",
            "trace_id",
            "span_id",
            "input_messages",
            "output_messages",
            "system_instructions",
            "tool_call_arguments",
            "tool_call_result",
            "expire_at",
        ],
        database=database,
        settings={"distributed_foreground_insert": 1},
    )
