import importlib
from functools import wraps
from typing import Any, Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def instructor_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def instructor_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        "We need to do this so we can check if `stream` is used"
        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


instructor_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "Instructor.create",
            instructor_wrapper_sync(name="Instructor.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("instructor.client"),
            "AsyncInstructor.create",
            instructor_wrapper_async(name="AsyncInstructor.create"),
        ),
    ]
)
