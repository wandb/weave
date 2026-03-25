"""Extract typed GenAI fields from OTel span attributes.

Pure functions that read standard OTel GenAI semantic convention attributes
(with vendor fallback chains) and return values suitable for the typed GenAI
columns on calls_complete.  No table or schema dependencies — this module
only depends on the helpers in this package.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from weave.trace_server.opentelemetry.helpers import get_attribute, try_parse_int


@dataclass
class GenAIFields:
    """Extracted GenAI column values ready for calls_complete insertion."""

    operation_name: str = ""
    provider_name: str = ""
    request_model: str = ""
    response_model: str = ""
    response_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    request_temperature: float = 0.0
    request_max_tokens: int = 0
    request_top_p: float = 0.0
    conversation_id: str = ""
    agent_name: str = ""
    tool_name: str = ""
    input_messages: list[tuple[str, str, str, str]] = field(default_factory=list)
    output_messages: list[tuple[str, str, str, str]] = field(default_factory=list)
    finish_reasons: list[str] = field(default_factory=list)
    system_instructions: list[str] = field(default_factory=list)
    tool_call_arguments: str = ""


_OPENAI_SPAN_TYPE_TO_OP: dict[str, str] = {
    "agent": "invoke_agent",
    "response": "chat",
    "function": "execute_tool",
    "handoff": "handoff",
    "guardrail": "guardrail",
}

_KNOWN_OP_PREFIXES: dict[str, str] = {
    "chat": "chat",
    "call_llm": "chat",
    "completion": "chat",
    "generate": "chat",
    "agent_run": "invoke_agent",
    "invocation": "invoke_agent",
    "agent:": "invoke_agent",
    "invoke_agent": "invoke_agent",
    "execute_tool": "execute_tool",
    "tool:": "execute_tool",
    "workflow:": "workflow",
}


def _str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return str(val)


def _int(val: Any) -> int:
    if val is None:
        return 0
    parsed = try_parse_int(val)
    return parsed if isinstance(parsed, int) else 0


def _float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def extract_operation_name(attrs: dict[str, Any], span_name: str) -> str:
    """Resolve the GenAI operation name via ordered fallback chain."""
    op = get_attribute(attrs, "gen_ai.operation.name")
    if op:
        return _str(op)

    agent_type = get_attribute(attrs, "agent.span.type")
    if agent_type and _str(agent_type) in _OPENAI_SPAN_TYPE_TO_OP:
        return _OPENAI_SPAN_TYPE_TO_OP[_str(agent_type)]

    name_lower = span_name.lower()
    for prefix, mapped in _KNOWN_OP_PREFIXES.items():
        if name_lower.startswith(prefix):
            return mapped

    llm_type = get_attribute(attrs, "llm.request.type")
    if llm_type:
        t = _str(llm_type).lower()
        if t in ("completion", "chat"):
            return "chat"

    if "." in span_name:
        suffix = span_name.rsplit(".", 1)[-1].lower()
        if suffix in ("chat", "completion", "generate", "generate_content"):
            return "chat"

    return ""


def extract_provider(attrs: dict[str, Any], span_name: str) -> str:
    """Resolve the GenAI provider via ordered fallback chain."""
    for key in ("gen_ai.provider.name", "gen_ai.system"):
        val = get_attribute(attrs, key)
        if val:
            return _str(val)

    for key in ("llm.provider", "ai.model.provider"):
        val = get_attribute(attrs, key)
        if val:
            return _str(val)

    known = ("anthropic", "openai", "google", "cohere", "mistral", "groq", "bedrock")
    name_lower = span_name.lower()
    for p in known:
        if name_lower.startswith(p):
            return p

    return ""


def extract_model(attrs: dict[str, Any]) -> tuple[str, str]:
    """Return (request_model, response_model)."""
    request = _str(
        get_attribute(attrs, "gen_ai.request.model")
        or get_attribute(attrs, "llm.model_name")
        or get_attribute(attrs, "ai.model.id")
    )
    response = _str(
        get_attribute(attrs, "gen_ai.response.model") or ""
    )
    return request, response


def extract_tokens(attrs: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return (input_tokens, output_tokens, total_tokens, reasoning_tokens)."""
    input_t = _int(
        get_attribute(attrs, "gen_ai.usage.input_tokens")
        or get_attribute(attrs, "gen_ai.usage.prompt_tokens")
        or get_attribute(attrs, "llm.token_count.prompt")
        or get_attribute(attrs, "ai.usage.promptTokens")
    )
    output_t = _int(
        get_attribute(attrs, "gen_ai.usage.output_tokens")
        or get_attribute(attrs, "gen_ai.usage.completion_tokens")
        or get_attribute(attrs, "llm.token_count.completion")
        or get_attribute(attrs, "ai.usage.completionTokens")
    )
    total_t = _int(
        get_attribute(attrs, "llm.usage.total_tokens")
        or get_attribute(attrs, "llm.token_count.total")
    )
    if not total_t and (input_t or output_t):
        total_t = input_t + output_t

    reasoning_t = _int(
        get_attribute(attrs, "gen_ai.usage.reasoning_tokens")
    )

    return input_t, output_t, total_t, reasoning_t


def extract_request_params(attrs: dict[str, Any]) -> tuple[float, int, float]:
    """Return (temperature, max_tokens, top_p)."""
    temperature = _float(
        get_attribute(attrs, "gen_ai.request.temperature")
    )
    max_tokens = _int(
        get_attribute(attrs, "gen_ai.request.max_tokens")
    )
    top_p = _float(
        get_attribute(attrs, "gen_ai.request.top_p")
    )

    req_blob = get_attribute(attrs, "gen_ai.request")
    if isinstance(req_blob, dict):
        if not temperature:
            temperature = _float(req_blob.get("temperature"))
        if not max_tokens:
            max_tokens = _int(req_blob.get("max_tokens"))
        if not top_p:
            top_p = _float(req_blob.get("top_p"))

    params_blob = get_attribute(attrs, "llm.invocation_parameters")
    if isinstance(params_blob, dict):
        if not temperature:
            temperature = _float(params_blob.get("temperature"))
        if not max_tokens:
            max_tokens = _int(params_blob.get("max_tokens"))
        if not top_p:
            top_p = _float(params_blob.get("top_p"))

    return temperature, max_tokens, top_p


def _normalize_messages(raw: Any) -> list[tuple[str, str, str, str]]:
    """Normalize messages from various provider formats to (role, content, tool_call_id, tool_name) tuples."""
    if raw is None:
        return []

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return [("user", raw, "", "")]

    if isinstance(raw, dict):
        contents = raw.get("contents") or raw.get("parts")
        if contents and isinstance(contents, list):
            raw = contents

    if not isinstance(raw, list):
        return []

    result: list[tuple[str, str, str, str]] = []
    for item in raw:
        if isinstance(item, str):
            result.append(("user", item, "", ""))
            continue
        if not isinstance(item, dict):
            continue

        role = _str(item.get("role", ""))
        content = ""
        tool_call_id = _str(item.get("tool_call_id", ""))
        tool_name_val = _str(item.get("name", "") or item.get("tool_name", ""))

        raw_content = item.get("content")
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict):
                    t = part.get("text") or part.get("content", "")
                    if t:
                        text_parts.append(_str(t))
            content = "\n".join(text_parts)
        elif raw_content is not None:
            content = _str(raw_content)

        result.append((role, content, tool_call_id, tool_name_val))

    return result


def extract_messages(attrs: dict[str, Any]) -> tuple[
    list[tuple[str, str, str, str]],
    list[tuple[str, str, str, str]],
]:
    """Return (input_messages, output_messages) as normalized tuple lists."""
    input_raw = (
        get_attribute(attrs, "gen_ai.input.messages")
        or get_attribute(attrs, "gen_ai.prompt")
        or get_attribute(attrs, "gcp.vertex.agent.llm_request")
    )

    output_raw = (
        get_attribute(attrs, "gen_ai.output.messages")
        or get_attribute(attrs, "gen_ai.completion")
        or get_attribute(attrs, "gcp.vertex.agent.llm_response")
    )

    return _normalize_messages(input_raw), _normalize_messages(output_raw)


def extract_genai_fields(attrs: dict[str, Any], span_name: str) -> GenAIFields:
    """Extract all GenAI fields from OTel span attributes.

    Args:
        attrs: The span's attribute dictionary (may be nested or flattened).
        span_name: The span's name, used for provider/operation inference.

    Returns:
        GenAIFields with all extractable values populated.
    """
    operation_name = extract_operation_name(attrs, span_name)
    provider_name = extract_provider(attrs, span_name)
    request_model, response_model = extract_model(attrs)
    input_t, output_t, total_t, reasoning_t = extract_tokens(attrs)
    temperature, max_tokens, top_p = extract_request_params(attrs)
    input_msgs, output_msgs = extract_messages(attrs)

    response_id = _str(get_attribute(attrs, "gen_ai.response.id") or "")

    conversation_id = _str(
        get_attribute(attrs, "gen_ai.conversation.id")
        or get_attribute(attrs, "gcp.vertex.agent.session_id")
        or ""
    )

    agent_name = _str(
        get_attribute(attrs, "gen_ai.agent.name")
        or get_attribute(attrs, "agent.name")
        or ""
    )

    tool_name = _str(get_attribute(attrs, "gen_ai.tool.name") or "")

    finish_raw = get_attribute(attrs, "gen_ai.response.finish_reasons")
    finish_reasons: list[str] = []
    if isinstance(finish_raw, list):
        finish_reasons = [_str(r) for r in finish_raw]
    elif finish_raw:
        finish_reasons = [_str(finish_raw)]

    sys_raw = get_attribute(attrs, "gen_ai.system_instructions")
    system_instructions: list[str] = []
    if isinstance(sys_raw, list):
        system_instructions = [_str(s) for s in sys_raw]
    elif isinstance(sys_raw, str) and sys_raw:
        system_instructions = [sys_raw]

    tool_args = _str(get_attribute(attrs, "gen_ai.tool.call.arguments") or "")

    return GenAIFields(
        operation_name=operation_name,
        provider_name=provider_name,
        request_model=request_model,
        response_model=response_model,
        response_id=response_id,
        input_tokens=input_t,
        output_tokens=output_t,
        total_tokens=total_t,
        reasoning_tokens=reasoning_t,
        request_temperature=temperature,
        request_max_tokens=max_tokens,
        request_top_p=top_p,
        conversation_id=conversation_id,
        agent_name=agent_name,
        tool_name=tool_name,
        input_messages=input_msgs,
        output_messages=output_msgs,
        finish_reasons=finish_reasons,
        system_instructions=system_instructions,
        tool_call_arguments=tool_args,
    )
