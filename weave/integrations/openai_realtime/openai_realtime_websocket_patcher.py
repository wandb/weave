from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from weave.integrations.openai_realtime import connection
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

_websocket_patcher: MultiPatcher | None = None

logger = logging.getLogger(__name__)


def _to_str_or_none(value: Any) -> str | None:
    try:
        if value is None:
            return None
        return str(value)
    except Exception:
        return None


def _is_valid_realtime_url(url: Any) -> bool:
    """Return True if url points to OpenAI Realtime service.

    Criteria:
    - URL starts with either 'wss://api.openai.com' or 'api.openai.com'
    """
    s = _to_str_or_none(url)
    if not s:
        return False
    s_lower = s.lower()
    print(url)
    return s_lower.startswith("wss://api.openai.com") or s_lower.startswith(
        "api.openai.com"
    )


def _extract_url_from_args_kwargs(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    pos: int = 0,
    kw: str | None = None,
) -> Any:
    # Prefer positional at given index if present
    if len(args) > pos:
        return args[pos]
    # Else fallback to provided kw name if any
    if kw is not None and kw in kwargs:
        return kwargs.get(kw)
    # Common alternates used by various libs
    for candidate in ("url", "uri", "wsuri"):
        if candidate in kwargs:
            return kwargs.get(candidate)
    return None


class OpenAIRealtimeSettings(IntegrationSettings):
    """Settings for OpenAI Realtime integration.

    Attributes:
        enabled: Whether the integration is enabled at all
        op_settings: Operation settings for traced functions
        patch_websockets: Whether to globally patch websocket modules (default: True)
        finish_timeout: Maximum seconds to wait for realtime exit handler.
            - float value N: run on_exit and wait up to N seconds (default: 3.0)
            - None: skip on_exit and exit immediately
    """

    patch_websockets: bool = True
    # Default to 3 seconds; None means skip exit handling
    finish_timeout: float | None = 3.0


def get_openai_realtime_websocket_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = OpenAIRealtimeSettings()

    # Check if settings is our custom type and respect patch_websockets flag
    if isinstance(settings, OpenAIRealtimeSettings):
        if not settings.enabled or not settings.patch_websockets:
            return NoOpPatcher()
    elif not settings.enabled:
        return NoOpPatcher()

    # Configure connection-level graceful-exit behavior
    try:
        # Import late to avoid circulars at module import time
        from weave.integrations.openai_realtime import connection as _conn

        if isinstance(settings, OpenAIRealtimeSettings):
            _conn.configure_realtime_finish_timeout(settings.finish_timeout)
        else:
            _conn.configure_realtime_finish_timeout(3.0)
    except Exception:
        logger.exception("Failed to configure realtime finish timeout; using default")

    global _websocket_patcher
    if _websocket_patcher is not None:
        return _websocket_patcher

    # Patcher for 'websocket-client'
    def make_new_sync_value(original_class: Any) -> Any:
        if getattr(original_class, "_weave_initialized", False):
            return original_class

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract URL and validate against OpenAI Realtime expectations
            supplied_url = _extract_url_from_args_kwargs(args, kwargs, pos=0, kw="url")
            if not _is_valid_realtime_url(supplied_url):
                # Autopatcher case: return unwrapped instance
                return original_class(*args, **kwargs)
            kwargs["original_websocket_app"] = original_class
            return connection.WebSocketApp(*args, **kwargs)

        for attr in dir(original_class):
            if not hasattr(wrapper, attr):
                try:
                    setattr(wrapper, attr, getattr(original_class, attr))
                except (AttributeError, TypeError):
                    pass

        return wrapper

    # Patcher for 'websockets'
    def make_new_async_value(original_connect: Any) -> Any:
        if getattr(original_connect, "_weave_initialized", False):
            return original_connect

        @wraps(original_connect)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            supplied_url = _extract_url_from_args_kwargs(args, kwargs, pos=0, kw="uri")
            if not _is_valid_realtime_url(supplied_url):
                # Autopatcher case: return unwrapped original connection
                return await original_connect(*args, **kwargs)
            original_connection = await original_connect(*args, **kwargs)
            return connection.WeaveAsyncWebsocketConnection(original_connection)

        return wrapper

    # Patcher for 'aiohttp'
    def make_aiohttp_ws_connect(original_ws_connect: Any) -> Any:
        if getattr(original_ws_connect, "_weave_initialized", False):
            return original_ws_connect

        @wraps(original_ws_connect)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # We only get a relative url here, base url is in the parent class
            # No relative url supplied
            if len(args) < 2:
                return await original_ws_connect(*args, **kwargs)

            rel_url = args[1]

            if not rel_url or not isinstance(rel_url, str) or "realtime" not in rel_url:
                return await original_ws_connect(*args, **kwargs)

            original_ws = await original_ws_connect(*args, **kwargs)
            return connection.WeaveAiohttpWebsocketConnection(original_ws)

        return wrapper

    _websocket_patcher = MultiPatcher(
        [
            SymbolPatcher(
                get_base_symbol=lambda: importlib.import_module("websocket"),
                attribute_name="WebSocketApp",
                make_new_value=make_new_sync_value,
            ),
            SymbolPatcher(
                get_base_symbol=lambda: importlib.import_module("websockets"),
                attribute_name="connect",
                make_new_value=make_new_async_value,
            ),
            SymbolPatcher(
                get_base_symbol=lambda: importlib.import_module(
                    "aiohttp"
                ).ClientSession,
                attribute_name="ws_connect",
                make_new_value=make_aiohttp_ws_connect,
            ),
        ]
    )

    return _websocket_patcher


# Direct wrapper functions for manual instance wrapping when global patching is disabled
def wrap_websocket_sync(websocket_app_class: type) -> Any:
    """Manually wrap a WebSocketApp class for Weave tracking.

    Use this when global patching is disabled and you want to wrap specific instances.

    Example:
        from websocket import WebSocketApp
        from weave.integrations.openai_realtime import wrap_websocket_sync

        TrackedWebSocketApp = wrap_websocket_sync(WebSocketApp)
        ws = TrackedWebSocketApp(url, on_message=handler)
    """
    if getattr(websocket_app_class, "_weave_initialized", False):
        return websocket_app_class

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        supplied_url = _extract_url_from_args_kwargs(args, kwargs, pos=0, kw="url")
        if not _is_valid_realtime_url(supplied_url):
            logger.error(
                "Cannot patch non-realtime websocket connection %s. Expected url to start with wss://api.openai.com",
                _to_str_or_none(supplied_url),
            )
            # Return unwrapped instance
            return websocket_app_class(*args, **kwargs)
        kwargs["original_websocket_app"] = websocket_app_class
        return connection.WebSocketApp(*args, **kwargs)

    for attr in dir(websocket_app_class):
        if not hasattr(wrapper, attr):
            try:
                setattr(wrapper, attr, getattr(websocket_app_class, attr))
            except (AttributeError, TypeError):
                pass

    return wrapper


def wrap_websocket_async(
    connection_instance: Any,
) -> connection.WeaveAsyncWebsocketConnection:
    """Manually wrap an async websocket connection for Weave tracking.

    Use this when global patching is disabled and you want to wrap specific connections.

    Example:
        import websockets
        from weave.integrations.openai_realtime import wrap_websocket_async

        async def connect():
            ws = await websockets.connect(url)
            tracked_ws = wrap_websocket_async(ws)
            return tracked_ws
    """
    if isinstance(connection_instance, connection.WeaveAsyncWebsocketConnection):
        return connection_instance
    return connection.WeaveAsyncWebsocketConnection(connection_instance)


def wrap_websocket_connect(connect_func: Callable) -> Callable:
    """Wrap an async websocket connect function to automatically track connections.

    Use this as a decorator or wrapper for connect functions.

    Example:
        import websockets
        from weave.integrations.openai_realtime import wrap_websocket_connect

        tracked_connect = wrap_websocket_connect(websockets.connect)
        ws = await tracked_connect(url)
    """
    if getattr(connect_func, "_weave_initialized", False):
        return connect_func

    @wraps(connect_func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        supplied_url = _extract_url_from_args_kwargs(args, kwargs, pos=0, kw="uri")
        if not _is_valid_realtime_url(supplied_url):
            logger.error(
                "Cannot patch non-realtime websocket connection %s. Expected url to start with wss://api.openai.com",
                _to_str_or_none(supplied_url),
            )
            # Return unwrapped original connection
            return await connect_func(*args, **kwargs)
        original_connection = await connect_func(*args, **kwargs)
        return connection.WeaveAsyncWebsocketConnection(original_connection)

    return wrapper
