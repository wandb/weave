"""
This file is responcible for modifying the output_type of an op_def to support tags. The primary
function exported is `process_opdef_output_type`
"""

import typing


from ... import weave_types as types
from .opdef_util import should_flow_tags, should_tag_op_def_outputs
from .tagging_ops import op_get_tag_type, op_make_type_key_tag, op_make_type_tagged
from ..util import currently_weavifying

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef

# `process_opdef_output_type` will take in an outoput type and an op_def to
# return a new output type that knows how to handle tags. It handles 3 cases: no
# tags, tagging outputs, and tag flowing - just like the
# `process_opdef_resolve_fn` sister function. In each case we handle if the
# user-defined output type is a `Type` or a `Callable[[Dict[str, Type]], Type]`.
# The raw output_type is still available on the op_def if needed.
def process_opdef_output_type(
    output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ],
    op_def: "OpDef.OpDef",
) -> typing.Union[
    types.Type,
    typing.Callable[[typing.Dict[str, types.Type]], types.Type],
]:
    if should_tag_op_def_outputs(op_def):
        first_arg_name = op_def.input_type.named_args()[0].name
        if isinstance(output_type, types.Type):

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if currently_weavifying(input_types):
                    return op_make_type_key_tag(
                        output_type,
                        first_arg_name,
                        input_types[first_arg_name],
                    )
                else:
                    return op_make_type_key_tag.resolve_fn(
                        output_type,
                        first_arg_name,
                        input_types[first_arg_name],
                    )

            return ot
        elif callable(output_type):
            callable_output_type = output_type

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if currently_weavifying(input_types):
                    return op_make_type_key_tag(
                        callable_output_type(input_types),
                        first_arg_name,
                        input_types[first_arg_name],
                    )
                else:
                    return op_make_type_key_tag.resolve_fn(
                        callable_output_type(input_types),
                        first_arg_name,
                        input_types[first_arg_name],
                    )

            return ot
        else:
            raise Exception("Invalid output_type")
    elif should_flow_tags(op_def):
        first_arg_name = op_def.input_type.named_args()[0].name
        if isinstance(output_type, types.Type):

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if currently_weavifying(input_types):
                    return op_make_type_tagged(
                        output_type, op_get_tag_type(input_types[first_arg_name])
                    )
                else:
                    return op_make_type_tagged.resolve_fn(
                        output_type,
                        op_get_tag_type.resolve_fn(input_types[first_arg_name]),
                    )

            return ot
        elif callable(output_type):
            callable_output_type = output_type

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if currently_weavifying(input_types):
                    return op_make_type_tagged(
                        callable_output_type(input_types),
                        op_get_tag_type(input_types[first_arg_name]),
                    )
                else:
                    return op_make_type_tagged.resolve_fn(
                        callable_output_type(input_types),
                        op_get_tag_type.resolve_fn(input_types[first_arg_name]),
                    )

            return ot
        else:
            raise Exception("Invalid output_type")
    else:
        return output_type
