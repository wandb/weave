import importlib
from typing import Callable, Optional, TYPE_CHECKING

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


def groq_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            groq_accumulator,
            should_accumulate=lambda _: True,
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
