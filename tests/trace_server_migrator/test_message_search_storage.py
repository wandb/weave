import uuid

import pytest

from tests.trace_server_migrator.test_message_retention import _insert_messages
from weave.trace_server.clickhouse_trace_server_migrator import (
    get_clickhouse_trace_server_migrator,
)


@pytest.mark.parametrize(
    ("replicated", "distributed"), [(False, False), (True, False), (True, True)]
)
def test_capture_upgrade_rollback(ch_client, replicated, distributed):
    database = f"search_{uuid.uuid4().hex[:8]}"
    ch_client.track_db(database + "_management")
    ch_client.track_db(database)
    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        management_db=database + "_management",
        replicated=replicated,
        use_distributed=distributed,
        post_migration_hook=None,
    )
    migrator.apply_migrations(database, target_version=47)
    _insert_messages(ch_client, database, "before")
    migrator.apply_migrations(database, target_version=48)
    _insert_messages(ch_client, database, "after")
    assert ch_client.query(
        "SELECT span_id, role FROM {db:Identifier}.message_occurrences ORDER BY role",
        parameters={"db": database},
    ).result_rows == [
        ("after", role)
        for role in ("assistant", "system", "tool_call", "tool_result", "user")
    ]
    assert ch_client.query(
        "SELECT content FROM {db:Identifier}.message_content WHERE hasAllTokens(content, ['question'])",
        parameters={"db": database},
    ).result_rows == [("question",)]
    migrator.apply_migrations(database, target_version=47)
    _insert_messages(ch_client, database, "rollback")
    assert ch_client.query(
        "SELECT span_id, count() FROM {db:Identifier}.messages GROUP BY span_id ORDER BY span_id",
        parameters={"db": database},
    ).result_rows == [("after", 5), ("before", 5), ("rollback", 5)]
