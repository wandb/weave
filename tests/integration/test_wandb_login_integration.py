"""Integration tests for wandb login functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from weave.compat.wandb.util.netrc import Netrc
from weave.compat.wandb.wandb_thin.login import login, _login
from weave.wandb_interface.context import get_wandb_api_context, set_wandb_api_context, reset_wandb_api_context


def test_full_login_flow_with_netrc():
    """Test complete login flow using netrc file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        netrc_path = Path(temp_dir) / ".netrc"
        
        # Create netrc with valid API key
        netrc_manager = Netrc(netrc_path)
        netrc_manager.add_or_update_entry(
            "api.wandb.ai",
            "user", 
            "a" * 40  # Valid 40-character key
        )
        
        # Mock the netrc path
        with patch("weave.compat.wandb.wandb_thin.login._get_default_host", return_value="api.wandb.ai"):
            with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
                mock_netrc_class.return_value = netrc_manager
                
                # Test login with existing credentials
                result = _login()
                
                assert result is True


def test_full_login_flow_with_prompting():
    """Test complete login flow with user prompting."""
    with patch("weave.compat.wandb.wandb_thin.login._get_default_host", return_value="api.wandb.ai"):
        with patch("weave.compat.wandb.util.netrc.Netrc") as mock_netrc_class:
            mock_netrc = Mock()
            mock_netrc.get_credentials.return_value = None  # No existing credentials
            mock_netrc_class.return_value = mock_netrc
            
            valid_key = "b" * 40
            with patch("click.prompt", return_value=valid_key):
                with patch("weave.compat.wandb.wandb_thin.util.app_url", return_value="https://wandb.ai"):
                    result = _login()
                    
                    assert result is True
                    # Should save the key
                    mock_netrc.add_or_update_entry.assert_called_once_with("api.wandb.ai", "user", valid_key)


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
    from weave.wandb_interface.context import init, from_environment
    
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


def test_api_key_validation_integration():
    """Test API key validation in realistic scenarios."""
    from weave.compat.wandb.wandb_thin.login import _validate_api_key
    
    # Test valid keys
    _validate_api_key("a" * 40)  # Should not raise
    _validate_api_key("local-" + "b" * 40)  # On-prem style
    
    # Test invalid keys
    with pytest.raises(ValueError):
        _validate_api_key("short")
    
    with pytest.raises(ValueError):
        _validate_api_key("local-short")


def test_host_parsing_integration():
    """Test host parsing in realistic scenarios."""
    from weave.compat.wandb.wandb_thin.login import _parse_wandb_host
    
    # Test various host formats
    assert _parse_wandb_host("https://api.wandb.ai/") == "api.wandb.ai"
    assert _parse_wandb_host("http://localhost:8080/") == "localhost:8080"
    assert _parse_wandb_host("custom.wandb.server") == "custom.wandb.server"
    assert _parse_wandb_host("https://custom.server.com/path/") == "custom.server.com/path"


def test_settings_management_integration():
    """Test settings management integration."""
    from weave.compat.wandb.wandb_thin.login import _set_setting, _clear_setting, _get_host_from_settings
    import configparser
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.dict("os.environ", {"WANDB_CONFIG_DIR": temp_dir}):
            # Test setting a value
            _set_setting("base_url", "https://custom.wandb.ai")
            
            # Test reading it back
            host = _get_host_from_settings()
            assert host == "custom.wandb.ai"
            
            # Test clearing it
            _clear_setting("base_url")
            
            host_after = _get_host_from_settings()
            assert host_after is None