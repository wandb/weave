import weave
import typing


class ScenarioResult(typing.TypedDict):
    scenario_id: str
    metric1: float
    metric2: float
    metric3: float
    metric4: float
    metric5: float
    metric6: float


class MetricsBankInput(typing.TypedDict):
    baseline: list[ScenarioResult]
    candidate: list[ScenarioResult]


@weave.type()
class MetricsBankPanel(weave.Panel):
    id = "MetricsBankPanel"
    input_node: weave.Node[MetricsBankInput]

    @weave.op()
    def render(self) -> weave.panels.Each:
        input = typing.cast(MetricsBankInput, self.input_node)

        baseline = input["baseline"]
        candidate = input["candidate"]

        joined = weave.ops.join_all(
            weave.ops.make_list(l0=baseline, l1=candidate),
            lambda row: row["scenario_id"],
            False,
        )

        # The output type of keys includes the keys (its List["scenario_id" | "metric1" | "metric2" | "metric3"])
        joined_keys = joined[0].keys()

        # The output type of difference is List["metric1" | "metric2" | "metric3"]
        metrics = weave.ops.difference(joined_keys, [weave.const("scenario_id")])

        # TODO: broken
        return weave.panels.Each(
            metrics,
            render=lambda metric_name: weave.panels.Group(
                items={
                    "title": metric_name,
                    "plot": weave.panels.Plot(
                        joined,
                        # TODO: bring this back
                        # title=metric_name,
                        # The [metric_name] pick operations correctly product list[float], since
                        # we know metric_name is not scenario_id in the type system.
                        # If this produced list[float | str], PanelPlot would not know how to render
                        # the data.
                        x=lambda row: row[metric_name][0],
                        # x_title="baseline",
                        y=lambda row: row[metric_name][1],
                        # y_title="candidate",
                    ),
                },
            ),
        )  # type: ignore
