import random
import string

from .. import graph
from .. import weave_types
from .. import weave_internal


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

    def _new_col_id(self):
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(14)
        )

    def add_column(self, select_expr, name=""):
        col_id = self._new_col_id()
        self._columns[col_id] = {"panel_id": "", "panel_config": None}
        self._column_names[col_id] = ""

        obj_type = self._input_node.type.object_type
        self._column_select_functions[col_id] = select_expr(
            weave_internal.make_var_node(obj_type, "row")
        )
        self._order.append(col_id)
        return col_id

    def update_col(self, col_id, select_expr):
        self._column_select_functions[col_id] = select_expr(
            weave_internal.make_var_node(
                weave_types.Dict(weave_types.String(), weave_types.Number()), "row"
            )
        )

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
