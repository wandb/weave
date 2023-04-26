import dataclasses
import typing

import weave

from ... import panel
from ... import panel_util


@weave.op()
def single_distribution(input_node: weave.Node[list[float]]) -> weave.panels.Plot:
    binned = input_node.groupby(lambda v: round(v * 10) / 10).map(  # type: ignore
        lambda group: weave.ops.dict_(value=group.key(), count=group.count())
    )
    return weave.panels.Plot(
        binned,
        x=lambda row: row["value"],
        y=lambda row: row["count"],
        mark="bar",
    )


@weave.type()
class AdderConfig:
    operand: weave.Node[int] = dataclasses.field(
        default_factory=lambda: weave.graph.ConstNode(weave.types.Int(), 10)
    )


def adder_set_default_config(config, new_config):
    return new_config


# TODO: really annoying that I need the setter here.
@weave.op(setter=adder_set_default_config)
def adder_default_config(config: typing.Optional[AdderConfig]) -> AdderConfig:
    if config == None:
        return AdderConfig(operand=panel_util.make_node(0.1))
    return typing.cast(AdderConfig, config)


@weave.op()
def adder_config(
    input_node: weave.Node[int], config: AdderConfig
) -> weave.panels.LabeledItem:
    input_val = typing.cast(int, input_node)
    config = adder_default_config(config)
    return weave.panels.LabeledItem(
        label="operand",
        item=weave.panels.Slider(
            config=weave.panels.SliderConfig(weave.ops.execute(config.operand))
        ),
    )


@weave.op()
def adder(input_node: weave.Node[int], config: AdderConfig) -> weave.panels.LabeledItem:
    input_val = typing.cast(int, input_node)
    config = adder_default_config(config)
    return weave.panels.LabeledItem(label="output", item=input_val + config.operand)  # type: ignore


@weave.type()
class Adder(panel.Panel):
    id = "op-adder"
    config: typing.Optional[AdderConfig] = None

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = AdderConfig()

        if "operand" in options:
            self.config.operand = panel_util.make_node(options["operand"])
