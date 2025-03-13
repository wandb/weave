from typing import Callable, Optional

from pydantic import BaseModel

import weave
from weave.trace.autopatch import OpSettings
from weave.trace.op import _add_accumulator


def instructor_partial_accumulator(
    acc: Optional[BaseModel], value: BaseModel
) -> BaseModel:
    if acc is None or acc != value:
        acc = value
    return acc


def instructor_wrapper_partial(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: instructor_partial_accumulator,
            should_accumulate=lambda inputs: True,
        )

    return wrapper
