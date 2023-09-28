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

LAZY_PATHS = [
    "signals.domain.x",
    "signals.domain.y",
]

LAZY_PATH_TYPES = {
    "signals.domain.x": weave.types.optional(weave.types.List(weave.types.Any())),
    "signals.domain.y": weave.types.optional(weave.types.List(weave.types.Any())),
}


SelectFunction = typing.Union[graph.Node, typing.Callable[[typing.Any], typing.Any]]


@weave.type()
class PlotConstants:
    mark: typing.Optional[MarkOption] = None
    pointShape: PointShapeOption = "circle"
    label: LabelOption = "series"
    lineStyle: LineStyleOption = "solid"


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
        groupby_dims: typing.Optional[list[DimName]] = None,
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

        groupby_dims = groupby_dims or []

        if select_functions:
            for dimname in groupby_dims:
                if dimname not in select_functions:
                    raise ValueError(
                        f"select_functions must contain a function for groupby dim {dimname}"
                    )
                table.enable_groupby(getattr(dims, dimname))
                if dimname == "label":
                    table.enable_groupby(dims.color)

                table.update_col(getattr(dims, dimname), select_functions[dimname])

            for dimname in select_functions:
                if dimname not in groupby_dims:
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
class AxisScale:
    # need to use scaleType instead of `type` here because
    # `type` serializes to the same key as the
    # `type` used by ObjectType
    scaleType: typing.Optional[ScaleType] = "linear"
    range: typing.Optional[
        dict[typing.Literal["field"], typing.Callable[[str], str]]
    ] = None
    base: typing.Optional[float] = None  # for log scale


@weave.type()
class AxisSetting:
    noLabels: bool = False
    noTitle: bool = False
    noTicks: bool = False
    title: typing.Optional[str] = None
    scale: typing.Optional[AxisScale] = None


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
    x: LegendSetting = dataclasses.field(default_factory=LegendSetting)
    y: LegendSetting = dataclasses.field(default_factory=LegendSetting)
    color: LegendSetting = dataclasses.field(default_factory=LegendSetting)
    pointShape: LegendSetting = dataclasses.field(default_factory=LegendSetting)
    pointSize: LegendSetting = dataclasses.field(default_factory=LegendSetting)
    lineStyle: LegendSetting = dataclasses.field(default_factory=LegendSetting)


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

LazySelection = typing.Union[Selection, SelectFunction]


# TODO: split this into 2 - one for lazy, one eager
@weave.type()
class AxisSelections:
    x: typing.Optional[Selection] = None
    y: typing.Optional[Selection] = None


@weave.type()
class LazyAxisSelections:
    x: SelectFunction = graph.ConstNode(weave.types.optional(weave.types.Any()), None)
    y: SelectFunction = graph.ConstNode(weave.types.optional(weave.types.Any()), None)


@weave.type()
class Signals:
    domain: LazyAxisSelections
    selection: AxisSelections


@weave.type("plotConfig")
class PlotConfig:
    series: typing.List[Series]
    axisSettings: typing.Optional[AxisSettings]
    legendSettings: typing.Optional[LegendSettings]
    configOptionsExpanded: typing.Optional[ConfigOptionsExpanded]
    signals: Signals
    configVersion: int = 15


def set_through_array(
    obj: typing.Any, path: typing.List[str], value: typing.Any
) -> None:
    """
    Recursively sets an attribute, key or index specified by a path in a nested object structure to a given value
    (consisting of dictionaries, lists or custom objects). The path is a list of strings, with the special value '#'
    used to denote all items in a list.

    Parameters:
    obj (Any): The object that will be traversed and modified.
    path (List[str]): The list of strings, where each string is a key or attribute name in the path to the location
    in the nested object structure to be modified. If a string is '#', it indicates that all items in the list at
    that level should be modified.
    value (Any): The value to set at the location specified by the path.

    Raises:
    ValueError: If the path cannot be followed in the object, it raises a ValueError.

    Returns:
    None: The function modifies the object in-place and does not return any value.
    """
    if len(path) == 0:
        return

    first, *rest = path

    if first == "#":
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                set_through_array(
                    item, rest, (value[i] if isinstance(value, list) else value)
                )
    elif len(rest) == 0:
        if isinstance(obj, dict):
            obj[first] = value
        else:
            setattr(obj, first, value)
    elif hasattr(obj, first):
        set_through_array(getattr(obj, first), rest, value)
    else:
        raise ValueError(f"Could not set {path} in {obj} to {value}")


def get_through_array(
    obj: typing.Any, path: typing.List[str], coerce_list_of_nodes_to_node=False
) -> typing.Any:
    """
    Recursively retrieves a value from an attribute, key or index specified by a path in a nested object structure
    (consisting of dictionaries, lists or custom objects). The path is a list of strings, with the special value '#'
    used to denote all items in a list.

    Parameters:
    obj (Any): The object that will be traversed.
    path (List[str]): The list of strings, where each string is a key or attribute name in the path to the location
    in the nested object structure to retrieve. If a string is '#', it indicates that values from all items in the
    list at that level should be retrieved.
    coerce_list_of_nodes_to_node (bool): This flag controls how lists of 'graph.Node' objects are handled. If set to
    True, lists of 'graph.Node' objects are turned into a single 'list_.make_list' object with nodes as its items.

    Raises:
    ValueError: If the path cannot be followed in the object, it raises a ValueError.

    Returns:
    Any: The value or list of values retrieved from the object at the location specified by the path.
    """
    if len(path) == 0:
        return obj

    first, *rest = path

    if first == "#":
        if isinstance(obj, list):
            result = [
                get_through_array(
                    item,
                    rest,
                    coerce_list_of_nodes_to_node=coerce_list_of_nodes_to_node,
                )
                for item in obj
            ]
            if coerce_list_of_nodes_to_node and all(
                isinstance(item, graph.Node) for item in result
            ):
                result = list_.make_list({i: item for i, item in enumerate(result)})
            return result
        else:
            raise ValueError(f"Could not get {path} in {obj}: not a list")
    elif hasattr(obj, first):
        return get_through_array(
            getattr(obj, first),
            rest,
            coerce_list_of_nodes_to_node=coerce_list_of_nodes_to_node,
        )
    elif len(rest) == 0:
        if isinstance(obj, dict):
            return obj[first]
        else:
            return getattr(obj, first, None)
    else:
        raise ValueError(f"Could not get {path} in {obj}")


def ensure_node(
    obj: typing.Any,
    path: typing.List[str],
    type: typing.Optional[weave.types.Type] = None,
) -> None:
    value = get_through_array(obj, path)
    if isinstance(value, list):
        if not all(item == value[0] for item in value):
            raise ValueError(f"Cannot ensure node for {path}: not all values are equal")
        value = value[0]
    if not isinstance(value, graph.Node):
        if type is None:
            type = weave.types.TypeRegistry.type_of(value)
        set_through_array(obj, path, graph.ConstNode(type, value))


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
        groupby_dims: typing.Optional[typing.List[DimName]] = None,
        tooltip: typing.Optional[SelectFunction] = None,
        pointShape: typing.Optional[SelectFunction] = None,
        lineStyle: typing.Optional[SelectFunction] = None,
        y2: typing.Optional[SelectFunction] = None,
        series: typing.Optional[typing.Union[Series, typing.List[Series]]] = None,
        no_axes: bool = False,
        no_legend: bool = False,
        x_title: typing.Optional[str] = None,
        y_title: typing.Optional[str] = None,
        x_axis_type: typing.Optional[ScaleType] = None,
        y_axis_type: typing.Optional[ScaleType] = None,
        color_title: typing.Optional[str] = None,
        domain_x: typing.Optional[SelectFunction] = None,
        domain_y: typing.Optional[SelectFunction] = None,
    ):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config

        if self.config is None:
            constants = PlotConstants(mark=mark)

            select_functions: typing.Optional[dict[DimName, SelectFunction]] = None
            for field, maybe_dim in zip(
                dataclasses.fields(DimConfig),
                [x, y, color, label, tooltip, pointShape, lineStyle, y2],
            ):
                if maybe_dim is not None:
                    if select_functions is None:
                        select_functions = {}
                    select_functions[typing.cast(DimName, field.name)] = maybe_dim

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
                        groupby_dims=groupby_dims,
                    )
                ]

            # Just moved these down so all series creation stuff is clustered
            # in the top.
            signals = Signals(domain=LazyAxisSelections(), selection=AxisSelections())
            if domain_x is not None:
                signals.domain.x = domain_x

            if domain_y is not None:
                signals.domain.y = domain_y

            config_axisSettings = AxisSettings(
                x=default_axis(), y=default_axis(), color=default_axis()
            )

            config_axisSettings.x.title = x_title
            config_axisSettings.y.title = y_title
            config_axisSettings.color.title = color_title

            if x_axis_type is not None:
                config_axisSettings.x.scale = AxisScale(scaleType=x_axis_type)
            if y_axis_type is not None:
                config_axisSettings.y.scale = AxisScale(scaleType=y_axis_type)

            config_legendSettings = LegendSettings(
                x=LegendSetting(),
                y=LegendSetting(),
                color=LegendSetting(),
                pointShape=LegendSetting(),
                lineStyle=LegendSetting(),
                pointSize=LegendSetting(),
            )

            self.config = PlotConfig(
                series=config_series,
                axisSettings=config_axisSettings,
                legendSettings=config_legendSettings,
                configOptionsExpanded=ConfigOptionsExpanded(),
                signals=signals,
            )

            for path in LAZY_PATHS:
                ensure_node(self.config, path.split("."), type=LAZY_PATH_TYPES[path])

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
            x=LegendSetting(True),
            y=LegendSetting(True),
            color=LegendSetting(True),
            pointShape=LegendSetting(),
            lineStyle=LegendSetting(),
            pointSize=LegendSetting(),
        )

    def to_code(self) -> typing.Optional[str]:
        field_vals: list[tuple[str, str]] = []
        default_signals = Signals(
            domain=LazyAxisSelections(),
            selection=AxisSelections(x=None, y=None),
        )
        default_axisSettings = AxisSettings(
            x=default_axis(), y=default_axis(), color=default_axis()
        )

        default_legendSettings = LegendSettings(
            x=LegendSetting(),
            y=LegendSetting(),
            color=LegendSetting(),
            pointShape=LegendSetting(),
            lineStyle=LegendSetting(),
            pointSize=LegendSetting(),
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
    node: graph.Node, selection: LazySelection, key: str
) -> graph.Node:
    if isinstance(selection, graph.Node):
        selection = weave_internal.call_fn(selection, {})

    selection = typing.cast(Selection, selection)

    if selection_is_continuous(selection):
        selection = typing.cast(ContinuousSelection, selection)

        def predicate(row: graph.Node[types.TypedDict]):
            target = dict_.TypedDict.pick(row, key)

            selection_min = selection[0]  # type: ignore
            selection_max = selection[1]  # type: ignore

            if (
                weave.types.Timestamp().assign_type(target.type)
                and isinstance(selection_min, (int, float))
                and isinstance(selection_max, (int, float))
            ):
                target = target.toNumber() * 1000

            return boolean.Boolean.bool_and(
                target >= selection_min, target <= selection_max
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
def _get_selected_rows_node(plot: Plot) -> graph.Node:
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
        node = list_.unnest(panel_table._get_rows_node(table_panel))
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
@weave.op(name="panel_plot-selected_rows_refine", hidden=True)
def selected_rows_refine(self: Plot) -> weave.types.Type:
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
    name="panel_plot-selected_rows",
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=selected_rows_refine,
)
def selected_rows(self: Plot):
    selected_rows_node = _get_selected_rows_node(self)
    return weave.use(selected_rows_node)


# TODO: keep in arrow
@weave.op(
    name="panel_plot-selected_data",
    output_type=weave.types.List(weave.types.Any()),
    refine_output_type=selected_data_refine,
)
def selected_data(self: Plot):
    selected_data_node = _get_selected_data_node(self)
    return selected_data_node
