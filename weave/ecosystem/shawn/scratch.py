import weave


@weave.op()
def single_distribution(input_node: weave.Node[list[float]]) -> weave.panels.Plot:
    binned = input_node.groupby(lambda v: round(v * 10) / 10).map(
        lambda group: weave.ops.dict_(value=group.key(), count=group.count())
    )
    return weave.panels.Plot(
        binned,
        x=lambda row: row["value"],
        y=lambda row: row["count"],
        mark="bar",
    )
