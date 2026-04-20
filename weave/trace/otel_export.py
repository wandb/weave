from __future__ import annotations

import datetime
import json
import logging
import threading
from typing import Any

from weave import version

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode
except ImportError:  # pragma: no cover - exercised only in envs without OTLP deps
    otel_trace = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    SimpleSpanProcessor = None
    SpanKind = None
    Status = None
    StatusCode = None

logger = logging.getLogger(__name__)

_OTEL_DEPS_MISSING = any(
    dependency is None
    for dependency in (
        otel_trace,
        OTLPSpanExporter,
        Resource,
        TracerProvider,
        SimpleSpanProcessor,
        SpanKind,
        Status,
        StatusCode,
    )
)


def _op_name_from_ref(ref: str) -> str:
    return ref.rsplit("/", maxsplit=1)[-1].split(":", maxsplit=1)[0]


def _to_unix_nanos(value: datetime.datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _normalize_attr_value(value: Any) -> str | bool | int | float | list[Any] | None:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list) and all(
        isinstance(item, (str, bool, int, float)) for item in value
    ):
        return value
    return _json_dumps(value)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _extract_prompt(inputs: dict[str, Any]) -> str | None:
    for key in ("messages", "contents", "input", "prompt"):
        if key in inputs and inputs[key] is not None:
            value = inputs[key]
            if isinstance(value, str):
                return value
            return _json_dumps(value)
    return None


def _extract_system_instructions(inputs: dict[str, Any]) -> str | None:
    system = _get_first(inputs, "system", "system_instruction", "instructions")
    if isinstance(system, str):
        return system

    messages = inputs.get("messages")
    if isinstance(messages, list):
        system_messages = [
            message
            for message in messages
            if isinstance(message, dict) and message.get("role") == "system"
        ]
        if system_messages:
            return _json_dumps(system_messages)
    return None


def _extract_completion(output: dict[str, Any]) -> str | None:
    for key in ("output_text", "text", "content", "completion"):
        value = output.get(key)
        if isinstance(value, str):
            return value

    choices = output.get("choices")
    if isinstance(choices, list):
        extracted: list[str] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                extracted.append(message["content"])
            elif isinstance(choice.get("text"), str):
                extracted.append(choice["text"])
        if extracted:
            return "\n".join(extracted)

    candidates = output.get("candidates")
    if isinstance(candidates, list):
        texts: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    texts.extend(
                        part["text"]
                        for part in parts
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
        if texts:
            return "\n".join(texts)

    if output:
        return _json_dumps(output)
    return None


def _extract_finish_reasons(output: dict[str, Any]) -> list[str] | None:
    finish_reason = output.get("finish_reason")
    if isinstance(finish_reason, str):
        return [finish_reason]

    choices = output.get("choices")
    if isinstance(choices, list):
        finish_reasons = [
            choice["finish_reason"]
            for choice in choices
            if isinstance(choice, dict) and isinstance(choice.get("finish_reason"), str)
        ]
        if finish_reasons:
            return finish_reasons

    candidates = output.get("candidates")
    if isinstance(candidates, list):
        finish_reasons = [
            candidate["finishReason"]
            for candidate in candidates
            if isinstance(candidate, dict)
            and isinstance(candidate.get("finishReason"), str)
        ]
        if finish_reasons:
            return finish_reasons

    stop_reason = output.get("stop_reason")
    if isinstance(stop_reason, str):
        return [stop_reason]

    return None


def _extract_usage(
    output: dict[str, Any], summary: dict[str, Any], request_model: str | None
) -> dict[str, int]:
    usage_sources: list[dict[str, Any]] = []

    summary_usage = summary.get("usage")
    if isinstance(summary_usage, dict):
        if request_model and isinstance(summary_usage.get(request_model), dict):
            usage_sources.append(summary_usage[request_model])
        usage_sources.extend(
            value for value in summary_usage.values() if isinstance(value, dict)
        )

    output_usage = output.get("usage")
    if isinstance(output_usage, dict):
        usage_sources.append(output_usage)
    output_usage_metadata = output.get("usageMetadata")
    if isinstance(output_usage_metadata, dict):
        usage_sources.append(output_usage_metadata)

    mappings = {
        "gen_ai.usage.prompt_tokens": ("prompt_tokens", "promptTokenCount"),
        "gen_ai.usage.completion_tokens": (
            "completion_tokens",
            "candidatesTokenCount",
        ),
        "gen_ai.usage.total_tokens": ("total_tokens", "totalTokenCount"),
        "gen_ai.usage.input_tokens": ("input_tokens", "inputTokenCount"),
        "gen_ai.usage.output_tokens": ("output_tokens", "outputTokenCount"),
    }
    extracted: dict[str, int] = {}
    for attr_name, keys in mappings.items():
        for source in usage_sources:
            value = _get_first(source, *keys)
            if isinstance(value, int):
                extracted[attr_name] = value
                break

    return extracted


def _extract_model(
    inputs: dict[str, Any], output: dict[str, Any], summary: dict[str, Any]
) -> tuple[str | None, str | None]:
    request_model = _get_first(inputs, "model", "model_name")
    response_model = _get_first(output, "model", "modelVersion", "response_model")

    if response_model is None:
        summary_usage = summary.get("usage")
        if isinstance(summary_usage, dict) and summary_usage:
            first_key = next(iter(summary_usage))
            if isinstance(first_key, str):
                response_model = first_key

    request_model_str = request_model if isinstance(request_model, str) else None
    response_model_str = response_model if isinstance(response_model, str) else None
    return request_model_str, response_model_str


def _infer_provider(op_name: str) -> str | None:
    normalized = op_name.lower()
    if normalized.startswith("openai."):
        return "openai"
    if normalized.startswith("anthropic."):
        return "anthropic"
    if normalized.startswith("google.genai.") or normalized.startswith(
        "google.generativeai."
    ):
        return "google"
    if normalized.startswith("cohere."):
        return "cohere"
    if normalized.startswith("mistral.") or normalized.startswith("mistralai."):
        return "mistral"
    return None


def _infer_operation_name(op_name: str, inputs: dict[str, Any]) -> str:
    normalized = op_name.lower()
    if "embedd" in normalized:
        return "embeddings"
    if "moderat" in normalized:
        return "moderation"
    if "image" in normalized or "imagen" in normalized:
        return "image_generation"
    if "count_tokens" in normalized:
        return "token_count"
    if "responses" in normalized or "chat" in normalized:
        return "chat"
    if "completion" in normalized:
        return "text_completion"
    if any(key in inputs for key in ("messages", "contents")):
        return "chat"
    return "execute"


class OTelCallExporter:
    def __init__(self, entity: str, project: str, project_id: str) -> None:
        if _OTEL_DEPS_MISSING:
            raise ImportError(
                "OpenTelemetry OTLP dependencies are required when "
                "UserSettings(export_otel=True). Install weave[otel] to "
                "enable OTLP export."
            )

        self.entity = entity
        self.project = project
        self.project_id = project_id
        self._lock = threading.Lock()
        self._spans: dict[str, Any] = {}
        resource = Resource.create(
            {
                "service.name": "weave",
                "weave.entity": entity,
                "weave.project": project,
                "weave.project_id": project_id,
                "weave.sdk.version": version.VERSION,
            }
        )
        self._provider = TracerProvider(resource=resource)
        self._provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
        self._tracer = self._provider.get_tracer("weave.export_otel", version.VERSION)

    def start_call(
        self,
        *,
        call_id: str,
        trace_id: str,
        parent_id: str | None,
        op_name_ref: str,
        display_name: str | None,
        started_at: datetime.datetime,
        inputs: dict[str, Any],
        attributes: dict[str, Any],
        thread_id: str | None,
        turn_id: str | None,
        wb_run_id: str | None,
        wb_run_step: int | None,
    ) -> None:
        inputs = _as_dict(inputs)
        attributes = _as_dict(attributes)
        parsed_op_name = _op_name_from_ref(op_name_ref)
        provider = _infer_provider(parsed_op_name)
        parent_context = None
        with self._lock:
            if parent_id is not None and parent_id in self._spans:
                parent_context = otel_trace.set_span_in_context(self._spans[parent_id])

        span_kind = SpanKind.CLIENT if provider else SpanKind.INTERNAL
        span = self._tracer.start_span(
            name=parsed_op_name,
            context=parent_context,
            kind=span_kind,
            start_time=_to_unix_nanos(started_at),
        )

        request_model, response_model = _extract_model(inputs, {}, {})
        span_attributes: dict[str, Any] = {
            "weave.call_id": call_id,
            "weave.trace_id": trace_id,
            "weave.op_name": parsed_op_name,
            "wandb.display_name": display_name,
            "gen_ai.provider.name": provider,
            "gen_ai.operation.name": _infer_operation_name(parsed_op_name, inputs),
            "gen_ai.request.model": request_model,
            "gen_ai.response.model": response_model,
            "gen_ai.prompt": _extract_prompt(inputs),
            "gen_ai.system_instructions": _extract_system_instructions(inputs),
            "gen_ai.conversation.id": thread_id,
            "wandb.wb_run_id": wb_run_id,
            "wandb.wb_run_step": wb_run_step,
        }
        if turn_id == call_id and thread_id is not None:
            span_attributes["wandb.is_turn"] = True

        for key, value in attributes.items():
            if key.startswith("_weave"):
                continue
            span_attributes[f"weave.attributes.{key}"] = value

        span.set_attributes(
            {
                key: normalized
                for key, value in span_attributes.items()
                if (normalized := _normalize_attr_value(value)) is not None
            }
        )

        with self._lock:
            self._spans[call_id] = span

    def finish_call(
        self,
        *,
        call_id: str,
        ended_at: datetime.datetime,
        output: Any,
        summary: dict[str, Any],
        exception: BaseException | None,
        exception_str: str | None,
        wb_run_step_end: int | None,
    ) -> None:
        with self._lock:
            span = self._spans.pop(call_id, None)

        if span is None:
            logger.warning("Missing OTel span for call %s", call_id)
            return

        output_dict = _as_dict(output)
        summary = _as_dict(summary)

        request_model, response_model = _extract_model({}, output_dict, summary)
        finish_reasons = _extract_finish_reasons(output_dict)
        usage = _extract_usage(output_dict, summary, request_model or response_model)
        completion = _extract_completion(output_dict)
        if completion is None and output is not None:
            normalized_output = _normalize_attr_value(output)
            if isinstance(normalized_output, str):
                completion = normalized_output

        span_attributes: dict[str, Any] = {
            "gen_ai.response.id": _get_first(output_dict, "id", "response_id"),
            "gen_ai.response.model": response_model,
            "gen_ai.completion": completion,
            "gen_ai.response.finish_reasons": finish_reasons,
            "wandb.wb_run_step_end": wb_run_step_end,
            "weave.summary": summary or None,
        }
        span_attributes.update(usage)

        span.set_attributes(
            {
                key: normalized
                for key, value in span_attributes.items()
                if (normalized := _normalize_attr_value(value)) is not None
            }
        )

        if exception is not None:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, exception_str))
        else:
            span.set_status(Status(StatusCode.OK))
        span.end(end_time=_to_unix_nanos(ended_at))

    def force_flush(self) -> None:
        self._provider.force_flush()

    def shutdown(self) -> None:
        self._provider.shutdown()
