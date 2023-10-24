import os
import typing

import weave
from .. import dispatch
from .. import weave_internal as internal
from .. import weave_types as types
from .. import weave_internal
from ..panels import panel_group
from ..panels import panel_board
from . import panel_autoboard
from .generator_templates import template_registry


panels = weave.panels
ops = weave.ops


# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "launch_observability_monitor"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "Monitor Launch Observability"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Understand performance and quality. Track trends and organization-wide usage."

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.
BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "timestamp": types.optional(types.Timestamp()),
            "entity": types.String(),
            "project": types.String(),
            "queue": types.String(),
            "run_id": types.optional(types.String()),
            "run_queue_item_id": types.String(),
            "state": types.String(),
            "metrics": types.optional(types.TypedDict()),
        }
    )
)


board_name = "py_board-" + BOARD_ID


@weave.op(  # type: ignore
    name=board_name,
    hidden=True,
    input_type={
        "input_node": types.Function(
            {},
            BOARD_INPUT_WEAVE_TYPE,
        )
    },
)
def board(
    input_node,
) -> panels.Group:
    timestamp_col_name = "timestamp"

    ### Varbar

    # Add the input node as raw data
    varbar = panel_board.varbar(editable=False)

    source_data = varbar.add("source_data", input_node)

    filter_fn = varbar.add(
        "filter_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: weave_internal.const(True)
        ),
        hidden=True,
    )

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["entity"]
        ),
        hidden=True,
    )

    filtered_data = varbar.add(
        "filtered_data", source_data.filter(filter_fn), hidden=True
    )

    # Setup date range variables:
    ## 1. raw_data_range is derived from raw_data
    filtered_range = varbar.add(
        "filtered_range",
        weave.ops.make_list(
            a=filtered_data[timestamp_col_name].min(),
            b=filtered_data[timestamp_col_name].max(),
        ),
        hidden=False,
    )

    ## 2. user_zoom_range is used to store the user's zoom range
    user_zoom_range = varbar.add("user_zoom_range", None, hidden=True)

    ## 2.b: Setup a date picker to set the user_zoom_range
    varbar.add(
        "time_range",
        weave.panels.DateRange(user_zoom_range, domain=source_data[timestamp_col_name]),
    )

    ## 3. bin_range is derived from user_zoom_range and raw_data_range. This is
    ##    the range of data that will be displayed in the charts.
    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )
    # Derive the windowed data to use in the plots as a function of bin_range

    window_data = varbar.add(
        "window_data",
        source_data.filter(
            lambda row: weave.ops.Boolean.bool_and(
                row[timestamp_col_name] >= bin_range[0],
                row[timestamp_col_name] <= bin_range[1],
            )
        ),
        hidden=True,
    )

    filters = varbar.add(
        "filters",
        weave.panels.FilterEditor(filter_fn, node=window_data),
    )

    filtered_window_data = varbar.add(
        "filtered_window_data", window_data.filter(filter_fn), hidden=True
    )

    grouping = varbar.add(
        "grouping",
        weave.panels.GroupingEditor(grouping_fn, node=window_data),
    )

    height = 5

    ### Overview tab

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )  # , showExpressions="titleBar")
    overview_tab.add(
        "request_count",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row.count(),
            y_title="request count",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=100,
            mark="bar",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=height),
    )

    overview_tab.add(
        "cost",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row["summary.cost"].sum(),
            y_title="total cost ($)",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=height, w=12, h=height),
    )

    overview_tab.add(
        "latency",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row["summary.latency_s"].avg(),
            y_title="avg latency (s)",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=12, y=height, w=12, h=height),
    )

    overview_tab.add(
        "metrics",
        filtered_window_data["metrics"].avg(),  # type: ignore
        layout=weave.panels.GroupPanelLayout(x=0, y=height * 2, w=6, h=3),
    )

    return panels.Board(vars=varbar, panels=overview_tab)


with open(
    os.path.join(os.path.dirname(__file__), "instructions", "panel_llm_monitor.md"), "r"
) as f:
    instructions_md = f.read()

template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
    is_featured=True,
    instructions_md=instructions_md,
    thumbnail_url="https://raw.githubusercontent.com/wandb/weave/master/docs/assets/monitor-open-ai-api-usage.png",
)
