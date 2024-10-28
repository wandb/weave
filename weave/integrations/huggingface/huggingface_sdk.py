import importlib
from typing import Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def huggingface_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name
        return op

    return wrapper


huggingface_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("huggingface_hub"),
            "InferenceClient.chat_completion",
            huggingface_wrapper_sync(
                name="huggingface_hub.InferenceClient.chat_completion"
            ),
        ),
    ]
)
