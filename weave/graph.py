import json
import typing

from . import errors
from . import weave_types
from . import uris
from . import storage

T = typing.TypeVar("T")


# The Generic here is currently only used in op definitions, its not actually
# applied within the class. See infer_types.py for usage.
class Node(typing.Generic[T]):
    type: weave_types.Type

    @classmethod
    def node_from_json(cls, obj):
        if obj["nodeType"] == "const":
            return ConstNode.from_json(obj)
        elif obj["nodeType"] == "output":
            return OutputNode.from_json(obj)
        elif obj["nodeType"] == "var":
            return VarNode.from_json(obj)
        elif obj["nodeType"] == "void":
            return VoidNode()
        else:
            raise errors.WeaveInternalError("invalid node type: %s" % obj)

    def to_json(self):
        raise NotImplementedError

    def __hash__(self):
        # We store nodes in a memoize cache in execute.py. They need to be
        # hashable. But the number.py ops override __eq__ which makes the default
        # Python hash not work, so we fix it up here.
        return id(self)

    def __str__(self):
        return node_expr_str(self)

    def __repr__(self):
        return "<%s(%s): %s %s>" % (
            self.__class__.__name__,
            id(self),
            self.type,
            str(self),
        )


weave_types.Function.instance_classes.append(Node)

OpInputNodeT = typing.TypeVar("OpInputNodeT")


class Op(typing.Generic[OpInputNodeT]):
    name: str
    inputs: typing.Dict[str, OpInputNodeT]

    def __init__(self, name, inputs):
        # TODO: refactor this variable to be "uri"
        self.name = name
        self.inputs = inputs

    def to_json(self):
        json_inputs = {}
        for k, v in self.inputs.items():
            json_inputs[k] = v.to_json()
        return {"name": self.name, "inputs": json_inputs}

    def __repr__(self):
        return f"<Op({id(self)} name={self.name} inputs={self.inputs}>"


class OutputNode(Node, typing.Generic[OpInputNodeT]):
    from_op: Op[OpInputNodeT]
    val: typing.Any

    def __init__(self, type, op_name, op_inputs):
        self.type = type
        self.from_op = Op(op_name, op_inputs)

    @classmethod
    def from_json(cls, val):
        op_inputs = val["fromOp"]["inputs"]
        inputs = {}
        for param_name, param_node_json in op_inputs.items():
            inputs[param_name] = Node.node_from_json(param_node_json)
        return cls(
            weave_types.TypeRegistry.type_from_dict(val["type"]),
            val["fromOp"]["name"],
            inputs,
        )

    def iteritems_op_inputs(self):
        return iter(self.from_op.inputs.items())

    def to_json(self):
        return {
            "nodeType": "output",
            "type": self.type.to_dict(),
            "fromOp": self.from_op.to_json(),
        }


class VarNode(Node):
    name: str

    def __init__(self, type, name):
        self.type = type
        self.name = name

    @classmethod
    def from_json(cls, val):
        return cls(weave_types.TypeRegistry.type_from_dict(val["type"]), val["varName"])

    def to_json(self):
        return {"nodeType": "var", "type": self.type.to_dict(), "varName": self.name}


class ConstNode(Node):
    val: typing.Any

    def __init__(self, type, val):
        self.type = type
        self.val = val

    @classmethod
    def from_json(cls, obj):
        val = obj["val"]
        if isinstance(val, dict) and "nodeType" in val:
            val = Node.node_from_json(val)
        else:
            val = storage.from_python({"_type": obj["type"], "_val": obj["val"]})
        return cls(weave_types.TypeRegistry.type_from_dict(obj["type"]), val)

    def equivalent_output_node(self):
        if isinstance(self.type, weave_types.Function):
            return

        val = self.val
        if (
            isinstance(self.type, (weave_types.BasicType, weave_types.TypedDict))
            or isinstance(self.type, weave_types.Const)
            and isinstance(
                self.type.val_type, (weave_types.BasicType, weave_types.TypedDict)
            )
        ):
            return

        ref = storage._get_ref(val)
        if ref is None:
            ref = storage.save(val)

        return OutputNode(
            self.type, "get", {"uri": ConstNode(weave_types.String(), str(ref))}
        )

    def to_json(self):
        # This is used to convert to WeaveJS compatible JS. There are business logic
        # decisions here, like for now if its a BasicType or TypedDict, we encode
        # as json directly, otherwise we save the object and return a get() operation
        equiv_output_node = self.equivalent_output_node()
        if equiv_output_node:
            return equiv_output_node.to_json()

        val = self.val
        if isinstance(self.type, weave_types.Function):
            val = val.to_json()
        return {"nodeType": "const", "type": self.type.to_dict(), "val": val}


class VoidNode(Node):
    type = weave_types.Invalid()

    def to_json(self):
        return {"nodeType": "void", "type": "invalid"}


def nodes_equal(n1: Node, n2: Node):
    return n1.to_json() == n2.to_json()


def for_each(graph: Node, visitor):
    if isinstance(graph, OutputNode):
        for param_name, param_node in graph.from_op.inputs.items():
            for_each(param_node, visitor)
    visitor(graph)


def opuri_full_name(op_uri: str):
    uri = uris.WeaveURI.parse(op_uri)
    return uri.full_name


def op_full_name(op: Op):
    return opuri_full_name(op.name)


def opuri_expr_str(op_uri: str) -> str:
    # TODO(jason): maybe this should return something different compared to opname_without_version??
    return uris.WeaveURI.parse(op_uri).friendly_name


def node_expr_str(node: Node):
    if isinstance(node, OutputNode):
        param_names = list(node.from_op.inputs.keys())
        if node.from_op.name == "dict":
            return "{%s}" % ", ".join(
                (
                    "%s: %s" % (k, node_expr_str(n))
                    for k, n in node.from_op.inputs.items()
                )
            )
        elif node.from_op.name.endswith("__getattr__"):
            inputs = list(node.from_op.inputs.values())
            return "%s.%s" % (
                node_expr_str(inputs[0]),
                inputs[1].val,
            )
        elif node.from_op.name.endswith("pick") or node.from_op.name.endswith(
            "__getitem__"
        ):
            inputs = list(node.from_op.inputs.values())
            return "%s[%s]" % (
                node_expr_str(inputs[0]),
                node_expr_str(inputs[1]),
            )
        elif all([not isinstance(n, OutputNode) for n in node.from_op.inputs.values()]):
            return "%s(%s)" % (
                opuri_expr_str(node.from_op.name),
                ", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names),
            )
        if not param_names:
            return "%s()" % opuri_expr_str(node.from_op.name)
        return "%s.%s(%s)" % (
            node_expr_str(node.from_op.inputs[param_names[0]]),
            opuri_expr_str(node.from_op.name),
            ", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names[1:]),
        )
    elif isinstance(node, ConstNode):
        if isinstance(node.type, weave_types.Function):
            res = node_expr_str(node.val)
            return res
        try:
            return json.dumps(node.val)
        except TypeError:
            # WARNING: This behavior means that sometimes this function
            # produces expressionions that JS can't parse (it happens when
            # we have Python Objects as values that have not yet been serialized)
            # TODO: fix
            return str(node.val)
    elif isinstance(node, VarNode):
        return node.name
    elif isinstance(node, VoidNode):
        return "<void>"
    else:
        return "**PARSE_ERROR**"


def _map_nodes(
    node: Node, map_fn: typing.Callable[[Node], Node], already_mapped: dict[Node, Node]
) -> Node:
    if node in already_mapped:
        return already_mapped[node]
    if isinstance(node, OutputNode):
        inputs = {
            k: _map_nodes(n, map_fn, already_mapped)
            for k, n in node.from_op.inputs.items()
        }
        node = OutputNode(node.type, node.from_op.name, inputs)
    mapped_node = map_fn(node)
    if mapped_node is None:
        mapped_node = node
    already_mapped[node] = mapped_node
    return mapped_node


def map_nodes(node: Node, map_fn: typing.Callable[[Node], Node]) -> Node:
    return _map_nodes(node, map_fn, {})


def _all_nodes(node: Node) -> set[Node]:
    if not isinstance(node, OutputNode):
        return set((node,))
    res: set[Node] = set((node,))
    for input in node.from_op.inputs.values():
        res.update(_all_nodes(input))
    return res


def filter_nodes(node: Node, filter_fn: typing.Callable[[Node], bool]) -> list[Node]:
    nodes = _all_nodes(node)
    return [n for n in nodes if filter_fn(n)]


def expr_vars(node: Node):
    return filter_nodes(node, lambda n: isinstance(n, VarNode))


def is_open(node: Node) -> bool:
    """A Node is 'open' (as in open function) if there are one or more VarNodes"""
    return len(filter_nodes(node, lambda n: isinstance(n, VarNode))) > 0


def count(node: Node) -> int:
    return len(_all_nodes(node))


def _linearize(node: OutputNode) -> list[OutputNode]:
    if not node.from_op.inputs:
        return [node]
    arg0 = next(iter(node.from_op.inputs.values()))
    if not isinstance(arg0, OutputNode):
        return [node]
    return _linearize(arg0) + [node]


def linearize(node: Node) -> typing.Optional[list[OutputNode]]:
    """Return a list of the nodes by walking 0th argument."""
    if not isinstance(node, OutputNode):
        return None
    return _linearize(node)
