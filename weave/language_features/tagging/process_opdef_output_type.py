"""
This file is responcible for modifying the output_type of an op_def to support tags. The primary
function exported is `process_opdef_output_type`
"""

import typing


from ... import weave_types as types
from .opdef_util import should_flow_tags, should_tag_op_def_outputs
from .tagging_op_logic import (
    op_get_tag_type_resolver,
    op_make_type_key_tag_resolver,
    op_make_type_tagged_resolver,
)
from ... import graph
from ... import registry_mem

if typing.TYPE_CHECKING:
    from ... import op_def as OpDef


# The following 3 functions are used to get the ops without introducing circular references
def op_get_tag_type(obj_type: types.Type) -> graph.OutputNode:
    return registry_mem.memory_registry.get_op("op_get_tag_type")(obj_type)


def op_make_type_key_tag(
    obj_type: types.Type, key: str, tag_type: types.Type
) -> graph.OutputNode:
    return registry_mem.memory_registry.get_op("op_make_type_key_tag")(
        obj_type, key, tag_type
    )


def op_make_type_tagged(obj_type: types.Type, tag_type: types.Type) -> graph.OutputNode:
    return registry_mem.memory_registry.get_op("op_make_type_tagged")(
        obj_type, tag_type
    )


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
                if _currently_weavifying(input_types):
                    return op_make_type_key_tag(  # type: ignore
                        output_type,  # type: ignore
                        first_arg_name,
                        input_types[first_arg_name],
                    )
                else:
                    return op_make_type_key_tag_resolver(
                        output_type,  # type: ignore
                        first_arg_name,
                        input_types[first_arg_name],
                    )

            return ot
        elif callable(output_type):
            callable_output_type = output_type

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if _currently_weavifying(input_types):
                    return op_make_type_key_tag(  # type: ignore
                        callable_output_type(input_types),
                        first_arg_name,
                        input_types[first_arg_name],
                    )
                else:
                    return op_make_type_key_tag_resolver(
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
                if _currently_weavifying(input_types):
                    return op_make_type_tagged(  # type: ignore
                        output_type, op_get_tag_type(input_types[first_arg_name])  # type: ignore
                    )
                else:
                    return op_make_type_tagged_resolver(
                        output_type,  # type: ignore
                        op_get_tag_type_resolver(input_types[first_arg_name]),
                    )

            return ot
        elif callable(output_type):
            callable_output_type = output_type

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                if _currently_weavifying(input_types):
                    return op_make_type_tagged(  # type: ignore
                        callable_output_type(input_types),
                        op_get_tag_type(input_types[first_arg_name]),  # type: ignore
                    )
                else:
                    return op_make_type_tagged_resolver(
                        callable_output_type(input_types),
                        op_get_tag_type_resolver(input_types[first_arg_name]),
                    )

            return ot
        else:
            raise Exception("Invalid output_type")
    else:
        return output_type


def process_opdef_refined_output_type(
    refined_output_type: types.Type,
    bound_params: typing.Dict[str, graph.Node],
    op_def: "OpDef.OpDef",
) -> types.Type:
    if should_tag_op_def_outputs(op_def):
        first_arg_name = op_def.input_type.named_args()[0].name
        return op_make_type_key_tag_resolver(
            refined_output_type,
            first_arg_name,
            bound_params[first_arg_name].type,
        )
    elif should_flow_tags(op_def):
        first_arg_name = op_def.input_type.named_args()[0].name
        return op_make_type_tagged_resolver(
            refined_output_type,
            op_get_tag_type_resolver(bound_params[first_arg_name].type),
        )
    else:
        return refined_output_type


def _currently_weavifying(input_types: typing.Any) -> bool:
    return isinstance(input_types, graph.Node) and types.TypedDict({}).assign_type(
        input_types.type
    )
