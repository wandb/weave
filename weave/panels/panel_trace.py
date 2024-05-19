import dataclasses
import typing
import weave
from .. import panel

span_typed_dict_type = weave.types.TypedDict(
    {
        "name": weave.types.optional(weave.types.String()),
        "span_id": weave.types.optional(weave.types.String()),
        "parent_id": weave.types.optional(weave.types.String()),
        "trace_id": weave.types.optional(weave.types.String()),
        "start_time_s": weave.types.optional(weave.types.Number()),
        "end_time_s": weave.types.optional(weave.types.Number()),
        "status_code": weave.types.optional(weave.types.String()),
        "inputs": weave.types.optional(weave.types.TypedDict({})),
        "output": weave.types.optional(weave.types.Any()),
        "exception": weave.types.optional(weave.types.String()),
        "attributes": weave.types.optional(weave.types.TypedDict({})),
        "summary": weave.types.optional(weave.types.TypedDict({})),
        "timestamp": weave.types.optional(weave.types.Timestamp()),
    },
    not_required_keys=set(
        # parent_id is not required because it is None for root spans
        [
            "status_code",
            "inputs",
            "output",
            "exception",
            "attributes",
            "summary",
            "parent_id",
        ]
    ),
)


@weave.type("tracePanelConfig")
class PanelTraceConfig:
    selectedSpanIndex: typing.Optional[int] = 0


@weave.type("tracePanel")
class Trace(panel.Panel):
    id = "tracePanel"
    config: typing.Optional[PanelTraceConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = PanelTraceConfig()
        if "selectedSpanIndex" in options:
            self.config.selectedSpanIndex = options["selectedSpanIndex"]


@weave.op(
    name="panel_trace-active_span",
    output_type=weave.types.optional(span_typed_dict_type),
)
def active_span(self: Trace):
    index = 0 if self.config is None else self.config.selectedSpanIndex
    return weave.ops_arrow.list_ops.index(self.input_node, index)
