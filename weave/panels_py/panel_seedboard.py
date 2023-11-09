import typing

import weave
from .. import weave_internal
from .generator_templates import template_registry


@weave.type()
class PyBoardSeedBoardConfig:
    pass


@weave.op(  # type: ignore
    name="py_board-seed_board",
    hidden=True,
)
def seed_board(
    input_node: weave.Node[list[dict]],
    config: typing.Optional[PyBoardSeedBoardConfig] = None,
) -> weave.panels.Group:
    control_items = [
        weave.panels.GroupPanel(
            input_node,
            id="data",
        ),
    ]

    panels = [
        weave.panels.BoardPanel(
            weave_internal.make_var_node(input_node.type, "data"),
            id="table",
            layout=weave.panels.BoardPanelLayout(x=0, y=0, w=24, h=6),
        ),
    ]
    return weave.panels.Board(vars=control_items, panels=panels)


template_registry.register(
    "py_board-seed_board",
    "Simple Board",
    "Seed a board with a simple visualization of this table.",
)
