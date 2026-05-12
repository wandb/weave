"""Scenario-focused tests for weave.trace_server.ttl_settings."""

import datetime
from unittest.mock import MagicMock

import pytest

from weave.trace_server import ttl_settings
from weave.trace_server.ttl_settings import (
    REDIS_TTL_EXPIRY_SECS,
    _ttl_cache_key,
    compute_expire_at,
    get_project_retention_days,
    invalidate_ttl_cache,
    reset_ttl_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure cache is empty before and after each test."""
    reset_ttl_cache()
    yield
    reset_ttl_cache()


@pytest.fixture
def no_redis(monkeypatch):
    """Pin get_redis_client() to None so L2 is skipped."""
    monkeypatch.setattr(ttl_settings, "get_redis_client", lambda: None)


def _patch_redis(monkeypatch, redis_obj):
    """Pin get_redis_client() to return the given redis-like object."""
    monkeypatch.setattr(ttl_settings, "get_redis_client", lambda: redis_obj)


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


def _make_ch_client(rows):
    """Build a mock ClickHouse client that returns the given rows on query."""
    mock_result = MagicMock()
    mock_result.row_count = len(rows)
    mock_result.first_row = rows[0] if rows else None
    client = MagicMock()
    client.query.return_value = mock_result
    return client


def test_compute_expire_at():
    """Zero → None, positive + naive → UTC, positive + aware → preserved, negative → minutes."""
    # retention_days=0 means no TTL in app code; DB adapters sentinelize at write time.
    result_zero = compute_expire_at(0, datetime.datetime(2025, 1, 1))
    assert result_zero is None

    # Positive days with naive datetime normalizes to UTC
    result_positive_naive = compute_expire_at(
        90, datetime.datetime(2025, 1, 1, 12, 0, 0)
    )
    assert result_positive_naive == datetime.datetime(
        2025, 4, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert result_positive_naive.tzinfo == datetime.timezone.utc

    # Positive days with aware datetime preserves original timezone
    tz_minus7 = datetime.timezone(datetime.timedelta(hours=-7))
    result_positive_aware = compute_expire_at(
        30, datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=tz_minus7)
    )
    assert result_positive_aware == datetime.datetime(
        2025, 1, 31, 12, 0, 0, tzinfo=tz_minus7
    )
    assert result_positive_aware.tzinfo == tz_minus7

    # Negative retention_days encodes minutes (e.g. -5 = 5 minutes)
    result_negative = compute_expire_at(-5, datetime.datetime(2025, 6, 15, 10, 0, 0))
    assert result_negative == datetime.datetime(
        2025, 6, 15, 10, 5, 0, tzinfo=datetime.timezone.utc
    )


EXPECTED_L3_QUERY = (
    "SELECT argMax(retention_days, updated_at) "
    "FROM project_ttl_settings "
    "WHERE project_id = {project_id:String}"
)


def test_get_project_retention_days_l1_cache(no_redis):
    """L1 caching: single CH query for repeated lookups, zero on CH miss."""
    ch_client = _make_ch_client([[90]])

    first = get_project_retention_days("entity/project", ch_client)
    second = get_project_retention_days("entity/project", ch_client)

    assert first == 90
    assert second == 90
    assert ch_client.query.call_count == 1
    ch_client.query.assert_called_once_with(
        EXPECTED_L3_QUERY, parameters={"project_id": "entity/project"}
    )

    # Different project with no rows → 0 (no TTL configured)
    ch_empty = _make_ch_client([])
    assert get_project_retention_days("entity/no-ttl", ch_empty) == 0


@pytest.mark.disable_logging_error_check
def test_get_project_retention_days_redis_l2_cache(monkeypatch):
    """L2 read, L2 populate after CH hit, and graceful Redis failure fallback."""
    redis = _FakeRedis()
    _patch_redis(monkeypatch, redis)

    # Pre-populated Redis → serves from L2, no CH query, then L1 on repeat
    ch_not_reached = _make_ch_client([[999]])
    redis.set(_ttl_cache_key("entity/proj"), "45", ex=300)

    first = get_project_retention_days("entity/proj", ch_not_reached)
    second = get_project_retention_days("entity/proj", ch_not_reached)
    assert first == 45
    assert second == 45
    assert ch_not_reached.query.call_count == 0

    # Cold Redis → CH query populates both L2 and L1
    redis_cold = _FakeRedis()
    _patch_redis(monkeypatch, redis_cold)
    ch_client = _make_ch_client([[60]])
    result = get_project_retention_days("entity/other", ch_client)
    assert result == 60
    assert ch_client.query.call_count == 1
    ch_client.query.assert_called_once_with(
        EXPECTED_L3_QUERY, parameters={"project_id": "entity/other"}
    )
    key = _ttl_cache_key("entity/other")
    assert redis_cold.get(key) == "60"
    assert redis_cold._store[key][1] == REDIS_TTL_EXPIRY_SECS

    # Broken Redis → falls back to CH transparently
    broken_redis = MagicMock()
    broken_redis.get.side_effect = ConnectionError("Redis down")
    broken_redis.set.side_effect = ConnectionError("Redis down")
    _patch_redis(monkeypatch, broken_redis)
    ch_fallback = _make_ch_client([[77]])
    assert get_project_retention_days("entity/broken-redis", ch_fallback) == 77
    assert ch_fallback.query.call_count == 1


@pytest.mark.disable_logging_error_check
def test_invalidate_ttl_cache(monkeypatch):
    """Invalidation clears L1+L2, forces refetch, and swallows Redis errors."""
    ch_client = _make_ch_client([[90]])
    redis = _FakeRedis()
    _patch_redis(monkeypatch, redis)
    key = _ttl_cache_key("entity/proj")

    # Populate both cache layers
    original = get_project_retention_days("entity/proj", ch_client)
    cached = get_project_retention_days("entity/proj", ch_client)
    assert original == 90
    assert cached == 90
    assert redis.get(key) == "90"
    assert ch_client.query.call_count == 1

    # Invalidate and verify refetch picks up new value
    ch_client.query.return_value.first_row = [30]
    invalidate_ttl_cache("entity/proj")
    assert redis.get(key) is None

    refreshed = get_project_retention_days("entity/proj", ch_client)
    assert refreshed == 30
    assert ch_client.query.call_count == 2

    # Broken Redis on delete → no exception raised
    broken_redis = MagicMock()
    broken_redis.delete.side_effect = ConnectionError("Redis down")
    _patch_redis(monkeypatch, broken_redis)
    invalidate_ttl_cache("entity/proj")
