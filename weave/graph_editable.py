import copy
import typing

from . import graph


# TODO: Switch this to use Node/Op terminolgy
# Edge should become EditNode, which is output_of an Op, and input_to an Op
class Edge:
    def __init__(
        self, output_of: graph.OutputNode, input_to: graph.OutputNode, input_name: str
    ):
        self.output_of = output_of
        self.input_to = input_to
        self.input_name = input_name


class EditGraph:
    nodes: typing.Set[graph.OutputNode]
    edges: typing.Set[Edge]
    output_edges: typing.MutableMapping[graph.OutputNode, typing.List[Edge]]
    input_edges: typing.MutableMapping[typing.Tuple[graph.Node, str], Edge]
    replacements: typing.MutableMapping[graph.OutputNode, graph.OutputNode]
    topologically_ordered_nodes: typing.List[graph.OutputNode]
    edit_log: list[tuple]

    def __init__(self, nodes: typing.List[graph.Node]):
        self._orig_nodes = nodes
        self.nodes = set()
        self.edges = set()
        self.output_edges = {}
        self.input_edges = {}
        self.replacements = {}
        self.topologically_ordered_nodes = []
        self.edit_log = []
        for node in self._orig_nodes:
            self._add_node(node)

    def to_standard_graph(self):
        return [self.get_node(n) for n in self._orig_nodes]

    def _add_edge(
        self, output_of: graph.OutputNode, input_to: graph.OutputNode, input_name: str
    ):
        # This is a builder method, used for graph construction. Does not affect
        # edit log.
        edge = Edge(output_of, input_to, input_name)
        self.edges.add(edge)
        self.output_edges.setdefault(output_of, []).append(edge)
        self.input_edges[(input_to, input_name)] = edge

    def _add_node(self, node: graph.Node):
        # This is a builder method, used for graph construction. Does not affect
        # edit log.
        if node in self.nodes:
            return
        if not isinstance(node, graph.OutputNode):
            return
        self.nodes.add(node)
        for input_name, input in node.from_op.inputs.items():
            if isinstance(input, graph.OutputNode):
                self._add_edge(input, node, input_name)
                self._add_node(input)
        self.topologically_ordered_nodes.append(node)

    def checkpoint(self):
        """Return edit log and reset it"""
        edit_log = copy.copy(self.edit_log)
        self.edit_log = []
        return edit_log

    def get_node(self, node: graph.Node):
        if not isinstance(node, graph.OutputNode):
            return node
        if node in self.replacements:
            return self.get_node(self.replacements[node])
        return node

    def replace(self, node: graph.OutputNode, replace_with: graph.OutputNode):
        self.edit_log.append(("replace", node, replace_with))
        return self._replace(node, replace_with)

    def _replace(self, node: graph.OutputNode, replace_with: graph.OutputNode):
        if node not in self.nodes:
            raise Exception("invalid")
        self.replacements[node] = replace_with
        if node not in self.output_edges:
            # TODO
            return
        for output_edge in self.output_edges[node]:
            consumer = self.get_node(output_edge.input_to)
            new_inputs = {
                k: self.get_node(v) for k, v in dict(consumer.from_op.inputs).items()
            }
            # If the edge name is out of date...
            edge_name = output_edge.input_name
            if edge_name not in new_inputs:
                for new_edge_name, new_input in new_inputs.items():
                    if self.get_node(new_input) == self.get_node(node):
                        edge_name = new_edge_name
                        break
            new_inputs[edge_name] = replace_with
            new_consumer: graph.OutputNode[graph.Node] = graph.OutputNode(
                consumer.type, consumer.from_op.name, new_inputs
            )
            self._replace(output_edge.input_to, new_consumer)

    @property
    def edges_with_replacements(self):
        """
        Users should use this to iterate over edges, as it will return the
        updated edges after replacements have been made.
        """
        for edge in self.edges:
            input_to_node = self.get_node(edge.input_to)
            input_to_node_inputs = list(input_to_node.from_op.inputs.keys())
            orig_to_node = edge.input_to
            orig_to_node_inputs = list(orig_to_node.from_op.inputs.keys())
            orig_to_node_input_ndx = (orig_to_node_inputs).index(edge.input_name)
            input_to_node_input_name = (input_to_node_inputs)[orig_to_node_input_ndx]
            yield Edge(
                self.get_node(edge.output_of),
                self.get_node(edge.input_to),
                input_to_node_input_name,
            )
