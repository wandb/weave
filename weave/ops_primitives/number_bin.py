import math

from ..api import op, use
from ..weave_types import Function, NumberBinType
from .. import weave_types as types
from .. import context
from .arrow import ArrowArrayVectorizer

import pyarrow as pa
from ..weave_internal import define_fn, call_fn, make_const_node


# TODO(DG): remove explicit checks for arrowArrayVectorizer in op resolver body.
@op(output_type=NumberBinType)
def _vectorized_bin_helper(start: float, stop: float):
    if isinstance(start, ArrowArrayVectorizer) and isinstance(
        stop, ArrowArrayVectorizer
    ):
        # TODO: this may not work if stop.arr or start.arr are pa.Tables
        return pa.chunked_array(
            pa.StructArray.from_arrays(
                list(map(lambda a: a.combine_chunks(), [start.arr, stop.arr])),
                ["start", "stop"],
            )
        )
    return {"start": start, "stop": stop}


# This is needed because it is not possible to resolve the type of row * mult at function definition time, and
# map_fn_to_arrow is not called on number_bins_fixed. TODO(DG): remove.
@op()
def _vectorized_floor(number: float) -> int:
    if isinstance(number, ArrowArrayVectorizer):
        return number.floor()
    return math.floor(number)


# TODO(DG): remove context.non_caching_execution_client(). We dont want op writers to have to know
# about caching. This should be removed when the arrow vectorization refactor goes in.
@op(
    input_type={"step": types.Number()},
    output_type=Function(
        input_types={"row": types.Number()},
        output_type=NumberBinType,  # type: ignore
    ),
)
def number_bins_fixed(step):
    def body(row):
        if step <= 0:
            raise ValueError("Step must be greater than zero.")
        mult = make_const_node(types.Number(), 1.0 / step)
        start_node = _vectorized_floor(row * mult) / mult
        return _vectorized_bin_helper(start=start_node, stop=start_node + step)

    # need to call use because define_fn returns a constNode
    # where the val is an outputNode
    with context.non_caching_execution_client():
        return use(define_fn({"row": types.Number()}, body))


# TODO(DG): remove context.non_caching_execution_client(). We dont want op writers to have to know
# about caching. This should be removed when the arrow vectorization refactor goes in.
@op(
    name="numbers-pybinsequal",
    input_type={"arr": types.List(types.Number()), "bins": types.Number()},
    output_type=Function(
        input_types={"row": types.Number()}, output_type=NumberBinType  # type: ignore
    ),
    render_info={"type": "function"},
)
def numbers_bins_equal(arr, bins):
    arr_min = min(arr) if len(arr) > 0 else 0
    arr_max = max(arr) if len(arr) > 0 else 0
    step = (arr_max - arr_min) / bins
    with context.non_caching_execution_client():
        return use(number_bins_fixed(step))


# TODO(DG): remove context.non_caching_execution_client(). We dont want op writers to have to know
# about caching. This should be removed when the arrow vectorization refactor goes in.
@op(
    name="number-pybin",
    input_type={
        "in_": types.Number(),
        "bin_fn": Function(
            input_types={"row": types.Number()}, output_type=NumberBinType  # type: ignore
        ),
    },
    output_type=NumberBinType,  # type: ignore
)
def number_bin(in_, bin_fn):
    with context.non_caching_execution_client():
        result = use(call_fn(bin_fn, {"row": make_const_node(types.Number(), in_)}))
    return result
