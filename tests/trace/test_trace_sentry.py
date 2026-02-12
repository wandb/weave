from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call

import pytest

from weave.telemetry import trace_sentry


def make_sentry(
    monkeypatch: pytest.MonkeyPatch, *, sentry_available: bool = True
) -> trace_sentry.Sentry:
    monkeypatch.setattr(trace_sentry, "SENTRY_AVAILABLE", sentry_available)
    monkeypatch.setattr(trace_sentry.atexit, "register", lambda _fn: None)
    return trace_sentry.Sentry()


def make_hub_with_scope(
    *,
    session: MagicMock | None = None,
    start_session_side_effect: bool = False,
    end_session_side_effect: bool = False,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock | None]:
    client = MagicMock()
    client.options = {"option": "value"}

    scope = MagicMock()
    scope._session = session

    hub = MagicMock()
    hub.client = client
    hub._stack = [(client, scope)]

    if start_session_side_effect:
        created_session = session if session is not None else MagicMock()

        def _start_session() -> None:
            scope._session = created_session

        hub.start_session.side_effect = _start_session

    if end_session_side_effect:

        def _end_session() -> None:
            scope._session = None

        hub.end_session.side_effect = _end_session

    scope_context = MagicMock()
    scope_context.__enter__.return_value = scope
    scope_context.__exit__.return_value = False
    hub.configure_scope.return_value = scope_context

    return hub, client, scope, session


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
    sentry_sdk = MagicMock()
    client = MagicMock()
    hub = MagicMock()
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
    session = MagicMock()
    hub, client, _scope, _ = make_hub_with_scope(session=session)
    sentry.hub = hub

    sentry.exception("boom", handled=True)

    sentry_sdk.utils.exc_info_from_error.assert_called_once()
    assert isinstance(sentry_sdk.utils.exc_info_from_error.call_args[0][0], Exception)
    sentry_sdk.utils.event_from_exception.assert_called_once_with(
        ("exc_type", "exc", "tb"),
        client_options=client.options,
        mechanism={"type": "generic", "handled": True},
    )
    hub.capture_event.assert_called_once_with({"event": "ok"}, hint={"hint": "ok"})
    session.update.assert_called_once_with(status="errored")
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
    session = MagicMock()
    hub, client, _scope, _ = make_hub_with_scope(session=session)
    hub.capture_event.side_effect = RuntimeError("capture failed")
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
    session.update.assert_called_once_with(status="abnormal")
    client.flush.assert_called_once()


def test_session_lifecycle_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    session = MagicMock()
    hub, client, scope, _ = make_hub_with_scope(
        session=None,
        start_session_side_effect=True,
        end_session_side_effect=True,
    )

    def _start_session() -> None:
        scope._session = session

    hub.start_session.side_effect = _start_session
    sentry.hub = hub

    sentry.start_session()
    assert hub.start_session.call_count == 1

    sentry.start_session()
    assert hub.start_session.call_count == 1

    sentry.mark_session(status="ok")
    session.update.assert_called_once_with(status="ok")

    sentry.end_session()
    assert hub.end_session.call_count == 1
    client.flush.assert_called_once()

    sentry.end_session()
    assert hub.end_session.call_count == 1
    client.flush.assert_called_once()


def test_configure_scope_sets_tags_user_and_starts_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=True)
    session = MagicMock()
    hub, _client, scope, _ = make_hub_with_scope(session=None)

    def _start_session() -> None:
        scope._session = session

    hub.start_session.side_effect = _start_session
    sentry.hub = hub

    sentry.configure_scope(
        tags={"team": "ml", "empty": "", "missing": None, "user": {"id": "u1"}}
    )

    assert scope.set_tag.call_args_list == [
        call("team", "ml"),
        call("user", {"id": "u1"}),
    ]
    assert scope.user == {"id": "u1"}
    assert hub.start_session.call_count == 1

    sentry.configure_scope(tags=None)
    assert hub.start_session.call_count == 1


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
    hub, _client, _scope, _ = make_hub_with_scope()
    sentry.hub = hub

    sentry.track_event("user_login", tags={"plan": "pro"}, username="andrew")

    hub.capture_event.assert_called_once_with(
        {
            "message": "user_login",
            "level": "info",
            "tags": {"plan": "pro"},
            "user": {"username": "andrew"},
        }
    )


def test_track_event_noops_when_sentry_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry = make_sentry(monkeypatch, sentry_available=False)
    hub, _client, _scope, _ = make_hub_with_scope()
    sentry.hub = hub

    sentry.track_event("ignored")
    hub.capture_event.assert_not_called()


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
