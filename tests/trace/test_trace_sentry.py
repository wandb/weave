from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, MagicMock, call

import pytest

from weave.telemetry import trace_sentry


class FakeSession:
    def __init__(self) -> None:
        self.status_updates: list[str | None] = []

    def update(self, status: str | None = None) -> None:
        self.status_updates.append(status)


class FakeScope:
    def __init__(self) -> None:
        self._session: FakeSession | None = None
        self.tags: dict[str, Any] = {}
        self.user: Any = None

    def set_tag(self, key: str, value: Any) -> None:
        self.tags[key] = value


class FakeScopeContext:
    def __init__(self, scope: FakeScope) -> None:
        self.scope = scope

    def __enter__(self) -> FakeScope:
        return self.scope

    def __exit__(self, *_args: object) -> bool:
        return False


class FakeHub:
    def __init__(self, client: MagicMock) -> None:
        self.client = client
        self.scope = FakeScope()
        self._stack = [(client, self.scope)]
        self.captured_events: list[tuple[object, object | None]] = []
        self.raise_on_capture = False
        self.start_session_calls = 0
        self.end_session_calls = 0

    def capture_event(self, event: object, hint: object | None = None) -> None:
        if self.raise_on_capture:
            raise RuntimeError("capture failed")
        self.captured_events.append((event, hint))

    def start_session(self) -> None:
        self.start_session_calls += 1
        self.scope._session = FakeSession()

    def end_session(self) -> None:
        self.end_session_calls += 1
        self.scope._session = None

    def configure_scope(self) -> FakeScopeContext:
        return FakeScopeContext(self.scope)


def make_client() -> MagicMock:
    client = MagicMock()
    client.options = {"option": "value"}
    return client


def make_sentry(
    monkeypatch: pytest.MonkeyPatch, *, sentry_available: bool = True
) -> trace_sentry.Sentry:
    monkeypatch.setattr(trace_sentry, "SENTRY_AVAILABLE", sentry_available)
    monkeypatch.setattr(trace_sentry.atexit, "register", lambda _fn: None)
    return trace_sentry.Sentry()


def test_sentry_init_uses_sentry_available_for_disabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled_sentry = make_sentry(monkeypatch, sentry_available=True)
    assert enabled_sentry._disabled is False

    disabled_sentry = make_sentry(monkeypatch, sentry_available=False)
    assert disabled_sentry._disabled is True


def test_safe_noop_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=False)
    assert sentry.start_session() is None


def test_safe_noop_reports_internal_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    sentry.exception = MagicMock()  # type: ignore[method-assign]
    sentry.hub = SimpleNamespace(_stack=[])

    assert sentry.start_session() is None
    sentry.exception.assert_called_once()
    assert "Error in start_session" in sentry.exception.call_args[0][0]


def test_exception_safe_noop_does_not_recurse(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    sentry.hub = None

    assert sentry.exception("boom") is None


def test_environment_prefers_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=False)
    monkeypatch.setenv("WEAVE_SENTRY_ENV", "ci")

    assert sentry.environment == "ci"


@pytest.mark.parametrize(
    ("is_dev", "expected"), [(True, "development"), (False, "production")]
)
def test_environment_uses_install_location(
    monkeypatch: pytest.MonkeyPatch, is_dev: bool, expected: str
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=False)
    monkeypatch.delenv("WEAVE_SENTRY_ENV", raising=False)
    monkeypatch.setattr(trace_sentry, "_is_local_dev_install", lambda _module: is_dev)

    assert sentry.environment == expected


def test_setup_creates_client_and_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    hub = FakeHub(client)

    sentry_sdk = MagicMock()
    sentry_sdk.Client.return_value = client
    sentry_sdk.Hub.return_value = hub

    monkeypatch.setenv("WEAVE_SENTRY_ENV", "ci")
    monkeypatch.setattr(trace_sentry, "sentry_sdk", sentry_sdk)
    sentry = make_sentry(monkeypatch, sentry_available=True)

    sentry.setup()

    sentry_sdk.Client.assert_called_once_with(
        dsn=trace_sentry.SENTRY_DEFAULT_DSN,
        default_integrations=False,
        environment="ci",
        release=ANY,
    )
    sentry_sdk.Hub.assert_called_once_with(client)
    assert sentry.hub is hub


def test_exception_marks_session_and_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry_sdk = MagicMock()
    sentry_sdk.utils = MagicMock()
    sentry_sdk.utils.exc_info_from_error.return_value = ("exc_type", "exc", "tb")
    sentry_sdk.utils.event_from_exception.return_value = (
        {"event": "ok"},
        {"hint": "ok"},
    )
    monkeypatch.setattr(trace_sentry, "sentry_sdk", sentry_sdk)

    sentry = make_sentry(monkeypatch, sentry_available=True)
    client = make_client()
    hub = FakeHub(client)
    hub.scope._session = FakeSession()
    sentry.hub = hub

    sentry.exception("boom", handled=True)

    sentry_sdk.utils.exc_info_from_error.assert_called_once()
    assert isinstance(sentry_sdk.utils.exc_info_from_error.call_args[0][0], Exception)
    sentry_sdk.utils.event_from_exception.assert_called_once_with(
        ("exc_type", "exc", "tb"),
        client_options=client.options,
        mechanism={"type": "generic", "handled": True},
    )
    assert hub.captured_events == [({"event": "ok"}, {"hint": "ok"})]
    assert hub.scope._session is not None
    assert hub.scope._session.status_updates == ["errored"]
    client.flush.assert_called_once()


def test_exception_uses_sys_exc_info_and_handles_capture_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry_sdk = MagicMock()
    sentry_sdk.utils = MagicMock()
    sentry_sdk.utils.event_from_exception.return_value = (
        {"event": "ok"},
        {"hint": "ok"},
    )
    monkeypatch.setattr(trace_sentry, "sentry_sdk", sentry_sdk)

    sentry = make_sentry(monkeypatch, sentry_available=True)
    client = make_client()
    hub = FakeHub(client)
    hub.scope._session = FakeSession()
    hub.raise_on_capture = True
    sentry.hub = hub

    exc_info = (RuntimeError, RuntimeError("boom"), None)
    monkeypatch.setattr(trace_sentry.sys, "exc_info", lambda: exc_info)

    sentry.exception(None, status="abnormal")

    sentry_sdk.utils.exc_info_from_error.assert_not_called()
    sentry_sdk.utils.event_from_exception.assert_called_once_with(
        exc_info,
        client_options=client.options,
        mechanism={"type": "generic", "handled": False},
    )
    assert hub.scope._session is not None
    assert hub.scope._session.status_updates == ["abnormal"]
    client.flush.assert_called_once()


def test_session_lifecycle_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    client = make_client()
    hub = FakeHub(client)
    sentry.hub = hub

    sentry.start_session()
    assert hub.start_session_calls == 1

    sentry.start_session()
    assert hub.start_session_calls == 1

    sentry.mark_session(status="ok")
    assert hub.scope._session is not None
    assert hub.scope._session.status_updates == ["ok"]

    sentry.end_session()
    assert hub.end_session_calls == 1
    client.flush.assert_called_once()

    sentry.end_session()
    assert hub.end_session_calls == 1
    client.flush.assert_called_once()


def test_configure_scope_sets_tags_user_and_starts_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    hub = FakeHub(make_client())
    sentry.hub = hub

    sentry.configure_scope(
        tags={"team": "ml", "empty": "", "missing": None, "user": {"id": "u1"}}
    )

    assert hub.scope.tags == {"team": "ml", "user": {"id": "u1"}}
    assert hub.scope.user == {"id": "u1"}
    assert hub.start_session_calls == 1

    sentry.configure_scope(tags=None)
    assert hub.start_session_calls == 1


def test_watch_decorator_reports_and_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    sentry.exception = MagicMock()  # type: ignore[method-assign]

    @sentry.watch()
    def explode() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        explode()

    sentry.exception.assert_called_once()


def test_track_event_captures_structured_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    hub = FakeHub(make_client())
    sentry.hub = hub

    sentry.track_event("user_login", tags={"plan": "pro"}, username="andrew")

    assert hub.captured_events == [
        (
            {
                "message": "user_login",
                "level": "info",
                "tags": {"plan": "pro"},
                "user": {"username": "andrew"},
            },
            None,
        )
    ]


def test_track_event_noops_when_sentry_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=False)
    hub = FakeHub(make_client())
    sentry.hub = hub

    sentry.track_event("ignored")
    assert hub.captured_events == []


def test_is_local_dev_install_checks_site_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        trace_sentry.site, "getsitepackages", lambda: ["/venv/lib/site-packages"]
    )
    in_site_packages = SimpleNamespace(
        __file__="/venv/lib/site-packages/weave/__init__.py"
    )
    in_repo = SimpleNamespace(__file__="/Users/andrew/src/weave/weave/__init__.py")
    missing_file = SimpleNamespace()

    assert trace_sentry._is_local_dev_install(in_site_packages) is False
    assert trace_sentry._is_local_dev_install(in_repo) is True
    assert trace_sentry._is_local_dev_install(missing_file) is False


def test_log_warning_and_error_report_to_sentry_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    capture_message = MagicMock()
    monkeypatch.setattr(trace_sentry, "logger", logger)
    monkeypatch.setattr(trace_sentry, "SENTRY_AVAILABLE", True)
    monkeypatch.setattr(
        trace_sentry, "sentry_sdk", SimpleNamespace(capture_message=capture_message)
    )

    trace_sentry.log_warning("warn")
    trace_sentry.log_error("err")

    logger.warning.assert_called_once_with("warn")
    logger.exception.assert_called_once_with("err")
    assert capture_message.call_args_list == [
        call("warn", level="warning"),
        call("err", level="error"),
    ]


def test_log_warning_and_error_skip_sentry_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    capture_message = MagicMock()
    monkeypatch.setattr(trace_sentry, "logger", logger)
    monkeypatch.setattr(trace_sentry, "SENTRY_AVAILABLE", False)
    monkeypatch.setattr(
        trace_sentry, "sentry_sdk", SimpleNamespace(capture_message=capture_message)
    )

    trace_sentry.log_warning("warn")
    trace_sentry.log_error("err")

    logger.warning.assert_called_once_with("warn")
    logger.exception.assert_called_once_with("err")
    capture_message.assert_not_called()
