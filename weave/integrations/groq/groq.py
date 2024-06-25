import importlib
from typing import TYPE_CHECKING, Callable, Dict, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from groq.resources.chat.completions import Completions


def groq_accumulator(
    acc: Optional["Completions"], value: "Completions"
) -> "Completions":
    if acc is None:
        acc = value
    return value


def should_use_accumulator(inputs: Dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def groq_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            groq_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


groq_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("groq.resources.chat.completions"),
            "Completions.create",
            groq_wrapper(name="groq.resources.chat.completions.Completions.create"),
        )
    ]
)
