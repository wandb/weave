import dataclasses
import inspect
import typing

import weave

from ... import weave_internal

from . import weave_plotly


# This is the panel's config (the state that is stored in the panel and configurable
# in the UI by clicking on the gear icon.)
@weave.type()
class GeoConfig:
    x_fn: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    y_fn: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    color_fn: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )


# This is boilerplate that I'd like to get rid of.
def _geo_set_default_config(config, input_node, new_config):
    return new_config


def _geo_default_config_output_type(input_type):
    # We have to do shenaningans to pass the input type through
    # because it might be a subtype since the input type has unions
    # TOOD: Fix
    config_type = input_type["config"]
    if config_type == None:
        return GeoConfig.WeaveType()
    if isinstance(config_type, weave.types.Const):
        return config_type.val_type
    return config_type


# TODO: really annoying that I need the setter here.
@weave.op(
    setter=_geo_set_default_config,
    output_type=_geo_default_config_output_type,
)
def geo_default_config(
    config: typing.Optional[GeoConfig],
    unnested_node: list[typing.Any],
):
    input_type_item_type = weave.type_of(unnested_node).object_type  # type: ignore
    if config == None:
        return GeoConfig(
            x_fn=weave.define_fn({"item": input_type_item_type}, lambda item: item),
            y_fn=weave.define_fn({"item": input_type_item_type}, lambda item: item),
            color_fn=weave.define_fn({"item": input_type_item_type}, lambda item: item),
        )
    return config


# The render op. This renders the panel.
@weave.op(name="Geo")
def geo(
    input_node: weave.Node[list[typing.Any]], config: GeoConfig
) -> weave_plotly.PanelPlotly:
    unnested = weave.ops.unnest(input_node)
    config = geo_default_config(config, unnested)
    plot_data = unnested.map(
        lambda item: weave.ops.dict_(
            long=config.x_fn(item),  # type: ignore
            lat=config.y_fn(item),  # type: ignore
            color=config.color_fn(item),  # type: ignore
        )
    )
    fig = weave_plotly.plotly_geo(plot_data)
    return weave_plotly.PanelPlotly(fig)


# The config render op. This renders the config editor.
@weave.op(name="Geo_config")
def geo_config(
    input_node: weave.Node[list[typing.Any]], config: GeoConfig
) -> weave.panels.Group:
    unnested = weave.ops.unnest(input_node)
    config = geo_default_config(config, unnested)
    return weave.panels.Group(
        items={
            "x_fn": weave.panels.LabeledItem(
                label="x",
                item=weave.panels.FunctionEditor(
                    config=weave.panels.FunctionEditorConfig(config.x_fn)
                ),
            ),
            "y_fn": weave.panels.LabeledItem(
                label="y",
                item=weave.panels.FunctionEditor(
                    config=weave.panels.FunctionEditorConfig(config.y_fn)
                ),
            ),
            "color_fn": weave.panels.LabeledItem(
                label="color",
                item=weave.panels.FunctionEditor(
                    config=weave.panels.FunctionEditorConfig(config.color_fn)
                ),
            ),
        }
    )


# The interface for constructing this Panel from Python
@weave.type()
class Geo(weave.Panel):
    id = "Geo"
    config: typing.Optional[GeoConfig] = None
    _renderAsPanel: typing.Optional[weave_plotly.PanelPlotly] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(
        self, input_node, vars=None, config=None, _renderAsPanel=None, **options
    ):
        super().__init__(input_node=input_node, vars=vars)
        self._renderAsPanel = _renderAsPanel
        if self._renderAsPanel is None:
            self._renderAsPanel = weave_plotly.PanelPlotly()

        self.config = config
        if self.config is None:
            self.config = GeoConfig()

            unnested = weave.ops.unnest(self.input_node)
            if "x_fn" in options:
                sig = inspect.signature(options["x_fn"])
                param_name = list(sig.parameters.values())[0].name
                self.config.x_fn = weave.define_fn(
                    {param_name: unnested.type.object_type}, options["x_fn"]
                )
            else:
                self.config.x_fn = weave.define_fn(
                    {"item": unnested.type.object_type}, lambda item: item
                )
            if "y_fn" in options:
                sig = inspect.signature(options["y_fn"])
                param_name = list(sig.parameters.values())[0].name
                self.config.y_fn = weave.define_fn(
                    {param_name: unnested.type.object_type}, options["y_fn"]
                )
            else:
                self.config.y_fn = weave.define_fn(
                    {"item": unnested.type.object_type}, lambda item: item
                )
            if "color_fn" in options:
                sig = inspect.signature(options["color_fn"])
                param_name = list(sig.parameters.values())[0].name
                self.config.color_fn = weave.define_fn(
                    {param_name: unnested.type.object_type}, options["color_fn"]
                )
            else:
                self.config.color_fn = weave.define_fn(
                    {"item": unnested.type.object_type}, lambda item: item
                )

    # This function currently requires a paired output_type implementation in WeaveJS!
    # TODO: Fix
    @weave.op(output_type=lambda input_type: input_type["self"].input_node.output_type)
    def selected(self):
        # TODO: This function is not right! We need to do a range selection in polar space!
        unnested = weave.ops.unnest(self.input_node)
        config = geo_default_config(self.config, unnested)
        filtered = unnested.filter(
            lambda item: weave.ops.Boolean.bool_and(
                weave.ops.Boolean.bool_and(
                    weave.ops.Boolean.bool_and(
                        config.x_fn(item)
                        > weave.ops.TypedDict.pick(
                            self._renderAsPanel.config.selected, "xMin"
                        ),
                        config.x_fn(item)
                        < weave.ops.TypedDict.pick(
                            self._renderAsPanel.config.selected, "xMax"
                        ),
                    ),
                    config.y_fn(item)
                    > weave.ops.TypedDict.pick(
                        self._renderAsPanel.config.selected, "yMin"
                    ),
                ),
                config.y_fn(item)
                < weave.ops.TypedDict.pick(self._renderAsPanel.config.selected, "yMax"),
            )
        )
        return weave_internal.use(filtered)
