import json
import typing

from . import weave_types


class Node:
    type: weave_types.Type

    @classmethod
    def node_from_json(cls, obj):
        if obj["nodeType"] == "const":
            return ConstNode.from_json(obj)
        elif obj["nodeType"] == "output":
            return OutputNode.from_json(obj)
        elif obj["nodeType"] == "var":
            return VarNode.from_json(obj)

    # def _repr_html_(self):
    # return show.weave_panel_iframe(self)
    def _ipython_display_(self):
        from . import show

        return show(self)

    def __hash__(self):
        # We store nodes in a memoize cache in execute.py. They need to be
        # hashable. But the number.py ops override __eq__ which makes the default
        # Python hash not work, so we fix it up here.
        return id(self)

    def print(self):
        import pprint

        pprint.pprint(self.to_json())
        pass

    def __str__(self):
        n = self.node_from_json(self.to_json())
        return node_expr_str(n)


weave_types.Function.instance_classes = Node


class Op:
    name: str
    inputs: typing.Dict[str, Node]

    def __init__(self, name, inputs):
        self.name = name
        self.inputs = inputs

    @property
    def shortname(self):
        if ":" in self.name:
            return self.name.split(":")[0]
        return self.name

    def to_json(self):
        json_inputs = {}
        for k, v in self.inputs.items():
            json_inputs[k] = v.to_json()
        return {"name": self.name, "inputs": json_inputs}


class OutputNode(Node):
    from_op: Op
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

    def __repr__(self):
        return "<OutputNode(%s) type: %s op_name: %s>" % (
            id(self),
            self.type,
            self.from_op.name,
        )


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
        return cls(
            weave_types.TypeRegistry.type_from_dict(obj["type"]),
            obj["val"],
        )

    def to_json(self):
        # This is a hack to ensure we don't send huge const nodes to the frontend.
        # TODO: find a better place for this logic.
        # - currently tested in test_show.py:test_large_const_node
        val = self.val
        from . import storage

        ref = storage._get_ref(val)
        from .ops_domain import file

        if ref is not None:
            val = file.get(str(ref)).to_json()
            return val

        return {"nodeType": "const", "type": self.type.to_dict(), "val": val}

    def __str__(self):
        from . import storage

        ref = storage._get_ref(self.val)
        from .ops_domain import file

        if ref is not None:
            return str(file.get(str(ref)))
        return str(self.val)
        # return "<ConstNode %s %s>" % (self.type, self.val)


class VoidNode(Node):
    def to_json(self):
        return {"nodeType": "void", "type": "invalid"}


def for_each(graph: Node, visitor):
    if isinstance(graph, OutputNode):
        for param_name, param_node in graph.from_op.inputs.items():
            for_each(param_node, visitor)
    visitor(graph)


def opname_expr_str(op_name):
    parts = op_name.split("-", 1)
    if len(parts) > 1:
        op_name = parts[1]
    parts = op_name.split(":")
    if len(parts) == 1:
        return op_name
    return parts[0]


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
        elif all([not isinstance(n, OutputNode) for n in node.from_op.inputs.values()]):
            return "%s(%s)" % (
                opname_expr_str(node.from_op.name),
                ", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names),
            )
        if not param_names:
            return "%s()" % opname_expr_str(node.from_op.name)
        return "%s.%s(%s)" % (
            node_expr_str(node.from_op.inputs[param_names[0]]),
            opname_expr_str(node.from_op.name),
            ", ".join(node_expr_str(node.from_op.inputs[n]) for n in param_names[1:]),
        )
    elif isinstance(node, ConstNode):
        if isinstance(node.type, weave_types.Function):
            return node_expr_str(node.val)
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


def map_nodes(node: Node, map_fn: typing.Callable[[Node], Node]) -> Node:
    if isinstance(node, OutputNode):
        inputs = {k: map_nodes(n, map_fn) for k, n in node.from_op.inputs.items()}
        node = OutputNode(node.type, node.from_op.name, inputs)
    return map_fn(node)
