from .. import panel
from . import table_state

from .. import graph


class Plot(panel.Panel):
    id = "plot"

    def __init__(self, *args):
        super().__init__(*args)
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

    @property
    def table_query(self):
        return self._table_state

    def set_x(self, expr):
        self._table_state.update_col(self._dims["x"], expr)

    def set_y(self, expr):
        self._table_state.update_col(self._dims["y"], expr)

    def set_no_axes(self):
        self._axis_settings["x"] = {
            "noLabels": True,
            "noTitle": True,
            "noTicks": True,
        }
        self._axis_settings["y"] = {"noLabels": True, "noTitle": True, "noTicks": True}

    def set_x_domain_range(self, min, max):
        self._axis_settings["x"]["scale"] = {"domainMin": min, "domainMax": max}

    def set_y_domain(self, domain):
        self._axis_settings["y"]["scale"] = {"domain": domain}

    def set_no_legend(self):
        self._legend_settings["color"] = {"noLegend": True}

    def set_label(self, expr):
        self._table_state.update_col(self._dims["label"], expr)

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
