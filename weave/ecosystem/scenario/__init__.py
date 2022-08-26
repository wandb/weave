import weave
import typing


class ScenarioResult(typing.TypedDict):
    scenario_id: str
    metric1: float
    metric2: float
    metric3: float


class MetricsBankInput(typing.TypedDict):
    baseline: list[ScenarioResult]
    candidate: list[ScenarioResult]


@weave.op(pure=False)
def metrics_bank(input_node: weave.Node[MetricsBankInput]) -> weave.panels.Plot:
    input = typing.cast(MetricsBankInput, input_node)

    baseline = input["baseline"]
    candidate = input["candidate"]

    metrics = weave.ops.union(baseline[0].keys(), candidate[0].keys())  # .subtract(
    #     ["scenario_id"]
    # )

    # TODO: make this a variable
    joined = weave.ops.join_all(
        weave.ops.make_list(l0=baseline, l1=candidate),
        lambda b_row: b_row["scenario_id"],
        False
        # lambda c_row: c_row["scenario_id"],
    )
    return weave.panels.Plot(
        joined,
        x=lambda scenario_metrics: scenario_metrics["metric1"][0],
        y=lambda scenario_metrics: scenario_metrics["metric2"][1],
    )

    # TODO: searchable PanelBank style thing
    return weave.panels.Facet(
        metrics,
        x=lambda m: m,
        select=lambda m: weave.panels.Plot(
            joined,
            x=lambda scenario_metrics: scenario_metrics[m][0],
            y=lambda scenario_metrics: scenario_metrics[m][1],
        ),
    )


# TODO:
#   Make it work
#   How do we setup sidebar
#   Drilldown
