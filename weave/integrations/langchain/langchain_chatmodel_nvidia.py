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


langchain_chatmodel_nvidia_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("langchain.Llm"),
            "ChatNVIDIA.invoke",
            create_wrapper_sync(name="langchain.Llm.ChatNVIDIA.invoke"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("langchain.Llm"),
            "ChatNVIDIA.invoke",
            create_wrapper_async(name="langchain.Llm.ChatNVIDIA.invoke"),
        ),
    ]
)
