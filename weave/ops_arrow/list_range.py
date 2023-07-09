# In its own file to avoid

import pyarrow as pa

from ..api import op
from .. import weave_types as types

from .list_ import ArrowWeaveList

py_range = range


@op(name="range")
def range(start: int, stop: int, step: int) -> ArrowWeaveList[int]:
    return ArrowWeaveList(pa.array(py_range(start, stop, step)), types.Int())
