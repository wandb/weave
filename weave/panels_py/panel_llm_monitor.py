import os
import typing

import weave
from .. import dispatch
from .. import weave_internal as internal
from .. import weave_types as types
from .. import weave_internal
from ..panels import panel_group
from ..panels import panel_board
from ..panels_py import panel_autoboard
from .generator_templates import template_registry


panels = weave.panels
ops = weave.ops


# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "llm_completions_monitor"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "Monitor OpenAI API usage"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Use the OpenAI integration to track, monitor and analyze API calls. Understand performance and quality. Track trends and organization-wide costs."

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.
BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "inputs": types.optional(
                types.TypedDict(
                    {
                        "messages": types.optional(
                            types.List(
                                types.TypedDict(
                                    {
                                        "role": types.optional(types.String()),
                                        "content": types.optional(types.String()),
                                    }
                                )
                            )
                        )
                    }
                )
            ),
            "output": types.optional(
                types.TypedDict(
                    {
                        "id": types.optional(types.String()),
                        "object": types.optional(types.String()),
                        "model": types.optional(types.String()),
                        "choices": types.optional(
                            types.List(
                                types.TypedDict(
                                    {
                                        "message": types.optional(
                                            types.TypedDict(
                                                {
                                                    "role": types.optional(
                                                        types.String()
                                                    ),
                                                    "content": types.optional(
                                                        types.String()
                                                    ),
                                                }
                                            )
                                        ),
                                        "finish_reason": types.optional(types.String()),
                                    }
                                )
                            )
                        ),
                    }
                )
            ),
            "timestamp": types.optional(types.Timestamp()),
            "summary": types.optional(
                types.TypedDict(
                    {
                        "prompt_tokens": types.optional(types.Number()),
                        "completion_tokens": types.optional(types.Number()),
                        "total_tokens": types.optional(types.Number()),
                    }
                )
            ),
        }
    )
)


board_name = "py_board-" + BOARD_ID


# @weave.type()
# class OpenAITable(weave.Panel):
#     id = "OpenAITable"
#     input_node: weave.Node[list[typing.Any]]

#     @weave.op()
#     def render(self) -> weave.panels.Table:
#         table = panels.Table(
#             self.input_node,
#             columns=[lambda row: row["inputs"]["messages"][-1]["content"]],
#         )
#         # table.add_column( lambda row: row["inputs"]["messages"][-1]["content"], "Messages"
#         # )
#         # table.add_column(lambda row: row["messages"][-1]["content"], "Message")
#         return table

API_COST_INPUT_TYPE = types.TypedDict(
    {
        "output": types.optional(
            types.TypedDict(
                {
                    "model": types.optional(types.String()),
                }
            )
        ),
        "summary": types.optional(
            types.TypedDict(
                {
                    "prompt_tokens": types.optional(types.Number()),
                    "completion_tokens": types.optional(types.Number()),
                }
            )
        ),
    }
)


@weave.op(weavify=True, input_type={"record": API_COST_INPUT_TYPE})  # type: ignore
def openai_request_cost(record) -> float:  # type: ignore
    model = record["output.model"]
    pt = record["summary.prompt_tokens"]
    ct = record["summary.completion_tokens"]
    cost_per_1000 = weave.ops.case(
        [
            # finetuned
            {"when": model.startsWith("ada:"), "then": pt * 0.0016 + ct * 0.0016},
            {"when": model.startsWith("babbage:"), "then": pt * 0.0024 + ct * 0.0024},
            {"when": model.startsWith("curie:"), "then": pt * 0.012 + ct * 0.012},
            {"when": model.startsWith("davinci:"), "then": pt * 0.12 + ct * 0.12},
            # non-finetuned
            {"when": model == "gpt-4-32k-0314", "then": pt * 0.06 + ct * 0.12},
            {"when": model == "gpt-4-32k-0613", "then": pt * 0.06 + ct * 0.12},
            {"when": model == "gpt-3.5-turbo-0613", "then": pt * 0.0015 + ct * 0.002},
            {
                "when": model == "gpt-3.5-turbo-16k-0613",
                "then": pt * 0.003 + ct * 0.004,
            },
            {
                "when": model == "text-embedding-ada-002-v2",
                "then": pt * 0.0001 + ct * 0.0001,
            },
            {"when": model == "ada", "then": pt * 0.0004 + ct * 0.0004},
            {"when": model == "babbage", "then": pt * 0.0005 + ct * 0.0005},
            {"when": model == "curie", "then": pt * 0.002 + ct * 0.002},
            {"when": model == "davinci", "then": pt * 0.02 + ct * 0.02},
            {
                "when": model.startsWith("gpt-3.5-turbo"),
                "then": pt * 0.002 + ct * 0.002,
            },
            {"when": model.startsWith("gpt-4"), "then": pt * 0.03 + ct * 0.06},
            {"when": True, "then": 0},
        ]
    )
    return cost_per_1000 / 1000  # type: ignore


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

    source_data = varbar.add("source_data", input_node)

    augmented_data = varbar.add(
        "augmented_data",
        source_data.with_columns(
            weave.ops.dict_(
                **{
                    "summary.cost": source_data.map(
                        lambda row: openai_request_cost(row)
                    )
                }
            )
        ),
        hidden=True,
    )

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
            {"row": input_node.type.object_type}, lambda row: row["output.model"]
        ),
        hidden=True,
    )

    filtered_data = varbar.add(
        "filtered_data", augmented_data.filter(filter_fn), hidden=True
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
        weave.panels.DateRange(user_zoom_range, domain=source_data[timestamp_col_name]),
    )

    ## 3. bin_range is derived from user_zoom_range and raw_data_range. This is
    ##    the range of data that will be displayed in the charts.
    bin_range = varbar.add(
        "bin_range", user_zoom_range.coalesce(filtered_range), hidden=True
    )
    # Derive the windowed data to use in the plots as a function of bin_range

    window_data = varbar.add(
        "window_data",
        augmented_data.filter(
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

    height = 5

    ### Overview tab

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
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=height),
    )

    overview_tab.add(
        "cost",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row["summary.cost"].sum(),
            y_title="total cost ($)",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=height, w=12, h=height),
    )

    overview_tab.add(
        "latency",
        panel_autoboard.timeseries(
            filtered_data,
            bin_domain_node=bin_range,
            x_axis_key="timestamp",
            y_expr=lambda row: row["summary.latency_s"].avg(),
            y_title="avg latency (s)",
            color_expr=lambda row: grouping_fn(row),
            color_title="group",
            x_domain=user_zoom_range,
            n_bins=50,
        ),
        layout=weave.panels.GroupPanelLayout(x=12, y=height, w=12, h=height),
    )

    overview_tab.add(
        "avg_cost_per_req",
        filtered_window_data["summary.cost"].avg(),  # type: ignore
        layout=weave.panels.GroupPanelLayout(x=0, y=height * 2, w=6, h=3),
    )
    overview_tab.add(
        "avg_prompt_tokens_per_req",
        filtered_window_data["summary.prompt_tokens"].avg(),  # type: ignore
        layout=weave.panels.GroupPanelLayout(x=6, y=height * 2, w=6, h=3),
    )
    overview_tab.add(
        "avg_completion_tokens_per_req",
        filtered_window_data["summary.completion_tokens"].avg(),  # type: ignore
        layout=weave.panels.GroupPanelLayout(x=12, y=height * 2, w=6, h=3),
    )
    overview_tab.add(
        "avg_total_tokens_per_req",
        filtered_window_data["summary.total_tokens"].avg(),  # type: ignore
        layout=weave.panels.GroupPanelLayout(x=18, y=height * 2, w=6, h=3),
    ),

    # Show a plot for each attribute.
    # TODO: This doesn't really work yet (needs some manual UI configuration currently,
    # and it's ugly).
    # overview_tab.add(
    #     "attributes", weave.panels.EachColumn(filtered_window_data["attributes"])
    # )

    ### Requests tab

    # requests_tab = weave.panels.Group(
    #     layoutMode="grid",
    #     showExpressions=True,
    # )  # l, showExpressions="titleBar")

    requests_table = panels.Table(filtered_window_data)  # type: ignore
    requests_table.add_column(lambda row: row["output.model"], "Model")
    requests_table.add_column(
        lambda row: row["inputs.messages"][-1]["content"], "Last Prompt"
    )
    requests_table.add_column(
        lambda row: row["output.choices"][-1]["message.content"],
        "Completion",
    )
    requests_table.add_column(lambda row: row["summary.prompt_tokens"], "Prompt Tokens")
    requests_table.add_column(
        lambda row: row["summary.completion_tokens"], "Completion Tokens"
    )
    requests_table.add_column(lambda row: row["summary.total_tokens"], "Total Tokens")
    requests_table.add_column(lambda row: row["summary.latency_s"], "Latency")
    requests_table.add_column(lambda row: row["summary.cost"], "Cost")
    requests_table.add_column(
        lambda row: row["timestamp"], "Timestamp", sort_dir="desc"
    )

    requests_table_var = overview_tab.add(
        "table",
        requests_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=13, w=24, h=8),
    )
    overview_tab.add(
        "input",
        panels.Table(  # type: ignore
            requests_table_var.active_data()["inputs.messages"],
            columns=[lambda row: row["role"], lambda row: row["content"]],
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=21, w=12, h=8),
    )
    overview_tab.add(
        "output",
        requests_table_var.active_row(),
        layout=weave.panels.GroupPanelLayout(x=12, y=21, w=12, h=8),
    )

    # attributes_tab = weave.panels.Group(layoutMode="grid")

    # users_tab = weave.panels.Group(layoutMode="grid")

    # models_tab = weave.panels.Group(layoutMode="grid")

    # tabs = panels.Group(
    #     layoutMode="tab",
    #     items={
    #         "Overview": overview_tab,
    #         "Requests": requests_tab,
    #         # "Attributes": attributes_tab,
    #         # "Users": users_tab,
    #         # "Models": models_tab,
    #     },
    # )

    return panels.Board(vars=varbar, panels=overview_tab)


with open(
    os.path.join(os.path.dirname(__file__), "instructions", "panel_llm_monitor.md"), "r"
) as f:
    instructions_md = f.read()

template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
    is_featured=True,
    instructions_md=instructions_md,
    thumbnail_url="https://raw.githubusercontent.com/wandb/weave/master/docs/assets/monitor-open-ai-api-usage.png",
)
