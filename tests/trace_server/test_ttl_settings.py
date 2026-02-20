"""Unit tests for weave.trace_server.ttl_settings."""

import datetime
from unittest.mock import MagicMock

import pytest

from weave.trace_server.ttl_settings import (
    _TTL_SENTINEL,
    compute_ttl_at,
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


# ---------------------------------------------------------------------------
# compute_ttl_at
# ---------------------------------------------------------------------------


def test_compute_ttl_at_zero_returns_sentinel():
    """retention_days=0 should return the far-future sentinel."""
    started_at = datetime.datetime(2025, 1, 1)
    result = compute_ttl_at(0, started_at)
    assert result == _TTL_SENTINEL


def test_compute_ttl_at_positive_days():
    """retention_days>0 should return started_at + N days."""
    started_at = datetime.datetime(2025, 1, 1, 12, 0, 0)
    result = compute_ttl_at(90, started_at)
    assert result == datetime.datetime(2025, 4, 1, 12, 0, 0)


def test_compute_ttl_at_one_day():
    started_at = datetime.datetime(2025, 3, 15)
    result = compute_ttl_at(1, started_at)
    assert result == datetime.datetime(2025, 3, 16)


def test_compute_ttl_at_strips_timezone():
    """ttl_at should be timezone-naive (ClickHouse DateTime has no tz)."""
    started_at = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    result = compute_ttl_at(30, started_at)
    assert result.tzinfo is None


def test_compute_ttl_at_sentinel_is_naive():
    started_at = datetime.datetime(2025, 6, 1)
    result = compute_ttl_at(0, started_at)
    assert result.tzinfo is None


# ---------------------------------------------------------------------------
# get_project_retention_days — cache behaviour
# ---------------------------------------------------------------------------


def _make_ch_client(rows):
    """Build a mock ClickHouse client that returns given rows."""
    mock_result = MagicMock()
    mock_result.row_count = len(rows)
    mock_result.first_row = rows[0] if rows else None
    client = MagicMock()
    client.query.return_value = mock_result
    return client


def test_cache_miss_queries_ch():
    ch_client = _make_ch_client([[90]])
    result = get_project_retention_days("entity/project", ch_client)
    assert result == 90
    assert ch_client.query.call_count == 1


def test_cache_hit_skips_ch():
    ch_client = _make_ch_client([[90]])
    get_project_retention_days("entity/project", ch_client)
    get_project_retention_days("entity/project", ch_client)
    # Second call should use cache
    assert ch_client.query.call_count == 1


def test_no_settings_row_returns_zero():
    ch_client = _make_ch_client([])  # no rows
    result = get_project_retention_days("entity/no-ttl-project", ch_client)
    assert result == 0


def test_different_projects_cached_independently():
    ch_client_a = _make_ch_client([[30]])
    ch_client_b = _make_ch_client([[7]])
    result_a = get_project_retention_days("entity/a", ch_client_a)
    result_b = get_project_retention_days("entity/b", ch_client_b)
    assert result_a == 30
    assert result_b == 7


# ---------------------------------------------------------------------------
# invalidate_ttl_cache
# ---------------------------------------------------------------------------


def test_invalidate_forces_refetch():
    ch_client = _make_ch_client([[90]])
    get_project_retention_days("entity/project", ch_client)

    # Change what CH returns
    ch_client.query.return_value.first_row = [30]

    # Without invalidation, still cached
    result = get_project_retention_days("entity/project", ch_client)
    assert result == 90
    assert ch_client.query.call_count == 1

    # After invalidation, refetches
    invalidate_ttl_cache("entity/project")
    result = get_project_retention_days("entity/project", ch_client)
    assert result == 30
    assert ch_client.query.call_count == 2


def test_invalidate_unknown_project_is_noop():
    """invalidate_ttl_cache on a project not in cache should not raise."""
    invalidate_ttl_cache("entity/not-in-cache")
