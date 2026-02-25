"""Tests for wandb login compatibility layer."""

import configparser
import os
from dataclasses import dataclass
from unittest.mock import patch

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
)
from weave.wandb_interface.context import (
    from_environment,
    get_wandb_api_context,
    reset_wandb_api_context,
    set_wandb_api_context,
)
from weave.wandb_interface.project_creator import _ensure_project_exists


@dataclass
class HostAndBaseURL:
    """Data class for host and base URL pairs."""

    host: str
    base_url: str


@pytest.fixture
def api_key(request):
    """Parametrized fixture for different API key formats."""
    if request.param == "valid-saas":
        return "a" * 86
    elif request.param == "valid-saas-legacy":
        return "a" * 40
    elif request.param == "valid-onprem":
        return "local-" + "b" * 86
    elif request.param == "valid-onprem-legacy":
        return "local-" + "b" * 40
    elif request.param == "invalid-too-short":
        return "short"
    elif request.param == "invalid-onprem-too-short":
        return "local-short-" + "c" * 39

    raise ValueError(f"Invalid API key type: {request.param}")


@pytest.fixture
def host_and_base_url(request):
    """Parametrized fixture for different host configurations."""
    if request.param == "saas":
        base_url = "https://api.wandb.ai"
        host = "api.wandb.ai"
    elif request.param == "aws":
        base_url = "https://example-aws.wandb.io"
        host = "example-aws.wandb.io"
    elif request.param == "gcp":
        base_url = "https://example-gcp.wandb.io"
        host = "example-gcp.wandb.io"
    elif request.param == "azure":
        base_url = "https://example-azure.wandb.io"
        host = "example-azure.wandb.io"
    elif request.param == "onprem":
        base_url = "https://wandb.customer.com"
        host = "wandb.customer.com"
    else:
        raise ValueError(f"Invalid host type: {request.param}")

    return HostAndBaseURL(host, base_url)


all_valid_keys = [
    "valid-saas",
    "valid-saas-legacy",
    "valid-onprem",
    "valid-onprem-legacy",
]
all_invalid_keys = [
    "invalid-too-short",
    "invalid-onprem-too-short",
]
all_hosts = ["saas", "aws", "gcp", "azure", "onprem"]


@pytest.mark.parametrize("api_key", all_valid_keys, indirect=True)
def test_validate_api_key_success(api_key):
    """All valid API keys should work."""
    _validate_api_key(api_key)


@pytest.mark.parametrize("api_key", all_invalid_keys, indirect=True)
def test_validate_api_key_failure(api_key):
    """All invalid API keys should raise ValueError."""
    with pytest.raises(ValueError, match="API key must be 40 characters long"):
        _validate_api_key(api_key)


@pytest.mark.parametrize("host_and_base_url", all_hosts, indirect=True)
def test_get_default_host_environment_variable(host_and_base_url):
    """If the WANDB_BASE_URL env var is set, it should take precedence."""
    with patch.dict(os.environ, {"WANDB_BASE_URL": host_and_base_url.base_url}):
        assert _get_default_host() == host_and_base_url.host


@pytest.mark.parametrize("host_and_base_url", all_hosts, indirect=True)
def test_get_default_host_settings_file(tmp_path, host_and_base_url):
    """If there is a settings file, it should be used."""
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
    """If there is no env var or settings file, it should fallback to api.wandb.ai."""
    with patch.dict(os.environ, {}, clear=True):
        with patch(
            "weave.compat.wandb.wandb_thin.login._get_host_from_settings",
            return_value=None,
        ):
            assert _get_default_host() == "api.wandb.ai"


def test_get_host_from_settings_missing_file(tmp_path):
    """If there is no settings file, it should return None."""
    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        assert _get_host_from_settings() is None


def test_set_setting(tmp_path):
    """Setting values should be written to the settings file."""
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
    """Clearing a setting should remove it from the settings file."""
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


def test_wandb_login_is_apikey_configured_from_netrc(mock_netrc, mock_default_host):
    """Test API key configuration detection from netrc."""
    mock_netrc.get_credentials.return_value = {"password": "test_api_key"}

    wlogin = _WandbLogin()
    assert wlogin.is_apikey_configured() is True


def test_wandb_login_is_apikey_configured_no_credentials(mock_netrc, mock_default_host):
    """Test API key configuration detection when no credentials exist."""
    mock_netrc.get_credentials.return_value = None

    wlogin = _WandbLogin()
    assert wlogin.is_apikey_configured() is False


def test_wandb_login_prompt_api_key_success(mock_default_host, mock_app_url):
    """Test successful API key prompting."""
    wlogin = _WandbLogin()

    valid_key = "a" * 40
    with patch("click.prompt", return_value=valid_key):
        key, status = wlogin._prompt_api_key()

        assert key == valid_key
        assert status == ApiKeyStatus.VALID


def test_wandb_login_prompt_api_key_abort(mock_default_host, mock_app_url):
    """Test API key prompting when user aborts."""
    wlogin = _WandbLogin()

    with patch("click.prompt", side_effect=click.Abort()):
        key, status = wlogin._prompt_api_key()

        assert key is None
        assert status == ApiKeyStatus.OFFLINE


def test_wandb_login_prompt_api_key_no_tty(mock_default_host, mock_app_url):
    """Test API key prompting when no TTY is available."""
    wlogin = _WandbLogin()

    with patch("click.prompt", side_effect=EOFError()):
        key, status = wlogin._prompt_api_key()

        assert key is None
        assert status == ApiKeyStatus.NOTTY


def test_wandb_login_prompt_api_key_invalid_then_valid(mock_default_host, mock_app_url):
    """Test API key prompting with invalid key followed by valid key."""
    wlogin = _WandbLogin()

    invalid_key = "short"
    valid_key = "a" * 40

    with patch("click.prompt", side_effect=[invalid_key, valid_key]):
        key, status = wlogin._prompt_api_key()

        assert key == valid_key
        assert status == ApiKeyStatus.VALID


def test_wandb_login_try_save_api_key(mock_netrc, mock_default_host):
    """Test saving API key to netrc."""
    wlogin = _WandbLogin()
    wlogin.try_save_api_key("test_key")

    mock_netrc.add_or_update_entry.assert_called_once_with(
        "api.wandb.ai", "user", "test_key"
    )


def test_wandb_login_try_save_api_key_with_url_host(mock_netrc):
    """URL hosts should be normalized before netrc write."""
    wlogin = _WandbLogin(host="https://custom.wandb.ai/")
    wlogin.try_save_api_key("test_key")

    mock_netrc.add_or_update_entry.assert_called_once_with(
        "custom.wandb.ai", "user", "test_key"
    )


def test_wandb_login_is_apikey_configured_with_url_host(mock_netrc):
    """URL hosts should be normalized before netrc lookup."""
    mock_netrc.get_credentials.return_value = {"password": "test_api_key"}

    wlogin = _WandbLogin(host="https://custom.wandb.ai/")
    assert wlogin.is_apikey_configured() is True
    mock_netrc.get_credentials.assert_called_once_with("custom.wandb.ai")


def test_login_internal_with_preconfigured_key(mock_netrc, mock_default_host):
    """Test internal login function with pre-configured key."""
    mock_netrc.get_credentials.return_value = {"password": "existing_key"}

    result = _login()

    assert result is True


def test_login_internal_with_provided_key(mock_netrc, mock_default_host):
    """Test internal login function with provided key."""
    result = _login(key="a" * 40)

    assert result is True
    mock_netrc.add_or_update_entry.assert_called_once_with(
        "api.wandb.ai", "user", "a" * 40
    )


def test_login_internal_with_provided_key_and_url_host(mock_netrc):
    """URL hosts should be normalized before key persistence."""
    result = _login(key="a" * 40, host="https://custom.wandb.ai/")

    assert result is True
    mock_netrc.add_or_update_entry.assert_called_once_with(
        "custom.wandb.ai", "user", "a" * 40
    )


def test_login_internal_with_prompting(mock_netrc, mock_default_host, mock_app_url):
    """Test internal login function with user prompting."""
    mock_netrc.get_credentials.return_value = None  # No existing credentials

    valid_key = "a" * 40
    with patch("click.prompt", return_value=valid_key):
        result = _login()

        assert result is True
        mock_netrc.add_or_update_entry.assert_called_once_with(
            "api.wandb.ai", "user", valid_key
        )


def test_login_internal_prompt_failure(mock_netrc, mock_default_host, mock_app_url):
    """Test internal login function when prompting fails."""
    mock_netrc.get_credentials.return_value = None

    with patch("click.prompt", side_effect=EOFError()):
        result = _login()

        assert result is False


def test_host_handling(temp_config_dir):
    """Test host handling functionality."""
    # Test handling default host (should clear setting)
    _handle_host_wandb_setting("https://api.wandb.ai")
    assert _get_host_from_settings() is None

    # Test handling custom host (should save setting)
    _handle_host_wandb_setting("https://custom.wandb.ai/")
    host = _get_host_from_settings()
    assert host == "custom.wandb.ai"  # Trailing slash removed

    # Test handling None (should clear setting)
    _handle_host_wandb_setting(None)
    assert _get_host_from_settings() is None


def test_settings_management(temp_config_dir):
    """Test setting, getting, and clearing settings."""
    # Test setting a value
    _set_setting("base_url", "https://custom.wandb.ai")

    # Test reading it back
    host = _get_host_from_settings()
    assert host == "custom.wandb.ai"

    # Test clearing it
    _clear_setting("base_url")

    host_after = _get_host_from_settings()
    assert host_after is None


@pytest.mark.parametrize("api_key", all_valid_keys, indirect=True)
def test_full_login_flow_with_netrc(api_key, mock_netrc, mock_default_host):
    """Test complete login flow using netrc file."""
    mock_netrc.get_credentials.return_value = {
        "login": "user",
        "account": "",
        "password": api_key,
    }

    result = _login()
    assert result is True  # User is logged in
    mock_netrc.add_or_update_entry.assert_not_called()  # No new creds are saved


@pytest.mark.parametrize("api_key", all_valid_keys, indirect=True)
def test_full_login_flow_without_netrc(
    api_key, mock_netrc, mock_default_host, mock_app_url
):
    """Test complete login flow with user prompting."""
    mock_netrc.get_credentials.return_value = None

    with patch("click.prompt", return_value=api_key):
        result = _login()
        assert result is True  # User is logged in
        mock_netrc.add_or_update_entry.assert_called_once_with(  # New creds are saved
            "api.wandb.ai", "user", api_key
        )


def test_wandb_context():
    """Test that the wandb context can be set and retrieved without errors."""
    token = set_wandb_api_context("test_user", "test_key", None, None)

    try:
        context = get_wandb_api_context()
        assert context is not None
        assert context.user_id == "test_user"
        assert context.api_key == "test_key"
    finally:
        if token:
            reset_wandb_api_context(token)

    # Verify context is cleared
    context_after = get_wandb_api_context()
    assert context_after is None


def test_auth_from_env_environment():
    """Test authentication from environment."""
    with patch("weave.trace.env.weave_wandb_api_key", return_value="test_api_key"):
        with from_environment():
            context = get_wandb_api_context()
            assert context is not None
            assert context.api_key == "test_api_key"
            assert context.user_id == "admin"

        # After context manager, context should be cleared
        context_after = get_wandb_api_context()
        assert context_after is None


def test_project_create_if_not_exists(mock_wandb_api):
    mock_wandb_api.project.return_value = None
    mock_wandb_api.upsert_project.return_value = {
        "upsertModel": {"model": {"name": "test_project"}}
    }
    res = _ensure_project_exists("test_entity", "test_project")
    assert res == {"project_name": "test_project"}
    mock_wandb_api.project.assert_called_once_with("test_entity", "test_project")
    mock_wandb_api.upsert_project.assert_called_once_with(
        entity="test_entity", project="test_project"
    )


def test_no_project_create_if_exists(mock_wandb_api):
    mock_wandb_api.project.return_value = {"project": {"name": "test_project"}}
    res = _ensure_project_exists("test_entity", "test_project")
    assert res == {"project_name": "test_project"}
    mock_wandb_api.project.assert_called_once_with("test_entity", "test_project")
    mock_wandb_api.upsert_project.assert_not_called()
