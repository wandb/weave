"""Extract GenAI typed column values from SDK call JSON dumps.

This module handles the case where LLM data arrives via the Weave SDK
(call_start/call_end) rather than OTel spans. The data is in inputs_dump,
output_dump, and summary_dump as JSON strings. For known integration
op_names, we can reliably extract model, tokens, messages, and parameters.
"""

import json
import logging
from typing import Any

from weave.trace_server.opentelemetry.genai_fields import GenAIFields

logger = logging.getLogger(__name__)

_KNOWN_CHAT_OP_PREFIXES = (
    "openai.chat.completions.",
    "openai.responses.",
    "anthropic.Messages.",
    "anthropic.AsyncMessages.",
    "anthropic.beta.Messages.",
    "mistralai.chat.",
    "groq.chat.completions.",
    "cohere.Client.chat",
    "google.genai.models.",
    "google_genai.",
    "vertexai.",
    "litellm.",
)

_OP_TO_PROVIDER: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "mistralai": "mistral",
    "groq": "groq",
    "cohere": "cohere",
    "google": "google",
    "vertexai": "google",
    "litellm": "litellm",
}


def _safe_json_loads(s: str | None) -> Any:
    if not s:
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return {}


def _extract_model_from_summary(summary: dict[str, Any]) -> str:
    """Extract model name from summary.usage keys.

    WeaveClient.finish_call() stores usage under summary["usage"][model_name].
    The model name IS the key (e.g. "gpt-4o", "claude-3-opus-20240229").
    """
    usage = summary.get("usage", {})
    if not isinstance(usage, dict):
        return ""
    for key in usage:
        if key != "usage":
            return key
    return ""


def _extract_tokens_from_summary(
    summary: dict[str, Any], model: str
) -> tuple[int, int, int]:
    """Extract token counts from summary.usage[model]."""
    usage = summary.get("usage", {})
    if not isinstance(usage, dict):
        return 0, 0, 0

    model_usage = usage.get(model) or usage.get("usage") or {}
    if not isinstance(model_usage, dict):
        return 0, 0, 0

    input_t = (
        model_usage.get("prompt_tokens")
        or model_usage.get("input_tokens")
        or 0
    )
    output_t = (
        model_usage.get("completion_tokens")
        or model_usage.get("output_tokens")
        or 0
    )
    total_t = model_usage.get("total_tokens") or 0
    if not total_t and (input_t or output_t):
        total_t = int(input_t) + int(output_t)

    return int(input_t), int(output_t), int(total_t)


def _provider_from_op_name(op_name: str) -> str:
    """Infer provider from op_name prefix."""
    bare = op_name.split("///")[-1] if "///" in op_name else op_name
    for prefix, provider in _OP_TO_PROVIDER.items():
        if bare.startswith(prefix):
            return provider
    return ""


def _is_known_chat_op(op_name: str) -> bool:
    bare = op_name.split("///")[-1] if "///" in op_name else op_name
    for part in bare.split("/"):
        for prefix in _KNOWN_CHAT_OP_PREFIXES:
            if part.startswith(prefix):
                return True
    return False


def _normalize_sdk_messages(
    messages: Any,
) -> list[tuple[str, str, str, str]]:
    """Normalize messages from SDK inputs into (role, content, tool_call_id, tool_name) tuples."""
    if not isinstance(messages, list):
        return []

    result: list[tuple[str, str, str, str]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", ""))
        content = ""
        raw = msg.get("content")
        if isinstance(raw, str):
            content = raw
        elif isinstance(raw, list):
            parts = []
            for p in raw:
                if isinstance(p, str):
                    parts.append(p)
                elif isinstance(p, dict):
                    t = p.get("text") or p.get("content", "")
                    if t:
                        parts.append(str(t))
            content = "\n".join(parts)
        tool_call_id = str(msg.get("tool_call_id", ""))
        tool_name = str(msg.get("name", "") or msg.get("tool_name", ""))
        result.append((role, content, tool_call_id, tool_name))
    return result


def _extract_output_messages(output: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Extract output messages from a ChatCompletion-shaped output."""
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return []

    result: list[tuple[str, str, str, str]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        msg = choice.get("message", {})
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "assistant"))
        content = str(msg.get("content", "") or "")
        result.append((role, content, "", ""))
    return result


def extract_genai_from_call(
    op_name: str,
    inputs_dump: str | None,
    output_dump: str | None,
    summary_dump: str | None,
) -> GenAIFields | None:
    """Extract GenAI fields from SDK call dumps for known integration op_names.

    Args:
        op_name: The call's op_name (may include weave:/// ref prefix).
        inputs_dump: JSON string of inputs.
        output_dump: JSON string of output.
        summary_dump: JSON string of summary.

    Returns:
        GenAIFields if the op is a known LLM integration call, None otherwise.
    """
    if not _is_known_chat_op(op_name):
        return None

    try:
        summary = _safe_json_loads(summary_dump)
        inputs = _safe_json_loads(inputs_dump)
        output = _safe_json_loads(output_dump)

        model = _extract_model_from_summary(summary)
        if not model:
            model = str(inputs.get("model", ""))

        input_t, output_t, total_t = _extract_tokens_from_summary(summary, model)

        provider = _provider_from_op_name(op_name)

        temperature = 0.0
        raw_temp = inputs.get("temperature")
        if raw_temp is not None:
            try:
                temperature = float(raw_temp)
            except (ValueError, TypeError):
                pass

        max_tokens = 0
        raw_max = inputs.get("max_tokens") or inputs.get("max_completion_tokens")
        if raw_max is not None:
            try:
                max_tokens = int(raw_max)
            except (ValueError, TypeError):
                pass

        top_p = 0.0
        raw_top_p = inputs.get("top_p")
        if raw_top_p is not None:
            try:
                top_p = float(raw_top_p)
            except (ValueError, TypeError):
                pass

        input_msgs = _normalize_sdk_messages(inputs.get("messages", []))
        output_msgs = _extract_output_messages(output) if isinstance(output, dict) else []

        response_model = ""
        if isinstance(output, dict):
            response_model = str(output.get("model", ""))

        finish_reasons: list[str] = []
        if isinstance(output, dict):
            choices = output.get("choices", [])
            if isinstance(choices, list):
                for c in choices:
                    if isinstance(c, dict) and c.get("finish_reason"):
                        finish_reasons.append(str(c["finish_reason"]))

        return GenAIFields(
            operation_name="chat",
            provider_name=provider,
            request_model=model,
            response_model=response_model,
            input_tokens=input_t,
            output_tokens=output_t,
            total_tokens=total_t,
            request_temperature=temperature,
            request_max_tokens=max_tokens,
            request_top_p=top_p,
            input_messages=input_msgs,
            output_messages=output_msgs,
            finish_reasons=finish_reasons,
        )
    except Exception:
        logger.debug("Failed to extract GenAI fields from SDK call", exc_info=True)
        return None
