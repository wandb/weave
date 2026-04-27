"""Tests for get_redis_client URL handling (direct vs sentinel)."""

from unittest.mock import patch

import pytest

from weave.trace_server import redis_client


@pytest.fixture(autouse=True)
def clear_cached_redis_client():
    redis_client.get_redis_client.cache_clear()
    yield
    redis_client.get_redis_client.cache_clear()


def test_no_url_returns_none(monkeypatch):
    redis_client.get_redis_client.cache_clear()
    monkeypatch.delenv("WEAVE_REDIS_URL", raising=False)
    assert redis_client.get_redis_client() is None


def test_client_resolution_from_url(monkeypatch):
    """Direct URL -> redis.from_url; ?master= URL -> Sentinel.master_for (port defaults to 26379)."""
    timeouts = {
        "socket_connect_timeout": redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        "socket_timeout": redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    }

    # Direct URL path.
    with patch.object(redis_client.redis, "from_url") as mock_from_url:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv("WEAVE_REDIS_URL", "redis://redis.example:6379")
        client = redis_client.get_redis_client()
        mock_from_url.assert_called_once_with(
            "redis://redis.example:6379", decode_responses=True, **timeouts
        )
        assert client is mock_from_url.return_value

    # Sentinel URL path with explicit port.
    with patch.object(redis_client, "Sentinel") as mock_sentinel:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv(
            "WEAVE_REDIS_URL", "redis://redis.example:26379?master=gorilla"
        )
        client = redis_client.get_redis_client()
        mock_sentinel.assert_called_once_with([("redis.example", 26379)], **timeouts)
        mock_sentinel.return_value.master_for.assert_called_once_with(
            "gorilla", decode_responses=True, **timeouts
        )
        assert client is mock_sentinel.return_value.master_for.return_value

    # Sentinel URL with no port defaults to 26379.
    with patch.object(redis_client, "Sentinel") as mock_sentinel:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv("WEAVE_REDIS_URL", "redis://redis.example?master=gorilla")
        redis_client.get_redis_client()
        assert mock_sentinel.call_args.args[0] == [("redis.example", 26379)]
