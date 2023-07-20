import dataclasses
import typing
import weave
from .. import panel


@weave.type("tracePanelConfig")
class TraceConfig:
    selected_span: typing.Optional[typing.Any]


@weave.type("tracePanel")
class Trace(panel.Panel):
    id = "tracePanel"
    input_node: weave.Node[typing.Optional[list[dict]]]
    config: typing.Optional[TraceConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = TraceConfig(None)


@weave.op(
    name="panel_trace-selected_span",
    output_type=weave.types.TypedDict({"a": weave.types.Number()}),
    # refine_output_type=rows_refine,
)
def selected_span(self: Trace):
    # raise Exception(self.config)
    return {"a": 1}
