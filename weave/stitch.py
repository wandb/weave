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
import functools
import typing

from . import weave_types as types
from . import graph
from . import errors
from . import registry_mem
from . import op_def
from .language_features.tagging import opdef_util


def node_visitor(node: graph.Node, visit_fn: typing.Callable[[graph.Node]]):
    if isinstance(node, graph.ConstNode):
        visit_fn(node)
    elif isinstance(node, graph.VarNode) or isinstance(node, graph.VoidNode):
        visit_fn(node)
    elif isinstance(node, graph.OutputNode):
        for input_node in node.from_op.inputs.values():
            node_visitor(input_node, visit_fn)
        visit_fn(node)
    else:
        raise errors.WeaveError(f"Unexpected node type {type(node)}")


@dataclasses.dataclass
class ForwardStitchedNode:
    """A node which contains pointers to the nodes which it is an input to, after stitching."""

    source_node: graph.Node
    input_to: set["ForwardStitchedNode"] = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class StitchedGraph2:
    leaf_nodes: set[graph.Node] = dataclasses.field(default_factory=set)
    forward_graph: dict[graph.Node, ForwardStitchedNode] = dataclasses.field(
        default_factory=dict
    )

    def add_node(self, node: graph.Node):
        node_visitor(node, self._add_node_visitor)

    def _assert_has_node(self, node: graph.Node):
        if node not in self.forward_graph:
            raise errors.WeaveError(
                f"Programming Error: Node {node} not in forward graph"
            )

    def _add_edge(self, from_node: graph.Node, to_node: graph.Node):
        self._assert_has_node(from_node)
        self._assert_has_node(to_node)
        self.forward_graph[from_node].input_to.add(self.forward_graph[to_node])

    def _remove_edge(self, from_node: graph.Node, to_node: graph.Node):
        self._assert_has_node(from_node)
        self._assert_has_node(to_node)
        self.forward_graph[from_node].input_to.remove(self.forward_graph[to_node])

    # def _stitch_node(self, from_node: graph.Node, orig_to_node: graph.Node, new_to_node: graph.Node):
    #     self._assert_has_node(from_node)
    #     self._assert_has_node(to_node)
    #     self._add_edge(from_node, to_node)
    #     if to_node not in self.forward_graph:
    #         raise errors.WeaveError(f"Programming Error: Node {to_node} not in forward graph")
    #     self.forward_graph[from_node].input_to.update(self.forward_graph[to_node].input_to)

    def _add_node_visitor(self, node: graph.Node):
        if node in self.forward_graph:
            forward_node = self.forward_graph[node]
        else:
            forward_node = ForwardStitchedNode(node)
        if isinstance(node, graph.OutputNode):
            for input_node in node.from_op.inputs.values():
                self._add_edge(input_node, node)
            self._stitch_lambda(node)

        self.forward_graph[node] = forward_node

    def _stitch_lambda(self, lambda_node: graph.OutputNode):
        lambda_node_name_endings = [
            "map",
            "sort",
            "filter",
            "groupby",
            "joinAll",
        ]
        if not any(
            lambda_node.from_op.name.endswith(ending)
            for ending in lambda_node_name_endings
        ):
            return

        row_arr_node = lambda_node.inputs.values()[0]
        fn_node = lambda_node.inputs.values()[1]

        row_nodes = []

        def visitor_fn(node: graph.Node):
            self._add_node_visitor(node)
            if isinstance(node, graph.VarNode) and node.name == "row":
                row_nodes.append(node)

        node_visitor(fn_node.val, visitor_fn)

        for row_node in row_nodes:
            self._add_edge(row_arr_node, row_node)
            if row_node not in self.forward_graph:
                raise errors.WeaveError(
                    f"Programming Error: Node {row_node} not in forward graph"
                )
            self.forward_graph[row_arr_node].input_to.update(
                self.forward_graph[row_node].input_to
            )

        row_arr_node.input_to.remove(self.forward_graph[lambda_node])

    def _stitch_lambda_visitor(
        self, node: graph.Node, var_node_map: dict[str, ForwardStitchedNode]
    ):
        self._add_node_visitor(node)
        if isinstance(node, graph.VarNode) and node.name in var_node_map:
            if node not in self.forward_graph:
                raise errors.WeaveError(
                    f"Programming Error: Node {node} not in forward graph"
                )
            var_node_map[node.name].input_to.update(self.forward_graph[node].input_to)

    # def add_nodes(self, nodes: list[graph.Node]):
    #     graph.map_nodes_full(nodes, self._add_node_no_map)

    # def stitch(self):


# @dataclasses.dataclass
# class StitchedGraph2:
#     leaf_nodes: set[graph.Node]
#     _orig_node_to_distinct_node: dict[graph.Node, graph.Node] = dataclasses.field(default_factory=dict)

#     def stitch():
#         self.initialize_orig_node_to_distinct_node()

#     def _initialize_orig_node_to_distinct_node(self):
#         def map_node_fn(node: graph.Node):
#             if isinstance(node, graph.VarNode):
#                 return node

#         graph.map_nodes_full(self.leaf_nodes, self.)

#     # def __init__(self, leaf_nodes: list[graph.Node]):
#     #     self.leaf_nodes = set(leaf_nodes)
#     #     self._orig_node_to_distinct_node = {}
#     #     graph.map_nodes_full(self.leaf_nodes, self.)


@dataclasses.dataclass
class OpCall:
    node: graph.OutputNode
    input_dict: dict[str, "ObjectRecorder"]
    output: "ObjectRecorder"

    @property
    def inputs(self) -> list["ObjectRecorder"]:
        return list(self.input_dict.values())

    # def __eq__(self, other: "OpCall") -> bool:
    #     return (
    #         self.node is other.node
    #         and all(other.input_dict[k] is v for k, v in self.input_dict.items())
    #         and self.output is other.output
    #     )


@dataclasses.dataclass()
class ObjectRecorder:
    node: graph.Node
    tags: dict[str, "ObjectRecorder"] = dataclasses.field(default_factory=dict)
    val: typing.Optional[typing.Any] = None
    calls: list[OpCall] = dataclasses.field(default_factory=list)

    def call_node(
        self, node: graph.OutputNode, input_dict: dict[str, "ObjectRecorder"]
    ) -> "ObjectRecorder":
        output = ObjectRecorder(node)
        self.calls.append(OpCall(node, input_dict, output))
        return output

    # def __hash__(self):
    #     return id(self)


class LiteralDictObjectRecorder(ObjectRecorder):
    val: dict[str, ObjectRecorder]


class LiteralListObjectRecorder(ObjectRecorder):
    val: list[ObjectRecorder]


@dataclasses.dataclass
class StitchedGraph:
    _node_map: typing.Dict[graph.Node, ObjectRecorder]

    def get_result(self, node: graph.Node) -> ObjectRecorder:
        return self._node_map[node]

    def add_result(self, node: graph.Node, result: ObjectRecorder) -> None:
        self._node_map[node] = result

    def _merge_result(self, node: graph.Node, result: ObjectRecorder) -> None:
        # Performs an in-place merge of the node result into the stitched graph.
        curr_result = self._node_map[node]
        if curr_result.val != result.val:
            raise errors.WeaveStitchGraphMergeError(
                f"Cannot merge ObjectRecorder with different values"
            )

        # Merge the calls
        known_called_nodes = {call.node for call in curr_result.calls}
        for call in result.calls:
            if call.node not in known_called_nodes:
                curr_result.calls.append(call)

        # Merge the tags
        for tag_name, other_tag_recorder in result.tags.items():
            if tag_name not in curr_result.tags:
                if other_tag_recorder.node in self._node_map:
                    other_tag_recorder = self._node_map[other_tag_recorder.node]
                else:
                    self.add_result(other_tag_recorder.node, other_tag_recorder)
                curr_result.tags[tag_name] = other_tag_recorder

    def add_subgraph_stitch_graph(self, other: "StitchedGraph") -> None:
        for node, result in other._node_map.items():
            if node not in self._node_map:
                self.add_result(node, result)
            else:
                self._merge_result(node, result)


def make_var_nodes_referentially_new(fn: graph.Node):
    res = graph.map_nodes_top_level(
        [fn],
        lambda n: graph.VarNode(n.type, n.name) if isinstance(n, graph.VarNode) else n,
    )[0]
    # breakpoint()
    return res


def stitch(
    leaf_nodes: list[graph.Node],
    var_values: typing.Optional[dict[str, ObjectRecorder]] = None,
) -> StitchedGraph:
    """Given a list of leaf nodes, stitch the graph together."""
    sg = StitchedGraph({})

    def handle_node(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            input_dict = {k: sg.get_result(v) for k, v in node.from_op.inputs.items()}
            sg.add_result(node, stitch_node(node, input_dict, sg))
        elif isinstance(node, graph.ConstNode):
            sg.add_result(node, ObjectRecorder(node, val=node.val))
        elif isinstance(node, graph.VarNode):
            if var_values and node.name in var_values:
                sg.add_result(node, var_values[node.name])
            else:
                # Originally, we would raise an error here, but we now allow
                # unbound vars to be in the graph. This makes sense to me (Tim)
                # since we could be stitching the compilation step of a
                # subgraph, but Shawn has pointed out that this case could be
                # removed if we stitched the entire graph in 1 pass. For now, we
                # assign an empty recorder, but this might be able to be
                # optimized out in the future.
                sg.add_result(node, ObjectRecorder(node))
                # raise errors.WeaveInternalError(
                #     "Encountered var %s but var_values not provided" % node.name
                # )
        else:
            raise errors.WeaveInternalError("Unexpected node type")
        return node

    graph.map_nodes_top_level(leaf_nodes, handle_node)

    return sg


def subgraph_stitch(
    function_node: graph.Node, args: dict[str, ObjectRecorder], sg: StitchedGraph
) -> ObjectRecorder:
    function_node = make_var_nodes_referentially_new(function_node)
    result_graph = stitch([function_node], args)
    sg.add_subgraph_stitch_graph(result_graph)
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
    node: graph.OutputNode, input_dict: dict[str, ObjectRecorder], sg: StitchedGraph
) -> ObjectRecorder:
    """
    It is the responsibility of the `stitch_node` function to do do two things:
    1. Ensure that the ObjectRecorder for the node is created (if not existing) and return it
    2. Ensure that all input `ObjectRecords` are connected to the ObjectRecorder in #1
        - These are two-way connections:
                - The ObjectRecorder in #1 has a list of inputs via `input_dict`
                - The ObjectRecorders in #2 have a list of outputs via `calls`

        Importantly, nodes which are `lambdas` (ex map). Need to traverse the inner function. This
        is done by calling `subgraph_stitch` and passing the current StitchedGraph. We need to pass
        the stitch graph so that the `subgraph_stitch` can merge the results of the inner function.
    """
    op = registry_mem.memory_registry.get_op(node.from_op.name)
    inputs = list(input_dict.values())
    if is_get_tag_op(op):
        tag_name = get_tag_name_from_tag_getter_op(op)
        return inputs[0].tags[tag_name]
    elif node.from_op.name.endswith("createIndexCheckpointTag"):
        inputs[0].tags["indexCheckpoint"] = ObjectRecorder(node)
    elif node.from_op.name == "dict":
        return LiteralDictObjectRecorder(node, val=input_dict)
    elif node.from_op.name == "list":
        # Merge element tags together and place them on the outer list.
        # This is overly aggressive, but it means we don't need to provide
        # special handling for concat and other structural list ops for
        # now.
        tags: dict[str, ObjectRecorder] = {}
        for input in input_dict.values():
            tags.update(input.tags)
        res = LiteralListObjectRecorder(node, tags=tags, val=list(input_dict.values()))
        op_call = OpCall(node, input_dict, res)
        for input in input_dict.values():
            input.calls.append(op_call)
        return res
    elif node.from_op.name.endswith("pick"):
        if isinstance(node.from_op.inputs["key"], graph.ConstNode):
            key = node.from_op.inputs["key"].val
            if isinstance(inputs[0], LiteralDictObjectRecorder):
                return inputs[0].val[key]
            else:
                # This is the case that the picked key is not found in the
                # dictionary. In this case, we just ignore the pick and don't
                # stitch any further.
                pass
        else:
            # In this case, we don't have a constant key. This case comes up
            # very often as it is used for run colors. in particular, run colors
            # in the table is something like {"run_name":
            # "run_color"}.pick([long_graph].name()) In this case, we don't know
            # which key to pick, so we just ignore. In the future, we may need
            # to act as if we are picking every key?
            pass
    elif node.from_op.name.endswith("map"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        # Return the resulting object from map!
        return subgraph_stitch(fn, {"row": inputs[0]}, sg)
    elif node.from_op.name.endswith("sort") or node.from_op.name.endswith("filter"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        subgraph_stitch(fn, {"row": inputs[0]}, sg)
        # # Return the original object
        return inputs[0]
    elif node.from_op.name.endswith("groupby"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        # The output of the subgraph function is the group key which becomes
        # the groupKey tag.
        groupkey = subgraph_stitch(fn, {"row": inputs[0]}, sg)
        inputs[0].tags["groupKey"] = groupkey
        # And we return the original object
        return inputs[0]
    elif node.from_op.name.endswith("joinAll"):
        fn = inputs[1].val
        if fn is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        # The output of the subgraph function is the joinKey which becomes
        # the joinkey tag.
        # TODO: Do we need to do this for each input?
        joinKey = subgraph_stitch(fn, {"row": inputs[0]}, sg)
        inputs[0].tags["joinObj"] = joinKey
        # And we return the original object
        return inputs[0]
    elif len(inputs) == 0:
        # op does not have any inputs, just track its downstream calls
        return ObjectRecorder(node)
    # Otherwise, not a special op, track its call.
    return inputs[0].call_node(node, input_dict)


def stitch_node(
    node: graph.OutputNode, input_dict: dict[str, ObjectRecorder], sg: StitchedGraph
) -> ObjectRecorder:
    op = registry_mem.memory_registry.get_op(node.from_op.name)
    input_names = list(input_dict.keys())
    inputs = list(input_dict.values())

    result = stitch_node_inner(node, input_dict, sg)

    # Tag logic
    # If the op is a mapped, derived op, then we need the tags to flow
    # internally. We know we need to do this because there is special tag
    # handling logic in the mapped ops which does a parallel job. Note: This is
    # probably somehting that needs to be done for arrow as well.
    if op.derived_from and op.derived_from.derived_ops.get("mapped"):
        if opdef_util.should_tag_op_def_outputs(op.derived_from):
            result.tags = inputs[0].tags
            result.tags[input_names[0]] = inputs[0]
        elif opdef_util.should_flow_tags(op.derived_from):
            result.tags = inputs[0].tags
    # Always do this, even for mapped
    if opdef_util.should_tag_op_def_outputs(op):
        result.tags = inputs[0].tags
        result.tags[input_names[0]] = inputs[0]
    elif opdef_util.should_flow_tags(op):
        result.tags = inputs[0].tags

    return result
