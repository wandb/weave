import weave

from ..panels_py import panel_autoboard
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
            color_title="state",
            x_domain=user_zoom_range,
            n_bins=101,
            mark="bar",
        ),
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    grouping_fn_2 = varbar.add(
        "grouping_fn_2",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["trace_id"]
        ),
        hidden=True,
    )

    group_by_state = varbar.add(
        "grouping_fn_3",
        weave_internal.define_fn(
            {"row": input_node.type.object_type}, lambda row: row["state"]
        ),
        hidden=True,
    )

    pending = filtered_data.filter(
        weave_internal.define_fn(
            {"row": source_data.type.object_type},
            lambda row: weave.ops.Boolean.bool_or(
                row["state"] == "rqi_launched",
                row["state"] == "rqi_pending",
            ),
        )
    )

    # f = weave.ops.arrow.arrow_as_array(pending)
    # f.groupby(lambda row: row["trace_id"]).map(
    #     lambda run: weave.ops.dict_(r=run["trace_id"])
    # )

    queued_durations_grouped = pending.groupby(lambda row: row["trace_id"])
    # t = (
    #     weave.ops.make_list(**{str(i): x for i, x in enumerate(pending.limit(20))})
    #     .concat()
    #     .groupby(lambda row: row["trace_id"])
    # )
    # queued_durations_mapped = t.map(
    queued_durations_mapped = queued_durations_grouped.map(
        lambda run: weave.ops.dict_(
            queued_time=weave.ops.timedelta_total_seconds(
                weave.ops.datetime_sub(
                    run[timestamp_col_name].max(), run[timestamp_col_name].min()
                )
            ),
            run_id=run["run_id"],
            trace_id=run["trace_id"],
            project_name=run["project_name"],
            entity_name=run["entity_name"],
            enqueued=run[timestamp_col_name].min(),
        )
    )

    qq = queued_durations_mapped.filter(lambda row: row["queued_time"] > 0)

    # .sort(
    #     lambda row: row["queued_time"], sort_dir="desc"
    # )

    overview_tab.add(
        "States",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key=timestamp_col_name,
            y_expr=lambda row: row.count(),
            y_title="States",
            color_expr=lambda row: group_by_state(row),
            color_title="state",
            x_domain=user_zoom_range,
            n_bins=80,
            mark="bar",
        ),
        layout=panels.GroupPanelLayout(x=0, y=0, w=24, h=6),
    )

    overview_tab.add(
        "Queued_time",
        panels.Plot(
            qq,
            x=lambda row: row["enqueued"].bin(
                weave.ops.timestamp_bins_nice(bin_range, 30)
            ),
            x_title="Time",
            y=lambda row: row["queued_time"],
            y_title="Time spent queued",
            label=lambda row: row["run_id"],
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "project": row["project_name"],
                    "user": row["entity_name"],
                    "duration": row["queued_time"],
                }
            ),
            color_title="id",
            color=lambda row: row["queued_time"],
            groupby_dims=["x"],
            mark="bar",
            no_legend=True,
            domain_x=user_zoom_range,
        ),
        layout=panels.GroupPanelLayout(x=0, y=0, w=12, h=8),
    )

    overview_tab.add(
        "Latest_runs",
        panels.Plot(
            pending.sort(lambda row: row[timestamp_col_name], sort_dir="desc").limit(
                20
            ),
            x=lambda row: row[timestamp_col_name].bin(
                weave.ops.timestamp_bins_nice(bin_range, 50)
            )["start"],
            x_title=timestamp_col_name,
            y=lambda row: row["state"].count(),
            y_title="group",
            label=lambda row: grouping_fn(row),
            tooltip=lambda row: weave.ops.dict_(
                **{
                    "project(s)": weave.ops.join_to_str(
                        row["project_name"].unique(), ","
                    ),
                    "entities(s)": weave.ops.join_to_str(
                        row["entity_name"].unique(), ","
                    ),
                    "state": row["state"][0],
                    "count": row.count(),
                    "total seconds": weave.ops.timedelta_total_seconds(
                        weave.ops.datetime_sub(
                            row[timestamp_col_name].max(), row[timestamp_col_name].min()
                        )
                    ),
                }
            ),
            color_title="id",
            groupby_dims=["x", "label"],  #  "tooltip"
            mark="line",
            no_legend=True,
            domain_x=user_zoom_range,
        ),
        layout=panels.GroupPanelLayout(x=12, y=6, w=12, h=8),
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
        layout=panels.GroupPanelLayout(x=0, y=12, w=24, h=6),
    )

    table = panels.Table(filtered_window_data)
    table.add_column(lambda row: row["state"], "State", groupby=True)
    table.add_column(lambda row: row.count(), "Count")
    overview_tab.add(
        "runs_by_state_table",
        table,
        layout=panels.GroupPanelLayout(x=0, y=8, w=12, h=8),
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
        layout=panels.GroupPanelLayout(x=12, y=8, w=12, h=8),
    )

    plot = weave.panels.Plot(
        filtered_data.filter(
            weave_internal.define_fn(
                {"row": source_data.type.object_type},
                lambda row: row["state"] == "finished",
            )
        ),
        # x=lambda row: row[timestamp_col_name].bin(
        #     weave.ops.timestamp_bins_nice(bin_range, 30)
        # )[
        #     "start"
        # ],  # ["start"],
        x=lambda row: row[timestamp_col_name],
        x_title=timestamp_col_name,
        y=lambda row: weave.ops.make_list(
            a=row["metrics"]["system"]["cpu_cores_util"][0].min(),
            b=row["metrics"]["system"]["cpu_cores_util"][0].avg(),
            c=row["metrics"]["system"]["cpu_cores_util"][0].max(),
        ),
        y_title="min, max, avg cpu %",
        label=lambda row: row["metrics"]["system"]["cpu_cores_util"].avg(),
        tooltip=lambda row: weave.ops.dict_(
            **{
                "min": row["metrics"]["system"]["cpu_cores_util"],
                "max": row["metrics"]["system"]["cpu_cores_util"],
                "avg": row["metrics"]["system"]["cpu_cores_util"],
            }
        ),
        color=lambda row: row["metrics"]["system"]["cpu_cores_util"].avg(),
        groupby_dims=["x", "label"],
        mark="boxplot",
        no_legend=True,
        domain_x=user_zoom_range,
    )

    overview_tab.add(
        "cpu_usage_on_run_finish",
        plot,
        layout=panels.GroupPanelLayout(x=0, y=26, w=24, h=6),
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
        layout=panels.GroupPanelLayout(x=0, y=32, w=24, h=8),
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
        layout=panels.GroupPanelLayout(x=0, y=32, w=12, h=8),
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
