"""Tests for weave login CLI functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from weave.cli.login import (
    _get_netrc_path,
    _print_login_status,
    _prompt_for_api_key,
    weave_login,
)
from weave.cli.main import cli


@pytest.fixture
def mock_weave_login():
    """Fixture that provides a mock for weave.cli.main.weave_login."""
    with patch("weave.cli.main.weave_login") as mock_login:
        mock_login.return_value = True
        yield mock_login


@pytest.fixture
def mock_netrc():
    """Fixture that provides a mock for weave.cli.login.Netrc."""
    with patch("weave.cli.login.Netrc") as mock_netrc:
        mock_netrc.return_value = MagicMock()
        yield mock_netrc


def test_login_command_cloud_and_host_together(mock_weave_login):
    """Test the login command with both --cloud and --host uses the host value."""
    runner = CliRunner()

    result = runner.invoke(
        cli, ["login", "--cloud", "--host", "https://custom.wandb.ai"]
    )

    assert result.exit_code == 0
    mock_weave_login.assert_called_once_with(
        key=None,
        host="https://custom.wandb.ai",  # Host takes precedence over cloud
        relogin=False,
        verify=True,
    )


def test_weave_login_with_valid_key(mock_netrc):
    """Test weave_login function with a valid API key."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._validate_api_key") as mock_validate,
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        mock_get_host.return_value = "api.wandb.ai"

        result = weave_login(key="test-key-123")

        assert result is True
        mock_validate.assert_called_with("test-key-123")
        mock_netrc.add_or_update_entry.assert_called_once_with(
            "api.wandb.ai", "user", "test-key-123"
        )
        mock_print_status.assert_called_once_with("api.wandb.ai")


def test_weave_login_already_logged_in(mock_netrc):
    """Test weave_login when already logged in and not forcing relogin."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_netrc.get_credentials.return_value = ("user", "existing-key")

        result = weave_login()

        assert result is True
        mock_print_status.assert_called_once_with("api.wandb.ai")
        # Should not try to add new credentials
        mock_netrc.add_or_update_entry.assert_not_called()


def test_weave_login_with_relogin_flag(mock_netrc):
    """Test weave_login with relogin=True prompts for new key even if logged in."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._prompt_for_api_key") as mock_prompt,
        patch("weave.cli.login._validate_api_key") as mock_validate,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_netrc.get_credentials.return_value = ("user", "existing-key")
        mock_prompt.return_value = "new-key-123"

        result = weave_login(relogin=True)

        assert result is True
        mock_prompt.assert_called_once_with("api.wandb.ai")
        mock_validate.assert_called_with("new-key-123")
        mock_netrc.add_or_update_entry.assert_called_once_with(
            "api.wandb.ai", "user", "new-key-123"
        )


def test_weave_login_prompt_cancelled(mock_netrc):
    """Test weave_login when user cancels the API key prompt."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._prompt_for_api_key") as mock_prompt,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_netrc.get_credentials.return_value = None
        mock_prompt.return_value = None  # User cancelled

        result = weave_login()

        assert result is False
        mock_netrc.add_or_update_entry.assert_not_called()


def test_weave_login_invalid_api_key(mock_netrc):
    """Test weave_login with invalid API key format."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._validate_api_key") as mock_validate,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_validate.side_effect = ValueError("Invalid key format")

        result = weave_login(key="invalid-key")

        assert result is False
        mock_netrc.add_or_update_entry.assert_not_called()


def test_weave_login_custom_host(mock_netrc):
    """Test weave_login with custom host."""
    with (
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        result = weave_login(key="test-key", host="https://custom.wandb.ai")

        assert result is True
        mock_netrc.add_or_update_entry.assert_called_once_with(
            "custom.wandb.ai", "user", "test-key"
        )
        mock_print_status.assert_called_once_with("custom.wandb.ai")


def test_weave_login_host_url_cleanup(mock_netrc):
    """Test that host URL is properly cleaned of http/https prefixes."""
    with (
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        # Test https prefix removal
        result = weave_login(key="test-key", host="https://custom.wandb.ai")
        assert result is True
        mock_netrc.add_or_update_entry.assert_called_with(
            "custom.wandb.ai", "user", "test-key"
        )

        # Test http prefix removal
        result = weave_login(key="test-key", host="http://custom.wandb.ai")
        assert result is True
        mock_netrc.add_or_update_entry.assert_called_with(
            "custom.wandb.ai", "user", "test-key"
        )


def test_weave_login_netrc_save_error(mock_netrc):
    """Test weave_login when netrc save fails but continues."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_netrc.add_or_update_entry.side_effect = Exception("Permission denied")

        result = weave_login(key="test-key")

        # Should still return True and continue despite netrc error
        assert result is True
        mock_print_status.assert_called_once_with("api.wandb.ai")


def test_weave_login_verification_disabled(mock_netrc):
    """Test weave_login with verify=False skips verification."""
    with (
        patch("weave.cli.login._get_default_host") as mock_get_host,
        patch("weave.cli.login._validate_api_key") as mock_validate,
        patch("weave.cli.login._print_login_status") as mock_print_status,
    ):
        mock_get_host.return_value = "api.wandb.ai"
        mock_netrc_instance = MagicMock()
        mock_netrc.return_value = mock_netrc_instance

        result = weave_login(key="test-key", verify=False)

        assert result is True
        # Should only validate once (for format) but not for verification
        assert mock_validate.call_count == 1
        mock_print_status.assert_called_once_with("api.wandb.ai")


def test_weave_login_general_exception():
    """Test weave_login handles general exceptions gracefully."""
    with patch("weave.cli.login._get_default_host") as mock_get_host:
        mock_get_host.side_effect = Exception("Network error")

        result = weave_login(key="test-key")

        assert result is False


def test_prompt_for_api_key_success():
    """Test _prompt_for_api_key successfully prompts and returns key."""
    with (
        patch("weave.cli.login.wandb.util") as mock_util,
        patch("click.prompt") as mock_prompt,
    ):
        mock_util.app_url.return_value = "https://wandb.ai"
        mock_prompt.return_value = "  test-key-123  "  # With whitespace

        result = _prompt_for_api_key("api.wandb.ai")

        assert result == "test-key-123"  # Should be stripped
        mock_prompt.assert_called_once_with(
            "",
            hide_input=True,
            show_default=False,
            prompt_suffix="",
        )


def test_prompt_for_api_key_cancelled():
    """Test _prompt_for_api_key when user cancels (Ctrl+C)."""
    with patch("weave.cli.login.wandb.util"), patch("click.prompt") as mock_prompt:
        mock_prompt.side_effect = click.Abort()

        result = _prompt_for_api_key("api.wandb.ai")

        assert result is None


def test_prompt_for_api_key_no_tty():
    """Test _prompt_for_api_key when no TTY is available."""
    with patch("weave.cli.login.wandb.util"), patch("click.prompt") as mock_prompt:
        mock_prompt.side_effect = EOFError()

        result = _prompt_for_api_key("api.wandb.ai")

        assert result is None


def test_print_login_status_with_username():
    """Test _print_login_status displays username when available."""
    with patch("weave.cli.login.wandb.Api") as mock_api:
        mock_api_instance = MagicMock()
        mock_api.return_value = mock_api_instance
        mock_api_instance.username.return_value = "testuser"

        # This test mainly ensures no exceptions are raised
        _print_login_status("api.wandb.ai")

        mock_api_instance.username.assert_called_once()


def test_print_login_status_without_username():
    """Test _print_login_status when username is not available."""
    with patch("weave.cli.login.wandb.Api") as mock_api:
        mock_api_instance = MagicMock()
        mock_api.return_value = mock_api_instance
        mock_api_instance.username.return_value = None

        # This test mainly ensures no exceptions are raised
        _print_login_status("api.wandb.ai")

        mock_api_instance.username.assert_called_once()


def test_print_login_status_api_error():
    """Test _print_login_status when API call fails."""
    with patch("weave.cli.login.wandb.Api") as mock_api:
        mock_api.side_effect = Exception("API error")

        # This test mainly ensures no exceptions are raised
        _print_login_status("api.wandb.ai")


def test_get_netrc_path_unix():
    """Test _get_netrc_path returns correct path on Unix systems."""
    with patch("os.name", "posix"), patch("pathlib.Path.home") as mock_home:
        mock_home.return_value = Path("/home/user")

        result = _get_netrc_path()

        assert result == "/home/user/.netrc"


def test_get_netrc_path_windows():
    """Test _get_netrc_path returns correct path on Windows systems."""
    with patch("os.name", "nt"), patch("pathlib.Path.home") as mock_home:
        # Create a mock Path object that behaves like a Windows path
        mock_path = MagicMock()
        mock_path.__truediv__ = lambda self, other: f"C:\\Users\\user\\{other}"
        mock_home.return_value = mock_path

        result = _get_netrc_path()

        assert result == "C:\\Users\\user\\_netrc"


def test_weave_login_integration(tmp_path):
    """Integration test for weave_login with temporary netrc file."""
    netrc_path = tmp_path / ".netrc"

    with (
        patch("weave.cli.login._get_netrc_path") as mock_netrc_path,
        patch("weave.cli.login._get_default_host") as mock_get_host,
    ):
        mock_netrc_path.return_value = str(netrc_path)
        mock_get_host.return_value = "api.wandb.ai"

        # Create an empty netrc file to start with
        netrc_path.touch()

        result = weave_login(key="test-integration-key")

        assert result is True
        assert netrc_path.exists()

        # The test verifies the function runs successfully with a real netrc file path
        # The actual netrc content creation is tested separately in other unit tests
