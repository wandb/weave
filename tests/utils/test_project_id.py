"""Tests for the project_id module."""

import pytest

from weave.utils.project_id import ProjectID


def test_project_id_creation() -> None:
    """Test creating a ProjectID with entity and project."""
    project_id = ProjectID(entity="my-entity", project="my-project")
    assert project_id.entity == "my-entity"
    assert project_id.project == "my-project"
    assert project_id.name == "my-entity/my-project"


def test_project_id_name_property() -> None:
    """Test the name property returns correct format."""
    project_id = ProjectID(entity="test-entity", project="test-project")
    assert project_id.name == "test-entity/test-project"


def test_project_id_from_string() -> None:
    """Test creating ProjectID from string format."""
    project_id = ProjectID.from_string("my-entity/my-project")
    assert project_id.entity == "my-entity"
    assert project_id.project == "my-project"
    assert project_id.name == "my-entity/my-project"


def test_project_id_from_string_invalid_format() -> None:
    """Test from_string raises ValueError for invalid format."""
    with pytest.raises(ValueError, match="Invalid project_id format"):
        ProjectID.from_string("invalid")


def test_project_id_empty_entity() -> None:
    """Test that empty entity raises ValueError."""
    with pytest.raises(ValueError, match="entity must be non-empty"):
        ProjectID(entity="", project="my-project")


def test_project_id_empty_project() -> None:
    """Test that empty project raises ValueError."""
    with pytest.raises(ValueError, match="project must be non-empty"):
        ProjectID(entity="my-entity", project="")


def test_project_id_entity_with_slash() -> None:
    """Test that entity with slash raises ValueError."""
    with pytest.raises(ValueError, match="entity cannot contain"):
        ProjectID(entity="my/entity", project="my-project")


def test_project_id_project_with_slash() -> None:
    """Test that project with slash raises ValueError."""
    with pytest.raises(ValueError, match="project cannot contain"):
        ProjectID(entity="my-entity", project="my/project")
