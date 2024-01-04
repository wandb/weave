import dataclasses
import typing

import weave
from weave import weave_internal
from weave import codify
from weave import codifiable_value_mixin
from weave.graph import ConstNode, Node, OutputNode, VoidNode
from .. import panel
from . import table_state

from .panel_query import Query


@weave.type("tablePanelConfig")
class TableConfig:
    tableState: table_state.TableState
    rowSize: int = dataclasses.field(default_factory=lambda: 1)
    pinnedRows: dict[str, list[int]] = dataclasses.field(default_factory=dict)
    pinnedColumns: list[str] = dataclasses.field(default_factory=list)
    activeRowForGrouping: dict[str, int] = dataclasses.field(default_factory=dict)


class ColumnDef(typing.TypedDict):
    columnName: str
    columnSelectFunction: weave.graph.Node


@dataclasses.dataclass
class TableColumn:
    select: typing.Callable
    groupby: bool = dataclasses.field(default=False)
    name: str = dataclasses.field(default_factory=lambda: "")


@weave.type("tablePanel")
class Table(panel.Panel, codifiable_value_mixin.CodifiableValueMixin):
    id = "table"
    input_node: weave.Node[list[typing.Any]]
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
                    if isinstance(column_expr, TableColumn):
                        table.add_column(
                            column_expr.select,
                            column_expr.name,
                            groupby=column_expr.groupby,
                        )
                    else:
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

    def to_code(self) -> typing.Optional[str]:
        field_vals: list[tuple[str, str]] = []
        if self.config is not None:
            ts = self.config.tableState
            if ts.autoColumns:
                return None
            if not isinstance(ts.preFilterFunction, VoidNode):
                return None
            if ts.groupBy != []:
                return None
            if ts.sort != []:
                return None

            default_column_panel_def = table_state.PanelDef("", {}, None)
            default_column_panel_def_as_dict = {
                "panelId": "",
                "panelConfig": None,
                "originalKey": "",
            }

            code_cols = []
            for col_id in ts.order:
                if ts.columnNames[col_id] != "":
                    return None
                if (
                    ts.columns[col_id] != default_column_panel_def
                    and ts.columns[col_id] != default_column_panel_def_as_dict
                ):
                    return None
                code_cols.append(
                    codify.lambda_wrapped_object_to_code_no_format(
                        ts.columnSelectFunctions[col_id], ["row"]
                    )
                )
            if len(code_cols) > 0:
                field_vals.append(("columns", "[" + ",".join(code_cols) + ",]"))

        param_str = ""
        if len(field_vals) > 0:
            param_str = (
                ",".join([f_name + "=" + f_val for f_name, f_val in field_vals]) + ","
            )
        return f"""weave.panels.panel_table.Table({codify.object_to_code_no_format(self.input_node)}, {param_str})"""

    def add_column(
        self,
        select_expr: typing.Callable,
        name: typing.Optional[str] = None,
        groupby: bool = False,
        sort_dir: typing.Optional[str] = None,
        panel_def: typing.Union[table_state.PanelDef, None, str] = None,
    ) -> str:
        config = typing.cast(TableConfig, self.config)
        if isinstance(panel_def, str):
            panel_def = table_state.PanelDef(panel_def)
        return config.tableState.add_column(
            select_expr,
            name,
            groupby=groupby,
            sort_dir=sort_dir,
            panel_def=panel_def,
        )

    def enable_sort(self, col_id: str, dir: typing.Optional[str] = "asc") -> None:
        config = typing.cast(TableConfig, self.config)
        config.tableState.enable_sort(col_id, dir=dir)


def _get_composite_group_key(self: typing.Union[Table, Query]) -> str:
    if self.config is None:
        return ""
    group_by_keys = self.config.tableState.groupBy
    group_by_keys = group_by_keys or []
    return ",".join(group_by_keys)


# TODO: preserve arrow
def _get_pinned_node(self: typing.Union[Table, Query], data_or_rows_node: Node) -> Node:
    if self.config is None:
        return weave.ops.make_list()

    composite_group_key = _get_composite_group_key(self)
    pinned_data = self.config.pinnedRows.get(composite_group_key)
    if pinned_data is None or len(pinned_data) == 0:
        return weave.ops.make_list()

    return weave.ops.make_list(
        **{
            f"v_{pin_ndx}": OutputNode(
                data_or_rows_node.type,
                "index",
                {
                    "arr": data_or_rows_node,
                    "index": ConstNode(weave.types.Int(), row_ndx),
                },
            )
            for pin_ndx, row_ndx in enumerate(pinned_data)
        }
    )


def _get_active_node(self: Table, data_or_rows_node: Node) -> Node:
    composite_group_key = _get_composite_group_key(self)
    if self.config is None or self.config.activeRowForGrouping is None:
        active_index = 0
    else:
        active_index = self.config.activeRowForGrouping.get(composite_group_key, 0)

    return OutputNode(
        data_or_rows_node.type,
        "list-__getitem__",
        {
            "arr": data_or_rows_node,
            "index": ConstNode(weave.types.Int(), active_index),
        },
    )


# TODO: preserve arrow for empty list
def _get_rows_node(self: Table, apply_sort: bool = True) -> Node:
    # Apply Filters
    data_node = self.input_node
    if (
        self.config
        and self.config.tableState.preFilterFunction is not None
        and self.config.tableState.preFilterFunction.type != weave.types.Invalid()
    ):
        data_node = weave.ops.List.filter(
            data_node,
            lambda row, index: weave_internal.call_fn(
                self.config.tableState.preFilterFunction, {"row": row, "index": index}
            ),
        )

    columns = self.get_final_named_select_functions()

    # Apply Grouping
    group_ids: typing.Set[str] = set()
    if self.config and self.config.tableState.groupBy:
        group_ids = set(self.config.tableState.groupBy)
        data_node = weave.ops.List.groupby(
            data_node,
            lambda row: weave.ops.dict_(
                **{
                    columns[col_id]["columnName"]: weave_internal.call_fn(
                        columns[col_id]["columnSelectFunction"],
                        {
                            "row": row,
                        },
                    )
                    for col_id in self.config.tableState.groupBy
                }
            ),
        )

    # Apply Selection
    data_node = weave.ops.List.map(
        data_node,
        lambda row, index: weave.ops.dict_(
            **{
                col_def["columnName"]: (
                    weave_internal.call_fn(
                        col_def["columnSelectFunction"], {"row": row, "index": index}
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
    if self.config and self.config.tableState.sort and apply_sort:
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

        data_node = weave.ops.List.sort(
            data_node,
            lambda row: weave.ops.make_list(
                **{
                    f"{sort_ndx}": make_sort_fn(sort_def, row)
                    for sort_ndx, sort_def in enumerate(sort_defs)
                }
            ),
            [sort_def["dir"] for sort_def in sort_defs],
        )

    return data_node


def _get_row_type(self: Table) -> weave.types.Type:
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

    return inner_type


# TODO: preserve arrow
@weave.op(name="panel_table-rows_refine", hidden=True)
def rows_refine(self: Table) -> weave.types.Type:
    return weave.types.List(_get_row_type(self))


@weave.op(name="panel_table-rows_single_refine", hidden=True)
def rows_single_refine(self: Table) -> weave.types.Type:
    return weave.types.optional(_get_row_type(self))


# TODO: preserve arrow
@weave.op(name="panel_table-data_refine", hidden=True)
def data_refine(self: Table) -> weave.types.Type:
    object_type = (
        self.input_node.type.object_type
        if hasattr(self.input_node.type, "object_type")
        else weave.types.Any()
    )
    return weave.types.List(object_type)


@weave.op(name="panel_table-data_single_refine", hidden=True)
def data_single_refine(self: Table) -> weave.types.Type:
    self_input_node_type = self.input_node.type
    # TODO: not sure why I need to defunction the type in the panel
    # construction case, but not when this is called from JS
    if isinstance(self_input_node_type, weave.types.Function):
        self_input_node_type = self_input_node_type.output_type
    if not hasattr(self_input_node_type, "object_type"):
        return weave.types.Any()
    # input_node.type should be FunctionType (since its a Node)
    # but for some reason its not.
    # TODO: fix
    return weave.types.optional(self_input_node_type.object_type)  # type: ignore


# TODO: keep type in arrow
@weave.op(
    name="panel_table-all_rows",
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=rows_refine,
)
def rows(self: Table):
    rows_node = _get_rows_node(self)
    return rows_node


# Defined on both Table and Query
@weave.op(
    name="panel_table-pinned_data",
    # we define output_type for pyton and refine_output_type for JS
    output_type=lambda inputs: inputs["self"].input_node.output_type,
    refine_output_type=data_refine,
)
def pinned_data(self: typing.Union[Table, Query]):
    pinned_data_node = _get_pinned_node(self, self.input_node)
    return weave.use(pinned_data_node)


# TODO: preserve arrow
@weave.op(
    name="panel_table-pinned_rows",
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=rows_refine,
)
def pinned_rows(self: Table):
    # _get_active_node uses an "activeRowForGrouping" which is relative to the unsorted table.
    # for the index to be correct, we need to use the unsorted table.
    rows_node = _get_rows_node(self, apply_sort=False)
    pinned_data_node = _get_pinned_node(self, rows_node)
    return weave.use(pinned_data_node)


@weave.op(
    name="panel_table-active_data",
    # We can't use the refine_output_type here, because it will become
    # non-weavifiable and not sent over the wire.
    # output_type=lambda inputs: inputs['self'].input_node.output_type.object_type,
    refine_output_type=data_single_refine,
)
def active_data(self: Table) -> typing.Optional[dict]:
    data_node = _get_active_node(self, self.input_node)
    return data_node  # type: ignore


@weave.op(
    name="panel_table-active_row",
    output_type=weave.types.optional(weave.types.TypedDict({})),
    refine_output_type=rows_single_refine,
)
def active_row(self: Table):
    # _get_active_node uses an "activeRowForGrouping" which is relative to the unsorted table.
    # for the index to be correct, we need to use the unsorted table.
    rows_node = _get_rows_node(self, apply_sort=False)
    data_node = _get_active_node(self, rows_node)
    return data_node
