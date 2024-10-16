import typing

import weave_query as weave
import weave_query
from weave_query import weave_internal
from weave_query.panels_py.generator_templates import template_registry


@weave.type()
class PyBoardSeedBoardConfig:
    pass


@weave.op(  # type: ignore
    name="py_board-seed_board",
    hidden=True,
)
def seed_board(
    input_node: weave.Node[typing.Any],
    config: typing.Optional[PyBoardSeedBoardConfig] = None,
) -> weave_query.panels.Group:
    control_items = [
        weave_query.panels.GroupPanel(
            input_node,
            id="data",
        ),
    ]

    panels = [
        weave_query.panels.BoardPanel(
            weave_internal.make_var_node(input_node.type, "data"),
            id="panel",
            layout=weave_query.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
        ),
    ]
    return weave_query.panels.Board(vars=control_items, panels=panels)


template_registry.register(
    "py_board-seed_board",
    "Simple Board",
    "Seed a board with a simple visualization of this table.",
)
