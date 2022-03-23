from .. import panel
from . import table_state

from .. import graph


class Plot(panel.Panel):
    def __init__(self, input_node):
        self.id = "plot"
        self.input_node = input_node
        self._table_state = table_state.TableState()
        self._dims = {
            "x": self._table_state.add_column(lambda row: graph.VoidNode()),
            "y": self._table_state.add_column(lambda row: graph.VoidNode()),
            "color": self._table_state.add_column(lambda row: graph.VoidNode()),
            "label": self._table_state.add_column(lambda row: graph.VoidNode()),
            "tooltip": self._table_state.add_column(lambda row: graph.VoidNode()),
        }

    @property
    def table_query(self):
        return self._table_state

    def set_x(self, expr):
        self._table_state.update_col(self._dims["x"], expr)

    def set_y(self, expr):
        self._table_state.update_col(self._dims["y"], expr)

    @property
    def config(self):
        return {"table": self._table_state.to_json(), "dims": self._dims}
