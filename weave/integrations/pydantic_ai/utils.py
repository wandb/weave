"""
Utility functions and span exporter for PydanticAI OpenTelemetry integration.

This module provides helpers for converting event dictionaries to OpenTelemetry events,
processing span attributes, mapping events to prompt/completion, and exporting spans
with Weave context headers. It also defines a custom PydanticAISpanExporter for use
with the OpenTelemetry SDK.
"""

import base64
import json
import os
from collections.abc import Sequence
from typing import Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace import Event
from opentelemetry.sdk.trace.export import SpanExporter

from weave.trace.context.weave_client_context import require_weave_client
from weave.wandb_interface import wandb_api


def dicts_to_events(
    event_dicts: Sequence[dict[str, Any]], span: trace_sdk.ReadableSpan
) -> Sequence[Event]:
    """
    Convert a sequence of event dictionaries into OpenTelemetry Event objects.

    Args:
        event_dicts: Sequence of dictionaries representing events. Each dictionary may contain:
            - "event.name" or "name": The name of the event (default is "event").
            - "timestamp": The timestamp of the event (optional).
            - Other keys are treated as attributes of the event.
        span: The span to which the events are associated. Used to infer timestamps if not provided.

    Returns:
        Sequence[Event]: A sequence of OpenTelemetry Event objects created from the input dictionaries.
    """
    event_objs: list[Event] = []
    n = len(event_dicts)
    for i, d in enumerate(event_dicts):
        name = d.get("event.name") or d.get("name") or "event"
        attrs = {
            k: v for k, v in d.items() if k not in ("event.name", "name", "timestamp")
        }
        timestamp = d.get("timestamp")
        if timestamp is None:
            if i == 0:
                timestamp = getattr(span, "start_time", None)
            elif i == n - 1:
                timestamp = getattr(span, "end_time", None)
            else:
                timestamp = getattr(span, "start_time", None)
        event = Event(name=name, attributes=attrs, timestamp=timestamp)
        event_objs.append(event)
    return event_objs


def handle_events(
    key: str, attrs: dict[str, Any], span: trace_sdk.ReadableSpan
) -> trace_sdk.ReadableSpan:
    """
    Process and attach events to a given OpenTelemetry span.

    Args:
        key: The key in the attributes dictionary that contains event data.
        attrs: A dictionary of attributes associated with the span.
        span: The OpenTelemetry span to which the events will be attached.

    Returns:
        trace_sdk.ReadableSpan: The updated span with the processed events attached.
    """
    if key in attrs:
        try:
            events = attrs.pop(key)
            if isinstance(events, str):
                events = json.loads(events)
            event_objs = dicts_to_events(
                events if isinstance(events, list) else [events], span
            )
            if hasattr(span, "_events") and isinstance(span._events, list):
                span._events.extend(event_objs)
            else:
                span._events = event_objs
        except Exception:
            pass
    return span


def map_events_to_prompt_completion(
    span: trace_sdk.ReadableSpan,
) -> trace_sdk.ReadableSpan:
    """
    Map events from a span to generate a prompt and completion for generative AI usage.

    Args:
        span: The OpenTelemetry span containing events to process.

    Returns:
        trace_sdk.ReadableSpan: The updated span with `gen_ai.prompt` and `gen_ai.completion` attributes.
    """
    messages: list[Any] = []
    for event in getattr(span, "_events", []):
        attrs = event.attributes
        if (
            event.name
            in (
                "gen_ai.system.message",
                "gen_ai.user.message",
                "gen_ai.assistant.message",
                "gen_ai.choice",
            )
            or attrs.get("role") == "tool"
        ):
            msg = attrs.get("message")
            if msg:
                messages.append(msg)
            else:
                msg_dict = {
                    "role": attrs.get("role"),
                    "content": attrs.get("content"),
                }
                # Only add tool_calls if present
                if "tool_calls" in attrs:
                    msg_dict["tool_calls"] = attrs["tool_calls"]
                messages.append(msg_dict)
    if messages:
        if len(messages) > 1:
            span._attributes["gen_ai.prompt"] = json.dumps(messages[:-1])
            span._attributes["gen_ai.completion"] = json.dumps(messages[-1])
        else:
            span._attributes["gen_ai.completion"] = json.dumps(messages[0])
    return span


def handle_usage(span: trace_sdk.ReadableSpan) -> trace_sdk.ReadableSpan:
    """
    Rename input/output token attributes to prompt/completion tokens for Weave schema.

    Args:
        span: The OpenTelemetry span to process.

    Returns:
        trace_sdk.ReadableSpan: The updated span with renamed usage attributes.
    """
    if "gen_ai.usage.input_tokens" in span._attributes:
        span._attributes["gen_ai.usage.prompt_tokens"] = span._attributes.pop(
            "gen_ai.usage.input_tokens"
        )
    if "gen_ai.usage.output_tokens" in span._attributes:
        span._attributes["gen_ai.usage.completion_tokens"] = span._attributes.pop(
            "gen_ai.usage.output_tokens"
        )
    return span


def handle_tool_call(span: trace_sdk.ReadableSpan) -> trace_sdk.ReadableSpan:
    """
    Update tool call attributes to match Weave's internal schema.

    Args:
        span: The OpenTelemetry span to process.

    Returns:
        trace_sdk.ReadableSpan: The updated span with tool call attributes set.
    """
    call_id = span._attributes.get("gen_ai.tool.call.id")
    if not call_id:
        return span
    tool_args = span._attributes.pop("tool_arguments", "")
    if tool_args is not None:
        span._attributes["input.value"] = tool_args
    span._attributes["gen_ai.operation.name"] = "execute_tool"
    tool_name = span._attributes.get("gen_ai.tool.name")
    if tool_name:
        span._attributes["wandb.display_name"] = f"calling tool: {tool_name}"
    return span


def get_otlp_headers_from_weave_context() -> dict[str, str]:
    """
    Get OTLP HTTP headers from the current Weave client context.

    Returns:
        dict: A dictionary containing the Authorization and project_id headers.

    Raises:
        RuntimeError: If the entity/project or API key cannot be determined.
    """
    client = require_weave_client()
    entity = getattr(client, "entity", None)
    project = getattr(client, "project", None)
    if not entity or not project:
        raise RuntimeError(
            "Could not determine entity/project from Weave client context."
        )
    project_id = f"{entity}/{project}"
    wandb_context = wandb_api.get_wandb_api_context()
    api_key = getattr(wandb_context, "api_key", None) if wandb_context else None
    if not api_key:
        raise RuntimeError("Could not determine W&B API key from wandb context.")
    auth = base64.b64encode(f"api:{api_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "project_id": project_id,
    }
    return headers


class PydanticAISpanExporter(SpanExporter):
    """
    Custom OpenTelemetry SpanExporter for PydanticAI that injects Weave context headers.

    This exporter processes spans to match Weave's schema and then delegates export
    to the standard OTLPSpanExporter with the correct endpoint and headers.
    """

    def __init__(self) -> None:
        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "https://trace.wandb.ai/otel/v1/traces"
        )
        self._otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint, headers=get_otlp_headers_from_weave_context()
        )

    def export(self, spans: Sequence[trace_sdk.ReadableSpan]) -> Any:
        """
        Process and export spans using the OTLPSpanExporter.

        Args:
            spans: Sequence of OpenTelemetry ReadableSpan objects to export.

        Returns:
            Any: The result of the underlying OTLPSpanExporter export call.
        """
        for span in spans:
            for key in ["all_messages_events", "events"]:
                span = handle_events(key, span._attributes, span)
        spans = [handle_usage(span) for span in spans]
        spans = [handle_tool_call(span) for span in spans]
        spans = [map_events_to_prompt_completion(span) for span in spans]
        return self._otlp_exporter.export(spans)

    def shutdown(self) -> None:
        """Shut down the underlying OTLPSpanExporter."""
        self._otlp_exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Force flush the underlying OTLPSpanExporter.

        Args:
            timeout_millis: Timeout in milliseconds.

        Returns:
            bool: True if flush was successful, False otherwise.
        """
        return self._otlp_exporter.force_flush(timeout_millis)
