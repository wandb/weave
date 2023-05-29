import dataclasses
import typing

import weave
from weave import weave_internal
from .. import panel
from .. import graph
from . import table_state


@weave.type()
class QueryDimsConfig:
    text: str


@weave.type()
class QueryConfig:
    tableState: table_state.TableState
    dims: QueryDimsConfig
    pinnedRows: dict[str, list[int]] = dataclasses.field(default_factory=dict)


@weave.type()
class Query(panel.Panel):
    id = "Query"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[QueryConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            table = table_state.TableState(self.input_node)
            self.config = QueryConfig(
                tableState=table,
                dims=QueryDimsConfig(
                    text=table.add_column(lambda row: graph.VoidNode(), name="text"),
                ),
                pinnedRows={"": [0]},
            )
            self.set_text(options["text"])

    def set_text(self, expr):
        self.config.tableState.update_col(self.config.dims.text, expr)

    # @weave.op()
    # def selected_refine(self) -> weave.types.Type:
    #     return self.input_node.type

    # @weave.op(
    #     output_type=weave.types.List(weave.types.TypedDict({})),
    #     refine_output_type=selected_refine,
    # )
    # def selected(self):
    #     # What a shame we have to execute the table :(

    #     # Apply Filters
    #     table_node = self.input_node
    #     if (
    #         self.config
    #         and self.config.tableState.preFilterFunction is not None
    #         and self.config.tableState.preFilterFunction.type != weave.types.Invalid()
    #     ):
    #         table_node = weave.ops.List.filter(
    #             table_node,
    #             lambda row: weave_internal.call_fn(
    #                 self.config.tableState.preFilterFunction, {"row": row}
    #             ),
    #         )
    #     return weave_internal.use(table_node)
