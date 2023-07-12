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


EditorType = typing.TypeVar("EditorType")


@weave.type()
class QueryCondition:
    expression: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    editor: EditorType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class QueryConfig:
    tableState: table_state.TableState
    dims: QueryDimsConfig
    conditions: list[QueryCondition] = dataclasses.field(default_factory=list)
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
        if "conditions" in options:
            conds = [
                cond(weave_internal.make_var_node(self.input_node.type, "queryInput"))
                for cond in options["conditions"]
            ]
            self.config.conditions = conds

    @weave.op(hidden=True)
    def selected_refine(self) -> weave.types.Type:
        return self.input_node.type

    @weave.op(
        output_type=lambda inputs: inputs["self"].input_node.output_type,
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
        return table_node
