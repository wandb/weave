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


langchain_chatmodel_nvidia_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._generate",
            create_wrapper_sync(name="langchain_nvidia_ai_endpoints.ChatNVIDIA.invoke"),
        )
    ]
)
