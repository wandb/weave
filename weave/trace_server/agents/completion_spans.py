"""Build agent spans from completion requests.

The playground and signals call LLMs via the ``completions_create`` /
``completions_create_stream`` endpoints.  This module converts the
request + response data into ``AgentSpanCHInsertable`` rows so they
appear in the agents data model alongside SDK-produced traces.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from weave.trace_server.agents.schema import (
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER, SENTINEL_EPOCH
from weave.trace_server.trace_server_interface import CompletionsCreateRequestInputs
from weave.trace_server.ttl_settings import compute_expire_at

logger = logging.getLogger(__name__)

PLAYGROUND_AGENT_NAME = "Weave Chat Playground"
SIGNALS_AGENT_NAME = "Weave Signals"

_SOURCE_TO_AGENT_NAME: dict[str | None, str] = {
    "playground": PLAYGROUND_AGENT_NAME,
    "signals": SIGNALS_AGENT_NAME,
}


def build_completion_span(
    *,
    project_id: str,
    trace_id: str,
    span_id: str,
    conversation_id: str,
    conversation_name: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    provider_name: str,
    model_name: str,
    request_inputs: CompletionsCreateRequestInputs,
    response: dict[str, Any] | None,
    wb_user_id: str,
    retention_days: int,
    error: str | None = None,
    source: str | None = None,
) -> AgentSpanCHInsertable:
    """Construct an ``AgentSpanCHInsertable`` from playground completion data.

    Parameters
    ----------
    ended_at:
        Pass ``SENTINEL_EPOCH`` for an open/streaming span that has not
        finished yet.
    response:
        The LiteLLM response dict.  ``None`` for open streaming spans.
    """
    agent_name = _SOURCE_TO_AGENT_NAME.get(source, PLAYGROUND_AGENT_NAME)
    weave_source = source or "playground"

    input_messages = _normalize_input_messages(request_inputs.messages)
    system_instructions = _extract_system_instructions(request_inputs.messages)
    output_messages: list[NormalizedMessage] = []
    finish_reasons: list[str] = []

    if response and "choices" in response:
        output_messages = _normalize_output_messages(response["choices"])
        finish_reasons = [
            c.get("finish_reason", "") or "" for c in response.get("choices", [])
        ]

    usage = (response or {}).get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0) or 0
    output_tokens = usage.get("completion_tokens", 0) or 0
    reasoning_tokens = (
        usage.get("reasoning_tokens", 0) or usage.get("reasoning_output_tokens", 0) or 0
    )
    cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0) or 0
    cache_read_input_tokens = usage.get("cache_read_input_tokens", 0) or 0

    request_temperature = request_inputs.temperature or 0.0
    request_max_tokens = (
        request_inputs.max_completion_tokens or request_inputs.max_tokens or 0
    )
    request_top_p = request_inputs.top_p or 0.0
    request_frequency_penalty = request_inputs.frequency_penalty or 0.0
    request_presence_penalty = request_inputs.presence_penalty or 0.0
    request_seed = request_inputs.seed or 0
    request_stop_sequences: list[str] = []
    if request_inputs.stop:
        if isinstance(request_inputs.stop, list):
            request_stop_sequences = [str(s) for s in request_inputs.stop]
        else:
            request_stop_sequences = [str(request_inputs.stop)]
    request_choice_count = request_inputs.n or 0

    tool_definitions = ""
    if request_inputs.tools:
        try:
            tool_definitions = json.dumps(request_inputs.tools)
        except (TypeError, ValueError):
            pass

    if ended_at == SENTINEL_EPOCH:
        status_code = "UNSET"
    elif error:
        status_code = "ERROR"
    else:
        status_code = "OK"

    expire_at = compute_expire_at(retention_days, started_at)
    if expire_at is None:
        expire_at = EXPIRE_AT_NEVER

    raw_dump: dict[str, Any] = {
        "inputs": request_inputs.model_dump(
            exclude_none=True, exclude={"vertex_credentials"}
        ),
    }
    if response is not None:
        raw_dump["response"] = response
    if error:
        raw_dump["error"] = error

    return AgentSpanCHInsertable(
        project_id=project_id,
        trace_id=trace_id,
        span_id=span_id,
        agent_name=agent_name,
        span_name=agent_name,
        span_kind="CLIENT",
        started_at=started_at,
        ended_at=ended_at,
        status_code=status_code,
        status_message=error or "",
        error_type="LLMError" if error else "",
        operation_name="chat",
        provider_name=provider_name.lower() if provider_name else "",
        request_model=model_name,
        response_model=(response or {}).get("model", ""),
        response_id=(response or {}).get("id", ""),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        finish_reasons=finish_reasons,
        request_temperature=request_temperature,
        request_max_tokens=request_max_tokens,
        request_top_p=request_top_p,
        request_frequency_penalty=request_frequency_penalty,
        request_presence_penalty=request_presence_penalty,
        request_seed=request_seed,
        request_stop_sequences=request_stop_sequences,
        request_choice_count=request_choice_count,
        tool_definitions=tool_definitions,
        input_messages=input_messages,
        output_messages=output_messages,
        system_instructions=system_instructions,
        custom_attrs_string={"weave.source": weave_source},
        raw_span_dump=json.dumps(raw_dump, default=str),
        wb_user_id=wb_user_id or "",
        expire_at=expire_at,
    )


def _normalize_input_messages(
    messages: list[Any],
) -> list[NormalizedMessage]:
    """Normalize playground input messages to NormalizedMessage list.

    Skips system messages (they go to ``system_instructions`` instead).
    """
    result: list[NormalizedMessage] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        if role == "system":
            continue
        content = _extract_content_text(msg.get("content", ""))
        result.append(NormalizedMessage(role=role, content=content))
    return result


def _normalize_output_messages(
    choices: list[dict[str, Any]],
) -> list[NormalizedMessage]:
    """Normalize LiteLLM response choices to output messages."""
    result: list[NormalizedMessage] = []
    for choice in choices:
        message = choice.get("message", {})
        if not isinstance(message, dict):
            continue
        role = message.get("role", "assistant")
        content = _extract_content_text(message.get("content", ""))

        tool_calls = message.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            parts = [content] if content else []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", "")
                    parts.append(f"[tool_call: {name}({args})]")
            content = "\n".join(parts)

        finish_reason = choice.get("finish_reason", "") or ""
        result.append(
            NormalizedMessage(role=role, content=content, finish_reason=finish_reason)
        )
    return result


def _extract_system_instructions(messages: list[Any]) -> list[str]:
    """Extract system message content from the message list."""
    instructions: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "system":
            content = _extract_content_text(msg.get("content", ""))
            if content:
                instructions.append(content)
    return instructions


def _extract_content_text(content: Any) -> str:
    """Extract plain text from various content formats.

    Content may be a string, a list of content parts (OpenAI multi-modal
    format), or None.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text", "")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content)
