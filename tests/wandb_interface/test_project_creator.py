"""Tests for wandb interface project creator."""

from unittest.mock import Mock, patch

import pytest

from weave.compat.wandb import AuthenticationError, CommError
from weave.wandb_interface.project_creator import (
    UnableToCreateProjectError,
    ensure_project_exists,
)


@pytest.fixture
def mock_api():
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture(autouse=True)
def fast_retry_settings():
    with (
        patch(
            "weave.wandb_interface.project_creator.retry_max_attempts", return_value=2
        ),
        patch(
            "weave.wandb_interface.project_creator.retry_max_interval", return_value=0
        ),
    ):
        yield


@pytest.fixture
def mock_api_with_existing_project(mock_api):
    mock_api.project.return_value = {"project": {"name": "existing_project"}}
    return mock_api


@pytest.fixture
def mock_api_with_no_project(mock_api):
    mock_api.project.return_value = None
    return mock_api


def test_ensure_project_exists_project_already_exists(mock_api_with_existing_project):
    """Test project creation when project already exists."""
    result = ensure_project_exists("test_entity", "test_project")

    assert result == {"project_name": "existing_project"}
    mock_api_with_existing_project.project.assert_called_once_with(
        "test_entity", "test_project"
    )
    mock_api_with_existing_project.upsert_project.assert_not_called()


def test_ensure_project_exists_project_not_found_create_success(
    mock_api_with_no_project,
):
    """Test project creation when project doesn't exist and creation succeeds."""
    # Mock upsert response - GraphQL structure
    upsert_response = {"upsertModel": {"model": {"name": "new_project"}}}
    # The fixture already made the existence check return "not found"; this is the
    # successful response from the follow-up create request.
    mock_api_with_no_project.upsert_project.return_value = upsert_response

    result = ensure_project_exists("test_entity", "test_project")

    assert result == {"project_name": "new_project"}
    mock_api_with_no_project.project.assert_called_once_with(
        "test_entity", "test_project"
    )
    mock_api_with_no_project.upsert_project.assert_called_once_with(
        entity="test_entity", project="test_project"
    )


def test_ensure_project_exists_retries_project_lookup_on_comm_error(mock_api):
    """Test project lookup retries on transient communication errors."""
    mock_api.project.side_effect = [
        CommError("Network error"),
        {"project": {"name": "existing_project"}},
    ]

    result = ensure_project_exists("test_entity", "test_project")

    assert result == {"project_name": "existing_project"}
    assert mock_api.project.call_count == 2
    mock_api.upsert_project.assert_not_called()


def test_ensure_project_exists_retries_project_create_on_comm_error(
    mock_api_with_no_project,
):
    """Test project creation retries on transient communication errors."""
    # This models a transient W&B error during project creation after the initial
    # existence check already determined the project does not exist.
    mock_api_with_no_project.upsert_project.side_effect = [
        CommError("Network error"),
        {"upsertModel": {"model": {"name": "new_project"}}},
    ]

    result = ensure_project_exists("test_entity", "test_project")

    assert result == {"project_name": "new_project"}
    # Only the create call is retried here: the existence lookup succeeded once,
    # then the first create attempt failed transiently and the second one succeeded.
    assert mock_api_with_no_project.project.call_count == 1
    assert mock_api_with_no_project.upsert_project.call_count == 2


def test_ensure_project_exists_project_not_found_create_fails(mock_api_with_no_project):
    """Test project creation when project doesn't exist and creation fails."""
    mock_api_with_no_project.upsert_project.return_value = None
    with pytest.raises(
        UnableToCreateProjectError,
        match="Failed to create project test_entity/test_project",
    ):
        ensure_project_exists("test_entity", "test_project")


@pytest.mark.disable_logging_error_check
def test_ensure_project_exists_authentication_error(mock_api_with_no_project):
    """Test project creation with authentication error."""
    # Upsert raises authentication error
    auth_error = AuthenticationError("Invalid API key")
    mock_api_with_no_project.upsert_project.side_effect = auth_error

    with pytest.raises(AuthenticationError, match="Invalid API key"):
        ensure_project_exists("test_entity", "test_project")

    mock_api_with_no_project.project.assert_called_once_with(
        "test_entity", "test_project"
    )
    mock_api_with_no_project.upsert_project.assert_called_once_with(
        entity="test_entity", project="test_project"
    )


@pytest.mark.disable_logging_error_check
def test_ensure_project_exists_comm_error(mock_api_with_no_project):
    """Test project creation with communication error."""
    # Upsert raises comm error
    comm_error = CommError("Network error")
    mock_api_with_no_project.upsert_project.side_effect = comm_error

    with pytest.raises(CommError, match="Network error"):
        ensure_project_exists("test_entity", "test_project")

    # The lookup still happens once, then project creation is attempted twice:
    # the initial call plus one retry before surfacing the final CommError.
    assert mock_api_with_no_project.project.call_count == 1
    assert mock_api_with_no_project.upsert_project.call_count == 2
