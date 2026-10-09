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
from weave.trace_server.base64_content_conversion import DATA_URI_PATTERN
from weave.trace_server.opentelemetry.helpers import (
    get_attribute,
    to_json_serializable,
)

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
_METADATA_KEY = "metadata"
_INPUT_MESSAGES_KEY = "llm.input_messages"
_OUTPUT_MESSAGES_KEY = "llm.output_messages"
_PROMPTS_KEY = "llm.prompts"
_CHOICES_KEY = "llm.choices"
_TOOLS_KEY = "llm.tools"
_INPUT_VALUE_KEY = "input.value"
_OUTPUT_VALUE_KEY = "output.value"
_INPUT_MIME_TYPE_KEY = "input.mime_type"
_OUTPUT_MIME_TYPE_KEY = "output.mime_type"
_TEXT_MIME_TYPE = "text/plain"
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
# The `ls_integration` run metadata LangGraph and LangChain's `create_agent` set.
_LANGGRAPH_INTEGRATIONS = ("langgraph", "langchain_create_agent")
# The nodes `create_agent` adds to its graph, besides middleware hooks.
_CREATE_AGENT_NODES = ("model", "tools")
_MIDDLEWARE_HOOKS = ("before_agent", "before_model", "after_model", "after_agent")
_SYSTEM_ROLE = "system"
_USER_ROLE = "user"
_ASSISTANT_ROLE = "assistant"
_TOOL_ROLE = "tool"
_TEXT_CONTENT_TYPE = "text"
_FUNCTION_TOOL_TYPE = "function"


def operation_name(attrs: dict[str, Any], span_name: str, *, is_root: bool) -> str:
    """Map `openinference.span.kind` to a GenAI operation name, or "".

    The LangChain instrumentor labels a run AGENT when its name contains
    "agent", which makes `create_react_agent`'s `agent` model node look like an
    agent. LangGraph spans take agent identity from LangGraph run metadata
    instead: the outermost graph run (no `langgraph_node`) is the turn, and a
    named `create_agent` graph is a subagent (see `_is_named_agent_run`). Any
    other root CHAIN span is the turn, the shape GenAI agent SDKs emit.
    """
    kind = _span_kind(attrs)
    metadata = _metadata(attrs)
    if (
        kind in {_CHAIN_KIND, _AGENT_KIND}
        and metadata.get("ls_integration") in _LANGGRAPH_INTEGRATIONS
    ):
        is_agent = "langgraph_node" not in metadata or _is_named_agent_run(
            span_name, metadata
        )
        return OP_INVOKE_AGENT if is_agent else ""
    if kind == _CHAIN_KIND and is_root:
        return OP_INVOKE_AGENT
    return _KIND_TO_OPERATION.get(kind, "")


def input_messages(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """An LLM span's non-system input messages as GenAI messages."""
    return [m for m in _input_messages(attrs) if m["role"] != _SYSTEM_ROLE]


def output_messages(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """An LLM span's output as GenAI messages.

    Reads `llm.output_messages`, else the completion texts in `llm.choices`,
    else `output.value` (see `_value_messages`). Other span kinds yield none,
    as for input.
    """
    if _span_kind(attrs) != _LLM_KIND:
        return []
    return (
        _llm_messages(attrs, _OUTPUT_MESSAGES_KEY)
        or _text_messages(
            _ASSISTANT_ROLE, get_attribute(attrs, _CHOICES_KEY), "completion"
        )
        or _value_messages(
            get_attribute(attrs, _OUTPUT_VALUE_KEY),
            get_attribute(attrs, _OUTPUT_MIME_TYPE_KEY),
            _ASSISTANT_ROLE,
        )
    )


def system_instructions(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """The text parts of an LLM span's system-role input messages."""
    return [
        part
        for message in _input_messages(attrs)
        if message["role"] == _SYSTEM_ROLE
        for part in message["parts"]
        if part["type"] == _TEXT_CONTENT_TYPE
    ]


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


def _metadata(attrs: dict[str, Any]) -> dict[str, Any]:
    """The LangChain instrumentor's run `metadata`, a JSON object ingest decodes."""
    value = get_attribute(attrs, _METADATA_KEY)
    return value if isinstance(value, dict) else {}


def _is_named_agent_run(span_name: str, metadata: dict[str, Any]) -> bool:
    """Whether a LangGraph span is the run of the `create_agent` graph it names.

    The graph's own nodes inherit `lc_agent_name`. An agent named after one of
    them (`model`, `tools`, or a middleware hook such as `Audit.before_model`)
    therefore counts only as a graph run under a top-level node, where
    `checkpoint_ns` equals `langgraph_checkpoint_ns`. LangChain sets
    `checkpoint_ns` once, at the first nested level, so deeper runs of such an
    agent cannot be told from its nodes.
    """
    if span_name != metadata.get("lc_agent_name"):
        return False
    _, dot, hook = span_name.rpartition(".")
    if span_name not in _CREATE_AGENT_NODES and not (dot and hook in _MIDDLEWARE_HOOKS):
        return True
    checkpoint_ns = metadata.get("checkpoint_ns")
    return (
        isinstance(checkpoint_ns, str)
        and bool(checkpoint_ns)
        and checkpoint_ns == metadata.get("langgraph_checkpoint_ns")
    )


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
    if not isinstance(value, str) or not value.lstrip().startswith(("{", "[")):
        return value
    try:
        return json.loads(value)
    except (ValueError, RecursionError):
        return value


def _input_messages(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """An LLM span's input as GenAI messages, system messages included.

    Reads `llm.input_messages`, else the prompt texts in `llm.prompts`, else
    `input.value` (see `_value_messages`). Only LLM spans qualify: the
    LangChain instrumentor also writes partial `llm.input_messages` onto CHAIN
    spans from their graph state, and every span kind carries `input.value`.
    """
    if _span_kind(attrs) != _LLM_KIND:
        return []
    return (
        _llm_messages(attrs, _INPUT_MESSAGES_KEY)
        or _text_messages(_USER_ROLE, get_attribute(attrs, _PROMPTS_KEY), "prompt")
        or _value_messages(
            get_attribute(attrs, _INPUT_VALUE_KEY),
            get_attribute(attrs, _INPUT_MIME_TYPE_KEY),
            _USER_ROLE,
        )
    )


def _llm_messages(attrs: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Rebuild GenAI messages from flattened `<key>.<i>.message.*` attributes."""
    messages = []
    for item in _indexed(get_attribute(attrs, key)):
        message = item.get("message") if isinstance(item, dict) else None
        if isinstance(message, dict):
            messages.append(_genai_message(message))
    return messages


def _text_messages(role: str, value: Any, item_key: str) -> list[dict[str, Any]]:
    """Messages from `llm.prompts` or `llm.choices`.

    The LangChain instrumentor sends a list of strings; the OpenAI instrumentor
    sends `<key>.<i>.prompt.text` or `<key>.<i>.completion.text`.
    """
    messages = []
    for item in _indexed(value):
        text = item
        if isinstance(item, dict) and item_key in item:
            entry = item[item_key]
            text = entry.get("text") if isinstance(entry, dict) else None
        if isinstance(text, (dict, list)) or (isinstance(text, str) and text):
            messages.append(_text_message(role, _text(text)))
    return messages


def _value_messages(value: Any, mime_type: Any, role: str) -> list[dict[str, Any]]:
    """Messages from an LLM span's `input.value` or `output.value`.

    A `text/plain` value is one text message, re-serialized if ingest decoded
    it as JSON. Otherwise this reads plain text, an OpenAI message list (or a
    JSON object holding one in `messages`), an OpenAI chat or completions
    response (`choices`), a LangChain `LLMResult` (`generations`), and a JSON
    object with one string value, the shape `@tracer.llm` records for a
    one-argument function. Other values yield no messages.
    """
    if mime_type == _TEXT_MIME_TYPE:
        text = "" if value is None else _text(value)
        return [_text_message(role, text)] if text else []
    if isinstance(value, dict):
        if isinstance(value.get("messages"), list):
            value = value["messages"]
        elif isinstance(value.get("choices"), list):
            return _choice_messages(value["choices"])
        elif isinstance(value.get("generations"), list):
            return _generation_messages(value["generations"])
        elif len(value) == 1 and isinstance(text := next(iter(value.values())), str):
            value = text
    if isinstance(value, str):
        return [_text_message(role, value)] if value else []
    if isinstance(value, list):
        return [
            _openai_message(item)
            for item in value
            if isinstance(item, dict) and "role" in item
        ]
    return []


def _choice_messages(choices: list[Any]) -> list[dict[str, Any]]:
    messages = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if isinstance(choice.get("message"), dict):
            messages.append(_openai_message(choice["message"]))
        elif isinstance(choice.get("text"), str) and choice["text"]:
            messages.append(_text_message(_ASSISTANT_ROLE, choice["text"]))
    return messages


def _generation_messages(generations: list[Any]) -> list[dict[str, Any]]:
    """Messages from the first prompt's generations, as `llm.output_messages` reads them."""
    first = generations[0] if generations and isinstance(generations[0], list) else []
    return [
        _text_message(_ASSISTANT_ROLE, generation["text"])
        for generation in first
        if isinstance(generation, dict)
        and isinstance(generation.get("text"), str)
        and generation["text"]
    ]


def _genai_message(message: dict[str, Any]) -> dict[str, Any]:
    """A GenAI message from flattened OpenInference `message.*` attributes."""
    role = str(message.get("role") or "")
    content = message.get("content")
    parts: list[dict[str, Any]] = []
    if content is not None and content != "":
        parts.append(_text_part(content))
    for item in _indexed(message.get("contents")):
        message_content = (
            item.get("message_content") if isinstance(item, dict) else None
        )
        if not isinstance(message_content, dict):
            continue
        content_type = message_content.get("type")
        text = message_content.get("text")
        image = message_content.get("image")
        if (content_type is None or content_type == _TEXT_CONTENT_TYPE) and text:
            parts.append(_text_part(text))
        elif content_type == "image" and isinstance(image, dict):
            image_url = image.get("image")
            if isinstance(image_url, dict) and (part := _image_part(image_url)):
                parts.append(part)
    if role == _TOOL_ROLE:
        return _tool_response_message(
            message.get("tool_call_id"), _tool_response(content, parts)
        )
    for item in _indexed(message.get("tool_calls")):
        tool_call = item.get("tool_call") if isinstance(item, dict) else None
        if isinstance(tool_call, dict):
            parts.append(_tool_call_part(tool_call))
    return {"role": role, "parts": parts}


def _tool_response(content: Any, parts: list[dict[str, Any]]) -> Any:
    """A tool message's `content`, else its `contents` text, else its `contents` parts."""
    if (content is not None and content != "") or not parts:
        return content
    texts = [part["content"] for part in parts if part["type"] == _TEXT_CONTENT_TYPE]
    return "".join(texts) if len(texts) == len(parts) else parts


def _openai_message(message: dict[str, Any]) -> dict[str, Any]:
    """A GenAI message from an OpenAI chat message dict."""
    role = str(message.get("role") or "")
    content = message.get("content")
    if role == _TOOL_ROLE:
        return _tool_response_message(message.get("tool_call_id"), content)

    parts: list[dict[str, Any]] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            image_url = item.get("image_url")
            if item.get("type") == _TEXT_CONTENT_TYPE and text:
                parts.append(_text_part(text))
            elif isinstance(image_url, dict) and (part := _image_part(image_url)):
                parts.append(part)
    elif content is not None and content != "":
        parts.append(_text_part(content))
    for tool_call in _indexed(message.get("tool_calls")):
        if isinstance(tool_call, dict):
            parts.append(_tool_call_part(tool_call))
    return {"role": role, "parts": parts}


def _text_message(role: str, text: str) -> dict[str, Any]:
    return {"role": role, "parts": [_text_part(text)]}


def _text_part(value: Any) -> dict[str, Any]:
    return {"type": _TEXT_CONTENT_TYPE, "content": _text(value)}


def _image_part(image: dict[str, Any]) -> dict[str, Any] | None:
    """A GenAI image part from `{"url": ...}`; a base64 data URL becomes a blob part.

    Ingest has already replaced a data URL over 8 KiB with a content ref,
    which stays a `uri` part.
    """
    url = image.get("url")
    if not isinstance(url, str) or not url:
        return None
    if data_url := DATA_URI_PATTERN.match(url):
        return {
            "type": "blob",
            "modality": "image",
            "mime_type": data_url.group(1),
            "content": data_url.group(2),
        }
    return {"type": "uri", "modality": "image", "uri": url}


def _tool_call_part(tool_call: dict[str, Any]) -> dict[str, Any]:
    function = tool_call.get("function")
    if not isinstance(function, dict):
        function = {}
    return {
        "type": "tool_call",
        "id": tool_call.get("id"),
        "name": function.get("name"),
        "arguments": function.get("arguments"),
    }


def _tool_response_message(tool_call_id: Any, response: Any) -> dict[str, Any]:
    return {
        "role": _TOOL_ROLE,
        "parts": [
            {"type": "tool_call_response", "id": tool_call_id, "response": response}
        ],
    }


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


def _text(value: Any) -> str:
    """Return message text; ingest JSON-decodes strings that start with `{` or `[`."""
    if isinstance(value, str):
        return value
    return json.dumps(to_json_serializable(value), ensure_ascii=False)
