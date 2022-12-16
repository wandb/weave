# Language feature: Automatic function calling
#
# A Weave Node is a Function. If there are no variables in the Node's DAG,
# the node can be executed.
#
# If you have a Node[Function[..., int]], you may pass it in positions that
# expect int. We automatically insert an .execute() op when this type of
# call is detected.
#
# TODO: resolve ambiguities:
#   - should it work recursively? (Node[Function[..., Function[..., int]]])
#   - does this cause invalid type/name overlap and collisions?

# There is also a compile pass for this in compile.py

import typing

from . import weave_types as types
from . import op_args


def update_input_types(
    op_input_type: typing.Optional[op_args.OpArgs],
    actual_input_types: dict[str, types.Type],
) -> dict[str, types.Type]:
    if not isinstance(op_input_type, op_args.OpNamedArgs):
        return actual_input_types
    expected_input_types = op_input_type.arg_types
    result: dict[str, types.Type] = {}
    try:
        for k, t in actual_input_types.items():
            expected_input_type = expected_input_types[k]
            if (
                isinstance(t, types.Function)
                and not callable(expected_input_type)
                and not isinstance(expected_input_type, types.Function)
            ):
                result[k] = t.output_type
            else:
                result[k] = t
    except KeyError:
        return actual_input_types
    return result
