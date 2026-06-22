"""Tests for SSL verification behavior controlled by WEAVE_INSECURE_DISABLE_SSL."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import gql
import httpx

from weave.compat.wandb.wandb_thin.internal_api import Api
from weave.trace.env import WEAVE_INSECURE_DISABLE_SSL, ssl_verify
from weave.utils import http_requests


class TestSslVerifyEnv:
    """env.ssl_verify() respects WEAVE_INSECURE_DISABLE_SSL."""

    def test_default_is_true(self, monkeypatch):
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
        assert ssl_verify() is True

    def test_true_string_disables(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        assert ssl_verify() is False

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "True")
        assert ssl_verify() is False

    def test_other_values_keep_enabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "false")
        assert ssl_verify() is True

    def test_empty_string_keeps_enabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "")
        assert ssl_verify() is True


class TestHttpxClientSslVerify:
    """`_get_client()` honors `ssl_verify()` at call time."""

    def test_client_verify_disabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        # httpx bakes the verify flag into an ssl_context on the transport pool;
        # CERT_NONE means SSL certificate verification is disabled.
        transport = http_requests._get_client()._transport
        assert isinstance(transport, httpx.HTTPTransport)
        assert transport._pool._ssl_context.verify_mode.name == "CERT_NONE"

    def test_client_verify_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
        transport = http_requests._get_client()._transport
        assert isinstance(transport, httpx.HTTPTransport)
        assert transport._pool._ssl_context.verify_mode.name != "CERT_NONE"

    def test_env_flip_swaps_cached_client(self, monkeypatch):
        # _get_client() reads ssl_verify() per call and caches clients keyed
        # on (verify, timeout). Flipping the env var post-import must surface
        # a client with the new verify setting on the very next request.
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
        verifying = http_requests._get_client()
        assert verifying._transport._pool._ssl_context.verify_mode.name != "CERT_NONE"

        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        insecure = http_requests._get_client()
        assert insecure is not verifying
        assert insecure._transport._pool._ssl_context.verify_mode.name == "CERT_NONE"

        # Flipping back returns the original cached client (connection pool
        # preserved across env-var toggles).
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
        assert http_requests._get_client() is verifying


class TestInternalApiSslVerify:
    """The wandb thin API client passes ssl_verify() to gql transports."""

    def test_httpx_transport_gets_verify_false_if_ssl_disabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")

        mock_transport_cls = MagicMock()
        mock_transport_instance = MagicMock()
        mock_transport_cls.return_value = mock_transport_instance

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
            assert kwargs["verify"] is False

    def test_httpx_transport_gets_verify_true_by_default(self, monkeypatch):
        monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)

        mock_transport_cls = MagicMock()
        mock_transport_instance = MagicMock()
        mock_transport_cls.return_value = mock_transport_instance

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
            assert kwargs["verify"] is True
