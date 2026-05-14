"""Google ADK (Agent Development Kit) OpenTelemetry integration.

ADK already emits OpenTelemetry spans, but its attributes do not fully
cover the Weave GenAI observability superset (see
``weave/trace_server/agents/semconv.py``). This integration enriches the
spans ADK emits so the resulting trace populates every dedicated column
Weave extracts in ``opentelemetry/genai_extraction.py``.

The integration wraps a handful of ADK tracing entry points:

- ``trace_agent_invocation`` adds ``gen_ai.provider.name`` /
  ``gen_ai.agent.id`` / ``gen_ai.operation.name`` to invoke_agent spans.
- ``trace_tool_call`` translates ADK's proprietary
  ``gcp.vertex.agent.tool_call_args`` and ``tool_response`` payloads to
  the canonical ``gen_ai.tool.call.arguments`` / ``...result`` keys.
- ``trace_call_llm`` (legacy) and the modern ``use_inference_span``
  pair (``_set_common_generate_content_attributes`` +
  ``trace_inference_result``) fill in request parameters, response
  identifiers, message arrays, system instructions, tool definitions
  and the cache + reasoning token counts.

Requires the Weave global ``TracerProvider`` (configured by
``weave.init()``) or any caller-provided provider that exports to the
GenAI OTLP endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from functools import wraps
from typing import TYPE_CHECKING, Any

# ADK imports are top-level. This module is only loaded by ``patch.py`` once
# the import hook fires on ``google.adk`` (or once a caller invokes
# ``weave.integrations.patch_google_adk()``), so ADK is always installed
# by the time we get here.
import google.adk as _adk
from google.adk.telemetry import tracing as _adk_tracing

# ADK exports the tool-definition discriminator from its experimental
# semconv module. Importing it lets the integration stay in lock-step with
# whatever string ADK uses on the wire (currently ``"function"``).
from google.adk.telemetry._experimental_semconv import FUNCTION_TOOL_DEFINITION_TYPE
from opentelemetry import trace as otel_trace

# GenAI semconv key constants. The OpenTelemetry semconv package is the
# upstream source ADK itself imports from. Every key the integration
# emits except one lives in OTel.
#
# The exception is ``gen_ai.usage.reasoning_tokens``. The upstream spec
# defines a reasoning-tokens attribute (PR
# https://github.com/open-telemetry/semantic-conventions/pull/3383, merged
# 2026-04-27, original request
# https://github.com/open-telemetry/semantic-conventions/issues/3194), but:
#
#   1. The merged name is ``gen_ai.usage.reasoning.output_tokens``, not
#      ``gen_ai.usage.reasoning_tokens``. Weave's server-side semconv
#      catalog (``weave/trace_server/agents/semconv.py``) currently
#      extracts the latter, so emitting the former wouldn't land in the
#      ``reasoning_tokens`` column.
#   2. The OTel Python package (0.62b1, our current floor) shipped three
#      days before the PR merged, so the constant isn't in any release
#      yet. The GenAI semconv has also since moved to a dedicated repo
#      (https://github.com/open-telemetry/semantic-conventions-genai)
#      that the Python codegen will start consuming.
#
# When Weave's server-side catalog adopts the canonical
# ``gen_ai.usage.reasoning.output_tokens`` name and the OTel Python
# package exposes the constant, this whole gap-fill should disappear in
# favour of a direct import alongside the others.
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_CHOICE_COUNT,
    GEN_AI_REQUEST_FREQUENCY_PENALTY,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_PRESENCE_PENALTY,
    GEN_AI_REQUEST_SEED,
    GEN_AI_REQUEST_STOP_SEQUENCES,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_RESULT,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GenAiOperationNameValues,
    GenAiOutputTypeValues,
    GenAiSystemValues,
)

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace_server.agents.semconv import USAGE_REASONING_TOKENS

# Only ``gen_ai.usage.reasoning_tokens`` is not yet upstreamed to the OTel
# semconv package; Weave's server-side catalog defines its gen_ai alias.
GEN_AI_USAGE_REASONING_TOKENS = USAGE_REASONING_TOKENS.gen_ai_alias

# Probe for the modern ``use_inference_span`` request-time hook. ADK
# names it with an underscore today; if a future release renames it we
# warn once at patch time and skip just that one hook. ``from X import Y``
# raises ``ImportError`` when ``Y`` is missing, so no ``hasattr`` needed.
_ADK_PRIVATE_REQUEST_HOOK = "_set_common_generate_content_attributes"
try:
    from google.adk.telemetry.tracing import (  # noqa: F401
        _set_common_generate_content_attributes,
    )

    _HAS_PRIVATE_REQUEST_HOOK = True
except ImportError:
    _HAS_PRIVATE_REQUEST_HOOK = False

if TYPE_CHECKING:
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events.event import Event
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools.base_tool import BaseTool
    from opentelemetry.trace import Span

logger = logging.getLogger(__name__)

_google_adk_patcher: MultiPatcher | None = None


# ADK reads this env var to decide between Vertex AI and Gemini at runtime.
# It is not exported as a named constant by any Google library — ADK itself
# uses the literal — so we keep the bare string but pin it as a module-level
# constant for one source of truth.
_USE_VERTEXAI_ENV_VAR = "GOOGLE_GENAI_USE_VERTEXAI"


def _provider_name_from_env() -> str:
    """Return the Weave-canonical provider name for the running ADK runtime.

    ADK only exposes ``gen_ai.system='gcp.vertex.agent'``, which is too
    generic for the dedicated ``provider_name`` column. We mirror ADK's
    own ``_guess_gemini_system_name`` and emit the upstream
    ``GenAiSystemValues`` value so the wire format matches the canonical
    semconv enum.
    """
    use_vertex = os.getenv(_USE_VERTEXAI_ENV_VAR, "").lower() in {"true", "1"}
    return (
        GenAiSystemValues.VERTEX_AI.value
        if use_vertex
        else GenAiSystemValues.GEMINI.value
    )


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _content_to_parts(content: Any) -> list[dict[str, Any]]:
    """Flatten a ``google.genai.types.Content`` into the GenAI parts model.

    The shapes mirror the ones in ``weave/trace_server/agents/semconv.py``
    (text / tool_call / tool_call_response). ADK's own ``_to_part`` covers
    the same shapes when experimental semconv is opted in; we duplicate the
    minimal logic so the integration works under the default semconv too.
    """
    parts: list[dict[str, Any]] = []
    for idx, part in enumerate(content.parts or []):
        if part.text is not None:
            parts.append({"type": "text", "content": part.text})
            continue
        fc = part.function_call
        if fc is not None:
            parts.append(
                {
                    "type": "tool_call",
                    "id": fc.id or f"{fc.name or ''}_{idx}",
                    "name": fc.name or "",
                    "arguments": fc.args,
                }
            )
            continue
        fr = part.function_response
        if fr is not None:
            parts.append(
                {
                    "type": "tool_call_response",
                    "id": fr.id or f"{fr.name or ''}_{idx}",
                    "response": fr.response,
                }
            )
            continue
        if part.inline_data is not None:
            # Bytes payloads aren't span-attribute-safe; Weave already
            # stores blobs out of band.
            parts.append(
                {"type": "blob", "mime_type": part.inline_data.mime_type or ""}
            )
            continue
        if part.file_data is not None:
            parts.append(
                {
                    "type": "file",
                    "mime_type": part.file_data.mime_type or "",
                    "uri": part.file_data.file_uri or "",
                }
            )
    return parts


def _adk_role_to_weave(role: str | None) -> str:
    if role == "user":
        return "user"
    if role == "model":
        return "assistant"
    return role or ""


def _llm_request_input_messages(llm_request: LlmRequest) -> list[dict[str, Any]]:
    return [
        {
            "role": _adk_role_to_weave(content.role),
            "parts": _content_to_parts(content),
        }
        for content in (llm_request.contents or [])
    ]


def _llm_response_output_message(llm_response: LlmResponse) -> dict[str, Any] | None:
    if llm_response.content is None:
        return None
    finish_str = ""
    finish_reason = llm_response.finish_reason
    if finish_reason is not None:
        # FinishReason is an Enum; ``.value`` is the wire form, fall back to
        # ``.name`` for older enum styles. No introspection needed beyond
        # the standard enum surface.
        finish_str = str(finish_reason.value or finish_reason.name).lower()
    return {
        "role": _adk_role_to_weave(llm_response.content.role) or "assistant",
        "parts": _content_to_parts(llm_response.content),
        "finish_reason": finish_str,
    }


def _system_instructions_to_text(config: Any) -> list[str]:
    """Collect plain text from ``LlmRequest.config.system_instruction``.

    ADK accepts ``str``, ``Content``, or ``list[Content]``. We flatten to
    a list of strings so it serialises cleanly into the GenAI parts model.
    """
    instruction = config.system_instruction
    if not instruction:
        return []
    if isinstance(instruction, str):
        return [instruction]
    candidates = instruction if isinstance(instruction, list) else [instruction]
    out: list[str] = []
    for cand in candidates:
        # ``Content`` exposes ``parts``; a bare ``Part`` exposes ``text``.
        # Try them in order; let AttributeError surface if neither matches —
        # that means the caller passed an unrecognised shape.
        try:
            parts = cand.parts
        except AttributeError:
            parts = None
        if parts:
            out.extend(p.text for p in parts if p.text)
            continue
        try:
            text = cand.text
        except AttributeError:
            continue
        if text:
            out.append(text)
    return out


def _tool_definitions(config: Any) -> list[dict[str, Any]]:
    """Extract tool definitions from ``LlmRequest.config.tools``."""
    defs: list[dict[str, Any]] = []
    for tool in config.tools or []:
        for fd in tool.function_declarations or []:
            parameters = None
            if fd.parameters is not None:
                parameters = fd.parameters.model_dump(exclude_none=True, mode="json")
            defs.append(
                {
                    "name": fd.name or "",
                    "description": fd.description or "",
                    "parameters": parameters,
                    "type": FUNCTION_TOOL_DEFINITION_TYPE,
                }
            )
    return defs


def _set_llm_request_attributes(span: Span, llm_request: LlmRequest) -> None:
    config = llm_request.config
    if config is None:
        return

    # ADK only emits ``top_p`` / ``max_output_tokens`` from config natively;
    # fill in the remaining decoding parameters the Weave schema cares about.
    if config.temperature is not None:
        span.set_attribute(GEN_AI_REQUEST_TEMPERATURE, float(config.temperature))
    if config.top_p is not None:
        span.set_attribute(GEN_AI_REQUEST_TOP_P, float(config.top_p))
    if config.max_output_tokens is not None:
        span.set_attribute(GEN_AI_REQUEST_MAX_TOKENS, int(config.max_output_tokens))
    if config.frequency_penalty is not None:
        span.set_attribute(
            GEN_AI_REQUEST_FREQUENCY_PENALTY, float(config.frequency_penalty)
        )
    if config.presence_penalty is not None:
        span.set_attribute(
            GEN_AI_REQUEST_PRESENCE_PENALTY, float(config.presence_penalty)
        )
    if config.seed is not None:
        span.set_attribute(GEN_AI_REQUEST_SEED, int(config.seed))
    if config.stop_sequences:
        span.set_attribute(GEN_AI_REQUEST_STOP_SEQUENCES, list(config.stop_sequences))
    if config.candidate_count is not None:
        span.set_attribute(
            GEN_AI_REQUEST_CHOICE_COUNT, int(config.candidate_count)
        )

    # System instructions, input messages and tool definitions are GenAI
    # "Opt-In" attributes — ADK only emits them under
    # ``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`` with
    # ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` enabled.
    # Emit them unconditionally so Weave's dedicated columns are always
    # populated.
    system_instructions = _system_instructions_to_text(config)
    if system_instructions:
        span.set_attribute(
            GEN_AI_SYSTEM_INSTRUCTIONS,
            _json_dumps([{"type": "text", "content": s} for s in system_instructions]),
        )

    input_messages = _llm_request_input_messages(llm_request)
    if input_messages:
        span.set_attribute(GEN_AI_INPUT_MESSAGES, _json_dumps(input_messages))

    tool_defs = _tool_definitions(config)
    if tool_defs:
        span.set_attribute(GEN_AI_TOOL_DEFINITIONS, _json_dumps(tool_defs))


def _set_llm_response_attributes(span: Span, llm_response: LlmResponse) -> None:
    # ADK's ``LlmResponse.interaction_id`` is the response identifier.
    if llm_response.interaction_id:
        span.set_attribute(GEN_AI_RESPONSE_ID, str(llm_response.interaction_id))

    if llm_response.model_version:
        span.set_attribute(GEN_AI_RESPONSE_MODEL, str(llm_response.model_version))

    output_message = _llm_response_output_message(llm_response)
    if output_message is not None:
        span.set_attribute(GEN_AI_OUTPUT_MESSAGES, _json_dumps([output_message]))
        span.set_attribute(GEN_AI_OUTPUT_TYPE, GenAiOutputTypeValues.TEXT.value)

    usage = llm_response.usage_metadata
    if usage is None:
        return
    # ADK emits prompt / candidates tokens via the legacy keys; we add the
    # reasoning + cache token columns that Weave exposes but ADK either
    # omits or stashes under the experimental namespace.
    if usage.thoughts_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_REASONING_TOKENS, int(usage.thoughts_token_count)
        )
    if usage.cached_content_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
            int(usage.cached_content_token_count),
        )
    if usage.cache_creation_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
            int(usage.cache_creation_token_count),
        )


def _wrap_trace_agent_invocation(original: Any) -> Any:
    @wraps(original)
    def wrapper(span: Span, agent: BaseAgent, ctx: InvocationContext) -> Any:
        result = original(span, agent, ctx)
        # ADK already sets agent_name / agent_description / conversation_id;
        # layer in the Weave-superset fields it does not emit natively.
        span.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        span.set_attribute(
            GEN_AI_OPERATION_NAME, GenAiOperationNameValues.INVOKE_AGENT.value
        )
        if ctx.invocation_id:
            span.set_attribute(GEN_AI_AGENT_ID, str(ctx.invocation_id))
        # ``agent.model`` is either a model name string or a ``BaseLlm``
        # instance. Only the string form is the OTel "request.model".
        if isinstance(agent.model, str) and agent.model:
            span.set_attribute(GEN_AI_REQUEST_MODEL, agent.model)
        return result

    return wrapper


def _wrap_trace_tool_call(original: Any) -> Any:
    @wraps(original)
    def wrapper(
        tool: BaseTool,
        args: dict[str, Any],
        function_response_event: Event | None,
        error: Exception | None = None,
        span: Span | None = None,
    ) -> Any:
        result = original(
            tool, args, function_response_event, error=error, span=span
        )
        # ``otel_trace.get_current_span`` mirrors ADK's own resolution
        # logic when the caller doesn't pass ``span`` explicitly.
        target = span if span is not None else otel_trace.get_current_span()
        target.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        target.set_attribute(GEN_AI_TOOL_CALL_ARGUMENTS, _json_dumps(args))

        if (
            function_response_event is not None
            and function_response_event.content is not None
            and function_response_event.content.parts
        ):
            fr = function_response_event.content.parts[0].function_response
            if fr is not None and fr.response is not None:
                target.set_attribute(
                    GEN_AI_TOOL_CALL_RESULT, _json_dumps(fr.response)
                )
        return result

    return wrapper


def _wrap_trace_call_llm(original: Any) -> Any:
    """Enrich the legacy ``trace_call_llm`` path.

    Pre-ADK-1.36 (and the deprecated ``use_generate_content_span`` path)
    emits LLM spans via ``trace_call_llm``. The modern runner uses
    ``use_inference_span`` + ``trace_inference_result`` instead — see
    ``_wrap_set_common_generate_content_attributes`` and
    ``_wrap_trace_inference_result`` below.
    """

    @wraps(original)
    def wrapper(
        invocation_context: InvocationContext,
        event_id: str,
        llm_request: LlmRequest,
        llm_response: LlmResponse,
        span: Span | None = None,
    ) -> Any:
        result = original(
            invocation_context, event_id, llm_request, llm_response, span=span
        )
        target = span if span is not None else otel_trace.get_current_span()
        target.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        target.set_attribute(
            GEN_AI_OPERATION_NAME, GenAiOperationNameValues.CHAT.value
        )

        agent = invocation_context.agent
        if agent is not None:
            if agent.name:
                target.set_attribute(GEN_AI_AGENT_NAME, agent.name)
            if agent.description:
                target.set_attribute(GEN_AI_AGENT_DESCRIPTION, agent.description)
        if invocation_context.session is not None and invocation_context.session.id:
            target.set_attribute(
                GEN_AI_CONVERSATION_ID, str(invocation_context.session.id)
            )

        _set_llm_request_attributes(target, llm_request)
        _set_llm_response_attributes(target, llm_response)
        return result

    return wrapper


def _wrap_set_common_generate_content_attributes(original: Any) -> Any:
    """Enrich the modern ``use_inference_span`` request-time entry point.

    ADK's ``_set_common_generate_content_attributes`` runs once when the
    ``generate_content`` span is opened. It sets ``gen_ai.operation.name``
    and ``gen_ai.request.model`` but leaves the parts-model messages,
    system instructions, tool definitions and decoding parameters off the
    span. Fill them in here so Weave's columns are always populated.
    """

    @wraps(original)
    def wrapper(span: Span, llm_request: LlmRequest, common_attributes: Any) -> Any:
        result = original(span, llm_request, common_attributes)
        span.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _set_llm_request_attributes(span, llm_request)
        return result

    return wrapper


def _wrap_trace_inference_result(original: Any) -> Any:
    """Enrich the modern ``use_inference_span`` response-time entry point.

    ``trace_inference_result`` is ADK's replacement for
    ``trace_call_llm``'s response-side logic. ADK sets ``finish_reasons``
    and the usage tokens here but leaves response model / id, output
    messages and reasoning / cache tokens off.
    """

    @wraps(original)
    def wrapper(span: Any, llm_response: LlmResponse) -> Any:
        result = original(span, llm_response)
        # ADK's helper accepts either a raw ``Span`` or a
        # ``GenerateContentSpan`` wrapper. The wrapper exposes the real
        # span via ``.span``; the raw span has no such attribute. Use
        # try/except as a narrow boundary unwrap.
        try:
            target: Span = span.span
        except AttributeError:
            target = span
        target.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name_from_env())
        _set_llm_response_attributes(target, llm_response)
        return result

    return wrapper


def get_google_adk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """Return the patcher that enriches ADK OTel spans with the OTLv2 superset.

    The patcher hooks ADK's tracing functions in-place; the spans created
    by ADK still go through the global OTel TracerProvider so they ride
    whichever BatchSpanProcessor was configured by ``weave.init()`` (or
    by the user).

    Validated against ``google-adk`` 1.17 through 1.33. The modern
    ``use_inference_span`` request enrichment hangs off a private
    function, ``_set_common_generate_content_attributes``; if it
    disappears in a future ADK release the patcher logs a warning and
    skips that one hook — the other four still apply.
    """
    global _google_adk_patcher  # noqa: PLW0603

    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()
    if _google_adk_patcher is not None:
        return _google_adk_patcher

    patchers: list[SymbolPatcher] = [
        SymbolPatcher(
            lambda: _adk_tracing,
            "trace_agent_invocation",
            _wrap_trace_agent_invocation,
        ),
        SymbolPatcher(
            lambda: _adk_tracing, "trace_tool_call", _wrap_trace_tool_call
        ),
        # Legacy LLM-call path (pre-1.36 ``use_generate_content_span``).
        SymbolPatcher(
            lambda: _adk_tracing, "trace_call_llm", _wrap_trace_call_llm
        ),
        # Modern LLM-call response-side path used by ADK's runner today.
        SymbolPatcher(
            lambda: _adk_tracing,
            "trace_inference_result",
            _wrap_trace_inference_result,
        ),
    ]

    if _HAS_PRIVATE_REQUEST_HOOK:
        patchers.append(
            SymbolPatcher(
                lambda: _adk_tracing,
                _ADK_PRIVATE_REQUEST_HOOK,
                _wrap_set_common_generate_content_attributes,
            )
        )
    else:
        logger.warning(
            "google.adk.telemetry.tracing.%s is missing in google-adk %s. "
            "Weave will not enrich generate_content spans with input.messages, "
            "system_instructions, tool.definitions, or request parameters. "
            "File an issue at https://github.com/wandb/weave/issues if you need "
            "these fields.",
            _ADK_PRIVATE_REQUEST_HOOK,
            _adk.__version__,
        )

    _google_adk_patcher = MultiPatcher(patchers)
    return _google_adk_patcher
