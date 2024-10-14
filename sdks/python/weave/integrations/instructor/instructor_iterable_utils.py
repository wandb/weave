from functools import wraps
from typing import Any, Callable, Optional

from pydantic import BaseModel

import weave
from weave.trace.op_extensions.accumulator import add_accumulator


def instructor_iterable_accumulator(
    acc: Optional[BaseModel], value: BaseModel
) -> list[BaseModel]:
    if acc is None:
        acc = [value]
    if acc[-1] != value:
        acc.append(value)
    return acc


def should_accumulate_iterable(inputs: dict) -> bool:
    if isinstance(inputs, dict):
        if "stream" in inputs:
            return inputs["stream"]
        elif "kwargs" in inputs:
            if "stream" in inputs["kwargs"]:
                return inputs.get("kwargs", {}).get("stream")
    return False


def instructor_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_iterable_accumulator,
            should_accumulate=should_accumulate_iterable,
        )

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
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_iterable_accumulator,
            should_accumulate=should_accumulate_iterable,
        )

    return wrapper
