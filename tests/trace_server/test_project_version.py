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

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        return entry[0] if entry else None

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = (value, ex)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def fresh_l1_cache():
    """Ensure L1 is empty around each test."""
    reset_project_residence_cache()
    yield
    reset_project_residence_cache()


@pytest.fixture
def no_redis(monkeypatch):
    """Pin get_redis_client() to None so L2 is skipped."""
    monkeypatch.setattr(project_version, "get_redis_client", lambda: None)


def _patch_redis(monkeypatch, redis_obj):
    """Pin get_redis_client() to return the given redis-like object."""
    monkeypatch.setattr(project_version, "get_redis_client", lambda: redis_obj)


def _make_resolver_with_residence(residences):
    """Return (resolver, ch_client, residence_fn_mock) backed by `residences`.

    `residences` is the value (or list of sequential values) that the patched
    `get_project_data_residence` returns. A MagicMock CH client stands in for
    a real ClickHouse client; the residence fn is what we count to detect
    fall-through to the DB.
    """
    resolver = TableRoutingResolver()
    resolver._mode = CallsStorageServerMode.AUTO
    ch_client = MagicMock()
    fn = MagicMock()
    if isinstance(residences, list):
        fn.side_effect = residences
    else:
        fn.return_value = residences
    return resolver, ch_client, fn


def test_get_residence_l1_cache_hit_skips_redis_and_ch(
    fresh_l1_cache, monkeypatch
):
    """L1 hit short-circuits — neither Redis nor ClickHouse should be touched."""
    redis_mock = MagicMock()
    _patch_redis(monkeypatch, redis_mock)
    resolver, ch_client, residence_fn = _make_resolver_with_residence(
        ProjectDataResidence.MERGED_ONLY
    )
    monkeypatch.setattr(
        project_version, "get_project_data_residence", residence_fn
    )

    # Cold: one CH fetch populates L1 + L2.
    first = resolver._get_residence("p1", ch_client)
    # Warm: pure L1 hit — Redis and CH untouched on this call.
    redis_mock.reset_mock()
    second = resolver._get_residence("p1", ch_client)

    assert first == ProjectDataResidence.MERGED_ONLY
    assert second == ProjectDataResidence.MERGED_ONLY
    assert residence_fn.call_count == 1
    redis_mock.get.assert_not_called()
    redis_mock.set.assert_not_called()


def test_get_residence_redis_l2_paths(fresh_l1_cache, monkeypatch):
    """L2 read, L2 populate after CH miss, and graceful Redis-failure fallback."""
    # 1. Pre-populated Redis → serves L2, no CH; second call promoted to L1.
    redis = _FakeRedis()
    _patch_redis(monkeypatch, redis)
    resolver, ch_client, residence_fn = _make_resolver_with_residence(
        ProjectDataResidence.COMPLETE_ONLY
    )
    monkeypatch.setattr(
        project_version, "get_project_data_residence", residence_fn
    )
    redis.set(
        _residence_cache_key("p_warm"),
        ProjectDataResidence.MERGED_ONLY.value,
        ex=REDIS_RESIDENCE_EXPIRY_SECS,
    )

    first = resolver._get_residence("p_warm", ch_client)
    second = resolver._get_residence("p_warm", ch_client)
    assert first == ProjectDataResidence.MERGED_ONLY
    assert second == ProjectDataResidence.MERGED_ONLY
    assert residence_fn.call_count == 0

    # 2. Cold Redis → CH populates both L2 and L1 (with the right TTL).
    reset_project_residence_cache()
    cold_redis = _FakeRedis()
    _patch_redis(monkeypatch, cold_redis)
    resolver2, ch2, fn2 = _make_resolver_with_residence(
        ProjectDataResidence.BOTH
    )
    monkeypatch.setattr(project_version, "get_project_data_residence", fn2)

    result = resolver2._get_residence("p_cold", ch2)
    assert result == ProjectDataResidence.BOTH
    assert fn2.call_count == 1
    key = _residence_cache_key("p_cold")
    assert cold_redis.get(key) == ProjectDataResidence.BOTH.value
    assert cold_redis._store[key][1] == REDIS_RESIDENCE_EXPIRY_SECS

    # 3. EMPTY residence must NOT be cached at either layer.
    reset_project_residence_cache()
    empty_redis = _FakeRedis()
    _patch_redis(monkeypatch, empty_redis)
    resolver3, ch3, fn3 = _make_resolver_with_residence(
        [ProjectDataResidence.EMPTY, ProjectDataResidence.EMPTY]
    )
    monkeypatch.setattr(project_version, "get_project_data_residence", fn3)

    assert resolver3._get_residence("p_empty", ch3) == ProjectDataResidence.EMPTY
    assert resolver3._get_residence("p_empty", ch3) == ProjectDataResidence.EMPTY
    # Both calls fall through — no caching.
    assert fn3.call_count == 2
    assert empty_redis.get(_residence_cache_key("p_empty")) is None


@pytest.mark.disable_logging_error_check
def test_get_residence_broken_redis_falls_back_to_clickhouse(
    fresh_l1_cache, monkeypatch
):
    """Redis read/write/decode failures degrade gracefully to ClickHouse."""
    # Connection errors on get/set.
    broken = MagicMock()
    broken.get.side_effect = ConnectionError("Redis down")
    broken.set.side_effect = ConnectionError("Redis down")
    _patch_redis(monkeypatch, broken)
    resolver, ch_client, residence_fn = _make_resolver_with_residence(
        ProjectDataResidence.COMPLETE_ONLY
    )
    monkeypatch.setattr(
        project_version, "get_project_data_residence", residence_fn
    )

    assert (
        resolver._get_residence("p_broken", ch_client)
        == ProjectDataResidence.COMPLETE_ONLY
    )
    assert residence_fn.call_count == 1

    # Stale/unknown enum value in Redis is treated as a miss.
    reset_project_residence_cache()
    stale_redis = _FakeRedis()
    stale_redis.set(_residence_cache_key("p_stale"), "future_value")
    _patch_redis(monkeypatch, stale_redis)
    resolver2, ch2, fn2 = _make_resolver_with_residence(
        ProjectDataResidence.MERGED_ONLY
    )
    monkeypatch.setattr(project_version, "get_project_data_residence", fn2)

    assert (
        resolver2._get_residence("p_stale", ch2)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert fn2.call_count == 1


@pytest.mark.disable_logging_error_check
def test_invalidate_project_residence_cache_clears_both_layers(
    fresh_l1_cache, monkeypatch
):
    """Invalidation drops L1 + L2 and forces a refetch from ClickHouse."""
    redis = _FakeRedis()
    _patch_redis(monkeypatch, redis)
    resolver, ch_client, residence_fn = _make_resolver_with_residence(
        [ProjectDataResidence.MERGED_ONLY, ProjectDataResidence.COMPLETE_ONLY]
    )
    monkeypatch.setattr(
        project_version, "get_project_data_residence", residence_fn
    )
    key = _residence_cache_key("p_inv")

    # Populate caches via a CH fetch.
    assert (
        resolver._get_residence("p_inv", ch_client)
        == ProjectDataResidence.MERGED_ONLY
    )
    assert redis.get(key) == ProjectDataResidence.MERGED_ONLY.value
    assert residence_fn.call_count == 1

    # Invalidate clears L2 immediately and forces the next call back to CH.
    invalidate_project_residence_cache("p_inv")
    assert redis.get(key) is None

    refreshed = resolver._get_residence("p_inv", ch_client)
    assert refreshed == ProjectDataResidence.COMPLETE_ONLY
    assert residence_fn.call_count == 2

    # Broken Redis on delete must not raise.
    broken = MagicMock()
    broken.delete.side_effect = ConnectionError("Redis down")
    _patch_redis(monkeypatch, broken)
    invalidate_project_residence_cache("p_inv")
