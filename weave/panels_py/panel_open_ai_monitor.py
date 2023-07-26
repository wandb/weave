import weave
from .. import weave_internal as internal
from .. import weave_types as types
from .generator_templates import template_registry


panels = weave.panels
ops = weave.ops


# IMPORTANT: To enable this (or any template), it must be imported in
# weave/panels_py/__init__.py This example is explicitly commented out since it
# is not intended to be in production. however, you are encourage to uncomment
# it and play around with it.

# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "open_ai_monitor"

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
    control_items = [
        panels.GroupPanel(input_node, id="data"),
    ]
    data_var = internal.make_var_node(input_node.type, "data")

    clean_data = data_var.map(
        lambda row: ops.dict_(
            id=row["output"]["id"],
            object=row["output"]["object"],
            model=row["output"]["model"],
            messages=row["inputs"]["kwargs"]["messages"],
            usage=row["output"]["usage"],
            completion=row["output"]["choices"][0]["message"],
            finish_reason=row["output"]["choices"][0]["finish_reason"],
            timestamp=row["timestamp"],
        )
    )
    control_items.append(panels.GroupPanel(clean_data, id="clean_data"))
    clean_data_var = internal.make_var_node(clean_data.type, "clean_data")

    # Create a table from the query
    table = panels.Table(clean_data_var)
    table_state = table.config.tableState
    table_state.add_column(lambda row: row["model"], "Model")
    table_state.add_column(lambda row: row["messages"][-1]["content"], "Message")
    table_state.add_column(lambda row: row["completion"]["content"], "Completion")
    table_state.add_column(lambda row: row["usage"]["prompt_tokens"], "Prompt Tokens")
    table_state.add_column(
        lambda row: row["usage"]["completion_tokens"], "Completion Tokens"
    )
    table_state.add_column(lambda row: row["usage"]["total_tokens"], "Total Tokens")
    table_state.add_column(lambda row: row["timestamp"], "Timestamp")
    table_panel = panels.BoardPanel(
        table, layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6), id="table"
    )

    board_panels = [
        table_panel,
    ]
    return panels.Board(vars=control_items, panels=board_panels)


template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
)
