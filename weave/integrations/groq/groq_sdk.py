import importlib
from typing import Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def groq_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


groq_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("groq.resources.chat.completions"),
            "Completions.create",
            groq_wrapper(name="groq.resources.chat.completions.Completions.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("groq.resources.chat.completions"),
            "AsyncCompletions.create",
            groq_wrapper(
                name="groq.resources.chat.completions.AsyncCompletions.create"
            ),
        ),
    ]
)
