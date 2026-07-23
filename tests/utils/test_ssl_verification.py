"""Tests for SSL verification behavior controlled by WEAVE_INSECURE_DISABLE_SSL."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import gql
import httpx
import pytest

from weave.compat.wandb.wandb_thin.internal_api import Api
from weave.trace.env import WEAVE_INSECURE_DISABLE_SSL, ssl_verify
from weave.utils import http_requests


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        (None, True),
        ("true", False),
        ("True", False),
        ("false", True),
        ("", True),
    ],
)
def test_ssl_verify_env(monkeypatch, env_value, expected):
    """env.ssl_verify() is True unless WEAVE_INSECURE_DISABLE_SSL is a true-string (case-insensitive)."""
    if env_value is None:
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
    else:
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, env_value)
    assert ssl_verify() is expected


def test_httpx_client_env_flip_swaps_cached_client(monkeypatch):
    """`_get_client()` reads ssl_verify() per call, caches by verify flag, and swaps clients on env flip."""
    monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
    verifying = http_requests._get_client()
    assert isinstance(verifying._transport, httpx.HTTPTransport)
    assert verifying._transport._pool._ssl_context.verify_mode.name != "CERT_NONE"

    monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
    insecure = http_requests._get_client()
    assert isinstance(insecure._transport, httpx.HTTPTransport)
    assert insecure is not verifying
    assert insecure._transport._pool._ssl_context.verify_mode.name == "CERT_NONE"

    # Flipping back returns the original cached client (connection pool preserved).
    monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
    assert http_requests._get_client() is verifying


@pytest.mark.parametrize(
    ("env_value", "expected_verify"),
    [("true", False), (None, True)],
)
def test_internal_api_passes_ssl_verify_to_gql_transport(
    monkeypatch, env_value, expected_verify
):
    """The wandb thin API client forwards ssl_verify() as the gql httpx transport's `verify`."""
    if env_value is None:
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
    else:
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, env_value)

    mock_transport_cls = MagicMock()
    mock_transport_cls.return_value = MagicMock()

    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value = {"data": {}}
    mock_client.connect_sync.return_value = mock_session

    with (
        patch("gql.Client", return_value=mock_client),
        patch(
            "weave.compat.wandb.wandb_thin.internal_api.get_wandb_api_context",
            return_value=None,
        ),
        patch.dict(
            "sys.modules",
            {"gql.transport.httpx": MagicMock(HTTPXTransport=mock_transport_cls)},
        ),
    ):
        api = Api()
        api.query(gql.gql("{ viewer { username } }"))

        _, kwargs = mock_transport_cls.call_args
        assert kwargs["verify"] is expected_verify
