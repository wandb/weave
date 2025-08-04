"""Integration tests for wandb login functionality."""

from unittest.mock import Mock, patch

import pytest

from weave.compat.wandb.util.netrc import Netrc
from weave.compat.wandb.wandb_thin.login import _login, _validate_api_key
from weave.wandb_interface.context import (
    get_wandb_api_context,
    reset_wandb_api_context,
    set_wandb_api_context,
)


@pytest.mark.parametrize("api_key", ["valid-saas"], indirect=True)
def test_full_login_flow_with_netrc(tmp_path, api_key, mock_default_host):
    """Test complete login flow using netrc file."""
    netrc_path = tmp_path / ".netrc"

    # Create netrc with valid API key
    netrc_manager = Netrc(netrc_path)
    netrc_manager.add_or_update_entry(
        "api.wandb.ai",
        "user",
        api_key,  # Use fixture API key
    )

    with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
        mock_netrc_class.return_value = netrc_manager

        # Test login with existing credentials
        result = _login()

        assert result is True


@pytest.mark.parametrize("api_key", ["valid-saas"], indirect=True)
def test_full_login_flow_with_prompting(
    api_key, mock_netrc, mock_default_host, mock_app_url
):
    """Test complete login flow with user prompting."""
    mock_netrc.get_credentials.return_value = None  # No existing credentials

    with patch("click.prompt", return_value=api_key):
        result = _login()

        assert result is True
        # Should save the key
        mock_netrc.add_or_update_entry.assert_called_once_with(
            "api.wandb.ai", "user", api_key
        )


def test_context_integration():
    """Test wandb context integration."""
    # Test that context can be set and retrieved without errors
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


def test_weave_init_login_integration():
    """Test that weave init properly triggers login when needed."""
    from weave.trace.weave_init import get_entity_project_from_project_name

    # Test with authenticated API
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api.default_entity_name.return_value = "test_entity"
        mock_api_class.return_value = mock_api

        entity, project = get_entity_project_from_project_name("test_project")

        assert entity == "test_entity"
        assert project == "test_project"


def test_project_creator_integration():
    """Test project creator with realistic GraphQL responses."""
    from weave.wandb_interface.project_creator import _ensure_project_exists

    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Test existing project scenario
        project_response = {"project": {"name": "existing_project"}}
        mock_api.project.return_value = project_response

        result = _ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "existing_project"}
        mock_api.project.assert_called_once_with("test_entity", "test_project")


def test_end_to_end_authentication_flow():
    """Test end-to-end authentication flow simulation."""
    from weave.wandb_interface.context import from_environment

    # Simulate environment with API key
    with patch("weave.trace.env.weave_wandb_api_key", return_value="test_api_key"):
        with from_environment():
            context = get_wandb_api_context()
            assert context is not None
            assert context.api_key == "test_api_key"
            assert context.user_id == "admin"

        # After context manager, context should be cleared
        context_after = get_wandb_api_context()
        assert context_after is None


@pytest.mark.parametrize("api_key", ["valid-saas", "valid-onprem"], indirect=True)
def test_api_key_validation_success(api_key):
    """Test API key validation with valid keys in realistic scenarios."""
    _validate_api_key(api_key)  # Should not raise


@pytest.mark.parametrize(
    "api_key", ["invalid-too-short", "invalid-onprem-too-short"], indirect=True
)
def test_api_key_validation_failure(api_key):
    """Test API key validation with invalid keys in realistic scenarios."""
    with pytest.raises(ValueError):
        _validate_api_key(api_key)


def test_host_handling_integration(temp_config_dir):
    """Test host handling functionality in realistic scenarios."""
    from weave.compat.wandb.wandb_thin.login import (
        _get_host_from_settings,
        _handle_host_wandb_setting,
    )

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


def test_settings_management_integration(temp_config_dir):
    """Test settings management integration."""
    from weave.compat.wandb.wandb_thin.login import (
        _clear_setting,
        _get_host_from_settings,
        _set_setting,
    )

    # Test setting a value
    _set_setting("base_url", "https://custom.wandb.ai")

    # Test reading it back
    host = _get_host_from_settings()
    assert host == "custom.wandb.ai"

    # Test clearing it
    _clear_setting("base_url")

    host_after = _get_host_from_settings()
    assert host_after is None
