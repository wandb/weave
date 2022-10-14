import dataclasses
import inspect
import typing

import weave

from ... import weave_internal
from ... import panel


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


@weave.type()
class DistributionConfig:
    value: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    label: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )


@weave.op()
def multi_distribution(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Plot:
    unnested = weave.ops.unnest(input_node)
    binned = unnested.groupby(
        lambda item: weave.ops.dict_(
            value=round(weave_internal.better_call_fn(config["value"], item) * 10) / 10,
            label=weave_internal.better_call_fn(config["label"], item),
        )
    ).map(
        lambda group: weave.ops.dict_(
            value=group.key()["value"], label=group.key()["label"], count=group.count()
        )
    )
    return weave.panels.Plot(
        binned,
        x=lambda row: row["value"],
        y=lambda row: row["count"],
        label=lambda row: row["label"],
        mark="bar",
    )


# TODO: not yet used
@weave.op()
def multi_distribution_config(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Group2:
    return weave.panels.Group2(
        items={
            "value_fn": weave.panels.LabeledItem(
                label="value", item=weave.panels.ExpressionEditor()
            ),
            "label_fn": weave.panels.LabeledItem(
                label="label", item=weave.panels.ExpressionEditor()
            ),
        }
    )


@weave.type()
class MultiDistribution(panel.Panel):
    id = "op-multi_distribution"
    config: typing.Optional[DistributionConfig] = None

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = DistributionConfig()

        unnested = weave.ops.unnest(self.input_node)
        if "value_fn" in options:
            sig = inspect.signature(options["value_fn"])
            param_name = list(sig.parameters.values())[0].name
            self.config.value = weave_internal.define_fn(
                {param_name: unnested.type.object_type}, options["value_fn"]
            )
        if "label_fn" in options:
            sig = inspect.signature(options["label_fn"])
            param_name = list(sig.parameters.values())[0].name
            self.config.label = weave_internal.define_fn(
                {param_name: unnested.type.object_type}, options["label_fn"]
            )
