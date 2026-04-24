"""Tests for get_redis_client URL handling (direct vs sentinel)."""

from unittest.mock import MagicMock, patch

from weave.trace_server import redis_client


def _reset_cache() -> None:
    redis_client.get_redis_client.cache_clear()


def test_returns_none_when_url_unset(monkeypatch):
    _reset_cache()
    monkeypatch.delenv("WEAVE_REDIS_URL", raising=False)
    assert redis_client.get_redis_client() is None


@patch.object(redis_client.redis, "from_url")
def test_direct_client_when_no_master_param(mock_from_url, monkeypatch):
    _reset_cache()
    monkeypatch.setenv("WEAVE_REDIS_URL", "redis://redis.example:6379")
    mock_from_url.return_value = MagicMock(name="direct-client")

    client = redis_client.get_redis_client()

    mock_from_url.assert_called_once_with(
        "redis://redis.example:6379",
        decode_responses=True,
        socket_connect_timeout=redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        socket_timeout=redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    )
    assert client is mock_from_url.return_value


@patch.object(redis_client, "Sentinel")
def test_sentinel_client_when_master_param_set(mock_sentinel_cls, monkeypatch):
    _reset_cache()
    monkeypatch.setenv(
        "WEAVE_REDIS_URL",
        "redis://redis.example:26379?master=gorilla",
    )
    sentinel_instance = mock_sentinel_cls.return_value
    master_client = sentinel_instance.master_for.return_value

    client = redis_client.get_redis_client()

    mock_sentinel_cls.assert_called_once_with(
        [("redis.example", 26379)],
        socket_connect_timeout=redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        socket_timeout=redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    )
    sentinel_instance.master_for.assert_called_once_with(
        "gorilla",
        decode_responses=True,
        socket_connect_timeout=redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        socket_timeout=redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    )
    assert client is master_client


@patch.object(redis_client, "Sentinel")
def test_sentinel_defaults_port_when_omitted(mock_sentinel_cls, monkeypatch):
    _reset_cache()
    monkeypatch.setenv("WEAVE_REDIS_URL", "redis://redis.example?master=gorilla")

    redis_client.get_redis_client()

    sentinel_call = mock_sentinel_cls.call_args
    assert sentinel_call.args[0] == [("redis.example", 26379)]
