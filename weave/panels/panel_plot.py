import dataclasses
import typing
import weave

from ..decorators import op
from .. import panel
from . import table_state

from .. import graph


@weave.type()
class PanelPlotDimsConfig:
    x: str
    y: str
    color: str
    label: str
    tooltip: str


@weave.type()
class AxisSettings:
    noLabels: bool = False
    noTitle: bool = False
    noTicks: bool = False
    title: str = None


@weave.type()
class PanelPlotAxisSettingsConfig:
    x: AxisSettings
    y: AxisSettings


@weave.type()
class LegendSettings:
    noLegend: bool = False


@weave.type()
class PanelPlotLegendSettingsConfig:
    color: LegendSettings


@weave.type()
class PanelPlotConfig:
    table: table_state.TableState
    dims: PanelPlotDimsConfig
    mark: str
    axisSettings: PanelPlotAxisSettingsConfig
    legendSettings: PanelPlotLegendSettingsConfig


@weave.type()
class Plot(panel.Panel):
    id = "plot"
    config: typing.Optional[PanelPlotConfig] = None

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            table = table_state.TableState(self.input_node)
            self.config = PanelPlotConfig(
                **{
                    "table": table,
                    "dims": PanelPlotDimsConfig(
                        x=table.add_column(lambda row: graph.VoidNode()),
                        y=table.add_column(lambda row: graph.VoidNode()),
                        color=table.add_column(lambda row: graph.VoidNode()),
                        label=table.add_column(lambda row: graph.VoidNode()),
                        tooltip=table.add_column(lambda row: graph.VoidNode()),
                    ),
                    "mark": None,
                    "axisSettings": PanelPlotAxisSettingsConfig(
                        x=AxisSettings(), y=AxisSettings()
                    ),
                    "legendSettings": PanelPlotLegendSettingsConfig(
                        color=LegendSettings()
                    ),
                }
            )

            # TODO is this correct?
            for k, v in options.items():
                method = getattr(self, "set_%s" % k, None)
                if method is None:
                    method = getattr(self, k)
                method(v)
            # if "x" in options:
            #     self.set_x(options["x"])

            # if "x_title" in options:
            #     self.config.axisSettings.x.title = options["x_title"]

            # if options.get("groupby_x"):
            #     self.groupby_x()

            # if "y" in options:
            #     self.set_y(options["y"])

            # if "y_title" in options:
            #     self.config.axisSettings.y.title = options["y_title"]

            # if options.get("groupby_y"):
            #     self.groupby_y()

            # if "label" in options:
            #     self.set_label(options["label"])

            # if options.get("groupby_label"):
            #     self.groupby_label(options["groupby_label"])

            # if "tooltip" in options:
            #     self.set_tooltip(options["tooltip"])

            # if options.get("no_axes"):
            #     self.set_no_axes()

            # if options.get("no_legend"):
            #     self.set_no_legend()

            # if options.get("mark"):
            #     self.set_mark(options["mark"])

    @property
    def table_query(self):
        return self._table_state

    # TODO: These should be settable properties. Would be very nice.
    def set_x(self, expr):
        self.config.table.update_col(self.config.dims.x, expr)

    def groupby_x(self, val):
        if not val:
            # TODO
            raise Exception("fix me")
        self.config.table.enable_groupby(self.config.dims.x)

    def set_y(self, expr):
        self.config.table.update_col(self.config.dims.y, expr)

    def groupby_y(self, val):
        if not val:
            # TODO
            raise Exception("wait fix")
        self.config.table.enable_groupby(self.config.dims.y)

    def set_label(self, expr):
        self.config.table.update_col(self.config.dims.label, expr)

    def groupby_label(self):
        self.config.table.enable_groupby(self.config.dims.color)
        self.config.table.enable_groupby(self.config.dims.label)

    def set_tooltip(self, expr):
        self.config.table.update_col(self.config.dims.tooltip, expr)

    def set_no_axes(self):
        self.config.axisSettings.x = AxisSettings(
            noLabels=True,
            noTitle=True,
            noTicks=True,
        )
        self.config.axisSettings.y = AxisSettings(
            noLabels=True,
            noTitle=True,
            noTicks=True,
        )

    def set_no_legend(self):
        self.config.legendSettings.color = LegendSettings(noLegend=True)

    def set_mark(self, mark_option):
        self.config.mark = mark_option
