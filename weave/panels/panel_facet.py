import typing
import weave
from .. import panel
from . import table_state

from .. import graph


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


@weave.type()
class FacetConfig:
    table: table_state.TableState
    dims: FacetDimsConfig
    cellSize: FacetCellSize
    padding: int


@weave.type()
class Facet(panel.Panel):
    id = "facet"
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
            )
            self.set_x(options["x"])
            self.set_y(options["y"])
            self.config.table.enable_groupby(self.config.dims.x)
            self.config.table.enable_groupby(self.config.dims.y)
            if "select" in options:
                self.set_select(options["select"])
            if "detail" in options:
                self.set_select(options["detail"])

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

    def set_select(self, expr):
        self.config.table.update_col(self.config.dims.select, expr)

    def set_detail(self, expr):
        self.config.table.update_col(self.config.dims.detail, expr)
