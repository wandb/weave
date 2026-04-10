"""Tests for weave init authentication flow."""

import logging
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from weave.chat.completions import Completions
from weave.chat.inference_models import InferenceModels
from weave.compat.wandb.wandb_thin.internal_api import Api
from weave.trace import urls, weave_init
from weave.trace.call import Call
from weave.trace.context import weave_client_context
from weave.trace.env import wandb_base_url
from weave.trace.init_message import print_init_message
from weave.trace.op import op
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import (
    get_entity_project_from_project_name,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)
from weave.wandb_interface.context import get_wandb_api_context
from weave.wandb_interface.project_creator import (
    _ensure_project_exists,
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
        "weave.wandb_interface.project_creator.ensure_project_exists",
        return_value={"project_name": "test-project"},
    ):
        yield


def _make_mock_server():
    mock = MagicMock(spec=RemoteHTTPTraceServer)
    mock.server_info.return_value = MagicMock(
        min_required_weave_python_version="0.0.0",
        trace_server_version=None,
    )
    mock.ensure_project_exists.return_value = MagicMock(project_name="test-project")
    mock.get_call_processor.return_value = None
    mock.get_feedback_processor.return_value = None
    return mock


def _init_patches(mock_server):
    """Context manager bundle for the common init_weave mock set."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        with (
            patch(
                "weave.trace.weave_init.init_weave_get_server",
                return_value=mock_server,
            ),
            patch("weave.trace.weave_init._weave_is_available", return_value=True),
            patch("weave.trace.weave_init.get_username", return_value="test-user"),
            patch("weave.trace.weave_init.init_message"),
        ):
            yield

    return _ctx()


# ---------------------------------------------------------------------------
# Project name parsing
# ---------------------------------------------------------------------------


@dataclass
class SuccessCase:
    project_name: str
    mock_default_entity: str | None
    expected_entity: str
    expected_project: str

    def __str__(self) -> str:
        return f"{self.expected_entity}/{self.expected_project}"


@dataclass
class ExceptionCase:
    project_name: str
    expected_match: str

    def __str__(self) -> str:
        return self.project_name


@pytest.mark.parametrize(
    "case",
    [
        SuccessCase("test_entity/test_project", None, "test_entity", "test_project"),
        SuccessCase("test_project", "default_entity", "default_entity", "test_project"),
    ],
    ids=str,
)
def test_get_entity_project_from_project_name_success(
    case: SuccessCase, mock_wandb_api
):
    if case.mock_default_entity is not None:
        mock_wandb_api.default_entity_name.return_value = case.mock_default_entity

    entity, project = get_entity_project_from_project_name(case.project_name)
    assert entity == case.expected_entity
    assert project == case.expected_project

    if case.mock_default_entity is not None:
        mock_wandb_api.default_entity_name.assert_called_once()


def test_get_entity_project_from_project_name_with_wandb_entity_env(
    mock_wandb_api, monkeypatch
):
    monkeypatch.setenv("WANDB_ENTITY", "env_entity")

    entity, project = get_entity_project_from_project_name("test_project")
    assert entity == "env_entity"
    assert project == "test_project"
    mock_wandb_api.default_entity_name.assert_not_called()

    # Explicit entity in project name overrides env var
    entity, project = get_entity_project_from_project_name(
        "explicit_entity/test_project"
    )
    assert entity == "explicit_entity"
    assert project == "test_project"


@pytest.mark.parametrize(
    "case",
    [
        ExceptionCase("", "project_name must be non-empty"),
        ExceptionCase("   ", "project_name must be non-empty"),
        ExceptionCase("\t\n", "project_name must be non-empty"),
        ExceptionCase("entity/project/extra", "project_name must be of the form"),
        ExceptionCase("/test_project", "entity_name must be non-empty"),
        ExceptionCase("test_entity/", "project_name must be non-empty"),
        ExceptionCase("/", "entity_name must be non-empty"),
    ],
    ids=str,
)
def test_get_entity_project_from_project_name_exceptions(case: ExceptionCase):
    with pytest.raises(ValueError, match=case.expected_match):
        get_entity_project_from_project_name(case.project_name)


# ---------------------------------------------------------------------------
# Server creation & trace_server_url derivation
# ---------------------------------------------------------------------------


def test_init_weave_get_server_with_and_without_trace_server_url():
    """init_weave_get_server uses explicit trace_server_url or falls back to env."""
    server_explicit = weave_init.init_weave_get_server(
        api_key="test-key", trace_server_url="https://custom.example.com"
    )
    assert server_explicit.trace_server_url == "https://custom.example.com"
    assert server_explicit._auth == ("api", "test-key")

    server_default = weave_init.init_weave_get_server(api_key="test-key")
    assert server_default.trace_server_url is not None
    assert server_default._auth == ("api", "test-key")


def test_base_url_derives_trace_server_url(mock_wandb_api):
    """base_url derives trace_server_url per documented contract; explicit
    trace_server_url takes precedence.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = MagicMock()
    mock_server.server_info.return_value = MagicMock(
        min_required_weave_python_version="0.0.0",
        trace_server_version=None,
    )
    mock_server.get_call_processor.return_value = None
    mock_server.get_feedback_processor.return_value = None

    cases = [
        # (base_url, trace_server_url, expected_trace_server_url)
        ("https://custom.example.com", None, "https://custom.example.com/traces"),
        ("https://api.wandb.ai", None, "https://trace.wandb.ai"),
        (
            "https://custom.example.com",
            "https://explicit-trace.example.com",
            "https://explicit-trace.example.com",
        ),
    ]
    for base_url, tsurl, expected in cases:
        with (
            patch(
                "weave.trace.weave_init.init_weave_get_server",
                return_value=mock_server,
            ) as mock_get_server,
            patch("weave.trace.weave_init._weave_is_available", return_value=True),
            patch("weave.trace.weave_init.get_username", return_value="test-user"),
            patch("weave.trace.weave_init.init_message"),
        ):
            weave_init.init_weave(
                "test-project", api_key="key", base_url=base_url,
                trace_server_url=tsurl,
            )
            mock_get_server.assert_called_with("key", trace_server_url=expected)
            weave_client_context.set_weave_client_global(None)


# ---------------------------------------------------------------------------
# Init flow: credential storage, reuse, re-init, env fallback
# ---------------------------------------------------------------------------


def test_init_weave_credential_storage_and_env_skipping(mock_wandb_api):
    """Explicit api_key skips env lookup and is stored on the client along
    with base_url.
    """
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
        mock_env_key.assert_not_called()
        mock_get_server.assert_called_once_with(
            "explicit-key", trace_server_url="https://trace.custom.example.com"
        )
        assert client._api_key == "explicit-key"
        assert client._base_url == "https://api.custom.example.com"
        client.finish()


def test_init_weave_reuse_and_reinit(mock_wandb_api):
    """Same project without credential params reuses client; passing any
    credential param forces re-init.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with _init_patches(mock_server):
        client_a = weave_init.init_weave("test-project", api_key="key")
        assert weave_init.init_weave("test-project") is client_a  # reuse

        client_b = weave_init.init_weave("test-project", api_key="new-key")
        assert client_b is not client_a

        client_c = weave_init.init_weave(
            "test-project", api_key="new-key", base_url="https://new.example.com"
        )
        assert client_c is not client_b

        client_d = weave_init.init_weave(
            "test-project", api_key="new-key",
            trace_server_url="https://trace.new.example.com",
        )
        assert client_d is not client_c
        client_d.finish()


def test_init_weave_env_fallback_paths(mock_wandb_api, monkeypatch):
    """When api_key is omitted it reads from env; when base_url is omitted it
    eagerly resolves from WANDB_BASE_URL.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()
    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
        patch(
            "weave.trace.weave_init.get_wandb_api_context", return_value="env-key"
        ) as mock_ctx,
    ):
        client = weave_init.init_weave("test-project")
        mock_ctx.assert_called_once()
        assert client._api_key == "env-key"
        assert client._base_url == "https://env.example.com"
        client.finish()


def test_init_weave_version_check_uses_explicit_url(mock_wandb_api):
    """Version check should use the explicit trace_server_url."""
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
        mock_init_msg.check_min_weave_version.assert_called_once_with(
            "0.0.0", "https://custom-trace.example.com"
        )
        call_args = mock_init_msg.check_min_trace_server_version.call_args
        assert call_args[0][2] == "https://custom-trace.example.com"


def test_init_weave_prompts_login_when_no_key_anywhere(mock_wandb_api):
    """When no key is found anywhere, wandb.login() is invoked with base_url."""
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
        patch(
            "weave.trace.weave_init.get_wandb_api_context",
            side_effect=[None, "login-key"],
        ),
        patch("weave.trace.weave_init.wandb") as mock_wandb,
    ):
        mock_wandb.app_url.return_value = "https://custom.example.com"
        mock_wandb.login.return_value = None
        client = weave_init.init_weave(
            "test-project", base_url="https://custom.example.com"
        )
        mock_wandb.login.assert_called_once()
        mock_wandb.app_url.assert_called_with("https://custom.example.com")
        client.finish()


# ---------------------------------------------------------------------------
# Env reader sanity checks
# ---------------------------------------------------------------------------


def test_env_readers_return_env_values(monkeypatch):
    """get_wandb_api_context and wandb_base_url read from env vars."""
    monkeypatch.setenv("WANDB_API_KEY", "env-key-123")
    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    assert get_wandb_api_context() == "env-key-123"
    assert wandb_base_url() == "https://env.example.com"


# ---------------------------------------------------------------------------
# Multi-client isolation & global state
# ---------------------------------------------------------------------------


def test_multi_client_isolation_and_global_state(mock_wandb_api, monkeypatch):
    """Two clients keep independent credentials; finishing one doesn't affect the
    other; module-level env readers are not polluted by explicit init params.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server_x = _make_mock_server()
    mock_server_y = _make_mock_server()

    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("WANDB_API_KEY", "env-key")

    with (
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch("weave.trace.weave_init.get_username", return_value="test-user"),
        patch("weave.trace.weave_init.init_message"),
    ):
        with patch(
            "weave.trace.weave_init.init_weave_get_server",
            return_value=mock_server_x,
        ):
            client_x = weave_init.init_weave(
                "proj-x", api_key="key-x", base_url="https://x.example.com"
            )
        with patch(
            "weave.trace.weave_init.init_weave_get_server",
            return_value=mock_server_y,
        ):
            client_y = weave_init.init_weave(
                "proj-y", api_key="key-y", base_url="https://y.example.com"
            )

    # Independent credentials
    assert client_x._api_key == "key-x"
    assert client_x._base_url == "https://x.example.com"
    assert client_y._api_key == "key-y"
    assert client_y._base_url == "https://y.example.com"

    # Finishing one doesn't affect the other
    client_x.finish()
    assert client_y._api_key == "key-y"
    assert client_y._base_url == "https://y.example.com"

    # Module-level env readers are NOT polluted by explicit init params
    assert wandb_base_url() == "https://env.example.com"
    assert get_wandb_api_context() == "env-key"

    client_y.finish()


# ---------------------------------------------------------------------------
# Credential passthrough to downstream helpers
# ---------------------------------------------------------------------------


def test_init_weave_threads_credentials_to_helpers(mock_wandb_api):
    """init_weave passes api_key and base_url to ensure_project_exists,
    get_username, and get_entity_project_from_project_name.
    """
    mock_wandb_api.default_entity_name.return_value = "test-entity"
    mock_server = _make_mock_server()

    with (
        patch("weave.trace.weave_init.init_weave_get_server", return_value=mock_server),
        patch("weave.trace.weave_init._weave_is_available", return_value=True),
        patch(
            "weave.trace.weave_init.get_username", return_value="test-user"
        ) as mock_get_user,
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
        mock_get_user.assert_called_once_with(
            api_key="explicit-key", base_url="https://explicit.example.com"
        )
        mock_server.ensure_project_exists.assert_called_once_with(
            "test-entity",
            "test-project",
            api_key="explicit-key",
            base_url="https://explicit.example.com",
        )


def test_project_creator_passes_credentials_to_api():
    """_ensure_project_exists constructs wandb.Api with the given credentials."""
    mock_api = MagicMock()
    mock_api.project.return_value = {"project": {"name": "proj"}}

    with patch("weave.wandb_interface.project_creator.wandb") as mock_wandb:
        mock_wandb.Api.return_value = mock_api
        result = _ensure_project_exists(
            "entity", "proj", api_key="key", base_url="https://example.com"
        )
        mock_wandb.Api.assert_called_once_with(
            api_key="key", base_url="https://example.com"
        )
        assert result == {"project_name": "proj"}


# ---------------------------------------------------------------------------
# Eager credential resolution: Api, Completions, InferenceModels
# ---------------------------------------------------------------------------


def test_api_eager_credential_resolution(monkeypatch):
    """Api resolves credentials eagerly: explicit values win; otherwise
    env/netrc is snapshotted at construction time.
    """
    # Explicit values
    api = Api(api_key="my-key", base_url="https://custom.example.com")
    assert api._api_key == "my-key"
    assert api._base_url == "https://custom.example.com"

    # Falls back to env when no args given
    monkeypatch.setenv("WANDB_API_KEY", "env-key")
    monkeypatch.setenv("WANDB_BASE_URL", "https://env.example.com")
    api_default = Api()
    assert api_default._api_key == "env-key"
    assert api_default._base_url == "https://env.example.com"


def test_client_resolves_env_key_for_completions_and_models(monkeypatch):
    """WeaveClient eagerly resolves api_key from env so Completions and
    InferenceModels see it without their own fallback logic.
    """
    monkeypatch.setenv("WANDB_API_KEY", "env-key")
    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity", "project", mock_server, ensure_project_exists=False, api_key=None
    )

    assert Completions(client)._client._api_key == "env-key"
    assert InferenceModels(client)._client._api_key == "env-key"
    client.finish()


def test_completions_prefers_explicit_client_key():
    """When client has an explicit api_key, Completions and InferenceModels
    use it without touching env readers.
    """
    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity", "project", mock_server,
        ensure_project_exists=False, api_key="client-key",
    )

    with patch("weave.wandb_interface.context.get_wandb_api_context") as mock_env_key:
        mock_env_key.return_value = "env-key"
        assert Completions(client)._client._api_key == "client-key"
        assert InferenceModels(client)._client._api_key == "client-key"
        mock_env_key.assert_not_called()

    client.finish()


# ---------------------------------------------------------------------------
# Call & URL behavior
# ---------------------------------------------------------------------------


def test_call_ui_url_uses_base_url():
    """Call.ui_url uses _base_url when set, falls back to env default otherwise."""
    call = Call(
        _op_name="test-op",
        project_id="entity/project",
        trace_id="trace-123",
        parent_id=None,
        inputs={},
        id="call-123",
        _base_url="https://custom.example.com",
    )
    assert "custom.example.com" in call.ui_url
    assert "call-123" in call.ui_url

    call_default = Call(
        _op_name="test-op",
        project_id="entity/project",
        trace_id="trace-456",
        parent_id=None,
        inputs={},
        id="call-456",
    )
    assert "call-456" in call_default.ui_url
    assert "custom.example.com" not in call_default.ui_url


def test_url_functions_with_explicit_base_url():
    """All URL helpers accept and use explicit base_url."""
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


@pytest.mark.disable_logging_error_check
def test_create_call_and_children_thread_base_url(mock_wandb_api):
    """create_call stamps _base_url on Call; Call.children() passes it to
    _make_calls_iterator.
    """
    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity", "project", mock_server,
        ensure_project_exists=False, base_url="https://custom.example.com",
    )
    weave_client_context.set_weave_client_global(client)

    @op
    def dummy_op():
        pass

    # create_call stamps base_url
    call = client.create_call(dummy_op, {})
    assert call._base_url == "https://custom.example.com"
    client.finish_call(call, output=None)

    # children() passes base_url to _make_calls_iterator
    child_call = Call(
        _op_name="test-op",
        project_id="entity/project",
        trace_id="trace-123",
        parent_id=None,
        inputs={},
        id="call-123",
    )
    with patch("weave.trace.call._make_calls_iterator") as mock_iter:
        mock_iter.return_value = iter([])
        list(child_call.children())
        _, kwargs = mock_iter.call_args
        assert kwargs.get("base_url") == "https://custom.example.com"

    client.finish()


# ---------------------------------------------------------------------------
# Thread safety & WAL
# ---------------------------------------------------------------------------


def test_thread_captures_client_credentials():
    """FutureExecutor closure reads correct client credentials."""
    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity", "project", mock_server,
        ensure_project_exists=False,
        api_key="thread-key", base_url="https://thread.example.com",
    )

    captured: dict = {}

    def capture():
        captured["api_key"] = client._api_key
        captured["base_url"] = client._base_url

    client.future_executor.defer(capture).result()
    assert captured == {"api_key": "thread-key", "base_url": "https://thread.example.com"}
    client.finish()


def test_wal_callback_uses_client_base_url():
    """WAL send callback uses self._base_url to generate call URLs."""
    mock_server = _make_mock_server()
    client = WeaveClient(
        "entity", "project", mock_server,
        ensure_project_exists=False, base_url="https://wal.example.com",
    )

    with patch("weave.trace.weave_client.redirect_call") as mock_redirect:
        mock_redirect.return_value = "https://wal.example.com/r/call/test-id"
        client._wal_pending_call_ids.add("test-call-id")
        client._on_wal_send("call_start", {
            "req": {"start": {"id": "test-call-id", "project_id": "entity/project"}}
        })
        mock_redirect.assert_called_once_with(
            "entity", "project", "test-call-id", base_url="https://wal.example.com"
        )

    client.finish()


# ---------------------------------------------------------------------------
# Init message
# ---------------------------------------------------------------------------


def test_print_init_message_uses_base_url(caplog):
    """print_init_message uses explicit base_url in the project URL."""
    with (
        patch("weave.trace.init_message._print_version_check"),
        caplog.at_level(logging.INFO, logger="weave.trace.init_message"),
    ):
        print_init_message(
            "user", "entity", "project",
            read_only=False, base_url="https://custom.example.com",
        )
    assert "custom.example.com" in caplog.text
