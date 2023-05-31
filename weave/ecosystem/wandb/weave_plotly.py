import datetime

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
    bar_data = list(bar_data)  # do this to get out of arrow :(
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


class ScatterData(typing.TypedDict):
    x: typing.Optional[float]
    y: typing.Optional[float]
    label: typing.Optional[str]


class TimeBin(typing.TypedDict):
    start: datetime.datetime
    center: datetime.datetime
    stop: datetime.datetime


class TimeSeriesData(typing.TypedDict):
    x: TimeBin
    y: float
    label: str


@weave.op(
    input_type={
        "data": weave.types.List(
            weave.types.TypedDict(
                {
                    "x": weave.types.TypedDict(
                        {
                            key: weave.types.optional(weave.types.Timestamp())
                            for key in ["start", "stop"]
                        }
                    ),
                    "y": weave.types.optional(weave.types.Float()),
                    "label": weave.types.optional(weave.types.String()),
                }
            )
        ),
        "mark": weave.types.String(),
        "labels": weave.types.TypedDict(
            {
                "x": weave.types.String(),
                "y": weave.types.String(),
                "label": weave.types.String(),
            }
        ),
        "label_overrides": weave.types.Dict(weave.types.String(), weave.types.String()),
    }
)
def plotly_time_series(data, mark, labels, label_overrides) -> plotly.graph_objs.Figure:
    data = list(data)  # do this to get out of arrow :(
    labels = {**labels, **label_overrides}

    def bin_center(bin):
        return bin["x"]["start"] + (bin["x"]["stop"] - bin["x"]["start"]) / 2

    if mark == "point":
        data = [{**d, "x": bin_center(d)} for d in data]  # type: ignore
        fig = px.scatter(
            data, x="x", y="y", color="label", template="plotly_white", labels=labels
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        fig.update_layout(dragmode="select")
        return fig
    elif mark == "bar":
        pruned = [{**d, "x": d["x"]["start"]} for d in data]  # type: ignore

        # plotly expects timedeltas in ms.
        # source https://community.plotly.com/t/bar-width-using-plotly-express/47580/5
        bin_size = (data[0]["x"]["stop"] - data[0]["x"]["start"]).total_seconds() * 1000
        fig = px.bar(
            pruned,
            x="x",
            y="y",
            color="label",
            barmode="stack",
            template="plotly_white",
            labels=labels,
        )
        fig.update_layout(showlegend=False)
        fig.update_traces(width=bin_size)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        fig.update_layout(dragmode="select")
        return fig
    elif mark == "line":
        data = [{**d, "x": bin_center(d)} for d in data]  # type: ignore
        fig = px.line(
            data, x="x", y="y", color="label", template="plotly_white", labels=labels
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        fig.update_layout(dragmode="select")
        return fig
    else:
        raise ValueError(f"Unknown mark {mark}")


@weave.op()
def plotly_scatter(data: list[ScatterData]) -> plotly.graph_objs.Figure:
    from ... import storage

    data = storage.to_weavejs(data)
    color = None
    if data and "label" in data[0]:
        color = "label"
    fig = px.scatter(data, x="x", y="y", color=color, template="plotly_white")
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
