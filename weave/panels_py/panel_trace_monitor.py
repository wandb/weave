import typing

import weave
from .. import dispatch
from .. import weave_internal as internal
from .. import weave_types as types
from .. import weave_internal
from ..panels import panel_group
from ..panels import panel_board
from ..panels import panel_trace
from ..panels_py import panel_autoboard
from .generator_templates import template_registry


panels = weave.panels
ops = weave.ops


# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "trace_monitor"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "Trace Monitor Board"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Monitor Traces"

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.


BOARD_INPUT_WEAVE_TYPE = types.List(panel_trace.span_typed_dict_type)


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

    all_spans = varbar.add("all_spans", input_node)

    trace_roots = all_spans.filter(lambda row: row["parent_id"].isNone())

    trace_roots_var = varbar.add("trace_roots", trace_roots, True)

    height = 5

    ### Overview tab

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    traces_table = panels.Table(trace_roots_var)  # type: ignore
    traces_table.add_column(lambda row: row["name"], "Span Name")
    traces_table.add_column(lambda row: row["trace_id"], "Trace ID")
    traces_table.add_column(lambda row: row["summary.latency_s"], "Latency")
    traces_table.add_column(lambda row: row["inputs"], "Inputs")
    traces_table.add_column(lambda row: row["output"], "Output")
    traces_table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")

    traces_table_var = overview_tab.add(
        "traces_table",
        traces_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=8),
    )

    trace_spans = all_spans.filter(
        lambda row: row["trace_id"] == traces_table_var.active_data()["trace_id"]
    )

    trace_viewer = panels.Trace(trace_spans)

    trace_viewer_var = overview_tab.add(
        "trace_viewer",
        trace_viewer,
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=8),
    )

    # selected_trace_obj = overview_tab.add(
    #     "selected_trace_obj",
    #     selected_trace,
    #     layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=8),
    # )

    return panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
)
