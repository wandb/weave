import json
import weave
from weave.panels import panel_table

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
            "metrics": types.TypedDict(
                {
                    "system": types.TypedDict(
                        {
                            "tpu": types.optional(types.Number()),
                            "cpu": types.optional(types.Number()),
                            "cpu_cores_util": types.optional(
                                types.List(types.Number())
                            ),
                            "gpu_cores_util": types.optional(
                                types.List(types.Number())
                            ),
                            "gpu_cores_mem": types.optional(types.List(types.Number())),
                            "memory": types.optional(types.Number()),
                            "disk": types.TypedDict(
                                {
                                    "in": types.optional(types.Number()),
                                    "out": types.optional(types.Number()),
                                }
                            ),
                            "proc": types.TypedDict(
                                {
                                    "memory": types.TypedDict(
                                        {
                                            "availableMB": types.optional(
                                                types.Number()
                                            ),
                                        }
                                    )
                                }
                            ),
                        }
                    )
                }
            ),
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
    # source_data = varbar.add("source_data", input_node)
    source_data = input_node

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

    varbar.add(
        "filters",
        weave.panels.FilterEditor(filter_fn, node=window_data),
    )

    filtered_window_data = varbar.add(
        "filtered_window_data", window_data.filter(filter_fn), hidden=True
    )

    varbar.add(
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
            n_bins=101,
            mark="bar",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    grouping_fn_2 = varbar.add(
        "grouping_fn_2",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["trace_id"]
        ),
        hidden=True,
    )

    overview_tab.add(
        "runtime_distribution",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key=timestamp_col_name,
            y_expr=lambda row: weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    row[timestamp_col_name].max(), row[timestamp_col_name].min()
                )
            ),
            y_title="duration",
            color_expr=lambda row: grouping_fn_2(row),
            color_title="trace_id",
            x_domain=user_zoom_range,
            n_bins=20,
            mark="bar",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    overview_tab.add(
        "time_in_state",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key=timestamp_col_name,
            y_expr=lambda row: weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    row[timestamp_col_name].max(), row[timestamp_col_name].min()
                )
            ),
            y_title="Time in state",
            color_expr=lambda row: grouping_fn(row),
            color_title="state",
            x_domain=user_zoom_range,
            n_bins=20,
            mark="bar",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["state"], "State", groupby=True)
    table.add_column(lambda row: row.count(), "Count")
    overview_tab.add(
        "runs_by_state_table",
        table,
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=9, h=8),
    )

    table = panels.Table(
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["run_id"] != None,
            )
        )
    )
    table.add_column(lambda row: row["entity_name"], "Entity", groupby=True)
    table.add_column(lambda row: row.count(), "Count")
    overview_tab.add(
        "runs_by_user_table",
        table,
        layout=weave.panels.GroupPanelLayout(x=9, y=0, w=14, h=8),
    )

    # metrics graph
    overview_tab.add(
        "metrics_over_time",
        panel_autoboard.timeseries(
            filtered_data.filter(
                weave_internal.define_fn(
                    {"row": source_data.type.object_type},
                    lambda row: row["state"] == "finished",
                )
            ),
            bin_domain_node=bin_range,
            x_axis_key=timestamp_col_name,
            y_expr=lambda row: row["metrics"]["system"]["cpu_cores_util"][0].avg(),
            y_title="Average run CPU utilization",
            color_expr=lambda row: row["metrics"]["system"]["cpu_cores_util"].avg(),
            # color_expr=lambda row: grouping_fn_2(row),
            color_title="cpu %",
            x_domain=user_zoom_range,
            n_bins=30,
            mark="point",
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=12, w=24, h=6),
    )

    table = panels.Table(
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "finished",
            )
        )
    )
    table.add_column(lambda row: row["trace_id"], "Id")
    table.add_column(lambda row: row["metrics"]["system"]["cpu"], "CPU")
    table.add_column(
        lambda row: row["metrics"]["system"]["cpu_cores_util"].count(), "CPU count"
    )
    table.add_column(
        lambda row: row["metrics"]["system"]["cpu_cores_util"].avg(), "CPU util avg"
    )
    table.add_column(
        lambda row: row["metrics"]["system"]["gpu_cores_util"].count(), "GPU count"
    )
    table.add_column(
        lambda row: row["metrics"]["system"]["gpu_cores_util"].avg(), "GPU util avg"
    )
    table.add_column(
        lambda row: row["metrics"]["system"]["gpu_cores_mem"].avg(), "GPU mem avg"
    )
    table.add_column(lambda row: row["metrics"]["system"]["memory"], "Memory")
    table.add_column(
        lambda row: row["metrics"]["system"]["proc"]["memory"]["availableMB"],
        "Memory available",
    )
    table.add_column(lambda row: row["metrics"]["system"]["disk"]["in"], "Disk in")
    table.add_column(lambda row: row["metrics"]["system"]["disk"]["in"], "Disk out")
    overview_tab.add(
        "metrics",
        table,
        layout=weave.panels.GroupPanelLayout(x=0, y=12, w=24, h=6),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")
    table.add_column(lambda row: row["run_id"], "Run ID", groupby=True)
    table.add_column(lambda row: row["entity_name"], "Entity")
    table.add_column(lambda row: row["project_name"], "Project")
    table.add_column(lambda row: row["state"], "State")
    overview_tab.add(
        "table",
        table,
        layout=weave.panels.GroupPanelLayout(x=0, y=12, w=24, h=8),
    )

    return weave.panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    "py_board-observability",
    "observability",
    "Seed a board with a launch observability viz.",
)
