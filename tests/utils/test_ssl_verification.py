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

    The client is built lazily on first call to ``get_client()`` and then
    frozen — to assert behavior tied to env vars read at construction time
    we drop the cached client first via ``_reset_client_for_tests``.
    """

    def test_client_verify_disabled(self, monkeypatch):
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        http_requests._reset_client_for_tests()
        try:
            # httpx bakes the verify flag into an ssl_context on the transport pool;
            # CERT_NONE means SSL certificate verification is disabled.
            client = http_requests.get_client()
            assert isinstance(client._transport, httpx.HTTPTransport)
            assert client._transport._pool._ssl_context.verify_mode.name == "CERT_NONE"
        finally:
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            http_requests._reset_client_for_tests()

    def test_client_verify_enabled_by_default(self):
        # Without WEAVE_INSECURE_DISABLE_SSL set, the client should verify certs.
        client = http_requests.get_client()
        assert isinstance(client._transport, httpx.HTTPTransport)
        assert client._transport._pool._ssl_context.verify_mode.name != "CERT_NONE"

    def test_env_var_takes_effect_when_set_after_import(self, monkeypatch):
        """Regression for WB-33539.

        The client used to be constructed at module import time, so users
        setting ``WEAVE_INSECURE_DISABLE_SSL`` after ``import weave`` saw no
        effect. With lazy construction, the env var is read on first call.
        """
        http_requests._reset_client_for_tests()
        assert http_requests._client is None
        monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
        try:
            client = http_requests.get_client()
            assert client._transport._pool._ssl_context.verify_mode.name == "CERT_NONE"
        finally:
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            http_requests._reset_client_for_tests()

    def test_config_is_frozen_after_first_use(self, monkeypatch):
        """Documents the intentional freeze-after-first-use contract.

        httpx does not allow changing ``verify`` on a live client (the SSL
        context is owned by the connection pool — encode/httpx#554), so once
        the client is built, env-var changes are ignored. Callers that need
        to change SSL config must set the env var before the first HTTP call.
        """
        http_requests._reset_client_for_tests()
        try:
            # First call: verify enabled.
            first = http_requests.get_client()
            assert first._transport._pool._ssl_context.verify_mode.name != "CERT_NONE"

            # Flip the env var. The cached client should NOT change.
            monkeypatch.setenv(WEAVE_INSECURE_DISABLE_SSL, "true")
            second = http_requests.get_client()
            assert second is first
            assert second._transport._pool._ssl_context.verify_mode.name != "CERT_NONE"
        finally:
            monkeypatch.delenv(WEAVE_INSECURE_DISABLE_SSL, raising=False)
            http_requests._reset_client_for_tests()


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
