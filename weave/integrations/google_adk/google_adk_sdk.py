"""Google ADK (Agent Development Kit) OpenTelemetry integration.

ADK already emits OpenTelemetry spans, but its attributes do not fully cover
the Weave GenAI observability superset (see
``weave/trace_server/agents/semconv.py``). This integration enriches every
ADK span before the OTel SDK exports it so the resulting trace populates the
full set of dedicated columns Weave extracts in
``opentelemetry/genai_extraction.py``.

Concretely, the integration wraps three ADK tracing entry points:

- ``trace_agent_invocation`` — adds ``gen_ai.provider.name``, ``gen_ai.agent.id``,
  and an early ``gen_ai.operation.name``.
- ``trace_tool_call`` — translates ADK's proprietary
  ``gcp.vertex.agent.tool_call_args`` / ``gcp.vertex.agent.tool_response`` keys
  to the canonical ``gen_ai.tool.call.arguments`` / ``gen_ai.tool.call.result``
  attributes and emits ``gen_ai.tool.definitions`` when available.
- ``trace_call_llm`` — derives request parameters
  (``gen_ai.request.{temperature,top_p,max_tokens,frequency_penalty,...}``)
  from the ``LlmRequest.config`` payload, propagates response identifiers and
  model versions, normalises the experimental reasoning/cache token keys, and
  emits ``gen_ai.input.messages`` / ``gen_ai.output.messages`` in the GenAI
  parts model that Weave consumes when ADK is not running with
  ``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental``.

Requires the Weave global ``TracerProvider`` (configured by ``weave.init()``)
or any caller-provided provider that exports to the GenAI OTLP endpoint.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from collections.abc import Iterable
from functools import wraps
from typing import Any

from opentelemetry import trace as otel_trace

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

logger = logging.getLogger(__name__)

_google_adk_patcher: MultiPatcher | None = None

# Keys we set explicitly on enriched spans. Defined as constants because they
# also feed assertions in the sample/integration script.
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GEN_AI_REQUEST_SEED = "gen_ai.request.seed"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GEN_AI_REQUEST_CHOICE_COUNT = "gen_ai.request.choice.count"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_REASONING_TOKENS = "gen_ai.usage.reasoning_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS = "gen_ai.usage.cache_creation.input_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_TYPE = "gen_ai.tool.type"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"
GEN_AI_TOOL_CALL_ARGUMENTS = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"
GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool.definitions"
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"
GEN_AI_OUTPUT_TYPE = "gen_ai.output.type"

ADK_LLM_REQUEST_ATTR = "gcp.vertex.agent.llm_request"
ADK_LLM_RESPONSE_ATTR = "gcp.vertex.agent.llm_response"
ADK_TOOL_CALL_ARGS_ATTR = "gcp.vertex.agent.tool_call_args"
ADK_TOOL_RESPONSE_ATTR = "gcp.vertex.agent.tool_response"


def _safe_set_attribute(span: Any, key: str, value: Any) -> None:
    """Best-effort span.set_attribute that never raises into the user's flow."""
    if span is None or value is None:
        return
    try:
        span.set_attribute(key, value)
    except Exception:
        logger.debug("Failed to set ADK span attribute %s", key, exc_info=True)


def _provider_name_from_env() -> str:
    """Return the Weave-canonical provider name for the running ADK runtime.

    ADK only exposes ``gen_ai.system='gcp.vertex.agent'`` which is too generic
    for the dedicated ``provider_name`` column. We map the standard ADK env
    toggle to ``vertex_ai`` (matches ``GenAiSystemValues.VERTEX_AI``) or
    fall back to ``gemini`` (matches ``GenAiSystemValues.GEMINI``).
    """
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"true", "1"}
    return "vertex_ai" if use_vertex else "gemini"


def _coerce_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        out = [str(v) for v in value if v is not None]
        return out or None
    return None


def _model_dump(obj: Any) -> Any:
    """Convert ``obj`` to a JSON-friendly representation if possible."""
    if obj is None:
        return None
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump(exclude_none=True, mode="json")
        except TypeError:
            try:
                return dump(exclude_none=True)
            except Exception:
                pass
        except Exception:
            pass
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _content_to_parts(content: Any) -> list[dict[str, Any]]:
    """Flatten a ``google.genai.types.Content`` into the GenAI parts model.

    Mirrors the part shapes used in
    ``weave/trace_server/agents/semconv.py`` (text/tool_call/tool_call_response)
    plus passthrough media. ADK's own ``_to_part`` covers the same shapes when
    experimental semconv is enabled; we duplicate the minimal logic so the
    integration works under the default (non-experimental) semconv too.
    """
    parts: list[dict[str, Any]] = []
    raw_parts = getattr(content, "parts", None) or []
    for idx, part in enumerate(raw_parts):
        text = getattr(part, "text", None)
        if text is not None:
            parts.append({"type": "text", "content": text})
            continue
        function_call = getattr(part, "function_call", None)
        if function_call is not None:
            parts.append(
                {
                    "type": "tool_call",
                    "id": getattr(function_call, "id", None)
                    or f"{getattr(function_call, 'name', '') or ''}_{idx}",
                    "name": getattr(function_call, "name", "") or "",
                    "arguments": getattr(function_call, "args", None),
                }
            )
            continue
        function_response = getattr(part, "function_response", None)
        if function_response is not None:
            parts.append(
                {
                    "type": "tool_call_response",
                    "id": getattr(function_response, "id", None)
                    or f"{getattr(function_response, 'name', '') or ''}_{idx}",
                    "response": getattr(function_response, "response", None),
                }
            )
            continue
        inline_data = getattr(part, "inline_data", None)
        if inline_data is not None:
            parts.append(
                {
                    "type": "blob",
                    "mime_type": getattr(inline_data, "mime_type", "") or "",
                    # Bytes payloads are dropped — span attributes must be
                    # primitive types, and Weave already stores blobs out of band.
                }
            )
            continue
        file_data = getattr(part, "file_data", None)
        if file_data is not None:
            parts.append(
                {
                    "type": "file",
                    "mime_type": getattr(file_data, "mime_type", "") or "",
                    "uri": getattr(file_data, "file_uri", "") or "",
                }
            )
            continue
    return parts


def _adk_role_to_weave(role: str | None) -> str:
    if role == "user":
        return "user"
    if role == "model":
        return "assistant"
    return role or ""


def _llm_request_to_input_messages(llm_request: Any) -> list[dict[str, Any]]:
    contents = getattr(llm_request, "contents", None) or []
    out: list[dict[str, Any]] = []
    for content in contents:
        out.append(
            {
                "role": _adk_role_to_weave(getattr(content, "role", None)),
                "parts": _content_to_parts(content),
            }
        )
    return out


def _llm_response_to_output_message(llm_response: Any) -> dict[str, Any] | None:
    content = getattr(llm_response, "content", None)
    if content is None:
        return None
    finish_reason = getattr(llm_response, "finish_reason", None)
    finish_str = ""
    if finish_reason is not None:
        finish_str = getattr(finish_reason, "value", None) or getattr(
            finish_reason, "name", None
        ) or str(finish_reason)
        finish_str = finish_str.lower()
    return {
        "role": _adk_role_to_weave(getattr(content, "role", None)) or "assistant",
        "parts": _content_to_parts(content),
        "finish_reason": finish_str,
    }


def _system_instructions_to_text(config: Any) -> list[str]:
    """Collect plain-text system instructions from an ADK LlmRequest.config.

    ADK accepts ``str``, ``Content``, or ``list[Content]`` for
    ``system_instruction``; we flatten everything to a list of strings.
    """
    instruction = getattr(config, "system_instruction", None)
    if not instruction:
        return []
    if isinstance(instruction, str):
        return [instruction]
    out: list[str] = []
    candidates = instruction if isinstance(instruction, list) else [instruction]
    for cand in candidates:
        text = getattr(cand, "text", None)
        if text:
            out.append(text)
            continue
        parts = getattr(cand, "parts", None) or []
        for part in parts:
            t = getattr(part, "text", None)
            if t:
                out.append(t)
    return out


def _tool_definitions(config: Any) -> list[dict[str, Any]]:
    """Best-effort extraction of tool definitions from LlmRequest.config.tools."""
    tools = getattr(config, "tools", None) or []
    defs: list[dict[str, Any]] = []
    for tool in tools:
        function_declarations = getattr(tool, "function_declarations", None) or []
        for fd in function_declarations:
            defs.append(
                {
                    "name": getattr(fd, "name", "") or "",
                    "description": getattr(fd, "description", "") or "",
                    "parameters": _model_dump(getattr(fd, "parameters", None)),
                    "type": "function",
                }
            )
    return defs


def _set_llm_request_attributes(span: Any, llm_request: Any) -> None:
    config = getattr(llm_request, "config", None)
    if config is None:
        return

    # Sampling / decoding parameters — ADK only emits top_p and max_tokens
    # natively, so we fill in the remaining ones the Weave schema cares about.
    temperature = getattr(config, "temperature", None)
    if temperature is not None:
        _safe_set_attribute(span, GEN_AI_REQUEST_TEMPERATURE, float(temperature))

    top_p = getattr(config, "top_p", None)
    if top_p is not None:
        _safe_set_attribute(span, GEN_AI_REQUEST_TOP_P, float(top_p))

    max_tokens = getattr(config, "max_output_tokens", None)
    if max_tokens is not None:
        _safe_set_attribute(span, GEN_AI_REQUEST_MAX_TOKENS, int(max_tokens))

    frequency_penalty = getattr(config, "frequency_penalty", None)
    if frequency_penalty is not None:
        _safe_set_attribute(
            span, GEN_AI_REQUEST_FREQUENCY_PENALTY, float(frequency_penalty)
        )

    presence_penalty = getattr(config, "presence_penalty", None)
    if presence_penalty is not None:
        _safe_set_attribute(
            span, GEN_AI_REQUEST_PRESENCE_PENALTY, float(presence_penalty)
        )

    seed = getattr(config, "seed", None)
    if seed is not None:
        _safe_set_attribute(span, GEN_AI_REQUEST_SEED, int(seed))

    stop_sequences = _coerce_str_list(getattr(config, "stop_sequences", None))
    if stop_sequences:
        _safe_set_attribute(span, GEN_AI_REQUEST_STOP_SEQUENCES, stop_sequences)

    candidate_count = getattr(config, "candidate_count", None)
    if candidate_count is not None:
        _safe_set_attribute(span, GEN_AI_REQUEST_CHOICE_COUNT, int(candidate_count))

    # System instructions, input messages, and tool definitions are GenAI
    # "Opt-In" attributes; ADK only emits them under
    # ``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`` with
    # ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` enabled. Emit them
    # unconditionally so Weave's dedicated columns are always populated.
    system_instructions = _system_instructions_to_text(config)
    if system_instructions:
        _safe_set_attribute(
            span,
            GEN_AI_SYSTEM_INSTRUCTIONS,
            _json_dumps([{"type": "text", "content": s} for s in system_instructions]),
        )

    input_messages = _llm_request_to_input_messages(llm_request)
    if input_messages:
        _safe_set_attribute(span, GEN_AI_INPUT_MESSAGES, _json_dumps(input_messages))

    tool_defs = _tool_definitions(config)
    if tool_defs:
        _safe_set_attribute(span, GEN_AI_TOOL_DEFINITIONS, _json_dumps(tool_defs))


def _set_llm_response_attributes(span: Any, llm_response: Any) -> None:
    # ADK's LlmResponse exposes the per-call identifier as ``interaction_id``
    # (see ``google.adk.models.llm_response``); other in-house response shapes
    # use ``response_id`` or ``id``. Probe all three so this works against
    # both real ADK objects and ad-hoc mocks.
    response_id = (
        getattr(llm_response, "response_id", None)
        or getattr(llm_response, "interaction_id", None)
        or getattr(llm_response, "id", None)
    )
    if response_id:
        _safe_set_attribute(span, GEN_AI_RESPONSE_ID, str(response_id))

    # ADK doesn't always expose the response model directly; mirror what it
    # records on llm_response when present (Gemini exposes ``model_version``).
    response_model = (
        getattr(llm_response, "model_version", None)
        or getattr(llm_response, "model", None)
        or ""
    )
    if response_model:
        _safe_set_attribute(span, GEN_AI_RESPONSE_MODEL, str(response_model))

    output_message = _llm_response_to_output_message(llm_response)
    if output_message is not None:
        _safe_set_attribute(
            span, GEN_AI_OUTPUT_MESSAGES, _json_dumps([output_message])
        )
        _safe_set_attribute(span, GEN_AI_OUTPUT_TYPE, "text")

    usage = getattr(llm_response, "usage_metadata", None)
    if usage is not None:
        # ADK already emits prompt/candidates tokens via legacy keys; we add
        # the canonical reasoning + cache token columns that the Weave schema
        # exposes but ADK either omits or stashes under the experimental keys.
        thoughts = getattr(usage, "thoughts_token_count", None)
        if thoughts is not None:
            _safe_set_attribute(span, GEN_AI_USAGE_REASONING_TOKENS, int(thoughts))
        cached = getattr(usage, "cached_content_token_count", None)
        if cached is not None:
            _safe_set_attribute(
                span, GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS, int(cached)
            )
        cache_creation = getattr(usage, "cache_creation_token_count", None)
        if cache_creation is not None:
            _safe_set_attribute(
                span,
                GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
                int(cache_creation),
            )


def _wrap_trace_agent_invocation(original: Any) -> Any:
    @wraps(original)
    def wrapper(span: Any, agent: Any, ctx: Any) -> Any:
        result = original(span, agent, ctx)
        # ADK already sets agent_name, agent_description and conversation_id.
        # Layer in the Weave-superset fields it does not emit natively.
        _safe_set_attribute(span, GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _safe_set_attribute(span, GEN_AI_OPERATION_NAME, "invoke_agent")
        invocation_id = getattr(ctx, "invocation_id", None)
        if invocation_id:
            _safe_set_attribute(span, GEN_AI_AGENT_ID, str(invocation_id))
        model = getattr(agent, "model", None)
        if isinstance(model, str) and model:
            _safe_set_attribute(span, GEN_AI_REQUEST_MODEL, model)
        return result

    return wrapper


def _wrap_trace_tool_call(original: Any) -> Any:
    @wraps(original)
    def wrapper(
        tool: Any,
        args: dict[str, Any],
        function_response_event: Any | None,
        error: Exception | None = None,
        span: Any | None = None,
    ) -> Any:
        result = original(
            tool, args, function_response_event, error=error, span=span
        )
        # ``trace.get_current_span()`` mirrors ADK's own resolution logic
        # when the caller doesn't pass ``span`` explicitly.
        target_span = span if span is not None else otel_trace.get_current_span()

        _safe_set_attribute(target_span, GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _safe_set_attribute(target_span, GEN_AI_TOOL_CALL_ARGUMENTS, _json_dumps(args))

        if function_response_event is not None:
            tool_response: Any = None
            content = getattr(function_response_event, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            if parts:
                response_obj = getattr(parts[0], "function_response", None)
                if response_obj is not None:
                    tool_response = getattr(response_obj, "response", None)
            if tool_response is not None:
                _safe_set_attribute(
                    target_span, GEN_AI_TOOL_CALL_RESULT, _json_dumps(tool_response)
                )

        return result

    return wrapper


def _wrap_trace_call_llm(original: Any) -> Any:
    """Enrich the legacy ``trace_call_llm`` path.

    Pre-ADK-1.36 (and the ``use_generate_content_span`` deprecated path) emit
    LLM spans via ``trace_call_llm``. The modern runner uses
    ``use_inference_span`` + ``trace_inference_result`` instead — see
    ``_wrap_set_common_generate_content_attributes`` and
    ``_wrap_trace_inference_result`` below.
    """

    @wraps(original)
    def wrapper(
        invocation_context: Any,
        event_id: str,
        llm_request: Any,
        llm_response: Any,
        span: Any | None = None,
    ) -> Any:
        result = original(invocation_context, event_id, llm_request, llm_response, span=span)
        target_span = span if span is not None else otel_trace.get_current_span()

        _safe_set_attribute(target_span, GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _safe_set_attribute(target_span, GEN_AI_OPERATION_NAME, "chat")
        agent = getattr(invocation_context, "agent", None)
        if agent is not None:
            agent_name = getattr(agent, "name", None)
            if agent_name:
                _safe_set_attribute(target_span, GEN_AI_AGENT_NAME, agent_name)
            agent_description = getattr(agent, "description", None)
            if agent_description:
                _safe_set_attribute(
                    target_span, GEN_AI_AGENT_DESCRIPTION, agent_description
                )
        session = getattr(invocation_context, "session", None)
        session_id = getattr(session, "id", None) if session is not None else None
        if session_id:
            _safe_set_attribute(target_span, GEN_AI_CONVERSATION_ID, str(session_id))

        _set_llm_request_attributes(target_span, llm_request)
        _set_llm_response_attributes(target_span, llm_response)
        return result

    return wrapper


def _wrap_set_common_generate_content_attributes(original: Any) -> Any:
    """Enrich the modern ``use_inference_span`` request-time entry point.

    ADK's ``_set_common_generate_content_attributes`` runs once when the
    ``generate_content`` span is opened. It sets ``gen_ai.operation.name`` /
    ``gen_ai.request.model`` but leaves the parts-model messages, system
    instructions, tool definitions and decoding parameters off the span
    (they only land in spans when ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT``
    opts in). Weave wants them every time, so we fill them in here.
    """

    @wraps(original)
    def wrapper(span: Any, llm_request: Any, common_attributes: Any) -> Any:
        result = original(span, llm_request, common_attributes)
        _safe_set_attribute(span, GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _set_llm_request_attributes(span, llm_request)
        return result

    return wrapper


def _wrap_trace_inference_result(original: Any) -> Any:
    """Enrich the modern ``use_inference_span`` response-time entry point.

    ``trace_inference_result`` is ADK's replacement for ``trace_call_llm``'s
    response-side logic. ADK sets ``finish_reasons`` and the usage tokens
    here but leaves response model/id, output messages and reasoning/cache
    tokens off. The Weave OTLv2 columns expect all of those, so we patch.
    """

    @wraps(original)
    def wrapper(span: Any, llm_response: Any) -> Any:
        result = original(span, llm_response)
        # ADK's helper accepts either a ``Span`` or a ``GenerateContentSpan``;
        # unwrap so ``set_attribute`` lands on the real span object.
        target_span = getattr(span, "span", span)
        _safe_set_attribute(
            target_span, GEN_AI_PROVIDER_NAME, _provider_name_from_env()
        )
        _set_llm_response_attributes(target_span, llm_response)
        return result

    return wrapper


def get_google_adk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """Return the patcher that enriches ADK OTel spans with the OTLv2 superset.

    The patcher hooks ADK's tracing functions in-place; the spans created by
    ADK still go through the global OTel TracerProvider so they ride whichever
    BatchSpanProcessor was configured by ``weave.init()`` (or by the user).
    """
    global _google_adk_patcher  # noqa: PLW0603

    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()
    if _google_adk_patcher is not None:
        return _google_adk_patcher

    base_module = "google.adk.telemetry.tracing"

    def _import_tracing() -> Any:
        return importlib.import_module(base_module)

    _google_adk_patcher = MultiPatcher(
        [
            SymbolPatcher(
                _import_tracing,
                "trace_agent_invocation",
                _wrap_trace_agent_invocation,
            ),
            SymbolPatcher(
                _import_tracing,
                "trace_tool_call",
                _wrap_trace_tool_call,
            ),
            # Legacy LLM-call path (pre-1.36 ``use_generate_content_span``).
            SymbolPatcher(
                _import_tracing,
                "trace_call_llm",
                _wrap_trace_call_llm,
            ),
            # Modern LLM-call path (``use_inference_span`` /
            # ``trace_inference_result``) used by ADK's runner today.
            SymbolPatcher(
                _import_tracing,
                "_set_common_generate_content_attributes",
                _wrap_set_common_generate_content_attributes,
            ),
            SymbolPatcher(
                _import_tracing,
                "trace_inference_result",
                _wrap_trace_inference_result,
            ),
        ]
    )
    return _google_adk_patcher
