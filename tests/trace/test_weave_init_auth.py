"""Tests for weave init authentication flow."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from weave.trace import api as weave_api
from weave.trace import weave_init
from weave.trace.context import weave_client_context
from weave.trace.weave_init import (
    get_entity_project_from_project_name,
)


@pytest.fixture(autouse=True)
def reset_weave_client():
    """Reset the global weave client state before each test."""
    weave_init._current_inited_client = None
    weave_client_context.set_weave_client_global(None)
    yield
    weave_client_context.set_weave_client_global(None)
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


# --- Tests for api_key and base_url parameters ---


def test_init_weave_get_server_uses_trace_server_url_param():
    """When trace_server_url is passed, it should be used instead of env-derived URL."""
    server = weave_init.init_weave_get_server(
        api_key="test-key", trace_server_url="https://custom.example.com"
    )
    assert server.trace_server_url == "https://custom.example.com"
    assert server._auth == ("api", "test-key")


def test_init_weave_get_server_falls_back_to_env_without_trace_server_url():
    """When trace_server_url is None, should use env-derived URL (existing behavior)."""
    server = weave_init.init_weave_get_server(api_key="test-key")
    assert server.trace_server_url is not None
    assert server._auth == ("api", "test-key")


def _make_mock_server():
    from weave.trace_server_bindings.remote_http_trace_server import (
        RemoteHTTPTraceServer,
    )

    mock = MagicMock(spec=RemoteHTTPTraceServer)
    mock.server_info.return_value = MagicMock(
        min_required_weave_python_version="0.0.0",
        trace_server_version=None,
    )
    mock.ensure_project_exists.return_value = MagicMock(project_name="test-project")
    # WeaveClient checks hasattr for these; return None so no batch processors are set
    mock.get_call_processor.return_value = None
    mock.get_feedback_processor.return_value = None
    return mock


def test_init_weave_with_api_key_skips_env_auth(mock_wandb_api):
    """When api_key is provided, should not read from env or prompt for login."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server
        ) as mock_get_server,
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
        patch("weave.wandb_interface.context.weave_wandb_api_key") as mock_env_key,
    ):
        client = weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://api.custom.example.com",
            trace_server_url="https://trace.custom.example.com",
        )
        # env-based key lookup should NOT be called
        mock_env_key.assert_not_called()
        # Server should be created with the explicit trace_server_url
        mock_get_server.assert_called_once_with(
            "explicit-key", trace_server_url="https://trace.custom.example.com"
        )
        assert client is not None
        client.finish()
        weave_client_context.set_weave_client_global(None)


def test_weave_init_passes_all_params(mock_wandb_api):
    """weave.init() should forward api_key, base_url, and trace_server_url."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client = weave_api.init(
            "test-project",
            api_key="my-key",
            base_url="https://api.custom.example.com",
            trace_server_url="https://trace.custom.example.com",
        )
        assert client is not None
        client.finish()
        weave_client_context.set_weave_client_global(None)


def test_sequential_init_with_different_credentials(mock_wandb_api):
    """Multiple weave.init() calls with different api_key/base_url should each
    configure the client correctly, not reuse a stale client.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"

    with (
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        # First init with credentials A
        server_a = _make_mock_server()
        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=server_a
        ):
            client_a = weave_api.init(
                "test-project",
                api_key="key-a",
                base_url="https://api-a.example.com",
            )

        # Second init with credentials B (same project name)
        server_b = _make_mock_server()
        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=server_b
        ):
            client_b = weave_api.init(
                "test-project",
                api_key="key-b",
                base_url="https://api-b.example.com",
            )

        # Should NOT have reused client_a
        assert client_b is not client_a

        client_b.finish()
        weave_client_context.set_weave_client_global(None)


def test_init_weave_with_explicit_params_sets_context(mock_wandb_api):
    """When api_key and base_url are provided, they should be set in context so
    downstream code (e.g. entity resolution, trace server URL derivation) can
    use them without env vars.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    from weave.trace.env import _explicit_base_url
    from weave.wandb_interface.context import _explicit_api_key

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://api.custom.example.com",
        )
        # Both should be set in context for downstream use
        assert _explicit_api_key.get() == "explicit-key"
        assert _explicit_base_url.get() == "https://api.custom.example.com"
        weave_client_context.set_weave_client_global(None)
