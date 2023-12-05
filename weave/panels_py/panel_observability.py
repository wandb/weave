import weave

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
    num_buckets = 80

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=False,
        enableAddPanel=False,
        disableDeletePanel=True,
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

    three_days_in_seconds = 60 * 60 * 24 * 3
    window_start = weave.ops.from_number(
        weave.ops.datetime_now() - three_days_in_seconds
    )
    window_end = weave.ops.from_number(weave.ops.datetime_now())

    filtered_range = weave.ops.make_list(
        a=window_start,
        b=window_end,
    )

    user_zoom_range = varbar.add("user_zoom_range", None, hidden=True)
    varbar.add(
        "Time_range",
        panels.DateRange(user_zoom_range, domain=filtered_range),
    )

    bin_range = user_zoom_range.coalesce(filtered_range)
    window_data = source_data.filter(
        lambda row: weave.ops.Boolean.bool_and(
            row[timestamp_col_name] >= bin_range[0],
            row[timestamp_col_name] <= bin_range[1],
        )
    )
    filtered_window_data = varbar.add(
        "filtered_window_data",
        window_data.filter(filter_fn),
        hidden=True,
    )

    varbar.add(
        "Filters",
        panels.FilterEditor(filter_fn, node=window_data),
    )

    colors_node = weave.ops.dict_(
        **{
            "running": "rgb(83, 135, 221)",
            "failed": "rgb(255, 80, 80)",
            "crashed": "rgb(218, 200, 76)",
            "finished": "rgb(0, 200, 100)",
            "starting": "rgb(218, 200, 0)",
            "failed_rqi": "rgb(255, 0, 0)",
            "queued": "rgb(218, 200, 200)",
            "popped": "rgb(150, 150, 150)",
        }
    )

    state_color_func = weave_internal.define_fn(
        {"row": input_node.type.object_type},
        lambda row: colors_node.pick(row["state"]),
    )

    queue_time_data = filtered_window_data.filter(
        lambda row: weave.ops.Boolean.bool_or(
            row["state"] == "queued",
            row["state"] == "starting",
        ),
    )

    is_start_stop_state = weave_internal.define_fn(
        {"row": input_node.type.object_type},
        lambda row: weave.ops.Boolean.bool_or(
            row["state"] == "running",
            weave.ops.Boolean.bool_or(
                row["state"] == "finished",
                weave.ops.Boolean.bool_or(
                    row["state"] == "crashed",
                    row["state"] == "failed",
                ),
            ),
        ),
    )

    # TODO: fix colors to special function
    state_transitions_plot = panels.Plot(
        filtered_window_data,
        x=lambda row: row[timestamp_col_name].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets)
        ),
        x_title="Time",
        y=lambda row: row.count(),
        y_title="Count of transitions by state",
        # label=lambda row: state_color_func(row),
        label=lambda row: row["state"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "state": row["state"][0],
                "count": row.count(),
            }
        ),
        color_title="state",
        color=state_color_func,
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=bin_range,
    )

    queued_time_plot = panels.Plot(
        queue_time_data,
        x=lambda row: row[timestamp_col_name].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets / 2)
        ),
        x_title="Time",
        y=lambda row: weave.ops.timedelta_total_seconds(
            weave.ops.datetime_sub(
                row[timestamp_col_name].max(), row[timestamp_col_name].min()
            )
        ),
        y_title="Time spent queued",
        label=lambda row: row["trace_id"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "job": row["job"][0],
                "user": row["entity_name"][0],
                "project": row["project_name"][0],
                "duration (s)": weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        row[timestamp_col_name].max(), row[timestamp_col_name].min()
                    )
                ),
            }
        ),
        color_title="id",
        color=lambda row: row["trace_id"],
        groupby_dims=["x", "label"],
        mark="bar",
        no_legend=True,
        domain_x=bin_range,
    )

    latest_runs_plot = panels.Plot(
        weave.ops.List.limit(
            list_.List.sort(
                list_.List.filter(filtered_window_data, is_start_stop_state),
                # make_list required for sorting (?)
                compFn=lambda row: weave.ops.make_list(
                    timestamp=row[timestamp_col_name],
                    # state=row["state"],
                ),
                columnDirs=["desc"],
            ),
            30,
        ),
        x=lambda row: row["run_id"],
        x_title="Run ID",
        y_title="Runtime",
        y=lambda row: weave.ops.timedelta_total_seconds(
            weave.ops.datetime_sub(
                row[timestamp_col_name].max(), row[timestamp_col_name].min()
            )
        ),
        tooltip=lambda row: weave.ops.dict_(
            **{
                "job": row[0]["job"],
                "run id": row[0]["run_id"],
                "user": row[0]["entity_name"],
                "project": row[0]["project_name"],
                "timestamp": row[0]["timestamp"],
            }
        ),
        label=lambda row: row["run_id"],
        color_title="runtime",
        groupby_dims=["x"],
        mark="bar",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    jobs_table = panels.Table(filtered_window_data.filter(is_start_stop_state))  # type: ignore
    jobs_table.add_column(lambda row: row["run_id"], "Run ID", groupby=True)
    jobs_table.add_column(
        lambda row: weave.ops.timedelta_total_seconds(
            weave.ops.datetime_sub(
                row[timestamp_col_name].max(), row[timestamp_col_name].min()
            )
        )
        / row.count(),
        "runtime (s)",
        sort_dir="desc",
    )
    jobs_table.add_column(lambda row: row["job"][0], "Job")  # groupby=True
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
        "avg cpu util %",
    )

    runs_table = panels.Table(  # type: ignore
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "starting",
            )
        )
    )
    runs_table.add_column(lambda row: row["entity_name"], "User", groupby=True)
    runs_table.add_column(lambda row: row.count(), "Count", sort_dir="desc")

    def make_metric_plot(metric_name: str, y_title: str) -> panels.Plot:
        return panels.Plot(
            filtered_window_data.filter(
                weave_internal.define_fn(
                    {"row": source_data.type.object_type},
                    lambda row: row["state"] == "finished",
                )
            ),
            x=lambda row: row[timestamp_col_name],
            x_title=timestamp_col_name,
            y=lambda row: row["metrics"]["system"][metric_name].avg(),
            y_title=y_title,
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "user": row["entity_name"][0],
                    "run id": row["run_id"][-1],
                    "project": row["project_name"][0],
                    "min": row["metrics"]["system"][metric_name][0].min(),
                    "max": row["metrics"]["system"][metric_name][0].max(),
                    "avg": row["metrics"]["system"][metric_name][0].avg(),
                }
            ),
            groupby_dims=["y", "x"],
            mark="line",
            no_legend=True,
            domain_x=bin_range,
        )

    cpu_plot = make_metric_plot("cpu_cores_util", "avg cpu %")
    gpu_plot = make_metric_plot("gpu_cores_util", "avg gpu %")
    gpu_memory_plot = make_metric_plot("gpu_cores_mem", "avg gpu memory util %")
    memory_plot = weave.panels.Plot(
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "finished",
            )
        ),
        x=lambda row: row[timestamp_col_name],
        x_title=timestamp_col_name,
        y=lambda row: row["metrics"]["system"]["memory"],
        y_title="system memory used (MB)",
        tooltip=lambda row: weave.ops.dict_(
            **{
                "user": row["entity_name"][0],
                "run id": row["run_id"][-1],
                "project": row["project_name"][0],
                "memory": row["metrics"]["system"]["memory"][0],
            }
        ),
        groupby_dims=["y", "x"],
        mark="line",
        no_legend=True,
        domain_x=bin_range,
    )

    errors_table = panels.Table(  # type: ignore
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["error"] != None,
            )
        )
    )
    errors_table.add_column(lambda row: row["run_id"], "Run ID")
    errors_table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")
    errors_table.add_column(lambda row: row["job"], "Job")
    errors_table.add_column(lambda row: row["error"], "Error", panel_def="object")

    # layout
    overview_tab.add(
        "State_transitions",
        state_transitions_plot,
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )
    overview_tab.add(
        "Queued_time",
        queued_time_plot,
        layout=panels.GroupPanelLayout(x=0, y=6, w=12, h=8),
    )
    overview_tab.add(
        "Lastest_runs",
        latest_runs_plot,
        layout=panels.GroupPanelLayout(x=12, y=6, w=12, h=8),
    )
    overview_tab.add(
        "Longest_jobs",
        jobs_table,
        layout=panels.GroupPanelLayout(x=0, y=14, w=12, h=8),
    )
    overview_tab.add(
        "Runs_by_users",
        runs_table,
        layout=panels.GroupPanelLayout(x=12, y=14, w=12, h=8),
    )
    overview_tab.add(
        "Cpu_usage_on_run_finish",
        cpu_plot,
        layout=panels.GroupPanelLayout(x=0, y=22, w=12, h=6),
    )
    overview_tab.add(
        "System_memory_on_run_finish",
        memory_plot,
        layout=panels.GroupPanelLayout(x=12, y=22, w=12, h=6),
    )
    overview_tab.add(
        "Gpu_usage_on_run_finish",
        gpu_plot,
        layout=panels.GroupPanelLayout(x=0, y=28, w=12, h=6),
    )
    overview_tab.add(
        "Gpu_memory_on_run_finish",
        gpu_memory_plot,
        layout=panels.GroupPanelLayout(x=12, y=28, w=12, h=6),
    )
    overview_tab.add(
        "Errors",
        errors_table,
        layout=panels.GroupPanelLayout(x=0, y=34, w=24, h=8),
    )

    return panels.Board(vars=varbar, panels=overview_tab, editable=False)


template_registry.register(
    "py_board-observability",
    "Launch Observability",
    "Seed a board with an observability view to track Launch queue performance.",
)
