import weave

from .. import weave_types as types
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

    display_states = weave.ops.dict_(
        **{
            "running": "running",
            "failed": "failed",
            "crashed": "crashed",
            "finished": "finished",
            "starting": "pending",
            "failed_rqi": "failed rqi",
            "queued": "queued",
            "popped": "TO_REMOVE",  # gets filtered out
        }
    )

    varbar = panel_board.varbar(editable=False)
    source_data = input_node.map(
        lambda row: weave.ops.dict_(
            **{
                "timestamp": row[timestamp_col_name],
                "entity_name": row["entity_name"],
                "project_name": row["project_name"],
                "queue_uri": row["queue_uri"],
                "sweep_id": row["sweep_id"],
                "run_id": row["run_id"],
                "job": row["job"],
                "trace_id": row["trace_id"],
                "state": display_states.pick(row["state"]),
                "error": row["error"],
                "metrics": row["metrics"],
            }
        )
    )

    filter_fn = varbar.add(
        "filter_fn",
        weave_internal.define_fn(
            {"row": source_data.type.object_type},
            lambda row: weave_internal.const(True),
        ),
        hidden=True,
    )

    group_by_user = weave_internal.define_fn(
        {"row": source_data.type.object_type}, lambda row: row["entity_name"]
    )

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": source_data.type.object_type}, lambda row: row["entity_name"]
        ),
        hidden=True,
    )

    seven_days_in_seconds = 60 * 60 * 24 * 7
    window_start = varbar.add(
        "window_start",
        weave.ops.from_number(now - seven_days_in_seconds),
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

    user_zoom_range = varbar.add(
        "user_zoom_range",
        filtered_range,
        hidden=True,
    )
    varbar.add(
        "Time_range",
        panels.DateRange(user_zoom_range, domain=filtered_range),
    )
    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )

    window_data = source_data.filter(
        lambda row: weave.ops.Boolean.bool_and(
            row["state"] != "TO_REMOVE",  # remove hidden states
            weave.ops.Boolean.bool_and(
                row[timestamp_col_name] >= bin_range[0],
                row[timestamp_col_name] <= bin_range[1],
            ),
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
            "pending": "rgb(125, 177, 250)",
            "failed rqi": "rgb(255, 199, 202)",
            "queued": "rgb(211, 215, 222)",
        }
    )

    state_color_func = weave_internal.define_fn(
        {"row": source_data.type.object_type},
        lambda row: colors_node.pick(row["state"]),
    )

    queued_time_data = varbar.add(
        "queued_time_data",
        filtered_window_data.filter(
            lambda row: weave.ops.Boolean.bool_or(
                row["state"] == "queued",
                row["state"] == "pending",
            ),
        ),
        hidden=True,
    )

    is_start_stop_state = weave_internal.define_fn(
        {"row": source_data.type.object_type},
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
                "State": row["state"][0],
                "Count": row.count(),
                "Job (s)": weave.ops.join_to_str(row["job"].unique(), ","),
            }
        ),
        color_title="state",
        color=state_color_func.val,
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=user_zoom_range,
    )

    runs_grouped = weave.ops.List.groupby(queued_time_data, lambda row: row["trace_id"])
    runs_mapped = weave.ops.List.map(
        runs_grouped,
        lambda row: weave.ops.dict_(
            **{
                "trace_id": row["trace_id"][0],
                "entity_name": row["entity_name"][0],
                "project_name": row["project_name"][0],
                "run_id": row["run_id"][-1],
                "job": row["job"][-1],
                "enqueued": row[timestamp_col_name][0],
                "run_start": row[timestamp_col_name][-1],
                "duration": weave.ops.Number.__truediv__(
                    weave.ops.Number.__mul__(
                        weave.ops.timedelta_total_seconds(
                            weave.ops.datetime_sub(
                                row[timestamp_col_name].max(),
                                row[timestamp_col_name].min(),
                            ),
                        ),
                        1000,
                    ),
                    60,
                ),
            }
        ),
    )
    runs_mapped_filtered = varbar.add(
        "runs_mapped_filtered",
        weave.ops.List.filter(
            runs_mapped,
            lambda row: row["duration"] >= 0,
        ),
        hidden=True,
    )

    queued_time_plot = panels.Plot(
        runs_mapped_filtered,
        x=lambda row: row["run_start"].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets)
        ),
        x_title="Time",
        y=lambda row: row["duration"].sum(),
        y_title="Time spent queued (m)",
        label=lambda row: grouping_fn(row),
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Job (s)": weave.ops.join_to_str(row["job"].unique(), ","),
                "User (s)": weave.ops.join_to_str(row["entity_name"].unique(), ","),
                "Project (s)": weave.ops.join_to_str(row["project_name"].unique(), ","),
                "Duration (m)": row["duration"].sum(),
                "Run count": row.count(),
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

    latest_runs_plot = panels.Plot(
        start_stop_states,
        x=lambda row: row[timestamp_col_name],
        x_title="Time",
        y_title="Job",
        y=lambda row: row["job"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Job": row["job"][0],
                "User": row["entity_name"][0],
                "Team": row["queue_uri"][0].split(":").index(2),
                "Project": row["project_name"][0],
                "Run ID": row["run_id"][-1],
                "Status": row["state"][-1],
                "Duration (m)": weave.ops.Number.__truediv__(
                    weave.ops.Number.__mul__(
                        weave.ops.timedelta_total_seconds(
                            weave.ops.datetime_sub(
                                row[timestamp_col_name].max(),
                                row[timestamp_col_name].min(),
                            ),
                        ),
                        1000,
                    ),
                    60,
                ),
            }
        ),
        label=lambda row: row["run_id"],
        groupby_dims=["label"],
        color_title="User",
        color=group_by_user.val,
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
    jobs_table.add_column(lambda row: row["run_id"], "Run", groupby=True)
    jobs_table.add_column(
        lambda row: weave.ops.run_ops.str_run_link(
            entity_name=row["queue_uri"][0].split(":").index(2),
            project_name=row["project_name"][0],
            name=row["run_id"][0],
        ),
        "Link",
        panel_def="link",
    )
    jobs_table.add_column(lambda row: row["job"][0], "Job")
    jobs_table.add_column(lambda row: row["entity_name"][0], "User")
    jobs_table.add_column(
        lambda row: row[timestamp_col_name][0], "Start Time", sort_dir="desc"
    )
    jobs_table.add_column(
        lambda row: row["state"][-1],
        "Current state",
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=weave.ops.Number.__truediv__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(),
                            row[timestamp_col_name].min(),
                        )
                    ),
                    60,
                ),
                b=weave.ops.Number.__truediv__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            weave.ops.from_number(weave.ops.datetime_now()),
                            row[timestamp_col_name].min(),
                        )
                    ),
                    60,
                ),
            ),
        ),
        "Runtime (m)",
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
                b=weave.ops.make_const_node(types.NoneType(), None),
            ),
        ),
        "Avg. CPU %",
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
                b=weave.ops.make_const_node(types.NoneType(), None),
            ),
        ),
        "Avg. GPU %",
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=row["metrics"]["system"]["gpu_cores_mem"][-1].avg(),
                b=weave.ops.make_const_node(types.NoneType(), None),
            ),
        ),
        "Avg. GPU mem. %",
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=row["metrics"]["system"]["memory"][-1],
                b=weave.ops.make_const_node(types.NoneType(), None),
            ),
        ),
        "Avg. mem (MB)",
    )

    runs_table_data = weave.ops.List.groupby(
        filtered_window_data, lambda row: row["trace_id"]
    )
    runs_table_data_mapped = varbar.add(
        "runs_table_data",
        weave.ops.List.map(
            runs_table_data,
            lambda row: weave.ops.dict_(
                **{
                    "trace_id": row["trace_id"][0],
                    "user": row["entity_name"][0],
                    "run_ids": row["run_id"],
                    "states": row["state"],
                }
            ),
        ),
        hidden=True,
    )
    runs_table = panels.Table(runs_table_data_mapped)  # type: ignore
    runs_table.add_column(lambda row: row["user"], "User", groupby=True)
    runs_table.add_column(
        lambda row: row.count(),
        "Queued",
        sort_dir="desc",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["states"][-1] == "failed rqi").count(),
        "Failed to start",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["states"][2] == "running").count(),
        "Started",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["states"][-1] == "running").count(),
        "Running",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["states"][-1] == "finished").count(),
        "Finished",
    )
    runs_table.add_column(
        lambda row: row.filter(
            lambda row: weave.ops.Boolean.bool_or(
                row["states"][-1] == "crashed",
                row["states"][-1] == "failed",
            ),
        ).count(),
        "Crashed",
    )

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

    runs_user_and_grouping_plot = panels.Plot(
        finished_runs,
        x=lambda row: row.count(),
        x_title="Count",
        y_title="Grouping",
        y=lambda row: grouping_fn(row),
        label=lambda row: grouping_fn(row),
        groupby_dims=["label"],
        mark="bar",
        no_legend=True,
    )

    metric_plot_data = weave.ops.List.groupby(
        start_stop_states, lambda row: row["trace_id"]
    )
    metric_plot_data_mapped = varbar.add(
        "metric_plot_data",
        weave.ops.List.map(
            metric_plot_data,
            lambda row: weave.ops.dict_(
                **{
                    "trace_id": row["trace_id"][0],
                    "run_id": row["run_id"][-1],
                    "entity_name": row["entity_name"][0],
                    "project_name": row["project_name"][0],
                    "job": row["job"][0],
                    "duration": weave.ops.Number.__truediv__(
                        weave.ops.Number.__mul__(
                            weave.ops.timedelta_total_seconds(
                                weave.ops.datetime_sub(
                                    row[timestamp_col_name].max(),
                                    row[timestamp_col_name].min(),
                                ),
                            ),
                            1000,
                        ),
                        60,
                    ),
                    "GPU util %": row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
                    "CPU util %": row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
                    "GPU memory %": row["metrics"]["system"]["gpu_cores_mem"][-1].avg(),
                    "Memory (MB)": row["metrics"]["system"]["memory"][-1],
                }
            ),
        ),
        hidden=True,
    )

    gpu_waste_by_user_plot = panels.Plot(
        metric_plot_data_mapped,
        x=lambda row: row["duration"],
        x_title="Run duration (minutes)",
        y_title="GPU utilization (%)",
        y=lambda row: row["GPU util %"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Run ID": row["run_id"],
                "Project": row["project_name"],
                "User": row["entity_name"],
                "Job": row["job"],
                "Duration (m)": row["duration"],
                "GPU util %": row["GPU util %"],
            }
        ),
        color_title="Grouping",
        label=lambda row: grouping_fn(row),
        color=lambda row: grouping_fn(row),
        groupby_dims=[],
        mark="point",
        domain_y=weave_internal.make_const_node(types.List(types.Number()), [0, 100]),
    )

    cpu_waste_by_user_plot = panels.Plot(
        metric_plot_data_mapped,
        x=lambda row: row["duration"],
        x_title="Run duration (minutes)",
        y_title="CPU utilization (%)",
        y=lambda row: row["CPU util %"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Run ID": row["run_id"],
                "Project": row["project_name"],
                "User": row["entity_name"],
                "Job": row["job"],
                "Duration (m)": row["duration"],
                "CPU util %": row["CPU util %"],
            }
        ),
        color_title="Grouping",
        label=lambda row: grouping_fn(row),
        color=lambda row: grouping_fn(row),
        groupby_dims=[],
        mark="point",
        domain_y=weave_internal.make_const_node(types.List(types.Number()), [0, 100]),
    )

    gpu_mem_by_user_plot = panels.Plot(
        metric_plot_data_mapped,
        x=lambda row: row["duration"],
        x_title="Run duration (minutes)",
        y_title="GPU memory (%)",
        y=lambda row: row["GPU memory %"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Run ID": row["run_id"],
                "Project": row["project_name"],
                "User": row["entity_name"],
                "Job": row["job"],
                "Duration (m)": row["duration"],
                "GPU memory (%)": row["GPU memory %"],
            }
        ),
        color_title="Grouping",
        label=lambda row: grouping_fn(row),
        color=lambda row: grouping_fn(row),
        groupby_dims=[],
        mark="point",
        domain_y=weave_internal.make_const_node(types.List(types.Number()), [0, 100]),
    )

    memory_by_user_plot = panels.Plot(
        metric_plot_data_mapped,
        x=lambda row: row["duration"],
        x_title="Run duration (minutes)",
        y_title="Memory usage (MB)",
        y=lambda row: row["Memory (MB)"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "Run ID": row["run_id"],
                "Project": row["project_name"],
                "User": row["entity_name"],
                "Job": row["job"],
                "Duration (m)": row["duration"],
                "Memory (MB)": row["Memory (MB)"],
            }
        ),
        color_title="Grouping",
        label=lambda row: grouping_fn(row),
        color=lambda row: grouping_fn(row),
        groupby_dims=[],
        mark="point",
    )

    errors_table = panels.Table(  # type: ignore
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["error"] != None,
            )
        )
    )
    errors_table.add_column(
        lambda row: row[timestamp_col_name], "Timestamp", sort_dir="desc"
    )
    errors_table.add_column(lambda row: row["job"], "Job")
    errors_table.add_column(lambda row: row["error"], "Error", panel_def="object")

    # layout
    dashboard.add(
        "Job_run_status",
        state_transitions_plot,
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )
    dashboard.add(
        "Job_run_table",
        jobs_table,
        layout=panels.GroupPanelLayout(x=0, y=6, w=24, h=8),
    )
    dashboard.add(
        "Queued_time",
        queued_time_plot,
        layout=panels.GroupPanelLayout(x=0, y=14, w=24, h=6),
    )
    latest_runs_plot_selector = dashboard.add(
        "Job_runs",
        latest_runs_plot,
        layout=panels.GroupPanelLayout(x=0, y=20, w=24, h=6),
    )
    selected_jobs = panels.Table(latest_runs_plot_selector.selected_rows())  # type: ignore
    selected_jobs.add_column(
        lambda row: weave.ops.run_ops.str_run_link(
            entity_name=row["c_4.Team"],
            project_name=row["c_4.Project"],
            name=row["c_4.Run ID"],
        ),
        "Run",
        panel_def="link",
        groupby=True,
    )
    selected_jobs.add_column(lambda row: row["c_4.Job"][0], "Job")
    selected_jobs.add_column(lambda row: row["c_4.User"][0], "User")
    selected_jobs.add_column(lambda row: row["c_4.Project"][0], "Project")
    selected_jobs.add_column(lambda row: row["c_4.Status"][-1], "Status")
    selected_jobs.add_column(lambda row: row["c_2"].min(), "Start")
    selected_jobs.add_column(lambda row: row["c_2"].max(), "Stop")
    selected_jobs.add_column(lambda row: row["c_4.Duration (m)"][0], "Duration (m)")

    dashboard.add(
        "Selected_job_runs",
        selected_jobs,
        layout=panels.GroupPanelLayout(x=0, y=26, w=24, h=10),
    )
    dashboard.add(
        "Runs_by_user",
        runs_table,
        layout=panels.GroupPanelLayout(x=10, y=36, w=14, h=8),
    )
    dashboard.add(
        "GPU_use_by_job_run",
        gpu_waste_by_user_plot,
        layout=panels.GroupPanelLayout(x=0, y=44, w=12, h=8),
    )
    dashboard.add(
        "CPU_use_by_job_run",
        cpu_waste_by_user_plot,
        layout=panels.GroupPanelLayout(x=12, y=44, w=12, h=8),
    )
    dashboard.add(
        "GPU_memory_by_job_run",
        gpu_mem_by_user_plot,
        layout=panels.GroupPanelLayout(x=0, y=52, w=12, h=8),
    )
    dashboard.add(
        "System_memory_by_job_run",
        memory_by_user_plot,
        layout=panels.GroupPanelLayout(x=12, y=52, w=12, h=8),
    )
    dashboard.add(
        "Finished_runs_by_grouping",
        runs_user_and_grouping_plot,
        layout=panels.GroupPanelLayout(x=0, y=34, w=10, h=8),
    )
    dashboard.add(
        "Errors",
        errors_table,
        layout=panels.GroupPanelLayout(x=0, y=60, w=24, h=8),
    )

    return panels.Board(vars=varbar, panels=dashboard, editable=False)


template_registry.register(
    "py_board-observability",
    "Launch Observability",
    "Seed a board with an observability view to track Launch queue performance.",
)
