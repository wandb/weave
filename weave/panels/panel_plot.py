# TODO: types are all messed up after panel_composition branch
import copy
import typing
import weave
from weave import codifiable_value_mixin
from weave import codify

from .. import panel
from . import table_state
from . import panel_table
import dataclasses

from .. import graph
from .. import errors
from .. import weave_internal
from .. import weave_types as types
from ..ops_primitives import list_, dict as dict_, boolean


@weave.type()
class DimConfig:
    x: str
    y: str
    color: str
    label: str
    tooltip: str
    pointSize: str
    pointShape: str
    y2: str


DimName = typing.Literal[
    "x",
    "y",
    "color",
    "label",
    "tooltip",
    "pointSize",
    "pointShape",
    "y2",
]
MarkOption = typing.Optional[typing.Literal["area", "line", "point", "bar", "boxplot"]]
PointShapeOption = typing.Literal[
    "series",
    "circle",
    "square",
    "cross",
    "diamond",
    "triangle-up",
    "triangle-down",
    "triangle-right",
    "triangle-left",
]

LabelOption = typing.Literal["series"]
LineStyleOption = typing.Literal[
    "solid",
    "dashed",
    "dotted",
    "dot-dashed",
    "short-dashed",
    "series",
]

SelectFunction = typing.Union[graph.Node, typing.Callable[[typing.Any], typing.Any]]


@weave.type()
class PlotConstants:
    mark: MarkOption
    pointShape: PointShapeOption
    label: LabelOption
    lineStyle: LineStyleOption

    def __init__(self, **kwargs):
        # set defaults
        self.mark = kwargs.get("mark", None)
        self.pointShape = kwargs.get("pointShape", "circle")
        self.label = kwargs.get("label", "series")
        self.lineStyle = kwargs.get("lineStyle", "solid")


class PlotConstantsInputDict(typing.TypedDict):
    # TODO(DG): replace these typing.Optionals with typing.NotRequired (https://peps.python.org/pep-0655/#usage-in-python-3-11)
    # when we drop support for Python 3.10 and python 3.11 is released

    # this will mimic the behavior of ? in typescript
    mark: typing.Optional[MarkOption]
    pointShape: typing.Optional[PointShapeOption]
    label: typing.Optional[LabelOption]
    lineStyle: typing.Optional[LineStyleOption]


DropdownWithExpressionMode = typing.Union[
    typing.Literal["dropdown"], typing.Literal["expression"]
]


@weave.type()
class PlotUIState:
    pointShape: DropdownWithExpressionMode
    label: DropdownWithExpressionMode


def default_axis():
    return AxisSetting(noLabels=False, noTitle=False, noTicks=False, scale=None)


@weave.type()
class Series:
    table: table_state.TableState
    dims: DimConfig
    constants: PlotConstants
    uiState: PlotUIState

    @property
    def y_expr_str(self):
        y_col_id = self.dims.y
        y_fn = self.table.columnSelectFunctions[y_col_id]
        if isinstance(y_fn, graph.Node):
            return graph.node_expr_str(y_fn)
        return None

    def clone(self):
        series = Series.__new__(Series)
        for attr in ["table", "dims", "constants", "uiState"]:
            value = getattr(self, attr)
            if hasattr(value, "clone"):
                setattr(series, attr, value.clone())
            else:
                setattr(series, attr, copy.deepcopy(value))
        return series

    def __init__(
        self,
        input_node: typing.Optional[graph.Node] = None,
        table: typing.Optional[table_state.TableState] = None,
        dims: typing.Optional[DimConfig] = None,
        constants: typing.Optional[PlotConstants] = None,
        select_functions: typing.Optional[typing.Dict[DimName, SelectFunction]] = None,
    ):
        if input_node is not None:
            table = table_state.TableState(input_node)
        if table is None:
            raise ValueError("table missing")

        if dims is None:
            _dims = {}
            for dim in dataclasses.fields(DimConfig):
                _dims[dim.name] = table.add_column(lambda row: graph.VoidNode())
            dims = DimConfig(**_dims)
        if constants is None:
            constants = PlotConstants()

        if select_functions:
            for dimname in select_functions:
                table.update_col(getattr(dims, dimname), select_functions[dimname])

        uiState = PlotUIState(pointShape="expression", label="expression")

        self.table = table
        self.dims = dims
        self.constants = constants
        self.uiState = uiState

    @classmethod
    def from_config(cls, **config) -> "Series":
        series = Series.__new__(Series)
        for attr in ["table", "dims", "constants", "uiState"]:
            value = config.get(attr, None)
            if value is None:
                raise ValueError(
                    f'Config must contain "{attr}" to initialize new series.'
                )
            setattr(series, attr, value)
        return series

    @property
    def table_query(self):
        return self.table


def make_set(dim_name: str) -> typing.Callable[[Series, typing.Any], None]:
    def set(self: Series, expr) -> None:
        col_id: str = getattr(self.dims, dim_name)
        self.table.update_col(col_id, expr)

    return set


def make_group(dim_name: str) -> typing.Callable[[Series], None]:
    def group(self: Series) -> None:
        col_id: str = getattr(self.dims, dim_name)
        self.table.enable_groupby(col_id)

    return group


def make_get(dim_name: str) -> typing.Callable[[Series], graph.Node]:
    def get(self: Series) -> graph.Node:
        col_id: str = getattr(self.dims, dim_name)
        return self.table.columnSelectFunctions[col_id]

    return get


def make_set_constant(
    const_name: str,
) -> typing.Callable[[Series, typing.Any], None]:
    def set(self: Series, value) -> None:
        setattr(self.constants, const_name, value)

    return set


def make_get_constant(const_name: str) -> typing.Callable[[Series], typing.Any]:
    def get(self: Series) -> typing.Any:
        return getattr(self.constants, const_name)

    return get


# install setters and groupers
for dim in dataclasses.fields(DimConfig):
    setattr(Series, f"set_{dim.name}", make_set(dim.name))
    setattr(Series, f"groupby_{dim.name}", make_group(dim.name))
    setattr(Series, f"get_{dim.name}", make_get(dim.name))

for dim in dataclasses.fields(PlotConstants):
    setattr(Series, f"set_{dim.name}_constant", make_set_constant(dim.name))
    setattr(Series, f"get_{dim.name}_constant", make_get_constant(dim.name))


ScaleType = typing.Literal["linear", "log"]


@weave.type()
class Scale:
    type: typing.Optional[ScaleType]
    range: typing.Optional[dict[typing.Literal["field"], typing.Callable[[str], str]]]
    base: typing.Optional[float]  # for log scale


@weave.type()
class AxisSetting:
    noLabels: bool
    noTitle: bool
    noTicks: bool
    scale: typing.Optional[Scale] = None


@weave.type()
class AxisSettings:
    x: AxisSetting
    y: AxisSetting
    color: AxisSetting
    # todo: figure out how to reproduce [key: string]: LegendSetting in python type system


@weave.type()
class LegendSetting:
    noLegend: bool = False


@weave.type()
class LegendSettings:
    x: LegendSetting
    y: LegendSetting
    color: LegendSetting


@weave.type()
class ConfigOptionsExpanded:
    x: bool = False
    y: bool = False
    label: bool = False
    tooltip: bool = False
    mark: bool = False


DiscreteSelection = typing.List[str]
ContinuousSelection = typing.Tuple[float, float]
Selection = typing.Optional[typing.Union[ContinuousSelection, DiscreteSelection]]


@weave.type()
class AxisSelections:
    x: typing.Optional[Selection] = None
    y: typing.Optional[Selection] = None


@weave.type()
class Signals:
    domain: AxisSelections
    selection: AxisSelections


@weave.type("plotConfig")
class PlotConfig:
    series: typing.List[Series]
    axisSettings: typing.Optional[AxisSettings]
    legendSettings: typing.Optional[LegendSettings]
    configOptionsExpanded: typing.Optional[ConfigOptionsExpanded]
    signals: Signals
    configVersion: int = 11


@weave.type("plot")
class Plot(panel.Panel, codifiable_value_mixin.CodifiableValueMixin):
    id = "plot"
    config: typing.Optional[PlotConfig] = None

    def __init__(
        self,
        input_node=None,
        vars=None,
        config: typing.Optional[PlotConfig] = None,
        constants: typing.Optional[PlotConstants] = None,
        mark: typing.Optional[MarkOption] = None,
        x: typing.Optional[SelectFunction] = None,
        y: typing.Optional[SelectFunction] = None,
        color: typing.Optional[SelectFunction] = None,
        label: typing.Optional[SelectFunction] = None,
        tooltip: typing.Optional[SelectFunction] = None,
        pointShape: typing.Optional[SelectFunction] = None,
        lineStyle: typing.Optional[SelectFunction] = None,
        y2: typing.Optional[SelectFunction] = None,
        series: typing.Optional[typing.Union[Series, typing.List[Series]]] = None,
        no_axes: bool = False,
        no_legend: bool = False,
        signals: typing.Optional[Signals] = None,
    ):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config

        if self.config is None:
            if mark is not None:
                constants = PlotConstants(mark=mark)
            else:
                constants = PlotConstants()

            select_functions: typing.Optional[dict[DimName, SelectFunction]] = None
            for field, maybe_dim in zip(
                dataclasses.fields(DimConfig),
                [x, y, color, label, tooltip, pointShape, lineStyle, y2],
            ):
                if maybe_dim is not None:
                    if select_functions is None:
                        select_functions = {}
                    select_functions[typing.cast(DimName, field.name)] = maybe_dim

            if not (
                (series is not None)
                ^ (select_functions is not None or input_node is not None)
            ):
                raise ValueError(
                    "Must provide either series or input_node/select_functions/constants, but not both"
                )

            config_series: typing.List[Series]
            if series is not None:
                if isinstance(series, Series):
                    config_series = [series]
                else:
                    config_series = series
            else:
                config_series = [
                    Series(
                        typing.cast(graph.Node, self.input_node),
                        constants=constants,
                        select_functions=select_functions,
                    )
                ]

            config_axisSettings = AxisSettings(
                x=default_axis(), y=default_axis(), color=default_axis()
            )

            config_legendSettings = LegendSettings(
                x=LegendSetting(), y=LegendSetting(), color=LegendSetting()
            )

            if signals is None:
                signals = Signals(
                    domain=AxisSelections(x=None, y=None),
                    selection=AxisSelections(x=None, y=None),
                )

            self.config = PlotConfig(
                series=config_series,
                axisSettings=config_axisSettings,
                legendSettings=config_legendSettings,
                configOptionsExpanded=ConfigOptionsExpanded(),
                signals=signals,
            )

            if no_axes:
                self.set_no_axes()

            if no_legend:
                self.set_no_legend()
        else:
            if self.config.series:
                for series in self.config.series:
                    series.table.input_node = self.input_node

    def add_series(self, series: Series):
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        self.config.series.append(series)

    def set_no_axes(self):
        if self.config is None:
            raise errors.WeaveInternalError("config is None")

        if self.config.axisSettings is None:
            self.config.axisSettings = AxisSettings(
                x=default_axis(), y=default_axis(), color=default_axis()
            )

        self.config.axisSettings.x = AxisSetting(
            noLabels=True,
            noTitle=True,
            noTicks=True,
            scale=None,
        )
        self.config.axisSettings.y = AxisSetting(
            noLabels=True,
            noTitle=True,
            noTicks=True,
            scale=None,
        )

    def set_no_legend(self):
        if self.config is None:
            raise errors.WeaveInternalError("config is None")

        self.config.legendSettings = LegendSettings(
            x=LegendSetting(True), y=LegendSetting(True), color=LegendSetting(True)
        )

    def to_code(self) -> typing.Optional[str]:
        field_vals: list[tuple[str, str]] = []
        default_signals = Signals(
            domain=AxisSelections(x=None, y=None),
            selection=AxisSelections(x=None, y=None),
        )
        default_axisSettings = AxisSettings(
            x=default_axis(), y=default_axis(), color=default_axis()
        )

        default_legendSettings = LegendSettings(
            x=LegendSetting(), y=LegendSetting(), color=LegendSetting()
        )
        default_configOptionsExpanded = ConfigOptionsExpanded()

        # These are total hacks and should be removed once we have a proper way
        # to ensure UI produces the correct types
        default_axisSettings_asDict: dict = {"x": {}, "y": {}, "color": {}}
        default_legendSettings_asDict: dict = {"color": {}}
        default_configOptionsExpanded_asDict: dict = {
            "x": False,
            "y": False,
            "label": False,
            "tooltip": False,
            "mark": False,
        }

        if self.config is not None:
            if self.config.signals != default_signals:
                return None
            if (
                self.config.axisSettings != default_axisSettings
                and self.config.axisSettings != default_axisSettings_asDict
            ):
                return None
            if (
                self.config.legendSettings != default_legendSettings
                and self.config.legendSettings != default_legendSettings_asDict
            ):
                return None
            if (
                self.config.configOptionsExpanded != default_configOptionsExpanded
                and self.config.configOptionsExpanded
                != default_configOptionsExpanded_asDict
            ):
                return None
            if len(self.config.series) != 1:
                return None

            # At this point we can turn the series into the params
            series = self.config.series[0]
            mark = series.constants.mark
            if mark != None:
                field_vals.append(("mark", codify.object_to_code_no_format(mark)))
            for dim_name in [
                "color",
                "label",
                "pointShape",
                "tooltip",
                "x",
                "y",
                "y2",
            ]:
                table_col_id = getattr(series.dims, dim_name)
                sel_fn = series.table.columnSelectFunctions[table_col_id]
                if not isinstance(sel_fn, graph.VoidNode):
                    field_vals.append(
                        (
                            dim_name,
                            codify.lambda_wrapped_object_to_code_no_format(
                                sel_fn, ["row"]
                            ),
                        )
                    )

        param_str = ""
        if len(field_vals) > 0:
            param_str = (
                ",".join([f_name + "=" + f_val for f_name, f_val in field_vals]) + ","
            )
        return f"""weave.panels.panel_plot.Plot({codify.object_to_code_no_format(self.input_node)}, {param_str})"""


def make_set_all_series(dim_name: str) -> typing.Callable[[Plot, typing.Any], None]:
    def set(self: Plot, expr) -> None:
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        for series in self.config.series:
            setter = getattr(series, f"set_{dim_name}")
            setter(expr)

    return set


def make_group_all_series(dim_name: str) -> typing.Callable[[Plot], None]:
    def group(self: Plot) -> None:
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        for series in self.config.series:
            grouper = getattr(series, f"groupby_{dim_name}")
            grouper()

    return group


def make_get_all_series(
    dim_name: str,
) -> typing.Callable[[Plot], typing.List[graph.Node]]:
    def get(self: Plot) -> typing.List[graph.Node]:
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        dim_select_functions: typing.List[graph.Node] = []
        for series in self.config.series:
            getter = getattr(series, f"get_{dim_name}")
            dim_select_functions.append(getter())
        return dim_select_functions

    return get


def make_set_constant_all_series(
    const_name: str,
) -> typing.Callable[[Plot, typing.Any], None]:
    def set(self: Plot, value) -> None:
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        for series in self.config.series:
            setter = getattr(series, f"set_{const_name}_constant")
            setter(value)

    return set


def make_get_constant_all_series(
    const_name: str,
) -> typing.Callable[[Plot], typing.List[typing.Any]]:
    constants: typing.List[typing.Any] = []

    def get(self: Plot) -> typing.List[typing.Any]:
        if self.config is None:
            raise errors.WeaveInternalError("config is None")
        for series in self.config.series:
            getter = getattr(series, f"get_{const_name}_constant")
            constants.append(getter())
        return constants

    return get


# install setters and groupers
for dim in dataclasses.fields(DimConfig):
    setattr(Plot, f"set_{dim.name}", make_set_all_series(dim.name))
    setattr(Plot, f"groupby_{dim.name}", make_group_all_series(dim.name))
    setattr(Plot, f"get_{dim.name}", make_get_all_series(dim.name))

for dim in dataclasses.fields(PlotConstants):
    setattr(Plot, f"set_{dim.name}_constant", make_set_constant_all_series(dim.name))
    setattr(Plot, f"get_{dim.name}_constant", make_get_constant_all_series(dim.name))


def selection_is_continuous(selection: Selection) -> bool:
    return (
        isinstance(selection, (tuple, list))
        and len(selection) == 2
        and all(isinstance(i, (int, float)) for i in selection)
    )


def selection_is_discrete(selection: Selection) -> bool:
    return not selection_is_continuous(selection)


# TODO: keep in arrow
def filter_node_to_selection(
    node: graph.Node, selection: Selection, key: str
) -> graph.Node:
    if selection_is_continuous(selection):
        selection = typing.cast(ContinuousSelection, selection)

        def predicate(row: graph.Node[types.TypedDict]):
            target = dict_.TypedDict.pick(row, key)
            return boolean.Boolean.bool_and(
                target >= selection[0], target <= selection[1]  # type: ignore
            )

    else:

        def predicate(row: graph.Node[types.TypedDict]):
            target = dict_.TypedDict.pick(row, key)
            return list_.contains(selection, target)

    node_type = typing.cast(
        types.List,
        node.type,
    )

    filter = weave_internal.define_fn({"row": node_type.object_type}, predicate)
    return list_.List.filter(node, filter)


# TODO: keep in arrow
def _get_rows_selected_node(plot: Plot) -> graph.Node:
    if plot.config is None:
        raise errors.WeaveInternalError("config is None")

    selection = plot.config.signals.selection

    table_nodes: typing.List[graph.Node[types.List]] = []
    for series in plot.config.series:
        table_config = panel_table.TableConfig(tableState=series.table)
        table_panel = panel_table.Table(plot.input_node, config=table_config)
        node = list_.unnest(panel_table.rows(table_panel))
        columns = table_panel.get_final_named_select_functions()

        if selection.x is None and selection.y is None:
            # nothing selected
            table_nodes.append(list_.make_list())
            continue

        if selection.x is not None:
            col_id = series.dims.x
            col = columns.get(col_id, None)
            if col is not None:
                key = col["columnName"]
                node = filter_node_to_selection(node, selection.x, key)

        if selection.y is not None:
            col_id = series.dims.y
            col = columns.get(col_id, None)
            if col is not None:
                key = col["columnName"]
                node = filter_node_to_selection(node, selection.y, key)

        if len(plot.config.series) > 1:

            def merge_func(row: graph.Node[types.TypedDict]):
                return dict_.TypedDict.merge(
                    row, dict_.dict_(y_expr_str=series.y_expr_str)
                )

            func = weave_internal.define_fn({"row": node.type.object_type}, merge_func)
            node = list_.List.map(node, func)

        table_nodes.append(node)

    node_list = list_.make_list(
        **{str(i): node for (i, node) in enumerate(table_nodes)}
    )
    concatted = list_.List.concat(node_list)
    return concatted


# TODO: keep in arrow
def _get_selected_data_node(plot: Plot) -> graph.Node:
    if plot.config is None:
        raise errors.WeaveInternalError("config is None")

    selection = plot.config.signals.selection

    table_nodes: typing.List[graph.Node[types.List]] = []
    for series in plot.config.series:
        table_config = panel_table.TableConfig(tableState=series.table)
        table_config.tableState.add_column(lambda row: row, "row")
        table_panel = panel_table.Table(plot.input_node, config=table_config)
        node = list_.unnest(panel_table.rows(table_panel))
        columns = table_panel.get_final_named_select_functions()

        if selection.x is None and selection.y is None:
            # nothing selected
            table_nodes.append(list_.make_list())
            continue

        if selection.x is not None:
            col_id = series.dims.x
            col = columns.get(col_id, None)
            if col is not None:
                key = col["columnName"]
                node = filter_node_to_selection(node, selection.x, key)

        if selection.y is not None:
            col_id = series.dims.y
            col = columns.get(col_id, None)
            if col is not None:
                key = col["columnName"]
                node = filter_node_to_selection(node, selection.y, key)

        if len(plot.config.series) > 1:

            def merge_func(row: graph.Node[types.TypedDict]):
                return dict_.TypedDict.merge(
                    row, dict_.dict_(y_expr_str=series.y_expr_str)
                )

            func = weave_internal.define_fn({"row": node.type.object_type}, merge_func)
            node = list_.List.map(node, func)

        table_nodes.append(node)

    node_list = list_.make_list(
        **{str(i): node for (i, node) in enumerate(table_nodes)}
    )
    concatted = list_.List.concat(node_list)
    if concatted.type.object_type == types.UnknownType():
        return concatted
    return concatted["row"]


# TODO: keep in arrow
@weave.op(name="panel_plot-rows_selected_refine", hidden=True)
def rows_selected_refine(self: Plot) -> weave.types.Type:
    if self.config is None:
        raise errors.WeaveInternalError("config is None")

    nodes = []
    for series in self.config.series:
        table_config = panel_table.TableConfig(tableState=series.table)
        table_panel = panel_table.Table(self.input_node, config=table_config)
        node = list_.unnest(panel_table.rows(table_panel))
        if len(self.config.series) > 1:
            node = dict_.TypedDict.merge(
                node[0], dict_.dict_(y_expr_str=series.y_expr_str)
            )
        else:
            node = node[0]
        nodes.append(node)
    table_row_types = [node.type for node in nodes]  # type: ignore
    return types.List(types.union(*table_row_types))


# TODO: keep in arrow
@weave.op(name="panel_plot-selected_data_refine", hidden=True)
def selected_data_refine(self: Plot) -> weave.types.Type:
    return types.List(typing.cast(weave.types.List, self.input_node.type).object_type)


# TODO: keep in arrow
@weave.op(
    name="panel_plot-rows_selected",
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=rows_selected_refine,
)
def rows_selected(self: Plot):
    rows_selected_node = _get_rows_selected_node(self)
    return weave.use(rows_selected_node)


# TODO: keep in arrow
@weave.op(
    name="panel_plot-selected_data",
    output_type=weave.types.List(weave.types.Any()),
    refine_output_type=selected_data_refine,
)
def selected_data(self: Plot):
    selected_data_node = _get_selected_data_node(self)
    return weave.use(selected_data_node)
