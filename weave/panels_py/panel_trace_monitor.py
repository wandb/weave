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
BOARD_ID = "trace_monitor"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "Trace Monitor Board"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "Monitor Traces"

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.


BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict(
        {
            "name": types.optional(types.String()),
            "span_id": types.optional(types.String()),
            "parent_id": types.optional(types.String()),
            "trace_id": types.optional(types.String()),
            "start_time_s": types.optional(types.Number()),
            "end_time_s": types.optional(types.Number()),
            "status_code": types.optional(types.String()),
            "inputs": types.optional(types.TypedDict({})),
            "output": types.optional(types.Any()),
            # "exception": types.optional(types.String()), # maybe use not_required_keys?
            "attributes": types.optional(types.TypedDict({})),
            "summary": types.optional(
                types.TypedDict(
                    {
                        "latency_s": types.optional(types.Number()),
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

    ### Varbar

    # Add the input node as raw data
    varbar = panel_board.varbar(editable=False)

    source_data = varbar.add("source_data", input_node)

    height = 5

    ### Overview tab

    overview_tab = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    requests_table = panels.Table(source_data)  # type: ignore
    # requests_table.add_column(lambda row: row["output.model"], "Model")
    # requests_table.add_column(
    #     lambda row: row["inputs.messages"][-1]["content"], "Last Prompt"
    # )
    # requests_table.add_column(
    #     lambda row: row["output.choices"][-1]["message.content"],
    #     "Completion",
    # )
    # requests_table.add_column(lambda row: row["summary.prompt_tokens"], "Prompt Tokens")
    # requests_table.add_column(
    #     lambda row: row["summary.completion_tokens"], "Completion Tokens"
    # )
    # requests_table.add_column(lambda row: row["summary.total_tokens"], "Total Tokens")
    # requests_table.add_column(lambda row: row["summary.latency_s"], "Latency")
    # requests_table.add_column(lambda row: row["summary.cost"], "Cost")
    # requests_table.add_column(
    #     lambda row: row["timestamp"], "Timestamp", sort_dir="desc"
    # )

    requests_table_var = overview_tab.add(
        "table",
        requests_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=24, h=8),
    )

    return panels.Board(vars=varbar, panels=overview_tab)


template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
)
