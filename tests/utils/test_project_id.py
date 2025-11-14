"""Tests for the project_id module."""

import pytest

from weave.utils.project_id import from_project_id, to_project_id


def test_to_project_id() -> None:
    """Test formatting entity and project as project_id."""
    project_id = to_project_id("my-entity", "my-project")
    assert project_id == "my-entity/my-project"


def test_from_project_id() -> None:
    """Test parsing project_id string into entity and project."""
    entity, project = from_project_id("my-entity/my-project")
    assert entity == "my-entity"
    assert project == "my-project"


def test_from_project_id_invalid_format() -> None:
    """Test from_project_id raises ValueError for invalid format."""
    with pytest.raises(ValueError, match="Invalid project_id format"):
        from_project_id("invalid")
