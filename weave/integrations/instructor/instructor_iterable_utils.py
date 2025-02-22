from typing import Callable, Optional

from pydantic import BaseModel

import weave
from weave.trace.autopatch import OpSettings
from weave.trace.op_extensions.accumulator import add_accumulator


def instructor_iterable_accumulator(
    acc: Optional[list[BaseModel]], value: BaseModel
) -> list[BaseModel]:
    if acc is None:
        return [value]
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


def instructor_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_iterable_accumulator,
            should_accumulate=should_accumulate_iterable,
        )

    return wrapper


def instructor_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_iterable_accumulator,
            should_accumulate=should_accumulate_iterable,
        )

    return wrapper
