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
) -> "StitchedGraph":
    """Given a list of leaf nodes, stitch the graph together. This is the primary entry point for this module."""
    sg = StitchedGraph()
    sg.stitch(leaf_nodes)
    return sg


@dataclasses.dataclass
class StitchedOutputNode:
    """Represents the user-facing data structure for a node after stitching. Importantly,
    each OutputNode in the original graph will have a single StitchedOutputNode and visa-versa.
    In other words, it is a 1:1 mapping."""

    # `node` is the original node in the user graph which this stitched node
    # represents.
    node: graph.OutputNode

    # `_stitched_graph` is a private reference to the stitched graph which is used
    # to lazily compute the input and output recorders
    _stitched_graph: "StitchedGraph"

    # `input_recorder_dict` is a dictionary of the input recorders for this node
    # with keys matching the op input keys.
    # Note: if a node is used in multiple places (should only be possible with)
    # inner lambda functions, then the input recorder dict will only be "correct"
    # of the first occurrence of the node. To fix this, we should not merge lambda
    # var nodes in deserialization of graphs.
    @property
    def input_recorder_dict(self) -> dict[str, "ObjectRecorder"]:
        return {
            k: self._stitched_graph.get_recorder_for_node(v)
            for k, v in self.node.from_op.inputs.items()
        }

    # `output_recorder` is the output recorder for this node. Note: it is possible,
    # and expected that the `output_recorder` for the node may not have an `original_node`
    # that is the same as the `node` for this stitched node. This is one of the purposes
    # of stitch in the first place. For example, if a node is a `pick` operation, then the
    # output recorder will be the recorder for the node that was picked.
    @property
    def output_recorder(self) -> "ObjectRecorder":
        return self._stitched_graph.get_recorder_for_node(self.node)


@dataclasses.dataclass
class ObjectRecorder:
    """Represents the user-facing data structure for node's value after stitching. Since some
    nodes will share ObjectRecorders, a StitchedGraph's total ObjectRecorders is always less than or equal to
    the total number of nodes in the original graph."""

    # `original_node` is the original node which produced this object recorder.
    original_node: graph.Node

    # `_stitched_graph` is a private reference to the stitched graph which is used
    # to lazily compute other properties.
    _stitched_graph: "StitchedGraph"

    # `_tag_source_node_map` is a dictionary of nodes which produce tags for this object
    _tag_source_node_map: dict[str, graph.Node] = dataclasses.field(
        default_factory=dict
    )

    # `_calls_target_nodes` is a list of node which this object recorder feeds into
    _calls_target_nodes: list[graph.OutputNode] = dataclasses.field(
        default_factory=list
    )

    # `tag_recorder_dict` is a dictionary of recorders which are the tags for this object.
    @property
    def tag_recorder_dict(self) -> dict[str, "ObjectRecorder"]:
        return {
            k: self._stitched_graph.get_recorder_for_node(v)
            for k, v in self._tag_source_node_map.items()
        }

    # `tag_recorder_for_key` fetches a specific tag recorder for a given key
    def tag_recorder_for_key(self, key: str) -> "ObjectRecorder":
        return self._stitched_graph.get_recorder_for_node(
            self._tag_source_node_map[key]
        )

    # `calls_stitched_output_node_list` is a list of stitched output nodes which this object recorder feeds into
    @property
    def calls_stitched_output_node_list(self) -> list[StitchedOutputNode]:
        return [
            self._stitched_graph._get_stitched_node_for_node(c)
            for c in self._calls_target_nodes
        ]

    # `add_call` is used to record that this object feeds into a target node
    def add_call(self, target_node: graph.OutputNode) -> None:
        self._calls_target_nodes.append(target_node)

    # `set_tag_recorder_for_key` sets the tag recorder for a given key
    def set_tag_recorder_for_key(self, key: str, recorder: "ObjectRecorder") -> None:
        self._tag_source_node_map[key] = recorder.original_node

    # `update_tag_recorder_dict` updates the tag recorder dict with a dictionary of tag recorders
    def update_tag_recorder_dict(
        self, tag_recorder_dict: dict[str, "ObjectRecorder"]
    ) -> None:
        for k, v in tag_recorder_dict.items():
            self.set_tag_recorder_for_key(k, v)

    # `merge_in` merges the contents of another object recorder into this one.
    # Note: once we have an invariant that all const function node var nodes are
    # unique, we can completely remove this function
    def merge_in(self, other: "ObjectRecorder") -> None:
        if self == other:
            return
        if type(self) != type(other):
            raise errors.WeaveInternalError(
                f"Programming error: ObjectRecorder can only merge in other ObjectRecorders of the same type. Found {type(self)} and {type(other)}"
            )
        for other_key, other_node in other._tag_source_node_map.items():
            if other_key in self._tag_source_node_map:
                self.tag_recorder_for_key(other_key).merge_in(
                    self._stitched_graph.get_recorder_for_node(other_node)
                )

        for c in other._calls_target_nodes:
            if c not in self._calls_target_nodes:
                self.add_call(c)


@dataclasses.dataclass
class ConstNodeObjectRecorder(ObjectRecorder):
    """Specific ObjectRecorder for ConstNodes."""

    @property
    def const_val(self) -> typing.Optional[typing.Any]:
        if not isinstance(self.original_node, graph.ConstNode):
            raise errors.WeaveInternalError(
                f"Programming error: ConstNodeObjectRecorder must be constructed with a `ConstNode`. Found {self.original_node}"
            )
        return self.original_node.val

    def merge_in(self, other: "ObjectRecorder") -> None:
        if not isinstance(other, ConstNodeObjectRecorder):
            raise errors.WeaveInternalError(
                f"Programming error: ConstNodeObjectRecorder can only merge in other ConstNodeObjectRecorders. Found {other}"
            )
        if self.const_val != other.const_val:
            raise errors.WeaveInternalError(
                f"Programming error: ConstNodeObjectRecorder can only merge in other ConstNodeObjectRecorders with the same value. Found {self.const_val} and {other.const_val}"
            )
        super().merge_in(other)


@dataclasses.dataclass
class LiteralDictObjectRecorder(ObjectRecorder):
    """Specific ObjectRecorder for Dictionary Literals."""

    @property
    def input_recorder_dict_val(self) -> dict[str, "ObjectRecorder"]:
        if not (
            isinstance(self.original_node, graph.OutputNode)
            and self.original_node.from_op.name.endswith("dict")
        ):
            raise errors.WeaveInternalError(
                f"Programming error: LiteralDictObjectRecorder must be constructed with a `dict` op. Found {self.original_node}"
            )
        return {
            k: self._stitched_graph.get_recorder_for_node(v)
            for k, v in self.original_node.from_op.inputs.items()
        }


@dataclasses.dataclass
class StitchedGraph:
    """A StitchedGraph is a graph is the primary data structure produced in this module.
    The main user-facing method is `get_recorder_for_node` which returns an ObjectRecorder
    for a given node."""

    # The ObjectRecorder for a Node my not be produced by that node. Therefore, the set of all
    # ObjectRecords is upper bounded by the set of all Nodes.
    _node_to_recorder_map: typing.Dict[graph.Node, ObjectRecorder] = dataclasses.field(
        default_factory=dict
    )

    # `get_recorder_for_node` returns the ObjectRecorder for a given node.
    def get_recorder_for_node(self, node: graph.Node) -> ObjectRecorder:
        # Internally, we create a default ObjectRecorder if one does not exist already.
        if node not in self._node_to_recorder_map:
            if isinstance(node, graph.OutputNode) and node.from_op.name.endswith(
                "dict"
            ):
                self._set_recorder_for_node(node, LiteralDictObjectRecorder(node, self))
            elif isinstance(node, graph.ConstNode):
                self._set_recorder_for_node(node, ConstNodeObjectRecorder(node, self))
            else:
                self._set_recorder_for_node(node, ObjectRecorder(node, self))
        return self._node_to_recorder_map[node]

    def _set_recorder_for_node(
        self, node: graph.Node, recorder: ObjectRecorder
    ) -> None:
        if node in self._node_to_recorder_map and not isinstance(node, graph.VarNode):
            # Normally, this would be a programming error. However, it is possible that actually
            # we are re-processing processing an inner lambda function which is shared by multiple nodes.
            # If this is the case, what we actually want to do is merge the object recorders. Ideally, this
            # can go back to being an error if we treat every var node as it's own logical node - this will
            # require refactoring the deserializer to create new const-function nodes for each lambda function
            # usage.
            self._node_to_recorder_map[node].merge_in(recorder)
            # raise errors.WeaveInternalError(
            #     f"Programming error: Attempted to set key {node} twice."
            # )
        self._node_to_recorder_map[node] = recorder

    def _get_stitched_node_for_node(self, node: graph.OutputNode) -> StitchedOutputNode:
        return StitchedOutputNode(node, self)

    def stitch(
        self,
        leaf_nodes: list[graph.Node],
        frame: typing.Optional[dict[str, ObjectRecorder]] = None,
    ) -> None:
        """Given a list of leaf nodes, stitch the graph together."""

        def handle_node(node: graph.Node) -> graph.Node:
            if isinstance(node, graph.OutputNode):
                # If the node is an output node, we perform stitching
                input_dict = {
                    k: self.get_recorder_for_node(v)
                    for k, v in node.from_op.inputs.items()
                }
                self._stitch_output_node_with_stitched_inputs(node, input_dict)
            elif isinstance(node, graph.VarNode):
                # If it is a var node, then we update it ito the frame value
                # if it exists, or a dummy recorder
                if frame and node.name in frame:
                    self._set_recorder_for_node(node, frame[node.name])
                else:
                    # This effectively "clears" the recorder for the var node.
                    self._set_recorder_for_node(node, ObjectRecorder(node, self))
            return node

        graph.map_nodes_top_level(leaf_nodes, handle_node)

    def _stitch_output_node_with_stitched_inputs(
        self,
        node: graph.OutputNode,
        stitched_input_recorder_dict: dict[str, ObjectRecorder],
    ) -> None:
        result = (
            self._stitch_output_node_optionally_returning_effective_object_recorder(
                node, stitched_input_recorder_dict
            )
        )
        if result is not None:
            self._set_recorder_for_node(node, result)
        recorder = self.get_recorder_for_node(node)

        # Tag logic
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        input_names = list(stitched_input_recorder_dict.keys())
        inputs = list(stitched_input_recorder_dict.values())
        # If the op is a mapped, derived op, then we need the tags to flow
        # internally. We know we need to do this because there is special tag
        # handling logic in the mapped ops which does a parallel job. Note: This is
        # probably something that needs to be done for arrow as well.
        if op.derived_from and op.derived_from.derived_ops.get("mapped"):
            if opdef_util.should_tag_op_def_outputs(op.derived_from):
                recorder.update_tag_recorder_dict(inputs[0].tag_recorder_dict)
                recorder.set_tag_recorder_for_key(input_names[0], inputs[0])
            elif opdef_util.should_flow_tags(op.derived_from):
                recorder.update_tag_recorder_dict(inputs[0].tag_recorder_dict)
        # Always do this, even for mapped
        if opdef_util.should_tag_op_def_outputs(op):
            recorder.update_tag_recorder_dict(inputs[0].tag_recorder_dict)
            recorder.set_tag_recorder_for_key(input_names[0], inputs[0])
        elif opdef_util.should_flow_tags(op):
            recorder.update_tag_recorder_dict(inputs[0].tag_recorder_dict)

    def _stitch_output_node_optionally_returning_effective_object_recorder(
        self,
        node: graph.OutputNode,
        stitched_input_recorder_dict: dict[str, ObjectRecorder],
    ) -> typing.Optional[ObjectRecorder]:
        op = registry_mem.memory_registry.get_op(node.from_op.name)
        inputs = list(stitched_input_recorder_dict.values())
        if _is_get_tag_op(op):
            tag_name = _get_tag_name_from_tag_getter_op(op)
            return inputs[0].tag_recorder_for_key(tag_name)
        elif node.from_op.name.endswith("createIndexCheckpointTag"):
            inputs[0].set_tag_recorder_for_key(
                "indexCheckpoint", self.get_recorder_for_node(node)
            )
        elif node.from_op.name.endswith("dict"):
            # We return early here because we don't want to do any call logic
            return None
        elif node.from_op.name.endswith("list"):
            # Merge element tags together and place them on the outer list.
            # This is overly aggressive, but it means we don't need to provide
            # special handling for concat and other structural list ops for
            # now.
            recorder = self.get_recorder_for_node(node)
            for input in stitched_input_recorder_dict.values():
                recorder.update_tag_recorder_dict(input.tag_recorder_dict)
                input.add_call(node)
            return None
        elif node.from_op.name.endswith("pick"):
            if isinstance(node.from_op.inputs["key"], graph.ConstNode):
                key = node.from_op.inputs["key"].val
                dict_recorder = inputs[0]
                if isinstance(dict_recorder, LiteralDictObjectRecorder):
                    return dict_recorder.input_recorder_dict_val[key]
        elif node.from_op.name.endswith("map"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.const_val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            # Return the resulting object from map!
            self.stitch([fn], {"row": inputs[0]})
            return self.get_recorder_for_node(fn)
        elif node.from_op.name.endswith("sort") or node.from_op.name.endswith("filter"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.const_val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0]})
            return inputs[0]
        elif node.from_op.name.endswith("groupby"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.const_val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0]})
            inputs[0].set_tag_recorder_for_key(
                "groupKey", self.get_recorder_for_node(fn)
            )
            return inputs[0]
        elif node.from_op.name.endswith("joinAll"):
            fn_recorder = inputs[1]
            if not isinstance(fn_recorder, ConstNodeObjectRecorder):
                raise errors.WeaveInternalError("non-const not yet supported")
            fn = fn_recorder.const_val
            if fn is None:
                raise errors.WeaveInternalError("Expected fn to be set")
            self.stitch([fn], {"row": inputs[0]})
            inputs[0].set_tag_recorder_for_key(
                "joinObj", self.get_recorder_for_node(fn)
            )
            return inputs[0]
        elif len(inputs) == 0:
            return None
        # In all cases that have not early returned, we need to add a call
        # from the input to the output.
        inputs[0].add_call(node)
        return None


### Helpers ###


def _is_get_tag_op(op: op_def.OpDef) -> bool:
    return "tag_getter_op" in str(op.raw_resolve_fn.__name__)


def _get_tag_name_from_tag_getter_op(op: op_def.OpDef) -> str:
    # Read the tag name from the resolve_fn closure.
    # TODO: Fragile!
    return op.raw_resolve_fn.__closure__[0].cell_contents  # type: ignore
