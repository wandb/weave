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

    def __init__(self, name: str, inputs: dict[str, OpInputNodeT]) -> None:
        # TODO: refactor this variable to be "uri"
        self.name = name
        self.inputs = inputs

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

    def __init__(self, type: weave_types.Type, name: str) -> None:
        self.type = type
        self.name = name

    @classmethod
    def from_json(cls, val: dict) -> "VarNode":
        return cls(weave_types.TypeRegistry.type_from_dict(val["type"]), val["varName"])

    def to_json(self) -> dict:
        return {"nodeType": "var", "type": self.type.to_dict(), "varName": self.name}


def _inner_type_skips_output_node(type: weave_types.Type) -> bool:
    return isinstance(
        type, (weave_types.BasicType, weave_types.TypedDict, weave_types.TypeType)
    )


def _type_skips_output_node(type: weave_types.Type) -> bool:
    return (
        _inner_type_skips_output_node(type)
        or isinstance(type, weave_types.Const)
        and _inner_type_skips_output_node(type.val_type)
    )


class ConstNode(Node):
    val: typing.Any

    def __init__(self, type: weave_types.Type, val: typing.Any) -> None:
        self.type = type
        self.val = val

    @classmethod
    def from_json(cls, obj: dict) -> "ConstNode":
        val = obj["val"]
        if isinstance(val, dict) and "nodeType" in val:
            val = Node.node_from_json(val)
        else:
            val = storage.from_python({"_type": obj["type"], "_val": obj["val"]})  # type: ignore
        return cls(weave_types.TypeRegistry.type_from_dict(obj["type"]), val)

    def equivalent_output_node(self) -> typing.Union[OutputNode, None]:
        if isinstance(self.type, weave_types.Function):
            return None

        val = self.val
        if _type_skips_output_node(self.type):
            return None

        ref = storage._get_ref(val)
        if ref is None:
            ref = storage.save(val)

        return OutputNode(
            self.type, "get", {"uri": ConstNode(weave_types.String(), str(ref))}
        )

    def to_json(self) -> dict:
        # This is used to convert to WeaveJS compatible JS. There are business logic
        # decisions here, like for now if its a BasicType or TypedDict, we encode
        # as json directly, otherwise we save the object and return a get() operation
        equiv_output_node = self.equivalent_output_node()
        if equiv_output_node is not None:
            return equiv_output_node.to_json()

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
    return uri.full_name


def op_full_name(op: Op) -> str:
    return opuri_full_name(op.name)


def opuri_expr_str(op_uri: str) -> str:
    # TODO(jason): maybe this should return something different compared to opname_without_version??
    return uris.WeaveURI.parse(op_uri).friendly_name


def node_expr_str(node: Node) -> str:
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
        elif node.from_op.name == "gqlroot-wbgqlquery":
            query_hash = "_query_"  # TODO: make a hash from the query for idenity
            return f'{opuri_expr_str(node.from_op.name)}({query_hash}, {", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names[1:])})'
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


def _is_const_function_node(node: Node) -> bool:
    return isinstance(node, ConstNode) and isinstance(node.type, weave_types.Function)


def _op_passes_first_arg_as_row_var(op: Op) -> bool:
    return (
        op.name.endswith("map")
        or op.name.endswith("filter")
        or op.name.endswith("sort")
        or op.name.endswith("groupby")
    )


def _map_nodes(
    start_node: Node,
    map_fn: typing.Callable[[Node], typing.Optional[Node]],
    already_mapped: dict[Node, Node],
    walk_lambdas: bool,
) -> Node:
    # TODO: Remove circular import (probably want to make
    # relationship between ops that take lambdas explicit)
    from . import weave_internal

    # This is an iterative implementation, to avoid blowing the stack and
    # to provide friendlier stack traces for exception merging tools.
    var_node_binding_map: dict[VarNode, Node] = {}
    skipped_var_nodes = set()
    to_consider = [start_node]
    while to_consider:
        node = to_consider[-1]
        if node in already_mapped:
            to_consider.pop()
            continue
        result_node = node
        # If it is a var node that has been bound to another node...
        if isinstance(node, VarNode) and node in var_node_binding_map:
            # Then only process the node once we've processed the node it is bound to.
            # and update the type accordingly
            bound_node = var_node_binding_map[node]
            if bound_node not in already_mapped:
                if node in skipped_var_nodes:
                    raise errors.WeaveInternalError(
                        f"Failed to resolve var node binding while mapping {start_node}. \
                        This is likely a bug in _map_nodes logic, or an invalid graph."
                    )
                skipped_var_nodes.add(node)
                continue
            # TODO: this assumes the var is a row of a list... be better!)
            # This also breaks in some tests since it is not always a "dispatchable" type
            bound_node_type = already_mapped[bound_node].type
            # THIS MUST BE REMOVED BEFORE MERGING - TOTAL HACK
            if isinstance(bound_node_type, weave_types.Function):
                bound_node_type = bound_node_type.output_type
            result_node.type = weave_internal.make_const_node(bound_node_type, None)[0].type  # type: ignore
        if isinstance(node, OutputNode):
            inputs = {}
            input_nodes_needed = []
            for param_name, param_node in node.from_op.inputs.items():
                if param_node not in already_mapped:
                    input_nodes_needed.append(param_node)
                    # We need to bind the variable inside the lambda to the correct parameter:
                    if (
                        walk_lambdas
                        and _op_passes_first_arg_as_row_var(node.from_op)
                        and _is_const_function_node(param_node)
                    ):
                        for var_node in expr_vars(param_node.val):
                            if var_node.name == "row":
                                var_node_binding_map[var_node] = list(
                                    node.from_op.inputs.values()
                                )[0]
                else:
                    inputs[param_name] = already_mapped[param_node]
            if len(input_nodes_needed) > 0:
                # This list reversal is required to ensure we map the params in order (required for dependent params like lambdas)
                to_consider.extend(input_nodes_needed[::-1])
                continue
            if any(n is not inputs[k] for k, n in node.from_op.inputs.items()):
                result_node = OutputNode(node.type, node.from_op.name, inputs)
        elif walk_lambdas and _is_const_function_node(node):
            node = typing.cast(ConstNode, node)
            if node.val not in already_mapped:
                to_consider.append(node.val)
                continue
            if node.val is not already_mapped[node.val]:
                result_node = ConstNode(node.type, already_mapped[node.val])

        to_consider.pop()
        mapped_node = map_fn(result_node)
        if mapped_node is None:
            mapped_node = result_node
        already_mapped[node] = mapped_node
    return already_mapped[start_node]


def map_nodes_top_level(
    leaf_nodes: list[Node],
    map_fn: typing.Callable[[Node], typing.Optional[Node]],
) -> list[Node]:
    """Map nodes in dag represented by leaf nodes, but not sub-lambdas"""
    already_mapped: dict[Node, Node] = {}
    return [_map_nodes(n, map_fn, already_mapped, False) for n in leaf_nodes]


def map_nodes_full(
    leaf_nodes: list[Node], map_fn: typing.Callable[[Node], typing.Optional[Node]]
) -> list[Node]:
    """Map nodes in dag represented by leaf nodes, including sub-lambdas"""
    already_mapped: dict[Node, Node] = {}
    return [_map_nodes(n, map_fn, already_mapped, True) for n in leaf_nodes]


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


def is_open(node: Node) -> bool:
    """A Node is 'open' (as in open function) if there are one or more VarNodes"""
    return len(filter_nodes_top_level([node], lambda n: isinstance(n, VarNode))) > 0


def _all_nodes(node: Node) -> set[Node]:
    if not isinstance(node, OutputNode):
        return set((node,))
    res: set[Node] = set((node,))
    for input in node.from_op.inputs.values():
        res.update(_all_nodes(input))
    return res


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


def map_const_nodes_to_x(node: Node) -> Node:
    return map_nodes_full(
        [node], lambda n: n if not isinstance(n, ConstNode) else VarNode(n.type, "x")
    )[0]
