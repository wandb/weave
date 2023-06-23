import contextlib
import contextvars
import collections
import typing

from . import graph
from . import errors


ExecutableNode = typing.Union[graph.OutputNode, graph.ConstNode]


class NoResult:
    pass


class ErrorResult:
    error: Exception

    def __init__(self, error: Exception) -> None:
        self.error = error


class NodeResultStore:
    _from_store: typing.Optional[collections.defaultdict[graph.OutputNode, typing.Any]]
    _store: collections.defaultdict[graph.OutputNode, typing.Any]

    def __init__(
        self, initialize_with: typing.Optional["NodeResultStore"] = None
    ) -> None:
        if initialize_with is None:
            self._from_store = None
        else:
            self._from_store = initialize_with._store
        self._store = collections.defaultdict(lambda: NoResult)

    def has(self, node: graph.OutputNode) -> bool:
        return not self[node] is NoResult

    def __setitem__(self, key: graph.OutputNode, value: typing.Any):
        self._store[key] = value

    def __getitem__(self, key: graph.OutputNode) -> typing.Any:
        res = self._store[key]
        if isinstance(res, NoResult) and self._from_store is not None:
            return self._from_store[key]
        return res

    def merge(self, other: "NodeResultStore"):
        for key, value in other._store.items():
            self._store[key] = value


_node_result_store: contextvars.ContextVar[
    typing.Optional[NodeResultStore]
] = contextvars.ContextVar("_top_level_forward_graph_ctx", default=None)


# Each top level call to execute.execute_nodes creates its own result store.
# Recursive calls share the top level result store.
@contextlib.contextmanager
def node_result_store(store: typing.Optional[NodeResultStore] = None):
    if store is None:
        store = _node_result_store.get()
    token = None
    if store is None:
        store = NodeResultStore()
        token = _node_result_store.set(store)
    try:
        yield store
    finally:
        if token is not None:
            _node_result_store.reset(token)


def get_node_result_store() -> NodeResultStore:
    store = _node_result_store.get()
    if store is None:
        return NodeResultStore()
    return store


class ForwardNode:
    node: graph.OutputNode[ExecutableNode]
    input_to: dict["ForwardNode", typing.Literal[True]]

    def __init__(self, node: graph.OutputNode[ExecutableNode]) -> None:
        self.node = node
        self.input_to = {}
        self.cache_id = None
        self.result_store = get_node_result_store()

    def __str__(self):
        return "<ForwardNode(%s): %s input_to %s>" % (
            id(self),
            self.node.from_op.name
            if isinstance(self.node, graph.OutputNode)
            else self.node.val,
            " ".join([str(id(fn)) for fn in self.input_to]),
        )

    @property
    def result(self) -> typing.Any:
        return self.result_store[self.node]

    @property
    def has_result(self) -> bool:
        return self.result_store.has(self.node)

    def set_result(self, result: typing.Any) -> None:
        self.result_store[self.node] = result


# Each execute.execute_nodes call gets its own ForwardGraph, and walks all
# the nodes in it. But it will skip executing nodes if the result already
# exist for that node in the top-level result store.
class ForwardGraph:
    roots: dict[ForwardNode, typing.Literal[True]]
    _node_to_forward_node: typing.Dict[graph.Node, ForwardNode]

    def __init__(self, allow_var_nodes=False) -> None:
        self.roots = {}
        self._node_to_forward_node = {}
        self._allow_var_nodes = allow_var_nodes

    def add_nodes(self, nodes: typing.Iterable[graph.Node]):
        for node in nodes:
            self.add_node(node)

    def add_node(self, node: graph.Node):
        if isinstance(node, graph.VoidNode):
            raise errors.WeaveBadRequest(
                "Found void node when constructing ForwardGraph: %s" % node
            )
        elif isinstance(node, graph.ConstNode):
            return
        if node in self._node_to_forward_node:
            return
        if isinstance(node, graph.VarNode) and not self._allow_var_nodes:
            raise errors.WeaveBadRequest(
                "Found var node when constructing ForwardGraph: %s" % node
            )

        forward_node = ForwardNode(node)  # type: ignore
        self._node_to_forward_node[node] = forward_node
        if isinstance(node, graph.OutputNode):
            is_root = True
            for param_node in node.from_op.inputs.values():
                self.add_node(param_node)
                if isinstance(param_node, graph.OutputNode):
                    self._node_to_forward_node[param_node].input_to[forward_node] = True
                    is_root = False
            if is_root:
                self.roots[forward_node] = True

    def get_forward_node(self, node: typing.Union[graph.OutputNode, graph.VarNode]):
        return self._node_to_forward_node[node]

    def has_result(self, node: ExecutableNode):
        if isinstance(node, graph.ConstNode):
            return True
        return self._node_to_forward_node[node].has_result

    def get_result(self, node: ExecutableNode):
        if isinstance(node, graph.ConstNode):
            return node.val
        return self._node_to_forward_node[node].result

    def __str__(self):
        lines = []
        to_print = self.roots
        printed = set()
        while len(to_print):
            printing_now = to_print.copy()
            to_print = set()
            for forward_node in printing_now:
                lines.append(str(forward_node))
                for downstream_forward_node in forward_node.input_to:
                    if downstream_forward_node not in printed:
                        to_print.add(downstream_forward_node)
                    printed.add(downstream_forward_node)
        return "\n".join(lines)
