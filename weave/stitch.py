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

from .ops_primitives import _dict_utils

from . import graph
from . import errors
from . import registry_mem
from . import op_def
from .language_features.tagging import opdef_util
from . import weave_types as types


@dataclasses.dataclass
class OpCall:
    node: graph.OutputNode
    input_dict: dict[str, "ObjectRecorder"]
    output: "ObjectRecorder"

    @property
    def inputs(self) -> list["ObjectRecorder"]:
        return list(self.input_dict.values())


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


class LiteralDictObjectRecorder(ObjectRecorder):
    val: dict[str, ObjectRecorder]


class LiteralListObjectRecorder(ObjectRecorder):
    val: list[ObjectRecorder]


def node_shortname(node: graph.Node) -> str:
    if isinstance(node, graph.OutputNode):
        return node.from_op.name
    elif isinstance(node, graph.ConstNode):
        return f"C[{str(node.val)[:10]}]"
    elif isinstance(node, graph.VarNode):
        return f"V[{node.name}]"
    else:
        raise errors.WeaveInternalError(f"Unknown node type {type(node)}")


@dataclasses.dataclass
class StitchedGraph:
    _node_map: typing.Dict[graph.Node, ObjectRecorder]

    def has_result(self, node: graph.Node) -> bool:
        return node in self._node_map

    def get_result(self, node: graph.Node) -> ObjectRecorder:
        return self._node_map[node]

    def add_result(self, node: graph.Node, result: ObjectRecorder) -> None:
        self._node_map[node] = result

    def print_debug_summary(self) -> None:
        res = ""
        node_names = {
            orig_node: f"<{i}-{node_shortname(orig_node)}>"
            for i, (orig_node, recorder) in enumerate(self._node_map.items())
        }
        res += "\n" + "StitchedGraph Summary:"
        res += "\n" + "  Nodes:"
        for curr_node, curr_node_name in node_names.items():
            if isinstance(curr_node, graph.OutputNode):
                res += (
                    "\n"
                    + f"  * {curr_node_name}({','.join([node_names[input_node] for input_node in  curr_node.from_op.inputs.values()])})"
                )
            else:
                res += "\n" + f"  * {curr_node_name}"
            recorder = self._node_map[curr_node]
            if recorder.calls:
                res += (
                    "\n"
                    + f"    calls: {','.join([node_names[call.node] for call in recorder.calls])}"
                )
            if recorder.tags:
                res += (
                    "\n"
                    + f"    tags: {','.join([str((tag_name, node_names[tag_recorder.node])) for tag_name, tag_recorder in recorder.tags.items()])}"
                )
        print(res)


def stitch(
    leaf_nodes: list[graph.Node],
    var_values: typing.Optional[dict[str, ObjectRecorder]] = None,
    stitched_graph: typing.Optional[StitchedGraph] = None,
    on_error: graph.OnErrorFnType = None,
) -> StitchedGraph:
    """Given a list of leaf nodes, stitch the graph together."""

    if stitched_graph is None:
        sg = StitchedGraph({})
    else:
        sg = stitched_graph

    def handle_node(node: graph.Node) -> graph.Node:
        if sg.has_result(node):
            return node
        if isinstance(node, graph.OutputNode):
            input_dict = {k: sg.get_result(v) for k, v in node.from_op.inputs.items()}
            sg.add_result(node, stitch_node(node, input_dict, sg))
        elif isinstance(node, graph.ConstNode):
            # Note from Tim: I believe this block of code should be correct (ie. stitching inside
            # of static lambdas). I wrote it while implementing a fix but it ended up not being needed.
            # Stitch is a particularly touchy part of the code base. So i would rather leave this
            # code commented out for now, but not delete it. My gut tells me that any static lambda
            # will be re-executed if needed and therefore re-stitched. And furthermore, any caller
            # of stitch right now (eg. gql compile) should explicitly NOT mutate static lambdas. So
            # it might be a foot-gun to allow this code to run, even if it is correct. Let's find a
            # use case for this code before we uncomment it.
            # is_static_lambda = (
            #     isinstance(node.type, types.Function)
            #     and len(node.type.input_types) == 0
            # )
            # if is_static_lambda:
            #     sg.add_result(node, subgraph_stitch(node.val, {}, sg))
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

    graph.map_nodes_top_level(leaf_nodes, handle_node, on_error)

    return sg


def subgraph_stitch(
    function_node: graph.Node, args: dict[str, ObjectRecorder], sg: StitchedGraph
) -> ObjectRecorder:
    result_graph = stitch([function_node], args, stitched_graph=sg)
    return result_graph.get_result(function_node)


def is_root_op(op: op_def.OpDef) -> bool:
    return (
        op.name == "root-project"
        or op.name == "get"
        or op.name == "getReturnType"
        or op.name == "render_table_runs2"
        or op.name == "project-runs2"
    )


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
    elif is_mapped_get_tag_op(op):
        tag_name = get_tag_name_from_mapped_tag_getter_op(op)
        return inputs[0].tags[tag_name]
    elif node.from_op.name.endswith("createIndexCheckpointTag"):
        inputs[0].tags["indexCheckpoint"] = ObjectRecorder(node)
        return inputs[0]
    elif node.from_op.name == "dict":
        return LiteralDictObjectRecorder(node, val=input_dict)
    elif node.from_op.name.endswith("__getitem__"):
        return inputs[0]
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
            path = _dict_utils.split_escaped_string(node.from_op.inputs["key"].val)
            if len(path) == 0:
                return ObjectRecorder(node, inputs[0].tags)
            key = _dict_utils.unescape_dots(path[0])
            if (
                isinstance(inputs[0], LiteralDictObjectRecorder)
                and key in inputs[0].val
            ):
                val = inputs[0].val.get(key)
                if val is not None:
                    if len(path) == 1:
                        return val
                    # If there are further path elements, recursively stitch.
                    sub_key = ".".join(path[1:])
                    # We manually construct a typedDict-pick op with the next sub-key
                    new_node = graph.OutputNode(
                        node.type,
                        "typedDict-pick",
                        {
                            # the first argument is unused by stitch_node_inner,
                            # so just set it to None
                            "arr": graph.ConstNode(types.NoneType(), None),
                            "key": graph.ConstNode(types.String(), sub_key),
                        },
                    )
                    # Make a new ObjectRecorder to hold the sub-key value.
                    oj_key = ObjectRecorder(new_node, {}, sub_key)
                    return stitch_node_inner(new_node, {"self": val, "key": oj_key}, sg)

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
    elif node.from_op.name.endswith("join"):
        fn1 = inputs[2].val
        fn2 = inputs[3].val
        if fn1 is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        if fn2 is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        alias1 = inputs[4].val
        alias2 = inputs[5].val
        if alias1 is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        if alias2 is None:
            raise errors.WeaveInternalError("non-const not yet supported")
        joinKey1 = subgraph_stitch(fn1, {"row": inputs[0]}, sg)
        joinKey2 = subgraph_stitch(fn2, {"row": inputs[1]}, sg)
        result = LiteralDictObjectRecorder(
            node, val={alias1: inputs[0], alias2: inputs[1]}
        )
        # We only pass joinKey1 in as tag. I think this is ok, as stitch has already determined
        # that everything in the tag is a necessary column (we needed those columns to produce
        # the join key in the first place).
        # But I'm not totally sure!
        result.tags["joinObj"] = joinKey1
        return result
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
    elif node.from_op.name == "execute":
        # Special case where the execute op is used to execute a subgraph.
        # We want the results to flow through
        fn_node = inputs[0].val
        if fn_node is None:
            raise errors.WeaveInternalError("execute function should not be none")
        return subgraph_stitch(fn_node, {}, sg)
    elif len(inputs) == 0:
        # op does not have any inputs, just track its downstream calls
        return ObjectRecorder(node)
    # Otherwise, not a special op, track its call.
    return inputs[0].call_node(node, input_dict)


def _apply_tag_rules_to_stitch_result(
    result: ObjectRecorder,
    op: op_def.OpDef,
    inputs: list[ObjectRecorder],
    input_names: list[str],
) -> None:
    # Tag logic
    # If the op is a mapped, derived op, then we need the tags to flow
    # internally. We know we need to do this because there is special tag
    # handling logic in the mapped ops which does a parallel job. Note: This is
    # probably something that needs to be done for arrow as well.
    should_tag_with_inputs = False
    should_flow_tags = False
    if op.derived_from and op.derived_from.derived_ops.get("mapped"):
        if opdef_util.should_tag_op_def_outputs(op.derived_from):
            should_tag_with_inputs = True
        elif opdef_util.should_flow_tags(op.derived_from):
            should_flow_tags = True
    # Always do this, even for mapped
    if opdef_util.should_tag_op_def_outputs(op):
        should_tag_with_inputs = True
    elif opdef_util.should_flow_tags(op):
        should_flow_tags = True

    if should_tag_with_inputs:
        result.tags.update(inputs[0].tags)
        result.tags[input_names[0]] = inputs[0]
    elif should_flow_tags:
        result.tags.update(inputs[0].tags)


def stitch_node(
    node: graph.OutputNode, input_dict: dict[str, ObjectRecorder], sg: StitchedGraph
) -> ObjectRecorder:
    op = registry_mem.memory_registry.get_op(node.from_op.name)
    input_names = list(input_dict.keys())
    inputs = list(input_dict.values())

    result = stitch_node_inner(node, input_dict, sg)
    _apply_tag_rules_to_stitch_result(result, op, inputs, input_names)

    return result
