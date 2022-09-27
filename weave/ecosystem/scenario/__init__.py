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
def metrics_bank(input_node: weave.Node[MetricsBankInput]) -> weave.panels.Each:
    input = typing.cast(MetricsBankInput, input_node)

    baseline = input["baseline"]
    candidate = input["candidate"]

    joined = weave.ops.join_all(
        weave.ops.make_list(l0=baseline, l1=candidate),
        lambda row: row["scenario_id"],
        False,
    )

    metrics = weave.ops.difference(joined[0].keys(), ["scenario_id"])

    return weave.panels.Each(
        metrics,
        render=lambda metric_name: weave.panels.Plot(
            joined,
            title=metric_name,
            x=lambda row: row[metric_name][0],
            y=lambda row: row[metric_name][1],
        ),
    )
