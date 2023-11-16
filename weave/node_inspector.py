# This file contains helper functions to inspect nodes. The main 
# purpose it to be used in debugging sessions


# NODE ID    NAME                                  PARAM        NODE TYPE          TYPE NAME          TYPE ID
# ---------  ------------------------------------  -----------  -----------------  ---------------  ---------
# 0          └- map                                             OutputNode         TV(List)                 0
# 1            ├- groupby                          arr          OutputNode         TV(List)                 1
# 2            │ ├- concat                         arr          OutputNode         TV(List)                 2
# 3            │ │ └- run-history3                 arr          OutputNode         TV(List)                 3
# 4            │ │   └- project-filteredRuns       run          OutputNode         TV(List)                 4
# 5            │ │     ├- root-project             project      OutputNode         TV(projectType)          5
# 6            │ │     │ ├- <<shawn>>              entityName   ConstNode          String                   6
# 7            │ │     │ └- <<fasion-sweep>>       projectName  ConstNode          String                   6
# 8            │ │     ├- <<{"name":...":null}}>>  runFilters   ConstNode          String                   6
# 9            │ │     └- <<-createdAt>>           order        ConstNode          String                   6
# 10           │ └- CONST_VAL                      groupByFn    ConstNode          Function                 7
# 11           │ f └- dict                         groupByFn    RuntimeOutputNode  TypedDict                8
# 12           │ f   ├- number-bin                 bin          OutputNode         TV(NoneType)             9
# 13           │ f   │ ├- pick                     in           OutputNode         TV(NoneType)             9
# 14           │ f   │ │ ├- row                    obj          VarNode            TV(TypedDict)           10
# 15           │ f   │ │ └- <<_step>>              key          ConstNode          String                   6
# 16           │ f   │ └- numbers-binsequal        binFn        OutputNode         Function                11
# 17           │ f   │   ├- list                   arr          OutputNode         List                    12
# 18           │ f   │   │ ├- numbers-min          a            OutputNode         TV(Number)              13
# 19           │ f   │   │ │ └- pick               arr          OutputNode         TV(List)                14
# .            │ f   │   │ │   ├- NODE_ID(2)       obj          OutputNode         TV(List)                 2
# .            │ f   │   │ │   └- NODE_ID(15)      key          ConstNode          String                   6
# 20           │ f   │   │ └- numbers-max          b            OutputNode         TV(Number)              13
# .            │ f   │   │   └- NODE_ID(19)        arr          OutputNode         TV(List)                14
# 21           │ f   │   └- <<50>>                 bins         ConstNode          Number                  15
# 22           │ f   └- run-name                   run_name     OutputNode         TV(String)              16
# 23           │ f     └- tag-run                  run          OutputNode         TV(runType)             17
# .            │ f       └- NODE_ID(14)            obj          VarNode            TV(TypedDict)           10
# 24           └- CONST_VAL                        mapFn        ConstNode          Function                18
# 25           f └- dict                           mapFn        RuntimeOutputNode  TypedDict               19
# 26           f   ├- group-groupkey               groupKey     OutputNode         TV(TypedDict)           20
# 27           f   │ └- row                        obj          VarNode            TV(List)                21
# 28           f   ├- numbers-min                  loss_min     OutputNode         TV(Number)              22
# 29           f   │ └- pick                       arr          OutputNode         TV(List)                23
# .            f   │   ├- NODE_ID(27)              obj          VarNode            TV(List)                21
# 30           f   │   └- <<loss>>                 key          ConstNode          String                   6
# 31           f   ├- numbers-avg                  loss_avg     OutputNode         TV(Number)              22
# .            f   │ └- NODE_ID(29)                arr          OutputNode         TV(List)                23
# 32           f   ├- numbers-max                  loss_max     OutputNode         TV(Number)              22
# .            f   │ └- NODE_ID(29)                arr          OutputNode         TV(List)                23
# 33           f   ├- numbers-min                  acc_min      OutputNode         TV(Number)              22
# 34           f   │ └- pick                       arr          OutputNode         TV(List)                23
# .            f   │   ├- NODE_ID(27)              obj          VarNode            TV(List)                21
# 35           f   │   └- <<acc>>                  key          ConstNode          String                   6
# 36           f   ├- numbers-avg                  acc_avg      OutputNode         TV(Number)              22
# .            f   │ └- NODE_ID(34)                arr          OutputNode         TV(List)                23
# 37           f   └- numbers-max                  acc_max      OutputNode         TV(Number)              22
# .            f     └- NODE_ID(34)                arr          OutputNode         TV(List)                23


import dataclasses
import json
import typing

import tabulate

from . import weave_types as types
from . import graph

def _trimmed_string(s: str, max_len: int = 20):
    if len(s) > max_len - 3:
        return s[:max_len // 2] + "..." + s[-max_len // 2:]
    return s

def _node_name(node: graph.Node):
    if isinstance(node, graph.OutputNode):
        return node.from_op.name
    elif isinstance(node, graph.VarNode):
        return node.name
    elif isinstance(node, graph.ConstNode):
        if (isinstance(node.val, (str, int, float, bool))):
            return _trimmed_string("<<" + str(node.val) + ">>")
        return 'CONST_VAL'
    elif isinstance(node, graph.VoidNode):
        return 'VOID'
    else:
        raise Exception(f"Unknown node type: {type(node)}")
    
def _node_type_name(node: graph.Node):
    return type(node).__name__
    

def _type_name(node_type: types.Type):
    from .language_features.tagging import tagged_value_type
    if isinstance(node_type, tagged_value_type.TaggedValueType):
        return f"TV({_type_name(node_type.value)})"
    return type(node_type).__name__


def _type_props(node_type: types.Type):
    if isinstance(node_type, types.UnionType):
        return {str(n):m for n, m in enumerate(node_type.members)}
    elif isinstance(node_type, types.TypedDict):
        return node_type.property_types
    elif isinstance(node_type, types.Function):
        props = {f"input.{k}": v for k, v in node_type.input_types.items()}
        props["output_type"] = node_type.output_type
        return props
    return node_type.type_vars


@dataclasses.dataclass
class NodeIter:
    param_name: str
    node: graph.Node
    depth: int
    is_last: bool
    parent_node: typing.Optional[graph.Node] = None

    


@dataclasses.dataclass
class Inspector:
    base_node: graph.Node

    id_to_node_map: dict[int, graph.Node] = dataclasses.field(default_factory=dict)
    node_to_id_map: dict[graph.Node, int] = dataclasses.field(default_factory=dict)

    id_to_type_map: dict[int, types.Type] = dataclasses.field(default_factory=dict)
    type_to_id_map: dict[types.Type, int] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        self._build_maps()

    def _pre_order_iter(self):
        stack = [NodeIter("", self.base_node, 0, True)]
        while stack:
            node_iter = stack.pop(0)
            yield node_iter
            if isinstance(node_iter.node, graph.OutputNode):
                num_params = len(node_iter.node.from_op.inputs)
                items = enumerate(node_iter.node.from_op.inputs.items())
                reversed_items = reversed(list(items))
                for ndx, (param_name, param) in reversed_items:
                    stack.insert(0, NodeIter(param_name, param, node_iter.depth + 1, is_last=num_params == ndx + 1, parent_node=node_iter.node))
            elif isinstance(node_iter.node, graph.ConstNode) and isinstance(node_iter.node.val, graph.Node):
                stack.insert(0, NodeIter(node_iter.param_name, node_iter.node.val, node_iter.depth + 1, is_last=True,  parent_node=node_iter.node))
    
    def _type_iter(self, node_type: types.Type):
        stack = [node_type]
        seen = set()
        while stack:
            type_iter = stack.pop(0)
            yield type_iter
            seen.add(type_iter)
            props = _type_props(type_iter)
            for prop_name, prop_type in reversed(props.items()):
                if prop_type not in seen:
                    stack.insert(0, prop_type)
        

    def _build_maps(self):
        for node_iter in self._pre_order_iter():
            if node_iter.node not in self.node_to_id_map:
                node_id = len(self.id_to_node_map)
                self.id_to_node_map[node_id] = node_iter.node
                self.node_to_id_map[node_iter.node] = node_id
            node_type = node_iter.node.type
            for node_type_iter in self._type_iter(node_type):
                if node_type_iter not in self.type_to_id_map:
                    type_id = len(self.id_to_type_map)
                    self.id_to_type_map[type_id] = node_type_iter
                    self.type_to_id_map[node_type_iter] = type_id

    def summarize(self, node_id: typing.Optional[int] = None):
        if (node_id is not None):
            target_node = self.id_to_node_map[node_id]
            Inspector(target_node).summarize()
            return target_node
        else:
            self.print_node_table()
            self.print_type_table()


    def print_node_table(self):
        table = []
        completed_nodes = set()
        reference_nodes = set()
        depth_state = []
        last_depth = -1
        for node_iter in self._pre_order_iter():
            if node_iter.depth > last_depth:
                depth_state.append("OPEN")
            # elif node_iter.depth < last_depth:
            #     pass
            last_depth = node_iter.depth
            depth_state = depth_state[:node_iter.depth + 1]
            if node_iter.is_last:
                depth_state[node_iter.depth] = "CLOSED"
                depth_state = depth_state[:node_iter.depth + 1]
            if isinstance(node_iter.node, graph.ConstNode) and isinstance(node_iter.node.val, graph.Node):
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
                        name_prefix += "└-"
                    else:
                        name_prefix += "f "
                elif state == "CLOSED":
                    if depth == node_iter.depth:
                        name_prefix += "└-"
                    else:
                        name_prefix += "  "

            name_prefix += " "

            base_data = {
                        'NODE ID': None,
                        'NAME': None,
                        'PARAM': node_iter.param_name,
                        'NODE TYPE': _node_type_name(node_iter.node),
                        'TYPE NAME': _type_name(node_iter.node.type),
                        'TYPE ID': self.type_to_id_map[node_iter.node.type],
                    }
            if node_iter.node in completed_nodes:
                reference_nodes.add(node_iter.node)
                if not (node_iter.parent_node in reference_nodes):
                    base_data['NODE ID'] = '.'
                    base_data['NAME'] = name_prefix + f"NODE_ID({self.node_to_id_map[node_iter.node]})"
                    table.append(base_data)
            else:
                base_data['NODE ID'] = self.node_to_id_map[node_iter.node]
                base_data['NAME'] = name_prefix + _node_name(node_iter.node)
                table.append(base_data)
                completed_nodes.add(node_iter.node)

        print("\n**Graph Table**")
        tabulate.PRESERVE_WHITESPACE = True
        print(tabulate.tabulate(table, headers="keys"))
        print("")

    def print_type_table(self):
        table = []
        for id, node_type in self.id_to_type_map.items():
            base_row ={
                'TYPE ID': id,
                'TYPE NAME': _type_name(node_type),
            }
            props =  _type_props(node_type)
            props_str = ""
            for p, t in props.items():
                props_str += f"{p}: {self.type_to_id_map[t]}:{_type_name(t)}\n"
            props = {p: str(self.type_to_id_map[t]) + ":" + _type_name(t) for p, t in props.items()}
            base_row['PROPERTIES'] = props_str
            
            table.append(base_row)

        print("\n**Simplified Types Table**")
        tabulate.PRESERVE_WHITESPACE = True
        print(tabulate.tabulate(table, headers="keys"))
        print("")

