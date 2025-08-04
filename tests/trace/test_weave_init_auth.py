"""Tests for weave init authentication flow."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import Mock, patch

import pytest

from weave.trace.weave_init import (
    get_entity_project_from_project_name,
    init_weave,
    init_weave_get_server,
)
from weave.wandb_interface.context import WandbApiContext


@dataclass
class SuccessCase:
    """Test case for successful project name parsing."""

    project_name: str
    mock_default_entity: Optional[str]
    expected_entity: str
    expected_project: str

    def __str__(self) -> str:
        return f"{self.expected_entity}/{self.expected_project}"


@dataclass
class ExceptionCase:
    """Test case for project name parsing exceptions."""

    project_name: str
    expected_match: str

    def __str__(self) -> str:
        return self.project_name


@pytest.mark.parametrize(
    "case",
    [
        SuccessCase(
            project_name="test_entity/test_project",
            mock_default_entity=None,
            expected_entity="test_entity",
            expected_project="test_project",
        ),
        SuccessCase(
            project_name="test_project",
            mock_default_entity="default_entity",
            expected_entity="default_entity",
            expected_project="test_project",
        ),
    ],
    ids=str,
)
def test_get_entity_project_from_project_name_success(
    case: SuccessCase, mock_wandb_api
):
    """Test successful project name parsing scenarios."""
    # Configure mock if needed
    if case.mock_default_entity is not None:
        mock_wandb_api.default_entity_name.return_value = case.mock_default_entity

    entity, project = get_entity_project_from_project_name(case.project_name)
    assert entity == case.expected_entity
    assert project == case.expected_project

    # Verify mock was called only when expected
    if case.mock_default_entity is not None:
        mock_wandb_api.default_entity_name.assert_called_once()


@pytest.mark.parametrize(
    "case",
    [
        ExceptionCase(
            project_name="entity/project/extra",
            expected_match="project_name must be of the form",
        ),
        ExceptionCase(
            project_name="/test_project",
            expected_match="entity_name must be non-empty",
        ),
        ExceptionCase(
            project_name="test_entity/",
            expected_match="project_name must be non-empty",
        ),
        ExceptionCase(
            project_name="/",
            expected_match="entity_name must be non-empty",
        ),
    ],
    ids=str,
)
def test_get_entity_project_from_project_name_exceptions(case: ExceptionCase):
    """Test project name parsing exception scenarios."""
    with pytest.raises(ValueError, match=case.expected_match):
        get_entity_project_from_project_name(case.project_name)


def test_init_weave_with_existing_context(
    mock_wandb_context,
    mock_wandb_api,
    mock_weave_init_components,
    mock_wandb_login,
):
    """Test init_weave when wandb context already exists."""
    # Configure existing context
    existing_context = WandbApiContext(user_id="test_user", api_key="test_api_key")
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
