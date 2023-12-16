import weave
from weave.panels.panel_plot import selected_rows

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


@weave.op(weavify=True, input_type={"grouped_row": types.TypedDict({})})  # type: ignore
def compute_run_duration(grouped_row) -> float:  # type: ignore
    timestamp_col_name = "timestamp"
    duration = weave.ops.case(
        [
            {
                "when": weave.ops.Boolean.bool_or(
                    grouped_row["state"][-1] == "finished",
                    weave.ops.Boolean.bool_or(
                        grouped_row["state"][-1] == "crashed",
                        grouped_row["state"][-1] == "failed",
                    ),
                ),
                "then": weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        grouped_row[timestamp_col_name].max(),
                        grouped_row[timestamp_col_name].min(),
                    )
                ),
            },
            {
                "when": weave.ops.Boolean.bool_not(
                    weave.ops.Boolean.bool_or(
                        grouped_row["state"][-1] == "finished",
                        weave.ops.Boolean.bool_or(
                            grouped_row["state"][-1] == "crashed",
                            grouped_row["state"][-1] == "failed",
                        ),
                    )
                ),
                "then": weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        weave.ops.from_number(weave.ops.datetime_now()),
                        grouped_row[timestamp_col_name].min(),
                    )
                ),
            },
        ],
    )

    return duration


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
                "timestamp": row["timestamp"],
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
        {"row": input_node.type.object_type}, lambda row: row["entity_name"]
    )

    grouping_fn = varbar.add(
        "grouping_fn",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["entity_name"]
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
        {"row": input_node.type.object_type},
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
                "job (s)": weave.ops.cond(
                    weave.ops.dict_(
                        a=row["job"].unique().count() <= 3,
                        b=row["job"].unique().count() > 3,
                    ),
                    weave.ops.dict_(
                        a=weave.ops.join_to_str(row["job"].unique(), ","),
                        # b=weave.ops.join_to_str(
                        #     weave.ops.make_list(
                        #         a=row["job"].unique(),
                        #         b=weave.ops.make_list(
                        #             a=weave_internal.make_const_node(
                        #                 types.String(),
                        #                 f"... ({row.count() - 3} more)",
                        #             ),
                        #         ),
                        #     ).concat(),
                        #     ",",
                        # ),
                        b=weave.ops.join_to_str(
                            weave.ops.make_list(
                                a=weave.ops.join_to_str(
                                    weave.ops.make_list(
                                        **{
                                            i: job
                                            for i, job in enumerate(row["job"].unique())
                                        }
                                    ),
                                    ",",
                                ),
                                b=weave_internal.make_const_node(
                                    types.String(),
                                    f"... ({row.count() - 3} more)",
                                ),
                            ),
                            ",",
                        ),
                        # b=weave.ops.join_to_str(row["job"].unique(), ","),
                    ),
                ),
            }
        ),
        color_title="state",
        color=state_color_func.val,
        groupby_dims=["x", "label"],
        mark="bar",
        domain_x=user_zoom_range,
    )

    selected_statuses = panels.Table(selected_rows(state_transitions_plot))
    selected_statuses.add_column(
        lambda row: row[timestamp_col_name], "Timestamp", sort_dir="desc"
    )
    selected_statuses.add_column(lambda row: row["state"], "State")
    selected_statuses.add_column(lambda row: row["job"], "Job")
    selected_statuses.add_column(lambda row: row["entity_name"], "User")
    selected_statuses.add_column(lambda row: row["project_name"], "Project")
    selected_statuses.add_column(lambda row: row["error"], "Error")

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
                "start": row[timestamp_col_name][0],
                "duration": weave.ops.Number.__mul__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(), row[timestamp_col_name].min()
                        ),
                    ),
                    1000,
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
        x=lambda row: row["start"].bin(
            weave.ops.timestamp_bins_nice(bin_range, num_buckets)
        ),
        x_title="Time",
        y=lambda row: row["duration"],
        y_title="Time spent queued",
        label=lambda row: row["entity_name"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "job": row["job"],
                "user": row["entity_name"],
                "project": row["project_name"],
                "run ID": row["run_id"],
                "job": row["job"],
                "duration (s)": row["duration"],
            }
        ),
        color=group_by_user.val,
        color_title="Grouping",
        groupby_dims=[],
        mark="bar",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    start_stop_states = varbar.add(
        "start_stop_states",
        weave.ops.List.filter(filtered_window_data, is_start_stop_state),
        hidden=True,
    )

    start_stop_states_grouped = weave.ops.List.groupby(
        start_stop_states, lambda row: row["trace_id"]
    )
    start_stop_states_mapped = weave.ops.List.map(
        start_stop_states_grouped,
        lambda row: weave.ops.dict_(
            **{
                "trace_id": row["trace_id"][0],
                "entity_name": row["entity_name"][0],
                "project_name": row["project_name"][0],
                "run_id": row["run_id"][-1],
                "job": row["job"][-1],
                "duration (s)": weave.ops.Number.__mul__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(), row[timestamp_col_name].min()
                        ),
                    ),
                    1000,
                ),
                "timestamps": row[timestamp_col_name],
            }
        ),
    )

    latest_runs_plot = panels.Plot(
        start_stop_states_mapped,
        x=lambda row: row["timestamps"],
        x_title="Time",
        y_title="Job",
        y=lambda row: row["job"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "job": row["job"],
                "user": row["entity_name"],
                "project": row["project_name"],
                "run ID": row["run_id"],
                "duration (s)": row["duration (s)"],
            }
        ),
        label=lambda row: group_by_user(row),
        groupby_dims=[],
        color_title="User",
        color=group_by_user.val,
        mark="line",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    latest_runs_plot = panels.Plot(
        start_stop_states,
        x=lambda row: row["timestamp"],
        x_title="Time",
        y_title="Job",
        y=lambda row: row["job"],
        tooltip=lambda row: weave.ops.dict_(
            **{
                "job": row["job"][0],
                "user": row["entity_name"][0],
                "project": row["project_name"][0],
                "run ID": row["run_id"][-1],
                "duration (s)": weave.ops.Number.__mul__(
                    weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(), row[timestamp_col_name].min()
                        ),
                    ),
                    1000,
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
    jobs_table.add_column(lambda row: row["run_id"], "Run ID", groupby=True)
    jobs_table.add_column(lambda row: row["job"][0], "Job")
    jobs_table.add_column(lambda row: row["entity_name"][0], "User")
    jobs_table.add_column(
        lambda row: row["timestamp"][0], "Start Time", sort_dir="desc"
    )
    jobs_table.add_column(
        lambda row: row["state"][-1],
        "Current state",
        panel_def=weave.panels.Color(12),
    )
    jobs_table.add_column(
        lambda row: weave.ops.cond(
            weave.ops.dict_(
                a=row["state"][-1] != "running",
                b=row["state"][-1] == "running",
            ),
            weave.ops.dict_(
                a=weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        row[timestamp_col_name].max(),
                        row[timestamp_col_name].min(),
                    )
                ),
                b=weave.ops.timedelta_total_seconds(
                    weave.ops.datetime_sub(
                        weave.ops.from_number(weave.ops.datetime_now()),
                        row[timestamp_col_name].min(),
                    )
                ),
            ),
        ),
        "Runtime (s)",
    )
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
        "Avg. cpu %",
    )
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
        "Avg. gpu %",
    )
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["gpu_cores_mem"][-1].avg(),
        "Avg. gpu mem. %",
    )
    jobs_table.add_column(
        lambda row: row["metrics"]["system"]["memory"][-1],
        "Avg. sys. mem (MB)",
    )

    runs_table_data = weave.ops.List.groupby(
        filtered_window_data, lambda row: row["trace_id"]
    )
    runs_table_data_mapped = weave.ops.List.map(
        runs_table_data,
        lambda row: weave.ops.dict_(
            **{
                "trace_id": row["trace_id"][0],
                "user": row["entity_name"][0],
                "run_ids": row["run_id"],
                "states": row["state"],
            }
        ),
    )
    runs_table = panels.Table(runs_table_data_mapped)  # type: ignore
    runs_table.add_column(lambda row: row["user"], "User", groupby=True)
    runs_table.add_column(lambda row: row["states"], "State")

    runs_table = panels.Table(filtered_window_data)  # type: ignore
    runs_table.add_column(lambda row: row["entity_name"], "User", groupby=True)
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["state"] == "pending").count(),
        "Jobs enqueued",
        sort_dir="desc",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["state"] == "failed rqi").count(),
        "Failed to init",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["state"] == "running").count(),
        "Started",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["state"] == "running").count(),
        "Running",
    )
    runs_table.add_column(
        lambda row: row.filter(lambda row: row["state"] == "finished").count(),
        "Finished",
    )
    runs_table.add_column(
        lambda row: row.filter(
            lambda row: weave.ops.Boolean.bool_or(
                row["state"] == "crashed",
                row["state"] == "failed",
            ),
        ).count(),
        "Failed",
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
        y_title="User",
        y=lambda row: row["entity_name"],
        label=lambda row: grouping_fn(row),
        groupby_dims=["label", "y"],
        mark="bar",
        no_legend=True,
    )

    gpu_waste_by_user_plot = panels.Plot(
        start_stop_states,
        x=lambda row: weave.ops.Number.__mul__(
            weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    row[timestamp_col_name].max(), row[timestamp_col_name].min()
                ),
            ),
            1000,
        ),
        x_title="Run duration",
        y_title="Gpu usage (%)",
        y=lambda row: row["metrics"]["system"]["gpu_cores_util"][-1].avg(),
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
                "Duration * (1 - gpu %)": weave.ops.Number.__mul__(
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
        color=group_by_user.val,
        groupby_dims=["label"],
        mark="point",
        no_legend=True,
        domain_y=weave_internal.make_const_node(types.List(types.Number()), [0, 100]),
    )

    cpu_waste_by_user_plot = panels.Plot(
        start_stop_states,
        x=lambda row: weave.ops.Number.__mul__(
            weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    row[timestamp_col_name].max(), row[timestamp_col_name].min()
                ),
            ),
            1000,
        ),
        x_title="Run duration",
        y_title="Cpu usage (%)",
        y=lambda row: row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
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
                "Duration * (1 - cpu %)": weave.ops.Number.__mul__(
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
                            row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
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
                "Cpu util %": row["metrics"]["system"]["cpu_cores_util"][-1].avg(),
            }
        ),
        label=lambda row: row["run_id"],
        color=group_by_user.val,
        groupby_dims=["label"],
        mark="point",
        no_legend=True,
        domain_y=weave_internal.make_const_node(types.List(types.Number()), [0, 100]),
    )

    errors_table = panels.Table(  # type: ignore
        filtered_window_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["error"] != None,
            )
        )
    )
    errors_table.add_column(lambda row: row["timestamp"], "Timestamp", sort_dir="desc")
    errors_table.add_column(lambda row: row["job"], "Job")
    errors_table.add_column(
        lambda row: weave.panels.WeaveLink(
            row["run_id"],
            vars={
                "entity_name": row["entity_name"],
                "project_name": row["project_name"],
                "run_id": row["run_id"],
            },
            to=lambda input, vars: weave.ops.project(
                vars["entity_name"], vars["project_name"]
            ).run(vars["run_id"]),
        ),
        "Run",
    )
    errors_table.add_column(lambda row: row["error"], "Error", panel_def="object")

    # layout
    dashboard.add(
        "Job_status",
        state_transitions_plot,
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )
    dashboard.add(
        "Selected_statuses",
        selected_statuses,
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )
    dashboard.add(
        "Queued_time",
        queued_time_plot,
        layout=panels.GroupPanelLayout(x=0, y=6, w=24, h=6),
    )
    dashboard.add(
        "Job_runs",
        latest_runs_plot,
        layout=panels.GroupPanelLayout(x=0, y=12, w=24, h=6),
    )
    dashboard.add(
        "Job_table",
        jobs_table,
        layout=panels.GroupPanelLayout(x=0, y=18, w=24, h=12),
    )
    dashboard.add(
        "Runs_by_user",
        runs_table,
        layout=panels.GroupPanelLayout(x=12, y=30, w=12, h=8),
    )
    dashboard.add(
        "Gpu_use_by_job",
        gpu_waste_by_user_plot,
        layout=panels.GroupPanelLayout(x=0, y=38, w=12, h=8),
    )
    dashboard.add(
        "Cpu_use_by_job",
        cpu_waste_by_user_plot,
        layout=panels.GroupPanelLayout(x=12, y=38, w=12, h=8),
    )
    dashboard.add(
        "Finished_runs_by_grouping",
        runs_user_and_grouping_plot,
        layout=panels.GroupPanelLayout(x=0, y=30, w=12, h=8),
    )
    dashboard.add(
        "Errors",
        errors_table,
        layout=panels.GroupPanelLayout(x=0, y=46, w=24, h=8),
    )

    return panels.Board(vars=varbar, panels=dashboard, editable=False)


template_registry.register(
    "py_board-observability",
    "Launch Observability",
    "Seed a board with an observability view to track Launch queue performance.",
)
