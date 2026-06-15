"""Tests for the project_id module."""

import re

import pytest

from weave.utils.project_id import from_project_id, to_project_id


@pytest.mark.parametrize(
    ("entity", "project"),
    [
        ("my-entity", "my-project"),
        (" my-entity ", " my-project "),
        ("my\tentity", "my\tproject"),
        ("my\nentity", "my\nproject"),
        ("mañana", "café"),
        ("東京", "项目"),
        ("team🚀", "proj✨"),
        ("entity!@#$%^&*()[]{}", "project~`+=_-.,:;?"),
    ],
    ids=[
        "basic",
        "leading-trailing-spaces",
        "tabs",
        "newlines",
        "accented-unicode",
        "multiscript-unicode",
        "emoji",
        "special-characters",
    ],
)
def test_to_project_id_format_and_round_trip(entity: str, project: str) -> None:
    """to_project_id joins on '/' preserving all supported chars, and round-trips through from_project_id."""
    project_id = to_project_id(entity, project)
    assert project_id == f"{entity}/{project}"
    assert from_project_id(project_id) == (entity, project)


def test_from_project_id() -> None:
    """from_project_id splits a project_id string into (entity, project)."""
    assert from_project_id("my-entity/my-project") == ("my-entity", "my-project")


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
    """to_project_id raises ValueError for empty or slash-containing inputs."""
    with pytest.raises(ValueError, match=re.escape(error_message)):
        to_project_id(entity, project)


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
    """from_project_id raises ValueError for malformed project_id strings."""
    with pytest.raises(ValueError, match=re.escape(error_message)):
        from_project_id(project_id)
