"""ADK tracing-function wrappers and the patcher factory.

Hooks ADK's tracing entry points so each span ADK emits carries the full
Weave GenAI semantic-convention superset. The wrappers themselves are
thin: they call the original, then write supplemental attributes via the
helpers in ``extractors``.

ADK's four tracing entry points cluster into three wrapper shapes:

1. **Direct-span** — ``trace_agent_invocation`` and
   ``_set_common_generate_content_attributes`` hand the wrapper a
   guaranteed ``Span``. No normalisation, no gating. Enrich and return.
2. **Inference-span** — ``trace_inference_result`` hands the wrapper
   either a ``Span`` or a ``GenerateContentSpan`` wrapper, and may
   stream partial chunks. Unwrap via ``_unwrap_inference_span``; skip
   partial chunks.
3. **Optional-span with content gate** — ``trace_tool_call`` may pass
   ``span=None`` (the current OTel span is then the target) and carries
   user/tool payloads gated by ``_capture_message_content``. Resolve via
   ``_resolve_optional_span``; gate content writes.

``_unwrap_inference_span`` and ``_resolve_optional_span`` are disjoint
span-normalisation rules — they handle different ADK input shapes and
should not be confused.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from functools import wraps

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.telemetry import tracing as adk_tracing
from google.adk.telemetry.tracing import GenerateContentSpan
from google.adk.tools.base_tool import BaseTool
from opentelemetry import trace as otel_trace
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_AGENT_ID,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_RESULT,
    GenAiOperationNameValues,
)
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue

from weave.integrations.google_adk.extractors import (
    _capture_message_content,
    _provider_name,
    set_llm_request_attributes,
    set_llm_response_attributes,
)
from weave.integrations.integration_metadata import library_integration
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

# ADK's ``telemetry.tracing`` module exposes the trace_* functions but not
# their signatures as ``TypeAlias`` / ``Protocol``, so we declare local
# aliases here to type the wrappers below. Each ADK function returns
# ``None`` — the wrappers capture the return value but never change it.
# ``_TraceToolCall`` narrows ADK's ``args: dict[str, Any]`` to
# ``Mapping[str, object]`` because the wrapper only passes ``args`` to
# ``json.dumps`` — it never indexes or mutates it.
_TraceAgentInvocation = Callable[[Span, BaseAgent, InvocationContext], None]
_TraceToolCall = Callable[
    [
        BaseTool,
        Mapping[str, object],
        Event | None,
        Exception | None,
        Span | None,
    ],
    None,
]
_SetCommonGenerateContentAttributes = Callable[
    [Span, LlmRequest, Mapping[str, AttributeValue]], None
]
_TraceInferenceResult = Callable[[Span | GenerateContentSpan, LlmResponse], None]

# Integration provenance, flattened once for OTel span attributes (scalars only).
# ADK creates the spans; these wrappers enrich them, so we stamp the same
# `integration.*` keys the other agent OTel integrations emit.
_INTEGRATION_OTEL_ATTRS = library_integration(
    "google_adk", distribution_name="google-adk"
).as_otel_attributes()


def _set_integration_attrs(span: Span) -> None:
    """Stamp integration-tracking provenance onto an ADK OTel span."""
    for key, value in _INTEGRATION_OTEL_ATTRS.items():
        span.set_attribute(key, value)


def _unwrap_inference_span(span: Span | GenerateContentSpan) -> Span:
    """Return the underlying OTel ``Span`` for an inference-shaped argument.

    ADK's ``trace_inference_result`` accepts either a raw OTel ``Span`` or
    a ``GenerateContentSpan`` wrapper that exposes the real span at
    ``.span``. Disjoint from ``_resolve_optional_span``: this handles the
    Span-vs-wrapper discrimination, not the None case.
    """
    if isinstance(span, GenerateContentSpan):
        return span.span
    return span


def _resolve_optional_span(span: Span | None) -> Span:
    """Return ``span`` if supplied, else the current OTel span.

    Mirrors ADK's own ``span if span is not None else
    otel_trace.get_current_span()`` pattern so our wrappers write to the
    same span ADK itself would. Disjoint from ``_unwrap_inference_span``:
    this handles the None case, not the wrapper case.
    """
    if span is not None:
        return span
    return otel_trace.get_current_span()


def _wrap_trace_agent_invocation(
    original: _TraceAgentInvocation,
) -> _TraceAgentInvocation:
    @wraps(original)
    def wrapper(span: Span, agent: BaseAgent, ctx: InvocationContext) -> None:
        original(span, agent, ctx)
        # ADK already sets agent_name / agent_description / conversation_id;
        # layer in the Weave-superset fields it does not emit natively.
        span.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name())
        _set_integration_attrs(span)
        span.set_attribute(
            GEN_AI_OPERATION_NAME, GenAiOperationNameValues.INVOKE_AGENT.value
        )
        if ctx.invocation_id:
            span.set_attribute(GEN_AI_AGENT_ID, str(ctx.invocation_id))
        # ``agent.model`` is either a model name string or a ``BaseLlm``
        # instance. Only the string form is the OTel "request.model".
        if isinstance(agent.model, str) and agent.model:
            span.set_attribute(GEN_AI_REQUEST_MODEL, agent.model)

    return wrapper


def _wrap_trace_tool_call(original: _TraceToolCall) -> _TraceToolCall:
    @wraps(original)
    def wrapper(
        tool: BaseTool,
        args: Mapping[str, object],
        function_response_event: Event | None,
        error: Exception | None = None,
        span: Span | None = None,
    ) -> None:
        # Pass ``error`` / ``span`` positionally — the ``Callable`` type
        # alias is positional-only, and ADK accepts them in this order.
        original(tool, args, function_response_event, error, span)
        target = _resolve_optional_span(span)
        target.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name())
        _set_integration_attrs(target)

        # Tool args/result are message content; respect the ADK opt-out
        # so PHI/PII users get the same gate they get from ADK itself.
        if not _capture_message_content():
            return

        # Tool args and results are external/user data — ``default=str``
        # is a defensive fallback so a pydantic-derived value nested in
        # the payload never raises into ADK's flow.
        target.set_attribute(
            GEN_AI_TOOL_CALL_ARGUMENTS,
            json.dumps(args, ensure_ascii=False, default=str),
        )

        if (
            function_response_event is not None
            and function_response_event.content is not None
            and function_response_event.content.parts
        ):
            fr = function_response_event.content.parts[0].function_response
            if fr is not None and fr.response is not None:
                target.set_attribute(
                    GEN_AI_TOOL_CALL_RESULT,
                    json.dumps(fr.response, ensure_ascii=False, default=str),
                )

    return wrapper


def _wrap_set_common_generate_content_attributes(
    original: _SetCommonGenerateContentAttributes,
) -> _SetCommonGenerateContentAttributes:
    """Enrich the modern ``use_inference_span`` request-time entry point.

    ADK's ``_set_common_generate_content_attributes`` runs once when the
    ``generate_content`` span is opened. It sets ``gen_ai.operation.name``
    and ``gen_ai.request.model`` but leaves the parts-model messages,
    system instructions, tool definitions and decoding parameters off the
    span. Fill them in here so Weave's columns are always populated.
    """

    @wraps(original)
    def wrapper(
        span: Span,
        llm_request: LlmRequest,
        common_attributes: Mapping[str, AttributeValue],
    ) -> None:
        original(span, llm_request, common_attributes)
        span.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name())
        _set_integration_attrs(span)
        set_llm_request_attributes(span, llm_request)

    return wrapper


def _wrap_trace_inference_result(
    original: _TraceInferenceResult,
) -> _TraceInferenceResult:
    """Enrich the modern ``use_inference_span`` response-time entry point."""

    @wraps(original)
    def wrapper(span: Span | GenerateContentSpan, llm_response: LlmResponse) -> None:
        original(span, llm_response)
        # ADK's own ``trace_inference_result`` bails on partial chunks
        # (``if llm_response.partial: return``) — mirror that contract so
        # the streaming path doesn't stomp the span N times with
        # half-built parts-model payloads. The final non-partial chunk
        # carries the aggregated response and is what should land on the
        # span.
        if llm_response.partial:
            return
        target = _unwrap_inference_span(span)
        target.set_attribute(GEN_AI_PROVIDER_NAME, _provider_name())
        _set_integration_attrs(target)
        set_llm_response_attributes(target, llm_response)

    return wrapper


def get_google_adk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """Return the patcher that enriches ADK OTel spans with the GenAI superset.

    The patcher hooks ADK's tracing functions in-place; the spans created
    by ADK still go through the global OTel TracerProvider so they ride
    whichever BatchSpanProcessor was configured by ``weave.init()`` (or
    by the user).

    Requires ``google-adk>=1.36`` (the cutover that introduced
    ``use_inference_span`` / ``trace_inference_result``); validated
    through 2.0. Every hooked symbol is imported at the top of this
    module so a future ADK release that removes one fails loudly at
    integration load time rather than as silently incomplete telemetry.

    Each call builds a fresh ``MultiPatcher``. Idempotency lives in
    ``SymbolPatcher.attempt_patch`` (which short-circuits when the symbol
    is already patched), so repeat calls are cheap and safe; we don't
    cache the assembled patcher because that would silently ignore an
    updated ``settings`` argument across calls.
    """
    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()

    return MultiPatcher(
        [
            SymbolPatcher(
                lambda: adk_tracing,
                "trace_agent_invocation",
                _wrap_trace_agent_invocation,
            ),
            SymbolPatcher(
                lambda: adk_tracing, "trace_tool_call", _wrap_trace_tool_call
            ),
            # Modern LLM-call response-side path used by ADK's runner today.
            SymbolPatcher(
                lambda: adk_tracing,
                "trace_inference_result",
                _wrap_trace_inference_result,
            ),
            # Modern LLM-call request-side. ``_set_common_generate_content_attributes``
            # is underscore-prefixed in ADK but stable from 1.36 onward; we
            # import it directly at module top so a future rename fails
            # loudly at integration load rather than silently degrading.
            SymbolPatcher(
                lambda: adk_tracing,
                "_set_common_generate_content_attributes",
                _wrap_set_common_generate_content_attributes,
            ),
        ]
    )
