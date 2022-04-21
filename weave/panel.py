from . import graph
from . import storage
from .ops_primitives.file import get as op_get


class Panel:
    def __init__(self, input_node):
        if not isinstance(input_node, graph.Node):
            ref = storage.save(input_node)
            input_node = op_get(str(ref.uri()))
        self.input_node = input_node
