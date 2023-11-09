import weave

from ..panels_py import panel_autoboard
from .. import weave_types as types
from ..panels import panel_group
from ..panels import panel_board
from .. import weave_internal
from .generator_templates import template_registry

panels = weave.panels


BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "timestamp": types.optional(types.Timestamp()),
            "_timestamp": types.Number(),
            "entity_name": types.optional(types.String()),
            "project_name": types.optional(types.String()),
            "queue_uri": types.optional(types.String()),
            "run_id": types.optional(types.String()),
            "job": types.optional(types.String()),
            "trace_id": types.optional(types.String()),
            "state": types.optional(types.String()),
            "error": types.optional(types.String()),
            "metrics": types.optional(types.String()),
        }
    )
)


@weave.op(  # type: ignore
    name="py_board-observability",
    hidden=False,
    input_type={
        "input_node": types.Function(
            {},
            BOARD_INPUT_WEAVE_TYPE,
        )
    },
)
def observability(
    input_node,
) -> panels.Group:
    timestamp_col_name = "timestamp"

    varbar = panel_board.varbar(editable=False)
    # source_data = weave_internal.make_var_for_value(input_node, "source_data")
    source_data = varbar.add("source_data", input_node)

    filter_fn = varbar.add(
        "filter_fn",
        weave_internal.define_fn(
            {"row": source_data.type.object_type},
            lambda row: weave_internal.const(True),
        ),
        hidden=True,
    )

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["state"]
        ),
        hidden=True,
    )

    filtered_data = varbar.add(
        "filtered_data", source_data.filter(filter_fn), hidden=True
    )

    filtered_range = varbar.add(
        "filtered_range",
        weave.ops.make_list(
            a=filtered_data[timestamp_col_name].min(),
            b=filtered_data[timestamp_col_name].max(),
        ),
        hidden=True,
    )

    ## 2. user_zoom_range is used to store the user's zoom range
    user_zoom_range = varbar.add("user_zoom_range", None, hidden=True)

    ## 2.b: Setup a date picker to set the user_zoom_range
    varbar.add(
        "time_range",
        weave.panels.DateRange(user_zoom_range, domain=source_data[timestamp_col_name]),
    )

    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )

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

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    overview_tab.add(
        "launch_runs",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key=timestamp_col_name,
            y_expr=lambda row: row.count(),
            y_title="Launch Runs",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=100,
            mark="bar",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=10),
    )

    grouping_fn_2 = varbar.add(
        "grouping_fn_2",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["trace_id"]
        ),
        hidden=True,
    )

    # overview_tab.add(
    #     "runtime_distribution",
    #     panel_autoboard.timeseries(
    #         source_complete,
    #         bin_domain_node=bin_range,
    #         x_axis_key=timestamp_col_name,
    #         y_expr=lambda row: (
    #             row[timestamp_col_name].max() - row[timestamp_col_name].min(),
    #         ),
    #         y_title="duration",
    #         color_expr=lambda row: grouping_fn_2(row),
    #         color_title="trace_id",
    #         x_domain=user_zoom_range,
    #         n_bins=50,
    #         mark="line",
    #     ),
    #     layout=weave.panels.GroupPanelLayout(x=0, y=6, w=6, h=6),
    # )

    requests_table = weave.panels.Table(filtered_window_data)  # type: ignore
    requests_table.add_column(
        lambda row: row["timestamp"], "Timestamp", sort_dir="desc"
    )
    requests_table_var = overview_tab.add(
        "table",
        requests_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=13, w=24, h=8),
    )

    # overview_tab.add(
    #     "table",
    #     weave.panels.BoardPanel(
    #         weave_internal.make_var_node(input_node.type, "data"),
    #         id="table",
    #         layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
    #     ),
    # )
    return weave.panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    "py_board-observability",
    "observability",
    "Seed a board with a launch observability viz.",
)
