"""Tests for weave init authentication flow."""

from unittest.mock import Mock, patch

import pytest

from weave.trace.weave_init import (
    WeaveWandbAuthenticationException,
    get_entity_project_from_project_name,
    init_weave,
    init_weave_get_server,
)
from weave.wandb_interface.context import WandbApiContext


def test_get_entity_project_from_project_name_with_entity():
    """Test project name parsing when entity is included."""
    entity, project = get_entity_project_from_project_name("test_entity/test_project")

    assert entity == "test_entity"
    assert project == "test_project"


def test_get_entity_project_from_project_name_without_entity(mock_wandb_api):
    """Test project name parsing when entity is not included."""
    mock_wandb_api.default_entity_name.return_value = "default_entity"

    entity, project = get_entity_project_from_project_name("test_project")

    assert entity == "default_entity"
    assert project == "test_project"
    mock_wandb_api.default_entity_name.assert_called_once()


def test_get_entity_project_from_project_name_no_default_entity(mock_wandb_api):
    """Test project name parsing when no default entity is available."""
    mock_wandb_api.default_entity_name.return_value = None

    with pytest.raises(
        WeaveWandbAuthenticationException,
        match='weave init requires wandb. Run "wandb login"',
    ):
        get_entity_project_from_project_name("test_project")


def test_get_entity_project_from_project_name_too_many_slashes():
    """Test project name parsing with too many slashes."""
    with pytest.raises(ValueError, match="project_name must be of the form"):
        get_entity_project_from_project_name("entity/project/extra")


def test_get_entity_project_from_project_name_empty_entity():
    """Test project name parsing with empty entity."""
    with pytest.raises(ValueError, match="entity_name must be non-empty"):
        get_entity_project_from_project_name("/test_project")


def test_get_entity_project_from_project_name_empty_project():
    """Test project name parsing with empty project."""
    with pytest.raises(ValueError, match="project_name must be non-empty"):
        get_entity_project_from_project_name("test_entity/")


def test_get_entity_project_from_project_name_both_empty():
    """Test project name parsing with both empty."""
    with pytest.raises(ValueError, match="entity_name must be non-empty"):
        get_entity_project_from_project_name("/")


def test_init_weave_with_existing_context(
    mock_wandb_context,
    mock_wandb_api,
    mock_weave_init_components,
    mock_wandb_login,
):
    """Test init_weave when wandb context already exists."""
    # Configure existing context
    existing_context = WandbApiContext(
        user_id="test_user", api_key="test_api_key", headers=None, cookies=None
    )
    mock_wandb_context["get"].return_value = existing_context

    # Configure API to return test_entity
    mock_wandb_api.default_entity_name.return_value = "test_entity"

    # This should not call wandb.login since context exists
    result = init_weave("test_project")

    mock_wandb_login.assert_not_called()
    assert result.client == mock_weave_init_components["client"]


def test_init_weave_without_context_triggers_login(
    mock_wandb_context,
    mock_wandb_api,
    mock_weave_init_components,
    mock_wandb_login,
):
    """Test init_weave when no wandb context exists (should trigger login)."""
    # Configure no context initially, then context after login
    login_context = WandbApiContext(user_id="test_user", api_key="test_api_key")
    mock_wandb_context["get"].side_effect = [None, login_context]

    # Configure API to return test_entity
    mock_wandb_api.default_entity_name.return_value = "test_entity"

    with patch("weave.trace.weave_init.wandb_termlog_patch.ensure_patched"):
        result = init_weave("test_project")

        # Should call login with specific parameters
        mock_wandb_login.assert_called_once_with(anonymous="never", force=True)
        assert result.client == mock_weave_init_components["client"]


def test_init_weave_get_server():
    """Test init_weave_get_server function."""
    with patch(
        "weave.trace_server_bindings.remote_http_trace_server.RemoteHTTPTraceServer.from_env"
    ) as mock_from_env:
        mock_server = Mock()
        mock_from_env.return_value = mock_server

        # Test without API key
        result = init_weave_get_server()

        assert result == mock_server
        mock_server.set_auth.assert_not_called()

        # Test with API key
        result = init_weave_get_server("test_api_key")

        assert result == mock_server
        mock_server.set_auth.assert_called_once_with(("api", "test_api_key"))
