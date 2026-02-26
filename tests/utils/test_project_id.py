"""Tests for the project_id module."""

import re

import pytest

from weave.utils.project_id import from_project_id, to_project_id


def test_to_project_id() -> None:
    """Test formatting entity and project as project_id."""
    assert to_project_id("my-entity", "my-project") == "my-entity/my-project"


@pytest.mark.parametrize(
    ("entity", "project"),
    [
        (" my-entity ", " my-project "),
        ("my\tentity", "my\tproject"),
        ("my\nentity", "my\nproject"),
        ("mañana", "café"),
        ("東京", "项目"),
        ("team🚀", "proj✨"),
        ("entity!@#$%^&*()[]{}", "project~`+=_-.,:;?"),
    ],
    ids=[
        "leading-trailing-spaces",
        "tabs",
        "newlines",
        "accented-unicode",
        "multiscript-unicode",
        "emoji",
        "special-characters",
    ],
)
def test_to_project_id_preserves_whitespace_unicode_and_special_characters(
    entity: str, project: str
) -> None:
    """Test to_project_id preserves supported characters exactly."""
    assert to_project_id(entity, project) == f"{entity}/{project}"


@pytest.mark.parametrize(
    ("entity", "project", "error_message"),
    [
        ("", "my-project", "entity must be non-empty"),
        ("my-entity", "", "project must be non-empty"),
        ("my/entity", "my-project", "entity cannot contain '/'"),
        ("my-entity", "my/project", "project cannot contain '/'"),
    ],
    ids=[
        "empty-entity",
        "empty-project",
        "entity-contains-slash",
        "project-contains-slash",
    ],
)
def test_to_project_id_invalid_inputs(
    entity: str, project: str, error_message: str
) -> None:
    """Test to_project_id raises ValueError for invalid inputs."""
    with pytest.raises(ValueError, match=re.escape(error_message)):
        to_project_id(entity, project)


def test_from_project_id() -> None:
    """Test parsing project_id string into entity and project."""
    assert from_project_id("my-entity/my-project") == ("my-entity", "my-project")


@pytest.mark.parametrize(
    ("project_id", "error_message"),
    [
        ("invalid", "Invalid project_id format: invalid. Expected 'entity/project'"),
        ("/my-project", "entity must be non-empty"),
        ("my-entity/", "project must be non-empty"),
        ("my-entity/my/project", "project cannot contain '/'"),
    ],
    ids=[
        "missing-slash-separator",
        "empty-entity-segment",
        "empty-project-segment",
        "extra-slash-in-project",
    ],
)
def test_from_project_id_invalid_inputs(project_id: str, error_message: str) -> None:
    """Test from_project_id raises ValueError for invalid inputs."""
    with pytest.raises(ValueError, match=re.escape(error_message)):
        from_project_id(project_id)


def test_project_id_round_trip() -> None:
    """Test project IDs can be round-tripped through parser and formatter."""
    entity = "my-entity"
    project = "my-project"
    assert from_project_id(to_project_id(entity, project)) == (entity, project)


@pytest.mark.parametrize(
    ("entity", "project"),
    [
        (" my-entity ", " my-project "),
        ("my\tentity", "my\tproject"),
        ("my\nentity", "my\nproject"),
        ("mañana", "café"),
        ("東京", "项目"),
        ("team🚀", "proj✨"),
        ("entity!@#$%^&*()[]{}", "project~`+=_-.,:;?"),
    ],
    ids=[
        "round-trip-leading-trailing-spaces",
        "round-trip-tabs",
        "round-trip-newlines",
        "round-trip-accented-unicode",
        "round-trip-multiscript-unicode",
        "round-trip-emoji",
        "round-trip-special-characters",
    ],
)
def test_project_id_round_trip_with_whitespace_unicode_and_special_characters(
    entity: str, project: str
) -> None:
    """Test round-trip parsing/formatting with non-standard valid strings."""
    assert from_project_id(to_project_id(entity, project)) == (entity, project)
