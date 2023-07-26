import weave
from .. import weave_internal as internal
from .. import weave_types as types
from .generator_templates import template_registry


# IMPORTANT: To enable this (or any template), it must be imported in
# weave/panels_py/__init__.py This example is explicitly commented out since it
# is not intended to be in production. however, you are encouraged to uncomment
# it and play around with it.

# BOARD_ID must be unique across all ops. It must only contain letters and underscores.
BOARD_ID = "example_custom_board"

# BOARD_DISPLAY_NAME is the name that will be displayed in the UI
BOARD_DISPLAY_NAME = "Example Custom Board"

# BOARD_DESCRIPTION is the description that will be displayed in the UI
BOARD_DESCRIPTION = "An example board for internal developers"

# BOARD_INPUT_WEAVE_TYPE is the weave type of the input node.
BOARD_INPUT_WEAVE_TYPE = types.List(
    types.TypedDict({})
    # Example of requiring an `api_cost` field
    # types.TypedDict({"api_cost": types.optional(weave.types.Number())})
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
) -> weave.panels.Group:
    # Define your VarBar variables here
    control_items = [
        weave.panels.GroupPanel(internal.const("Example Custom Board"), id="title"),
        weave.panels.GroupPanel(input_node, id="data"),
    ]

    title_var = internal.make_var_node(input_node.type, "title")
    data_var = internal.make_var_node(input_node.type, "data")

    # Define your panels here
    panels = [
        weave.panels.BoardPanel(title_var, id="title_panel"),
        weave.panels.BoardPanel(data_var, id="table"),
    ]

    # Example of using the input type to modify the board:
    # Here, we add a panel for each numeric column, showing a distribution
    for column_name, column_type in input_node.type.object_type.property_types.items():
        if types.optional(types.Number()).assign_type(column_type):
            panels.append(
                weave.panels.BoardPanel(
                    data_var[column_name],  # type: ignore
                    id=column_name + "_distribution",
                )
            )

    return weave.panels.Board(vars=control_items, panels=panels)


template_registry.register(
    board_name,
    BOARD_DISPLAY_NAME,
    BOARD_DESCRIPTION,
)
