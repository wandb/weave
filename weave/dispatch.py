"""Functions for determining which op is being called."""

import typing
from . import registry_mem
from . import errors
from . import graph
from . import types
from . import op_def
from . import op_args


def get_op_for_inputs(
    name: str, inputs: dict[str, graph.Node]
) -> typing.Optional[op_def.OpDef]:
    candidates = []
    for op in registry_mem.memory_registry.list_ops():
        if op.name.endswith(name):
            # TODO: assuming all ops have NamedArgs. Need to handle both!
            if not isinstance(op.input_type, op_args.OpNamedArgs) or len(
                op.input_type.arg_types
            ) != len(inputs):
                continue
            for input_node, op_input_type in zip(
                inputs.values(), op.input_type.arg_types.values()
            ):
                if op_input_type.assign_type(input_node.type) == types.Invalid():
                    break
            else:
                candidates.append(op)
    if len(candidates) > 1:
        # Rejecting here is important. We don't in Weave0, which is what leads to ambiguous.
        # cases.
        # TODO: reject earlier, at declaration time.
        raise errors.WeaveInternalError(
            "Too many candidate ops, this means there are two ops declared with same name and overlapping input types: %s"
            % candidates
        )
    if candidates:
        return candidates[0]
    return None
