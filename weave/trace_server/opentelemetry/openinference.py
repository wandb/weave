"""OpenInference fallbacks for agent span columns.

OpenInference instrumentors, such as openinference-instrumentation-langchain for
LangGraph, describe spans with `openinference.span.kind` and `llm.*`, `tool.*`,
`agent.name`, and `session.id` keys instead of `gen_ai.*`. `genai_extraction`
reads these keys only after every `weave.*` and `gen_ai.*` key for the same
column misses, so a span carrying both keeps its GenAI values.

Spec: https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md
"""

import json
from typing import Any

from weave.trace_server.agents.constants import OP_EXECUTE_TOOL, OP_INVOKE_AGENT
from weave.trace_server.opentelemetry.helpers import get_attribute

PROVIDER_KEYS = ("llm.provider", "llm.system")
# OpenInference usually sends one `llm.model_name`; the Agents UI groups and
# filters on request_model, so it fills both model columns.
REQUEST_MODEL_KEYS = ("llm.request.model_name", "llm.model_name")
RESPONSE_MODEL_KEYS = ("llm.response.model_name", "llm.model_name")
INPUT_TOKENS_KEYS = ("llm.token_count.prompt",)
OUTPUT_TOKENS_KEYS = ("llm.token_count.completion",)
REASONING_TOKENS_KEYS = ("llm.token_count.completion_details.reasoning",)
CACHE_READ_INPUT_TOKENS_KEYS = ("llm.token_count.prompt_details.cache_read",)
CACHE_CREATION_INPUT_TOKENS_KEYS = ("llm.token_count.prompt_details.cache_write",)
FINISH_REASON_KEYS = ("llm.finish_reason",)
CONVERSATION_ID_KEYS = ("session.id",)
AGENT_NAME_KEYS = ("agent.name",)
TOOL_NAME_KEYS = ("tool.name",)
TOOL_DESCRIPTION_KEYS = ("tool.description",)
TOOL_CALL_ID_KEYS = ("tool.id",)

_SPAN_KIND_KEY = "openinference.span.kind"
_TOOLS_KEY = "llm.tools"
_INPUT_VALUE_KEY = "input.value"
_OUTPUT_VALUE_KEY = "output.value"
_LLM_KIND = "LLM"
_TOOL_KIND = "TOOL"
_CHAIN_KIND = "CHAIN"
_AGENT_KIND = "AGENT"
_KIND_TO_OPERATION = {
    _LLM_KIND: "chat",
    _TOOL_KIND: OP_EXECUTE_TOOL,
    _AGENT_KIND: OP_INVOKE_AGENT,
    "EMBEDDING": "embeddings",
    "RETRIEVER": "retrieval",
}
_TOOL_ROLE = "tool"
_FUNCTION_TOOL_TYPE = "function"


def operation_name(attrs: dict[str, Any], *, is_root: bool) -> str:
    """Map `openinference.span.kind` to a GenAI operation name, or "".

    A CHAIN span with no parent in its process is the turn, so it maps to
    `invoke_agent`, the shape GenAI agent SDKs emit. LangGraph reports its root
    graph span as CHAIN unless the graph's name contains "agent".
    """
    kind = _span_kind(attrs)
    if kind == _CHAIN_KIND and is_root:
        return OP_INVOKE_AGENT
    return _KIND_TO_OPERATION.get(kind, "")


def tool_definitions(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """An LLM span's `llm.tools` as GenAI tool definitions.

    Each `llm.tools.<i>.tool.json_schema` holds the provider's tool dict, such
    as OpenAI's `{"type": "function", "function": {...}}` or Anthropic's
    `{"name", "input_schema"}`. It is flattened to `{"type", "name",
    "description", "parameters"}`, the shape the Agents UI reads, with
    `tool.name` and `tool.description` winning over the schema's values.
    """
    if _span_kind(attrs) != _LLM_KIND:
        return []
    definitions = []
    for item in _indexed(get_attribute(attrs, _TOOLS_KEY)):
        tool = item.get("tool") if isinstance(item, dict) else None
        if isinstance(tool, dict) and (definition := _tool_definition(tool)):
            definitions.append(definition)
    return definitions


def tool_call_arguments(attrs: dict[str, Any]) -> Any:
    """A TOOL span's `input.value`, or None for other span kinds."""
    if _span_kind(attrs) != _TOOL_KIND:
        return None
    return get_attribute(attrs, _INPUT_VALUE_KEY)


def tool_call_result(attrs: dict[str, Any]) -> Any:
    """A TOOL span's `output.value`, or None for other span kinds.

    The LangChain instrumentor records the `ToolMessage` a tool returns, so
    the result is that message's content.
    """
    if _span_kind(attrs) != _TOOL_KIND:
        return None
    value = get_attribute(attrs, _OUTPUT_VALUE_KEY)
    if (message := _tool_message(value)) is not None:
        return message.get("content")
    return value


def tool_call_id(attrs: dict[str, Any]) -> str:
    """The `tool_call_id` of the LangChain `ToolMessage` a TOOL span returned."""
    if _span_kind(attrs) != _TOOL_KIND:
        return ""
    message = _tool_message(get_attribute(attrs, _OUTPUT_VALUE_KEY))
    return str((message or {}).get("tool_call_id") or "")


def _span_kind(attrs: dict[str, Any]) -> str:
    return str(get_attribute(attrs, _SPAN_KIND_KEY) or "").upper()


def _tool_message(value: Any) -> dict[str, Any] | None:
    """The `data` of a serialized LangChain `ToolMessage`, or None.

    Requires the message's own `type`, `content` and `tool_call_id`, so a tool
    that returns `{"type": "tool", "data": ...}` itself keeps its result.
    """
    value = _json_value(value)
    if not isinstance(value, dict) or value.get("type") != _TOOL_ROLE:
        return None
    data = value.get("data")
    if (
        isinstance(data, dict)
        and data.get("type") == _TOOL_ROLE
        and "content" in data
        and "tool_call_id" in data
    ):
        return data
    return None


def _tool_definition(tool: dict[str, Any]) -> dict[str, Any] | None:
    schema = _json_value(tool.get("json_schema"))
    if not isinstance(schema, dict):
        schema = {}
    function = schema.get("function")
    if not isinstance(function, dict):
        function = schema
    definition = {
        "type": schema.get("type") or _FUNCTION_TOOL_TYPE,
        "name": tool.get("name") or function.get("name"),
        "description": tool.get("description") or function.get("description"),
        "parameters": function.get("parameters", function.get("input_schema")),
    }
    if not definition["name"]:
        return None
    return {key: value for key, value in definition.items() if value is not None}


def _json_value(value: Any) -> Any:
    """Decode a JSON string that ingest left as text, such as one with leading whitespace."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _indexed(value: Any) -> list[Any]:
    """Items of an expanded OpenInference list: a dict keyed "0", "1", ... or a list.

    Reads without mutating, unlike `convert_numeric_keys_to_list`, because the
    span's attributes are dumped verbatim after extraction.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value[key] for key in sorted(filter(str.isdecimal, value), key=int)]
    return []
