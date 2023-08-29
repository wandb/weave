import typing
from . import graph
from . import weave_types as types
from . import stitch
from . import registry_mem
from . import errors
from . import op_args
from . import gql_to_weave
from . import gql_op_plugin

import graphql

from .input_provider import InputAndStitchProvider


if typing.TYPE_CHECKING:
    from . import op_def


def fragment_to_query(fragment: str) -> str:
    return f"query WeavePythonCG {{ {fragment} }}"


# This is the primary exposed function of this module and is called in `compile.py`. It's primary role
# is to roll up all the GQLOps such that a single query can be composed - then replace the root op with a
# special op that calls such query and constructs the correct type. It makes heavy use of the
# `stitch` module to do this. Moreover, all GQL is zipped and deduped so that the minimum request
# is made to the server. See the helper functions below for more details.
def apply_domain_op_gql_translation(
    leaf_nodes: list[graph.Node], on_error: graph.OnErrorFnType = None
) -> list[graph.Node]:
    # Only apply this transformation at least one of the leaf nodes is a root node
    if not graph.filter_nodes_full(leaf_nodes, _is_root_node):
        return leaf_nodes

    p = stitch.stitch(leaf_nodes, on_error=on_error)

    query_str_const_node = graph.ConstNode(types.String(), "")
    alias_list_const_node = graph.ConstNode(types.List(types.String()), [])
    output_type_node = graph.ConstNode(types.TypeType(), types.Any())
    query_root_node = graph.OutputNode(
        types.Dict(types.String(), types.TypedDict({})),
        "gqlroot-wbgqlquery",
        {
            "query_str": query_str_const_node,
            "alias_list": alias_list_const_node,
            "output_type": output_type_node,
        },
    )
    fragments = []
    aliases = []

    def _replace_with_merged_gql(node: graph.Node) -> graph.Node:
        if not _is_root_node(node):
            return node
        node = typing.cast(graph.OutputNode, node)
        inner_fragment = _get_fragment(node, p)
        fragments.append(inner_fragment)
        alias = gql_to_weave.get_outermost_alias(inner_fragment)
        aliases.append(alias)
        custom_resolver = _custom_root_resolver(node)

        if custom_resolver is not None:
            return custom_resolver(query_root_node, **node.from_op.inputs)
        else:
            output_type = get_plugin_output_type(node)

            return graph.OutputNode(
                output_type,
                "gqlroot-querytoobj",
                {
                    "result_dict": query_root_node,
                    "result_key": graph.ConstNode(types.String(), alias),
                    "output_type": graph.ConstNode(types.TypeType(), output_type),
                    "gql_query_fragment": graph.ConstNode(
                        types.String(), inner_fragment
                    ),
                },
            )

    res = graph.map_nodes_full(leaf_nodes, _replace_with_merged_gql, on_error)

    combined_query_fragment = "\n".join(fragments)
    query_str = fragment_to_query(combined_query_fragment)
    if combined_query_fragment.strip() != "":
        query_str = normalize_gql_query_string(query_str)
    query_str_const_node.val = query_str
    alias_list_const_node.val = aliases

    return res


### Everything below are helpers for the above function ###


def get_plugin_output_type(node: graph.OutputNode) -> types.Type:
    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    return op_def.concrete_output_type


def _get_fragment(node: graph.OutputNode, stitchedGraph: stitch.StitchedGraph) -> str:
    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    # TODO: make this a helper (it is used in stich.py as well)
    if op_def.derived_from and op_def.derived_from.derived_ops["mapped"] == op_def:
        op_def = op_def.derived_from

    # These are all passthrough ops - should this be in stitch?
    is_passthrough = (
        op_def.name.endswith("offset")
        or op_def.name.endswith("limit")
        or op_def.name.endswith("index")
        or op_def.name.endswith("__getitem__")
        or op_def.name.endswith("concat")
        or op_def.name.endswith("contains")
        or op_def.name.endswith("list")
        or op_def.name.endswith("concat")
        or op_def.name.endswith("flatten")
        or op_def.name.endswith("unnest")
        or op_def.name.endswith("dropna")
        or op_def.name == "list-createIndexCheckpointTag"
    )

    wb_domain_gql = gql_op_plugin.get_gql_plugin(op_def)
    if wb_domain_gql is None and not is_passthrough:
        return ""

    forward_obj = stitchedGraph.get_result(node)
    calls = forward_obj.calls
    child_fragment = "\n".join(
        [
            _get_fragment(call.node, stitchedGraph)
            for call in calls
            if isinstance(call.node, graph.OutputNode)
        ]
    )

    if is_passthrough:
        return child_fragment
    wb_domain_gql = typing.cast(gql_op_plugin.GqlOpPlugin, wb_domain_gql)

    const_node_input_vals = {
        key: value.val
        for key, value in node.from_op.inputs.items()
        if isinstance(value, graph.ConstNode)
    }
    ip = InputAndStitchProvider(const_node_input_vals, forward_obj)

    fragment = wb_domain_gql.query_fn(
        ip,
        child_fragment,
    )

    return fragment


def _get_configsummaryhistory_keys_or_specs(
    field: graphql.language.ast.FieldNode,
) -> typing.Optional[typing.List[str]]:
    if len(field.arguments) > 1:
        raise errors.WeaveInternalError(
            "Custom merge for config, summaryMetrics, and sampledHistory only supports one argument"
        )
    if not field.arguments:
        return None
    field_arg0 = field.arguments[0]
    if field_arg0.name.value not in ["keys", "specs", "liveKeys"]:
        raise errors.WeaveInternalError(
            "First argument for custom merge must be 'keys' or 'specs'"
        )
    if not isinstance(field_arg0.value, graphql.language.ast.ListValueNode):
        raise errors.WeaveInternalError(
            "First argument for custom merge must be a list"
        )
    keys: list[str] = []
    for key in field_arg0.value.values:
        if not isinstance(key, graphql.language.ast.StringValueNode):
            raise errors.WeaveInternalError(
                "First argument for custom merge must be a list of strings"
            )
        keys.append(key.value)
    return keys


def _field_selections_hardcoded_merge(
    merge_from: graphql.language.ast.FieldNode,
    merge_to: graphql.language.ast.FieldNode,
) -> bool:
    # Custom field merging for config, summaryMetrics, and history keys.
    # Must be kept in sync with run_ops config* and summary_metrics* ops.
    if merge_from.name.value != merge_to.name.value:
        return False
    if merge_from.name.value not in [
        "config",
        "summaryMetrics",
        "sampledHistory",
        "parquetHistory",
    ]:
        return False
    if (
        merge_from.alias is None
        or merge_to.alias is None
        or merge_from.alias.value != merge_to.alias.value
    ):
        return False
    if (
        merge_from.alias.value != "configSubset"
        and merge_from.alias.value != "summaryMetricsSubset"
        and merge_from.alias.value != "sampledHistorySubset"
        and merge_from.alias.value != "sampledParquetHistory"
    ):
        return False
    merge_from_keys = _get_configsummaryhistory_keys_or_specs(merge_from)
    merge_to_keys = _get_configsummaryhistory_keys_or_specs(merge_to)
    if merge_to_keys is None:
        # merge_to already selects all
        pass
    elif merge_from_keys is None:
        # select all by removing arguments
        merge_to.arguments = ()
    else:
        for k in merge_from_keys:
            if k not in merge_to_keys:
                merge_to_keys.append(k)
        merge_to.arguments[0].value.values = tuple(
            graphql.language.ast.StringValueNode(value=k) for k in merge_to_keys
        )
    return True


def _field_selections_are_mergeable(
    selection1: graphql.language.ast.FieldNode,
    selection2: graphql.language.ast.FieldNode,
) -> bool:
    if selection1.name.value != selection2.name.value:
        return False
    if selection1.alias is None and selection2.alias is not None:
        return False
    if selection1.alias is not None and selection2.alias is None:
        return False
    if (
        selection1.alias is not None
        and selection2.alias is not None
        and selection1.alias.value != selection2.alias.value
    ):
        return False
    if len(selection1.arguments) != len(selection2.arguments):
        return False
    for arg1, arg2 in zip(selection1.arguments, selection2.arguments):
        if arg1.name.value != arg2.name.value:
            return False
        if arg1.value.to_dict() != arg2.value.to_dict():
            return False
    return True


def _fragment_selections_are_mergeable(
    selection1: graphql.language.ast.InlineFragmentNode,
    selection2: graphql.language.ast.InlineFragmentNode,
) -> bool:
    return selection1.type_condition.name.value == selection2.type_condition.name.value


def _zip_selection_set(
    selection_set: graphql.language.ast.SelectionSetNode,
) -> graphql.language.ast.SelectionSetNode:
    selections = selection_set.selections
    # Two selections can be merged if their alias, name, and arguments are the same
    # unfortunately, this seems to be O(n^2) in the number of selections
    new_selections: list[
        typing.Union[
            graphql.language.ast.FieldNode, graphql.language.ast.InlineFragmentNode
        ]
    ] = []
    for selection in selections:
        if isinstance(selection, graphql.language.ast.FieldNode) or isinstance(
            selection, graphql.language.ast.InlineFragmentNode
        ):
            for new_selection in new_selections:
                did_custom_merge = (
                    isinstance(selection, graphql.language.ast.FieldNode)
                    and isinstance(new_selection, graphql.language.ast.FieldNode)
                    and _field_selections_hardcoded_merge(selection, new_selection)
                )
                if did_custom_merge:
                    break

                should_merge = (
                    isinstance(selection, graphql.language.ast.FieldNode)
                    and isinstance(new_selection, graphql.language.ast.FieldNode)
                    and _field_selections_are_mergeable(selection, new_selection)
                )
                should_merge = should_merge or (
                    isinstance(selection, graphql.language.ast.InlineFragmentNode)
                    and isinstance(
                        new_selection, graphql.language.ast.InlineFragmentNode
                    )
                    and _fragment_selections_are_mergeable(selection, new_selection)
                )
                if should_merge:
                    if selection.selection_set:
                        if new_selection.selection_set is None:
                            new_selection.selection_set = (
                                graphql.language.ast.SelectionSetNode(selections=())
                            )
                        new_selection.selection_set.selections = (
                            *new_selection.selection_set.selections,
                            *selection.selection_set.selections,
                        )
                    break
            else:
                new_selections.append(selection)
        else:
            raise ValueError(
                f"Found unsupported selection type {type(selection)}, please add implementation in compile_domain.py"
            )
    for selection in new_selections:
        if selection.selection_set:
            selection.selection_set = _zip_selection_set(selection.selection_set)
    selection_set.selections = tuple(new_selections)
    return selection_set


def _zip_gql_doc(
    gql_doc: graphql.language.ast.DocumentNode,
) -> graphql.language.ast.DocumentNode:
    if len(gql_doc.definitions) > 1:
        raise ValueError("Only one query definition is supported")
    query_def = gql_doc.definitions[0]
    if not isinstance(query_def, graphql.language.ast.OperationDefinitionNode):
        raise ValueError("Only operation definitions are supported")

    query_def.selection_set = _zip_selection_set(query_def.selection_set)
    gql_doc.definitions = (query_def,)
    return gql_doc


def normalize_gql_query_string(query_str: str) -> str:
    gql_doc = graphql.language.parse(query_str)
    gql_doc = _zip_gql_doc(gql_doc)
    return graphql.utilities.strip_ignored_characters(
        graphql.language.print_ast(gql_doc)
    )


def _is_root_node(node: graph.Node) -> bool:
    if not isinstance(node, graph.OutputNode):
        return False

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    wb_domain_gql = gql_op_plugin.get_gql_plugin(op_def)
    return wb_domain_gql is not None and wb_domain_gql.is_root


def _custom_root_resolver(node: graph.Node) -> typing.Optional["op_def.OpDef"]:
    if not isinstance(node, graph.OutputNode):
        return None

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    wb_domain_gql = gql_op_plugin.get_gql_plugin(op_def)
    if wb_domain_gql is not None:
        return wb_domain_gql.root_resolver
    return None


def required_const_input_names(node: graph.Node) -> typing.Optional[list[str]]:
    if not isinstance(node, graph.OutputNode):
        return None

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    wb_domain_gql = gql_op_plugin.get_gql_plugin(op_def)
    if wb_domain_gql is None:
        return None
    if not isinstance(op_def.input_type, op_args.OpNamedArgs):
        raise errors.WeaveInternalError(
            'Only named args are supported for "gql" domain'
        )
    input_names = list(op_def.input_type.arg_types.keys())
    if wb_domain_gql.is_root:
        return input_names
    return input_names[1:]
