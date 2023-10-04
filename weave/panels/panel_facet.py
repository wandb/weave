import dataclasses
import typing
import weave
from .. import panel
from . import table_state

from .. import weave_types as types
from .. import graph
from .. import weave_internal


@weave.type()
class FacetDimsConfig:
    x: str
    y: str
    select: str
    detail: str


@weave.type()
class FacetCellSize:
    w: int
    h: int


class FacetCell(typing.TypedDict):
    x: str
    y: str


@weave.type()
class FacetConfig:
    table: table_state.TableState
    dims: FacetDimsConfig
    cellSize: FacetCellSize
    padding: int
    selectedCell: typing.Optional[FacetCell] = dataclasses.field(
        default_factory=lambda: None
    )
    xAxisLabel: weave.Node[str] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    yAxisLabel: weave.Node[str] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )


@weave.type()
class Facet(panel.Panel):
    id = "Facet"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[FacetConfig] = None

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            table = table_state.TableState(self.input_node)
            self.config = FacetConfig(
                table=table,
                dims=FacetDimsConfig(
                    x=table.add_column(lambda row: graph.VoidNode()),
                    y=table.add_column(lambda row: graph.VoidNode()),
                    select=table.add_column(lambda row: graph.VoidNode()),
                    detail=table.add_column(lambda row: graph.VoidNode()),
                ),
                cellSize=FacetCellSize(w=50, h=50),
                padding=0,
                selectedCell=None,
                xAxisLabel=graph.VoidNode(),
                yAxisLabel=graph.VoidNode(),
            )
            self.set_x(options["x"])
            self.set_y(options["y"])
            self.config.table.enable_groupby(self.config.dims.x)
            self.config.table.enable_groupby(self.config.dims.y)
            if "select" in options:
                self.set_select(options["select"])
            if "detail" in options:
                self.set_detail(options["detail"])
            if "cell_size" in options:
                self.set_cell_size(*options["cell_size"])

    def debug_dim_select_functions(self):
        for dim in ["x", "y", "select", "detail"]:
            print(
                dim,
                self.config.table.columnSelectFunctions[
                    getattr(self.config.dims, dim)
                ].__repr__(),
            )

    def set_x(self, expr):
        self.config.table.update_col(self.config.dims.x, expr)

    def set_y(self, expr):
        self.config.table.update_col(self.config.dims.y, expr)

    def set_cell_size(self, w, h):
        self.config.cellSize = FacetCellSize(w=w, h=h)

    def set_select(self, expr):
        self.config.table.update_col(self.config.dims.select, expr)

    def set_detail(self, expr):
        self.config.table.update_col(self.config.dims.detail, expr)

    @weave.op(output_type=lambda input_type: input_type["self"].input_node.output_type)
    def selected(self):
        if self.config.selectedCell == None:
            from ..ops_arrow import list_

            return weave_internal.make_const_node(
                list_.ArrowWeaveListType(types.NoneType()), list_.make_vec_none(0)
            )
        x_fn = self.config.table.columnSelectFunctions[self.config.dims.x]
        y_fn = self.config.table.columnSelectFunctions[self.config.dims.y]
        filtered = weave.ops.List.filter(
            self.input_node,
            lambda item: weave.ops.Boolean.bool_and(
                weave.ops.String.__eq__(
                    x_fn,
                    self.config.selectedCell["x"],
                ),
                weave.ops.String.__eq__(
                    y_fn,
                    self.config.selectedCell["y"],
                ),
            ),
        )

        return filtered
