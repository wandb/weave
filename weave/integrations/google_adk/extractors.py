"""ADK → GenAI semconv attribute extractors.

Given a parsed ADK object (``LlmRequest`` / ``LlmResponse`` / agent / tool),
emit the GenAI semantic-convention attributes Weave extracts into dedicated
columns.

These functions take an OTel ``Span`` and write attributes directly to it.
They never raise into ADK's flow — if a value isn't present, the attribute
just isn't set, which is the correct behaviour for optional GenAI fields.

The per-content-part wire shape (``{"type": "text", "content": ...}``,
``{"type": "tool_call", ...}``, etc.) comes from ADK's own ``_to_part``
helper — same TypedDicts ADK uses on its native spans — with one local
override that strips the ``Blob`` binary payload because bytes aren't
span-attribute-safe and Weave already stores blobs out of band.
"""

from __future__ import annotations

import json
import os
from typing import Any

from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

# ADK's experimental semconv module exports the tool-definition
# discriminator, the per-part ``_to_part`` builder, and
# ``_to_system_instructions``, which normalises ``config.system_instruction``
# — a polymorphic field that ADK accepts as a bare ``str``, a
# ``google.genai.types.Content``, a list of either, a dict that quacks like
# ``Content`` / ``Part``, or even a PIL image — into the parts-model wire
# shape Weave's column extractor reads. Reusing ADK's helpers means we
# stay in lock-step with google-genai's content-normalisation logic
# (``_transformers.t_contents``) rather than duplicating its many
# branches here.
from google.adk.telemetry._experimental_semconv import (
    FUNCTION_TOOL_DEFINITION_TYPE,
    Part,
    _to_part,
    _to_system_instructions,
)
from google.genai.types import Content, GenerateContentConfig
from opentelemetry.trace import Span

from weave.integrations.google_adk._semconv import (
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_REQUEST_CHOICE_COUNT,
    GEN_AI_REQUEST_FREQUENCY_PENALTY,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_PRESENCE_PENALTY,
    GEN_AI_REQUEST_SEED,
    GEN_AI_REQUEST_STOP_SEQUENCES,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
    OUTPUT_TYPE_TEXT,
    PROVIDER_GEMINI,
    PROVIDER_VERTEX_AI,
)

# Runtime config — env vars the integration reads on every span. Both the
# extractors below and the patcher wrappers in ``google_adk_sdk`` consult
# these. Re-reading per call (no module-level caching) keeps notebooks
# and tests honest: they can flip the env var between agent runs without
# locking in the patch-time value.

# ADK's own opt-out env var for message-content capture. Mirrored from
# ``google.adk.telemetry.tracing._should_add_request_response_to_spans``;
# ADK uses the literal there, so we mirror Google's contract.
# Users in regulated domains (PHI/PII/PCI) set this to ``false`` to
# keep message bodies off spans — Weave honours that for the same
# attributes ADK would gate.
_ADK_CAPTURE_MESSAGE_CONTENT_ENV = "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"

# google-genai's runtime-mode toggle. ADK itself reads this literal in
# ``_guess_gemini_system_name`` (and in ``utils/variant_utils.py``,
# ``utils/vertex_ai_utils.py``) — neither library exports it as a
# constant, so we mirror Google's contract and use the literal too.
_GOOGLE_GENAI_USE_VERTEXAI_ENV = "GOOGLE_GENAI_USE_VERTEXAI"

# ADK uses ``"user"`` for the user turn and ``"model"`` for the assistant
# turn. Weave's UI follows the OTel-standard ``"user"``/``"assistant"``
# pair. Unrecognised roles fall through unchanged so future ADK roles
# (e.g. ``"system"``) do not silently collapse.
_ADK_TO_WEAVE_ROLE: dict[str, str] = {"user": "user", "model": "assistant"}


def _capture_message_content() -> bool:
    """Return True iff message content may be written to spans."""
    return os.getenv(_ADK_CAPTURE_MESSAGE_CONTENT_ENV, "true").lower() in {
        "true",
        "1",
    }


def _provider_name() -> str:
    """Return the Weave-canonical provider name for the running ADK runtime.

    Mirrors ADK's own ``_guess_gemini_system_name`` and emits the vendored
    provider value (see ``_semconv``) so the wire format matches the
    canonical semconv enum.
    """
    use_vertex = os.getenv(_GOOGLE_GENAI_USE_VERTEXAI_ENV, "").lower() in {
        "true",
        "1",
    }
    if use_vertex:
        return PROVIDER_VERTEX_AI
    return PROVIDER_GEMINI


def _adk_role_to_weave(role: str | None) -> str:
    """Map an ADK role label to the GenAI parts-model role."""
    if not role:
        return ""
    return _ADK_TO_WEAVE_ROLE.get(role, role)


def _content_to_parts(content: Content) -> list[Part]:
    """Flatten a ``google.genai.types.Content`` into the GenAI parts model.

    Delegates to ADK's ``_to_part`` per element; strips the binary
    payload from ``Blob`` so the span attribute stays size-bounded.
    """
    parts: list[Part] = []
    for idx, part in enumerate(content.parts or []):
        converted = _to_part(part, idx)
        if converted is None:
            continue
        if converted.get("type") == "blob":
            # Keep the mime-type signal, drop the bytes payload — Weave
            # stores blobs out of band, and bytes aren't span-safe.
            converted = {
                "type": "blob",
                "mime_type": converted.get("mime_type", ""),
            }
        parts.append(converted)
    return parts


def _llm_request_input_messages(llm_request: LlmRequest) -> list[dict[str, Any]]:
    """Serialise ``LlmRequest.contents`` to GenAI input-messages JSON shape."""
    return [
        {
            "role": _adk_role_to_weave(content.role),
            "parts": _content_to_parts(content),
        }
        for content in (llm_request.contents or [])
    ]


def _llm_response_output_message(
    llm_response: LlmResponse,
) -> dict[str, Any] | None:
    """Serialise an ``LlmResponse`` to the single output-message JSON object.

    Returns ``None`` when the response has no content (e.g. error responses).
    """
    if llm_response.content is None:
        return None
    finish_str = ""
    finish_reason = llm_response.finish_reason
    if finish_reason is not None:
        # ``FinishReason`` is an Enum; ``.value`` is the wire form, fall
        # back to ``.name`` for older enum styles.
        finish_str = str(finish_reason.value or finish_reason.name).lower()
    return {
        "role": _adk_role_to_weave(llm_response.content.role) or "assistant",
        "parts": _content_to_parts(llm_response.content),
        "finish_reason": finish_str,
    }


def _tool_definitions(config: GenerateContentConfig) -> list[dict[str, Any]]:
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


def set_llm_request_attributes(span: Span, llm_request: LlmRequest) -> None:
    """Set request-side GenAI attributes from an ADK ``LlmRequest``."""
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
        span.set_attribute(GEN_AI_REQUEST_CHOICE_COUNT, int(config.candidate_count))

    # System instructions, input messages and tool definitions are GenAI
    # "Opt-In" attributes — ADK only emits them under
    # ``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`` with
    # ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` enabled.
    # We emit them by default so Weave's columns are populated, but honour
    # ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false so PHI/PII users get the
    # same opt-out they get from ADK itself. Tool definitions stay on the
    # span — they're schema, not user data.
    if _capture_message_content():
        # ``_to_system_instructions`` and ``_llm_request_input_messages``
        # already return the parts-model wire shape as plain dicts (the
        # ADK ``Part`` TypedDicts are ``dict`` at runtime), so
        # ``json.dumps`` serialises them with no wrapping.
        system_instructions = _to_system_instructions(config)
        if system_instructions:
            span.set_attribute(
                GEN_AI_SYSTEM_INSTRUCTIONS,
                json.dumps(system_instructions, ensure_ascii=False),
            )

        input_messages = _llm_request_input_messages(llm_request)
        if input_messages:
            span.set_attribute(
                GEN_AI_INPUT_MESSAGES, json.dumps(input_messages, ensure_ascii=False)
            )

    tool_defs = _tool_definitions(config)
    if tool_defs:
        span.set_attribute(
            GEN_AI_TOOL_DEFINITIONS, json.dumps(tool_defs, ensure_ascii=False)
        )


def set_llm_response_attributes(span: Span, llm_response: LlmResponse) -> None:
    """Set response-side GenAI attributes from an ADK ``LlmResponse``."""
    # ADK's ``LlmResponse.interaction_id`` is the response identifier.
    if llm_response.interaction_id:
        span.set_attribute(GEN_AI_RESPONSE_ID, str(llm_response.interaction_id))

    if llm_response.model_version:
        span.set_attribute(GEN_AI_RESPONSE_MODEL, str(llm_response.model_version))

    if _capture_message_content():
        output_message = _llm_response_output_message(llm_response)
        if output_message is not None:
            span.set_attribute(
                GEN_AI_OUTPUT_MESSAGES,
                json.dumps([output_message], ensure_ascii=False),
            )
            span.set_attribute(GEN_AI_OUTPUT_TYPE, OUTPUT_TYPE_TEXT)

    usage = llm_response.usage_metadata
    if usage is None:
        return
    # ADK emits prompt / candidates tokens via the canonical keys; we add
    # the two Gemini-specific usage fields Weave exposes that ADK leaves
    # in the experimental namespace or omits. We do NOT emit
    # ``gen_ai.usage.cache_creation.input_tokens`` here — that's an
    # Anthropic-style "tokens written to cache" metric with no equivalent
    # field on ``google-genai``'s ``GenerateContentResponseUsageMetadata``.
    if usage.thoughts_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_REASONING_OUTPUT_TOKENS, int(usage.thoughts_token_count)
        )
    if usage.cached_content_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
            int(usage.cached_content_token_count),
        )
