"""Generalized OTEL span-to-events parser.

Converts OTEL spans from *any* LLM instrumentation library into a normalized
list of :class:`OtelEvent` objects with structured inputs, outputs, and
parent–child relationships.

Architecture
------------
Each OTEL span is converted to exactly one :class:`OtelEvent`::

    OtelEvent(
        id        = span_id,
        parent_id = parent span_id  (None ↔ root),
        inputs    = what was provided to this step,
        output    = what this step produced,
        ...metadata (model, provider, usage, timing, status)
    )

The resulting event list mirrors the span tree::

    root (type=agent / chain / unknown)
    ├── LLM call    inputs=[system, user]       output=assistant-response
    │   └── tool    inputs=<call-args>          output=<tool-result>
    └── LLM call    inputs=[...full-history...] output=final-response

Key semantics
~~~~~~~~~~~~~
- **Child context**: when a span has a parent, its ``inputs`` represent what
  was explicitly passed to that step (e.g. function arguments for a tool
  call).  The parent–child link expresses *why* those inputs exist.
- **Outermost LLM calls** (direct children of the root): because instrumented
  LLM clients include the full conversation history in each API call, the
  *last* such event's ``inputs`` naturally contains all prior turns.

Supported instrumentation sources
----------------------------------
- OpenAI SDK  (``gen_ai.input.messages`` / ``gen_ai.output.messages``)
- Anthropic SDK (same via logfire / opentelemetry-instrumentation-anthropic)
- PydanticAI   (``pydantic_ai.all_messages`` / ``final_result``)
- Google GenAI (span events: ``gen_ai.user.message``, ``gen_ai.choice``, …)
- OpenAI Agents via logfire (span events)
- LangChain / LlamaIndex (``gen_ai.prompt``, ``input.value``, ``output.value``)
- Vercel AI SDK (``ai.prompt``, ``ai.response``)
- MLFlow (``mlflow.spanInputs``, ``mlflow.spanOutputs``)
- Traceloop / OpenLLMetry (``traceloop.entity.*``)
- Google Vertex AI (``gcp.vertex.agent.*``)
- Generic spans (``input`` / ``inputs``, ``output`` / ``outputs``)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from weave.trace_server.opentelemetry.python_spans import Span

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """Coarse classification of a span's role in an LLM pipeline."""

    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    CHAIN = "chain"
    RETRIEVAL = "retrieval"
    EMBEDDING = "embedding"
    UNKNOWN = "unknown"


@dataclass
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def as_dict(self) -> dict[str, int]:
        return {
            k: v
            for k, v in (
                ("input_tokens", self.input_tokens),
                ("output_tokens", self.output_tokens),
                ("total_tokens", self.total_tokens),
            )
            if v is not None
        }


@dataclass
class OtelEvent:
    """A single execution step extracted from one OTEL span.

    ``inputs`` and ``output`` carry framework-agnostic representations:

    * **LLM call** — ``inputs`` is a list of chat-message dicts
      (each with ``role`` + ``content`` / ``tool_calls`` / …);
      ``output`` is the assistant-message dict (or list thereof for
      multi-choice responses).
    * **Tool call** — ``inputs`` is a dict of function arguments;
      ``output`` is the tool's return value.
    * **Agent / Chain** — ``inputs`` and ``output`` mirror the span's
      generic input/output attributes.

    Message dict shape (normalised from all supported conventions)::

        {
            "role":         "system" | "user" | "assistant" | "tool",
            "content":      str | list[str | dict],   # text or parts
            "tool_calls":   [{"id": ..., "name": ..., "arguments": ...}],  # optional
            "tool_call_id": str,                       # for role="tool"
            "name":         str,                       # tool name if role="tool"
            "finish_reason": str,                      # for output messages
        }
    """

    id: str
    trace_id: str
    name: str
    type: EventType
    parent_id: str | None

    # Structured inputs: message list (LLM) or arg dict (tool/generic)
    inputs: list[dict[str, Any]] | dict[str, Any]
    # Structured output: message dict, message list, scalar, or None
    output: Any

    model: str | None = None
    provider: str | None = None
    usage: TokenUsage | None = None
    started_at: str | None = None   # ISO-8601
    ended_at: str | None = None     # ISO-8601
    status: str = "success"         # "success" | "error"
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "trace_id": self.trace_id,
            "name": self.name,
            "type": self.type.value,
            "parent_id": self.parent_id,
            "inputs": self.inputs,
            "output": self.output,
            "status": self.status,
        }
        if self.model is not None:
            d["model"] = self.model
        if self.provider is not None:
            d["provider"] = self.provider
        if self.usage is not None:
            d["usage"] = self.usage.as_dict()
        if self.started_at is not None:
            d["started_at"] = self.started_at
        if self.ended_at is not None:
            d["ended_at"] = self.ended_at
        if self.error is not None:
            d["error"] = self.error
        return d


@dataclass
class OtelTrace:
    """All events for a single OTEL trace, ordered by start time.

    ``events`` is a **flat** list; parent–child relationships are encoded
    via :attr:`OtelEvent.parent_id`.  The root event is identified by
    :attr:`root_id`.
    """

    trace_id: str
    root_id: str | None
    events: list[OtelEvent] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_id": self.root_id,
            "events": [e.as_dict() for e in self.events],
        }


# ---------------------------------------------------------------------------
# Attribute-key priority tables
# ---------------------------------------------------------------------------

# Checked in order; first non-None value wins.
_INPUT_ATTR_KEYS: list[str] = [
    "gen_ai.input.messages",            # OTel Gen AI semconv v2 (logfire, pydantic-ai)
    "pydantic_ai.all_messages",         # PydanticAI full history (handled specially)
    "gen_ai.prompt",                    # OTel Gen AI semconv v1
    "input.value",                      # OpenInference
    "mlflow.spanInputs",                # MLFlow
    "ai.prompt",                        # Vercel AI SDK
    "gcp.vertex.agent.llm_request",     # Google Vertex AI
    "traceloop.entity.input",           # Traceloop / OpenLLMetry
    "input",                            # generic
    "inputs",                           # generic
]

_OUTPUT_ATTR_KEYS: list[str] = [
    "gen_ai.output.messages",           # OTel Gen AI semconv v2
    "final_result",                     # PydanticAI
    "gen_ai.completion",                # OTel Gen AI semconv v1
    "output.value",                     # OpenInference
    "gen_ai.content.completion",        # OpenLit
    "mlflow.spanOutputs",               # MLFlow
    "ai.response",                      # Vercel AI SDK
    "gcp.vertex.agent.llm_response",    # Google Vertex AI
    "traceloop.entity.output",          # Traceloop / OpenLLMetry
    "output",                           # generic
    "outputs",                          # generic
]

# Span-event names that carry conversation history (inputs side)
_CONV_HISTORY_EVENT_NAMES: frozenset[str] = frozenset({
    "gen_ai.system.message",
    "gen_ai.user.message",
    "gen_ai.assistant.message",  # includes tool-call invocations mid-turn
    "gen_ai.tool.message",       # tool results fed back to the model
})

# Span-event names that carry the model's choice / final response
_CHOICE_EVENT_NAMES: frozenset[str] = frozenset({
    "gen_ai.choice",
})

# Attributes that positively identify an LLM span
_LLM_INDICATOR_ATTRS: frozenset[str] = frozenset({
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.prompt",
    "gen_ai.completion",
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.prompt_tokens",
    "llm.model_name",
    "ai.model.id",
    "pydantic_ai.all_messages",
})

# openinference.span.kind / traceloop.span.kind → EventType
_SPAN_KIND_MAP: dict[str, EventType] = {
    "llm": EventType.LLM,
    "LLM": EventType.LLM,
    "embedding": EventType.EMBEDDING,
    "EMBEDDING": EventType.EMBEDDING,
    "chain": EventType.CHAIN,
    "CHAIN": EventType.CHAIN,
    "agent": EventType.AGENT,
    "AGENT": EventType.AGENT,
    "tool": EventType.TOOL,
    "TOOL": EventType.TOOL,
    "retriever": EventType.RETRIEVAL,
    "RETRIEVER": EventType.RETRIEVAL,
    "workflow": EventType.CHAIN,
    "WORKFLOW": EventType.CHAIN,
    "task": EventType.CHAIN,
    "TASK": EventType.CHAIN,
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _try_json(value: Any) -> Any:
    """Return ``json.loads(value)`` if *value* is a JSON string, else *value*."""
    if isinstance(value, str) and value and value[0] in ("{", "[", '"'):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return value


def _get_attr(attrs: dict[str, Any], key: str) -> Any:
    """Retrieve an attribute by dotted key from a (possibly nested) dict."""
    val = attrs.get(key)
    if val is not None:
        return val
    if "." not in key:
        return None
    node: Any = attrs
    for part in key.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit():
            idx = int(part)
            node = node[idx] if idx < len(node) else None
        else:
            return None
        if node is None:
            return None
    return node


def _first_attr(attrs: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        v = _get_attr(attrs, key)
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------------
# Message normalisation
# ---------------------------------------------------------------------------


def _normalise_part(part: Any) -> Any:
    """Simplify a single content part into a string or compact dict."""
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return str(part)
    ptype = part.get("type", "")
    if ptype == "text":
        return part.get("content", "")
    if ptype == "output_text":
        return part.get("text", "")
    # uri / blob / tool_call / tool_call_response → keep compact
    return {k: v for k, v in part.items() if v is not None}


def _normalise_message(raw: Any) -> dict[str, Any] | None:
    """Normalise one raw message from any convention into the common shape.

    Returns ``None`` for dicts that don't look like messages (no ``role`` /
    ``parts`` / ``tool_calls`` / ``tool_call_id`` key), so that generic
    attribute dicts (e.g. ``{"x": 1}``) are not silently treated as messages.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return {"role": "user", "content": raw}
    if not isinstance(raw, dict):
        return {"role": "unknown", "content": str(raw)}

    # Reject plain dicts that have no message-like keys.
    # Note: "content" alone is not enough — {"type": "text", "content": "..."}
    # is a MessagePart, not a message; we require "role" or "parts" as well.
    _MSG_KEYS = {"role", "parts", "tool_calls", "tool_call_id"}
    if not any(k in raw for k in _MSG_KEYS):
        return None

    role: str = raw.get("role") or "unknown"

    # ── logfire v2 / OTel semconv: {"role": ..., "parts": [...]} ──────────
    if "parts" in raw:
        parts = raw["parts"] if isinstance(raw["parts"], list) else [raw["parts"]]
        text_parts: list[Any] = []
        tool_calls: list[dict[str, Any]] = []
        tool_call_id: str | None = None
        tool_name: str | None = None

        for part in parts:
            if not isinstance(part, dict):
                text_parts.append(str(part))
                continue
            ptype = part.get("type", "")
            if ptype == "text":
                text_parts.append(part.get("content", ""))
            elif ptype == "tool_call":
                tool_calls.append({
                    "id": part.get("id", ""),
                    "name": part.get("name", ""),
                    "arguments": part.get("arguments"),
                })
            elif ptype == "tool_call_response":
                tool_call_id = part.get("id") or tool_call_id
                tool_name = raw.get("name") or tool_name
                resp = part.get("response", "")
                text_parts.append(resp if isinstance(resp, str) else json.dumps(resp))
            elif ptype in ("uri", "blob"):
                text_parts.append(_normalise_part(part))
            else:
                text_parts.append(_normalise_part(part))

        msg: dict[str, Any] = {"role": role}
        if len(text_parts) == 1 and isinstance(text_parts[0], str):
            msg["content"] = text_parts[0]
        elif text_parts:
            msg["content"] = text_parts
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        if tool_name:
            msg["name"] = tool_name
        if fr := raw.get("finish_reason"):
            msg["finish_reason"] = fr
        return msg

    # ── plain dict: {"role": ..., "content": ...} ─────────────────────────
    msg = {"role": role}
    if (content := raw.get("content")) is not None:
        msg["content"] = content
    if tcs := raw.get("tool_calls"):
        msg["tool_calls"] = tcs
    if tcid := raw.get("tool_call_id"):
        msg["tool_call_id"] = tcid
    if name := raw.get("name"):
        msg["name"] = name
    if fr := raw.get("finish_reason"):
        msg["finish_reason"] = fr
    return msg


def _normalise_messages(value: Any) -> list[dict[str, Any]]:
    """Return a list of normalised message dicts from any raw representation."""
    if value is None:
        return []
    value = _try_json(value)
    if isinstance(value, list):
        return [m for raw in value if (m := _normalise_message(raw)) is not None]
    if isinstance(value, dict):
        m = _normalise_message(value)
        return [m] if m else []
    if isinstance(value, str):
        return [{"role": "user", "content": value}]
    return []


def _system_instructions_to_msg(raw: Any) -> dict[str, Any] | None:
    """Convert ``gen_ai.system_instructions`` (a list of MessageParts) to a system message.

    ``gen_ai.system_instructions`` is defined as ``list[MessagePart]`` in the
    OTel Gen AI semconv — it is *not* a list of messages.  Each part is a
    dict like ``{"type": "text", "content": "..."}`` or a plain string.
    """
    parsed = _try_json(raw)
    if parsed is None:
        return None
    if isinstance(parsed, str):
        return {"role": "system", "content": parsed}
    if isinstance(parsed, list):
        texts: list[Any] = []
        for p in parsed:
            if isinstance(p, str):
                texts.append(p)
            elif isinstance(p, dict):
                ptype = p.get("type", "")
                if ptype in ("text", "output_text"):
                    texts.append(p.get("content") or p.get("text", ""))
                else:
                    texts.append(p)  # keep non-text parts as-is
        if texts:
            content: Any = texts[0] if len(texts) == 1 else texts
            return {"role": "system", "content": content}
    return None


def _normalise_pydantic_ai_messages(value: Any) -> list[dict[str, Any]]:
    """Convert PydanticAI ``all_messages`` (kind-based) to normalised messages.

    PydanticAI serialises conversation history as a list of dicts with a
    ``kind`` field (``"request"`` or ``"response"``), each containing
    ``parts`` with their own ``part_kind`` discriminator.

    Falls back to generic message normalisation if no kind-based items are
    found (e.g. when the attribute already contains standard chat messages).
    """
    raw = _try_json(value)
    if not isinstance(raw, list):
        return _normalise_messages(value)

    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind", "")
        parts = item.get("parts") or []
        if not isinstance(parts, list):
            parts = [parts]

        if kind == "request":
            for part in parts:
                if not isinstance(part, dict):
                    continue
                part_kind = part.get("part_kind", "")
                if part_kind == "user-prompt":
                    result.append({"role": "user", "content": part.get("content", "")})
                elif part_kind == "system-prompt":
                    result.append({"role": "system", "content": part.get("content", "")})
                elif part_kind == "tool-return":
                    result.append({
                        "role": "tool",
                        "name": part.get("tool_name", ""),
                        "content": part.get("content", ""),
                        "tool_call_id": part.get("tool_call_id", ""),
                    })
                elif part_kind == "retry-prompt":
                    result.append({"role": "user", "content": part.get("content", "")})

        elif kind == "response":
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                part_kind = part.get("part_kind", "")
                if part_kind == "text":
                    text_parts.append(part.get("content", ""))
                elif part_kind == "tool-call":
                    tool_calls.append({
                        "id": part.get("tool_call_id", ""),
                        "name": part.get("tool_name", ""),
                        "arguments": part.get("args"),
                    })
            msg: dict[str, Any] = {"role": "assistant"}
            if text_parts:
                msg["content"] = " ".join(text_parts) if len(text_parts) > 1 else text_parts[0]
            if tool_calls:
                msg["tool_calls"] = tool_calls
            result.append(msg)

    # Fall back to generic normalisation if no kind-based items were processed
    # (handles the case where pydantic_ai.all_messages already contains
    # standard chat messages like [{"role": "user", "content": "hi"}]).
    if not result:
        return _normalise_messages(value)
    return result


# ---------------------------------------------------------------------------
# Span-event extraction (Google GenAI, OpenAI Agents via logfire)
# ---------------------------------------------------------------------------


def _msg_from_span_event(evt_name: str, evt_attrs: dict[str, Any]) -> dict[str, Any] | None:
    """Build a normalised message dict from a single OTEL span event."""
    # logfire / google-genai encode the body as JSON in "event_body"
    body_raw = evt_attrs.get("event_body")
    if body_raw is not None:
        body = _try_json(body_raw)
        if isinstance(body, dict):
            # gen_ai.choice: {"index":0, "message":{...}, "finish_reason":"..."}
            if "message" in body:
                raw_msg = body["message"]
                if isinstance(raw_msg, dict):
                    nm = _normalise_message(raw_msg)
                    if nm and (fr := body.get("finish_reason")):
                        nm["finish_reason"] = fr
                    return nm
            # Direct message dict in body
            role = body.get("role") or evt_name.split(".")[1]
            content = body.get("content") or body.get("text")
            if content is not None:
                msg: dict[str, Any] = {"role": role}
                if isinstance(content, list):
                    # Google GenAI parts: [{"text": "..."}, ...]
                    texts = []
                    for p in content:
                        if isinstance(p, dict):
                            if "text" in p:
                                texts.append(p["text"])
                            else:
                                texts.append(p)
                        else:
                            texts.append(str(p))
                    msg["content"] = texts[0] if len(texts) == 1 else texts
                else:
                    msg["content"] = content
                if tcs := body.get("tool_calls"):
                    msg["tool_calls"] = tcs
                if fr := body.get("finish_reason"):
                    msg["finish_reason"] = fr
                return msg
        return None

    # Standard OTel gen_ai event attributes
    role = evt_attrs.get("role") or evt_name.split(".")[1]  # e.g. "user"
    content = evt_attrs.get("content")
    if content is None and "message" in evt_attrs:
        content = evt_attrs["message"]

    if content is not None or "tool_calls" in evt_attrs:
        msg = {"role": role}
        if content is not None:
            msg["content"] = _try_json(content) if isinstance(content, str) else content
        if tcs := evt_attrs.get("tool_calls"):
            msg["tool_calls"] = _try_json(tcs) if isinstance(tcs, str) else tcs
        if tcid := evt_attrs.get("id"):
            msg["tool_call_id"] = tcid
        if name := evt_attrs.get("name"):
            msg["name"] = name
        if fr := evt_attrs.get("finish_reason"):
            msg["finish_reason"] = fr
        return msg

    return None


def _extract_inputs_from_events(span: Span) -> list[dict[str, Any]] | None:
    """Extract input conversation messages from OTEL span events.

    Returns ``None`` when no relevant events are found (so the caller can
    fall through to attribute-based extraction).
    """
    msgs: list[dict[str, Any]] = []
    for evt in span.events:
        if evt.name not in _CONV_HISTORY_EVENT_NAMES:
            continue
        m = _msg_from_span_event(evt.name, evt.attributes or {})
        if m is not None:
            msgs.append(m)
    return msgs if msgs else None


def _extract_output_from_events(span: Span) -> Any:
    """Extract the model's output from OTEL span events (gen_ai.choice, …).

    Returns ``None`` when no choice/output events are found.
    """
    choices: list[dict[str, Any]] = []
    for evt in span.events:
        if evt.name not in _CHOICE_EVENT_NAMES:
            continue
        m = _msg_from_span_event(evt.name, evt.attributes or {})
        if m is not None:
            choices.append(m)

    if not choices:
        return None
    return choices[0] if len(choices) == 1 else choices


# ---------------------------------------------------------------------------
# Span type detection
# ---------------------------------------------------------------------------


def _detect_event_type(span: Span) -> EventType:
    """Classify a span into an :class:`EventType`."""
    attrs = span.attributes

    # 1. Explicit kind annotations from various conventions
    for key in ("openinference.span.kind", "traceloop.span.kind", "weave.span.kind"):
        val = _get_attr(attrs, key)
        if val and val in _SPAN_KIND_MAP:
            return _SPAN_KIND_MAP[val]

    # 2. gen_ai.operation.name
    op = _get_attr(attrs, "gen_ai.operation.name")
    if op:
        op_l = str(op).lower()
        if op_l in ("chat", "text_completion", "completion"):
            return EventType.LLM
        if op_l in ("embeddings", "embedding"):
            return EventType.EMBEDDING

    # 3. Presence of LLM-specific attributes
    for key in _LLM_INDICATOR_ATTRS:
        if _get_attr(attrs, key) is not None:
            return EventType.LLM

    # 4. Check span events (Google GenAI, OpenAI Agents emit gen_ai.* events)
    for evt in span.events:
        if evt.name.startswith("gen_ai."):
            return EventType.LLM

    # 5. Tool indicators
    for key in ("gen_ai.tool.name", "tool.name", "function.name"):
        if _get_attr(attrs, key) is not None:
            return EventType.TOOL

    # 6. Name heuristics (last resort)
    name_l = span.name.lower()
    if any(kw in name_l for kw in ("chat", "completion", "generate", "inference", "predict")):
        return EventType.LLM
    if any(kw in name_l for kw in ("tool", "function", "execute", "call")):
        return EventType.TOOL
    if any(kw in name_l for kw in ("agent", "run", "pipeline", "workflow")):
        return EventType.AGENT
    if "embed" in name_l:
        return EventType.EMBEDDING
    if any(kw in name_l for kw in ("retrieve", "search", "query", "fetch")):
        return EventType.RETRIEVAL

    return EventType.UNKNOWN


# ---------------------------------------------------------------------------
# Input extraction
# ---------------------------------------------------------------------------


def _extract_inputs(span: Span) -> list[dict[str, Any]] | dict[str, Any]:
    """Extract inputs from a span, trying all known attribute conventions.

    Returns a list of normalised message dicts for LLM spans, or a plain
    dict of arguments for tool/generic spans.
    """
    attrs = span.attributes

    # ── 1. Span events (Google GenAI, OpenAI Agents) ──────────────────────
    from_events = _extract_inputs_from_events(span)
    if from_events is not None:
        # Prepend system instructions if provided separately as a parts-list
        sys_raw = _get_attr(attrs, "gen_ai.system_instructions")
        if sys_raw and not any(m.get("role") == "system" for m in from_events):
            sys_msg = _system_instructions_to_msg(sys_raw)
            if sys_msg:
                from_events = [sys_msg] + from_events
        return from_events

    # ── 2. PydanticAI all_messages (full conversation history) ────────────
    pai_raw = _get_attr(attrs, "pydantic_ai.all_messages")
    if pai_raw is not None:
        msgs = _normalise_pydantic_ai_messages(pai_raw)
        if msgs:
            return msgs

    # ── 3. gen_ai.input.messages (logfire v2 / new OTel semconv) ──────────
    input_msgs_raw = _get_attr(attrs, "gen_ai.input.messages")
    if input_msgs_raw is not None:
        msgs = _normalise_messages(input_msgs_raw)
        # Prepend system instructions if provided separately as a parts-list
        sys_raw = _get_attr(attrs, "gen_ai.system_instructions")
        if sys_raw and not any(m.get("role") == "system" for m in msgs):
            sys_msg = _system_instructions_to_msg(sys_raw)
            if sys_msg:
                msgs = [sys_msg] + msgs
        if msgs:
            return msgs

    # ── 4. gen_ai.prompt (OTel v1 semconv, Traceloop) ────────────────────
    prompt_raw = _get_attr(attrs, "gen_ai.prompt")
    if prompt_raw is not None:
        msgs = _normalise_messages(prompt_raw)
        if msgs:
            return msgs

    # ── 5. Tool / function arguments (tool-type spans) ────────────────────
    event_type = _detect_event_type(span)
    if event_type == EventType.TOOL:
        args_raw = _first_attr(attrs, [
            "gen_ai.tool.call.arguments",
            "tool.arguments",
            "function.arguments",
        ])
        if args_raw is not None:
            parsed = _try_json(args_raw)
            return parsed if isinstance(parsed, dict) else {"arguments": parsed}

    # ── 6. Remaining keys in priority order ───────────────────────────────
    for key in (
        "input.value",
        "mlflow.spanInputs",
        "ai.prompt",
        "gcp.vertex.agent.llm_request",
        "traceloop.entity.input",
        "input",
        "inputs",
    ):
        val = _get_attr(attrs, key)
        if val is None:
            continue
        parsed = _try_json(val)
        msgs = _normalise_messages(parsed)
        if msgs:
            return msgs
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}

    return {}


# ---------------------------------------------------------------------------
# Output extraction
# ---------------------------------------------------------------------------


def _extract_output(span: Span) -> Any:
    """Extract output from a span, trying all known attribute conventions."""
    attrs = span.attributes

    # ── 1. Span events (gen_ai.choice) ────────────────────────────────────
    from_events = _extract_output_from_events(span)
    if from_events is not None:
        return from_events

    # ── 2. gen_ai.output.messages (logfire v2 / new OTel semconv) ─────────
    output_msgs_raw = _get_attr(attrs, "gen_ai.output.messages")
    if output_msgs_raw is not None:
        msgs = _normalise_messages(output_msgs_raw)
        if msgs:
            return msgs[0] if len(msgs) == 1 else msgs

    # ── 3. Remaining keys in priority order ───────────────────────────────
    for key in (
        "final_result",
        "gen_ai.completion",
        "output.value",
        "gen_ai.content.completion",
        "mlflow.spanOutputs",
        "ai.response",
        "gcp.vertex.agent.llm_response",
        "traceloop.entity.output",
        "output",
        "outputs",
    ):
        val = _get_attr(attrs, key)
        if val is None:
            continue
        parsed = _try_json(val)
        # If it looks like a message list, normalise it
        if isinstance(parsed, list):
            msgs = _normalise_messages(parsed)
            if msgs:
                return msgs[0] if len(msgs) == 1 else msgs
        return parsed

    return None


# ---------------------------------------------------------------------------
# Usage / model / provider extraction
# ---------------------------------------------------------------------------


def _extract_usage(attrs: dict[str, Any]) -> TokenUsage | None:
    def _int(key: str) -> int | None:
        v = _get_attr(attrs, key)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    input_tokens = (
        _int("gen_ai.usage.input_tokens")
        or _int("gen_ai.usage.prompt_tokens")
        or _int("llm.token_count.prompt")
        or _int("ai.usage.promptTokens")
    )
    output_tokens = (
        _int("gen_ai.usage.output_tokens")
        or _int("gen_ai.usage.completion_tokens")
        or _int("llm.token_count.completion")
        or _int("ai.usage.completionTokens")
    )
    total_tokens = (
        _int("llm.usage.total_tokens")
        or _int("llm.token_count.total")
    )

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    if input_tokens is not None and output_tokens is not None and total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _extract_model(attrs: dict[str, Any]) -> str | None:
    for key in ("gen_ai.response.model", "gen_ai.request.model", "llm.model_name", "ai.model.id"):
        v = _get_attr(attrs, key)
        if isinstance(v, str) and v:
            return v
    return None


def _extract_provider(attrs: dict[str, Any]) -> str | None:
    for key in ("gen_ai.provider.name", "gen_ai.system", "llm.provider", "ai.model.provider"):
        v = _get_attr(attrs, key)
        if isinstance(v, str) and v:
            return v
    return None


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------


def span_to_event(span: Span, known_span_ids: set[str] | None = None) -> OtelEvent:
    """Convert one :class:`~python_spans.Span` to an :class:`OtelEvent`.

    Parameters
    ----------
    span:
        The OTEL span to convert.
    known_span_ids:
        The set of all span IDs present in the current batch.  If a span's
        ``parent_id`` is *not* in this set the event is treated as a root
        (``parent_id`` is set to ``None``).
    """
    attrs = span.attributes

    parent_id = span.parent_id
    if parent_id and known_span_ids is not None and parent_id not in known_span_ids:
        parent_id = None

    is_error = span.status.code.name == "ERROR"
    status = "error" if is_error else "success"
    error = span.status.message if is_error and span.status.message else None

    return OtelEvent(
        id=span.span_id,
        trace_id=span.trace_id,
        name=span.name,
        type=_detect_event_type(span),
        parent_id=parent_id,
        inputs=_extract_inputs(span),
        output=_extract_output(span),
        model=_extract_model(attrs),
        provider=_extract_provider(attrs),
        usage=_extract_usage(attrs),
        started_at=span.start_time.isoformat(),
        ended_at=span.end_time.isoformat(),
        status=status,
        error=error,
    )


# ---------------------------------------------------------------------------
# Trace-level builder
# ---------------------------------------------------------------------------


def spans_to_traces(spans: list[Span]) -> list[OtelTrace]:
    """Convert a batch of :class:`~python_spans.Span` objects into :class:`OtelTrace` instances.

    Spans are grouped by ``trace_id``.  Within each group they are sorted by
    start time.  The root is the span whose ``parent_id`` is absent or points
    to a span not present in the batch.

    Parameters
    ----------
    spans:
        Flat list of spans (may span multiple traces).

    Returns
    -------
    list[OtelTrace]
        One :class:`OtelTrace` per distinct ``trace_id`` found in *spans*.
    """
    by_trace: dict[str, list[Span]] = {}
    for span in spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    traces: list[OtelTrace] = []
    for trace_id, trace_spans in by_trace.items():
        known_ids: set[str] = {s.span_id for s in trace_spans}

        roots = [s for s in trace_spans if not s.parent_id or s.parent_id not in known_ids]
        root_id = roots[0].span_id if roots else None

        sorted_spans = sorted(trace_spans, key=lambda s: s.start_time_unix_nano)
        events = [span_to_event(s, known_ids) for s in sorted_spans]

        traces.append(OtelTrace(trace_id=trace_id, root_id=root_id, events=events))

    return traces
