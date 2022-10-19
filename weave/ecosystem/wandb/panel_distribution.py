import dataclasses
import inspect
import typing

import weave


@weave.type()
class DistributionConfig:
    value_fn: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    label_fn: weave.Node[str] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    bin_size: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.ConstNode(weave.types.Float(), 10)
    )


@weave.op()
def multi_distribution(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Plot:
    unnested = weave.ops.unnest(input_node)
    binned = unnested.groupby(
        lambda item: weave.ops.dict_(
            value=round(config.value_fn(item) / config.bin_size) * config.bin_size,
            label=config.label_fn(item),
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


@weave.op()
def multi_distribution_config(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Group2:
    return weave.panels.Group2(
        items={
            "value_fn": weave.panels.LabeledItem(
                label="value",
                item=weave.panels.ExpressionEditor(
                    config=weave.panels.ExpressionEditorConfig(config.value_fn)
                ),
            ),
            "label_fn": weave.panels.LabeledItem(
                label="label",
                item=weave.panels.ExpressionEditor(
                    config=weave.panels.ExpressionEditorConfig(config.label_fn)
                ),
            ),
            "bin_size": weave.panels.LabeledItem(
                label="bin_size",
                item=weave.panels.Slider2(
                    config=weave.panels.Slider2Config(config.bin_size)
                ),
            ),
        }
    )


@weave.type()
class MultiDistribution(weave.Panel):
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
            self.config.value_fn = weave.define_fn(
                {param_name: unnested.type.object_type}, options["value_fn"]
            )
        if "label_fn" in options:
            sig = inspect.signature(options["label_fn"])
            param_name = list(sig.parameters.values())[0].name
            self.config.label_fn = weave.define_fn(
                {param_name: unnested.type.object_type}, options["label_fn"]
            )
        if "bin_size" in options:
            self.config.bin_size = weave.make_node(options["bin_size"])
