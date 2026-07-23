from __future__ import annotations

from typing import cast

from opentelemetry import context as otel_context
from opentelemetry.context import Context
from opentelemetry.trace import Span

_MODEL_SPAN_KEY = otel_context.create_key("weave.openai_agents.model_span")


def set_model_span_in_context(span: Span, context: Context) -> Context:
    return otel_context.set_value(_MODEL_SPAN_KEY, span, context)


def has_active_sampled_model_span() -> bool:
    span = cast(Span | None, otel_context.get_value(_MODEL_SPAN_KEY))
    return (
        span is not None
        and span.is_recording()
        and span.get_span_context().trace_flags.sampled
    )
