# In its own file to avoid

import pyarrow as pa

from weave_query import weave_types as types
from weave_query.api import op
from weave_query.arrow.list_ import ArrowWeaveList

py_range = range


@op(name="range")
def range(start: int, stop: int, step: int) -> ArrowWeaveList[int]:
    return ArrowWeaveList(pa.array(py_range(start, stop, step)), types.Int())
