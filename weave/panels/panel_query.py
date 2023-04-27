import dataclasses
import typing

import weave
from weave import weave_internal
from .. import panel
from . import table_state


@weave.type()
class QueryConfig:
    tableState: table_state.TableState


@weave.type()
class Query(panel.Panel):
    id = "Query"
    config: typing.Optional[QueryConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            table = table_state.TableState(self.input_node)
            self.config = QueryConfig(table)

            if "columns" in options:
                for col_ndx, column_expr in enumerate(options["columns"]):
                    table.add_column(column_expr)

    @weave.op()
    def selected_refine(self) -> weave.types.Type:
        return self.input_node.type

    @weave.op(
        output_type=weave.types.List(weave.types.TypedDict({})),
        refine_output_type=selected_refine,
    )
    def selected(self):
        # What a shame we have to execute the table :(

        # Apply Filters
        table_node = self.input_node
        if (
            self.config
            and self.config.tableState.preFilterFunction is not None
            and self.config.tableState.preFilterFunction.type != weave.types.Invalid()
        ):
            table_node = weave.ops.List.filter(
                table_node,
                lambda row: weave_internal.call_fn(
                    self.config.tableState.preFilterFunction, {"row": row}
                ),
            )
        return weave_internal.use(table_node)
