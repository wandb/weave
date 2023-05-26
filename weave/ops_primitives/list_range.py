# In its own file to avoid

from ..api import op

py_range = range


@op(name="range")
def range(start: int, stop: int, step: int) -> list[int]:
    return list(py_range(start, stop, step))
