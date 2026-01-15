"""Tests for the weave CLI doctor command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from weave.cli import (
    CheckResult,
    _check_api_key,
    _check_authentication,
    _check_base_url,
    _check_trace_server_connectivity,
    _check_trace_server_url,
    _check_version_compatibility,
    cli,
    doctor,
)
from weave.trace_server_bindings.models import ServerInfoRes


@pytest.fixture
def cli_runner():
    return CliRunner()


class TestCheckResult:
    def test_check_result_creation(self):
        result = CheckResult(
            name="Test Check",
            passed=True,
            message="Test passed",
            details="Some details",
        )
        assert result.name == "Test Check"
        assert result.passed is True
        assert result.message == "Test passed"
        assert result.details == "Some details"

    def test_check_result_without_details(self):
        result = CheckResult(name="Test", passed=False, message="Failed")
        assert result.details == ""


class TestCheckApiKey:
    def test_api_key_from_env(self):
        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            with patch("weave.cli.env._wandb_api_key_via_env") as mock_env:
                mock_key.return_value = "test_api_key_12345678"
                mock_env.return_value = "test_api_key_12345678"
                result = _check_api_key()
                assert result.passed is True
                assert "WANDB_API_KEY environment variable" in result.message

    def test_api_key_from_netrc(self):
        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            with patch("weave.cli.env._wandb_api_key_via_env") as mock_env:
                mock_key.return_value = "test_api_key_12345678"
                mock_env.return_value = None
                result = _check_api_key()
                assert result.passed is True
                assert "netrc file" in result.message

    def test_api_key_not_found(self):
        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            mock_key.return_value = None
            result = _check_api_key()
            assert result.passed is False
            assert "Not found" in result.message


class TestCheckBaseUrl:
    def test_default_base_url(self):
        with patch("weave.cli.env.wandb_base_url") as mock_url:
            mock_url.return_value = "https://api.wandb.ai"
            result = _check_base_url()
            assert result.passed is True
            assert "https://api.wandb.ai" in result.message
            assert "Default" in result.details

    def test_custom_base_url(self):
        with patch("weave.cli.env.wandb_base_url") as mock_url:
            mock_url.return_value = "https://custom.wandb.ai"
            result = _check_base_url()
            assert result.passed is True
            assert "https://custom.wandb.ai" in result.message
            assert "Custom" in result.details


class TestCheckTraceServerUrl:
    def test_default_trace_server_url(self):
        with patch("weave.cli.env.weave_trace_server_url") as mock_url:
            with patch("weave.cli.env.MTSAAS_TRACE_URL", "https://trace.wandb.ai"):
                mock_url.return_value = "https://trace.wandb.ai"
                result = _check_trace_server_url()
                assert result.passed is True
                assert "https://trace.wandb.ai" in result.message

    def test_custom_trace_server_url(self):
        with patch("weave.cli.env.weave_trace_server_url") as mock_url:
            with patch("weave.cli.env.MTSAAS_TRACE_URL", "https://trace.wandb.ai"):
                mock_url.return_value = "https://custom-trace.example.com"
                result = _check_trace_server_url()
                assert result.passed is True
                assert "https://custom-trace.example.com" in result.message


class TestCheckTraceServerConnectivity:
    def test_successful_connection(self):
        mock_server_info = ServerInfoRes(
            min_required_weave_python_version="0.1.0",
            trace_server_version="1.0.0",
        )
        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server.server_info.return_value = mock_server_info
            mock_server_class.return_value = mock_server

            with patch("weave.cli.env.weave_trace_server_url") as mock_url:
                mock_url.return_value = "https://trace.wandb.ai"
                result = _check_trace_server_connectivity("test_api_key")
                assert result.passed is True
                assert "Connected successfully" in result.message
                assert "1.0.0" in result.details

    def test_connection_error(self):
        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server.server_info.side_effect = httpx.ConnectError("Connection refused")
            mock_server_class.return_value = mock_server

            with patch("weave.cli.env.weave_trace_server_url") as mock_url:
                mock_url.return_value = "https://trace.wandb.ai"
                result = _check_trace_server_connectivity("test_api_key")
                assert result.passed is False
                assert "Connection failed" in result.message

    def test_authentication_error(self):
        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
            mock_server = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_server.server_info.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
            mock_server_class.return_value = mock_server

            with patch("weave.cli.env.weave_trace_server_url") as mock_url:
                mock_url.return_value = "https://trace.wandb.ai"
                result = _check_trace_server_connectivity("test_api_key")
                assert result.passed is False
                assert "Authentication failed" in result.message


class TestCheckVersionCompatibility:
    def test_compatible_versions(self):
        mock_server_info = ServerInfoRes(
            min_required_weave_python_version="0.1.0",
            trace_server_version="1.0.0",
        )
        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server.server_info.return_value = mock_server_info
            mock_server_class.return_value = mock_server

            with patch("weave.cli.env.weave_trace_server_url") as mock_url:
                mock_url.return_value = "https://trace.wandb.ai"
                with patch("weave.cli.weave.__version__", "0.50.0"):
                    with patch("weave.cli.MIN_TRACE_SERVER_VERSION", None):
                        result = _check_version_compatibility("test_api_key")
                        assert result.passed is True
                        assert "Compatible" in result.message

    def test_client_version_too_old(self):
        mock_server_info = ServerInfoRes(
            min_required_weave_python_version="99.0.0",
            trace_server_version="1.0.0",
        )
        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
            mock_server = MagicMock()
            mock_server.server_info.return_value = mock_server_info
            mock_server_class.return_value = mock_server

            with patch("weave.cli.env.weave_trace_server_url") as mock_url:
                mock_url.return_value = "https://trace.wandb.ai"
                with patch("weave.cli.weave.__version__", "0.50.0"):
                    result = _check_version_compatibility("test_api_key")
                    assert result.passed is False
                    assert "Client version too old" in result.message


class TestCheckAuthentication:
    def test_no_api_key(self):
        result = _check_authentication(None)
        assert result.passed is False
        assert "No API key configured" in result.message

    def test_successful_authentication(self):
        mock_context = MagicMock()
        mock_context.user_id = "user123"
        with patch("weave.wandb_interface.context.get_wandb_api_context") as mock_get_context:
            with patch("weave.wandb_interface.context.init"):
                mock_get_context.return_value = mock_context
                result = _check_authentication("test_api_key")
                assert result.passed is True
                assert "Authenticated" in result.message


class TestDoctorCommand:
    def test_doctor_help(self, cli_runner):
        result = cli_runner.invoke(doctor, ["--help"])
        assert result.exit_code == 0
        assert "Test connectivity and configuration" in result.output

    def test_doctor_all_checks_pass(self, cli_runner):
        mock_server_info = ServerInfoRes(
            min_required_weave_python_version="0.1.0",
            trace_server_version="1.0.0",
        )
        mock_context = MagicMock()
        mock_context.user_id = "user123"

        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            with patch("weave.cli.env._wandb_api_key_via_env") as mock_env:
                with patch("weave.cli.env.wandb_base_url") as mock_base_url:
                    with patch("weave.cli.env.weave_trace_server_url") as mock_trace_url:
                        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
                            with patch("weave.wandb_interface.context.get_wandb_api_context") as mock_get_context:
                                with patch("weave.wandb_interface.context.init"):
                                    with patch("weave.cli.env.MTSAAS_TRACE_URL", "https://trace.wandb.ai"):
                                        mock_key.return_value = "test_api_key_12345678"
                                        mock_env.return_value = "test_api_key_12345678"
                                        mock_base_url.return_value = "https://api.wandb.ai"
                                        mock_trace_url.return_value = "https://trace.wandb.ai"

                                        mock_server = MagicMock()
                                        mock_server.server_info.return_value = mock_server_info
                                        mock_server_class.return_value = mock_server

                                        mock_get_context.return_value = mock_context

                                        with patch("weave.cli.weave.__version__", "0.50.0"):
                                            with patch("weave.cli.MIN_TRACE_SERVER_VERSION", None):
                                                result = cli_runner.invoke(doctor)
                                                assert result.exit_code == 0
                                                assert "All checks passed" in result.output

    def test_doctor_verbose_output(self, cli_runner):
        mock_server_info = ServerInfoRes(
            min_required_weave_python_version="0.1.0",
            trace_server_version="1.0.0",
        )
        mock_context = MagicMock()
        mock_context.user_id = "user123"

        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            with patch("weave.cli.env._wandb_api_key_via_env") as mock_env:
                with patch("weave.cli.env.wandb_base_url") as mock_base_url:
                    with patch("weave.cli.env.weave_trace_server_url") as mock_trace_url:
                        with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
                            with patch("weave.wandb_interface.context.get_wandb_api_context") as mock_get_context:
                                with patch("weave.wandb_interface.context.init"):
                                    with patch("weave.cli.env.MTSAAS_TRACE_URL", "https://trace.wandb.ai"):
                                        mock_key.return_value = "test_api_key_12345678"
                                        mock_env.return_value = "test_api_key_12345678"
                                        mock_base_url.return_value = "https://api.wandb.ai"
                                        mock_trace_url.return_value = "https://trace.wandb.ai"

                                        mock_server = MagicMock()
                                        mock_server.server_info.return_value = mock_server_info
                                        mock_server_class.return_value = mock_server

                                        mock_get_context.return_value = mock_context

                                        with patch("weave.cli.weave.__version__", "0.50.0"):
                                            with patch("weave.cli.MIN_TRACE_SERVER_VERSION", None):
                                                result = cli_runner.invoke(doctor, ["--verbose"])
                                                assert result.exit_code == 0
                                                # Verbose mode should show details
                                                assert "Server version:" in result.output

    def test_doctor_with_failures(self, cli_runner):
        with patch("weave.cli.env.weave_wandb_api_key") as mock_key:
            mock_key.return_value = None  # No API key will cause failures

            with patch("weave.cli.env.wandb_base_url") as mock_base_url:
                with patch("weave.cli.env.weave_trace_server_url") as mock_trace_url:
                    with patch("weave.cli.RemoteHTTPTraceServer") as mock_server_class:
                        with patch("weave.cli.env.MTSAAS_TRACE_URL", "https://trace.wandb.ai"):
                            mock_base_url.return_value = "https://api.wandb.ai"
                            mock_trace_url.return_value = "https://trace.wandb.ai"

                            mock_server = MagicMock()
                            mock_server.server_info.side_effect = httpx.ConnectError("Connection refused")
                            mock_server_class.return_value = mock_server

                            result = cli_runner.invoke(doctor)
                            assert result.exit_code == 1
                            assert "Some checks failed" in result.output


class TestCliGroup:
    def test_cli_version(self, cli_runner):
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "weave" in result.output

    def test_cli_help(self, cli_runner):
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "doctor" in result.output
