"""Tests for get_redis_client URL handling (direct vs sentinel)."""

from unittest.mock import patch

import pytest

from weave.trace_server import redis_client


@pytest.fixture(autouse=True)
def clear_cached_redis_client():
    redis_client.get_redis_client.cache_clear()
    yield
    redis_client.get_redis_client.cache_clear()


def test_client_resolution_from_url(monkeypatch):
    """No URL -> None; direct URL -> redis.from_url; ?master= URL -> Sentinel.master_for (port defaults to 26379)."""
    timeouts = {
        "socket_connect_timeout": redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        "socket_timeout": redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    }

    # Unset URL path -> no client.
    redis_client.get_redis_client.cache_clear()
    monkeypatch.delenv("WEAVE_REDIS_URL", raising=False)
    assert redis_client.get_redis_client() is None

    # Direct URL path.
    with patch.object(redis_client.redis, "from_url") as mock_from_url:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv("WEAVE_REDIS_URL", "redis://redis.example:6379")
        client = redis_client.get_redis_client()
        mock_from_url.assert_called_once_with(
            "redis://redis.example:6379",
            decode_responses=True,
            ssl_ca_certs=None,
            **timeouts,
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


def test_direct_url_strips_wandb_query_params(monkeypatch):
    """Wandb-specific query params must not leak into redis-py kwargs.

    The Go connector at `services/connectors/redis.go` consumes params like
    `tls`, `caCertPath`, `ttlInSeconds`. redis-py treats unknown URL params as
    Connection.__init__ kwargs, so leaving them in raises `AbstractConnection.
    __init__() got an unexpected keyword argument 'tls'` at first command.
    """
    timeouts = {
        "socket_connect_timeout": redis_client.REDIS_CONNECT_TIMEOUT_SECS,
        "socket_timeout": redis_client.REDIS_SOCKET_TIMEOUT_SECS,
    }

    # tls=true rewrites the scheme to rediss:// and adds ssl_ca_certs.
    with patch.object(redis_client.redis, "from_url") as mock_from_url:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv(
            "WEAVE_REDIS_URL",
            "redis://:pw@host:6378?tls=true&ttlInSeconds=604800"
            "&caCertPath=/etc/ssl/certs/server_ca.pem",
        )
        redis_client.get_redis_client()
        mock_from_url.assert_called_once_with(
            "rediss://:pw@host:6378",
            decode_responses=True,
            ssl_ca_certs="/etc/ssl/certs/server_ca.pem",
            **timeouts,
        )

    # tls=true without caCertPath -> rediss:// scheme, ssl_ca_certs stays None.
    with patch.object(redis_client.redis, "from_url") as mock_from_url:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv("WEAVE_REDIS_URL", "redis://host:6379?tls=true")
        redis_client.get_redis_client()
        mock_from_url.assert_called_once_with(
            "rediss://host:6379",
            decode_responses=True,
            ssl_ca_certs=None,
            **timeouts,
        )

    # Non-tls wandb params are still stripped, scheme left as-is.
    with patch.object(redis_client.redis, "from_url") as mock_from_url:
        redis_client.get_redis_client.cache_clear()
        monkeypatch.setenv("WEAVE_REDIS_URL", "redis://host:6379?ttlInSeconds=604800")
        redis_client.get_redis_client()
        mock_from_url.assert_called_once_with(
            "redis://host:6379",
            decode_responses=True,
            ssl_ca_certs=None,
            **timeouts,
        )


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "bad_url",
    [
        # K8s manifest interpolation failure -> literal `$(REDIS_PORT)` in port slot.
        "redis://redis.example:$(REDIS_PORT)$(REDIS_PARAMS)",
        # Sentinel URL with the same interpolation failure.
        "redis://redis.example:$(REDIS_PORT)?master=gorilla",
        # Sentinel branch with no hostname -> our own ValueError.
        "redis://?master=gorilla",
        # Outright garbage that urlparse will choke on at port access.
        "redis://host:not-a-number/0",
    ],
)
def test_construction_failure_returns_none(monkeypatch, caplog, bad_url):
    """Malformed URL must fall through to None, not raise.

    Callers treat the L2 client as optional; a construction failure here
    used to bubble up as a 500 on every request that touched
    ``get_project_retention_days``. Now it's logged once and cached as None.
    """
    redis_client.get_redis_client.cache_clear()
    monkeypatch.setenv("WEAVE_REDIS_URL", bad_url)
    with caplog.at_level("ERROR", logger="weave.trace_server.redis_client"):
        assert redis_client.get_redis_client() is None
    assert any(
        "Failed to construct Redis client" in rec.message for rec in caplog.records
    )

    # lru_cache should pin the None so a second call doesn't re-parse.
    with patch.object(redis_client, "urlparse") as mock_urlparse:
        assert redis_client.get_redis_client() is None
        mock_urlparse.assert_not_called()
