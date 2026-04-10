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
    from weave.trace.env import set_wandb_base_url
    from weave.wandb_interface.context import set_wandb_api_context

    weave_client_context.set_weave_client_global(None)
    set_wandb_api_context(None)
    set_wandb_base_url(None)
    yield
    weave_client_context.set_weave_client_global(None)
    set_wandb_api_context(None)
    set_wandb_base_url(None)


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


def test_init_weave_with_explicit_params_sets_context(mock_wandb_api):
    """When api_key and base_url are provided, they should be set in context so
    downstream code (e.g. entity resolution, trace server URL derivation) can
    use them without env vars.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    import weave.trace.env as env_module
    import weave.wandb_interface.context as context_module

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
        # Both should be set as module-level overrides for downstream use
        assert context_module._explicit_api_key == "explicit-key"
        assert env_module._explicit_base_url == "https://api.custom.example.com"
        weave_client_context.set_weave_client_global(None)


def test_init_weave_reuses_client_when_no_credential_params(mock_wandb_api):
    """When the same project is re-initialized without api_key/base_url/trace_server_url,
    the existing client should be returned (no re-init).
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client_a = weave_init.init_weave("test-project", api_key="key")
        client_b = weave_init.init_weave("test-project")
        # Same client should be reused (no credential params passed to second call)
        assert client_b is client_a
        client_a.finish()
        weave_client_context.set_weave_client_global(None)


def test_init_weave_reinits_when_credential_params_provided(mock_wandb_api):
    """Even if project name matches, passing api_key/base_url/trace_server_url
    should force a re-init (not reuse stale client).
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client_a = weave_init.init_weave("test-project", api_key="original-key")

        # Re-init with api_key should NOT reuse
        client_b = weave_init.init_weave("test-project", api_key="new-key")
        assert client_b is not client_a

        # Re-init with base_url should NOT reuse
        client_c = weave_init.init_weave("test-project", base_url="https://new.example.com")
        assert client_c is not client_b

        # Re-init with trace_server_url should NOT reuse
        client_d = weave_init.init_weave(
            "test-project", trace_server_url="https://trace.new.example.com"
        )
        assert client_d is not client_c

        client_d.finish()
        weave_client_context.set_weave_client_global(None)


def test_init_weave_uses_effective_trace_server_url_for_version_check(mock_wandb_api):
    """When trace_server_url is passed, it should be used for version checks
    instead of the env-derived URL.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message") as mock_init_msg,
    ):
        mock_init_msg.check_min_weave_version.return_value = True
        mock_init_msg.check_min_trace_server_version.return_value = True

        weave_init.init_weave(
            "test-project",
            api_key="key",
            trace_server_url="https://custom-trace.example.com",
        )

        # Version checks should use the explicit trace_server_url
        mock_init_msg.check_min_weave_version.assert_called_once_with(
            "0.0.0", "https://custom-trace.example.com"
        )
        mock_init_msg.check_min_trace_server_version.assert_called_once()
        # Third arg is the trace server URL
        call_args = mock_init_msg.check_min_trace_server_version.call_args
        assert call_args[0][2] == "https://custom-trace.example.com"

        weave_client_context.set_weave_client_global(None)


def test_init_weave_without_base_url_does_not_set_override(mock_wandb_api):
    """When base_url is not provided, _explicit_base_url should remain None."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    import weave.trace.env as env_module

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        weave_init.init_weave("test-project", api_key="key")
        assert env_module._explicit_base_url is None
        weave_client_context.set_weave_client_global(None)


def test_api_finish_flushes_before_clearing_overrides(mock_wandb_api):
    """api.finish() must flush the client before clearing explicit overrides,
    so that callbacks during flush still see the correct base_url.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    import weave.trace.env as env_module
    import weave.wandb_interface.context as context_module

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        weave_api.init(
            "test-project",
            api_key="explicit-key",
            base_url="https://api.custom.example.com",
        )

    # Track the order: flush should happen before clearing
    call_order = []
    original_client = weave_client_context.get_weave_client()
    original_finish = original_client.finish

    def tracked_finish(*args, **kwargs):
        # At flush time, overrides should still be set
        call_order.append("client_finish")
        assert env_module._explicit_base_url == "https://api.custom.example.com"
        assert context_module._explicit_api_key == "explicit-key"
        return original_finish(*args, **kwargs)

    original_client.finish = tracked_finish
    weave_api.finish()

    call_order.append("overrides_cleared")
    assert call_order == ["client_finish", "overrides_cleared"]
    assert env_module._explicit_base_url is None
    assert context_module._explicit_api_key is None


def test_get_wandb_api_context_falls_back_to_env(monkeypatch):
    """When no explicit api_key is set, get_wandb_api_context should fall back
    to environment variables.
    """
    from weave.wandb_interface.context import (
        get_wandb_api_context,
        set_wandb_api_context,
    )

    set_wandb_api_context(None)
    monkeypatch.setenv("WANDB_API_KEY", "env-key-123")
    assert get_wandb_api_context() == "env-key-123"


def test_get_wandb_api_context_explicit_overrides_env(monkeypatch):
    """When explicit api_key is set, it should override the env var."""
    from weave.wandb_interface.context import (
        get_wandb_api_context,
        set_wandb_api_context,
    )

    monkeypatch.setenv("WANDB_API_KEY", "env-key-123")
    set_wandb_api_context("explicit-key-456")
    assert get_wandb_api_context() == "explicit-key-456"
    set_wandb_api_context(None)


def test_wandb_base_url_explicit_overrides_env(monkeypatch):
    """When explicit base_url is set, it should override the env var."""
    from weave.trace.env import set_wandb_base_url, wandb_base_url

    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    set_wandb_base_url("https://explicit.example.com")
    assert wandb_base_url() == "https://explicit.example.com"
    set_wandb_base_url(None)


def test_wandb_base_url_falls_back_to_env(monkeypatch):
    """When no explicit base_url is set, should fall back to env var."""
    from weave.trace.env import set_wandb_base_url, wandb_base_url

    set_wandb_base_url(None)
    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    assert wandb_base_url() == "https://env.example.com"


def test_wandb_base_url_strips_trailing_slash():
    """Explicit base_url should have trailing slash stripped."""
    from weave.trace.env import set_wandb_base_url, wandb_base_url

    set_wandb_base_url("https://explicit.example.com/")
    assert wandb_base_url() == "https://explicit.example.com"
    set_wandb_base_url(None)


def test_finish_clears_explicit_globals(mock_wandb_api):
    """weave.finish() must clear explicit api_key and base_url globals so a
    subsequent init without params falls back to env vars.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    import weave.trace.env as env_module
    import weave.wandb_interface.context as context_module

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
        assert context_module._explicit_api_key == "explicit-key"
        assert env_module._explicit_base_url == "https://api.custom.example.com"

    # finish() should clear the globals
    weave_init.finish()
    assert context_module._explicit_api_key is None
    assert env_module._explicit_base_url is None
