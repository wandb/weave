import dataclasses
import typing

import weave
from weave import weave_internal
from .. import panel
from . import table_state


@weave.type("tablePanelConfig")
class TableConfig:
    tableState: table_state.TableState
    rowSize: int = dataclasses.field(default_factory=lambda: 1)


class ColumnDef(typing.TypedDict):
    columnName: str
    columnSelectFunction: weave.graph.Node


@weave.type("tablePanel")
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
                for col_ndx, column_expr in enumerate(options["columns"]):
                    table.add_column(column_expr)

    def get_final_named_select_functions(self) -> dict[str, ColumnDef]:
        if not self.config:
            return {}
        else:
            result = {}
            existing_names: typing.Set[str] = set()
            group_columns = self.config.tableState.groupBy
            use_order = group_columns + [
                key for key in self.config.tableState.order if key not in group_columns
            ]
            for internal_col_key in use_order:
                fn_node = self.config.tableState.columnSelectFunctions[internal_col_key]
                if fn_node.type != weave.types.Invalid():
                    name = self.config.tableState.columnNames[internal_col_key]
                    if name == "":
                        name = "c_" + str(len(existing_names))
                    added_suffix = 1
                    _name = name
                    while _name in result:
                        _name = f"{name}_{added_suffix}"
                        added_suffix += 1
                    name = _name

                    existing_names.add(name)
                    result[internal_col_key] = ColumnDef(
                        columnName=name,
                        columnSelectFunction=fn_node,
                    )
        return result


@weave.op(name="panel_table-columns_refine")
def columns_refine(self: Table) -> weave.types.Type:
    columns = self.get_final_named_select_functions()
    inner_type = weave.types.TypedDict(
        {
            col_def["columnName"]: col_def["columnSelectFunction"].type
            for col_def in columns.values()
        }
    )

    # Since we are executing the node, tags don't come out!
    # if self.config and self.config.tableState.groupBy:
    #     inner_type = tagged_value_type.TaggedValueType(weave.types.TypedDict({
    #         "groupKey": weave.types.TypedDict({
    #             columns[key]['columnName']: columns[key]["columnSelectFunction"].type
    #             for key in self.config.tableState.groupBy
    #         })
    #     }), inner_type)

    return weave.types.List(inner_type)


@weave.op(
    name="panel_table-columns",
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=columns_refine,
)
# TODO: should this be named rows?
def columns(self: Table):
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

    columns = self.get_final_named_select_functions()

    # Apply Grouping
    group_ids: typing.Set[str] = set()
    if self.config and self.config.tableState.groupBy:
        group_ids = set(self.config.tableState.groupBy)
        table_node = weave.ops.List.groupby(
            table_node,
            lambda row: weave.ops.dict_(
                **{
                    columns[col_id]["columnName"]: weave_internal.call_fn(
                        columns[col_id]["columnSelectFunction"], {"row": row}
                    )
                    for col_id in self.config.tableState.groupBy
                }
            ),
        )

    # Apply Selection
    table_node = weave.ops.List.map(
        table_node,
        lambda row: weave.ops.dict_(
            **{
                col_def["columnName"]: (
                    weave_internal.call_fn(
                        col_def["columnSelectFunction"], {"row": row}
                    )
                    if col_id not in group_ids
                    else
                    # Here, we materialize the groupkey tags as columns. This is nicer for downstream
                    # consumers, to be able to directly fetch the col by name, even if it
                    # was the grouping column. I (Tim) took this design liberty, easy to change.
                    row.groupkey()[col_def["columnName"]]
                )
                for col_id, col_def in columns.items()
            }
        ),
    )

    # Apply Sorting
    if self.config and self.config.tableState.sort:
        sort_defs = self.config.tableState.sort

        def make_sort_fn(sort_def, row_node):
            col_name = columns[sort_def["columnId"]]["columnName"]
            return row_node[col_name]
            # If we don't materialize the group column above, we need to do
            # something like this
            # if sort_def['columnId'] in group_ids:
            #     return row_node.groupkey()[col_name]
            # else:
            #     return row_node[col_name]

        table_node = weave.ops.List.sort(
            table_node,
            lambda row: weave.ops.make_list(
                **{
                    f"{sort_ndx}": make_sort_fn(sort_def, row)
                    for sort_ndx, sort_def in enumerate(sort_defs)
                }
            ),
            [sort_def["dir"] for sort_def in sort_defs],
        )

    return weave_internal.use(table_node)
