import weave

from ..panels_py import panel_autoboard
from .. import weave_types as types
from ..panels import panel_board
from .. import weave_internal
from .generator_templates import template_registry

from ..ops_primitives import list_


panels = weave.panels


BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "timestamp": types.optional(types.Timestamp()),
            "_timestamp": types.Number(),
            "entity_name": types.optional(types.String()),
            "project_name": types.optional(types.String()),
            "queue_uri": types.optional(types.String()),
            "sweep_id": types.optional(types.String()),
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

num_buckets = 80


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

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    varbar = panel_board.varbar(editable=False)
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
        "Time_range",
        panels.DateRange(user_zoom_range, domain=source_data[timestamp_col_name]),
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
        "Filters",
        panels.FilterEditor(filter_fn, node=window_data),
    )

    filtered_window_data = varbar.add(
        "filtered_window_data", window_data.filter(filter_fn), hidden=True
    )

    varbar.add(
        "Grouping",
        panels.GroupingEditor(grouping_fn, node=window_data),
    )

    grouping_by_trace = varbar.add(
        "grouping_fn_2",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["trace_id"]
        ),
        hidden=True,
    )

    colors_node = weave.ops.dict_(
        **{
            "running": "rgb(83, 135, 221)",
            "failed": "rgb(218, 76, 76)",
            "crashed": "rgb(218, 200, 76)",
            "finished": "rgb(218, 200, 200)",
            "rqi_pending": "rgb(218, 0, 76)",
            "rqi_failed": "rgb(255, 0, 0)",
            "rqi_launched": "rgb(0, 200, 76)",
            "rqi_popped": "rgb(218, 200, 0)",
        }
    )

    state_color_func = varbar.add(
        "state_color_func",
        weave_internal.define_fn(
            {"row": input_node.type.object_type},
            lambda row: colors_node.pick(row["state"]),
        ),
        hidden=True,
    )

    grouped = list_.List.groupby(filtered_window_data, lambda row: row["trace_id"])

    grouped_mapped = list_.List.map(
        grouped,
        lambda run: weave.ops.dict_(
            queued_time=weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    run[timestamp_col_name][2], run[timestamp_col_name][0]
                )
            ),
            job=run["job"][0],
            run_id=run["run_id"][-1],
            trace_id=run["trace_id"][0],
            project_name=run["project_name"][0],
            entity_name=run["entity_name"][0],
            enqueued=run[timestamp_col_name].min(),
            start=run[timestamp_col_name][2],
            end=run[timestamp_col_name].max(),
            duration=weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    run[timestamp_col_name].max(), run[timestamp_col_name][2]
                )
            ),
        ),
    )

    overview_tab.add(
        "State_transitions",
        panels.Plot(
            filtered_data,
            x=lambda row: row[timestamp_col_name].bin(
                weave.ops.timestamp_bins_nice(bin_range, num_buckets)
            ),
            x_title="Time",
            y=lambda row: row.count(),
            y_title="State Transitions",
            label=lambda row: state_color_func(row),
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "state": row["state"][0],
                    "count": row.count(),
                }
            ),
            color_title="state",
            color=lambda row: state_color_func(row),
            groupby_dims=["x", "label"],
            mark="bar",
            no_legend=True,
            domain_x=user_zoom_range,
        ),
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    overview_tab.add(
        "Queued_time",
        panels.Plot(
            grouped_mapped.filter(lambda row: row["queued_time"] > 0),
            x=lambda row: row["enqueued"].bin(
                weave.ops.timestamp_bins_nice(bin_range, num_buckets / 2)
            ),
            x_title="Time",
            y=lambda row: row["queued_time"],
            y_title="Time spent queued",
            label=lambda row: row["trace_id"],
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "project": row["project_name"][0],
                    "user": row["entity_name"][0],
                    "duration": row["queued_time"][0],
                }
            ),
            color_title="id",
            color=lambda row: row["queued_time"],
            groupby_dims=["x", "label"],
            mark="bar",
            no_legend=True,
            domain_x=user_zoom_range,
        ),
        layout=panels.GroupPanelLayout(x=0, y=6, w=12, h=8),
    )

    overview_tab.add(
        "Recent_run_runtimes",
        panels.Plot(
            weave.ops.List.limit(
                grouped_mapped.filter(lambda row: row["duration"] > 0),
                10,
            ),
            x=lambda row: row["run_id"],
            x_title="Run ID",
            y_title="Runtime",
            y=lambda row: row["duration"],
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "job": row["job"],
                    "run_id": row["run_id"],
                    "entity_name": row["entity_name"],
                    "project_name": row["project_name"],
                    "queued_time": row["queued_time"],
                    "runtime (s)": row["duration"],
                }
            ),
            color=lambda row: row["run_id"],
            color_title="runtime",
            groupby_dims=[],
            mark="bar",
            no_legend=True,
            domain_x=user_zoom_range,
        ),
        layout=panels.GroupPanelLayout(x=12, y=6, w=12, h=8),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["state"], "State", groupby=True)
    table.add_column(lambda row: row.count(), "Count")
    overview_tab.add(
        "runs_by_state_table",
        table,
        layout=panels.GroupPanelLayout(x=0, y=14, w=12, h=8),
    )

    table = panels.Table(
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "rqi_launched",
            )
        )
    )
    table.add_column(lambda row: row["entity_name"], "Entity", groupby=True)
    table.add_column(lambda row: row.count(), "Count")
    overview_tab.add(
        "runs_by_user_table",
        table,
        layout=panels.GroupPanelLayout(x=12, y=14, w=12, h=8),
    )

    plot = weave.panels.Plot(
        filtered_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "finished",
            )
        ),
        x=lambda row: row[timestamp_col_name].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets)
        )["start"],
        x_title=timestamp_col_name,
        y=lambda row: weave.ops.make_list(
            a=row["metrics"]["system"]["cpu_cores_util"][0].min(),
            b=row["metrics"]["system"]["cpu_cores_util"][0].avg(),
            c=row["metrics"]["system"]["cpu_cores_util"][0].max(),
        ),
        y_title="min, max, avg cpu %",
        # label=lambda row: row["metrics"]["system"]["cpu_cores_util"][0].avg(),
        tooltip=lambda row: weave.ops.dict_(
            **{
                "min": row["metrics"]["system"]["cpu_cores_util"],
                "max": row["metrics"]["system"]["cpu_cores_util"],
                "avg": row["metrics"]["system"]["cpu_cores_util"],
            }
        ),
        color=lambda row: row["metrics"]["system"]["cpu_cores_util"][0].avg(),
        groupby_dims=["x", "tooltip"],
        mark="line",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    overview_tab.add(
        "cpu_usage_on_run_finish",
        plot,
        layout=panels.GroupPanelLayout(x=0, y=24, w=24, h=6),
    )

    table = panels.Table(
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["error"] != None,
            )
        )
    )
    table.add_column(lambda row: row["run_id"], "Run ID")
    table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")
    table.add_column(lambda row: row["error"], "Error", panel_def="object")
    table.add_column(lambda row: row["job"], "Job")
    table.add_column(lambda row: row["queue_uri"], "Queue")
    overview_tab.add(
        "errors",
        table,
        layout=panels.GroupPanelLayout(x=0, y=30, w=24, h=8),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["job"], "Job", groupby=True)
    table.add_column(lambda row: row.count(), "# Runs", sort_dir="desc")
    table.add_column(
        lambda row: weave.ops.timedelta_total_seconds(
            weave.ops.datetime_sub(
                row[timestamp_col_name].max(), row[timestamp_col_name].min()
            )
        )
        / row.count(),
        "avg runtime (duration)",
    )
    overview_tab.add(
        "jobs",
        table,
        layout=panels.GroupPanelLayout(x=0, y=38, w=12, h=8),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["entity_name"], "User", groupby=True)
    table.add_column(lambda row: row.count(), "# Runs", sort_dir="desc")
    overview_tab.add(
        "users",
        table,
        layout=panels.GroupPanelLayout(x=12, y=38, w=12, h=8),
    )

    return panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    "py_board-observability",
    "observability",
    "Seed a board with a launch observability viz.",
)
