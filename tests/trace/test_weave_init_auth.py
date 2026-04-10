"""Tests for weave init authentication flow."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from weave.trace import weave_init
from weave.trace.context import weave_client_context
from weave.trace.weave_init import (
    get_entity_project_from_project_name,
)


@pytest.fixture(autouse=True)
def reset_weave_client():
    """Reset the global weave client state before each test."""
    weave_client_context.set_weave_client_global(None)
    yield
    weave_client_context.set_weave_client_global(None)


@pytest.fixture(autouse=True)
def mock_project_creator():
    """Mock project_creator.ensure_project_exists for all tests that create clients."""
    with patch(
        "weave.trace.weave_client._ensure_project",
        return_value={"project_name": "test-project"},
    ):
        yield


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


def test_base_url_derives_trace_server_url(mock_wandb_api):
    """When base_url is provided but trace_server_url is not, the trace server
    URL should be derived from base_url (matching the documented contract).
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = MagicMock()
    mock_server.server_info.return_value = MagicMock(
        min_required_weave_python_version="0.0.0",
        trace_server_version=None,
    )
    mock_server.get_call_processor.return_value = None
    mock_server.get_feedback_processor.return_value = None

    with (
        patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server
        ) as mock_get_server,
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        # Non-default base_url → should derive trace_server_url as base_url + "/traces"
        weave_init.init_weave(
            "test-project",
            api_key="key",
            base_url="https://custom.example.com",
        )
        mock_get_server.assert_called_with(
            "key", trace_server_url="https://custom.example.com/traces"
        )
        weave_client_context.set_weave_client_global(None)

    with (
        patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server
        ) as mock_get_server,
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        # Default base_url → should derive MTSAAS trace URL
        weave_init.init_weave(
            "test-project",
            api_key="key",
            base_url="https://api.wandb.ai",
        )
        mock_get_server.assert_called_with(
            "key", trace_server_url="https://trace.wandb.ai"
        )
        weave_client_context.set_weave_client_global(None)

    with (
        patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server
        ) as mock_get_server,
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        # Explicit trace_server_url should NOT be overridden by base_url derivation
        weave_init.init_weave(
            "test-project",
            api_key="key",
            base_url="https://custom.example.com",
            trace_server_url="https://explicit-trace.example.com",
        )
        mock_get_server.assert_called_with(
            "key", trace_server_url="https://explicit-trace.example.com"
        )
        weave_client_context.set_weave_client_global(None)


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


def test_init_weave_stores_creds_on_client(mock_wandb_api):
    """When api_key and base_url are provided, they should be stored on the
    client instance (not in module-level globals).
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client = weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://api.custom.example.com",
        )
        assert client._api_key == "explicit-key"
        assert client._base_url == "https://api.custom.example.com"
        client.finish()
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

        # Re-init with base_url (and api_key) should NOT reuse
        client_c = weave_init.init_weave(
            "test-project",
            api_key="new-key",
            base_url="https://new.example.com",
        )
        assert client_c is not client_b

        # Re-init with trace_server_url should NOT reuse
        client_d = weave_init.init_weave(
            "test-project",
            api_key="new-key",
            trace_server_url="https://trace.new.example.com",
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


def test_init_weave_without_base_url_stores_none_on_client(mock_wandb_api):
    """When base_url is not provided, client._base_url should be None."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client = weave_init.init_weave("test-project", api_key="key")
        assert client._base_url is None
        client.finish()
        weave_client_context.set_weave_client_global(None)


def test_get_wandb_api_context_falls_back_to_env(monkeypatch):
    """get_wandb_api_context should read from environment variables."""
    from weave.wandb_interface.context import get_wandb_api_context

    monkeypatch.setenv("WANDB_API_KEY", "env-key-123")
    assert get_wandb_api_context() == "env-key-123"


def test_wandb_base_url_falls_back_to_env(monkeypatch):
    """wandb_base_url should read from env var."""
    from weave.trace.env import wandb_base_url

    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    assert wandb_base_url() == "https://env.example.com"


# --- Multi-client isolation tests ---


def test_two_clients_have_independent_credentials(mock_wandb_api):
    """Two clients created with different credentials should each retain
    their own api_key and base_url without cross-contamination.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server_x = _make_mock_server()
    mock_server_y = _make_mock_server()

    with (
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server_x
        ):
            client_x = weave_init.init_weave(
                "proj-x",
                api_key="key-x",
                base_url="https://x.example.com",
            )

        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server_y
        ):
            client_y = weave_init.init_weave(
                "proj-y",
                api_key="key-y",
                base_url="https://y.example.com",
            )

        # client_x should still have its own credentials
        assert client_x._api_key == "key-x"
        assert client_x._base_url == "https://x.example.com"

        # client_y should have its own credentials
        assert client_y._api_key == "key-y"
        assert client_y._base_url == "https://y.example.com"

        client_y.finish()
        weave_client_context.set_weave_client_global(None)


def test_call_ui_url_uses_client_base_url(mock_wandb_api):
    """Call.ui_url should use the base_url from the client that created it,
    not a global or the default.
    """
    from weave.trace.call import Call

    call = Call(
        _op_name="test-op",
        project_id="test-entity/test-project",
        trace_id="trace-123",
        parent_id=None,
        inputs={},
        id="call-123",
        _base_url="https://custom.example.com",
    )
    url = call.ui_url
    assert "custom.example.com" in url
    assert "call-123" in url

    # A call without _base_url should fall back to env-based default
    call_default = Call(
        _op_name="test-op",
        project_id="test-entity/test-project",
        trace_id="trace-456",
        parent_id=None,
        inputs={},
        id="call-456",
    )
    url_default = call_default.ui_url
    assert "call-456" in url_default
    assert "custom.example.com" not in url_default


def test_no_global_state_leakage_after_init(mock_wandb_api, monkeypatch):
    """After init with explicit credentials, the module-level env readers
    should NOT return the explicit values (they should only read from env/netrc).
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    from weave.trace.env import wandb_base_url
    from weave.wandb_interface.context import get_wandb_api_context

    # Set env vars to known values
    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("WANDB_API_KEY", "env-key")

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        client = weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )

    # The client should hold the explicit values
    assert client._api_key == "explicit-key"
    assert client._base_url == "https://explicit.example.com"

    # But module-level readers should still return env values, NOT the explicit ones
    assert wandb_base_url() == "https://env.example.com"
    assert get_wandb_api_context() == "env-key"

    client.finish()
    weave_client_context.set_weave_client_global(None)


def test_internal_api_uses_client_credentials(mock_wandb_api):
    """wandb.Api created with explicit credentials should use them,
    not fall back to global state.
    """
    from weave.compat.wandb.wandb_thin.internal_api import Api

    api = Api(api_key="my-key", base_url="https://custom.example.com")
    assert api._api_key == "my-key"
    assert api._base_url == "https://custom.example.com"

    # Api without credentials should have None (falls back to env at query time)
    api_default = Api()
    assert api_default._api_key is None
    assert api_default._base_url is None


def test_project_creator_receives_client_credentials(mock_wandb_api):
    """WeaveClient.__init__ should pass api_key and base_url to
    project_creator.ensure_project_exists.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
        patch(
            "weave.trace.weave_client._ensure_project",
            return_value={"project_name": "test-project"},
        ) as mock_ensure,
    ):
        weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )
        mock_ensure.assert_called_once_with(
            "test-entity",
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )
        weave_client_context.set_weave_client_global(None)


def test_get_username_receives_credentials(mock_wandb_api):
    """get_username should be called with the explicit api_key and base_url."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch(
            "weave.trace.weave_init.get_username", return_value="test-user"
        ) as mock_get_user,
        patch("weave.trace.weave_init.init_message"),
    ):
        weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )
        mock_get_user.assert_called_once_with(
            api_key="explicit-key", base_url="https://explicit.example.com"
        )
        weave_client_context.set_weave_client_global(None)


def test_get_entity_project_receives_credentials(mock_wandb_api):
    """get_entity_project_from_project_name should pass credentials to Api."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
        patch(
            "weave.trace.weave_init.get_entity_project_from_project_name",
            return_value=("test-entity", "test-project"),
        ) as mock_get_entity,
    ):
        weave_init.init_weave(
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )
        mock_get_entity.assert_called_once_with(
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )
        weave_client_context.set_weave_client_global(None)


def test_completions_uses_client_api_key():
    """Completions and InferenceModels should prefer client._api_key over env."""
    from weave.chat.completions import Completions
    from weave.chat.inference_models import InferenceModels
    from weave.trace.weave_client import WeaveClient

    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity",
        "project",
        mock_server,
        ensure_project_exists=False,
        api_key="client-key",
    )
    comp = Completions(client)
    models = InferenceModels(client)

    with patch("weave.wandb_interface.context.get_wandb_api_context") as mock_env_key:
        mock_env_key.return_value = "env-key"
        # Both should prefer client._api_key without calling the env reader
        assert comp._client._api_key == "client-key"
        assert models._client._api_key == "client-key"
        mock_env_key.assert_not_called()

    client.finish()


def test_url_functions_with_explicit_base_url():
    """All URL functions should use explicit base_url when provided."""
    from weave.trace import urls

    for fn, args in [
        (urls.remote_project_root_url, ("entity", "project")),
        (urls.project_weave_root_url, ("entity", "project")),
        (urls.op_version_path, ("entity", "project", "my-op", "abc123")),
        (urls.object_version_path, ("entity", "project", "my-obj", "abc123")),
        (urls.leaderboard_path, ("entity", "project", "my-lb")),
        (urls.redirect_call, ("entity", "project", "call-id")),
    ]:
        url = fn(*args, base_url="https://custom.example.com")
        assert "custom.example.com" in url


def test_finish_one_client_does_not_affect_another(mock_wandb_api):
    """Finishing client_a should not affect client_b's credentials."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server_a = _make_mock_server()
    mock_server_b = _make_mock_server()

    with (
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server_a
        ):
            client_a = weave_init.init_weave(
                "proj-a",
                api_key="key-a",
                base_url="https://a.example.com",
            )

        with patch(
            "weave.trace.weave_init.init_weave_get_server", return_value=mock_server_b
        ):
            client_b = weave_init.init_weave(
                "proj-b",
                api_key="key-b",
                base_url="https://b.example.com",
            )

    # Finish client_a
    client_a.finish()

    # client_b's credentials should be unaffected
    assert client_b._api_key == "key-b"
    assert client_b._base_url == "https://b.example.com"

    client_b.finish()
    weave_client_context.set_weave_client_global(None)


@pytest.mark.disable_logging_error_check
def test_client_create_call_sets_base_url(mock_wandb_api):
    """WeaveClient.create_call should set _base_url on the Call object."""
    from weave.trace.weave_client import WeaveClient

    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity",
        "project",
        mock_server,
        ensure_project_exists=False,
        base_url="https://custom.example.com",
    )
    weave_client_context.set_weave_client_global(client)

    from weave.trace.op import op

    @op
    def dummy_op():
        pass

    call = client.create_call(dummy_op, {})
    assert call._base_url == "https://custom.example.com"
    client.finish_call(call, output=None)
    client.finish()
    weave_client_context.set_weave_client_global(None)


def test_thread_captures_client_base_url(mock_wandb_api):
    """Operations deferred to FutureExecutor should capture the client's
    _base_url via closure, not read from globals.
    """
    from weave.trace.weave_client import WeaveClient

    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity",
        "project",
        mock_server,
        ensure_project_exists=False,
        api_key="thread-key",
        base_url="https://thread.example.com",
    )

    captured_values: dict = {}

    def capture_creds():
        captured_values["api_key"] = client._api_key
        captured_values["base_url"] = client._base_url

    fut = client.future_executor.defer(capture_creds)
    fut.result()

    assert captured_values["api_key"] == "thread-key"
    assert captured_values["base_url"] == "https://thread.example.com"

    client.finish()


def test_wal_callback_uses_client_base_url(mock_wandb_api):
    """The WAL send callback should use self._base_url to generate call URLs."""
    from weave.trace.weave_client import WeaveClient

    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity",
        "project",
        mock_server,
        ensure_project_exists=False,
        base_url="https://wal.example.com",
    )

    with patch("weave.trace.weave_client.redirect_call") as mock_redirect:
        mock_redirect.return_value = "https://wal.example.com/r/call/test-id"
        client._wal_pending_call_ids.add("test-call-id")
        record = {
            "req": {
                "start": {
                    "id": "test-call-id",
                    "project_id": "entity/project",
                }
            }
        }
        client._on_wal_send("call_start", record)
        mock_redirect.assert_called_once_with(
            "entity", "project", "test-call-id", base_url="https://wal.example.com"
        )

    client.finish()
