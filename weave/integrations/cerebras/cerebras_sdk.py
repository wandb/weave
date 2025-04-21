from __future__ import annotations

import importlib
from functools import wraps
from typing import Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_cerebras_patcher: MultiPatcher | None = None


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


def get_cerebras_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _cerebras_patcher
    if _cerebras_patcher is not None:
        return _cerebras_patcher

    base = settings.op_settings

    create_settings = base.model_copy(
        update={"name": base.name or "cerebras.chat.completions.create"}
    )

    _cerebras_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
                "CompletionsResource.create",
                create_wrapper_sync(create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
                "AsyncCompletionsResource.create",
                create_wrapper_async(create_settings),
            ),
        ]
    )

    return _cerebras_patcher
