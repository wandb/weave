import typing

import weave
from .. import weave_internal


@weave.type()
class PyBoardSeedBoardConfig:
    pass


@weave.op(  # type: ignore
    name="py_board-seed_board",
)
def seed_board(
    input_node: weave.Node[typing.Any],
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


@weave.type()
class PyBoardSeedBoardConfig:
    pass


@weave.op(  # type: ignore
    name="py_board-seed_open_ai_completions",
)
def seed_open_ai_completions(
    input_node: weave.Node[typing.Any],
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


class PyBoardGeneratorSpec(typing.TypedDict):
    display_name: str
    description: str
    op_name: str


no_config_generator_specs = [
    PyBoardGeneratorSpec(
        display_name="Simple Board",
        description="Create a dashboard for any data",
        op_name="py_board-seed_board",
    ),
    PyBoardGeneratorSpec(
        display_name="Timeseries Auto-Board",
        description="Column-level analysis of timeseries data",
        op_name="py_board-seed_autoboard",
    ),
    PyBoardGeneratorSpec(
        display_name="OpenAI Completion Monitoring",
        description="Track and visualize OpenAI completions",
        op_name="py_board-seed_open_ai_completions",
    ),
]


@weave.op(name="py_board-get_no_config_generators_for_node")
def get_no_config_generators_for_node(
    input_node: weave.Node[typing.Any],
) -> list[PyBoardGeneratorSpec]:
    # TODO: Filter this down
    return no_config_generator_specs
