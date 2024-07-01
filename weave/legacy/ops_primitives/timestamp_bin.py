from weave import weave_internal
from weave import weave_types as types
from weave.api import op, use
from weave.legacy import graph
from weave.legacy.ops_primitives.dict import dict_
from weave.weave_internal import call_fn, define_fn, make_const_node
from weave.weave_types import Function, TimestampBinType

NICE_BIN_SIZES_SEC = [
    # TODO: will need more steps along here for smooth zooming.
    1e-9,  # ns
    1e-6,  # microsec
    1e-3,  # ms
    1,
    2.5,
    5,
    10,
    15,
    30,
    60,  # 1min
    300,  # 5min
    600,  # 10min
    1200,  # 20min
    1800,  # 30 min
    *(3600 * i for i in range(1, 25)),  # 1 - 24 hr, increments of 1hr
    *(86400 * i for i in range(2, 31)),  # 2 - 30 days, increments of 1 day
    *(
        86400 * 30 * i for i in range(2, 13)
    ),  # 2 - 12 months (assuming 1 month = 30days) increments of 1 month
    *(
        365 * 86400 * i for i in range(1, 11)
    ),  # 1 - 10 years (assuming 1 year = 365 days) increments of 1 year
]

NICE_BIN_SIZES_SEC_NODE = weave_internal.make_const_node(
    types.List(types.Number()), NICE_BIN_SIZES_SEC
)


@op(
    output_type=Function(
        input_types={"ts": types.Timestamp()},
        output_type=TimestampBinType,  # type: ignore
    ),
)
def timestamp_bins_fixed(bin_size_s: float):
    def body(ts):
        if bin_size_s <= 0:
            raise ValueError("bin_size_s must be greater than zero.")
        return dict_(start=ts.floor(bin_size_s), stop=ts.ceil(bin_size_s))

    # this should be vectorized by expansion
    return define_fn({"ts": types.Timestamp()}, body)


@op(
    name="timestamps-binsnice",
    input_type={
        "arr": types.List(types.optional(types.Timestamp())),
        "target_n_bins": types.Number(),
    },
    output_type=Function(
        input_types={"ts": types.Timestamp()}, output_type=TimestampBinType  # type: ignore
    ),
    render_info={"type": "function"},
)
def timestamp_bins_nice(arr, target_n_bins):
    arr_min = min(arr) if len(arr) > 0 else 0
    arr_max = max(arr) if len(arr) > 0 else 0
    exact_bin_size = ((arr_max - arr_min) / target_n_bins).total_seconds()  # type: ignore
    bin_size_s = (
        min(NICE_BIN_SIZES_SEC, key=lambda x: abs(x / exact_bin_size - 1))
        if exact_bin_size != 0
        else 1
    )
    return use(timestamp_bins_fixed(bin_size_s))


@op(
    name="timestamp-bin",
    input_type={
        "in_": types.Timestamp(),
        "bin_fn": types.optional(
            Function(
                input_types={"row": types.Timestamp()}, output_type=TimestampBinType  # type: ignore
            )
        ),
    },
    output_type=TimestampBinType,  # type: ignore
)
def timestamp_bin(in_, bin_fn):
    if not isinstance(bin_fn, graph.Node) and bin_fn == None:
        return None
    return use(call_fn(bin_fn.val, {"ts": make_const_node(types.Timestamp(), in_)}))
