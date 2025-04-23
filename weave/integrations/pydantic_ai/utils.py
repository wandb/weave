import os
import json
from opentelemetry.sdk import trace as trace_sdk
from typing import Sequence
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import Event
import base64
from weave.trace.context.weave_client_context import require_weave_client
from weave.wandb_interface import wandb_api


def dicts_to_events(
    event_dicts: Sequence[dict], span: trace_sdk.ReadableSpan
) -> Sequence[Event]:
    event_objs = []
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
    key: str, attrs: dict, span: trace_sdk.ReadableSpan
) -> trace_sdk.ReadableSpan:
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
    messages = []
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
                for k, v in attrs.items():
                    if k in ("tool_calls"):
                        msg_dict[k] = v
                messages.append(msg_dict)
    if messages:
        if len(messages) > 1:
            span._attributes["gen_ai.prompt"] = json.dumps(messages[:-1])
            span._attributes["gen_ai.completion"] = json.dumps(messages[-1])
        else:
            span._attributes["gen_ai.completion"] = json.dumps(messages[0])
    return span


def handle_usage(span: trace_sdk.ReadableSpan) -> trace_sdk.ReadableSpan:
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


def get_otlp_headers_from_weave_context():
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

    def __init__(self):
        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "https://trace.wandb.ai/otel/v1/traces"
        )
        self._otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint, headers=get_otlp_headers_from_weave_context()
        )

    def export(self, spans: Sequence[trace_sdk.ReadableSpan]):
        for span in spans:
            attrs = span._attributes
            for key in ["all_messages_events", "events"]:
                span = handle_events(key, attrs, span)

        spans = [handle_usage(span) for span in spans]
        spans = [handle_tool_call(span) for span in spans]
        spans = [map_events_to_prompt_completion(span) for span in spans]

        return self._otlp_exporter.export(spans)

    def shutdown(self) -> None:
        self._otlp_exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._otlp_exporter.force_flush(timeout_millis)
