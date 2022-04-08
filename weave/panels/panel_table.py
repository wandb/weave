from .. import panel
from . import table_state


class Table(panel.Panel):
    id = "table"

    def __init__(self, *args):
        super().__init__(*args)
        self._table_state = table_state.TableState(self.input_node)

    @property
    def table_query(self):
        return self._table_state

    @property
    def config(self):
        return {"tableState": self._table_state.to_json()}
