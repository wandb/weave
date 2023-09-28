import os

import weave
from weave.panels.panel_trace_span import TraceSpanModelPanel, TraceSpanPanel
from .. import dispatch
from .. import weave_internal as internal
from .. import weave_types as types
from .. import weave_internal
from .. import graph
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
BOARD_DISPLAY_NAME = "Trace an LLM pipeline"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Analyze traces from LLM chains, applications or any ML pipeline. Understand LLM agent behavior, monitor systems and debug ML pipelines."

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.


BOARD_INPUT_WEAVE_TYPE = types.List(panel_trace.span_typed_dict_type)


board_name = "py_board-" + BOARD_ID


def make_span_table(input_node: graph.Node) -> panels.Table:
    traces_table = panels.Table(input_node)  # type: ignore
    traces_table.add_column(lambda row: row["status_code"].equal("SUCCESS"), "Success")
    traces_table.add_column(lambda row: row["name"], "Span Name")
    traces_table.add_column(lambda row: row["trace_id"], "Trace ID")
    traces_table.add_column(
        lambda row: row["end_time_s"] - row["start_time_s"], "Latency"
    )
    traces_table.add_column(lambda row: row["inputs"], "Inputs", panel_def="object")
    traces_table.add_column(lambda row: row["output"], "Output", panel_def="object")
    # traces_table.add_column(
    #     lambda row: row["attributes.model.id"], "Model ID", panel_def="object"
    # )
    traces_table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")

    return traces_table


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
    input_node,  # type: ignore
) -> panels.Group:
    timestamp_col_name = "timestamp"

    ### Varbar

    # Add the input node as raw data
    varbar = panel_board.varbar(editable=False)

    all_spans = varbar.add("all_spans", input_node)

    trace_roots = all_spans.filter(lambda row: row["parent_id"].isNone())

    trace_roots_var = varbar.add("trace_roots", trace_roots, True)

    filter_fn = varbar.add(
        "filter_fn",
        weave_internal.define_fn(
            {"row": trace_roots.type.object_type},
            lambda row: weave_internal.const(True),
        ),
        hidden=True,
    )

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["name"]
        ),
        hidden=True,
    )

    filtered_data = varbar.add(
        "filtered_data", trace_roots.filter(filter_fn), hidden=True
    )

    # Setup date range variables:
    ## 1. raw_data_range is derived from raw_data
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
        weave.panels.DateRange(user_zoom_range, domain=trace_roots[timestamp_col_name]),
    )

    ## 3. bin_range is derived from user_zoom_range and raw_data_range. This is
    ##    the range of data that will be displayed in the charts.
    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )
    # Derive the windowed data to use in the plots as a function of bin_range

    window_data = varbar.add(
        "window_data",
        trace_roots.filter(
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

    ### Overview tab

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    # traces_table =   # type: ignore

    overview_tab.add(
        "latency_over_time",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row.map(
                lambda ir: ir["end_time_s"] - ir["start_time_s"]
            ).avg(),
            y_title="avg latency (s)",
            color_expr=lambda row: grouping_fn(row),
            color_title="Root Span Name",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=6, h=6),
    )

    overview_tab.add(
        "latency_distribution",
        filtered_window_data.map(lambda row: row["end_time_s"] - row["start_time_s"]),
        layout=weave.panels.GroupPanelLayout(x=6, y=0, w=6, h=6),
    )

    overview_tab.add(
        "success_over_time",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: (
                row.filter(
                    lambda inner_row: inner_row["status_code"] == "SUCCESS"
                ).count()
                / row.count()
            ),
            y_title="success rate",
            color_expr=lambda row: grouping_fn(row),
            color_title="Root Span Name",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=12, y=0, w=6, h=6),
    )

    overview_tab.add(
        "success_distribution",
        weave.ops.dict_(
            **{
                "success": filtered_window_data.filter(
                    lambda row: row["status_code"] == "SUCCESS"
                ).count(),
                "error": filtered_window_data.filter(
                    lambda row: row["status_code"] != "SUCCESS"
                ).count(),
            }
        ),
        layout=weave.panels.GroupPanelLayout(x=18, y=0, w=6, h=6),
    )

    traces_table_var = overview_tab.add(
        "traces_table",
        make_span_table(filtered_window_data),
        layout=weave.panels.GroupPanelLayout(x=0, y=6, w=24, h=6),
    )

    trace_spans = all_spans.filter(
        lambda row: row["trace_id"] == traces_table_var.active_data()["trace_id"]
    )

    trace_viewer = panels.Trace(trace_spans)  # type: ignore

    trace_viewer_var = overview_tab.add(
        "trace_viewer",
        trace_viewer,
        layout=weave.panels.GroupPanelLayout(x=0, y=12, w=16, h=6),
    )

    selected_trace_model = overview_tab.add(
        "selected_trace_model",
        TraceSpanModelPanel(traces_table_var.active_data()),
        layout=weave.panels.GroupPanelLayout(x=0, y=18, w=16, h=6),
    )

    active_span = trace_viewer_var.active_span()

    selected_span_details = overview_tab.add(
        "selected_span_details",
        TraceSpanPanel(active_span),
        layout=weave.panels.GroupPanelLayout(x=16, y=12, w=8, h=12),
    )

    similar_spans = all_spans.filter(lambda row: row["name"] == active_span["name"])

    similar_spans_table = make_span_table(similar_spans)
    similar_spans_table_var = overview_tab.add(
        "similar_spans_table",
        similar_spans_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=22, w=24, h=6),
    )

    return panels.Board(vars=varbar, panels=overview_tab)


with open(
    os.path.join(os.path.dirname(__file__), "instructions", "panel_trace_monitor.md"),
    "r",
) as f:
    instructions_md = f.read()

template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
    is_featured=True,
    instructions_md=instructions_md,
    thumbnail_url="https://raw.githubusercontent.com/wandb/weave/master/docs/assets/trace-an-llm-pipeline.png",
)
