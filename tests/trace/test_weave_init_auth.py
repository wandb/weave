"""Tests for weave init authentication flow."""

from unittest.mock import Mock, patch

import pytest

from weave.trace.weave_init import (
    WeaveWandbAuthenticationException,
    get_entity_project_from_project_name,
)

# Local fixtures for this test module


@pytest.fixture
def mock_wandb_api_with_default_entity():
    """Fixture that provides a mocked wandb Api instance with default entity."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api.default_entity_name.return_value = "default_entity"
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_wandb_api_no_entity():
    """Fixture that provides a mocked wandb Api instance with no default entity."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api = Mock()
        mock_api.default_entity_name.return_value = None
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_weave_login():
    """Fixture that provides a mocked weave login function."""
    with patch("weave.compat.wandb.login") as mock_login:
        yield mock_login


@pytest.fixture
def mock_weave_context_with_existing():
    """Fixture that provides mocked weave context with existing context."""
    from weave.wandb_interface.context import WandbApiContext

    existing_context = WandbApiContext(
        user_id="test_user", api_key="test_api_key", headers=None, cookies=None
    )

    with (
        patch("weave.wandb_interface.context.init") as mock_context_init,
        patch(
            "weave.wandb_interface.context.get_wandb_api_context",
            return_value=existing_context,
        ) as mock_get_context,
    ):
        yield {
            "init": mock_context_init,
            "get": mock_get_context,
            "existing_context": existing_context,
        }


@pytest.fixture
def mock_weave_context_without_existing():
    """Fixture that provides mocked weave context with no existing context initially."""
    from weave.wandb_interface.context import WandbApiContext

    login_context = WandbApiContext(
        user_id="test_user", api_key="test_api_key", headers=None, cookies=None
    )

    with (
        patch("weave.wandb_interface.context.init") as mock_context_init,
        patch(
            "weave.wandb_interface.context.get_wandb_api_context",
            side_effect=[None, login_context],
        ) as mock_get_context,
    ):
        yield {
            "init": mock_context_init,
            "get": mock_get_context,
            "login_context": login_context,
        }


def test_get_entity_project_from_project_name_with_entity():
    """Test project name parsing when entity is included."""
    entity, project = get_entity_project_from_project_name("test_entity/test_project")

    assert entity == "test_entity"
    assert project == "test_project"


def test_get_entity_project_from_project_name_without_entity(
    mock_wandb_api_with_default_entity,
):
    """Test project name parsing when entity is not included."""
    entity, project = get_entity_project_from_project_name("test_project")

    assert entity == "default_entity"
    assert project == "test_project"
    mock_wandb_api_with_default_entity.default_entity_name.assert_called_once()


def test_get_entity_project_from_project_name_no_default_entity(
    mock_wandb_api_no_entity,
):
    """Test project name parsing when no default entity is available."""
    with pytest.raises(
        WeaveWandbAuthenticationException,
        match='weave init requires wandb. Run "wandb login"',
    ):
        get_entity_project_from_project_name("test_project")


def test_get_entity_project_from_project_name_too_many_slashes():
    """Test project name parsing with too many slashes."""
    with pytest.raises(ValueError, match="project_name must be of the form"):
        get_entity_project_from_project_name("entity/project/extra")


def test_get_entity_project_from_project_name_empty_entity():
    """Test project name parsing with empty entity."""
    with pytest.raises(ValueError, match="entity_name must be non-empty"):
        get_entity_project_from_project_name("/test_project")


def test_get_entity_project_from_project_name_empty_project():
    """Test project name parsing with empty project."""
    with pytest.raises(ValueError, match="project_name must be non-empty"):
        get_entity_project_from_project_name("test_entity/")


def test_get_entity_project_from_project_name_both_empty():
    """Test project name parsing with both empty."""
    with pytest.raises(ValueError, match="entity_name must be non-empty"):
        get_entity_project_from_project_name("/")


def test_init_weave_with_existing_context(
    mock_weave_context_with_existing,
    mock_wandb_api_with_default_entity,
    mock_weave_init_components,
    mock_weave_login,
):
    """Test init_weave when wandb context already exists."""
    from weave.trace.weave_init import init_weave

    # Update the mock API to return test_entity
    mock_wandb_api_with_default_entity.default_entity_name.return_value = "test_entity"

    # This should not call wandb.login since context exists
    result = init_weave("test_project")

    mock_weave_login.assert_not_called()
    assert result.client == mock_weave_init_components["client"]


def test_init_weave_without_context_triggers_login(
    mock_weave_context_without_existing,
    mock_wandb_api_with_default_entity,
    mock_weave_init_components,
    mock_weave_login,
):
    """Test init_weave when no wandb context exists (should trigger login)."""
    from weave.trace.weave_init import init_weave

    # Update the mock API to return test_entity
    mock_wandb_api_with_default_entity.default_entity_name.return_value = "test_entity"

    with patch("weave.trace.weave_init.wandb_termlog_patch.ensure_patched"):
        result = init_weave("test_project")

        # Should call login with specific parameters
        mock_weave_login.assert_called_once_with(anonymous="never", force=True)
        assert result.client == mock_weave_init_components["client"]


def test_init_weave_authentication_order():
    """Test that authentication happens before entity resolution."""
    from weave.trace.weave_init import init_weave
    from weave.wandb_interface.context import WandbApiContext

    # This tests our fix - entity resolution should happen AFTER authentication
    login_context = WandbApiContext(
        user_id="test_user", api_key="test_api_key", headers=None, cookies=None
    )

    call_order = []

    def mock_get_context(*args, **kwargs):
        call_order.append("get_context")
        return None  # No context initially

    def mock_get_context_after_login(*args, **kwargs):
        call_order.append("get_context_after_login")
        return login_context

    def mock_login(*args, **kwargs):
        call_order.append("login")

    def mock_get_entity_project(*args, **kwargs):
        call_order.append("get_entity_project")
        return "test_entity", "test_project"

    with patch("weave.wandb_interface.context.init"):
        # Mock the sequence: no context -> login -> context available
        with patch(
            "weave.wandb_interface.context.get_wandb_api_context",
            side_effect=[mock_get_context(), mock_get_context_after_login()],
        ):
            with patch("weave.compat.wandb.login", side_effect=mock_login):
                with patch(
                    "weave.trace.weave_init.get_entity_project_from_project_name",
                    side_effect=mock_get_entity_project,
                ):
                    with patch("weave.trace.weave_init.init_weave_get_server"):
                        with patch("weave.trace.weave_client.WeaveClient"):
                            with patch(
                                "weave.trace.weave_init.use_server_cache",
                                return_value=False,
                            ):
                                with patch(
                                    "weave.trace.weave_init.wandb_termlog_patch.ensure_patched"
                                ):
                                    try:
                                        init_weave("test_project")
                                    except:
                                        pass  # We just care about call order

    # Verify that login happens before entity resolution
    assert "login" in call_order
    assert "get_entity_project" in call_order
    login_index = call_order.index("login")
    entity_index = call_order.index("get_entity_project")
    assert login_index < entity_index, (
        f"Login should happen before entity resolution. Call order: {call_order}"
    )


def test_init_weave_with_server_cache():
    """Test init_weave with server caching enabled."""
    from weave.trace.weave_init import init_weave
    from weave.wandb_interface.context import WandbApiContext

    existing_context = WandbApiContext(
        user_id="test_user", api_key="test_api_key", headers=None, cookies=None
    )

    with patch("weave.wandb_interface.context.init"):
        with patch(
            "weave.wandb_interface.context.get_wandb_api_context",
            return_value=existing_context,
        ):
            with patch("weave.compat.wandb.Api") as mock_api_class:
                mock_api = Mock()
                mock_api.default_entity_name.return_value = "test_entity"
                mock_api_class.return_value = mock_api

                with patch(
                    "weave.trace.weave_init.init_weave_get_server"
                ) as mock_get_server:
                    mock_server = Mock()
                    mock_server.server_info.return_value.min_required_weave_python_version = "0.0.0"
                    mock_get_server.return_value = mock_server

                    with patch(
                        "weave.trace_server_bindings.caching_middleware_trace_server.CachingMiddlewareTraceServer.from_env"
                    ) as mock_cache:
                        mock_cached_server = Mock()
                        mock_cache.return_value = mock_cached_server

                        with patch(
                            "weave.trace.weave_client.WeaveClient"
                        ) as mock_client_class:
                            mock_client = Mock()
                            mock_client.project = "test_project"
                            mock_client_class.return_value = mock_client

                            with patch(
                                "weave.trace.weave_init.use_server_cache",
                                return_value=True,
                            ):
                                result = init_weave("test_project")

                                # Should use cached server
                                mock_cache.assert_called_once_with(mock_server)
                                # Client should be initialized with cached server
                                mock_client_class.assert_called_once()
                                call_args = mock_client_class.call_args[0]
                                assert (
                                    call_args[2] == mock_cached_server
                                )  # server parameter


def test_init_weave_get_server():
    """Test init_weave_get_server function."""
    from weave.trace.weave_init import init_weave_get_server

    with patch(
        "weave.trace_server_bindings.remote_http_trace_server.RemoteHTTPTraceServer.from_env"
    ) as mock_from_env:
        mock_server = Mock()
        mock_from_env.return_value = mock_server

        # Test without API key
        result = init_weave_get_server()

        assert result == mock_server
        mock_server.set_auth.assert_not_called()

        # Test with API key
        result = init_weave_get_server("test_api_key")

        assert result == mock_server
        mock_server.set_auth.assert_called_once_with(("api", "test_api_key"))


def test_init_weave_disabled():
    """Test init_weave_disabled function."""
    from weave.trace.weave_init import init_weave_disabled

    with patch(
        "weave.trace_server.sqlite_trace_server.SqliteTraceServer"
    ) as mock_server_class:
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        with patch("weave.trace.weave_client.WeaveClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            result = init_weave_disabled()

            # Should create disabled client
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args

            # Check that ensure_project_exists is False
            assert call_args[1]["ensure_project_exists"] is False

            assert result.client == mock_client
