import copy
import typing

from .. import panel
from . import table_state
import dataclasses

from .. import graph


@dataclasses.dataclass
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


@dataclasses.dataclass
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


@dataclasses.dataclass
class PlotUIState:
    pointShape: DropdownWithExpressionMode
    label: DropdownWithExpressionMode


def default_axis():
    return AxisSetting(noLabels=False, noTitle=False, noTicks=False)


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
        input_node: graph.Node,
        constants: typing.Optional[PlotConstantsInputDict] = None,
        select_functions: typing.Optional[typing.Dict[DimName, SelectFunction]] = None,
    ):
        _dims = {}
        table = table_state.TableState(input_node)
        for dim in dataclasses.fields(DimConfig):
            _dims[dim.name] = table.add_column(lambda row: graph.VoidNode())

        if select_functions:
            for dimname in select_functions:
                table.update_col(_dims[dimname], select_functions[dimname])

        dims = DimConfig(**_dims)

        rendered_constants = PlotConstants(
            **(constants or typing.cast(PlotConstantsInputDict, {}))
        )
        uiState = PlotUIState(pointShape="expression", label="expression")

        self.table = table
        self.dims = dims
        self.constants = rendered_constants
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
    def config(self):
        return {
            "table": _serialize(self.table),
            "dims": _serialize(self.dims),
            "constants": _serialize(self.constants),
            "uiState": _serialize(self.uiState),
        }

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
        return self.table._column_select_functions[col_id]

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


@dataclasses.dataclass
class AxisSetting:
    noLabels: bool
    noTitle: bool
    noTicks: bool


@dataclasses.dataclass
class AxisSettings:
    x: AxisSetting
    y: AxisSetting
    color: typing.Optional[AxisSetting]


@dataclasses.dataclass
class LegendSetting:
    noLegend: bool = False


@dataclasses.dataclass
class LegendSettings:
    x: LegendSetting
    y: LegendSetting
    color: LegendSetting


@dataclasses.dataclass
class ConfigOptionsExpanded:
    x: bool = False
    y: bool = False
    label: bool = False
    tooltip: bool = False
    mark: bool = False


def _serialize(obj: object) -> object:
    if isinstance(obj, table_state.TableState):
        return obj.to_json()
    elif isinstance(obj, Series):
        return obj.config
    elif isinstance(obj, dict):
        return {k: _serialize(v) for (k, v) in obj.items()}
    elif isinstance(obj, list):
        return list(map(_serialize, obj))
    elif dataclasses.is_dataclass(obj):
        return {
            field.name: _serialize(getattr(obj, field.name))
            for field in dataclasses.fields(obj)  # type: ignore
        }
    return obj


class Plot(panel.Panel):
    id = "plot"
    series: typing.List[Series]
    axisSettings: AxisSettings
    legendSettings: LegendSettings
    configOptionsExpanded: ConfigOptionsExpanded
    configVersion: int = 7

    def __init__(
        self,
        input_node: typing.Optional[graph.Node] = None,
        constants: typing.Optional[PlotConstantsInputDict] = None,
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
        super().__init__(input_node)

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
            ^ (
                constants is not None
                or select_functions is not None
                or input_node is not None
            )
        ):
            raise ValueError(
                "Must provide either series or input_node/select_functions/constants, but not both"
            )

        if series is not None:
            if isinstance(series, Series):
                self.series = [series]
            else:
                self.series = series
        else:
            self.series = [
                Series(
                    typing.cast(graph.Node, self.input_node),
                    constants=constants,
                    select_functions=select_functions,
                )
            ]

        self.axisSettings = AxisSettings(
            x=default_axis(), y=default_axis(), color=default_axis()
        )

        self.legendSettings = LegendSettings(
            x=LegendSetting(), y=LegendSetting(), color=LegendSetting()
        )

        if no_axes:
            self.set_no_axes()

        if no_legend:
            self.set_no_legend()

        self.configOptionsExpanded = ConfigOptionsExpanded()

    def add_series(self, series: Series):
        self.series.append(series)

    def set_no_axes(self):
        self.axisSettings.x = AxisSetting(noLabels=True, noTitle=True, noTicks=True)
        self.axisSettings.y = AxisSetting(noLabels=True, noTitle=True, noTicks=True)

    def set_no_legend(self):
        self.legendSettings.color = LegendSetting(noLegend=True)

    def __eq__(self, other):
        return self.config == other.config

    @property
    def config(self):
        return _serialize(
            {
                "series": self.series,
                "axisSettings": self.axisSettings,
                "legendSettings": self.legendSettings,
                "configOptionsExpanded": self.configOptionsExpanded,
                "configVersion": self.configVersion,
            }
        )


def make_set_all_series(dim_name: str) -> typing.Callable[[Plot, typing.Any], None]:
    def set(self: Plot, expr) -> None:
        for series in self.series:
            setter = getattr(series, f"set_{dim_name}")
            setter(expr)

    return set


def make_group_all_series(dim_name: str) -> typing.Callable[[Plot], None]:
    def group(self: Plot) -> None:
        for series in self.series:
            grouper = getattr(series, f"groupby_{dim_name}")
            grouper()

    return group


def make_get_all_series(
    dim_name: str,
) -> typing.Callable[[Plot], typing.List[graph.Node]]:
    def get(self: Plot) -> typing.List[graph.Node]:
        dim_select_functions: typing.List[graph.Node] = []
        for series in self.series:
            getter = getattr(series, f"get_{dim_name}")
            dim_select_functions.append(getter())
        return dim_select_functions

    return get


def make_set_constant_all_series(
    const_name: str,
) -> typing.Callable[[Plot, typing.Any], None]:
    def set(self: Plot, value) -> None:
        for series in self.series:
            setter = getattr(series, f"set_{const_name}_constant")
            setter(value)

    return set


def make_get_constant_all_series(
    const_name: str,
) -> typing.Callable[[Plot], typing.List[typing.Any]]:
    constants: typing.List[typing.Any] = []

    def get(self: Plot) -> typing.List[typing.Any]:
        for series in self.series:
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
