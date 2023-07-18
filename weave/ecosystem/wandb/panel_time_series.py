import dataclasses
import typing

import weave
from weave import weave_internal

from . import weave_plotly
from ...language_features.tagging import tagged_value_type

TIME_SERIES_BIN_SIZES_SEC = [
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

TIME_SERIES_BIN_SIZES_SEC_NODE = weave_internal.make_const_node(
    weave.types.List(weave.types.Number()), TIME_SERIES_BIN_SIZES_SEC
)

N_BINS = 50  # number of bins to show in plot

mark_py_type = typing.Union[
    typing.Literal["line"], typing.Literal["bar"], typing.Literal["point"]
]

mark_weave_type = weave.types.UnionType(
    weave.types.Const(weave.types.String(), "line"),
    weave.types.Const(weave.types.String(), "bar"),
    weave.types.Const(weave.types.String(), "point"),
)


@weave.type()
class TimeSeriesConfig:
    x: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    agg: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    min_x: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    max_x: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    label: weave.Node[
        typing.Optional[typing.Union[str, weave.types.InvalidPy]]
    ] = dataclasses.field(default_factory=lambda: weave.graph.VoidNode())
    mark: weave.Node[str] = dataclasses.field(
        default_factory=lambda: weave.graph.ConstNode(weave.types.String(), "bar")
    )
    axis_labels: weave.Node[dict[str, str]] = dataclasses.field(
        default_factory=lambda: weave.graph.ConstNode(
            weave.types.Dict(weave.types.String(), weave.types.String()),
            {},
        )
    )


def first_column_of_type(
    node_type: weave.types.Type,
    desired_type: weave.types.Type,
) -> typing.Tuple[weave.graph.ConstNode, weave.graph.ConstNode]:
    if isinstance(node_type, tagged_value_type.TaggedValueType):
        node_type = node_type.value
    if weave.types.List().assign_type(node_type):
        node_type = typing.cast(weave.types.List, node_type)
        object_type = node_type.object_type
        if desired_type.assign_type(object_type):
            return weave.define_fn(
                {"input_node": node_type}, lambda item: item
            ), weave.define_fn({"item": object_type}, lambda item: item)
        elif weave.types.TypedDict().assign_type(object_type):
            object_type = typing.cast(weave.types.TypedDict, object_type)
            _, non_none_desired = weave.types.split_none(desired_type)
            if (
                isinstance(non_none_desired, weave.types.Timestamp)
                and "_timestamp" in object_type.property_types
            ):
                return (
                    weave.define_fn(
                        {"input_node": node_type},
                        lambda item: (item["_timestamp"] * 1000).toTimestamp(),
                    ),
                    weave.define_fn(
                        {"item": object_type},
                        lambda item: (item["_timestamp"] * 1000).toTimestamp(),
                    ),
                )
            for key in object_type.property_types:
                value_type = object_type.property_types[key]
                if desired_type.assign_type(value_type):
                    return weave.define_fn(
                        {"input_node": node_type}, lambda item: item[key]
                    ), weave.define_fn({"item": object_type}, lambda item: item[key])
        # return weave.define_fn(
        #     {"input_node": node_type}, weave.graph.VoidNode()
        # ), weave.define_fn({"item": object_type}, lambda _: weave.graph.VoidNode())
    raise ValueError(
        f"Can't extract column with type {desired_type} from node of type {node_type}"
    )


@weave.op(
    input_type={
        "fn": weave.types.Function(
            {
                "item": weave.types.Any(),
            },
            weave.types.Any(),
        )
    }
)
def function_to_string(fn) -> str:
    ret = str(fn)
    if fn.val.from_op.name.endswith("pick"):
        ret = str(fn.val.from_op.inputs["key"])
    elif fn.val.from_op.name.endswith("__getattr__"):
        ret = str(fn.val.from_op.inputs["attr"])
    ret = ret.strip('"')
    return ret


# The render op. This renders the panel.


# The interface for constructing this Panel from Python
@weave.type()
class TimeSeries(weave.Panel):
    id = "TimeSeries"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[TimeSeriesConfig] = None

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config

        unnested = weave.ops.unnest(input_node)

        # TODO: add the ability to configure options here
        if self.config is None:
            self.config = TimeSeriesConfig()
            for attr in ["x", "min_x", "max_x", "label", "mark", "agg", "axis_labels"]:
                if attr in options:
                    value = options[attr]
                    if not isinstance(value, weave.graph.Node):
                        if attr in ["min_x", "max_x", "mark", "axis_labels"]:
                            value = weave.make_node(value)
                        if attr in ["min_x", "max_x"]:
                            value = weave_internal.const(value)
                            # value = weave.make_node(value)
                        elif attr in ["x", "label"]:
                            value = weave.define_fn(
                                {"item": unnested.type.object_type}, value
                            )
                        elif attr in ["agg"]:
                            value = weave.define_fn(
                                {"group": weave.types.List(unnested.type.object_type)},
                                value,
                            )
                else:
                    value = weave.define_fn(
                        {"item": unnested.type.object_type},
                        lambda item: weave.graph.VoidNode(),
                    )
                setattr(self.config, attr, value)

    @weave.op()
    def initialize(self) -> TimeSeriesConfig:
        input_node = self.input_node
        # TODO: unnested_table should be Node, that way we don't evaluate it just
        # to figure it outs type here.
        # TODO: we need input variables (frame) available here. For now we have
        # manually construct them :(
        col_fn, item_fn = first_column_of_type(
            input_node.type, weave.types.optional(weave.types.Timestamp())
        )

        min_x_called = col_fn(input_node).min()  # type: ignore
        min_x = weave_internal.const(
            min_x_called,
            weave.types.Function(col_fn.type.input_types, min_x_called.type),  # type: ignore
        )

        max_x_called = col_fn(input_node).max()  # type: ignore
        max_x = weave_internal.const(
            max_x_called,
            weave.types.Function(col_fn.type.input_types, max_x_called.type),  # type: ignore
        )

        mark = weave_internal.const("bar")

        config = TimeSeriesConfig(
            x=item_fn,
            label=first_column_of_type(
                input_node.type,
                weave.types.optional(
                    weave.types.union(
                        weave.types.String(),
                        weave.types.Boolean(),
                    )
                ),
            )[1],
            agg=weave_internal.define_fn(
                {"group": input_node.type},  # type: ignore
                lambda group: group.count(),
            ),
            min_x=min_x,
            max_x=max_x,
            mark=mark,
        )

        return config

    # The config render op. This renders the config editor.
    @weave.op()
    def render_config(self) -> weave.panels.Group:
        input_node = self.input_node
        config = typing.cast(TimeSeriesConfig, self.config)
        return weave.panels.Group(
            items={
                "x": weave.panels.LabeledItem(
                    label="x", item=weave.panels.FunctionEditor(config.x)
                ),
                "label": weave.panels.LabeledItem(
                    label="label", item=weave.panels.FunctionEditor(config.label)
                ),
                "min_x": weave.panels.LabeledItem(
                    label="min_x", item=weave.panels.FunctionEditor(config.min_x)
                ),
                "max_x": weave.panels.LabeledItem(
                    label="max_x", item=weave.panels.FunctionEditor(config.max_x)
                ),
                "agg": weave.panels.LabeledItem(
                    label="agg", item=weave.panels.FunctionEditor(config.agg)
                ),
                "mark": weave.panels.LabeledItem(
                    label="mark",
                    item=weave.panels.ObjectPicker(
                        weave_internal.make_const_node(
                            weave.types.List(weave.types.String()),
                            [
                                "bar",
                                "line",
                                "point",
                            ],
                        ),
                        config=weave.panels.ObjectPickerConfig(choice=config.mark),
                    ),
                ),
            }
        )

    @weave.op()
    def render(self) -> weave_plotly.PanelPlotly:
        input_node = self.input_node
        config = typing.cast(TimeSeriesConfig, self.config)
        # NOTE: everything inside this function is operating on nodes. There are no concrete values in here.
        # We are just constructing a graph here. It will be executed later on.

        unnested = input_node.unnest()  # type: ignore

        min_x = config.min_x
        max_x = config.max_x

        if not weave.types.optional(weave.types.Timestamp()).assign_type(
            min_x.type
        ) or not weave.types.optional(weave.types.Timestamp()).assign_type(max_x.type):
            return weave.panels.PanelHtml(weave.ops.Html("No data"))  # type: ignore

        exact_bin_size = ((max_x - min_x) / N_BINS).totalSeconds()  # type: ignore
        bin_size_index = TIME_SERIES_BIN_SIZES_SEC_NODE.map(  # type: ignore
            lambda x: (
                (x - exact_bin_size).abs()
                / weave.ops.make_list(a=x, b=exact_bin_size).min()
            )
            # lambda x: (x / exact_bin_size - 1).abs() # original
        ).argmin()

        bin_size = TIME_SERIES_BIN_SIZES_SEC_NODE[bin_size_index]  # type: ignore
        bin_size_s = bin_size

        def bin_fn(item):
            label_fn_output_type = config.label.type.output_type
            group_items = {}

            # convert timestamp to seconds
            timestamp = config.x(item)

            bin_start_ms = timestamp.floor(bin_size_s)
            bin_end_ms = timestamp.ceil(bin_size_s)

            bin_start = bin_start_ms
            bin_end = bin_end_ms

            group_items["bin"] = weave.ops.dict_(start=bin_start, stop=bin_end)

            if label_fn_output_type == weave.types.Invalid():
                group_items["label"] = "no_label"
            else:
                group_items["label"] = config.label(item)

            return weave.ops.dict_(**group_items)

        binned = (
            unnested.filter(
                lambda item: weave.ops.Boolean.bool_and(
                    config.x(item) <= max_x, config.x(item) >= min_x  # type: ignore
                )
            )
            .groupby(lambda item: bin_fn(item))
            .map(
                lambda group: weave.ops.dict_(
                    x=group.groupkey()["bin"],
                    label=group.groupkey()["label"],
                    y=config.agg(group),  # type: ignore
                )
            )
            # this is needed because otherwise the lines look like a scrambled mess
            .sort(lambda item: weave.ops.make_list(a=item["x"]["start"]), ["asc"])
        )

        default_labels = weave.ops.dict_(
            # x=function_to_string(config.x),
            # y=function_to_string(config.agg),
            # label=function_to_string(config.label),
            x="x",
            y="y",
            label="label",
        )

        fig = weave_plotly.plotly_time_series(
            binned, config.mark, default_labels, config.axis_labels
        )
        return weave_plotly.PanelPlotly(fig)
