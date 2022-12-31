import copy
import typing

import contextvars
import contextlib

from . import graph

# TODO: make a nicer data structure that has pointers to who provided what

_frame: contextvars.ContextVar[dict[str, graph.Node]] = contextvars.ContextVar(
    "loading_op_location", default={}
)


@contextlib.contextmanager
def scope_vars(vars: dict[str, graph.Node]) -> typing.Generator[None, None, None]:
    new_frame = copy.copy(_frame.get())
    new_frame.update(vars)
    token = _frame.set(new_frame)
    try:
        yield
    finally:
        _frame.reset(token)


def get_frame() -> dict[str, graph.Node]:
    return _frame.get()
