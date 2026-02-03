"""Tests for the Weave CLI login command."""

from unittest.mock import patch

from click.testing import CliRunner

from weave.cli.login import login as login_command


def test_cli_login_passes_normalized_host() -> None:
    runner = CliRunner()
    api_key = "a" * 40

    with patch("weave.cli.login.wandb.login", return_value=True) as mock_login:
        result = runner.invoke(
            login_command,
            [api_key, "--host", "api.wandb.ai", "--relogin"],
        )

    assert result.exit_code == 0
    mock_login.assert_called_once_with(
        anonymous=None,
        key=api_key,
        relogin=True,
        host="https://api.wandb.ai",
        force=True,
        timeout=None,
        verify=False,
    )


def test_cli_login_failure_returns_error() -> None:
    runner = CliRunner()

    with patch("weave.cli.login.wandb.login", return_value=False):
        result = runner.invoke(login_command, [])

    assert result.exit_code != 0
    assert "Login failed." in result.output
