from typing import Callable, Optional

from pydantic import BaseModel

import weave
from weave.trace.op_extensions.accumulator import add_accumulator


def instructor_partial_accumulator(
    acc: Optional[BaseModel], value: BaseModel
) -> BaseModel:
    if acc is None or acc != value:
        acc = value
    return acc


def instructor_wrapper_partial(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_partial_accumulator,
            should_accumulate=lambda inputs: True,
        )

    return wrapper
