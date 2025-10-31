"""Tests for weave init authentication flow."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from weave.trace import weave_init
from weave.trace.api import init
from weave.trace.weave_init import (
    get_entity_project_from_project_name,
)


@pytest.fixture(autouse=True)
def reset_weave_client():
    """Reset the global weave client state before each test."""
    weave_init._current_inited_client = None
    yield
    weave_init._current_inited_client = None


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


def test_get_entity_project_from_project_name_with_wandb_entity_env(
    mock_wandb_api, monkeypatch
):
    """Test that WANDB_ENTITY environment variable is respected."""
    # Set WANDB_ENTITY environment variable
    monkeypatch.setenv("WANDB_ENTITY", "env_entity")

    # Test that env var is used when project has no entity
    entity, project = get_entity_project_from_project_name("test_project")
    assert entity == "env_entity"
    assert project == "test_project"

    # Verify wandb API was not called since we used env var
    mock_wandb_api.default_entity_name.assert_not_called()

    # Test that explicit entity in project name overrides env var
    entity, project = get_entity_project_from_project_name(
        "explicit_entity/test_project"
    )
    assert entity == "explicit_entity"
    assert project == "test_project"


@pytest.mark.parametrize(
    "case",
    [
        ExceptionCase(
            project_name="",
            expected_match="project_name must be non-empty",
        ),
        ExceptionCase(
            project_name="   ",
            expected_match="project_name must be non-empty",
        ),
        ExceptionCase(
            project_name="\t\n",
            expected_match="project_name must be non-empty",
        ),
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


def test_init_with_entity_and_project_parameters(mock_wandb_api):
    """Test that weave.init() accepts entity and project parameters."""
    with (
        patch("weave.trace.weave_init.init_weave_get_server") as mock_get_server,
        patch(
            "weave.wandb_interface.context.get_wandb_api_context"
        ) as mock_get_context,
        patch("weave.trace.weave_init.get_username") as mock_get_username,
        patch("weave.trace.init_message.print_init_message") as mock_print_message,
    ):
        mock_get_context.return_value = MagicMock(api_key="test_key")
        mock_server = MagicMock(spec=["server_info", "ensure_project_exists"])
        mock_server.server_info.return_value.min_required_weave_python_version = "0.0.0"
        # Mock ensure_project_exists to return an object with project_name attribute
        ensure_project_resp = MagicMock()
        ensure_project_resp.project_name = "test_project"
        mock_server.ensure_project_exists.return_value = ensure_project_resp
        mock_get_server.return_value = mock_server
        mock_get_username.return_value = "test_user"
        mock_wandb_api.default_entity_name.return_value = "default_entity"

        # Test the new entity/project parameter style
        client = init(entity="test_entity", project="test_project")

        assert client is not None
        assert client.entity == "test_entity"
        assert client.project == "test_project"

        # Cleanup
        try:
            client.finish()
        except Exception:
            pass


def test_init_with_project_name_backward_compatible(mock_wandb_api):
    """Test that weave.init() still works with project_name parameter (backward compatible)."""
    with (
        patch("weave.trace.weave_init.init_weave_get_server") as mock_get_server,
        patch(
            "weave.wandb_interface.context.get_wandb_api_context"
        ) as mock_get_context,
        patch("weave.trace.weave_init.get_username") as mock_get_username,
        patch("weave.trace.init_message.print_init_message") as mock_print_message,
    ):
        mock_get_context.return_value = MagicMock(api_key="test_key")
        mock_server = MagicMock(spec=["server_info", "ensure_project_exists"])
        mock_server.server_info.return_value.min_required_weave_python_version = "0.0.0"
        # Mock ensure_project_exists to return an object with project_name attribute
        ensure_project_resp = MagicMock()
        ensure_project_resp.project_name = "test_project"
        mock_server.ensure_project_exists.return_value = ensure_project_resp
        mock_get_server.return_value = mock_server
        mock_get_username.return_value = "test_user"
        mock_wandb_api.default_entity_name.return_value = "default_entity"

        # Test backward compatibility with project_name
        client = init("test_entity/test_project")

        assert client is not None
        assert client.entity == "test_entity"
        assert client.project == "test_project"

        # Cleanup
        try:
            client.finish()
        except Exception:
            pass


def test_init_with_both_project_name_and_entity_project_raises_error():
    """Test that providing both project_name and entity/project raises an error."""
    with pytest.raises(
        ValueError,
        match="Cannot specify both 'project_name' and 'entity'/'project' parameters",
    ):
        init("test_entity/test_project", entity="test_entity", project="test_project")


def test_init_with_only_entity_raises_error():
    """Test that providing only entity without project raises an error."""
    with pytest.raises(
        ValueError, match="Both 'entity' and 'project' must be provided"
    ):
        init(entity="test_entity")


def test_init_with_only_project_raises_error():
    """Test that providing only project without entity raises an error."""
    with pytest.raises(
        ValueError, match="Both 'entity' and 'project' must be provided"
    ):
        init(project="test_project")


def test_init_with_no_parameters_raises_error():
    """Test that providing neither project_name nor entity/project raises an error."""
    with pytest.raises(
        ValueError,
        match="Must provide either 'project_name' or both 'entity' and 'project' parameters",
    ):
        init()


def test_init_with_empty_entity_or_project_raises_error():
    """Test that providing empty entity or project raises an error."""
    with pytest.raises(
        ValueError, match="entity and project must be non-empty strings"
    ):
        init(entity="", project="test_project")

    with pytest.raises(
        ValueError, match="entity and project must be non-empty strings"
    ):
        init(entity="test_entity", project="")
