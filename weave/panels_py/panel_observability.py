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

    now = weave.ops.datetime_now()

    dashboard = weave.panels.Group(
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

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["entity_name"]
        ),
        hidden=True,
    )

    three_days_in_seconds = 60 * 60 * 24 * 3
    window_start = varbar.add(
        "window_start",
        weave.ops.from_number(now - three_days_in_seconds),
        hidden=True,
    )
    window_end = varbar.add(
        "window_end",
        weave.ops.from_number(now),
        hidden=True,
    )

    filtered_range = varbar.add(
        "filtered_range",
        weave.ops.make_list(
            a=window_start,
            b=window_end,
        ),
        hidden=True,
    )

    user_zoom_range = varbar.add("user_zoom_range", None, hidden=True)
    varbar.add(
        "Time_range",
        panels.DateRange(user_zoom_range, domain=filtered_range),
    )
    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )

    window_data = source_data.filter(
        lambda row: weave.ops.Boolean.bool_and(
            row[timestamp_col_name] >= bin_range[0],
            row[timestamp_col_name] <= bin_range[1],
        )
    )
    varbar.add(
        "Grouping",
        panels.GroupingEditor(grouping_fn, node=window_data),
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
            "running": "rgb(57, 126, 237)",
            "failed": "rgb(255, 122, 136)",
            "crashed": "rgb(255, 61, 90)",
            "finished": "rgb(0, 178, 110)",
            "starting": "rgb(125, 177, 250)",
            "failed_rqi": "rgb(255, 199, 202)",
            "queued": "rgb(211, 215, 222)",
            "popped": "rgb(189, 217, 255)",
        }
    )

    state_color_func = weave_internal.define_fn(
        {"row": input_node.type.object_type},
        lambda row: colors_node.pick(row["state"]),
    )

    queued_time_data = varbar.add(
        "queued_time_data",
        filtered_window_data.filter(
            lambda row: weave.ops.Boolean.bool_or(
                row["state"] == "queued",
                row["state"] == "starting",
            ),
        ),
        hidden=True,
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

    state_transitions_plot = panels.Plot(
        filtered_window_data,
        x=lambda row: row[timestamp_col_name].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets)
        ),
        x_title="Time",
        y=lambda row: row.count(),
        y_title="Count of transitions by state",
        label=lambda row: row["state"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "state": row["state"][0],
                "count": row.count(),
            }
        ),
        color_title="state",
        color=state_color_func.val,
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=user_zoom_range,
    )

    queued_time_plot = panels.Plot(
        queued_time_data,
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
        label=lambda row: grouping_fn(row),
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
        color_title="Grouping",
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=user_zoom_range,
    )

    start_stop_states = varbar.add(
        "start_stop_states",
        weave.ops.List.filter(filtered_window_data, is_start_stop_state),
        hidden=True,
    )

    latest_runs = varbar.add(
        "latest_runs",
        weave.ops.List.limit(
            weave.ops.List.sort(
                arr=start_stop_states,
                compFn=lambda row: weave.ops.make_list(a=row["timestamp"]),
                columnDirs=["desc"],
            ),
            30,
        ),
        hidden=True,
    )

    latest_runs_plot = panels.Plot(
        latest_runs,
        x=lambda row: row[timestamp_col_name],
        x_title="Time",
        y_title="Run ID",
        y=lambda row: row["run_id"],
        tooltip=lambda row: row[0]["job"],
        label=lambda row: row["trace_id"],
        groupby_dims=["label"],
        mark="line",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    jobs = varbar.add(
        "jobs",
        filtered_window_data.filter(is_start_stop_state),
        hidden=True,
    )
    jobs_table = panels.Table(jobs)  # type: ignore
    jobs_table.add_column(lambda row: row["run_id"], "Run ID", groupby=True)
    jobs_table.add_column(
        lambda row: weave.ops.timedelta_total_seconds(
            weave.ops.datetime_sub(
                row[timestamp_col_name].max(), row[timestamp_col_name].min()
            )
        ),
        "runtime (s)",
        sort_dir="desc",
    )
    jobs_table.add_column(lambda row: row["job"][0], "Job")  # groupby=True
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
        "avg cpu util %",
    )

    starting_runs = varbar.add(
        "starting_runs",
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "starting",
            )
        ),
        hidden=True,
    )
    runs_table = panels.Table(starting_runs)  # type: ignore
    runs_table.add_column(lambda row: row["entity_name"], "User", groupby=True)
    runs_table.add_column(lambda row: row.count(), "Count", sort_dir="desc")

    finished_runs = varbar.add(
        "finished_runs",
        filtered_window_data.filter(
            lambda row: weave.ops.Boolean.bool_or(
                row["state"] == "finished",
                weave.ops.Boolean.bool_or(
                    row["state"] == "crashed",
                    row["state"] == "failed",
                ),
            ),
        ),
        hidden=True,
    )

    runs_by_user_project_plot = panels.Plot(
        finished_runs,
        x=lambda row: row["project_name"],
        x_title="Grouping",
        y_title="Count by user",
        y=lambda row: row.count(),
        label=lambda row: grouping_fn(row),
        groupby_dims=["x", "label"],
        mark="bar",
        no_legend=True,
    )

    gpu_waste_by_user_plot = panels.Plot(
        start_stop_states,
        x=lambda row: grouping_fn(row),
        x_title="Grouping",
        y_title="Run duration * gpu waste",
        y=lambda row: weave.ops.Number.__mul__(
            weave.ops.Number.__mul__(
                weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        row[timestamp_col_name].max(), row[timestamp_col_name].min()
                    ),
                ),
                1000,
            ),
            weave.ops.Number.__sub__(
                1,
                weave.ops.Number.__truediv__(
                    row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
                    100,
                ),
            ),
        ),
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Run": weave.ops.join_to_str(
                    weave.ops.make_list(
                        a=row["entity_name"][0],
                        b=row["project_name"][0],
                        c=row["run_id"][0],
                    ),
                    "/",
                ),
                "Job": row["job"][0],
                "Duration (s) * (1 - gpu %)": weave.ops.Number.__mul__(
                    weave.ops.Number.__mul__(
                        weave.ops.timedelta_total_seconds(
                            weave.ops.datetime_sub(
                                row[timestamp_col_name].max(),
                                row[timestamp_col_name].min(),
                            ),
                        ),
                        1000,
                    ),
                    weave.ops.Number.__sub__(
                        1,
                        weave.ops.Number.__truediv__(
                            row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
                            100,
                        ),
                    ),
                ),
                "Duration (s)": weave.ops.Number.__mul__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(), row[timestamp_col_name].min()
                        ),
                    ),
                    1000,
                ),
                "Gpu util %": row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
            }
        ),
        label=lambda row: row["run_id"],
        groupby_dims=["x", "label"],
        mark="bar",
        no_legend=True,
    )

    def make_metric_plot(metric_name: str, y_title: str) -> panels.Plot:
        return panels.Plot(
            finished_runs,
            x=lambda row: row[timestamp_col_name],
            x_title=timestamp_col_name,
            y=lambda row: list_.List.concat(
                row["metrics"]["system"][metric_name]
            ).avg(),
            y_title=y_title,
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "user": row["entity_name"][0],
                    "run id": row["run_id"][-1],
                    "job": row["job"][0],
                    "project": row["project_name"][0],
                    "min": row["metrics"]["system"][metric_name][0].min(),
                    "max": row["metrics"]["system"][metric_name][0].max(),
                    "avg": row["metrics"]["system"][metric_name][0].avg(),
                }
            ),
            groupby_dims=["x"],
            mark="line",
            no_legend=True,
            domain_x=bin_range,
            domain_y=weave_internal.make_const_node(
                types.List(types.Number()), [0, 100]
            ),
        )

    cpu_plot = make_metric_plot("cpu_cores_util", "avg cpu %")
    gpu_plot = make_metric_plot("gpu_cores_util", "avg gpu %")
    gpu_memory_plot = make_metric_plot("gpu_cores_mem", "avg gpu memory util %")
    memory_plot = weave.panels.Plot(
        finished_runs,
        x=lambda row: row[timestamp_col_name],
        x_title=timestamp_col_name,
        y=lambda row: row["metrics"]["system"]["memory"][0],
        y_title="system memory used (MB)",
        tooltip=lambda row: weave.ops.dict_(
            **{
                "user": row["entity_name"][0],
                "run id": row["run_id"][-1],
                "job": row["job"][0],
                "project": row["project_name"][0],
                "memory": row["metrics"]["system"]["memory"][0],
            }
        ),
        groupby_dims=["x"],
        mark="line",
        no_legend=True,
        domain_x=user_zoom_range,
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
    dashboard.add(
        "Job_status",
        state_transitions_plot,
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )
    dashboard.add(
        "Queued_time",
        queued_time_plot,
        layout=panels.GroupPanelLayout(x=0, y=6, w=12, h=8),
    )
    dashboard.add(
        "Lastest_runs",
        latest_runs_plot,
        layout=panels.GroupPanelLayout(x=12, y=6, w=12, h=8),
    )
    dashboard.add(
        "Longest_jobs",
        jobs_table,
        layout=panels.GroupPanelLayout(x=0, y=14, w=12, h=8),
    )
    dashboard.add(
        "Runs_by_user",
        runs_table,
        layout=panels.GroupPanelLayout(x=12, y=14, w=12, h=8),
    )
    dashboard.add(
        "Runs_by_project",
        runs_by_user_project_plot,
        layout=panels.GroupPanelLayout(x=0, y=22, w=12, h=6),
    )
    dashboard.add(
        "Gpu_waste_by_user",
        gpu_waste_by_user_plot,
        layout=panels.GroupPanelLayout(x=12, y=22, w=12, h=6),
    )
    dashboard.add(
        "Cpu_usage_on_run_finish",
        cpu_plot,
        layout=panels.GroupPanelLayout(x=0, y=28, w=12, h=6),
    )
    dashboard.add(
        "System_memory_on_run_finish",
        memory_plot,
        layout=panels.GroupPanelLayout(x=12, y=28, w=12, h=6),
    )
    dashboard.add(
        "Gpu_usage_on_run_finish",
        gpu_plot,
        layout=panels.GroupPanelLayout(x=0, y=34, w=12, h=6),
    )
    dashboard.add(
        "Gpu_memory_on_run_finish",
        gpu_memory_plot,
        layout=panels.GroupPanelLayout(x=12, y=34, w=12, h=6),
    )
    dashboard.add(
        "Errors",
        errors_table,
        layout=panels.GroupPanelLayout(x=0, y=40, w=24, h=8),
    )

    return panels.Board(vars=varbar, panels=dashboard, editable=False)


template_registry.register(
    "py_board-observability",
    "Launch Observability",
    "Seed a board with an observability view to track Launch queue performance.",
)
