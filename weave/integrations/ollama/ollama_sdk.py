from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import wraps
from typing import Any

import weave
from weave.integrations.integration_metadata import (
    library_integration,
    with_integration_metadata,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_ollama_patcher: MultiPatcher | None = None
OLLAMA_INTEGRATION = library_integration("ollama", distribution_name="ollama")


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def create_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        return op

    return wrapper


def get_ollama_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _ollama_patcher  # noqa: PLW0603
    if _ollama_patcher is not None:
        return _ollama_patcher

    base = with_integration_metadata(settings.op_settings, OLLAMA_INTEGRATION)

    chat_settings = base.model_copy(
        update={
            "name": base.name or "ollama.chat",
            "kind": base.kind or "llm",
        }
    )

    # ``ollama.Client.chat`` / ``AsyncClient.chat`` cover explicit client usage.
    # The module-level ``ollama.chat`` helper is bound to a shared client at
    # import time, so it captured the unpatched method — patch it separately so
    # the common ``import ollama; ollama.chat(...)`` path is traced too. The three
    # symbols do not overlap on a single call, so no call is double-counted.
    _ollama_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("ollama._client"),
                "Client.chat",
                create_wrapper_sync(chat_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("ollama._client"),
                "AsyncClient.chat",
                create_wrapper_async(chat_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("ollama"),
                "chat",
                create_wrapper_sync(chat_settings),
            ),
        ]
    )

    return _ollama_patcher
