from ..api import op, use
from ..weave_types import Function
from .. import weave_types as types
from ..ops_primitives import Number
from .. import storage
from .arrow import ArrowArrayVectorizer

import pyarrow as pa
from ..weave_internal import define_fn, call_fn, make_const_node


NumberBinType = types.TypedDict({"start": types.Float(), "stop": types.Float()})


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
        start_node = Number.floor(row * mult) / mult
        return _vectorized_bin_helper(start=start_node, stop=start_node + step)

    # need to call use because define_fn returns a constNode
    # where the val is an outputNode
    return use(define_fn({"row": types.Number()}, body))


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
    return use(number_bins_fixed(step))


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
    storage.save(in_)
    result = use(call_fn(bin_fn, {"row": make_const_node(types.Number(), in_)}))
    return result
