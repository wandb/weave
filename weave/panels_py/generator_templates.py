import typing

import weave
from .. import registry_mem


# @dataclasses.dataclass
# class PyBoardGeneratorInternalSpec:
#     spec: PyBoardGeneratorSpec
#     predicate


# def is_table_like(type_: weave.types.Type) -> bool:
#     return hasattr(type_, "object_type") and hasattr(
#         typing.cast(weave.types.List, type_.object_type), "property_types"
#     )


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
    # PyBoardGeneratorSpec(
    #     display_name="OpenAI Completion Monitoring",
    #     description="Track and visualize OpenAI completions",
    #     op_name="py_board-seed_open_ai_completions",
    # ),
]


@weave.op(name="py_board-get_no_config_generators_for_node")
def get_no_config_generators_for_node(
    input_node: weave.Node[typing.Any],
) -> list[PyBoardGeneratorSpec]:
    final_specs = []
    for spec in no_config_generator_specs:
        op = registry_mem.memory_registry._ops[spec["op_name"]]
        if op.input_type.first_param_valid(input_node.type):
            final_specs.append(spec)
    return final_specs
