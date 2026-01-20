import base64
import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
    ReadTable,
    WriteSourceVersion,
    WriteTarget,
)


def make_project_id(name: str) -> str:
    return base64.b64encode(f"test_entity/{name}".encode()).decode()


def insert_call(ch_client, table: str, project_id: str):
    ch_client.command(
        f"""
        INSERT INTO {table} (project_id, id, op_name, started_at, trace_id, parent_id)
        VALUES ('{project_id}', '{uuid.uuid4()}', 'test_op', now(), '{uuid.uuid4()}', '')
        """
    )


@contextmanager
def count_queries(ch_client):
    call_count = 0
    original_query = ch_client.query

    def counting_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_query(*args, **kwargs)

    with patch.object(ch_client, "query", side_effect=counting_query):
        yield lambda: call_count


@pytest.mark.parametrize(
    ("tables", "expected_read_table", "expected_write_targets"),
    [
        # EMPTY: V1 -> MERGED (new projects), V2 -> COMPLETE (new projects)
        (
            [],
            ReadTable.CALLS_COMPLETE,
            {
                WriteSourceVersion.V1: WriteTarget.CALLS_MERGED,
                WriteSourceVersion.V2: WriteTarget.CALLS_COMPLETE,
            },
        ),
        # MERGED_ONLY: V1 -> MERGED, V2 -> MERGED (keep data together)
        (
            ["calls_merged"],
            ReadTable.CALLS_MERGED,
            {
                WriteSourceVersion.V1: WriteTarget.CALLS_MERGED,
                WriteSourceVersion.V2: WriteTarget.CALLS_MERGED,
            },
        ),
        # COMPLETE_ONLY: V1 -> COMPLETE (triggers error), V2 -> COMPLETE
        (
            ["calls_complete"],
            ReadTable.CALLS_COMPLETE,
            {
                WriteSourceVersion.V1: WriteTarget.CALLS_COMPLETE,
                WriteSourceVersion.V2: WriteTarget.CALLS_COMPLETE,
            },
        ),
        # BOTH: V1 -> MERGED, V2 -> COMPLETE (prefer COMPLETE for new writes)
        (
            ["calls_merged", "calls_complete"],
            ReadTable.CALLS_COMPLETE,
            {
                WriteSourceVersion.V1: WriteTarget.CALLS_MERGED,
                WriteSourceVersion.V2: WriteTarget.CALLS_COMPLETE,
            },
        ),
    ],
)
def test_version_resolution_by_table_contents(
    client, trace_server, tables, expected_read_table, expected_write_targets
):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    # manually set this to auto so we can test the switching
    resolver._mode = CallsStorageServerMode.AUTO

    project_id = make_project_id("table_contents")
    for table in tables:
        insert_call(ch_server.ch_client, table, project_id)

    assert (
        resolver.resolve_read_table(project_id, ch_server.ch_client)
        == expected_read_table
    )
    for source_version, expected_write_target in expected_write_targets.items():
        assert (
            resolver.resolve_write_target(
                project_id,
                ch_server.ch_client,
                write_source=source_version,
            )
            == expected_write_target
        )


def test_caching_behavior(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.AUTO

    cached_proj = make_project_id("cached_project")
    insert_call(ch_server.ch_client, "calls_complete", cached_proj)

    with count_queries(ch_server.ch_client) as get_count:
        table1 = resolver.resolve_read_table(cached_proj, ch_server.ch_client)
        assert table1 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

        table2 = resolver.resolve_read_table(cached_proj, ch_server.ch_client)
        assert table2 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

    empty_proj = make_project_id("empty_not_cached")
    with count_queries(ch_server.ch_client) as get_count:
        table1 = resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert table1 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

        table2 = resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert table2 == ReadTable.CALLS_COMPLETE
        assert get_count() == 2


def test_mode_off_and_force_legacy(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver

    project_id = make_project_id("mode_test")
    insert_call(ch_server.ch_client, "calls_complete", project_id)

    resolver._mode = CallsStorageServerMode.OFF
    with count_queries(ch_server.ch_client) as get_count:
        table = resolver.resolve_read_table(project_id, ch_server.ch_client)
        assert table == ReadTable.CALLS_MERGED
        assert get_count() == 0

    resolver._mode = CallsStorageServerMode.FORCE_LEGACY
    # FORCE_LEGACY performs the query but returns MERGED
    with count_queries(ch_server.ch_client) as get_count:
        table = resolver.resolve_read_table(project_id, ch_server.ch_client)
        assert table == ReadTable.CALLS_MERGED
        assert get_count() == 1

    resolver._mode = CallsStorageServerMode.AUTO
    table = resolver.resolve_read_table(project_id, ch_server.ch_client)
    assert table == ReadTable.CALLS_COMPLETE


def test_clickhouse_provider_directly(client, trace_server):
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    project_id = make_project_id("provider_direct")
    insert_call(ch_server.ch_client, "calls_merged", project_id)

    residence = get_project_data_residence(project_id, ch_server.ch_client)

    assert residence == ProjectDataResidence.MERGED_ONLY


def test_resolver_as_trace_server_member(client, trace_server):
    """Test that the resolver is properly integrated as a trace server member."""
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server

    # Test that the resolver is lazily initialized
    assert ch_server._table_routing_resolver is None
    resolver1 = ch_server.table_routing_resolver
    assert resolver1 is not None

    resolver2 = ch_server.table_routing_resolver
    assert resolver1 is resolver2

    project_id = make_project_id("trace_server_member")
    insert_call(ch_server.ch_client, "calls_complete", project_id)

    with count_queries(ch_server.ch_client) as get_count:
        resolver1._mode = CallsStorageServerMode.AUTO
        table = resolver1.resolve_read_table(project_id, ch_server.ch_client)
        assert table == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

        # Subsequent requests hit the cache
        table2 = resolver1.resolve_read_table(project_id, ch_server.ch_client)
        assert table2 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

        table3 = resolver2.resolve_read_table(project_id, ch_server.ch_client)
        assert table3 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1


def test_project_version_mode_from_env():
    original_value = os.environ.get("PROJECT_VERSION_MODE")

    try:
        test_cases = [
            ("off", CallsStorageServerMode.OFF),
            ("force_legacy", CallsStorageServerMode.FORCE_LEGACY),
            ("auto", CallsStorageServerMode.AUTO),
            ("invalid_mode", CallsStorageServerMode.AUTO),
        ]

        for env_val, expected_mode in test_cases:
            os.environ["PROJECT_VERSION_MODE"] = env_val
            mode = CallsStorageServerMode.from_env()
            assert mode == expected_mode

        if "PROJECT_VERSION_MODE" in os.environ:
            del os.environ["PROJECT_VERSION_MODE"]
        mode = CallsStorageServerMode.from_env()
        assert mode == CallsStorageServerMode.AUTO

    finally:
        if original_value is not None:
            os.environ["PROJECT_VERSION_MODE"] = original_value
        elif "PROJECT_VERSION_MODE" in os.environ:
            del os.environ["PROJECT_VERSION_MODE"]
