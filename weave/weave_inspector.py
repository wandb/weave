# This file contains helper functions to inspect nodes. The main
# purpose it to be used in debugging sessions

"""
NODE ID    NAME                                            PARAM        NODE TYPE          TYPE NAME          TYPE ID
---------  ----------------------------------------------  -----------  -----------------  ---------------  ---------
0          ** CONST_VAL                                                 ConstNode          Function                 0
1          f └- dict                                                    RuntimeOutputNode  TypedDict                7
2          f   ├- number-bin                               bin          OutputNode         TV(NoneType)             8
3          f   │ ├- pick                                   in           OutputNode         TV(NoneType)             8
4          f   │ │ ├- row                                  obj          VarNode            TV(TypedDict)            1
5          f   │ │ └- <<_step>>                            key          ConstNode          String                   3
6          f   │ └- numbers-binsequal                      binFn        OutputNode         Function                11
7          f   │   ├- list                                 arr          OutputNode         List                    14
8          f   │   │ ├- numbers-min                        a            OutputNode         TV(Number)              15
9          f   │   │ │ └- pick                             arr          OutputNode         TV(List)                17
10         f   │   │ │   ├- concat                         obj          OutputNode         TV(List)                21
11         f   │   │ │   │ └- run-history3                 arr          OutputNode         TV(List)                24
12         f   │   │ │   │   └- project-filteredRuns       run          OutputNode         TV(List)                28
13         f   │   │ │   │     ├- root-project             project      OutputNode         TV(projectType)         30
14         f   │   │ │   │     │ ├- <<shawn>>              entityName   ConstNode          String                   3
15         f   │   │ │   │     │ └- <<fasion-sweep>>       projectName  ConstNode          String                   3
16         f   │   │ │   │     ├- <<{"name":...":null}}>>  runFilters   ConstNode          String                   3
17         f   │   │ │   │     └- <<-createdAt>>           order        ConstNode          String                   3
.          f   │   │ │   └- NODE_ID(5)                     key          ConstNode          String                   3
18         f   │   │ └- numbers-max                        b            OutputNode         TV(Number)              15
.          f   │   │   └- NODE_ID(9)                       arr          OutputNode         TV(List)                17
19         f   │   └- <<50>>                               bins         ConstNode          Number                  12
20         f   └- run-name                                 run_name     OutputNode         TV(String)              10
21         f     └- tag-run                                run          OutputNode         TV(runType)             32
.          f       └- NODE_ID(4)                           obj          VarNode            TV(TypedDict)            1


**Types Table**
TYPE ID    TYPE NAME
---------  -----------------------------------
0          ** Function
1            ├- [input.row]: TV(TypedDict)
2            │ ├- [tag]: TypedDict
3            │ │ ├- [entityName]: String
.            │ │ ├- [projectName]: String
4            │ │ ├- [project]: projectType
.            │ │ ├- [runFilters]: String
.            │ │ ├- [order]: String
5            │ │ └- [run]: runType
6            │ └- [value]: TypedDict
7            └- [output_type]: TypedDict
8              ├- [bin]: TV(NoneType)
.              │ ├- [tag]: TYPE_ID(2)
9              │ └- [value]: NoneType
10             └- [run_name]: TV(String)
.                ├- [tag]: TYPE_ID(2)
.                └- [value]: String
11         ** Function
12           ├- [input.row]: Number
13           └- [output_type]: TypedDict
.              ├- [start]: Number
.              └- [stop]: Number
14         ** List
15           └- [object_type]: TV(Number)
16             ├- [tag]: TypedDict
.              │ ├- [entityName]: String
.              │ ├- [projectName]: String
.              │ ├- [project]: projectType
.              │ ├- [runFilters]: String
.              │ └- [order]: String
.              └- [value]: Number
17         ** TV(List)
.            ├- [tag]: TYPE_ID(16)
18           └- [value]: List
19             └- [object_type]: TV(NoneType)
20               ├- [tag]: TypedDict
.                │ └- [run]: runType
.                └- [value]: NoneType
21         ** TV(List)
.            ├- [tag]: TYPE_ID(16)
22           └- [value]: List
23             └- [object_type]: TV(TypedDict)
.                ├- [tag]: TYPE_ID(20)
.                └- [value]: TypedDict
24         ** TV(List)
.            ├- [tag]: TYPE_ID(16)
25           └- [value]: List
26             └- [object_type]: TV(List)
.                ├- [tag]: TYPE_ID(20)
27               └- [value]: List
.                  └- [object_type]: TypedDict
28         ** TV(List)
.            ├- [tag]: TYPE_ID(16)
29           └- [value]: List
.              └- [object_type]: runType
30         ** TV(projectType)
31           ├- [tag]: TypedDict
.            │ ├- [entityName]: String
.            │ └- [projectName]: String
.            └- [value]: projectType
32         ** TV(runType)
.            ├- [tag]: TYPE_ID(16)
.            └- [value]: runType

"""

import dataclasses
import json
import typing

import tabulate


from . import weave_types as types
from . import graph

from .partial_object import PartialObjectType


def _trimmed_string(s: str, max_len: int = 20) -> str:
    if len(s) > max_len - 3:
        return s[: max_len // 2] + "..." + s[-max_len // 2 :]
    return s


def _node_name(node: graph.Node) -> str:
    if isinstance(node, graph.OutputNode):
        return node.from_op.name
    elif isinstance(node, graph.VarNode):
        return node.name
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.val, (str, int, float, bool)):
            return _trimmed_string("<<" + str(node.val) + ">>")
        return "CONST_VAL"
    elif isinstance(node, graph.VoidNode):
        return "VOID"
    else:
        raise Exception(f"Unknown node type: {type(node)}")


def _node_type_name(node: graph.Node) -> str:
    return type(node).__name__


def _type_name(node_type: types.Type) -> str:
    from .language_features.tagging import tagged_value_type

    if isinstance(node_type, tagged_value_type.TaggedValueType):
        return f"TV({_type_name(node_type.value)})"
    return str(type(node_type).__name__)


def _type_props(node_type: types.Type) -> typing.Dict[str, types.Type]:
    if isinstance(node_type, types.UnionType):
        return {str(n): m for n, m in enumerate(node_type.members)}
    elif isinstance(node_type, types.TypedDict):
        return node_type.property_types
    elif isinstance(node_type, types.Function):
        props = {f"input.{k}": v for k, v in node_type.input_types.items()}
        props["output_type"] = node_type.output_type
        return props
    elif isinstance(node_type, PartialObjectType):
        return node_type.keys
    return node_type.type_vars


@dataclasses.dataclass
class NodeIter:
    param_name: str
    node: graph.Node
    depth: int
    is_last: bool
    parent_node: typing.Optional[graph.Node] = None


@dataclasses.dataclass
class TypeIter:
    param_name: str
    node_type: types.Type
    depth: int
    is_last: bool
    parent_type: typing.Optional[types.Type] = None


def _type_iter(node_type: types.Type) -> typing.Iterator[TypeIter]:
    stack = [TypeIter("", node_type, 0, True)]
    while stack:
        type_iter = stack.pop(0)
        yield type_iter
        props = _type_props(type_iter.node_type)
        num_props = len(props)

        for ndx, (prop_name, prop_type) in reversed(list(enumerate(props.items()))):
            stack.insert(
                0,
                TypeIter(
                    prop_name,
                    prop_type,
                    type_iter.depth + 1,
                    is_last=num_props == ndx + 1,
                    parent_type=type_iter.node_type,
                ),
            )


def _print_type_table(
    type_iterator: typing.Iterator[TypeIter],
    type_to_id_map: dict[types.Type, int],
) -> None:
    table = []
    completed_nodes = set()
    reference_nodes = set()
    depth_state = []
    last_depth = -1
    for type_iter in type_iterator:
        if type_iter.depth > last_depth:
            depth_state.append("OPEN")
        last_depth = type_iter.depth
        depth_state = depth_state[: type_iter.depth + 1]
        if type_iter.is_last:
            depth_state[type_iter.depth] = "CLOSED"
            depth_state = depth_state[: type_iter.depth + 1]
        name_prefix = ""
        for depth, state in enumerate(depth_state):
            if state == "OPEN":
                if depth == type_iter.depth:
                    name_prefix += "├-"
                else:
                    name_prefix += "│ "
            elif state == "CLOSED":
                if depth == type_iter.depth:
                    if depth == 0:
                        name_prefix += "**"
                    else:
                        name_prefix += "└-"
                else:
                    name_prefix += "  "

        if type_iter.param_name:
            name_prefix += f" [{type_iter.param_name}]: "
        else:
            name_prefix += " "

        row = {
            "TYPE ID": type_to_id_map[type_iter.node_type],
            "TYPE NAME": name_prefix + _type_name(type_iter.node_type),
        }

        if type_iter.node_type in completed_nodes:
            reference_nodes.add(type_iter.node_type)
            if type_iter.depth > 0 and not (type_iter.parent_type in reference_nodes):
                row["TYPE ID"] = "."
                if len(_type_props(type_iter.node_type)) == 0:
                    row["TYPE NAME"] = name_prefix + _type_name(type_iter.node_type)
                else:
                    row["TYPE NAME"] = (
                        name_prefix + f"TYPE_ID({type_to_id_map[type_iter.node_type]})"
                    )
                table.append(row)
        else:
            row["TYPE ID"] = type_to_id_map[type_iter.node_type]
            row["TYPE NAME"] = name_prefix + _type_name(type_iter.node_type)
            table.append(row)
            completed_nodes.add(type_iter.node_type)

    print("\n**Types Table**")
    tabulate.PRESERVE_WHITESPACE = True
    print(tabulate.tabulate(table, headers="keys"))
    print("")


@dataclasses.dataclass
class TypeInspector:
    base_type: types.Type

    id_to_type_map: dict[int, types.Type] = dataclasses.field(default_factory=dict)
    type_to_id_map: dict[types.Type, int] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self._build_maps()

    def _build_maps(self) -> None:
        for type_iter in self._pre_order_type_iter():
            if type_iter.node_type not in self.type_to_id_map:
                type_id = len(self.id_to_type_map)
                self.id_to_type_map[type_id] = type_iter.node_type
                self.type_to_id_map[type_iter.node_type] = type_id

    def _pre_order_type_iter(self) -> typing.Iterator[TypeIter]:
        for type_iter in _type_iter(self.base_type):
            yield type_iter

    def lookup(self, type_id: int) -> types.Type:
        target_type = self.id_to_type_map[type_id]
        return target_type

    def summarize(self) -> None:
        print("\Type Summary:")
        print("\nType as string:", str(self.base_type))
        _print_type_table(self._pre_order_type_iter(), self.type_to_id_map)


@dataclasses.dataclass
class NodeInspector:
    base_node: graph.Node

    id_to_node_map: dict[int, graph.Node] = dataclasses.field(default_factory=dict)
    node_to_id_map: dict[graph.Node, int] = dataclasses.field(default_factory=dict)

    id_to_type_map: dict[int, types.Type] = dataclasses.field(default_factory=dict)
    type_to_id_map: dict[types.Type, int] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self._build_maps()

    def _pre_order_node_iter(self) -> typing.Iterator[NodeIter]:
        stack = [NodeIter("", self.base_node, 0, True)]
        while stack:
            node_iter = stack.pop(0)
            yield node_iter
            if isinstance(node_iter.node, graph.OutputNode):
                num_params = len(node_iter.node.from_op.inputs)
                items = enumerate(node_iter.node.from_op.inputs.items())
                reversed_items = reversed(list(items))
                for ndx, (param_name, param) in reversed_items:
                    stack.insert(
                        0,
                        NodeIter(
                            param_name,
                            param,
                            node_iter.depth + 1,
                            is_last=num_params == ndx + 1,
                            parent_node=node_iter.node,
                        ),
                    )
            elif isinstance(node_iter.node, graph.ConstNode) and isinstance(
                node_iter.node.val, graph.Node
            ):
                stack.insert(
                    0,
                    NodeIter(
                        node_iter.param_name,
                        node_iter.node.val,
                        node_iter.depth + 1,
                        is_last=True,
                        parent_node=node_iter.node,
                    ),
                )

    def _pre_order_type_iter(self) -> typing.Iterator[TypeIter]:
        for node_iter in self._pre_order_node_iter():
            for type_iter in _type_iter(node_iter.node.type):
                yield type_iter

    def _build_maps(self) -> None:
        for node_iter in self._pre_order_node_iter():
            if node_iter.node not in self.node_to_id_map:
                node_id = len(self.id_to_node_map)
                self.id_to_node_map[node_id] = node_iter.node
                self.node_to_id_map[node_iter.node] = node_id
            node_type = node_iter.node.type
            for type_iter in _type_iter(node_type):
                if type_iter.node_type not in self.type_to_id_map:
                    type_id = len(self.id_to_type_map)
                    self.id_to_type_map[type_id] = type_iter.node_type
                    self.type_to_id_map[type_iter.node_type] = type_id

    def lookup(self, node_id: int) -> graph.Node:
        target_node = self.id_to_node_map[node_id]
        return target_node

    def summarize(self) -> None:
        print("\nNode Summary:")
        print("\nNode as string:", self.base_node)
        self.print_node_table()
        print("\nType as string:", str(self.base_node.type))
        _print_type_table(self._pre_order_type_iter(), self.type_to_id_map)

    def print_node_table(self) -> None:
        table = []
        completed_nodes = set()
        reference_nodes = set()
        depth_state = []
        last_depth = -1
        for node_iter in self._pre_order_node_iter():
            if node_iter.depth > last_depth:
                depth_state.append("OPEN")
            last_depth = node_iter.depth
            depth_state = depth_state[: node_iter.depth + 1]
            if node_iter.is_last:
                depth_state[node_iter.depth] = "CLOSED"
                depth_state = depth_state[: node_iter.depth + 1]
            if isinstance(node_iter.node, graph.ConstNode) and isinstance(
                node_iter.node.val, graph.Node
            ):
                depth_state[node_iter.depth] = "FUNCTION"
            name_prefix = ""
            for depth, state in enumerate(depth_state):
                if state == "OPEN":
                    if depth == node_iter.depth:
                        name_prefix += "├-"
                    else:
                        name_prefix += "│ "
                elif state == "FUNCTION":
                    if depth == node_iter.depth:
                        if depth == 0:
                            name_prefix += "**"
                        else:
                            name_prefix += "└-"
                    else:
                        name_prefix += "f "
                elif state == "CLOSED":
                    if depth == node_iter.depth:
                        if depth == 0:
                            name_prefix += "**"
                        else:
                            name_prefix += "└-"
                    else:
                        name_prefix += "  "

            name_prefix += " "

            row = {
                "NODE ID": None,
                "NAME": None,
                "PARAM": node_iter.param_name,
                "NODE TYPE": _node_type_name(node_iter.node),
                "TYPE NAME": _type_name(node_iter.node.type),
                "TYPE ID": self.type_to_id_map[node_iter.node.type],
            }
            if node_iter.node in completed_nodes:
                reference_nodes.add(node_iter.node)
                if not (node_iter.parent_node in reference_nodes):
                    row["NODE ID"] = "."
                    row["NAME"] = (
                        name_prefix + f"NODE_ID({self.node_to_id_map[node_iter.node]})"
                    )
                    table.append(row)
            else:
                row["NODE ID"] = self.node_to_id_map[node_iter.node]
                row["NAME"] = name_prefix + _node_name(node_iter.node)
                table.append(row)
                completed_nodes.add(node_iter.node)

        print("\n**Graph Table**")
        tabulate.PRESERVE_WHITESPACE = True
        print(tabulate.tabulate(table, headers="keys"))
        print("")
