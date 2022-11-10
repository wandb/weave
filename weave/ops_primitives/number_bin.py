import math

from ..api import op, use
from ..weave_types import Function, NumberBinType
from .. import weave_types as types
from .. import context
from .dict import dict_

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
