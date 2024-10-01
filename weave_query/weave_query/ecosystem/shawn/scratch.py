import dataclasses
import typing

import weave_query as weave
import weave_query
from weave_query import panel, panel_util


@weave.op()
def single_distribution(
    input_node: weave.Node[list[float]],
) -> weave_query.panels.Plot:
    binned = input_node.groupby(lambda v: round(v * 10) / 10).map(  # type: ignore
        lambda group: weave_query.ops.dict_(value=group.key(), count=group.count())
    )
    return weave_query.panels.Plot(
        binned,
        x=lambda row: row["value"],
        y=lambda row: row["count"],
        mark="bar",
    )


@weave.type()
class AdderConfig:
    operand: weave.Node[int] = dataclasses.field(
        default_factory=lambda: weave_query.graph.ConstNode(weave.types.Int(), 10)
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
) -> weave_query.panels.LabeledItem:
    input_val = typing.cast(int, input_node)
    config = adder_default_config(config)
    return weave_query.panels.LabeledItem(
        label="operand",
        item=weave_query.panels.Slider(
            config=weave_query.panels.SliderConfig(
                weave_query.ops.execute(config.operand)
            )
        ),
    )


@weave.op()
def adder(
    input_node: weave.Node[int], config: AdderConfig
) -> weave_query.panels.LabeledItem:
    input_val = typing.cast(int, input_node)
    config = adder_default_config(config)
    return weave_query.panels.LabeledItem(label="output", item=input_val + config.operand)  # type: ignore


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
