import dataclasses
import typing

import weave

from . import weave_plotly


@weave.type()
class DistributionConfig:
    # value_fn and label_fn are functions of input item. They will be
    # represented in the config as Const(FunctionType(...), Node).
    # We should make a better type to represent this, so it can be
    # distinguished from an expression like bin_size.
    value_fn: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    label_fn: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    # This is an expression. It will be stored in the config as Node.
    bin_size: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )


# The interface for constructing this Panel from Python
@weave.type()
class Distribution(weave.Panel):
    id = "Distribution"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[DistributionConfig] = None

    @weave.op()
    def initialize(self) -> DistributionConfig:
        input_node = self.input_node
        unnested = weave.ops.unnest(input_node)
        return DistributionConfig(
            value_fn=weave.define_fn(
                {"item": unnested.type.object_type}, lambda item: item  # type: ignore
            ),
            label_fn=weave.define_fn(
                {"item": unnested.type.object_type}, lambda item: item  # type: ignore
            ),
            # Would be nice to call this weave.expr
            bin_size=weave.make_node(10),  # type: ignore
        )

    @weave.op()
    def render_config(self) -> weave.panels.Group:
        config = typing.cast(DistributionConfig, self.config)
        return weave.panels.Group(
            items={
                "value_fn": weave.panels.LabeledItem(
                    label="value",
                    item=weave.panels.FunctionEditor(config.value_fn),
                ),
                "label_fn": weave.panels.LabeledItem(
                    label="label",
                    item=weave.panels.FunctionEditor(config.label_fn),
                ),
                "bin_size": weave.panels.LabeledItem(
                    label="bin_size",
                    # Must execute here because bin_size is an expression.
                    # Editor panels take the actual type they edit (in this
                    # case float). The slider will edit the value of the
                    # const node directly in the config, or if the expression
                    # refers to variables, the edit will be routed to the appropriate
                    # owner.
                    item=weave.panels.Slider(config.bin_size.execute()),  # type: ignore
                ),
            }
        )

    # The render op. This renders the panel.
    @weave.op()
    def render(self) -> weave_plotly.PanelPlotly:
        input_node = self.input_node
        config = typing.cast(DistributionConfig, self.config)

        if not weave.types.union(
            weave.types.NoneType(), weave.types.String(), weave.types.Float()
        ).assign_type(
            config.value_fn.type.output_type  # type: ignore
        ):
            # TODO: need a nicer way to return error states
            return weave.panels.PanelString("Invalid value_fn")  # type: ignore
        # We always unnest, so that we can compare across groups of items
        # easily. (the Distribution notebook)
        unnested = weave.ops.unnest(input_node)
        bin_size = config.bin_size

        def bin_func(item):
            value_fn_output_type = config.value_fn.type.output_type
            label_fn_output_type = config.label_fn.type.output_type
            group_items = {}
            if value_fn_output_type == weave.types.String():
                group_items["value"] = config.value_fn(item)
            else:
                group_items["value"] = (
                    round(config.value_fn(item) / bin_size) * bin_size
                )

            if not weave.types.optional(weave.types.String()).assign_type(
                label_fn_output_type
            ):
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


# PanelPlot version... This is used by a test.
@weave.op()
def distribution_panel_plot_render(
    input_node: weave.Node[list[typing.Any]], config: DistributionConfig
) -> weave.panels.Plot:
    unnested = weave.ops.unnest(input_node)
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
