# In its own file to avoid

import pyarrow as pa

from weave import weave_types as types
from weave.api import op
from weave.legacy.arrow.list_ import ArrowWeaveList

py_range = range


@op(name="range")
def range(start: int, stop: int, step: int) -> ArrowWeaveList[int]:
    return ArrowWeaveList(pa.array(py_range(start, stop, step)), types.Int())
