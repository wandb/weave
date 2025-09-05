# OpenAI Realtime API integration for Weave
# This module automatically patches websocket connections to track sessions and conversations

from weave.integrations.openai_realtime.openai_realtime_sdk import (
    OpenAIRealtimeSettings,
    wrap_websocket_async,
    wrap_websocket_connect,
    wrap_websocket_sync,
)

__all__ = [
    "OpenAIRealtimeSettings",
    "wrap_websocket_async",
    "wrap_websocket_connect",
    "wrap_websocket_sync",
]
