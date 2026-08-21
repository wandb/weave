"""Turn a window of calls into the span shape the agents product reads.

The output is plain dicts holding the project's own ids and ISO timestamps. Encoding them for the
wire is `otlp_export`'s job, so this module stays a readable description of the mapping.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from payload_paths import Row, last_user_message_text, resolve, resolve_text


def build_spans(
    calls: list[Row], mapping: dict[str, list[str]]
) -> list[dict[str, object]]:
    """One span per call, in the vocabulary the agents product reads."""
    tools, agents = tool_ops(calls), agent_ops(calls)
    by_trace: dict[str, list[Row]] = {}
    for call in calls:
        by_trace.setdefault(str(call.get("trace_id") or ""), []).append(call)

    spans: list[dict[str, object]] = []
    for trace_id, trace_calls in by_trace.items():
        root = next((call for call in trace_calls if not call.get("parent_id")), None)
        if root is None:
            continue
        # A root carrying no conversation key becomes its own single-turn conversation, which
        # keeps traces that predate the project's session concept instead of dropping them.
        conversation = resolve_text(root, mapping["conversation"]) or trace_id
        user_text, assistant_text = turn_texts(root, trace_calls, mapping)
        for call in trace_calls:
            spans.append(
                _span(
                    call,
                    conversation=conversation,
                    is_root=call is root,
                    is_tool=call is not root and op_short(call) in tools,
                    is_agent=call is root or op_short(call) in agents,
                    turn_model=_answer_model(trace_calls) if call is root else "",
                    user_text=user_text if call is root else "",
                    assistant_text=assistant_text if call is root else "",
                )
            )
    return spans


def _span(
    call: Row,
    *,
    conversation: str,
    is_root: bool,
    is_tool: bool,
    is_agent: bool,
    turn_model: str,
    user_text: str,
    assistant_text: str,
) -> dict[str, object]:
    model = model_of(call)
    # A root that is itself a model call is still the turn, not a bare chat span.
    if is_tool:
        operation = EXECUTE_TOOL
    elif is_root or (is_agent and not model):
        operation = INVOKE_AGENT
    elif model:
        operation = CHAT
    else:
        operation = ""
    agent = op_short(call) if operation == INVOKE_AGENT else ""
    subject = op_short(call) if is_tool else (model or agent)

    attributes: dict[str, object] = {"weave.operation.name": operation}
    # Only a tool span goes without the conversation. Leaving it off the model spans would hide
    # their tokens from every conversation-scoped total, which is what zeroes out turn cost.
    if not is_tool:
        attributes["weave.conversation.id"] = conversation
    if agent:
        attributes["weave.agent.name"] = agent
    if model or turn_model:
        attributes["weave.request.model"] = model or turn_model
        attributes["weave.response.model"] = model or turn_model
    if model:
        attributes["weave.provider.name"] = _provider(model)
    if is_tool:
        attributes["weave.tool.name"] = op_short(call)
        attributes["weave.tool.call.id"] = str(call.get("id") or "")
        attributes["weave.tool.call.arguments"] = _json(call.get("inputs"))
        attributes["weave.tool.call.result"] = _json(call.get("output"))
    for name, count in usage_of(call).items():
        attributes[USAGE_ATTRIBUTES[name]] = count
    if is_root:
        if user_text:
            attributes["weave.input.messages"] = _json(
                [{"role": "user", "content": user_text}]
            )
        if assistant_text:
            attributes["weave.output.messages"] = _json(
                [{"role": "assistant", "content": assistant_text}]
            )

    return {
        "trace_id": str(call.get("trace_id") or ""),
        "span_id": str(call.get("id") or ""),
        "parent_span_id": str(call.get("parent_id") or ""),
        "name": f"{operation} {subject}".strip() or op_short(call),
        # A model call leaves the process; everything else is internal work.
        "kind": "CLIENT" if model else "INTERNAL",
        "started_at": str(call.get("started_at") or ""),
        "ended_at": str(call.get("ended_at") or call.get("started_at") or ""),
        # Emitters mark a healthy span UNSET rather than OK; only failures carry a status.
        "error": bool(call.get("exception")),
        "attributes": {
            key: value for key, value in attributes.items() if value not in {"", None}
        },
    }


def turn_texts(
    root: Row, trace_calls: list[Row], mapping: dict[str, list[str]]
) -> tuple[str, str]:
    """User text from the root; assistant text from the last model child when one exists."""
    user = last_user_message_text(root) or resolve_text(root, mapping["user"])
    children = [call for call in trace_calls if model_of(call) and call is not root]
    if children:
        last = max(children, key=lambda call: str(call.get("started_at") or ""))
        assistant = resolve_text(last, mapping["assistant"]) or resolve_text(
            root, mapping["assistant"]
        )
    else:
        assistant = resolve_text(root, mapping["assistant"])
    return user, assistant


def _answer_model(trace_calls: list[Row]) -> str:
    """The model that produced the reply: the last one that actually reported tokens."""
    model_calls = sorted(
        (call for call in trace_calls if model_of(call)),
        key=lambda call: str(call.get("started_at") or ""),
    )
    priced = [call for call in model_calls if usage_of(call).get("input")]
    return model_of((priced or model_calls)[-1]) if (priced or model_calls) else ""


def agent_ops(calls: list[Row]) -> frozenset[str]:
    """Ops with a model call somewhere beneath them: the system's actual agents."""
    by_id = {str(call.get("id")): call for call in calls}
    marked: set[str] = set()
    for call in calls:
        if not model_of(call):
            continue
        parent = str(call.get("parent_id") or "")
        while parent and parent not in marked:
            marked.add(parent)
            parent = str(by_id.get(parent, {}).get("parent_id") or "")
    return frozenset(op_short(by_id[call_id]) for call_id in marked if call_id in by_id)


def tool_ops(calls: list[Row]) -> frozenset[str]:
    """Ops that are always childless and never name a model: the agent's tool surface."""
    parents = {str(call.get("parent_id")) for call in calls if call.get("parent_id")}
    grouped: dict[str, list[Row]] = {}
    for call in calls:
        grouped.setdefault(op_short(call), []).append(call)
    return frozenset(
        op
        for op, group in grouped.items()
        if all(
            call.get("parent_id")
            and str(call.get("id")) not in parents
            and not model_of(call)
            for call in group
        )
    )


def model_of(call: Row) -> str:
    """The model this call invoked, which is what separates a model call from its wrapper."""
    for path in ("output.model", "inputs.model"):
        model = resolve(call, path)
        if isinstance(model, str) and model:
            return model
    return ""


def usage_of(call: Row) -> dict[str, int]:
    """Token counts from the model call's own payload.

    Only calls naming a model are read: a wrapper op repeats the usage of the model calls beneath
    it, so counting every op that carries a `usage` block multiplies the trace's real tokens.
    """
    usage = resolve(call, "output.usage")
    if not isinstance(usage, Mapping):
        return {}
    counts = {
        "input": _first_int(usage, ("input_tokens", "inputTokens", "prompt_tokens")),
        "output": _first_int(
            usage, ("output_tokens", "outputTokens", "completion_tokens")
        ),
        "reasoning": _nested_int(usage, "output_tokens_details", ("reasoning_tokens",)),
        "cache_read": _first_int(usage, ("cache_read_input_tokens",))
        or _nested_int(usage, "prompt_tokens_details", ("cached_tokens",))
        or _nested_int(usage, "input_tokens_details", ("cached_tokens",)),
        "cache_write": _first_int(usage, ("cache_creation_input_tokens",)),
    }
    return {key: value for key, value in counts.items() if value}


def op_short(row: Row) -> str:
    """The op's bare name, dropping the `weave:///entity/project/op:` envelope and its digest."""
    return str(row.get("op_name") or "").split("/")[-1].split(":")[0]


def _provider(model: str) -> str:
    lowered = model.lower()
    for prefix, provider in PROVIDERS:
        if lowered.startswith(prefix):
            return provider
    return ""


def _json(value: object) -> str:
    if value in (None, "", {}, []):
        return ""
    return json.dumps(value, default=str)[:MAX_JSON_CHARS]


def _first_int(payload: Mapping[str, object], keys: tuple[str, ...]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return 0


def _nested_int(
    payload: Mapping[str, object], field: str, keys: tuple[str, ...]
) -> int:
    detail = payload.get(field)
    if isinstance(detail, list):
        return sum(
            _first_int(item, keys) for item in detail if isinstance(item, Mapping)
        )
    return _first_int(detail, keys) if isinstance(detail, Mapping) else 0


INVOKE_AGENT = "invoke_agent"

EXECUTE_TOOL = "execute_tool"

CHAT = "chat"

USAGE_ATTRIBUTES = {
    "input": "weave.usage.input_tokens",
    "output": "weave.usage.output_tokens",
    "reasoning": "weave.usage.reasoning_tokens",
    "cache_read": "weave.usage.cache_read.input_tokens",
    "cache_write": "weave.usage.cache_creation.input_tokens",
}

PROVIDERS = (
    ("gpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("claude", "anthropic"),
    ("gemini", "gcp.gemini"),
    ("llama", "meta"),
)

MAX_JSON_CHARS = 16_000
