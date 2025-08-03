"""Tests for wandb login compatibility layer."""

import configparser
import os
from unittest.mock import Mock, patch

import click
import pytest

from weave.compat.wandb.wandb_thin.login import (
    ApiKeyStatus,
    _clear_setting,
    _get_default_host,
    _get_host_from_settings,
    _handle_host_wandb_setting,
    _login,
    _set_setting,
    _validate_api_key,
    _WandbLogin,
    login,
)


def test_validate_api_key_success():
    """Test API key validation with valid keys."""
    # Normal 40-character key
    valid_key = "a" * 40
    _validate_api_key(valid_key)  # Should not raise

    # On-prem style key with dash
    valid_onprem_key = "local-" + "b" * 40
    _validate_api_key(valid_onprem_key)  # Should not raise


def test_validate_api_key_failure():
    """Test API key validation with invalid keys."""
    # Too short
    with pytest.raises(ValueError, match="API key must be 40 characters long"):
        _validate_api_key("short")

    # Too long
    with pytest.raises(ValueError, match="API key must be 40 characters long"):
        _validate_api_key("a" * 41)

    # On-prem key with wrong length after dash
    with pytest.raises(ValueError, match="API key must be 40 characters long"):
        _validate_api_key("local-short")


def test_get_default_host_environment_variable():
    """Test default host resolution from environment variable."""
    with patch.dict(os.environ, {"WANDB_BASE_URL": "https://custom.wandb.ai/"}):
        assert _get_default_host() == "custom.wandb.ai"


def test_get_default_host_settings_file(tmp_path):
    """Test default host resolution from settings file."""
    settings_path = tmp_path / "settings"

    # Create settings file with base_url
    config = configparser.ConfigParser()
    config.add_section("default")
    config.set("default", "base_url", "https://custom.wandb.server")

    with open(settings_path, "w") as f:
        config.write(f)

    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        assert _get_default_host() == "custom.wandb.server"


def test_get_default_host_fallback():
    """Test default host fallback to api.wandb.ai."""
    with patch.dict(os.environ, {}, clear=True):
        with patch(
            "weave.compat.wandb.wandb_thin.login._get_host_from_settings",
            return_value=None,
        ):
            assert _get_default_host() == "api.wandb.ai"


def test_get_host_from_settings_missing_file(tmp_path):
    """Test getting host from settings when file doesn't exist."""
    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        assert _get_host_from_settings() is None


def test_set_setting(tmp_path):
    """Test setting configuration values."""
    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        _set_setting("base_url", "https://test.wandb.ai")

        # Verify setting was written
        settings_path = tmp_path / "settings"
        assert settings_path.exists()

        config = configparser.ConfigParser()
        config.read(str(settings_path))

        assert config.has_section("default")
        assert config.get("default", "base_url") == "https://test.wandb.ai"


def test_clear_setting(tmp_path):
    """Test clearing configuration values."""
    settings_path = tmp_path / "settings"

    # Create settings file with a setting
    config = configparser.ConfigParser()
    config.add_section("default")
    config.set("default", "base_url", "https://test.wandb.ai")

    with open(settings_path, "w") as f:
        config.write(f)

    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        _clear_setting("base_url")

        # Verify setting was cleared
        config_after = configparser.ConfigParser()
        config_after.read(str(settings_path))

        assert not config_after.has_option("default", "base_url")


def test_handle_host_wandb_setting_default():
    """Test host setting handling for default values."""
    with patch("weave.compat.wandb.wandb_thin.login._clear_setting") as mock_clear:
        _handle_host_wandb_setting("https://api.wandb.ai")
        mock_clear.assert_called_once_with("base_url")

    with patch("weave.compat.wandb.wandb_thin.login._clear_setting") as mock_clear:
        _handle_host_wandb_setting(None)
        mock_clear.assert_called_once_with("base_url")


def test_handle_host_wandb_setting_custom():
    """Test host setting handling for custom values."""
    with patch("weave.compat.wandb.wandb_thin.login._set_setting") as mock_set:
        _handle_host_wandb_setting("https://custom.wandb.ai/")
        mock_set.assert_called_once_with("base_url", "https://custom.wandb.ai")


def test_wandb_login_initialization():
    """Test WandbLogin class initialization."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin(
            anonymous="never",
            force=True,
            host="custom.wandb.ai",
            key="test_key",
            relogin=True,
            timeout=30,
        )

        assert wlogin._relogin is True
        assert wlogin._force is True
        assert wlogin._timeout == 30
        assert wlogin._key == "test_key"
        assert wlogin._host == "custom.wandb.ai"
        assert wlogin.is_anonymous is False


def test_wandb_login_is_apikey_configured_with_key():
    """Test API key configuration detection when key is provided."""
    wlogin = _WandbLogin(key="test_key")
    assert wlogin.is_apikey_configured() is True


def test_wandb_login_is_apikey_configured_from_netrc():
    """Test API key configuration detection from netrc."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        mock_credentials = {"password": "test_api_key"}
        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc.get_credentials.return_value = mock_credentials
            mock_netrc_class.return_value = mock_netrc

            assert wlogin.is_apikey_configured() is True


def test_wandb_login_is_apikey_configured_no_credentials():
    """Test API key configuration detection when no credentials exist."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc.get_credentials.return_value = None
            mock_netrc_class.return_value = mock_netrc

            assert wlogin.is_apikey_configured() is False


def test_wandb_login_prompt_api_key_success():
    """Test successful API key prompting."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        valid_key = "a" * 40
        with patch("click.prompt", return_value=valid_key):
            with patch(
                "weave.compat.wandb.wandb_thin.util.app_url",
                return_value="https://wandb.ai",
            ):
                key, status = wlogin._prompt_api_key()

                assert key == valid_key
                assert status == ApiKeyStatus.VALID


def test_wandb_login_prompt_api_key_abort():
    """Test API key prompting when user aborts."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        with patch("click.prompt", side_effect=click.Abort()):
            with patch(
                "weave.compat.wandb.wandb_thin.util.app_url",
                return_value="https://wandb.ai",
            ):
                key, status = wlogin._prompt_api_key()

                assert key is None
                assert status == ApiKeyStatus.OFFLINE


def test_wandb_login_prompt_api_key_no_tty():
    """Test API key prompting when no TTY is available."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        with patch("click.prompt", side_effect=EOFError()):
            with patch(
                "weave.compat.wandb.wandb_thin.util.app_url",
                return_value="https://wandb.ai",
            ):
                key, status = wlogin._prompt_api_key()

                assert key is None
                assert status == ApiKeyStatus.NOTTY


def test_wandb_login_prompt_api_key_invalid_then_valid():
    """Test API key prompting with invalid key followed by valid key."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        invalid_key = "short"
        valid_key = "a" * 40

        with patch("click.prompt", side_effect=[invalid_key, valid_key]):
            with patch(
                "weave.compat.wandb.wandb_thin.util.app_url",
                return_value="https://wandb.ai",
            ):
                key, status = wlogin._prompt_api_key()

                assert key == valid_key
                assert status == ApiKeyStatus.VALID


def test_wandb_login_try_save_api_key():
    """Test saving API key to netrc."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        wlogin = _WandbLogin()

        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc_class.return_value = mock_netrc

            wlogin.try_save_api_key("test_key")

            mock_netrc.add_or_update_entry.assert_called_once_with(
                "api.wandb.ai", "user", "test_key"
            )


def test_login_function_signature():
    """Test login function with all parameters."""
    with patch("weave.compat.wandb.wandb_thin.login._handle_host_wandb_setting"):
        with patch(
            "weave.compat.wandb.wandb_thin.login._login", return_value=True
        ) as mock_login:
            result = login(
                anonymous="never",
                key="test_key",
                relogin=True,
                host="custom.wandb.ai",
                force=True,
                timeout=30,
                verify=True,
                referrer="test",
            )

            assert result is True
            mock_login.assert_called_once_with(
                anonymous="never",
                key="test_key",
                relogin=True,
                host="custom.wandb.ai",
                force=True,
                timeout=30,
                verify=True,
                referrer="test",
            )


def test_login_internal_with_preconfigured_key():
    """Test internal login function with pre-configured key."""
    with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
        mock_netrc = Mock()
        mock_credentials = {"password": "existing_key"}
        mock_netrc.get_credentials.return_value = mock_credentials
        mock_netrc_class.return_value = mock_netrc

        with patch(
            "weave.compat.wandb.wandb_thin.login._get_default_host",
            return_value="api.wandb.ai",
        ):
            result = _login()

            assert result is True


def test_login_internal_with_provided_key():
    """Test internal login function with provided key."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc_class.return_value = mock_netrc

            result = _login(key="a" * 40)

            assert result is True
            mock_netrc.add_or_update_entry.assert_called_once_with(
                "api.wandb.ai", "user", "a" * 40
            )


def test_login_internal_with_prompting():
    """Test internal login function with user prompting."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc.get_credentials.return_value = None  # No existing credentials
            mock_netrc_class.return_value = mock_netrc

            valid_key = "a" * 40
            with patch("click.prompt", return_value=valid_key):
                with patch(
                    "weave.compat.wandb.wandb_thin.util.app_url",
                    return_value="https://wandb.ai",
                ):
                    result = _login()

                    assert result is True
                    mock_netrc.add_or_update_entry.assert_called_once_with(
                        "api.wandb.ai", "user", valid_key
                    )


def test_login_internal_prompt_failure():
    """Test internal login function when prompting fails."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc.get_credentials.return_value = None
            mock_netrc_class.return_value = mock_netrc

            with patch("click.prompt", side_effect=EOFError()):
                with patch(
                    "weave.compat.wandb.wandb_thin.util.app_url",
                    return_value="https://wandb.ai",
                ):
                    result = _login()

                    assert result is False


def test_login_internal_with_verification():
    """Test internal login function with key verification."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        valid_key = "a" * 40
        result = _login(key=valid_key, verify=True)

        assert result is True


def test_login_internal_verification_failure():
    """Test internal login function when verification fails."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        invalid_key = "short"
        result = _login(key=invalid_key, verify=True)

        assert result is False
