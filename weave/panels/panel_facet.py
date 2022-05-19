from .. import panel
from . import table_state
from .. import weave_internal
from .. import ops

from .. import graph


class Facet(panel.Panel):
    id = "facet"

    def __init__(self, input_node, **config):
        super().__init__(input_node)
        self._table_state = table_state.TableState(self.input_node)
        self._dims = {
            "x": self._table_state.add_column(lambda row: graph.VoidNode()),
            "y": self._table_state.add_column(lambda row: graph.VoidNode()),
            "select": self._table_state.add_column(lambda row: graph.VoidNode()),
            "detail": self._table_state.add_column(lambda row: graph.VoidNode()),
        }
        self._table_state.set_groupby([self._dims["x"], self._dims["y"]])

        if "x" in config:
            self.set_x(config["x"])

        if "y" in config:
            self.set_y(config["y"])

        if "select" in config:
            self.set_select(config["select"])

        if "detail" in config:
            self.set_detail(config["detail"])

    @property
    def var_cell_input(self):
        return weave_internal.make_var_node(
            ops.GroupResultType(self.input_node.type.object_type), "row"
        )

    @property
    def table_query(self):
        return self._table_state

    def set_x(self, expr):
        self._table_state.update_col(self._dims["x"], expr)

    def set_y(self, expr):
        self._table_state.update_col(self._dims["y"], expr)

    def set_select(self, expr):
        self._table_state.update_col(self._dims["select"], expr)

    def set_detail(self, expr):
        self._table_state.update_col(self._dims["detail"], expr)

    @property
    def config(self):
        return {
            "table": self._table_state.to_json(),
            "dims": self._dims,
            "cellSize": {"w": 50, "h": 50},
            "padding": 0,
        }
