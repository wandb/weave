from .. import panel
from . import table_state


class Table(panel.Panel):
    id = "table"

    def __init__(self, input_node, **kwargs):
        super().__init__(input_node)
        self._table_state = None  # None instructs JS to automatically configure how to display the table

        if "columns" in kwargs:
            # if we explicitly have columns as args, we explicitly construct a table state here and pass
            # it to JS to configure how the resulting panel should be displayed
            self._table_state = table_state.TableState(self.input_node)
            for column_expr in kwargs["columns"]:
                self.append_column(column_expr)

    @property
    def table_query(self):
        return self._table_state

    def append_column(self, expr, name=""):
        self._table_state.add_column(expr, name=name)

    @property
    def config(self):
        state = self._table_state.to_json() if self._table_state else self._table_state
        return {"tableState": state}
