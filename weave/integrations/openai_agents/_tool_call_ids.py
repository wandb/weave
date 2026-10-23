"""Report the model's tool call id for each running Agents function span.

`FunctionSpanData` carries no call id, but the SDK builds the tool's
`ToolContext` from `tool_call.call_id` while that function span is current.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable

from agents.tool_context import ToolContext
from agents.tracing import FunctionSpanData, get_current_span

logger = logging.getLogger(__name__)

_FACTORY_NAME = "from_agent_context"

ToolCallIdSink = Callable[[str, str], None]


def install_tool_call_id_hook(sink: ToolCallIdSink) -> Callable[[], None] | None:
    """Wrap `ToolContext.from_agent_context` to pass `(span_id, call_id)` to `sink`; return the undo."""
    original = inspect.getattr_static(ToolContext, _FACTORY_NAME, None)
    if not isinstance(original, classmethod):
        logger.warning(
            "ToolContext.%s is not a classmethod in this openai-agents version; "
            "execute_tool spans will not carry gen_ai.tool.call.id.",
            _FACTORY_NAME,
        )
        return None

    factory = original.__func__

    def from_agent_context(
        cls: type[ToolContext],
        context: object,
        tool_call_id: str,
        *args: object,
        **kwargs: object,
    ) -> ToolContext:
        tool_context = factory(cls, context, tool_call_id, *args, **kwargs)
        span = get_current_span()
        # Custom tools build their context before opening a function span.
        if span is not None and isinstance(span.span_data, FunctionSpanData):
            sink(span.span_id, tool_call_id)

        return tool_context

    setattr(ToolContext, _FACTORY_NAME, classmethod(from_agent_context))

    def undo() -> None:
        setattr(ToolContext, _FACTORY_NAME, original)

    return undo
