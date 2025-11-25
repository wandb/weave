from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import wraps
from typing import Any

from weave.integrations.openai_realtime import connection
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace import autopatch

_openai_realtime_patcher: MultiPatcher | None = None


def websocket_wrapper(original_class: Any) -> Callable:
    @wraps(original_class)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Add original_websocket_app to kwargs
        kwargs["original_websocket_app"] = original_class
        return connection.WeaveMediaConnection(*args, **kwargs)

    return wrapper


def get_openai_realtime_patcher(
    settings: autopatch.IntegrationSettings | None = None,
) -> MultiPatcher:
    global _openai_realtime_patcher

    if _openai_realtime_patcher is not None:
        return _openai_realtime_patcher

    if settings is None:
        settings = autopatch.IntegrationSettings()

    base = NoOpPatcher()

    if not settings.enabled:
        _openai_realtime_patcher = MultiPatcher([base])
        return _openai_realtime_patcher

    websocket_app_patcher = SymbolPatcher(
        lambda: importlib.import_module("websocket"),
        "WebSocketApp",
        lambda original: websocket_wrapper(original),
    )

    _openai_realtime_patcher = MultiPatcher([base, websocket_app_patcher])
    return _openai_realtime_patcher
