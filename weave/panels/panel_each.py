import dataclasses
import inspect
import typing
import weave

from .. import panel
from .. import graph
from .. import weave_internal

RenderType = typing.TypeVar("RenderType")


@weave.type()
class PanelEachConfig(typing.Generic[RenderType]):
    x: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    y: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    w: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    h: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    render: graph.Node[RenderType] = dataclasses.field(
        default_factory=lambda: graph.VoidNode()
    )


@weave.type()
class Each(panel.Panel):
    id = "Each"
    config: typing.Optional[PanelEachConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = PanelEachConfig()

            object_type = self.input_node.type.object_type
            render_expr = options["render"]
            sig = inspect.signature(render_expr)
            var_name = list(sig.parameters.values())[0].name
            self.config.render = render_expr(
                weave_internal.make_var_node(object_type, var_name)
            )

            if "x" in options:
                sig = inspect.signature(options["x"])
                param_name = list(sig.parameters.values())[0].name
                self.config.x = weave.define_fn(
                    {param_name: object_type},
                    options["x"]
                    # NOTE THIS IS DIFFERENT FROM PANEL SCATTER! We don't
                    # send up an actual function!
                ).val
            if "y" in options:
                sig = inspect.signature(options["y"])
                param_name = list(sig.parameters.values())[0].name
                self.config.y = weave.define_fn(
                    {param_name: object_type}, options["y"]
                ).val
            if "w" in options:
                sig = inspect.signature(options["w"])
                param_name = list(sig.parameters.values())[0].name
                self.config.w = weave.define_fn(
                    {param_name: object_type}, options["w"]
                ).val
            if "h" in options:
                sig = inspect.signature(options["h"])
                param_name = list(sig.parameters.values())[0].name
                self.config.h = weave.define_fn(
                    {param_name: object_type}, options["h"]
                ).val
