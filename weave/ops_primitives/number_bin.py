import math

from ..api import op, use
from ..weave_types import Function, NumberBinType
from .. import weave_types as types
from .. import graph
from .dict import dict_
from . import date

from ..weave_internal import define_fn, call_fn, make_const_node


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
        start_node = (row * mult).floor() / mult
        return dict_(start=start_node, stop=start_node + step)

    # this should be vectorized by expansion
    return define_fn({"row": types.Number()}, body).val


@op(
    name="numbers-binsequal",
    input_type={
        "arr": types.List(types.optional(types.Number())),
        "bins": types.Number(),
    },
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
    name="number-bin",
    input_type={
        "in_": types.Number(),
        "bin_fn": types.optional(
            Function(
                input_types={"row": types.Number()}, output_type=NumberBinType  # type: ignore
            )
        ),
    },
    output_type=NumberBinType,  # type: ignore
)
def number_bin(in_, bin_fn):
    if not isinstance(bin_fn, graph.Node) and bin_fn == None:
        return None
    return use(call_fn(bin_fn, {"row": make_const_node(types.Number(), in_)}))
