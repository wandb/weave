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
from . import op_def
from .language_features.tagging import opdef_util


def stitch(
    leaf_nodes: list[graph.Node],
    # var_values: typing.Optional[dict[str, ObjectRecorder]] = None,
) -> "StitchedGraph":
    """Given a list of leaf nodes, stitch the graph together."""
    sg = StitchedGraph()
    sg.stitch(leaf_nodes)
    return sg


@dataclasses.dataclass
class OpCall:
    node: graph.OutputNode
    input_dict: dict[str, "ObjectRecorder"]
    output: "ObjectRecorder"

    @property
    def inputs(self) -> list["ObjectRecorder"]:
        return list(self.input_dict.values())


@dataclasses.dataclass
class ObjectRecorder:
    node: graph.Node
    tags: dict[str, "ObjectRecorder"] = dataclasses.field(default_factory=dict)
    calls: list[OpCall] = dataclasses.field(default_factory=list)

    # def __post_init__(self) -> None:
    #     print(f"ObjectRecorder.__post_init__ <{id(self)}, {id(self.node)}>{self.node}")
    #     # if str(self.node) == "list(1, 2)[0]":
    #     #     print("here")

    def __hash__(self) -> int:
        return id(self)


@dataclasses.dataclass
class ConstNodeObjectRecorder(ObjectRecorder):
    val: typing.Optional[typing.Any] = None


@dataclasses.dataclass
class LiteralDictObjectRecorder(ObjectRecorder):
    val: dict[str, ObjectRecorder] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class LiteralListObjectRecorder(ObjectRecorder):
    val: list[ObjectRecorder] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class StitchedGraph:
    _node_recorder_map: typing.Dict[graph.Node, ObjectRecorder] = dataclasses.field(
        default_factory=dict
    )
    _node_call_map: typing.Dict[graph.Node, OpCall] = dataclasses.field(
        default_factory=dict
    )

    def get_result(self, node: graph.Node) -> ObjectRecorder:
        return self._recorder_for_node(node)

    def _set_object_recorder(self, node: graph.Node, recorder: ObjectRecorder) -> None:
        if node in self._node_recorder_map and not isinstance(node, graph.VarNode):
            raise errors.WeaveInternalError(
                f"Non VarNode {node} already has an object recorder"
            )
        self._node_recorder_map[node] = recorder

    def _recorder_for_node(self, node: graph.Node) -> ObjectRecorder:
        if (
            isinstance(node, graph.OutputNode)
            and node.from_op.name.endswith("pick")
            and "groupkey" in str(node)
        ):
            print(f"recorder_for_node {node}")
        if node not in self._node_recorder_map:
            if isinstance(node, graph.OutputNode) and node.from_op.name.endswith(
                "pick"
            ):
                print("minting new")
            if isinstance(node, graph.OutputNode) and node.from_op.name.endswith(
                "dict"
            ):
                self._node_recorder_map[node] = LiteralDictObjectRecorder(node)
            elif isinstance(node, graph.OutputNode) and node.from_op.name.endswith(
                "list"
            ):
                self._node_recorder_map[node] = LiteralListObjectRecorder(node)
            elif isinstance(node, graph.ConstNode):
                self._node_recorder_map[node] = ConstNodeObjectRecorder(
                    node, val=node.val
                )
            else:
                self._node_recorder_map[node] = ObjectRecorder(node)
        return self._node_recorder_map[node]

    def _call_for_node(self, node: graph.OutputNode) -> OpCall:
        if node not in self._node_call_map:
            inputs = {
                k: self._recorder_for_node(v) for k, v in node.from_op.inputs.items()
            }
            output = self._recorder_for_node(node)
            self._node_call_map[node] = OpCall(node, inputs, output)
        return self._node_call_map[node]

    def _add_call(self, from_node: graph.Node, to_node: graph.OutputNode) -> None:
        self._recorder_for_node(from_node).calls.append(self._call_for_node(to_node))

    def stitch(
        self,
        leaf_nodes: list[graph.Node],
        frame: typing.Optional[dict[str, graph.Node]] = None,
    ) -> None:
        """Given a list of leaf nodes, stitch the graph together."""

        def handle_node(node: graph.Node) -> graph.Node:
            if isinstance(node, graph.OutputNode):
                input_dict = {
                    k: self.get_result(v) for k, v in node.from_op.inputs.items()
                }
                self._stitch_node_mapper(node, input_dict)
            elif isinstance(node, graph.VarNode):
                if frame and node.name in frame:
                    self._set_object_recorder(
                        node, self._node_recorder_map[frame[node.name]]
                    )
                else:
                    self._set_object_recorder(node, ObjectRecorder(node))
            return node

        graph.map_nodes_top_level(leaf_nodes, handle_node)

    def _stitch_node_mapper(
        self, node: graph.OutputNode, input_dict: dict[str, ObjectRecorder]
    ) -> None:
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        input_names = list(input_dict.keys())
        inputs = list(input_dict.values())

        result = self._stitch_node_inner(node, input_dict)
        if result is not None:
            self._set_object_recorder(node, result)
        recorder = self._recorder_for_node(node)

        # Tag logic
        # If the op is a mapped, derived op, then we need the tags to flow
        # internally. We know we need to do this because there is special tag
        # handling logic in the mapped ops which does a parallel job. Note: This is
        # probably somehting that needs to be done for arrow as well.
        if op.derived_from and op.derived_from.derived_ops.get("mapped"):
            if opdef_util.should_tag_op_def_outputs(op.derived_from):
                recorder.tags = inputs[0].tags
                recorder.tags[input_names[0]] = inputs[0]
            elif opdef_util.should_flow_tags(op.derived_from):
                recorder.tags = inputs[0].tags
        # Always do this, even for mapped
        if opdef_util.should_tag_op_def_outputs(op):
            recorder.tags = inputs[0].tags
            recorder.tags[input_names[0]] = inputs[0]
        elif opdef_util.should_flow_tags(op):
            recorder.tags = inputs[0].tags

    def _stitch_node_inner(
        self, node: graph.OutputNode, input_dict: dict[str, ObjectRecorder]
    ) -> typing.Optional[ObjectRecorder]:
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        inputs = list(input_dict.values())
        if _is_get_tag_op(op):
            tag_name = _get_tag_name_from_tag_getter_op(op)
            return inputs[0].tags[tag_name]
        elif node.from_op.name.endswith("createIndexCheckpointTag"):
            inputs[0].tags["indexCheckpoint"] = self._recorder_for_node(node)
        elif node.from_op.name.endswith("dict"):
            recorder = self._recorder_for_node(node)
            assert isinstance(recorder, LiteralDictObjectRecorder)
            recorder.val.update(input_dict)
            # for input in input_dict.values():
            #     self._add_call(input.node, node)
        elif node.from_op.name.endswith("list"):
            # Merge element tags together and place them on the outer list.
            # This is overly aggressive, but it means we don't need to provide
            # special handling for concat and other structural list ops for
            # now.
            recorder = self._recorder_for_node(node)
            assert isinstance(recorder, LiteralListObjectRecorder)
            for input in input_dict.values():
                recorder.tags.update(input.tags)
            for input in input_dict.values():
                self._add_call(input.node, node)
        elif node.from_op.name.endswith("pick"):
            if isinstance(node.from_op.inputs["key"], graph.ConstNode):
                key = node.from_op.inputs["key"].val
                dict_recorder = self._recorder_for_node(inputs[0].node)
                if isinstance(dict_recorder, LiteralDictObjectRecorder):
                    return dict_recorder.val[key]
            self._add_call(inputs[0].node, node)
        elif node.from_op.name.endswith("map"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            # Return the resulting object from map!
            self.stitch([fn], {"row": inputs[0].node})
            return self._recorder_for_node(fn)
        elif node.from_op.name.endswith("sort") or node.from_op.name.endswith("filter"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0].node})
            return inputs[0]
        elif node.from_op.name.endswith("groupby"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0].node})
            inputs[0].tags["groupKey"] = fn_recorder
            return inputs[0]
        elif node.from_op.name.endswith("joinAll"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0].node})
            inputs[0].tags["joinObj"] = fn_recorder
            return inputs[0]
        elif len(inputs) == 0:
            # op does not have any inputs, just track its downstream calls
            pass
        else:
            # Otherwise, not a special op, track its call.
            self._add_call(inputs[0].node, node)
        return None


### Helpers ###


def _is_get_tag_op(op: op_def.OpDef) -> bool:
    return "tag_getter_op" in str(op.raw_resolve_fn.__name__)


def _get_tag_name_from_tag_getter_op(op: op_def.OpDef) -> str:
    # Read the tag name from the resolve_fn closure.
    # TODO: Fragile!
    return op.raw_resolve_fn.__closure__[0].cell_contents  # type: ignore
