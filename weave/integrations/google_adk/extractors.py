"""ADK → GenAI semconv attribute extractors.

Given a parsed ADK object (``LlmRequest`` / ``LlmResponse`` / agent / tool),
emit the GenAI semantic-convention attributes Weave extracts into dedicated
columns.

These functions take an OTel ``Span`` and write attributes directly to it.
They never raise into ADK's flow — if a value isn't present, the attribute
just isn't set, which is the correct behaviour for optional GenAI fields.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

# ADK exports the tool-definition discriminator from its experimental
# semconv module. Importing it lets the integration stay in lock-step with
# whatever string ADK uses on the wire (currently ``"function"``).
from google.adk.telemetry._experimental_semconv import FUNCTION_TOOL_DEFINITION_TYPE
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
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
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GenAiOutputTypeValues,
    GenAiSystemValues,
)

from weave.integrations.google_adk.parts import (
    json_dumps,
    llm_request_input_messages,
    llm_response_output_message,
)

if TYPE_CHECKING:
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from opentelemetry.trace import Span

# TODO(2026-Q3): replace with the upstream import once
# ``opentelemetry-semantic-conventions`` ships
# ``GEN_AI_USAGE_REASONING_OUTPUT_TOKENS`` (PR open-telemetry/semantic-conventions#3383,
# merged 2026-04-27 — three days after our 0.62b1 floor was released).
# Weave's server-side ``semconv.py`` already recognises this name as the
# canonical wire form plus legacy aliases for backfill compatibility.
GEN_AI_USAGE_REASONING_OUTPUT_TOKENS = "gen_ai.usage.reasoning.output_tokens"

# ADK reads this env var to decide between Vertex AI and Gemini at runtime.
# Neither ``google.genai`` nor ``google.adk`` exports it as a named
# constant — ADK itself uses the literal in ``_guess_gemini_system_name``
# — so we mirror Google's contract and keep the bare string here.
_GOOGLE_GENAI_USE_VERTEXAI_ENV = "GOOGLE_GENAI_USE_VERTEXAI"


def provider_name_from_env() -> str:
    """Return the Weave-canonical provider name for the running ADK runtime.

    Mirrors ADK's own ``_guess_gemini_system_name`` and emits the upstream
    ``GenAiSystemValues`` value so the wire format matches the canonical
    semconv enum. Re-reads the env var on every call: tests and notebooks
    do flip it between agent runs and we don't want to lock in the value
    we saw at patch time.
    """
    use_vertex = os.getenv(_GOOGLE_GENAI_USE_VERTEXAI_ENV, "").lower() in {"true", "1"}
    return (
        GenAiSystemValues.VERTEX_AI.value
        if use_vertex
        else GenAiSystemValues.GEMINI.value
    )


def _system_instructions_to_text(config: Any) -> list[str]:
    """Collect plain text from ``LlmRequest.config.system_instruction``.

    ADK accepts ``str``, ``Content``, or ``list[Content]``. Flatten to
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
    # Emit them unconditionally so Weave's dedicated columns are always
    # populated.
    system_instructions = _system_instructions_to_text(config)
    if system_instructions:
        span.set_attribute(
            GEN_AI_SYSTEM_INSTRUCTIONS,
            json_dumps([{"type": "text", "content": s} for s in system_instructions]),
        )

    input_messages = llm_request_input_messages(llm_request)
    if input_messages:
        span.set_attribute(GEN_AI_INPUT_MESSAGES, json_dumps(input_messages))

    tool_defs = _tool_definitions(config)
    if tool_defs:
        span.set_attribute(GEN_AI_TOOL_DEFINITIONS, json_dumps(tool_defs))


def set_llm_response_attributes(span: Span, llm_response: LlmResponse) -> None:
    """Set response-side GenAI attributes from an ADK ``LlmResponse``."""
    # ADK's ``LlmResponse.interaction_id`` is the response identifier.
    if llm_response.interaction_id:
        span.set_attribute(GEN_AI_RESPONSE_ID, str(llm_response.interaction_id))

    if llm_response.model_version:
        span.set_attribute(GEN_AI_RESPONSE_MODEL, str(llm_response.model_version))

    output_message = llm_response_output_message(llm_response)
    if output_message is not None:
        span.set_attribute(GEN_AI_OUTPUT_MESSAGES, json_dumps([output_message]))
        span.set_attribute(GEN_AI_OUTPUT_TYPE, GenAiOutputTypeValues.TEXT.value)

    usage = llm_response.usage_metadata
    if usage is None:
        return
    # ADK emits prompt / candidates tokens via the legacy keys; we add the
    # reasoning + cache token columns that Weave exposes but ADK either
    # omits or stashes under the experimental namespace.
    if usage.thoughts_token_count is not None:
        span.set_attribute(
            GEN_AI_USAGE_REASONING_OUTPUT_TOKENS, int(usage.thoughts_token_count)
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
