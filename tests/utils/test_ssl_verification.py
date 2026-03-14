"""Tests for SSL verification behavior controlled by WEAVE_INSECURE_DISABLE_SSL."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.trace.env import WEAVE_INSECURE_DISABLE_SSL, ssl_verify


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
    """The global httpx.Client in http_requests respects ssl_verify()."""

    def test_client_verify_disabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        from weave.utils import http_requests

        importlib.reload(http_requests)
        try:
            # httpx stores verify as an ssl_context on the transport pool
            transport = http_requests.client._transport
            assert isinstance(transport, httpx.HTTPTransport)
            pool = transport._pool
            assert pool._ssl_context.verify_mode.name == "CERT_NONE"
        finally:
            # Restore default state
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            importlib.reload(http_requests)

    def test_client_verify_enabled_by_default(self):
        from weave.utils import http_requests

        transport = http_requests.client._transport
        assert isinstance(transport, httpx.HTTPTransport)
        pool = transport._pool
        assert pool._ssl_context.verify_mode.name != "CERT_NONE"


class TestInternalApiSslVerify:
    """The wandb thin API client passes ssl_verify() to gql transports."""

    def test_httpx_transport_gets_verify_false(self, monkeypatch):
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
            from weave.compat.wandb.wandb_thin.internal_api import Api
            import gql

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
            from weave.compat.wandb.wandb_thin.internal_api import Api
            import gql

            api = Api()
            api.query(gql.gql("{ viewer { username } }"))

            _, kwargs = mock_transport_cls.call_args
            assert kwargs["verify"] is True
