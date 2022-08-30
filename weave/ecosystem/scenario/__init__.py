import weave
import typing


class ScenarioResult(typing.TypedDict):
    scenario_id: float
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

    joined = weave.ops.join_all(
        weave.ops.make_list(l0=baseline, l1=candidate),
        lambda row: row["scenario_id"],
        False,
    )

    # Note metrics is keys of joined, so we don't need to compute it here
    # really...
    metrics = weave.ops.subtract(
        weave.ops.union(baseline[0].keys(), candidate[0].keys()), ["scenario_id"]
    )

    return weave.panels.Each(
        metrics,
        render=lambda metric_name: weave.panels.Plot(
            joined,
            title=metric_name,
            x=lambda row: row[metric_name][0],
            y=lambda row: row[metric_name][1],
        ),
    )


from ... import weave_internal


def cast_type(node: weave.graph.OutputNode, type):
    return weave_internal.make_output_node(type, node.from_op.name, node.from_op.inputs)


def row_x(row, metric_name):
    print("ROW", row)
    return cast_type(row[metric_name], weave.types.List(weave.types.Float()))[0]


def row_y(row, metric_name):
    print("ROW Y", row)
    return cast_type(row[metric_name], weave.types.List(weave.types.Float()))[1]
