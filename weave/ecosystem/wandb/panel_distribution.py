import dataclasses
import inspect
import typing

import weave

from ... import panel_util

from . import weave_plotly


@weave.type()
class DistributionConfig:
    value_fn: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    label_fn: weave.Node[typing.Union[str, weave.types.InvalidPy]] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    bin_size: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.ConstNode(weave.types.Float(), 10)
    )


# This is boilerplate that I'd like to get rid of.
def _multi_distribution_set_default_config(config, input_node, new_config):
    return new_config


def _multi_distribution_default_config_output_type(input_type):
    # We have to do shenaningans to pass the input type through
    # because it might be a subtype since the input type has unions
    # TOOD: Fix
    config_type = input_type["config"]
    if config_type == None:
        return DistributionConfig.WeaveType()
    if isinstance(config_type, weave.types.Const):
        return config_type.val_type
    return config_type


# TODO: really annoying that I need the setter here.
@weave.op(
    setter=_multi_distribution_set_default_config,
    output_type=_multi_distribution_default_config_output_type,
)
def multi_distribution_default_config(
    config: typing.Optional[DistributionConfig],
    unnested_node: list[typing.Any],
):
    input_type_item_type = weave.type_of(unnested_node).object_type  # type: ignore
    if config == None:
        return DistributionConfig(
            value_fn=weave.define_fn({"item": input_type_item_type}, lambda item: item),
            label_fn=weave.define_fn({"item": input_type_item_type}, lambda item: item),
            bin_size=panel_util.make_node(10),
        )
    return config


# The render op. This renders the panel.
@weave.op()
def multi_distribution(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave_plotly.PanelPlotly:
    # I can't edit the frontend right now and I want to get this test passing.
    # So doing a little bit of type: ignore here.
    # TODO: Fix
    if not weave.types.union(weave.types.String(), weave.types.Float()).assign_type(
        config.value_fn.type.output_type  # type: ignore
    ):
        # TODO: need a nicer way to return error states
        return weave.panels.PanelHtml(weave.ops.Html("Invalid value_fn"))  # type: ignore
    unnested = weave.ops.unnest(input_node)
    config = multi_distribution_default_config(config, unnested)
    bin_size = weave.ops.execute(config.bin_size)

    def bin_func(item):
        value_fn_output_type = config.value_fn.type.output_type
        label_fn_output_type = config.label_fn.type.output_type
        group_items = {}
        if value_fn_output_type == weave.types.String():
            group_items["value"] = config.value_fn(item)
        else:
            group_items["value"] = round(config.value_fn(item) / bin_size) * bin_size

        if label_fn_output_type == weave.types.Invalid():
            group_items["label"] = "no_label"
        else:
            group_items["label"] = config.label_fn(item)

        return weave.ops.dict_(**group_items)

    binned = unnested.groupby(lambda item: bin_func(item)).map(
        lambda group: weave.ops.dict_(
            value=group.groupkey()["value"],
            label=group.groupkey()["label"],
            count=group.count(),
        )
    )
    fig = weave_plotly.plotly_barplot(binned)
    return weave_plotly.PanelPlotly(fig)


# PanelPlot version...
@weave.op()
def multi_distribution_panel_plot(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Plot:
    unnested = weave.ops.unnest(input_node)
    config = multi_distribution_default_config(config, unnested)
    bin_size = weave.ops.execute(config.bin_size)

    def bin_func(item):
        value_fn_output_type = config.value_fn.type.output_type
        label_fn_output_type = config.label_fn.type.output_type
        group_items = {}
        if value_fn_output_type == weave.types.String():
            group_items["value"] = config.value_fn(item)
        else:
            group_items["value"] = round(config.value_fn(item) / bin_size) * bin_size

        if label_fn_output_type == weave.types.Invalid():
            group_items["label"] = "no_label"
        else:
            group_items["label"] = config.label_fn(item)

        res = weave.ops.dict_(**group_items)
        return res

    binned = unnested.groupby(lambda item: bin_func(item)).map(
        lambda group: weave.ops.dict_(
            value=group.groupkey()["value"],
            label=group.groupkey()["label"],
            count=group.count(),
        )
    )

    return weave.panels.Plot(
        binned,
        x=lambda row: row["value"],
        y=lambda row: row["count"],
        label=lambda row: row["label"],
        mark="bar",
    )


# The config render op. This renders the config editor.
@weave.op()
def multi_distribution_config(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Group2:
    unnested = weave.ops.unnest(input_node)
    config = multi_distribution_default_config(config, unnested)
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
                    config=weave.panels.Slider2Config(
                        # Need execute here because....
                        # TODO: I don't quite know. Figure this out.
                        weave.ops.execute(config.bin_size)
                    )
                ),
            ),
        }
    )


# The interface for constructing this Panel from Python
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
            else:
                self.config.value_fn = weave.define_fn(
                    {"item": unnested.type.object_type}, lambda item: item
                )
            if "label_fn" in options:
                sig = inspect.signature(options["label_fn"])
                param_name = list(sig.parameters.values())[0].name
                self.config.label_fn = weave.define_fn(
                    {param_name: unnested.type.object_type}, options["label_fn"]
                )
            else:
                self.config.label_fn = weave.define_fn(
                    {"item": unnested.type.object_type},
                    lambda item: weave.graph.VoidNode(),
                )
            if "bin_size" in options:
                self.config.bin_size = weave.make_node(options["bin_size"])
