import base64
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from cachetools import LRUCache, TTLCache

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from weave.trace_server.project_version import project_version as pv
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
    ReadTable,
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
    (
        "tables",
        "expected_read_table",
        "expected_v1_write_target",
        "expected_v2_write_target",
        "expect_dual_residency_warning",
    ),
    [
        # EMPTY: V1 -> MERGED (new projects), V2 -> COMPLETE (new projects)
        (
            [],
            ReadTable.CALLS_COMPLETE,
            WriteTarget.CALLS_MERGED,
            WriteTarget.CALLS_COMPLETE,
            False,
        ),
        # MERGED_ONLY: V1 -> MERGED, V2 -> MERGED (keep data together)
        (
            ["calls_merged"],
            ReadTable.CALLS_MERGED,
            WriteTarget.CALLS_MERGED,
            WriteTarget.CALLS_MERGED,
            False,
        ),
        # COMPLETE_ONLY: V1 -> COMPLETE (triggers error), V2 -> COMPLETE
        (
            ["calls_complete"],
            ReadTable.CALLS_COMPLETE,
            WriteTarget.CALLS_COMPLETE,
            WriteTarget.CALLS_COMPLETE,
            False,
        ),
        # BOTH: Unexpected state - data should never be in both tables in production.
        # This is a graceful failure: V1 -> COMPLETE (triggers error to prompt upgrade),
        # V2 -> COMPLETE. Reads from COMPLETE to ensure latest data is visible.
        (
            ["calls_merged", "calls_complete"],
            ReadTable.CALLS_COMPLETE,
            WriteTarget.CALLS_COMPLETE,
            WriteTarget.CALLS_COMPLETE,
            True,  # Dual residency triggers a warning log
        ),
    ],
)
@pytest.mark.parametrize("log_collector", ["warning"], indirect=True)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_version_resolution_by_table_contents(
    client,
    trace_server,
    tables,
    expected_read_table,
    expected_v1_write_target,
    expected_v2_write_target,
    expect_dual_residency_warning,
    log_collector,
):
    """Test routing resolution for different project data residency states."""
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
    assert (
        resolver.resolve_v1_write_target(project_id, ch_server.ch_client)
        == expected_v1_write_target
    )
    assert (
        resolver.resolve_v2_write_target(project_id, ch_server.ch_client)
        == expected_v2_write_target
    )

    # Verify dual residency warning is logged when expected
    warning_logs = log_collector.get_warning_logs()
    dual_residency_warnings = [
        log for log in warning_logs if "dual call residency" in log.message.lower()
    ]
    if expect_dual_residency_warning:
        assert len(dual_residency_warnings) > 0, (
            "Expected dual residency warning but none was logged"
        )
    else:
        assert len(dual_residency_warnings) == 0, (
            f"Unexpected dual residency warning: {dual_residency_warnings}"
        )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_caching_behavior(client, trace_server):

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

    # EMPTY residence is now cached (short TTL) so cold projects stop re-probing.
    empty_proj = make_project_id("empty_cached")
    with count_queries(ch_server.ch_client) as get_count:
        table1 = resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert table1 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1

        table2 = resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert table2 == ReadTable.CALLS_COMPLETE
        assert get_count() == 1


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_empty_residence_expires_after_ttl(client, trace_server, monkeypatch):
    """EMPTY is re-probed after the short TTL; populated residence never expires."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(
        pv,
        "_empty_residence_cache",
        TTLCache(
            maxsize=10,
            ttl=pv.EMPTY_RESIDENCE_CACHE_TTL_SECS,
            timer=lambda: clock["t"],
        ),
    )
    monkeypatch.setattr(pv, "_project_residence_cache", LRUCache(maxsize=10))

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.AUTO

    empty_proj = make_project_id("empty_ttl_expiry")
    with count_queries(ch_server.ch_client) as get_count:
        resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert get_count() == 1  # cached within TTL
        clock["t"] += pv.EMPTY_RESIDENCE_CACHE_TTL_SECS + 1
        resolver.resolve_read_table(empty_proj, ch_server.ch_client)
        assert get_count() == 2  # re-probed after TTL


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_cached_empty_does_not_mask_write(client, trace_server):
    """A read that cached EMPTY must not hide a subsequent write's data.

    A read caches EMPTY (routing reads to calls_complete); a legacy V1 write then
    lands in calls_merged. The write resolution evicts the cached EMPTY so the next
    read re-probes and routes to calls_merged (read-your-writes).
    """
    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.AUTO

    proj = make_project_id("cached_empty_then_write")
    assert (
        resolver.resolve_read_table(proj, ch_server.ch_client)
        == ReadTable.CALLS_COMPLETE
    )
    assert (
        resolver.resolve_v1_write_target(proj, ch_server.ch_client)
        == WriteTarget.CALLS_MERGED
    )
    insert_call(ch_server.ch_client, "calls_merged", proj)
    assert (
        resolver.resolve_read_table(proj, ch_server.ch_client) == ReadTable.CALLS_MERGED
    )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_mode_off_and_force_legacy(client, trace_server):

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


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_clickhouse_provider_directly(client, trace_server):

    ch_server = trace_server._internal_trace_server
    project_id = make_project_id("provider_direct")
    insert_call(ch_server.ch_client, "calls_merged", project_id)

    residence = get_project_data_residence(project_id, ch_server.ch_client)

    assert residence == ProjectDataResidence.MERGED_ONLY


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: table routing/residence"
)
def test_resolver_as_trace_server_member(client, trace_server):
    """Test that the resolver is properly integrated as a trace server member."""
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


def test_project_version_mode_from_env(monkeypatch):
    test_cases = [
        ("off", CallsStorageServerMode.OFF),
        ("force_legacy", CallsStorageServerMode.FORCE_LEGACY),
        ("auto", CallsStorageServerMode.AUTO),
        ("invalid_mode", CallsStorageServerMode.AUTO),
    ]
    for env_val, expected_mode in test_cases:
        monkeypatch.setenv("PROJECT_VERSION_MODE", env_val)
        assert CallsStorageServerMode.from_env() == expected_mode

    monkeypatch.delenv("PROJECT_VERSION_MODE", raising=False)
    assert CallsStorageServerMode.from_env() == CallsStorageServerMode.AUTO
