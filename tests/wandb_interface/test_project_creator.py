"""Tests for wandb interface project creator."""

from unittest.mock import Mock, patch

import pytest

from weave.wandb_interface.project_creator import (
    UnableToCreateProjectError,
    _ensure_project_exists,
    _format_project_result,
    ensure_project_exists,
    wandb_logging_disabled,
)


def test_format_project_result():
    """Test formatting project result from API response."""
    project = {"name": "test_project"}
    result = _format_project_result(project)

    assert result == {"project_name": "test_project"}


def test_format_project_result_missing_name():
    """Test formatting project result when name is missing."""
    project = {"id": "123"}

    with pytest.raises(KeyError):
        _format_project_result(project)


def test_wandb_logging_disabled_context_manager():
    """Test wandb logging disabled context manager."""
    with patch("weave.compat.wandb.termerror") as mock_termerror:
        original_termerror = mock_termerror

        with wandb_logging_disabled():
            # Inside context, termerror should be disabled
            from weave.compat import wandb

            wandb.termerror("test", "message")  # Should be no-op

        # After context, original function should be restored
        assert wandb.termerror == original_termerror


def test_ensure_project_exists_wrapper():
    """Test the public ensure_project_exists function (wrapper)."""
    with patch(
        "weave.wandb_interface.project_creator._ensure_project_exists"
    ) as mock_ensure:
        mock_ensure.return_value = {"project_name": "test_project"}

        result = ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "test_project"}
        mock_ensure.assert_called_once_with("test_entity", "test_project")


def test_ensure_project_exists_project_already_exists():
    """Test project creation when project already exists."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock project query response - GraphQL structure
        project_response = {"project": {"name": "existing_project"}}
        mock_api.project.return_value = project_response

        result = _ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "existing_project"}
        mock_api.project.assert_called_once_with("test_entity", "test_project")
        mock_api.upsert_project.assert_not_called()


def test_ensure_project_exists_project_not_found_create_success():
    """Test project creation when project doesn't exist and creation succeeds."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Mock upsert response - GraphQL structure
        upsert_response = {"upsertModel": {"model": {"name": "new_project"}}}
        mock_api.upsert_project.return_value = upsert_response

        result = _ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "new_project"}
        mock_api.project.assert_called_once_with("test_entity", "test_project")
        mock_api.upsert_project.assert_called_once_with(
            entity="test_entity", project="test_project"
        )


def test_ensure_project_exists_project_not_found_create_fails():
    """Test project creation when project doesn't exist and creation fails."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Upsert fails
        mock_api.upsert_project.return_value = None

        with pytest.raises(
            UnableToCreateProjectError,
            match="Failed to create project test_entity/test_project",
        ):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_project_not_found_create_exception():
    """Test project creation when project doesn't exist and creation raises exception."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Upsert raises exception
        test_exception = Exception("API Error")
        mock_api.upsert_project.side_effect = test_exception

        with pytest.raises(Exception, match="API Error"):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_authentication_error():
    """Test project creation with authentication error."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Import the actual exception classes
        from weave.compat.wandb import AuthenticationError

        # Upsert raises authentication error
        auth_error = AuthenticationError("Invalid API key")
        mock_api.upsert_project.side_effect = auth_error

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_comm_error():
    """Test project creation with communication error."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Import the actual exception classes
        from weave.compat.wandb import CommError

        # Upsert raises comm error
        comm_error = CommError("Network error")
        mock_api.upsert_project.side_effect = comm_error

        with pytest.raises(CommError, match="Network error"):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_malformed_project_response():
    """Test project creation with malformed project response."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Malformed project response (missing "project" key)
        project_response = {"data": "something"}
        mock_api.project.return_value = project_response

        # Should fall through to creation
        upsert_response = {"upsertModel": {"model": {"name": "new_project"}}}
        mock_api.upsert_project.return_value = upsert_response

        result = _ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "new_project"}
        mock_api.upsert_project.assert_called_once()


def test_ensure_project_exists_malformed_upsert_response():
    """Test project creation with malformed upsert response."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Malformed upsert response (missing nested structure)
        upsert_response = {"data": "something"}
        mock_api.upsert_project.return_value = upsert_response

        with pytest.raises(UnableToCreateProjectError):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_project_response_empty_project():
    """Test project creation when project response has null project."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project response with null project
        project_response = {"project": None}
        mock_api.project.return_value = project_response

        # Should fall through to creation
        upsert_response = {"upsertModel": {"model": {"name": "new_project"}}}
        mock_api.upsert_project.return_value = upsert_response

        result = _ensure_project_exists("test_entity", "test_project")

        assert result == {"project_name": "new_project"}
        mock_api.upsert_project.assert_called_once()


def test_ensure_project_exists_upsert_response_null_model():
    """Test project creation when upsert response has null model."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Upsert response with null model
        upsert_response = {"upsertModel": {"model": None}}
        mock_api.upsert_project.return_value = upsert_response

        with pytest.raises(UnableToCreateProjectError):
            _ensure_project_exists("test_entity", "test_project")


def test_ensure_project_exists_upsert_response_no_upsert_model():
    """Test project creation when upsert response has no upsertModel."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Project doesn't exist
        mock_api.project.return_value = None

        # Upsert response with no upsertModel
        upsert_response = {"something": "else"}
        mock_api.upsert_project.return_value = upsert_response

        with pytest.raises(UnableToCreateProjectError):
            _ensure_project_exists("test_entity", "test_project")
