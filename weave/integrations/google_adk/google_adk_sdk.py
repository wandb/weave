"""ADK tracing-function wrappers and the patcher factory.

Hooks ADK's five tracing entry points so each span ADK emits carries the
full Weave GenAI semantic-convention superset. The wrappers themselves
are thin: they call the original, then write supplemental attributes via
the helpers in ``extractors``.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any

# ADK imports are top-level. This module is only loaded by ``patch.py`` once
# the import hook fires on ``google.adk`` (or once a caller invokes
# ``weave.integrations.patch_google_adk()``), so ADK is always installed
# by the time we get here.
import google.adk as _adk
from google.adk.telemetry import tracing as _adk_tracing
from opentelemetry import trace as otel_trace
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_RESULT,
    GenAiOperationNameValues,
)

from weave.integrations.google_adk.extractors import (
    provider_name_from_env,
    set_llm_request_attributes,
    set_llm_response_attributes,
)
from weave.integrations.google_adk.parts import json_dumps
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

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

# ``trace_inference_result`` can be handed either a raw OTel ``Span`` or a
# ``GenerateContentSpan`` wrapper that exposes the real span at ``.span``.
# Import the wrapper class so we can ``isinstance`` it explicitly instead
# of probing attributes with try/except.
try:
    from google.adk.telemetry.tracing import (
        GenerateContentSpan as _AdkGenerateContentSpan,
    )
except ImportError:
    _AdkGenerateContentSpan = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events.event import Event
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools.base_tool import BaseTool
    from opentelemetry.trace import Span

logger = logging.getLogger(__name__)


def _unwrap_inference_span(span: Any) -> Span:
    """Resolve an ADK inference-span argument to the underlying OTel ``Span``.

    ADK's ``trace_inference_result`` accepts either a raw OTel ``Span`` or
    a ``GenerateContentSpan`` wrapper that exposes the real span at
    ``.span``.
    """
    if _AdkGenerateContentSpan is not None and isinstance(
        span, _AdkGenerateContentSpan
    ):
        return span.span
    return span


def _wrap_trace_agent_invocation(original: Any) -> Any:
    @wraps(original)
    def wrapper(span: Span, agent: BaseAgent, ctx: InvocationContext) -> Any:
        result = original(span, agent, ctx)
        # ADK already sets agent_name / agent_description / conversation_id;
        # layer in the Weave-superset fields it does not emit natively.
        span.set_attribute(GEN_AI_PROVIDER_NAME, provider_name_from_env())
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
        target.set_attribute(GEN_AI_PROVIDER_NAME, provider_name_from_env())
        target.set_attribute(GEN_AI_TOOL_CALL_ARGUMENTS, json_dumps(args))

        if (
            function_response_event is not None
            and function_response_event.content is not None
            and function_response_event.content.parts
        ):
            fr = function_response_event.content.parts[0].function_response
            if fr is not None and fr.response is not None:
                target.set_attribute(
                    GEN_AI_TOOL_CALL_RESULT, json_dumps(fr.response)
                )
        return result

    return wrapper


# TODO: remove this wrapper once google-adk's min supported version is 1.36+
# (the cutover to ``use_inference_span`` / ``trace_inference_result``).
def _wrap_trace_call_llm(original: Any) -> Any:
    """Enrich the legacy ``trace_call_llm`` path.

    Pre-ADK-1.36 (and the deprecated ``use_generate_content_span`` path)
    emits LLM spans via ``trace_call_llm``. The modern runner uses
    ``use_inference_span`` + ``trace_inference_result`` instead.
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
        target.set_attribute(GEN_AI_PROVIDER_NAME, provider_name_from_env())
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

        set_llm_request_attributes(target, llm_request)
        set_llm_response_attributes(target, llm_response)
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
        span.set_attribute(GEN_AI_PROVIDER_NAME, provider_name_from_env())
        set_llm_request_attributes(span, llm_request)
        return result

    return wrapper


def _wrap_trace_inference_result(original: Any) -> Any:
    """Enrich the modern ``use_inference_span`` response-time entry point."""

    @wraps(original)
    def wrapper(span: Any, llm_response: LlmResponse) -> Any:
        result = original(span, llm_response)
        target = _unwrap_inference_span(span)
        target.set_attribute(GEN_AI_PROVIDER_NAME, provider_name_from_env())
        set_llm_response_attributes(target, llm_response)
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

    return MultiPatcher(patchers)
