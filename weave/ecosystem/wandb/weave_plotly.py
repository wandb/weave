import dataclasses
import io
import plotly
import weave
import typing
import plotly.express as px
import pandas as pd
from plotly import graph_objs as go

from ... import weave_internal
from ... import infer_types


class PlotlyType(weave.types.Type):
    instance_classes = plotly.graph_objs.Figure

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.plotly") as f:
            plotly.io.write_json(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.plotly") as f:
            return plotly.io.from_json(f.read())


@weave.weave_class(weave_type=PlotlyType)
class PlotlyOps:
    @weave.op()
    def contents(self) -> str:
        f = io.StringIO()
        plotly.io.write_json(self, f)
        f.seek(0)
        return f.read()


class BoxRange(typing.TypedDict):
    xMin: float
    xMax: float
    yMin: float
    yMax: float


@weave.type()
class PanelPlotlyConfig:
    selected: weave.Node[BoxRange] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(
            infer_types.python_type_to_type(BoxRange),
            {"xMin": 0, "xMax": 0, "yMin": 0, "yMax": 0},
        )
    )


@weave.type()
class PanelPlotly(weave.Panel):
    id = "PanelPlotly"
    config: PanelPlotlyConfig = dataclasses.field(default_factory=PanelPlotlyConfig)


class BarData:
    value: float
    label: str
    count: float


@weave.op()
def plotly_barplot(bar_data: list[BarData]) -> plotly.graph_objs.Figure:
    if not bar_data:
        fig = plotly.graph_objs.Figure()
        fig.update_layout(template="plotly_white")
        return fig
    fig = px.bar(
        bar_data,
        x="value",
        y="count",
        color="label",
        barmode="group",
        template="plotly_white",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    fig.update_layout(dragmode="select")
    return fig


class ScatterData:
    x: float
    y: float


@weave.op()
def plotly_scatter(data: list[ScatterData]) -> plotly.graph_objs.Figure:
    from ... import ops_arrow

    # TODO: Should convert to dataframe instead of list!
    if isinstance(data, ops_arrow.ArrowWeaveList):
        data = data.to_pylist_tagged()
    fig = px.scatter(data, x="x", y="y", template="plotly_white")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    fig.update_layout(dragmode="select")
    return fig


class GeoData(typing.TypedDict):
    lat: float
    long: float
    color: typing.Union[float, str]


@weave.op()
def plotly_geo(data: list[GeoData]) -> plotly.graph_objs.Figure:
    de = pd.DataFrame(data)

    fig = go.Figure(
        data=go.Scattergeo(
            lon=de["long"],
            lat=de["lat"],
            mode="markers",
            # text=de["Map label"],  # str(de["Magnitude"]) + " " + de["Date"],
            marker_color=de["color"]  # , colors[df["Type"][0]]
            # showlegend=True,
            # marker=dict(
            #     color=de["Magnitude"], size=15, opacity=0.9, colorscale="Sunset"
            # )
            # opacity
            # marker_color=colors[volcano_types[df["Type"][0]]]
        )
    )
    fig.update_geos(
        projection_type="orthographic",
        landcolor="white",
        oceancolor="MidnightBlue",
        showocean=True,
        lakecolor="LightBlue",
    )
    return fig
