import base64
import os
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace_server.project_version import project_version
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.project_version import (
    REDIS_RESIDENCE_EXPIRY_SECS,
    TableRoutingResolver,
    _residence_cache_key,
    invalidate_project_residence_cache,
    reset_project_residence_cache,
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


# ---------------------------------------------------------------------------
# Two-layer cache (L1 + Redis L2) unit tests
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal dict-backed Redis mock for testing L2 cache."""

    def __init__(self):
        self._store: dict[str, tuple[str, int | None]] = {}

    def get(self, key):
        entry = self._store.get(key)
        return entry[0] if entry else None

    def set(self, key, value, ex=None):
        self._store[key] = (value, ex)

    def delete(self, key):
        self._store.pop(key, None)


def _wire(monkeypatch, *, redis_obj, residences):
    """Patch L2 client + CH fetch and return (resolver, ch_client, residence_fn)."""
    monkeypatch.setattr(project_version, "get_redis_client", lambda: redis_obj)
    fn = MagicMock()
    if isinstance(residences, list):
        fn.side_effect = residences
    else:
        fn.return_value = residences
    monkeypatch.setattr(project_version, "get_project_data_residence", fn)
    resolver = TableRoutingResolver()
    resolver._mode = CallsStorageServerMode.AUTO
    return resolver, MagicMock(), fn


def test_two_layer_cache_paths(monkeypatch):
    """Cover L1 short-circuit, L2 hit + L1 promotion, cold-redis populate, EMPTY skip."""
    reset_project_residence_cache()
    redis = _FakeRedis()

    # --- 1. Cold CH fetch populates both layers; second call is pure L1 (no Redis I/O).
    spy = MagicMock(wraps=redis)
    resolver, ch_client, residence_fn = _wire(
        monkeypatch, redis_obj=spy, residences=ProjectDataResidence.MERGED_ONLY
    )
    assert (
        resolver._get_residence("p_cold", ch_client)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert residence_fn.call_count == 1
    cold_key = _residence_cache_key("p_cold")
    assert redis.get(cold_key) == ProjectDataResidence.MERGED_ONLY.value
    assert redis._store[cold_key][1] == REDIS_RESIDENCE_EXPIRY_SECS

    spy.reset_mock()
    assert (
        resolver._get_residence("p_cold", ch_client)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert residence_fn.call_count == 1  # no extra CH call
    spy.get.assert_not_called()
    spy.set.assert_not_called()

    # --- 2. Pre-populated Redis serves L2 (no CH); cleared L1 forces it.
    reset_project_residence_cache()
    redis.set(_residence_cache_key("p_warm"), ProjectDataResidence.BOTH.value)
    resolver2, ch2, fn2 = _wire(
        monkeypatch, redis_obj=redis, residences=ProjectDataResidence.COMPLETE_ONLY
    )
    assert resolver2._get_residence("p_warm", ch2) == ProjectDataResidence.BOTH
    assert resolver2._get_residence("p_warm", ch2) == ProjectDataResidence.BOTH
    assert fn2.call_count == 0  # never hit CH

    # --- 3. EMPTY residence is never cached at either layer.
    reset_project_residence_cache()
    empty_redis = _FakeRedis()
    resolver3, ch3, fn3 = _wire(
        monkeypatch,
        redis_obj=empty_redis,
        residences=[ProjectDataResidence.EMPTY, ProjectDataResidence.EMPTY],
    )
    assert resolver3._get_residence("p_e", ch3) == ProjectDataResidence.EMPTY
    assert resolver3._get_residence("p_e", ch3) == ProjectDataResidence.EMPTY
    assert fn3.call_count == 2
    assert empty_redis.get(_residence_cache_key("p_e")) is None


@pytest.mark.disable_logging_error_check
def test_redis_failure_modes_and_invalidation(monkeypatch):
    """Broken-redis + stale-enum fall back to CH; invalidate clears L1+L2."""
    reset_project_residence_cache()

    # --- 1. Connection errors on get/set degrade to CH transparently.
    broken = MagicMock()
    broken.get.side_effect = ConnectionError("Redis down")
    broken.set.side_effect = ConnectionError("Redis down")
    resolver, ch_client, fn = _wire(
        monkeypatch, redis_obj=broken, residences=ProjectDataResidence.COMPLETE_ONLY
    )
    assert (
        resolver._get_residence("p_broken", ch_client)
        == ProjectDataResidence.COMPLETE_ONLY
    )
    assert fn.call_count == 1

    # --- 2. Unknown enum value written by an older/newer build is treated as a miss.
    reset_project_residence_cache()
    stale = _FakeRedis()
    stale.set(_residence_cache_key("p_stale"), "future_value")
    resolver2, ch2, fn2 = _wire(
        monkeypatch, redis_obj=stale, residences=ProjectDataResidence.MERGED_ONLY
    )
    assert (
        resolver2._get_residence("p_stale", ch2)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert fn2.call_count == 1

    # --- 3. invalidate clears both layers, forces refetch, and swallows delete errors.
    reset_project_residence_cache()
    redis = _FakeRedis()
    resolver3, ch3, fn3 = _wire(
        monkeypatch,
        redis_obj=redis,
        residences=[
            ProjectDataResidence.MERGED_ONLY,
            ProjectDataResidence.COMPLETE_ONLY,
        ],
    )
    key = _residence_cache_key("p_inv")
    assert (
        resolver3._get_residence("p_inv", ch3)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert redis.get(key) == ProjectDataResidence.MERGED_ONLY.value

    invalidate_project_residence_cache("p_inv")
    assert redis.get(key) is None
    assert (
        resolver3._get_residence("p_inv", ch3)
        == ProjectDataResidence.COMPLETE_ONLY
    )
    assert fn3.call_count == 2

    monkeypatch.setattr(
        project_version,
        "get_redis_client",
        lambda: MagicMock(delete=MagicMock(side_effect=ConnectionError("down"))),
    )
    invalidate_project_residence_cache("p_inv")  # must not raise
