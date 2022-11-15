import dataclasses
import inspect
import random
import string
import copy
import typing

from .. import graph
from .. import weave_internal
from .. import ops
from .. import panel
from .. import decorator_type


@decorator_type.type()
class PanelDef:
    panelId: str
    panelConfig: typing.Optional[dict[str, str]]  # TODO: WRONG!!!


@decorator_type.type()
class TableState:
    input_node: graph.Node
    autoColumns: bool = dataclasses.field(default=False)
    columns: dict[str, PanelDef] = dataclasses.field(default_factory=dict)
    preFilterFunction: graph.Node = dataclasses.field(
        default_factory=lambda: graph.VoidNode()
    )
    columnNames: dict[str, str] = dataclasses.field(default_factory=dict)
    columnSelectFunctions: dict[str, graph.Node] = dataclasses.field(
        default_factory=dict
    )
    order: list[str] = dataclasses.field(default_factory=list)
    groupBy: list[str] = dataclasses.field(default_factory=list)
    sort: list[str] = dataclasses.field(default_factory=list)  # TODO: WRONG
    pageSize: int = dataclasses.field(default=10)
    page: int = dataclasses.field(default=0)

    # def __init__(self, input_node):
    #     self._input_node = input_node
    #     self._auto_columns = False
    #     self._columns = {}
    #     self._pre_filter_function = graph.VoidNode()
    #     self._column_names = {}
    #     self._column_select_functions = {}
    #     self._order = []
    #     self._group_by = []
    #     self._sort = []
    #     self._page_size = 10
    #     self._page = 0

    def clone(self):
        return copy.deepcopy(self)

    def _new_col_id(self):
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(14)
        )

    def add_column(self, select_expr, name=""):
        col_id = self._new_col_id()
        self.columns[col_id] = PanelDef("", None)
        self.columnNames[col_id] = name
        self.order.append(col_id)
        self.update_col(col_id, select_expr)
        return col_id

    def set_groupby(self, col_ids):
        self.group_by = col_ids

    def enable_groupby(self, col_id):
        if col_id not in self.groupBy:
            self.groupBy.append(col_id)

    def disable_groupby(self, col_id):
        if col_id in self.groupBy:
            self.groupBy.remove(col_id)

    def update_col(self, col_id, select_expr):
        object_type = self.input_node.type.object_type
        if self.groupBy and col_id not in self.groupBy:
            object_type = ops.GroupResultType(object_type)

        sig = inspect.signature(select_expr)
        kwargs = {}
        if "domain" in sig.parameters:
            kwargs = {
                "domain": weave_internal.make_var_node(
                    weave.types.List(object_type), "domain"
                )
            }
        selected = select_expr(
            weave_internal.make_var_node(object_type, "row"), **kwargs
        )

        if isinstance(selected, panel.Panel):
            self.columnSelectFunctions[col_id] = selected.input_node
            self.columns[col_id] = PanelDef(
                panelId=selected.id, panelConfig=selected.config
            )
        else:
            # TOTAL HACK HERE THIS IS NOT GENERAL!
            # TODO: abstract this behavior. We need to do this wherever we encounter a list
            # of Nodes. I think probably in lazy_call().
            if isinstance(selected, list):
                make_list_args = {}
                for i, item in enumerate(selected):
                    make_list_args["i%s" % i] = item
                selected = ops.make_list(**make_list_args)
            self.columnSelectFunctions[col_id] = selected

    def __eq__(self, other):
        return self.to_json() == other.to_json()

    def to_json(self):
        # TODO: its annoying that we have to manually rename everything to fix js
        # v python conventions. Automate or settle on one.
        columns = {
            id: {"panelId": v.panelId, "panelConfig": v.panelConfig}
            for (id, v) in self.columns.items()
        }
        pre_filter_function = self.preFilterFunction.to_json()
        column_select_functions = {
            id: v.to_json() for (id, v) in self.columnSelectFunctions.items()
        }
        return {
            "autoColumns": self.autoColumns,
            "columns": columns,
            "preFilterFunction": pre_filter_function,
            "columnNames": self.columnNames,
            "columnSelectFunctions": column_select_functions,
            "order": self.order,
            "groupBy": self.groupBy,
            "sort": self.sort,
            "pageSize": self.pageSize,
            "page": self.page,
        }
