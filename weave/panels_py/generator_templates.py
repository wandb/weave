import dataclasses
import typing

import weave
from .. import registry_mem

from .panel_autoboard import node_qualifies_for_autoboard


class PyBoardGeneratorSpec(typing.TypedDict):
    display_name: str
    description: str
    op_name: str


@dataclasses.dataclass
class PyBoardGeneratorInternalSpec:
    spec: PyBoardGeneratorSpec
    additional_predicate: typing.Optional[
        typing.Callable[[weave.Node[typing.Any]], bool]
    ] = None


no_config_generator_specs = [
    PyBoardGeneratorInternalSpec(
        PyBoardGeneratorSpec(
            display_name="Timeseries Auto-Board",
            description="Column-level analysis of timeseries data",
            op_name="py_board-seed_autoboard",
        ),
        node_qualifies_for_autoboard,
    )
]


@weave.op(name="py_board-get_no_config_generators_for_node", hidden=True)
def get_no_config_generators_for_node(
    input_node: weave.Node[typing.Any],
) -> list[PyBoardGeneratorSpec]:
    final_specs = []
    for internal_spec in no_config_generator_specs:
        spec = internal_spec.spec
        op = registry_mem.memory_registry._ops[spec["op_name"]]
        if op.input_type.first_param_valid(input_node.type):
            predicate = internal_spec.additional_predicate
            if predicate is None or predicate(input_node):
                final_specs.append(spec)
    return final_specs
