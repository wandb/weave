import importlib
from functools import wraps
from typing import Any, Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def create_wrapper_sync(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def create_wrapper_async(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


cerebras_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
            "CompletionsResource.create",
            create_wrapper_sync(name="cerebras.chat.completions.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
            "AsyncCompletionsResource.create",
            create_wrapper_async(name="cerebras.chat.completions.create"),
        ),
    ]
)
