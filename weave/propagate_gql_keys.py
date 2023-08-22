from . import op_def
from . import graph
from . import weave_types as types
from . import registry_mem
from . import partial_object
from . import input_provider
from . import gql_op_plugin

import typing


def _propagate_gql_keys_for_node(
    opdef: "op_def.OpDef",
    node: graph.OutputNode,
    key_fn: gql_op_plugin.GQLOutputTypeFn,
    ip: input_provider.InputProvider,
) -> types.Type:
    # Mutates node
    # TODO: see if this can be done without mutations
    from .language_features.tagging import (
        tagged_value_type_helpers,
        tagged_value_type,
        opdef_util,
    )

    input_types = node.from_op.input_types

    first_arg_name = gql_op_plugin.first_arg_name(opdef)
    if first_arg_name is None:
        raise ValueError("OpDef does not have named args, cannot propagate GQL keys")

    # unwrap and rewrap tags
    original_input_type = input_types[first_arg_name]

    unwrapped_input_type, wrap = tagged_value_type_helpers.unwrap_tags(
        original_input_type
    )

    is_mapped = opdef.derived_from and opdef.derived_from.derived_ops["mapped"] == opdef
    if is_mapped:
        unwrapped_input_type = typing.cast(types.List, unwrapped_input_type).object_type

    # key fn operates on untagged types
    new_output_type = key_fn(ip, unwrapped_input_type)

    if isinstance(new_output_type, types.Invalid):
        raise ValueError('GQL key function returned "Invalid" type')

    if is_mapped:
        new_output_type = types.List(new_output_type)

    # now we rewrap the types to propagate the tags
    if opdef_util.should_tag_op_def_outputs(opdef):
        new_output_type = tagged_value_type.TaggedValueType(
            types.TypedDict({first_arg_name: original_input_type}), new_output_type
        )
    elif opdef_util.should_flow_tags(opdef):
        new_output_type = wrap(new_output_type)

    return new_output_type


def propagate_gql_keys(
    maybe_refined_node: graph.OutputNode,
    ip: input_provider.InputProvider,
) -> types.Type:
    if not maybe_refined_node.from_op.name == "gqlroot-wbgqlquery":
        fq_opname = maybe_refined_node.from_op.full_name
        opdef = registry_mem.memory_registry.get_op(fq_opname)
        plugin = gql_op_plugin.get_gql_plugin(opdef)

        key_fn: typing.Optional[gql_op_plugin.GQLOutputTypeFn] = None

        if plugin is None or plugin.gql_op_output_type is None:
            if fq_opname.endswith("GQLResolver"):
                original_opdef = registry_mem.memory_registry.get_op(
                    fq_opname.replace("GQLResolver", "")
                )
                original_plugin = gql_op_plugin.get_gql_plugin(original_opdef)
                if (
                    original_plugin is not None
                    and original_plugin.gql_op_output_type is not None
                ):
                    key_fn = original_plugin.gql_op_output_type
            if opdef.derived_from and opdef.derived_from.derived_ops["mapped"] == opdef:
                scalar_plugin = gql_op_plugin.get_gql_plugin(opdef.derived_from)
                if scalar_plugin is not None:
                    key_fn = scalar_plugin.gql_op_output_type
        else:
            key_fn = plugin.gql_op_output_type

        if key_fn is not None:
            return _propagate_gql_keys_for_node(opdef, maybe_refined_node, key_fn, ip)

    return maybe_refined_node.type
