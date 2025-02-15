"""
This module provides a simple interface to the Sentry SDK.
It is a thin wrapper around the Sentry SDK that provides a few
convenience methods for logging exceptions and marking sessions.
Furthermore, it ensures that the Sentry SDK is properly set up
and that we don't interfere with the user's own Sentry SDK setup.

This file is a trimmed down version of the original WandB Sentry module.
"""

from __future__ import annotations

__all__ = ("Sentry",)


import atexit
import functools
import os
import site
import sys
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from sentry_sdk._types import Event, ExcInfo


import sentry_sdk  # type: ignore
import sentry_sdk.utils  # type: ignore

SENTRY_DEFAULT_DSN = "https://99697cf8ca5158250d3dd6cb23cca9b0@o151352.ingest.us.sentry.io/4507019311251456"

SessionStatus = Literal["ok", "exited", "crashed", "abnormal"]


def _safe_noop(func: Callable) -> Callable:
    """Decorator to ensure that Sentry methods do nothing if disabled and don't raise."""

    @functools.wraps(func)
    def wrapper(self: type[Sentry], *args: Any, **kwargs: Any) -> Any:
        if self._disabled:
            return None
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            # do not call self.exception here to avoid infinite recursion
            if func.__name__ != "exception":
                self.exception(f"Error in {func.__name__}: {e}")
            return None

    return wrapper


class Sentry:
    _disabled: bool

    def __init__(self) -> None:
        self._sent_messages: set = set()

        self.dsn = SENTRY_DEFAULT_DSN

        self.hub: sentry_sdk.hub.Hub | None = None

        self._disabled = False

        # ensure we always end the Sentry session
        atexit.register(self.end_session)

    @property
    def environment(self) -> str:
        """Return the environment we're running in."""
        set_env = os.environ.get("WEAVE_SENTRY_ENV", None)
        if set_env:
            return set_env

        import weave

        is_dev = _is_local_dev_install(weave)
        if is_dev:
            return "development"

        return "production"

    @_safe_noop
    def setup(self) -> None:
        """Setup Sentry SDK.

        We use lower-level APIs (i.e., not sentry_sdk.init) here
        to avoid the possibility of interfering with the user's
        own Sentry SDK setup.
        """
        from weave import version

        client = sentry_sdk.Client(
            dsn=self.dsn,
            default_integrations=False,
            environment=self.environment,
            release=version.VERSION,
        )
        self.hub = sentry_sdk.Hub(client)

    @_safe_noop
    def exception(
        self,
        exc: str | BaseException | ExcInfo | None,
        handled: bool = False,
        status: SessionStatus | None = None,
    ) -> None:
        """Log an exception to Sentry."""
        error = Exception(exc) if isinstance(exc, str) else exc
        # based on self.hub.capture_exception(_exc)
        if error is not None:
            exc_info = sentry_sdk.utils.exc_info_from_error(error)
        else:
            exc_info = sys.exc_info()

        event, hint = sentry_sdk.utils.event_from_exception(
            exc_info,
            client_options=self.hub.client.options,  # type: ignore
            mechanism={"type": "generic", "handled": handled},
        )
        try:
            self.hub.capture_event(event, hint=hint)  # type: ignore
        except Exception:
            pass

        # if the status is not explicitly set, we'll set it to "crashed" if the exception
        # was unhandled, or "errored" if it was handled
        status = status or ("crashed" if not handled else "errored")  # type: ignore
        self.mark_session(status=status)

        client, _ = self.hub._stack[-1]  # type: ignore
        if client is not None:
            client.flush()

        return None

    @_safe_noop
    def start_session(self) -> None:
        """Start a new session."""
        assert self.hub is not None
        # get the current client and scope
        _, scope = self.hub._stack[-1]
        session = scope._session

        # if there's no session, start one
        if session is None:
            self.hub.start_session()

    @_safe_noop
    def end_session(self) -> None:
        """End the current session."""
        assert self.hub is not None
        # get the current client and scope
        client, scope = self.hub._stack[-1]
        session = scope._session

        if session is not None and client is not None:
            self.hub.end_session()
            client.flush()

    @_safe_noop
    def mark_session(self, status: SessionStatus | None = None) -> None:
        """Mark the current session with a status."""
        assert self.hub is not None
        _, scope = self.hub._stack[-1]
        session = scope._session

        if session is not None:
            session.update(status=status)

    @_safe_noop
    def configure_scope(
        self,
        tags: dict[str, Any] | None = None,
    ) -> None:
        """Configure the Sentry scope for the current thread.

        This function should be called at the beginning of every thread that
        will send events to Sentry. It sets the tags that will be applied to
        all events sent from this thread. It also tries to start a session
        if one doesn't already exist for this thread.
        """
        assert self.hub is not None

        with self.hub.configure_scope() as scope:
            if tags is not None:
                for tag in tags:
                    val = tags.get(tag, None)
                    if val not in (None, ""):
                        scope.set_tag(tag, val)
                    if tag == "user":
                        scope.user = val

        self.start_session()

    # Not in the original WandB Sentry module
    def watch(self) -> Callable:
        def watch_dec(func: Callable) -> Callable:
            """Decorator to watch a function for exceptions and log them to Sentry."""

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.exception(e)
                    raise

            return wrapper

        return watch_dec

    # Not in the original WandB Sentry module
    def track_event(
        self,
        event_name: str,
        tags: dict[str, Any] | None = None,
        username: str | None = None,
    ) -> None:
        """Track an event to Sentry."""
        assert self.hub is not None

        event_data: Event = {
            "message": event_name,
            "level": "info",
            "tags": tags or {},
            "user": {
                "username": username,
            },
        }

        self.hub.capture_event(event_data)


def _is_local_dev_install(module: Any) -> bool:
    # Check if the __file__ attribute exists
    if hasattr(module, "__file__"):
        module_path = module.__file__
        # Check if the path is within any of the site-packages directories
        for directory in site.getsitepackages():
            if directory in module_path:
                return False
        return True
    else:
        return False


global_trace_sentry = Sentry()
global_trace_sentry.setup()
global_trace_sentry.configure_scope()
