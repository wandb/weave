"""
This module contains a new Version 2 of the StitchedGraph class and related functions. Stitch is used in 2 places in Weave:
1. (compile_domain) When constructing GQL based on the graph of ops
2. (compile_table) When constructing a run history table selection based on the graph of ops
    - Note: the `get_projection` logic in #2 is used as a subset of #1 for summary/config key selection.

The key use case of stitch is as follows:
```
# create a stitched graph by passing in target nodes
sg = stitch([op1, op2, op3])

# fetch an object recorder for any node in the graph
obj = sg.get_result(op1) # note: does not need to be a target node.

# Obtain a list of direct "columns" accessed by ops in the graph
calls = obj.calls
```

The most naive implementation would be to simply invert the nodes (since nodes store their inputs). However,
this would fail to traverse all the special cases. There are explicitly 4 special cases to handle:

1. So-called "lambda" ops. "Lambda ops" are ops which accept a function as an input. As of this writing, these
    are: opMap, opMapEach, opSort, opFilter, opGroupBy, opJoin, opJoinAll. These are special because their inner
    lambda function may meaningfully access the outer scope. Within this set there are 2 sub-special cases:
        a) opMap and opMapEach - unlike their sibling lambda ops, these ops, therefore downstream ops may be operating
            on the graph of the inner lambda function. This is in contrast to the peer ops (ex. Sort), where downstream
            ops do not operate on the graph of the inner lambda function.
        b) opJoin - this is special because there are actually 2 lambda functions. This just means extra bookkeeping.
2. So-called "Passthrough" ops. These ops are ops which operate on lists (concat, flatten, etc). They are special in that
    the `call` chain should "pass through" these ops transparently.
3. Index / Pick Operations. These are special in that when a pick follows a dictionary constructor, or an index follows
    a list constructor (and the keys are consts), then we can more intelligently construct the call chain.
    These constructors serve as a "router" to the correct inputs.
4. Tags. Some ops Tag their outputs. There are generally 3 cases here: run/project ops, group/join, and indexCheckpoints.
    The idea of stitch is that we "resolve" where tags originate, such that the downstream calls from a tag getter are
    attached to the op which produces the object in the tag.


The original implementation of stitch attempts to solve all these problems simultaneously. However, upon deeper analysis
I believe to do this correctly, we would need to perform many passes of the graph at most N passes, (where N is the number
of nodes). While we can do #1 in in a single pass, #2/3/4 effect each other. each time a rule "dirties" the graph, we would
need to re-run all rules. Imagine a particularly nasty graph where we had a chain of tagger-pick-index repeated many times,
followed by index-pick-tagGetter repeated many times. Each pass would resolve part of the graph, requiring another pass. This
doesn't even account for the complexity that pick can be applied through a list!. 

In order to avoid this multi-pass complexity, we make the following simplifying assumptions:
1. While we MUST never miss assigning a correct call, we permit ourselves a "false positive" - That is, we might assign a call
    to a node which is not actually used. The net result is we may request a bit more data, in certain certain cases.

"""


from collections import defaultdict
import dataclasses
import typing

from . import graph
from . import registry_mem
from . import op_def
from . import types
from .language_features.tagging import opdef_util


@dataclasses.dataclass
class DAGNode:
    original_node: graph.Node
    stitched_inputs: set["DAGNode"] = dataclasses.field(default_factory=set)
    stitched_outputs: set["DAGNode"] = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class EdgeDAG:
    """
    A EdgeDAG maintains a DAG (with O(1) access to node inputs, and the nodes which consume them). This is in
    contrast to the normal graph which only maintains inputs. When initializing a EdgeDAG, we build the DAG from
    the normal graph. At initialization, each original node has a 1-1 mapping with a node in the EdgeDAG - with
    the edges being a perfect mapping of the original edges. However, the EdgeDAG supports a number of mutations
    which will modify the edges to support different compellation goals. It is entirely possible that by the end
    of such mutations, an original node has different edges coming in, going out, or both - even completely
    disconnected from the graph!
    """

    _original_node_to_dag_node: dict[graph.Node, "DAGNode"] = dataclasses.field(
        default_factory=dict
    )
    _locked: bool = False

    def lock_graph(self) -> None:
        self._locked = True

    def add_node(self: "EdgeDAG", node_to_add: graph.Node) -> None:
        if not isinstance(node_to_add, graph.OutputNode):
            return
        output_node = node_to_add
        for input_node in output_node.from_op.inputs.values():
            self._add_raw_edge(input_node, output_node)
            self.add_node(input_node)

            # Explode any lambda params
            if is_fn_node(input_node):
                fn_node = input_node.val
                self.add_node(fn_node)

    def _ensure_node(self, node: graph.Node) -> DAGNode:
        if self._locked:
            raise RuntimeError("Cannot add nodes to a locked graph")

        if node not in self._original_node_to_dag_node:
            self._original_node_to_dag_node[node] = DAGNode(node)
        return self._original_node_to_dag_node[node]

    def _add_raw_edge(self, input_node: graph.Node, output_node: graph.Node) -> None:
        self._add_dag_edge(
            self._ensure_node(input_node), self._ensure_node(output_node)
        )

    def _add_dag_edge(self, input_node: DAGNode, output_node: DAGNode) -> None:
        input_node.stitched_outputs.add(output_node)
        output_node.stitched_inputs.add(input_node)

    def _remove_dag_edge(self, input_node: DAGNode, output_node: DAGNode) -> None:
        input_node.stitched_outputs.remove(output_node)
        output_node.stitched_inputs.remove(input_node)

    def _get_leaf_nodes(self) -> list[DAGNode]:
        return [
            node
            for node in self._original_node_to_dag_node.values()
            if not node.stitched_outputs
            and isinstance(node.original_node, graph.OutputNode)
        ]

    def _apply_bottoms_up_bfs(self, fn: typing.Callable[[DAGNode], None]) -> None:
        """
        Apply a function to each node in the graph, in a bottoms up BFS order. This means that the function will be
        applied to all nodes which have no outputs first, then all nodes which have outputs which have no outputs, etc.
        """
        self.lock_graph()
        leaf_nodes = self._get_leaf_nodes()
        visited = set()
        while leaf_nodes:
            node = leaf_nodes.pop()
            if node in visited:
                continue
            visited.add(node)
            fn(node)
            leaf_nodes.extend(node.stitched_inputs)

    def apply_lambda_stitch(self) -> None:
        """ """

        def lambda_stitch(node: DAGNode) -> None:
            if isinstance(node.original_node, graph.OutputNode):
                op_name = node.original_node.from_op.name
                if op_name.endswith("map") or op_name.endswith("mapEach"):
                    orig_inputs = list(node.original_node.from_op.inputs.values())
                    orig_fn_node = orig_inputs[1]
                    orig_var_nodes = graph.expr_vars(orig_fn_node)
                    orig_var_nodes = [
                        var_node
                        for var_node in orig_var_nodes
                        if var_node.name == "row"
                    ]

                    dag_arr_node = self._ensure_node(orig_inputs[0])
                    dag_fn_node = self._ensure_node(orig_fn_node)
                    dag_var_nodes = [
                        self._ensure_node(var_node) for var_node in orig_var_nodes
                    ]

                    # For each output of the map node, delete it and add a link from the fn node
                    for output_node in node.stitched_outputs:
                        self._remove_dag_edge(node, output_node)
                        self._add_dag_edge(dag_fn_node, output_node)

                    if len(dag_var_nodes) > 0:
                        # In this case, we want to unlink the varNode from each of it's outputs, and for each
                        # output, add a new link to the original array node.
                        for dag_var_node in dag_var_nodes:
                            for output_node in dag_var_node.stitched_outputs:
                                self._remove_dag_edge(dag_var_node, output_node)
                                self._add_dag_edge(dag_arr_node, output_node)
                    else:
                        # This is sort of a weird situation, but we need to allow tag lineage to flow through. We can
                        # do this by Lambda bridge! - This dummy dag node will prevent non-tag stitch operations from
                        # flowing through, but will allow tags later on.
                        lambda_tag_bridge = DAGNode(
                            graph.ConstNode(types.NoneType(), None)
                        )
                        for output_node in node.stitched_outputs:
                            self._add_dag_edge(lambda_tag_bridge, output_node)
                            self._add_dag_edge(dag_arr_node, lambda_tag_bridge)
                # elif op_name.endswith("groupby"):

        self._apply_bottoms_up_bfs(lambda_stitch)


# def _lambda_node


# @dataclasses.dataclass
# class DependencyGraph:
#     # Map of inputs to outputs
#     input_to_output: defaultdict[graph.Node, set[graph.Node]] = dataclasses.field(
#         default_factory=lambda: defaultdict(set)
#     )

#     # Map from outputs to inputs
#     output_to_input: defaultdict[graph.Node, set[graph.Node]] = dataclasses.field(
#         default_factory=lambda: defaultdict(set)
#     )

#     def add_node(self: "DependencyGraph", node_to_add: graph.Node) -> None:
#         if not isinstance(node_to_add, graph.OutputNode):
#             return
#         output_node = node_to_add
#         node_inputs = list(output_node.from_op.inputs.values())
#         # Add each input node to the graph and mark the output dependents
#         for input_node_ndx, input_node in enumerate(node_inputs):
#             if node_is_mapper(input_node):
#                 # Special case for mappers - if the input is a mapper (opMap or opMapEach), then we
#                 # need to connect the fn_node to the output node directly (since the tag getter can
#                 # apply to either inside the map fn or to the map fn itself). We don't do this
#                 # for for all lambdas (like opSort), since the lambda terminates with the execution
#                 # of that op.
#                 self._add_edge(get_map_fn_from_mapper_node(input_node), output_node)
#             self._add_edge(input_node, output_node)
#             self.add_node(input_node)

#             # Special case for lambdas. Example:
#             # ouput_node = opMap
#             # fn_node = the lambda
#             if is_fn_node(input_node):
#                 fn_node = input_node.val

#                 # Add the node to the graph
#                 self.add_node(fn_node)

#                 # Get a reference to the vars:
#                 vars = graph.expr_vars(fn_node)

#                 # Assume that each var depends on all inputs (this is a more liberal assumption than we need)
#                 # If we wanted to optimize further, we could have branching rules for each lambda function,
#                 # but this helps it be more general.
#                 for var in vars:
#                     for var_input_to in self.input_to_output[var]:
#                         # Here, we only add the input nodes that come before the current fn param!
#                         for input_node_2 in node_inputs[:input_node_ndx]:
#                             self._add_edge(input_node_2, var_input_to)

#     def _add_edge(self, input_node: graph.Node, output_node: graph.Node) -> None:
#         self.input_to_output[input_node].add(output_node)
#         self.output_to_input[output_node].add(input_node)


@dataclasses.dataclass
class TagSubscriptionManager:
    downstream_tag_subscriptions: defaultdict[
        graph.Node, defaultdict[str, set[graph.Node]]
    ] = dataclasses.field(default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    node_provides_tag_for_downstream_nodes: defaultdict[
        graph.Node, set[graph.Node]
    ] = dataclasses.field(default_factory=lambda: defaultdict(set))

    def _direct_add_subscriptions_for_tag_to_node(
        self: "TagSubscriptionManager",
        sub_nodes: set[graph.Node],
        tag_name: str,
        to_node: graph.Node,
    ) -> None:
        self.downstream_tag_subscriptions[to_node][tag_name].update(sub_nodes)

    def _direct_merge_subscriptions_into_node_from_downstream_node(
        self: "TagSubscriptionManager", node: graph.Node, downstream_node: graph.Node
    ) -> None:
        for tag_name, tag_subscriptions in self.downstream_tag_subscriptions[
            downstream_node
        ].items():
            self._direct_add_subscriptions_for_tag_to_node(
                tag_subscriptions, tag_name, node
            )

    def rollup_tags(
        self: "TagSubscriptionManager",
        curr_node: graph.Node,
        downstream_nodes: set[graph.Node],
        dg: DependencyGraph,
    ) -> None:
        for downstream_node in downstream_nodes:
            tag_get_name = node_gets_tag_by_name(downstream_node)
            if tag_get_name:
                # If the current node is a tag getter, then it adds itself
                self.downstream_tag_subscriptions[curr_node][tag_get_name].add(
                    downstream_node
                )
            else:
                # else, rollup the downstream tag subscriptions
                # Merge the downstream tag subscriptions
                self._direct_merge_subscriptions_into_node_from_downstream_node(
                    curr_node, downstream_node
                )

        # If the current node provides a tag, then we need to connect the wormholes
        # and update the downstream tag subscriptions
        provider_result = node_provides_tag(curr_node)
        if provider_result:
            subscriptions_to_provided_tag = self.downstream_tag_subscriptions[
                curr_node
            ][provider_result.tag_name]
            self.downstream_tag_subscriptions[curr_node][
                provider_result.tag_name
            ] = set()
            for provider in provider_result.tag_providers:
                for sub_node in subscriptions_to_provided_tag:
                    self.node_provides_tag_for_downstream_nodes[provider].update(
                        dg.input_to_output[sub_node]
                    )
                    self.rollup_tags(provider, dg.input_to_output[sub_node], dg)


# Just for compatibility with the old stitcher
@dataclasses.dataclass
class ObjectRecorder:
    node: graph.Node
    _sg2: "StitchedGraph"

    @property
    def calls(self) -> list["OpCall"]:
        return [
            OpCall(node, self._sg2)
            for node in self._sg2.get_combined_outputs(self.node)
            if isinstance(node, graph.OutputNode)
        ]

    @property
    def val(self) -> typing.Any:
        if isinstance(self.node, graph.ConstNode):
            return self.node.val
        return None


# Just for compatibility with the old stitcher
@dataclasses.dataclass
class OpCall:
    node: graph.OutputNode
    _sg2: "StitchedGraph"

    @property
    def inputs(self) -> list["ObjectRecorder"]:
        return [
            self._sg2.get_result(input_node)
            for input_node in self.node.from_op.inputs.values()
        ]

    @property
    def output(self) -> "ObjectRecorder":
        return ObjectRecorder(self.node, self._sg2)


def is_call_passthrough(node: graph.Node) -> bool:
    if isinstance(node, graph.OutputNode):
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        return (
            op.name.endswith("offset")
            or op.name.endswith("limit")
            or op.name.endswith("index")
            # or op.name.endswith("__getitem__")
            # or op.name.endswith("pick")
            or op.name.endswith("concat")
            or op.name.endswith("contains")
            or op.name.endswith("list")
            or op.name.endswith("dict")
            or op.name.endswith("flatten")
            or op.name.endswith("dropna")
            or op.name.endswith("filter")
            or op.name.endswith("join")
            or op.name.endswith("joinAll")
            or op.name.endswith("groupby")
            or op.name.endswith("createIndexCheckpointTag")
        )
    return False


@dataclasses.dataclass
class StitchedGraph:
    _subscription_manager: TagSubscriptionManager
    _dependency_graph: DependencyGraph

    def get_combined_outputs(self, node: graph.Node) -> set[graph.Node]:
        direct_outputs = self._dependency_graph.input_to_output[node]
        tag_subscriptions = (
            self._subscription_manager.node_provides_tag_for_downstream_nodes[node]
        )
        return direct_outputs.union(tag_subscriptions)
        # child_outputs = direct_outputs.union(tag_subscriptions)
        # final_outputs = set()
        # for child in child_outputs:
        #     final_outputs.add(child)
        #     if is_call_passthrough(child):
        #         final_outputs = final_outputs.union(self.get_combined_outputs(child))
        #     else:
        #         final_outputs.add(child)

        # return final_outputs

    # Just for compatibility with the old stitcher
    def get_result(self, node: graph.Node) -> ObjectRecorder:
        return ObjectRecorder(node, self)


def stitch(nodes: list[graph.Node]) -> StitchedGraph:
    """
    Stitch2 is a new version of the stitcher that uses a bottom-up traversal, similar
    to Weave0. Here, we start at the leaf nodes, and collect "tag getters" along the way.
    """
    # Tag subscription manager
    tag_subscription_manager = TagSubscriptionManager()

    # First we need to create a dependency graph (basically a forward graph in our old terminology)
    dependency_graph = DependencyGraph()
    for node in nodes:
        dependency_graph.add_node(node)

    # Next, we basically do BFS on the nodes
    frontier = [n for n in nodes]
    visited = set()
    while frontier:
        # Standard BFS bookkeeping
        curr_node = frontier.pop()
        if curr_node in visited:
            continue
        visited.add(curr_node)

        # Add nodes to the frontier
        ## Add the node's inputs to the frontier if all their dependents have been visited
        for input_node in dependency_graph.output_to_input[curr_node]:
            if all(
                output_of_input in visited
                for output_of_input in dependency_graph.input_to_output[input_node]
            ):
                frontier.append(input_node)

        ## Special case for lambdas
        if is_fn_node(curr_node):
            fn_node = typing.cast(graph.ConstNode, curr_node).val
            if all(
                output_of_input in visited
                for output_of_input in dependency_graph.input_to_output[fn_node]
            ):
                frontier.append(fn_node)

        # Now we can process the node
        tag_subscription_manager.rollup_tags(
            curr_node, dependency_graph.input_to_output[curr_node], dependency_graph
        )

    return StitchedGraph(tag_subscription_manager, dependency_graph)


def is_fn_node(node: graph.Node) -> bool:
    return isinstance(node, graph.ConstNode) and isinstance(node.val, graph.Node)


def node_gets_tag_by_name(node: graph.Node) -> typing.Optional[str]:
    if isinstance(node, graph.OutputNode):
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        if is_get_tag_op(op):
            return get_tag_name_from_tag_getter_op(op)
        elif is_mapped_get_tag_op(op):
            return get_tag_name_from_mapped_tag_getter_op(op)
    return None


def node_is_mapper(node: graph.Node) -> bool:
    return isinstance(node, graph.OutputNode) and (
        node.from_op.name.endswith("map") or node.from_op.name.endswith("mapEach")
    )


def get_map_fn_from_mapper_node(node: graph.OutputNode) -> graph.Node:
    return list(node.from_op.inputs.values())[1].val


def get_input_fn_vals(node: graph.OutputNode) -> list[graph.Node]:
    return [
        n.val for n in node.from_op.inputs.values() if isinstance(n.val, graph.Node)
    ]


@dataclasses.dataclass
class TagProviderResult:
    tag_name: str
    tag_providers: list[graph.Node]


def node_provides_tag(node: graph.Node) -> typing.Optional[TagProviderResult]:
    if isinstance(node, graph.OutputNode):
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        if (
            op.derived_from
            and op.derived_from.derived_ops.get("mapped")
            and opdef_util.should_tag_op_def_outputs(op.derived_from)
        ) or opdef_util.should_tag_op_def_outputs(op):
            first_input_key, first_input_node = list(node.from_op.inputs.items())[0]
            return TagProviderResult(first_input_key, [first_input_node])
        elif node.from_op.name.endswith("groupby"):
            return TagProviderResult("groupKey", get_input_fn_vals(node))
        elif node.from_op.name.endswith("joinAll"):
            return TagProviderResult("joinKey", get_input_fn_vals(node))
        elif node.from_op.name.endswith("join"):
            return TagProviderResult("joinKey", get_input_fn_vals(node))
    return None


def is_mapped_get_tag_op(op: op_def.OpDef) -> bool:
    if op.derived_from and op.derived_from.derived_ops.get("mapped") == op:
        return is_get_tag_op(op.derived_from)
    return False


def is_get_tag_op(op: op_def.OpDef) -> bool:
    return op._gets_tag_by_name != None


def get_tag_name_from_tag_getter_op(op: op_def.OpDef) -> str:
    assert (
        op._gets_tag_by_name != None
    ), "Caller should verify that this is a tag getter op"
    return op._gets_tag_by_name  # type: ignore


def get_tag_name_from_mapped_tag_getter_op(op: op_def.OpDef) -> str:
    assert (
        op.derived_from != None
    ), "Caller should verify that this is a mapped tag getter op"
    return get_tag_name_from_tag_getter_op(op.derived_from)  # type: ignore
