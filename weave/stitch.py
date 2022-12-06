# "Stitch" a graph together, by traversing tag and literal construction and access.
#
# The resulting stitched graph is appropriate for optimizations like projection
# pushdown and predicate pushdown.
#
# Weave DAGs can contain ops that change the shape of values in ways that are entirely
# recoverable from the DAG. For example, you can use the dict_ op to create a dict
# that has values at known dict keys. The resulting dict may be passed around, and
# eventually have its keys accessed by getitem. This library attaches ops that operate
# on a downstream getitem back to the original item that was placed in the dict at the
# dict_ call.
#
# It also enters sub-DAGs, like the argument to map, and stitches encountered ops
# back to the map's input node.
#
# This implementation MUST be comprehensive. IE it must correctly get all downstream
# ops that should be stitched to a given node, or denote that its not possible. Optimizers
# need accurate information to optimize!
#
# Not yet implemented: list literals, execute() traversal, and probably a bunch more!

import dataclasses
import typing

from . import graph
from . import errors
from . import registry_mem
from . import compile
from . import op_def
from .language_features.tagging import opdef_util


@dataclasses.dataclass
class OpCall:
    op_name: str
    input_dict: dict[str, "ObjectRecorder"]
    output: "ObjectRecorder"

    @property
    def inputs(self) -> list["ObjectRecorder"]:
        return list(self.input_dict.values())


@dataclasses.dataclass()
class ObjectRecorder:
    tags: dict[str, "ObjectRecorder"] = dataclasses.field(default_factory=dict)
    val: typing.Optional[typing.Any] = None
    calls: list[OpCall] = dataclasses.field(default_factory=list)

    def call_op(
        self, op_name: str, input_dict: dict[str, "ObjectRecorder"]
    ) -> "ObjectRecorder":
        output = ObjectRecorder()
        self.calls.append(OpCall(op_name, input_dict, output))
        return output


class LiteralDictObjectRecorder(ObjectRecorder):
    val: dict[str, ObjectRecorder]


@dataclasses.dataclass
class StitchedGraph:
    node_map: typing.Dict[graph.Node, ObjectRecorder]

    def get_result(self, node: graph.Node) -> ObjectRecorder:
        return self.node_map[node]


def stitch(
    leaf_nodes: list[graph.Node],
    var_values: typing.Optional[dict[str, ObjectRecorder]] = None,
) -> StitchedGraph:
    """Given a list of leaf nodes, stitch the graph together."""
    results: dict[graph.Node, ObjectRecorder] = {}

    def handle_node(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            input_dict = {k: results[v] for k, v in node.from_op.inputs.items()}
            results[node] = stitch_node(node, input_dict)
        elif isinstance(node, graph.ConstNode):
            results[node] = ObjectRecorder(val=node.val)
        elif isinstance(node, graph.VarNode):
            if not var_values:
                raise errors.WeaveInternalError(
                    "Encountered var %s but var_values not provided" % node.name
                )
            results[node] = var_values[node.name]
        else:
            raise errors.WeaveInternalError("Unexpected node type")
        return node

    graph.map_all_nodes(leaf_nodes, handle_node)

    return StitchedGraph(results)


def subgraph_stitch(
    function_node: graph.Node, args: dict[str, ObjectRecorder]
) -> ObjectRecorder:
    function_node = compile.compile([function_node])[0]
    result_graph = stitch([function_node], args)
    return result_graph.get_result(function_node)


def is_root_op(op: op_def.OpDef) -> bool:
    return (
        op.name == "root-project"
        or op.name == "get"
        or op.name == "getReturnType"
        or op.name == "render_table_runs2"
        or op.name == "project-runs2"
    )


def is_get_tag_op(op: op_def.OpDef) -> bool:
    return "tag_getter_op" in str(op.raw_resolve_fn.__name__)


def get_tag_name_from_tag_getter_op(op: op_def.OpDef) -> str:
    # Read the tag name from the resolve_fn closure.
    # TODO: Fragile!
    return op.raw_resolve_fn.__closure__[0].cell_contents  # type: ignore


def stitch_node_inner(
    node: graph.OutputNode, input_dict: dict[str, ObjectRecorder]
) -> ObjectRecorder:
    op = registry_mem.memory_registry.get_op(node.from_op.name)
    inputs = list(input_dict.values())
    if is_get_tag_op(op):
        tag_name = get_tag_name_from_tag_getter_op(op)
        return inputs[0].tags[tag_name]
    elif node.from_op.name.endswith("createIndexCheckpointTag"):
        inputs[0].tags["index"] = ObjectRecorder()
    elif node.from_op.name == "dict":
        return LiteralDictObjectRecorder(val=input_dict)
    elif node.from_op.name.endswith("pick"):
        key = node.from_op.inputs["key"].val
        if key is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        if isinstance(inputs[0], LiteralDictObjectRecorder):
            return inputs[0].val[key]
    elif node.from_op.name.endswith("map"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        # Return the resulting object from map!
        return subgraph_stitch(fn, {"row": inputs[0]})
    elif node.from_op.name.endswith("sort") or node.from_op.name.endswith("filter"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        subgraph_stitch(fn, {"row": inputs[0]})
        # Return the original object
        return inputs[0]
    elif node.from_op.name.endswith("groupby"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        # The output of the subgraph function is the group key which becomes
        # the groupKey tag.
        groupkey = subgraph_stitch(fn, {"row": inputs[0]})
        inputs[0].tags["groupKey"] = groupkey
        # And we return the original object
        return inputs[0]
    # Otherwise, not a special op, track its call.
    return inputs[0].call_op(op.name, input_dict)


def stitch_node(
    node: graph.OutputNode, input_dict: dict[str, ObjectRecorder]
) -> ObjectRecorder:
    op = registry_mem.memory_registry.get_op(node.from_op.name)
    input_names = list(input_dict.keys())
    inputs = list(input_dict.values())

    result = stitch_node_inner(node, input_dict)

    # Tag logic
    if opdef_util.should_tag_op_def_outputs(op):
        result.tags = inputs[0].tags
        result.tags[input_names[0]] = inputs[0]
    elif opdef_util.should_flow_tags(op):
        result.tags = inputs[0].tags

    return result
