import importlib
from typing import Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def instructor_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


instructor_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "Instructor.create",
            instructor_wrapper(name="Instructor.create"),
        ),
    ]
)
