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
    """The shared httpx.Client in http_requests respects ssl_verify().

    The client is now created lazily on first use, so we use ``reset_client()``
    to drop the cached client and let the next access re-read the env var.
    """

    def test_client_verify_disabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        http_requests.reset_client()
        try:
            # httpx bakes the verify flag into an ssl_context on the transport pool;
            # CERT_NONE means SSL certificate verification is disabled.
            transport = http_requests.client._transport
            assert isinstance(transport, httpx.HTTPTransport)
            pool = transport._pool
            assert pool._ssl_context.verify_mode.name == "CERT_NONE"
        finally:
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            http_requests.reset_client()

    def test_client_verify_enabled_by_default(self):
        # Without WEAVE_INSECURE_DISABLE_SSL set, the client should verify certs.
        transport = http_requests.client._transport
        assert isinstance(transport, httpx.HTTPTransport)
        pool = transport._pool
        assert pool._ssl_context.verify_mode.name != "CERT_NONE"

    def test_client_is_lazy(self, monkeypatch):
        """Setting WEAVE_INSECURE_DISABLE_SSL after import still takes effect.

        Regression: the client used to be created at import time, so setting
        the env var after ``import weave`` was a no-op. With lazy init, the
        env var is read on first access.
        """
        http_requests.reset_client()
        assert http_requests._client is None
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        try:
            transport = http_requests.client._transport
            pool = transport._pool
            assert pool._ssl_context.verify_mode.name == "CERT_NONE"
        finally:
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            http_requests.reset_client()


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
