import typing

import weave
from ..panels import panel_board
from ..panels_py import panel_autoboard
from .. import weave_internal
from .generator_templates import template_registry
from .. import weave_types as types


@weave.type()
class PyBoardSeedBoardConfig:
    pass


@weave.op(  # type: ignore
    name="py_board-seed_board",
    hidden=True,
)
def seed_board(
    input_node: weave.Node[list[dict]],
    config: typing.Optional[PyBoardSeedBoardConfig] = None,
) -> weave.panels.Group:
    control_items = [
        weave.panels.GroupPanel(
            input_node,
            id="data",
        ),
    ]

    panels = [
        weave.panels.BoardPanel(
            weave_internal.make_var_node(input_node.type, "data"),
            id="table",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
        ),
    ]
    return weave.panels.Board(vars=control_items, panels=panels)


template_registry.register(
    "py_board-seed_board",
    "Simple Board",
    "Seed a board with a simple visualization of this table.",
)

BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "timestamp": types.optional(types.String()),
            # "server_timestamp": types.Timestamp(),
            "server_timestamp": types.optional(types.String()),
            "entity_name": types.optional(types.String()),
            "project_name": types.optional(types.String()),
            "queue_uri": types.optional(types.String()),
            "run_id": types.optional(types.String()),
            "job": types.optional(types.String()),
            "error": types.optional(types.String()),
            "trace_id": types.optional(types.String()),
            "state": types.optional(types.String()),
            "metrics": types.optional(types.String()),
            "_step": types.Number(),
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
    config: typing.Optional[PyBoardSeedBoardConfig] = None,
) -> weave.panels.Group:
    timestamp_col_name = "timestamp"

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
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=5),
    )

    # overview_tab.add(
    #     "table-raw",
    #     weave.panels.BoardPanel(
    #         weave_internal.make_var_node(BOARD_INPUT_WEAVE_TYPE, "data"),
    #         id="table-raw",
    #         layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
    #     ),
    # )

    return weave.panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    "py_board-observability_board",
    "Observability Board from streamtable rows",
    "Seed a board with a simple visualization of this table.",
)
