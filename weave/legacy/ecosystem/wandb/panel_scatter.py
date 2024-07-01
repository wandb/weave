import dataclasses
import inspect
import typing

import weave
from weave import weave_internal
from weave.legacy.ecosystem.wandb import weave_plotly


@weave.type()
class ScatterConfig:
    x_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.legacy.graph.VoidNode()
    )
    y_fn: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.legacy.graph.VoidNode()
    )
    label_fn: weave.Node[typing.Any] = dataclasses.field(
        default_factory=lambda: weave.legacy.graph.VoidNode()
    )


@weave.type()
class Scatter(weave.Panel):
    id = "Scatter"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[ScatterConfig] = None
    _renderAsPanel: typing.Optional[weave_plotly.PanelPlotly] = None

    @weave.op()
    def initialize(self) -> ScatterConfig:
        input_node = self.input_node
        unnested = weave.legacy.ops.unnest(input_node)
        return ScatterConfig(
            x_fn=weave_internal.define_fn(
                {"item": unnested.type.object_type},
                lambda item: item,  # type: ignore
            ),
            y_fn=weave_internal.define_fn(
                {"item": unnested.type.object_type},
                lambda item: item,  # type: ignore
            ),
            label_fn=weave_internal.define_fn(
                {"item": unnested.type.object_type},
                lambda item: item,  # type: ignore
            ),
        )

    # The config render op. This renders the config editor.
    @weave.op()
    def render_config(self) -> weave.legacy.panels.Group:
        config = typing.cast(ScatterConfig, self.config)
        return weave.legacy.panels.Group(
            items={
                "x_fn": weave.legacy.panels.LabeledItem(
                    label="x", item=weave.legacy.panels.FunctionEditor(config.x_fn)
                ),
                "y_fn": weave.legacy.panels.LabeledItem(
                    label="y", item=weave.legacy.panels.FunctionEditor(config.y_fn)
                ),
                "label_fn": weave.legacy.panels.LabeledItem(
                    label="label",
                    item=weave.legacy.panels.FunctionEditor(config.label_fn),
                ),
            }
        )

    # The render op. This renders the panel.
    @weave.op()
    def render(self) -> weave_plotly.PanelPlotly:
        input_node = self.input_node
        config = typing.cast(ScatterConfig, self.config)
        unnested = weave.legacy.ops.unnest(input_node)
        if (
            not weave.types.optional(weave.types.Float()).assign_type(config.x_fn.type)
            or not weave.types.optional(weave.types.Float()).assign_type(
                config.y_fn.type
            )
            or not weave.types.optional(weave.types.String()).assign_type(
                config.label_fn.type
            )
        ):
            return weave.legacy.panels.PanelHtml(weave.legacy.ops.Html("No data"))  # type: ignore
        if config.label_fn.type == weave.types.Invalid():
            plot_data = unnested.map(
                lambda item: weave.legacy.ops.dict_(x=config.x_fn(item), y=config.y_fn(item))  # type: ignore
            )
        else:
            plot_data = unnested.map(
                lambda item: weave.legacy.ops.dict_(
                    x=config.x_fn(item),
                    y=config.y_fn(item),
                    label=config.label_fn(item),
                )  # type: ignore
            )
        fig = weave_plotly.plotly_scatter(plot_data)
        return weave_plotly.PanelPlotly(fig)

    # This function currently requires a paired output_type implementation in WeaveJS!
    # TODO: Fix
    @weave.op(output_type=lambda input_type: input_type["self"].input_node.output_type)
    def selected(self):
        unnested = weave.legacy.ops.unnest(self.input_node)
        config = self.config
        filtered = unnested.filter(
            lambda item: weave.legacy.ops.Boolean.bool_and(
                weave.legacy.ops.Boolean.bool_and(
                    weave.legacy.ops.Boolean.bool_and(
                        config.x_fn(item)
                        > weave.legacy.ops.TypedDict.pick(
                            self._renderAsPanel.config.selected, "xMin"
                        ),
                        config.x_fn(item)
                        < weave.legacy.ops.TypedDict.pick(
                            self._renderAsPanel.config.selected, "xMax"
                        ),
                    ),
                    config.y_fn(item)
                    > weave.legacy.ops.TypedDict.pick(
                        self._renderAsPanel.config.selected, "yMin"
                    ),
                ),
                config.y_fn(item)
                < weave.legacy.ops.TypedDict.pick(
                    self._renderAsPanel.config.selected, "yMax"
                ),
            )
        )
        return weave_internal.use(filtered)
