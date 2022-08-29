from .. import panel
from . import table_state


class Table(panel.Panel):
    id = "table"

    def __init__(self, input_node, **kwargs):
        super().__init__(input_node)
        self._table_state = table_state.TableState(self.input_node)

        if "columns" in kwargs:
            for column_expr in kwargs["columns"]:
                self.append_column(column_expr)

    @property
    def table_query(self):
        return self._table_state

    def append_column(self, expr, name=""):
        self._table_state.add_column(expr, name=name)

    @property
    def config(self):
        return {"tableState": self._table_state.to_json()}
