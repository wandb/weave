import typing

from .. import panel
from . import table_state


class Table(panel.Panel):
    id = "table"
    _table_state: typing.Optional[table_state.TableState]

    def _set_default_nonauto_tablestate(self):
        self._table_state = table_state.TableState(self.input_node)

    def __init__(self, input_node, **kwargs):
        super().__init__(input_node)
        # None instructs JS to automatically configure how to display the table
        self._table_state = None

        if "columns" in kwargs:
            # if we explicitly have columns as args, we explicitly construct
            # a table state here and pass it to JS to configure how the resulting
            # panel should be displayed
            self._set_default_nonauto_tablestate()
            for column_expr in kwargs["columns"]:
                self.append_column(column_expr)


@weave.type()
class Table(panel.Panel):
    id = "table"
    config: typing.Optional[TableConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def append_column(self, expr, name=""):
        if self._table_state is None:
            self._set_default_nonauto_tablestate()
        self._table_state.add_column(expr, name=name)

    @property
    def config(self):
        state = self._table_state.to_json() if self._table_state else self._table_state
        return {"tableState": state}
