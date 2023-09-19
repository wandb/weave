# Notes of stuff to do:
# - Add filter controls
# - Make groupby a dropdown
# - Better categorical detection. Currently we can't tell if something is a unique
#   string column or categorical. There are three options I see:
#   - put this information in the type system
#   - fully weavify the Render body here so it can switch based on the result of .execute
#     (execute a grouping operation on the input node to get summary stats, then switch
#     behavior based on the result, or make a summary_stats op and do the same).
#   - allow panel render bodies to call use. The problem here is we don't want rendering
#     to incur round-trips. Maybe its already ok since we only recall python panel
#     renders when the input node or type changes, but no other time.
#   - There might be a more appealing edge based alternative... like if we could use
#     .initialize to do the summary, and stick that information in the panel's config?
#     that might work!
# - Multiple segments (allow defining multiple segment filters, concat tables together
#   including segment name, and then groupby segment name)
# - An earlier version of this used section layout instead of grid, and used ChildPanel
#   vars instead of VarBar, and it looked really nice in a notebook. We can make it
#   so you can switch between configurable panel (that can be added into an existing
#   Board), v whole new board layout. The information is the same in both cases, we
#   just use different UI structures to render.


import os
import typing

import weave
from .. import weave_internal
from ..panels import panel_plot

from .generator_templates import template_registry


@weave.type()
class AutoBoardConfig:
    pass


# Was putting in these midpoint functions, but date-add and some other
# date functions don't have arrow equivalents yet, so these don't vectorize
# @weave.op(
#     weavify=True,
#     name="numberbin-midpoint",
#     input_type={"bin": weave.types.NumberBinType},
# )
# def number_bin_midpoint(bin) -> float:
#     return (bin["start"] + bin["stop"]) / 2


# @weave.op(
#     weavify=True,
#     name="timestampbin-midpoint",
#     input_type={"bin": weave.types.TimestampBinType},
# )
# def timestamp_bin_midpoint(bin) -> float:
#     return bin["start"].add((bin["stop"].sub(bin["start"])).div(2))


def timeseries(
    input_node: weave.Node[list[typing.Any]],
    bin_domain_node: weave.Node,
    x_axis_key: str,
    y_expr: typing.Callable,
    y_title: str,
    color_expr: typing.Callable,
    color_title: str,
    x_domain: weave.Node,
    n_bins: int,
    mark: panel_plot.MarkOption = "line",
) -> weave.Panel:
    x_axis_type = input_node[x_axis_key].type.object_type  # type: ignore
    if weave.types.optional(weave.types.Timestamp()).assign_type(x_axis_type):
        x_title = ""
        bin_fn = weave.ops.timestamp_bins_nice
    elif weave.types.optional(weave.types.Number()).assign_type(x_axis_type):
        x_title = x_axis_key
        bin_fn = weave.ops.numbers_bins_equal
    else:
        raise ValueError(f"Unsupported type for x_axis_key {x_axis_key}: {x_axis_type}")
    if mark == "bar":
        x = lambda row: row[x_axis_key].bin(bin_fn(bin_domain_node, n_bins))
    else:
        # TODO: should be midpoint
        x = lambda row: row[x_axis_key].bin(bin_fn(bin_domain_node, n_bins))["start"]

    return weave.panels.Plot(
        input_node,
        x=x,
        x_title=x_title,
        y=y_expr,
        y_title=y_title,
        label=color_expr,
        color_title=color_title,
        groupby_dims=["x", "label"],
        mark=mark,
        domain_x=x_domain,
    )


def timeseries_avg_line(
    input_node: weave.Node[list[typing.Any]],
    bin_domain_node: weave.Node,
    x_axis_key: str,
    y_axis_key: str,
    groupby_key: typing.Union[weave.Node[str], str],
    x_domain: weave.Node,
) -> weave.Panel:
    x_axis_type = input_node[x_axis_key].type.object_type  # type: ignore
    if weave.types.optional(weave.types.Timestamp()).assign_type(x_axis_type):
        bin_fn = weave.ops.timestamp_bins_nice
    elif weave.types.optional(weave.types.Number()).assign_type(x_axis_type):
        bin_fn = weave.ops.numbers_bins_equal
    else:
        raise ValueError(f"Unsupported type for x_axis_key {x_axis_key}: {x_axis_type}")
    return weave.panels.Plot(
        input_node,
        x=lambda row: row[x_axis_key].bin(bin_fn(bin_domain_node, 100))["start"],
        x_title=x_axis_key,
        y=lambda row: row[y_axis_key].avg(),
        y_title="avg" + y_axis_key,
        label=lambda row: row[groupby_key],
        groupby_dims=["x", "label"],
        mark="line",
        no_legend=True,
        domain_x=x_domain,
    )


def timeseries_sum_bar(
    input_node: weave.Node[list[typing.Any]],
    bin_domain_node: weave.Node,
    x_axis_key: str,
    y_axis_key: str,
    groupby_key: typing.Union[weave.Node[str], str],
    x_domain: weave.Node,
    n_bins: int,
) -> weave.Panel:
    x_axis_type = input_node[x_axis_key].type.object_type  # type: ignore
    if weave.types.optional(weave.types.Timestamp()).assign_type(x_axis_type):
        x_title = ""
        bin_fn = weave.ops.timestamp_bins_nice
    elif weave.types.optional(weave.types.Number()).assign_type(x_axis_type):
        x_title = x_axis_key
        bin_fn = weave.ops.numbers_bins_equal
    else:
        raise ValueError(f"Unsupported type for x_axis_key {x_axis_key}: {x_axis_type}")
    return weave.panels.Plot(
        input_node,
        x=lambda row: row[x_axis_key].bin(bin_fn(bin_domain_node, n_bins)),
        x_title=x_title,
        y=lambda row: row[y_axis_key].sum(),
        y_title="sum_" + y_axis_key,
        label=lambda row: row[groupby_key],
        groupby_dims=["x", "label"],
        mark="bar",
        no_legend=True,
        domain_x=x_domain,
    )


def timeseries_count_bar(
    input_node: weave.Node[list[typing.Any]],
    bin_domain_node: weave.Node,
    x_axis_key: str,
    groupby_key: typing.Union[weave.Node[str], str],
    x_domain: weave.Node,
    n_bins: int,
) -> weave.Panel:
    x_axis_type = input_node[x_axis_key].type.object_type  # type: ignore
    if weave.types.optional(weave.types.Timestamp()).assign_type(x_axis_type):
        x_title = ""
        bin_fn = weave.ops.timestamp_bins_nice
    elif weave.types.optional(weave.types.Number()).assign_type(x_axis_type):
        x_title = x_axis_key
        bin_fn = weave.ops.numbers_bins_equal
    else:
        raise ValueError(f"Unsupported type for x_axis_key {x_axis_key}: {x_axis_type}")
    return weave.panels.Plot(
        input_node,
        x=lambda row: row[x_axis_key].bin(bin_fn(bin_domain_node, n_bins)),
        x_title=x_title,
        y=lambda row: row.count(),
        label=lambda row: row[groupby_key],
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=x_domain,
    )


def categorical_dist(
    input_node: weave.Node[list[typing.Any]],
    key: str,
) -> weave.Panel:
    return weave.panels.Plot(
        input_node,
        y=lambda row: row[key],
        x=lambda row: row.count(),
        label=lambda row: row[key],
        groupby_dims=["y", "label"],
        mark="bar",
        no_legend=True,
    )


def node_qualifies_for_autoboard(input_node: weave.Node[typing.Any]) -> bool:
    input_type = input_node.type
    if not weave.types.is_list_like(input_type):
        return False

    object_type = input_type.object_type  # type: ignore
    if not weave.types.TypedDict().assign_type(object_type):
        return False
    property_types = typing.cast(
        dict[str, weave.types.Type], object_type.property_types
    )
    x_axis = None

    for k, prop_type in property_types.items():
        if not weave.types.NoneType().assign_type(prop_type) and weave.types.optional(
            weave.types.Timestamp()
        ).assign_type(prop_type):
            x_axis = k
            x_axis_type = prop_type
            break
    if x_axis is None:
        for step_key in ["_step", "step"]:
            if step_key in property_types and weave.types.optional(
                weave.types.Int()
            ).assign_type(property_types[step_key]):
                x_axis = step_key
                x_axis_type = property_types[step_key]

    if x_axis is None:
        return False

    return True


def auto_panels(
    input_node: weave.Node[list[typing.Any]],
    config: typing.Optional[AutoBoardConfig] = None,
) -> weave.Panel:
    input_type = input_node.type
    if isinstance(input_type, weave.types.Function):
        input_type = input_type.output_type
    if not weave.types.is_list_like(input_type):
        raise ValueError("Input node must be a list")
    object_type = input_type.object_type  # type: ignore
    if not weave.types.TypedDict().assign_type(object_type):
        raise ValueError("Input node must be a list of objects")
    property_types = typing.cast(
        dict[str, weave.types.Type], object_type.property_types
    )
    x_axis = None

    for k, prop_type in property_types.items():
        if not weave.types.NoneType().assign_type(prop_type) and weave.types.optional(
            weave.types.Timestamp()
        ).assign_type(prop_type):
            x_axis = k
            x_axis_type = prop_type
            break
    if x_axis is None:
        for step_key in ["_step", "step"]:
            if step_key in property_types and weave.types.optional(
                weave.types.Int()
            ).assign_type(property_types[step_key]):
                x_axis = step_key
                x_axis_type = property_types[step_key]

    if x_axis is None:
        # TODO: handle instead
        raise ValueError(
            'No suitable x-axis (Timestamp type, or _step) property found in input type "%s"'
            % input_type
        )

    groupby = weave_internal.const(None)
    for k, prop_type in property_types.items():
        if ("version" in k or "snapshot" in k) and weave.types.optional(
            weave.types.String()
        ).assign_type(prop_type):
            groupby = weave_internal.const(k)

    metric_panels = []
    categorical_panels = []

    data_node = weave_internal.make_var_node(input_node.type, "data")
    x_domain_node = weave_internal.make_var_node(
        weave.types.optional(weave.types.List(x_axis_type)), "zoom_range"
    )
    time_domain_node = weave_internal.make_var_node(
        weave.types.List(x_axis_type), "bin_range"
    )
    window_data_node = weave_internal.make_var_node(input_node.type, "window_data")

    groupby_key_node = weave_internal.make_var_node(groupby.type, "groupby")

    for key, prop_type in property_types.items():
        if weave.types.optional(weave.types.Number()).assign_type(prop_type):
            panel = timeseries_sum_bar(
                data_node,
                time_domain_node,
                x_axis,
                key,
                groupby_key_node,
                x_domain_node,
                50,
            )
            metric_panels.append(panel)
        elif (
            weave.types.optional(weave.types.String()).assign_type(prop_type)
            and key != "prompt"
            and key != "completion"
        ):
            panel = categorical_dist(window_data_node, key)
            categorical_panels.append(panel)

    metrics = weave.panels.Group(
        layoutMode=weave.panels.GroupLayoutFlow(2, 3),
        items={"panel%s" % i: panel for i, panel in enumerate(metric_panels)},
    )
    categoricals = weave.panels.Group(
        layoutMode=weave.panels.GroupLayoutFlow(2, 3),
        items={"panel%s" % i: panel for i, panel in enumerate(categorical_panels)},
    )
    control_items = [
        weave.panels.GroupPanel(
            input_node,
            id="data",
        ),
        # TODO: We need a filter editor. Can start with a filter expression
        # editor and make it more user-friendly later
        weave.panels.GroupPanel(
            lambda data: weave.ops.make_list(
                a=data[x_axis].min(), b=data[x_axis].max()
            ),
            id="data_range",
            hidden=True,
        ),
        weave.panels.GroupPanel(None, id="zoom_range", hidden=True),
        weave.panels.GroupPanel(
            lambda zoom_range, data_range: zoom_range.coalesce(data_range),
            id="bin_range",
            hidden=True,
        ),
        weave.panels.GroupPanel(
            lambda data, zoom_range: weave.panels.DateRange(
                zoom_range, domain=data[x_axis]
            ),
            id="date_picker",
        ),
        # TODO: groupby should really be a Dropdown / multi-select instead
        # of an expression
        weave.panels.GroupPanel(
            groupby,
            id="groupby",
        ),
        weave.panels.GroupPanel(
            lambda data, bin_range: data.filter(
                lambda row: weave.ops.Boolean.bool_and(
                    row[x_axis] >= bin_range[0], row[x_axis] < bin_range[1]
                )
            ),
            id="window_data",
            hidden=True,
        ),
    ]

    panels = [
        weave.panels.BoardPanel(
            metrics,
            id="metrics",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=12),
        ),
        weave.panels.BoardPanel(
            categoricals,
            id="categoricals",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=12),
        ),
    ]
    if "step" not in x_axis:
        panels.insert(
            0,
            weave.panels.BoardPanel(
                timeseries_count_bar(
                    data_node,
                    time_domain_node,
                    x_axis,
                    groupby_key_node,
                    x_domain_node,
                    150,
                ),
                id="volume",
                layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
            ),
        )

    panels.append(
        weave.panels.BoardPanel(
            window_data_node,
            id="table",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
        ),
    )
    return weave.panels.Board(vars=control_items, panels=panels, editable=False)


# The interface for constructing this Panel from Python
@weave.type()
class AutoBoard(weave.Panel):
    id = "AutoBoard"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[AutoBoardConfig] = None

    @weave.op()  # type: ignore
    def render(self) -> weave.panels.Group:
        return auto_panels(self.input_node, self.config)  # type: ignore


@weave.op(  # type: ignore
    name="py_board-seed_autoboard",
    hidden=True,
)
def seed_autoboard(
    input_node: weave.Node[typing.Any],
    config: typing.Optional[AutoBoardConfig] = None,
) -> weave.panels.Group:
    return auto_panels(input_node, config)  # type: ignore


with open(
    os.path.join(os.path.dirname(__file__), "instructions", "panel_autoboard.md"), "r"
) as f:
    instructions_md = f.read()


template_registry.register(
    "py_board-seed_autoboard",
    "Timeseries Auto-Board",
    "Column-level analysis of timeseries data",
    input_node_predicate=node_qualifies_for_autoboard,
    # Not featuring because it is pretty buggy
    # is_featured=True,
    instructions_md=instructions_md,
)
