# TODO: types are all messed up after panel_composition branch
import copy
import typing
import weave

from .. import panel
from . import table_state
import dataclasses

from .. import graph
from .. import errors


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
    "x", "y", "color", "label", "tooltip", "pointSize", "pointShape", "y2"
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
LineStyleOption = typing.Literal["series", "solid", "dashed", "dotted", "dot-dashed"]

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
    return AxisSetting(noLabels=False, noTitle=False, noTicks=False)


@weave.type()
class Series:
    table: table_state.TableState
    dims: DimConfig
    constants: PlotConstants
    uiState: PlotUIState

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
        input_node: graph.Node = None,
        table: table_state.TableState = None,
        dims: DimConfig = None,
        constants: PlotConstants = None,
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
                table.update_col(_dims[dimname], select_functions[dimname])

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


@weave.type()
class AxisSetting:
    noLabels: bool
    noTitle: bool
    noTicks: bool


@weave.type()
class AxisSettings:
    x: AxisSetting
    y: AxisSetting
    color: typing.Optional[AxisSetting]


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


@weave.type(__override_name="plotConfig")
class PlotConfig:
    series: typing.List[Series]
    axisSettings: typing.Optional[AxisSettings]
    legendSettings: typing.Optional[LegendSettings]
    configOptionsExpanded: typing.Optional[ConfigOptionsExpanded]
    configVersion: int = 7


@weave.type(__override_name="plot")
class Plot(panel.Panel):
    id = "plot"
    config: typing.Optional[PlotConfig] = None

    def __init__(
        self,
        input_node=None,
        vars=None,
        config: typing.Optional[PlotConfig] = None,
        constants: PlotConstants = None,
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
    ):
        if vars is None:
            vars = {}
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            if mark is not None:
                constants = PlotConstants(
                    mark=mark, pointShape=None, lineStyle=None, label=None
                )
            else:
                constants = PlotConstants(
                    mark=None, pointShape=None, lineStyle=None, label=None
                )

            select_functions: typing.Optional[dict[DimName, SelectFunction]] = None
            for (field, maybe_dim) in zip(
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
            self.config = PlotConfig(
                series=config_series,
                axisSettings=config_axisSettings,
                legendSettings=config_legendSettings,
                configOptionsExpanded=ConfigOptionsExpanded(),
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
        self.config.axisSettings.x = AxisSetting(
            noLabels=True, noTitle=True, noTicks=True
        )
        self.config.axisSettings.y = AxisSetting(
            noLabels=True, noTitle=True, noTicks=True
        )

    def set_no_legend(self):
        self.config.legendSettings.color = LegendSetting(noLegend=True)


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
