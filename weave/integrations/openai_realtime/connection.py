import json
import uuid
from typing import Any

import websocket
from weave.integrations.openai_realtime.conversation_manager import ConversationManager

# Use project-local modules (no package-relative imports here)
from weave.integrations.openai_realtime.models import (
    create_server_message_from_dict,
    create_user_message_from_dict,
)

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

    def _wrap_sender(self, sender: Any) -> Any:
        def wrapper(data: Any, opcode: int = websocket.ABNF.OPCODE_TEXT) -> Any:
            # Process outgoing events with session manager
            parsed_data = _try_json_load(data)
            if isinstance(parsed_data, dict):
                # Convert to typed user message and forward to conversation manager
                try:
                    typed_message = create_user_message_from_dict(parsed_data)
                    self.conversation_manager.process_event(typed_message)
                except Exception:
                    # If parsing fails, ignore for state tracking but still forward on the wire
                    pass
            return sender(data, opcode)

        return wrapper

    def _wrap_handler(self, name: str, handler: Any) -> Any:
        if handler is None:
            return None

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # The first argument is always the websocket instance, so we skip it
            return handler(*args, **kwargs)

        return wrapper

    def _wrap_handler_with_session(self, name: str, handler: Any) -> Any:
        if handler is None:
            return None

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Process incoming message events with session manager
            if len(args) > 1:  # Message is the second argument
                message = args[1]
                parsed_message = _try_json_load(message)
                if isinstance(parsed_message, dict):
                    # Convert to typed server message and forward to conversation manager
                    try:
                        typed_message = create_server_message_from_dict(
                            parsed_message
                        )
                        self.conversation_manager.process_event(typed_message)
                    except Exception:
                        # If parsing fails, ignore for state tracking but still forward to handler
                        pass
            # Call the original handler
            return handler(*args, **kwargs)

        return wrapper

    def send(self, data: Any, opcode: int = websocket.ABNF.OPCODE_TEXT) -> Any:
        self.ws.send(data, opcode)

    def run_forever(self, **kwargs: Any) -> Any:
        self.ws.run_forever(**kwargs)

    def close(self, **kwargs: Any) -> Any:
        self.ws.close(**kwargs)

    def get_session(self) -> Any:
        """Convenience: return the current Session state from the conversation manager."""
        return self.conversation_manager.state.session

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager


class WebSocketApp(WeaveMediaConnection):
    pass


class WeaveAsyncWebsocketConnection:
    _weave_initialized = True

    def __init__(self, original_connection: Any):
        self.original_connection = original_connection
        self.id = str(uuid.uuid4())
        self.conversation_manager = ConversationManager()

    async def send(self, *args: Any, **kwargs: Any) -> None:
        message = args[0] if args else None
        parsed_message = _try_json_load(message)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_message, dict):
            try:
                typed_message = create_user_message_from_dict(parsed_message)
                self.conversation_manager.process_event(typed_message)
            except Exception:
                pass
        return await self.original_connection.send(*args, **kwargs)

    async def recv(self, *args: Any, **kwargs: Any) -> Any:
        message = await self.original_connection.recv(*args, **kwargs)
        parsed_message = _try_json_load(message)
        # Forward incoming server messages to conversation manager
        if isinstance(parsed_message, dict):
            try:
                typed_message = create_server_message_from_dict(parsed_message)
                self.conversation_manager.process_event(typed_message)
            except Exception:
                pass
        return message

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        try:
            return await self.recv()
        except self.original_connection.ConnectionClosed:
            raise StopAsyncIteration from None

    def get_session(self) -> Any:
        return self.conversation_manager.state.session

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager

    def __getattr__(self, name: str) -> Any:
        if name == "send":
            return self.send
        if name == "recv":
            return self.recv
        if name == "get_session":
            return self.get_session
        if name == "get_conversation_manager":
            return self.get_conversation_manager
        return getattr(self.original_connection, name)


class WeaveAiohttpWebsocketConnection:
    """Wrapper for aiohttp ClientWebSocketResponse to add Weave tracking."""

    _weave_initialized = True

    def __init__(self, original_ws: Any) -> None:
        self.original_ws = original_ws
        self.id = str(uuid.uuid4())
        self.conversation_manager = ConversationManager()

    async def send_str(self, data: str, *args: Any, **kwargs: Any) -> None:
        parsed_data = _try_json_load(data)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_data, dict):
            try:
                typed_message = create_user_message_from_dict(parsed_data)
                self.conversation_manager.process_event(typed_message)
            except Exception:
                pass
        return await self.original_ws.send_str(data, *args, **kwargs)

    async def send_bytes(self, data: bytes, *args: Any, **kwargs: Any) -> None:
        parsed_data = _try_json_load(data)
        # Forward outgoing user messages to conversation manager
        if isinstance(parsed_data, dict):
            try:
                typed_message = create_user_message_from_dict(parsed_data)
                self.conversation_manager.process_event(typed_message)
            except Exception:
                pass
        return await self.original_ws.send_bytes(data, *args, **kwargs)

    async def send_json(self, data: Any, *args: Any, **kwargs: Any) -> None:
        # Forward outgoing user messages to conversation manager
        if isinstance(data, dict):
            try:
                typed_message = create_user_message_from_dict(data)
                self.conversation_manager.process_event(typed_message)
            except Exception:
                pass
            return await self.original_ws.send_json(data, *args, **kwargs)

    async def receive(self, *args: Any, **kwargs: Any) -> Any:
        msg = await self.original_ws.receive(*args, **kwargs)
        if msg.type in (WSMsgType.TEXT, WSMsgType.BINARY) if WSMsgType else (1, 2):
            parsed_data = _try_json_load(msg.data)
            # Forward incoming server messages to conversation manager
            if isinstance(parsed_data, dict):
                try:
                    typed_message = create_server_message_from_dict(parsed_data)
                    self.conversation_manager.process_event(typed_message)
                except Exception:
                    pass
                return msg
        return msg

    async def close(self, *args: Any, **kwargs: Any) -> Any:
        return await self.original_ws.close(*args, **kwargs)

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        msg = await self.receive()
        if msg.type == WSMsgType.ERROR if WSMsgType else 258:
            raise StopAsyncIteration
        return msg

    def get_session(self) -> Any:
        return self.conversation_manager.state.session

    def get_conversation_manager(self) -> ConversationManager:
        return self.conversation_manager

    def __getattr__(self, name: str) -> Any:
        # Delegate all other attributes to the original websocket
        return getattr(self.original_ws, name)
