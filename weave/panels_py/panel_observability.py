import weave
from weave.panels_py import panel_autoboard
from weave import types
from ..panels import panel_board
from .. import weave_internal
from .generator_templates import template_registry


BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "timestamp": types.Timestamp(),
            "entity": types.String(),
            "project": types.String(),
            "queue": types.String(),
            "run_id": types.optional(types.String()),
            "job": types.optional(types.String()),
            "trace_id": types.String(),
            "state": types.String(),
            "error": types.optional(types.String()),
            "metrics": types.optional(types.TypedDict()),
        }
    )
)


@weave.op(  # type: ignore
    name="py_board-observability_board",
    hidden=False,
    input_type={
        "input_node": types.Function(
            {},
            BOARD_INPUT_WEAVE_TYPE,
        )
    },
)
def observability_board(
    input_node,  # : weave.Node[list[dict]],
) -> weave.panels.Group:
    timestamp_col_name = "_timestamp"

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
            a=filtered_data[timestamp_col_name][0],
            b=filtered_data[timestamp_col_name][-1],
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

    # window_data = varbar.add(
    #     "window_data",
    #     source_data.filter(
    #         lambda row: weave.ops.Boolean.bool_and(
    #             row[timestamp_col_name] >= bin_range[0],
    #             row[timestamp_col_name] <= bin_range[1],
    #         )
    #     ),
    #     hidden=True,
    # )

    # filters = varbar.add(
    #     "filters",
    #     weave.panels.FilterEditor(filter_fn, node=window_data),
    # )

    # filtered_window_data = varbar.add(
    #     "filtered_window_data", window_data.filter(filter_fn), hidden=True
    # )

    # grouping = varbar.add(
    #     "grouping",
    #     weave.panels.GroupingEditor(grouping_fn, node=window_data),
    # )

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )  # , showExpressions="titleBar")
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

    overview_tab.add(
        "table",
        weave.panels.BoardPanel(
            weave_internal.make_var_node(input_node.type, "data"),
            id="table",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
        ),
    )
    return weave.panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    "py_board-seed_board_st",
    "Simple Board st",
    "Seed a board with a simple visualization of this table.",
)
