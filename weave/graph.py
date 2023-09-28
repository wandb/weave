import functools
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

    def __deepcopy__(self, memo: dict) -> "Node":
        return self.node_from_json(self.to_json())

    @classmethod
    def node_from_json(cls, obj: dict) -> "Node":
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

    def to_json(self) -> dict:
        raise NotImplementedError

    def __hash__(self) -> int:
        # We store nodes in a memoize cache in execute.py. They need to be
        # hashable. But the number.py ops override __eq__ which makes the default
        # Python hash not work, so we fix it up here.
        return id(self)

    def __str__(self) -> str:
        return node_expr_str(self)

    def __repr__(self) -> str:
        return "<%s(%s): %s %s>" % (
            self.__class__.__name__,
            id(self),
            self.type,
            str(self),
        )

    def __bool__(self) -> bool:
        raise errors.WeaveTypeError("Cannot use a node as a boolean predicate.")


# weave_types.Function.instance_classes = Node
weave_types.Function.instance_classes.append(Node)

OpInputNodeT = typing.TypeVar("OpInputNodeT", bound=Node)

Frame = typing.Mapping[str, Node]


class Op(typing.Generic[OpInputNodeT]):
    name: str
    inputs: dict[str, OpInputNodeT]
    _full_name: typing.Optional[str]

    def __init__(self, name: str, inputs: dict[str, OpInputNodeT]) -> None:
        # TODO: refactor this variable to be "uri"
        self.name = name
        self.inputs = inputs
        self._full_name = None

    @property
    def friendly_name(self) -> str:
        full_name = self.full_name
        return full_name.split("-", 1)[-1]

    # Called frequently and expensive, so cache it.
    @functools.cached_property
    def full_name(self) -> str:
        return opuri_full_name(self.name)

    # Called frequently and expensive, so cache it.
    @functools.cached_property
    def input_types(self) -> dict[str, weave_types.Type]:
        its: dict[str, weave_types.Type] = {}
        for k, v in self.inputs.items():
            if isinstance(v, ConstNode):
                its[k] = weave_types.Const(v.type, v.val)
            else:
                its[k] = v.type
        return its

    def to_json(self) -> dict:
        json_inputs = {}
        for k, v in self.inputs.items():
            json_inputs[k] = v.to_json()
        return {"name": self.name, "inputs": json_inputs}

    def __repr__(self) -> str:
        return f"<Op({id(self)} name={self.name} inputs={self.inputs}>"


class OutputNode(Node, typing.Generic[OpInputNodeT]):
    from_op: Op[OpInputNodeT]
    val: typing.Any

    def __init__(
        self, type: weave_types.Type, op_name: str, op_inputs: dict[str, OpInputNodeT]
    ) -> None:
        self.type = type
        self.from_op = Op(op_name, op_inputs)

    @classmethod
    def from_json(cls, val: dict) -> "OutputNode":
        op_inputs = val["fromOp"]["inputs"]
        inputs: dict[str, OpInputNodeT] = {}
        for param_name, param_node_json in op_inputs.items():
            # I am not sure why we need a cast here, `OpInputNodeT` is bound to
            # `Node` so it should be fine.
            inputs[param_name] = typing.cast(
                OpInputNodeT, Node.node_from_json(param_node_json)
            )
        return cls(
            weave_types.TypeRegistry.type_from_dict(val["type"]),
            val["fromOp"]["name"],
            inputs,
        )

    def iteritems_op_inputs(self) -> typing.Iterator[typing.Tuple[str, Node]]:
        return iter(self.from_op.inputs.items())

    def to_json(self) -> dict:
        return {
            "nodeType": "output",
            "type": self.type.to_dict(),
            "fromOp": self.from_op.to_json(),
        }

    def __repr__(self) -> str:
        return "<OutputNode(%s) type: %s op_name: %s>" % (
            id(self),
            self.type,
            self.from_op.name,
        )


class VarNode(Node):
    name: str

    # This is used to store the value node that the var is pointing at.
    # Used when constructing panels to track var values so we can correctly
    # perform refinement.
    _var_val: typing.Optional["Node"] = None

    def __init__(self, type: weave_types.Type, name: str) -> None:
        self.type = type
        self.name = name

    @classmethod
    def from_json(cls, val: dict) -> "VarNode":
        return cls(weave_types.TypeRegistry.type_from_dict(val["type"]), val["varName"])

    def to_json(self) -> dict:
        return {"nodeType": "var", "type": self.type.to_dict(), "varName": self.name}


class ConstNode(Node):
    val: typing.Any

    def __init__(self, type: weave_types.Type, val: typing.Any) -> None:
        self.type = type
        self.val = val

    @classmethod
    def from_json(cls, obj: dict) -> "ConstNode":
        from . import dispatch

        val = obj["val"]
        if isinstance(val, dict) and "nodeType" in val:
            val = Node.node_from_json(val)
        else:
            val = storage.from_python({"_type": obj["type"], "_val": obj["val"]})  # type: ignore
        t = weave_types.TypeRegistry.type_from_dict(obj["type"])
        if isinstance(t, weave_types.Function):
            cls = dispatch.RuntimeConstNode

        return cls(t, val)

    def to_json(self) -> dict:
        val = storage.to_python(self.val)["_val"]  # type: ignore
        # mapper = mappers_python.map_to_python(self.type, None)
        # val = mapper.apply(self.val)

        # val = self.val
        # if isinstance(self.type, weave_types.Function):
        #     val = val.to_json()
        return {"nodeType": "const", "type": self.type.to_dict(), "val": val}


class VoidNode(Node):
    type = weave_types.Invalid()

    def to_json(self) -> dict:
        return {"nodeType": "void", "type": "invalid"}


def nodes_equal(n1: Node, n2: Node) -> bool:
    return n1.to_json() == n2.to_json()


def for_each(graph: Node, visitor: typing.Callable[[Node], None]) -> None:
    if isinstance(graph, OutputNode):
        for param_name, param_node in graph.from_op.inputs.items():
            for_each(param_node, visitor)
    visitor(graph)


def opuri_full_name(op_uri: str) -> str:
    uri = uris.WeaveURI.parse(op_uri)
    return uri.name


def op_full_name(op: Op) -> str:
    return opuri_full_name(op.name)


def node_expr_str(node: Node) -> str:
    from . import partial_object

    if isinstance(node, OutputNode):
        param_names = list(node.from_op.inputs.keys())
        if node.from_op.name == "dict":
            return "{%s}" % ", ".join(
                (
                    '"%s": %s' % (k, node_expr_str(n))
                    for k, n in node.from_op.inputs.items()
                )
            )
        elif node.from_op.name == "list":
            return "[%s]" % ", ".join(
                (
                    '"%s": %s' % (k, node_expr_str(n))
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
        elif node.from_op.name == "gqlroot-wbgqlquery":
            query_hash = "_query_"  # TODO: make a hash from the query for idenity
            return f"{node.from_op.friendly_name}({query_hash})"
        elif node.from_op.name == "gqlroot-querytoobj":
            const = node.from_op.inputs[param_names[2]]
            try:
                assert isinstance(const, ConstNode)
                narrow_type = const.val
                assert isinstance(narrow_type, partial_object.PartialObjectType)
            except AssertionError:
                return (
                    f"{node_expr_str(node.from_op.inputs[param_names[0]])}."
                    f"querytoobj({node_expr_str(node.from_op.inputs[param_names[1]])}, ?)"
                )
            else:
                return (
                    f"{node_expr_str(node.from_op.inputs[param_names[0]])}."
                    f"querytoobj({node_expr_str(node.from_op.inputs[param_names[1]])},"
                    f" {narrow_type.keyless_weave_type_class()})"
                )

        elif all([not isinstance(n, OutputNode) for n in node.from_op.inputs.values()]):
            return "%s(%s)" % (
                node.from_op.friendly_name,
                ", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names),
            )
        if not param_names:
            return "%s()" % node.from_op.friendly_name
        return "%s.%s(%s)" % (
            node_expr_str(node.from_op.inputs[param_names[0]]),
            node.from_op.friendly_name,
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
    node: Node,
    map_fn: typing.Callable[[Node], typing.Optional[Node]],
    already_mapped: dict[Node, Node],
    walk_lambdas: bool,
) -> Node:
    # This is an iterative implementation, to avoid blowing the stack and
    # to provide friendlier stack traces for exception merging tools.
    to_consider = [node]
    while to_consider:
        curr_node = to_consider[-1]
        if curr_node in already_mapped:
            to_consider.pop()
            continue
        result_node = curr_node
        if isinstance(curr_node, OutputNode):
            inputs = {}
            need_inputs = False
            for param_name, param_node in curr_node.from_op.inputs.items():
                if param_node not in already_mapped:
                    to_consider.append(param_node)
                    need_inputs = True
                else:
                    inputs[param_name] = already_mapped[param_node]
            if need_inputs:
                continue
            if any(n is not inputs[k] for k, n in curr_node.from_op.inputs.items()):
                result_node = OutputNode(curr_node.type, curr_node.from_op.name, inputs)
        elif (
            walk_lambdas
            and isinstance(curr_node, ConstNode)
            and isinstance(curr_node.type, weave_types.Function)
        ):
            is_static_lambda = len(curr_node.type.input_types) == 0
            if not is_static_lambda:
                if curr_node.val not in already_mapped:
                    to_consider.append(curr_node.val)
                    continue
                if curr_node.val is not already_mapped[curr_node.val]:
                    result_node = ConstNode(
                        curr_node.type, already_mapped[curr_node.val]
                    )

        to_consider.pop()
        mapped_node = map_fn(result_node)
        if mapped_node is None:
            mapped_node = result_node
        already_mapped[curr_node] = mapped_node
    return already_mapped[node]


OnErrorFnType = typing.Optional[typing.Callable[[int, Exception], Node]]


def map_nodes_top_level(
    leaf_nodes: list[Node],
    map_fn: typing.Callable[[Node], typing.Optional[Node]],
    on_error: OnErrorFnType = None,
) -> list[Node]:
    """Map nodes in dag represented by leaf nodes, but not sub-lambdas"""
    already_mapped: dict[Node, Node] = {}
    results: list[Node] = []
    for node_ndx, node in enumerate(leaf_nodes):
        try:
            results.append(_map_nodes(node, map_fn, already_mapped, False))
        except Exception as e:
            if on_error:
                results.append(on_error(node_ndx, e))
            else:
                raise e

    return results


def map_nodes_full(
    leaf_nodes: list[Node],
    map_fn: typing.Callable[[Node], typing.Optional[Node]],
    on_error: OnErrorFnType = None,
) -> list[Node]:
    """Map nodes in dag represented by leaf nodes, including sub-lambdas"""
    already_mapped: dict[Node, Node] = {}
    results: list[Node] = []
    for node_ndx, node in enumerate(leaf_nodes):
        try:
            results.append(_map_nodes(node, map_fn, already_mapped, True))
        except Exception as e:
            if on_error:
                results.append(on_error(node_ndx, e))
            else:
                raise e

    return results


def all_nodes_full(leaf_nodes: list[Node]) -> list[Node]:
    result: list[Node] = []
    map_nodes_full(leaf_nodes, lambda n: result.append(n))
    return result


def filter_nodes_top_level(
    nodes: list[Node], filter_fn: typing.Callable[[Node], bool]
) -> list[Node]:
    """Filter nodes in dag represented by leaf nodes, but not sub-lambdas"""
    result = []

    def mapped_fn(node: Node) -> Node:
        if filter_fn(node):
            result.append(node)
        return node

    map_nodes_top_level(nodes, mapped_fn)
    return result


def filter_nodes_full(
    nodes: list[Node], filter_fn: typing.Callable[[Node], bool]
) -> list[Node]:
    """Filter nodes in dag represented by leaf nodes, including sub-lambdas"""
    result = []

    def mapped_fn(node: Node) -> Node:
        if filter_fn(node):
            result.append(node)
        return node

    map_nodes_full(nodes, mapped_fn)
    return result


def expr_vars(node: Node) -> list[VarNode]:
    return typing.cast(
        list[VarNode], filter_nodes_top_level([node], lambda n: isinstance(n, VarNode))
    )


def resolve_vars(node: Node) -> Node:
    """Replace all VarNodes with the value they point to."""

    def _replace_var_with_val(n: Node) -> typing.Optional[Node]:
        if isinstance(n, VarNode) and hasattr(n, "_var_val") and n._var_val is not None:
            # Recursively replace vars in the value node.
            return resolve_vars(n._var_val)
        return None

    return map_nodes_full([node], _replace_var_with_val)[0]


def is_open(node: Node) -> bool:
    """A Node is 'open' (as in open function) if there are one or more VarNodes"""
    return len(filter_nodes_top_level([node], lambda n: isinstance(n, VarNode))) > 0


def count(node: Node) -> int:
    counter = 0

    def inc(n: Node) -> None:
        nonlocal counter
        counter += 1

    map_nodes_full([node], inc)
    return counter


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


def map_const_nodes_to_x(node: Node) -> Node:
    return map_nodes_full(
        [node],
        lambda n: n if not isinstance(n, ConstNode) else VarNode(n.type, "x"),
    )[0]
