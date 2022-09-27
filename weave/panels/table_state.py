import random
import string
import copy

from .. import graph
from .. import weave_internal
from .. import ops
from .. import panel


class TableState(object):
    def __init__(self, input_node):
        self._input_node = input_node
        self._auto_columns = False
        self._columns = {}
        self._pre_filter_function = graph.VoidNode()
        self._column_names = {}
        self._column_select_functions = {}
        self._order = []
        self._group_by = []
        self._sort = []
        self._page_size = 10
        self._page = 0

    def clone(self):
        return copy.deepcopy(self)

    def _new_col_id(self):
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(14)
        )

    def add_column(self, select_expr, name=""):
        col_id = self._new_col_id()
        self._columns[col_id] = {"panel_id": "", "panel_config": None}
        self._column_names[col_id] = name
        self._order.append(col_id)
        self.update_col(col_id, select_expr)
        return col_id

    def set_groupby(self, col_ids):
        self._group_by = col_ids

    def enable_groupby(self, col_id):
        if col_id not in self._group_by:
            self._group_by.append(col_id)

    def disable_groupby(self, col_id):
        if col_id in self._group_by:
            self._group_by.remove(col_id)

    def update_col(self, col_id, select_expr):
        object_type = self._input_node.type.object_type
        if self._group_by and col_id not in self._group_by:
            object_type = ops.GroupResultType(object_type)
        selected = select_expr(weave_internal.make_var_node(object_type, "row"))

        if isinstance(selected, panel.Panel):
            self._column_select_functions[col_id] = selected.input_node
            self._columns[col_id] = {
                "panel_id": selected.id,
                "panel_config": selected.config,
            }
        else:
            # TOTAL HACK HERE THIS IS NOT GENERAL!
            # TODO: abstract this behavior. We need to do this wherever we encounter a list
            # of Nodes. I think probably in lazy_call().
            if isinstance(selected, list):
                make_list_args = {}
                for i, item in enumerate(selected):
                    make_list_args["i%s" % i] = item
                selected = ops.make_list(**make_list_args)
            self._column_select_functions[col_id] = selected

    def __eq__(self, other):
        return self.to_json() == other.to_json()

    def to_json(self):
        # TODO: its annoying that we have to manually rename everything to fix js
        # v python conventions. Automate or settle on one.
        columns = {
            id: {"panelId": v["panel_id"], "panelConfig": v["panel_config"]}
            for (id, v) in self._columns.items()
        }
        pre_filter_function = self._pre_filter_function.to_json()
        column_select_functions = {
            id: v.to_json() for (id, v) in self._column_select_functions.items()
        }
        return {
            "autoColumns": self._auto_columns,
            "columns": columns,
            "preFilterFunction": pre_filter_function,
            "columnNames": self._column_names,
            "columnSelectFunctions": column_select_functions,
            "order": self._order,
            "groupBy": self._group_by,
            "sort": self._sort,
            "pageSize": self._page_size,
            "page": self._page,
        }
