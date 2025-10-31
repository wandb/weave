"""Tests for weave init authentication flow."""

from dataclasses import dataclass

import pytest

from weave.trace import weave_init
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
    mock_default_entity: str | None
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
