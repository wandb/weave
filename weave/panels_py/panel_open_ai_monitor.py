import typing

import weave
from .. import weave_internal as internal
from .. import weave_types as types
from .generator_templates import template_registry


panels = weave.panels
ops = weave.ops


# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "open_ai_completions_monitor"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "OpenAI Monitor Board"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Monitor OpenAI Completions"

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.
BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "inputs": types.optional(
                types.TypedDict(
                    {
                        "kwargs": types.optional(
                            types.TypedDict(
                                {
                                    "messages": types.optional(
                                        types.List(
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
                                        )
                                    ),
                                }
                            )
                        ),
                    }
                )
            ),
            "output": types.optional(
                types.TypedDict(
                    {
                        "id": types.optional(types.String()),
                        "object": types.optional(types.String()),
                        "model": types.optional(types.String()),
                        "usage": types.optional(
                            types.TypedDict(
                                {
                                    "prompt_tokens": types.optional(types.Number()),
                                    "completion_tokens": types.optional(types.Number()),
                                    "total_tokens": types.optional(types.Number()),
                                }
                            )
                        ),
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
        }
    )
)


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
    control_items = []

    # Add the input node as raw data
    control_items.append(panels.GroupPanel(input_node, id="raw_data"))
    data_var = internal.make_var_node(input_node.type, "raw_data")

    # Setup date range variables:
    ## 1. raw_data_range is derived from raw_data
    control_items.append(
        weave.panels.GroupPanel(
            lambda raw_data: weave.ops.make_list(
                a=raw_data[timestamp_col_name].min(),
                b=raw_data[timestamp_col_name].max(),
            ),
            id="raw_data_range",
            hidden=True,
        )
    )
    ## 2. user_zoom_range is used to store the user's zoom range
    control_items.append(
        weave.panels.GroupPanel(None, id="user_zoom_range", hidden=True)
    )
    ## 2.b: Setup a date picker to set the user_zoom_range
    control_items.append(
        weave.panels.GroupPanel(
            lambda raw_data, user_zoom_range: weave.panels.DateRange(
                user_zoom_range, domain=raw_data[timestamp_col_name]
            ),
            id="date_picker",
        ),
    )
    ## 3. bin_range is derived from user_zoom_range and raw_data_range. This is
    ##    the range of data that will be displayed in the charts.
    control_items.append(
        weave.panels.GroupPanel(
            lambda user_zoom_range, raw_data_range: user_zoom_range.coalesce(
                raw_data_range
            ),
            id="bin_range",
            hidden=True,
        )
    )

    control_items.append(
        panels.GroupPanel(
            lambda raw_data: raw_data.map(
                lambda row: ops.dict_(
                    id=row["output"]["id"],
                    object=row["output"]["object"],
                    model=row["output"]["model"],
                    messages=row["inputs"]["kwargs"]["messages"],
                    usage=row["output"]["usage"],
                    completion=row["output"]["choices"][0]["message"],
                    finish_reason=row["output"]["choices"][0]["finish_reason"],
                    timestamp=row["timestamp"],
                    latency_ms=row["latency_ms"],
                )
            ),
            id="clean_data",
            hidden=True,
        )
    )

    # Derive the windowed data to use in the plots as a function of bin_range
    control_items.append(
        weave.panels.GroupPanel(
            lambda clean_data, bin_range: clean_data.filter(
                lambda row: weave.ops.Boolean.bool_and(
                    row[timestamp_col_name] >= bin_range[0],
                    row[timestamp_col_name] < bin_range[1],
                )
            ),
            id="window_data",
            hidden=True,
        )
    )

    def make_table() -> typing.Callable:
        def maker(window_data: typing.Any) -> panels.Table:
            table = panels.Table(window_data)  # type: ignore
            table_state = table.config.tableState  # type: ignore
            table_state.add_column(lambda row: row["model"], "Model")
            table_state.add_column(
                lambda row: row["messages"][-1]["content"], "Message"
            )
            table_state.add_column(
                lambda row: row["completion"]["content"], "Completion"
            )
            table_state.add_column(
                lambda row: row["usage"]["prompt_tokens"], "Prompt Tokens"
            )
            table_state.add_column(
                lambda row: row["usage"]["completion_tokens"], "Completion Tokens"
            )
            table_state.add_column(
                lambda row: row["usage"]["total_tokens"], "Total Tokens"
            )
            table_state.add_column(lambda row: row["latency_ms"], "Latency")
            table_state.add_column(lambda row: row["timestamp"], "Timestamp")
            return table

        return maker

    def make_timeseries_for_field(y_fn: typing.Callable) -> typing.Callable:
        def maker(
            clean_data: typing.Any, bin_range: typing.Any, user_zoom_range: typing.Any
        ) -> panels.Plot:
            return panels.Plot(
                clean_data,
                x=lambda item: item["timestamp"].bin(
                    ops.timestamp_bins_nice(bin_range, 50)
                ),
                y=y_fn,
                groupby_dims=["x"],
                domain_x=user_zoom_range,
                mark="bar",
            )

        return maker

    height = 5
    board_panels = [
        panels.BoardPanel(
            make_table(),
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=8),
            id="table",
        ),
        panels.BoardPanel(
            lambda table: table.active_row(),
            id="execution",
            layout=weave.panels.BoardPanelLayout(x=0, y=8, w=12, h=8),
        ),
        panels.BoardPanel(
            lambda table: panels.Table(  # type: ignore
                table.active_data()["messages"],
                columns=[lambda row: row["role"], lambda row: row["content"]],
            ),
            id="messages",
            layout=weave.panels.BoardPanelLayout(x=12, y=8, w=12, h=8),
        ),
        panels.BoardPanel(
            lambda window_data: window_data["latency_ms"].avg(),  # type: ignore
            id="latency_avg",
            layout=weave.panels.BoardPanelLayout(x=0, y=14 + 0, w=6, h=height),
        ),
        panels.BoardPanel(
            make_timeseries_for_field(lambda preds: preds["latency_ms"].avg()),
            id="latency_over_time",
            layout=weave.panels.BoardPanelLayout(x=6, y=14 + 0, w=18, h=height),
        ),
        panels.BoardPanel(
            lambda window_data: window_data["usage"]["prompt_tokens"].sum(),  # type: ignore
            id="prompt_tokens_sum",
            layout=weave.panels.BoardPanelLayout(x=0, y=14 + height, w=6, h=height),
        ),
        panels.BoardPanel(
            make_timeseries_for_field(
                lambda preds: preds["usage"]["prompt_tokens"].sum()
            ),
            id="prompt_tokens_over_time",
            layout=weave.panels.BoardPanelLayout(x=6, y=14 + height, w=18, h=height),
        ),
        panels.BoardPanel(
            lambda window_data: window_data["usage"]["completion_tokens"].sum(),  # type: ignore
            id="completion_tokens_sum",
            layout=weave.panels.BoardPanelLayout(x=0, y=14 + height * 2, w=6, h=height),
        ),
        panels.BoardPanel(
            make_timeseries_for_field(
                lambda preds: preds["usage"]["completion_tokens"].sum()
            ),
            id="completion_tokens_over_time",
            layout=weave.panels.BoardPanelLayout(
                x=6, y=14 + height * 2, w=18, h=height
            ),
        ),
        panels.BoardPanel(
            lambda window_data: window_data["usage"]["total_tokens"].sum(),  # type: ignore
            id="total_tokens_sum",
            layout=weave.panels.BoardPanelLayout(x=0, y=14 + height * 3, w=6, h=height),
        ),
        panels.BoardPanel(
            make_timeseries_for_field(
                lambda preds: preds["usage"]["total_tokens"].sum()
            ),
            id="total_tokens_over_time",
            layout=weave.panels.BoardPanelLayout(
                x=6, y=14 + height * 3, w=18, h=height
            ),
        ),
    ]
    return panels.Board(vars=control_items, panels=board_panels)


template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
)
