import dataclasses
import typing

import weave
from .. import panel
from . import table_state


@weave.type()
class TableConfig:
    tableState: table_state.TableState
    rowSize: int = dataclasses.field(default_factory=lambda: 1)


@weave.type()
class Table(panel.Panel):
    id = "table"
    config: typing.Optional[TableConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            table = table_state.TableState(self.input_node)
            self.config = TableConfig(table)

            if "columns" in options:
                for column_expr in options["columns"]:
                    table.add_column(column_expr)
