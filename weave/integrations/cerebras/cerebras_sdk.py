import dataclasses
import importlib
from functools import wraps
from typing import Any, Callable, Optional

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, SymbolPatcher

_cerebras_patcher: Optional[MultiPatcher] = None


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = dataclasses.asdict(settings)
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

        op_kwargs = dataclasses.asdict(settings)
        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        return op

    return wrapper


def get_cerebras_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> MultiPatcher:
    global _cerebras_patcher

    if _cerebras_patcher is not None:
        return _cerebras_patcher

    if settings is None:
        settings = IntegrationSettings()

    base = settings.op_settings

    create_settings = dataclasses.replace(
        base,
        name="cerebras.chat.completions.create",
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
