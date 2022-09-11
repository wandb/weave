from .. import panel
from . import table_state

from .. import graph


class Plot(panel.Panel):
    id = "plot"

    def __init__(self, input_node, **config):
        super().__init__(input_node)
        self._table_state = table_state.TableState(self.input_node)
        self._dims = {
            "x": self._table_state.add_column(lambda row: graph.VoidNode()),
            "y": self._table_state.add_column(lambda row: graph.VoidNode()),
            "color": self._table_state.add_column(lambda row: graph.VoidNode()),
            "label": self._table_state.add_column(lambda row: graph.VoidNode()),
            "tooltip": self._table_state.add_column(lambda row: graph.VoidNode()),
        }
        self._mark = None
        self._axis_settings = {
            "x": {},
            "y": {},
        }
        self._legend_settings = {}

        # TODO: handle all this stuff generically!
        if "x" in config:
            self.set_x(config["x"])

        if config.get("groupby_x"):
            self.groupby_x(config["groupby_x"])

        if "y" in config:
            self.set_y(config["y"])

        if config.get("groupby_y"):
            self.groupby_y(config["groupby_y"])

        if "label" in config:
            self.set_label(config["label"])

        if config.get("groupby_label"):
            self.groupby_label(config["groupby_label"])

        if "tooltip" in config:
            self.set_tooltip(config["tooltip"])

        if config.get("no_axes"):
            self.set_no_axes()

        if config.get("no_legend"):
            self.set_no_legend()

        if config.get("mark"):
            self.set_mark(config["mark"])

    @property
    def table_query(self):
        return self._table_state

    # TODO: These should be settable properties. Would be very nice.
    def set_x(self, expr):
        self._table_state.update_col(self._dims["x"], expr)

    def groupby_x(self):
        self._table_state.enable_groupby(self._dims["x"])

    def set_y(self, expr):
        self._table_state.update_col(self._dims["y"], expr)

    def groupby_y(self):
        self._table_state.enable_groupby(self._dims["y"])

    def set_label(self, expr):
        self._table_state.update_col(self._dims["label"], expr)

    def groupby_label(self):
        self._table_state.enable_groupby(self._dims["color"])

        self._table_state.enable_groupby(self._dims["label"])

    def set_tooltip(self, expr):
        self._table_state.update_col(self._dims["tooltip"], expr)

    def set_no_axes(self):
        self._axis_settings["x"] = {
            "noLabels": True,
            "noTitle": True,
            "noTicks": True,
        }
        self._axis_settings["y"] = {"noLabels": True, "noTitle": True, "noTicks": True}

    def set_no_legend(self):
        self._legend_settings["color"] = {"noLegend": True}

    def set_mark(self, mark_option):
        self._mark = mark_option

    @property
    def config(self):
        return {
            "table": self._table_state.to_json(),
            "dims": self._dims,
            "mark": self._mark,
            "axisSettings": self._axis_settings,
            "legendSettings": self._legend_settings,
        }
