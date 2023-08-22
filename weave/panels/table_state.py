import contextlib
import contextvars
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
from .. import weave_types
from ..language_features.tagging import tagged_value_type


@decorator_type.type()
class PanelDef:
    panelId: str
    panelVars: dict[str, graph.Node] = dataclasses.field(default_factory=dict)
    panelConfig: typing.Any = dataclasses.field(default_factory=lambda: None)


class SortDef(typing.TypedDict):
    dir: str
    columnId: str


_use_consistent_col_ids: contextvars.ContextVar[
    typing.Optional[bool]
] = contextvars.ContextVar("use_consistent_col_ids", default=False)


@contextlib.contextmanager
def use_consistent_col_ids(val: bool = True):
    token = _use_consistent_col_ids.set(val)
    yield
    _use_consistent_col_ids.reset(token)


@decorator_type.type()
class TableState:
    input_node: graph.Node = dataclasses.field(default_factory=lambda: graph.VoidNode())
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
    sort: list[SortDef] = dataclasses.field(default_factory=list)
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
        if _use_consistent_col_ids.get():
            if hasattr(self, "_col_id_counter"):
                self._col_id_counter += 1
            else:
                self._col_id_counter = 0
            return f"col_{self._col_id_counter}"
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(14)
        )

    def _expr_to_fn_node(self, fn, post_group_dimensionality=False):
        if isinstance(fn, graph.Node):
            return fn
        self_input_type = self.input_node.type
        if isinstance(self_input_type, weave_types.Function):
            self_input_type = self_input_type.output_type
        object_type = self_input_type.object_type

        # TODO: we are not deriving this type correctly
        if post_group_dimensionality:
            object_type = tagged_value_type.TaggedValueType(
                weave_types.TypedDict({}), weave_types.List(object_type)
            )

        sig = inspect.signature(fn)
        kwargs = {}
        if "domain" in sig.parameters:
            kwargs = {
                "domain": weave_internal.make_var_node(
                    weave_types.List(object_type), "domain"
                )
            }
        if "index" in sig.parameters:
            kwargs["index"] = weave_internal.make_var_node(weave_types.Int(), "index")
        return fn(weave_internal.make_var_node(object_type, "row"), **kwargs)

    def add_column(
        self,
        select_expr,
        name="",
        panel_def: typing.Optional[PanelDef] = None,
        groupby: bool = False,
        sort_dir: typing.Optional[str] = None,
    ):
        col_id = self._new_col_id()
        if panel_def is None:
            panel_def = PanelDef("", {}, None)
        self.columns[col_id] = panel_def
        self.columnNames[col_id] = name
        self.order.append(col_id)
        if groupby:
            self.enable_groupby(col_id)
        self.update_col(col_id, select_expr)
        if sort_dir:
            self.enable_sort(col_id, dir=sort_dir)
        return col_id

    def set_groupby(self, col_ids):
        self.group_by = col_ids

    def enable_groupby(self, col_id):
        if col_id not in self.groupBy:
            self.groupBy.append(col_id)

    def disable_groupby(self, col_id):
        if col_id in self.groupBy:
            self.groupBy.remove(col_id)

    def set_filter_fn(self, filter_exp):
        self.preFilterFunction = self._expr_to_fn_node(filter_exp)

    def enable_sort(self, col_id, dir="asc"):
        for sort_def in self.sort:
            if sort_def["columnId"] == col_id:
                sort_def["dir"] = dir
                return
        self.sort.append(SortDef(dir=dir, columnId=col_id))

    def update_col(self, col_id, select_expr):
        selected = self._expr_to_fn_node(
            select_expr, self.groupBy and col_id not in self.groupBy
        )

        if isinstance(selected, panel.Panel):
            self.columnSelectFunctions[col_id] = selected.input_node
            self.columns[col_id] = PanelDef(
                panelVars=selected.vars,
                panelId=selected.id,
                panelConfig=selected.config,
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
