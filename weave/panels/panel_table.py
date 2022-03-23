from .. import panel
from . import table_state


class Table(panel.Panel):
    def __init__(self, input_node):
        self.id = "table"
        self.input_node = input_node
        self._table_state = table_state.TableState()

    @property
    def table_query(self):
        return self._table_state

    @property
    def config(self):
        return {"tableState": self._table_state.to_json()}
