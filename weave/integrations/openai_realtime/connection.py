from __future__ import annotations

import atexit
import json
import logging
import threading
import uuid
from typing import Any

from weave.integrations.openai_realtime.conversation_manager import ConversationManager

# Use project-local modules (no package-relative imports here)
from weave.integrations.openai_realtime.models import (
    create_server_message_from_dict,
    create_user_message_from_dict,
)

logger = logging.getLogger(__name__)

try:
    from aiohttp import WSMsgType
except ImportError:
    ClientWebSocketResponse = None
    WSMsgType = None


def _try_json_load(data: Any) -> Any:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    if isinstance(data, bytes):
        try:
            return json.loads(data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return data
    return data


class WeaveMediaConnection:
    _weave_initialized = True
    # Global config set by patcher
    _finish_timeout_seconds: float | None = 3.0
    _skip_on_exit: bool = False

    @classmethod
    def _configure_finish_behavior(cls, finish_timeout: float | None) -> None:
        # None => skip on_exit entirely
        if finish_timeout is None:
            cls._skip_on_exit = True
            cls._finish_timeout_seconds = None
            return
        try:
            cls._finish_timeout_seconds = float(finish_timeout)
            cls._skip_on_exit = False
        except Exception:
            # Fall back to default
            cls._finish_timeout_seconds = 3.0
            cls._skip_on_exit = False

    def __init__(
        self,
        url: str,
        header: Any = None,
        on_open: Any = None,
        on_message: Any = None,
        on_error: Any = None,
        on_close: Any = None,
        original_websocket_app: Any = None,
        **kwargs: Any,
    ) -> None:
        if original_websocket_app is None:
            raise ValueError("original_websocket_app must be provided")
        self.url = url
        self.header = header
        self.id = str(uuid.uuid4())
        # Track conversation state for this connection
        self.conversation_manager = ConversationManager()
        # Attach base URL for downstream exports
        try:
            self.conversation_manager.client_base_url = self.url
        except Exception:
            pass

        # Wrap user-provided handlers with tracing and session management
        self.wrapped_on_open = self._wrap_handler("on_open", on_open)
        self.wrapped_on_message = self._wrap_handler_with_session(
            "on_message", on_message
        )
        self.wrapped_on_error = self._wrap_handler("on_error", on_error)
        self.wrapped_on_close = self._wrap_handler("on_close", on_close)

        self.ws = original_websocket_app(
            self.url,
            header=self.header,
            on_open=self.wrapped_on_open,
            on_message=self.wrapped_on_message,
            on_error=self.wrapped_on_error,
            on_close=self.wrapped_on_close,
            **kwargs,
        )
        self.ws.send = self._wrap_sender(self.ws.send)
        # Ensure on-exit runs if process exits abruptly
        self._exit_ran = False
        self._atexit_registered = False
        try:
            atexit.register(self._run_exit_handler_once)
            self._atexit_registered = True
        except Exception:
            pass

    def _wrap_sender(self, sender: Any) -> Any:
        def wrapper(
            data: Any, opcode: int = 1
        ) -> Any:  # opcode is websocket.ABNF.OPCODE_TEXT
            # Process outgoing events with session manager
            parsed_data = _try_json_load(data)
            if isinstance(parsed_data, dict) and (
                typed_message := create_user_message_from_dict(parsed_data)
            ):
                self.conversation_manager.process_event(typed_message)
            return sender(data, opcode)

        return wrapper

    def _wrap_handler(self, name: str, handler: Any) -> Any:
        if handler is None:
            # If this is an on_close handler, still run our exit logic
            if name == "on_close":

                def _default_on_close(*_args: Any, **_kwargs: Any) -> None:
                    self._run_exit_handler_once()

                return _default_on_close
            return None

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # The first argument is always the websocket instance, so we skip it
            try:
                return handler(*args, **kwargs)
            finally:
                if name == "on_close":
                    self._run_exit_handler_once()

        return wrapper

    def _wrap_handler_with_session(self, name: str, handler: Any) -> Any:
        if handler is None:
            return None

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Process incoming message events with session manager
            if len(args) > 1:  # Message is the second argument
                data = args[1]
                parsed_data = _try_json_load(data)
                if isinstance(parsed_data, dict) and (
                    typed_message := create_server_message_from_dict(parsed_data)
                ):
                    self.conversation_manager.process_event(typed_message)
            # Call the original handler
            return handler(*args, **kwargs)

        return wrapper

    def send(
        self, data: Any, opcode: int = 1
    ) -> Any:  # opcode is websocket.ABNF.OPCODE_TEXT
        self.ws.send(data, opcode)

    def run_forever(self, **kwargs: Any) -> Any:
        self.ws.run_forever(**kwargs)

    def close(self, **kwargs: Any) -> Any:
        try:
            return self.ws.close(**kwargs)
        finally:
            self._run_exit_handler_once()

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager

    # ---- Exit handling ----
    def _run_exit_handler_once(self) -> None:
        if getattr(self, "_exit_ran", False):
            return
        self._exit_ran = True
        try:
            # Optionally skip on_exit entirely
            if self._skip_on_exit:
                return

            timeout = self._finish_timeout_seconds

            def _target() -> None:
                try:
                    self.conversation_manager.state.on_exit()
                except Exception:
                    logger.exception("Error in realtime on_exit handler")

            t = threading.Thread(
                target=_target, name="WeaveRealtimeOnExit", daemon=True
            )
            t.start()
            # If timeout is None, treat as immediate return
            if isinstance(timeout, (int, float)) and timeout is not None:
                t.join(timeout=float(timeout))
        finally:
            # Stop the worker thread promptly
            try:
                self.conversation_manager._stop_worker_thread()
            except Exception:
                pass


class WebSocketApp(WeaveMediaConnection):
    pass


class WeaveAsyncWebsocketConnection:
    _weave_initialized = True

    def __init__(self, original_connection: Any):
        self.original_connection = original_connection
        self.id = str(uuid.uuid4())
        self.conversation_manager = ConversationManager()
        self._exit_ran = False
        try:
            atexit.register(self._run_exit_handler_once)
        except Exception:
            pass

    async def send(self, *args: Any, **kwargs: Any) -> None:
        data = args[0] if args else None
        parsed_data = _try_json_load(data)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_data, dict) and (
            typed_message := create_user_message_from_dict(parsed_data)
        ):
            self.conversation_manager.process_event(typed_message)
        return await self.original_connection.send(*args, **kwargs)

    async def recv(self, *args: Any, **kwargs: Any) -> Any:
        data = await self.original_connection.recv(*args, **kwargs)
        parsed_data = _try_json_load(data)
        # Forward incoming server messages to conversation manager
        if isinstance(parsed_data, dict) and (
            typed_message := create_server_message_from_dict(parsed_data)
        ):
            self.conversation_manager.process_event(typed_message)
        return data

    async def close(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await self.original_connection.close(*args, **kwargs)
        finally:
            self._run_exit_handler_once()

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        try:
            return await self.recv()
        except self.original_connection.ConnectionClosed:
            raise StopAsyncIteration from None

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager

    def __getattr__(self, name: str) -> Any:
        if name == "send":
            return self.send
        if name == "recv":
            return self.recv
        if name == "close":
            return self.close
        if name == "get_conversation_manager":
            return self.get_conversation_manager
        return getattr(self.original_connection, name)

    # ---- Exit handling ----
    def _run_exit_handler_once(self) -> None:
        if getattr(self, "_exit_ran", False):
            return
        self._exit_ran = True
        try:
            timeout = WeaveMediaConnection._finish_timeout_seconds
            if WeaveMediaConnection._skip_on_exit:
                return

            def _target() -> None:
                try:
                    self.conversation_manager.state.on_exit()
                except Exception:
                    logger.exception("Error in realtime on_exit handler")

            t = threading.Thread(
                target=_target, name="WeaveRealtimeOnExit", daemon=True
            )
            t.start()
            if isinstance(timeout, (int, float)) and timeout is not None:
                t.join(timeout=float(timeout))
        finally:
            try:
                self.conversation_manager._stop_worker_thread()
            except Exception:
                pass


class WeaveAiohttpWebsocketConnection:
    """Wrapper for aiohttp ClientWebSocketResponse to add Weave tracking."""

    _weave_initialized = True

    def __init__(self, original_ws: Any) -> None:
        self.original_ws = original_ws
        self.id = str(uuid.uuid4())
        self.conversation_manager = ConversationManager()
        self._exit_ran = False
        try:
            atexit.register(self._run_exit_handler_once)
        except Exception:
            pass

    async def send_str(self, data: str, *args: Any, **kwargs: Any) -> None:
        parsed_data = _try_json_load(data)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_data, dict) and (
            typed_message := create_user_message_from_dict(parsed_data)
        ):
            self.conversation_manager.process_event(typed_message)
        return await self.original_ws.send_str(data, *args, **kwargs)

    async def send_bytes(self, data: bytes, *args: Any, **kwargs: Any) -> None:
        parsed_data = _try_json_load(data)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_data, dict) and (
            typed_message := create_user_message_from_dict(parsed_data)
        ):
            self.conversation_manager.process_event(typed_message)
        return await self.original_ws.send_bytes(data, *args, **kwargs)

    async def send_json(self, data: Any, *args: Any, **kwargs: Any) -> None:
        # Forward outgoing user messages to conversation manager
        if isinstance(data, dict) and (
            typed_message := create_user_message_from_dict(data)
        ):
            self.conversation_manager.process_event(typed_message)
        return await self.original_ws.send_json(data, *args, **kwargs)

    async def receive(self, *args: Any, **kwargs: Any) -> Any:
        msg = await self.original_ws.receive(*args, **kwargs)
        if not (
            msg.type in (WSMsgType.TEXT, WSMsgType.BINARY) if WSMsgType else (1, 2)
        ):
            return msg
        # Forward outgoing user messages to conversation manager
        parsed_data = _try_json_load(msg.data)
        if isinstance(parsed_data, dict) and (
            typed_message := create_server_message_from_dict(parsed_data)
        ):
            self.conversation_manager.process_event(typed_message)
        return msg

    async def close(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await self.original_ws.close(*args, **kwargs)
        finally:
            self._run_exit_handler_once()

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        msg = await self.receive()
        if msg.type == WSMsgType.ERROR if WSMsgType else 258:
            raise StopAsyncIteration
        return msg

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager

    def __getattr__(self, name: str) -> Any:
        # Delegate all other attributes to the original websocket
        return getattr(self.original_ws, name)

    # ---- Exit handling ----
    def _run_exit_handler_once(self) -> None:
        if getattr(self, "_exit_ran", False):
            return
        self._exit_ran = True
        try:
            # Leverage the same class-level config as sync connection
            timeout = WeaveMediaConnection._finish_timeout_seconds
            if WeaveMediaConnection._skip_on_exit:
                return

            def _target() -> None:
                try:
                    self.conversation_manager.state.on_exit()
                except Exception:
                    logger.exception("Error in realtime on_exit handler")

            t = threading.Thread(
                target=_target, name="WeaveRealtimeOnExit", daemon=True
            )
            t.start()
            if isinstance(timeout, (int, float)) and timeout is not None:
                t.join(timeout=float(timeout))
        finally:
            try:
                self.conversation_manager._stop_worker_thread()
            except Exception:
                pass


# ---- Module-level configuration API called by the patcher ----
def configure_realtime_finish_timeout(value: float | None) -> None:
    try:
        WeaveMediaConnection._configure_finish_behavior(value)
    except Exception:
        # Best-effort; leave defaults
        logger.exception("Failed to set realtime finish timeout; keeping defaults")
