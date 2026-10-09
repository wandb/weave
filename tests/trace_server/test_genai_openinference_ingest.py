"""OpenInference LangGraph spans through the agents OTel ingest and read path.

Exports one LangGraph `create_agent` turn, carrying the keys
openinference-instrumentation-langchain emits, through the real
``genai_otel_export`` on ClickHouse, then reads it back the way the Agents view
does: the trace chat, the agents list, and the conversation.
"""

from __future__ import annotations

import json
from typing import Any

from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from tests.trace_server.helpers import make_project_id
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import (
    AgentChatMessage,
    AgentConversationChatReq,
    AgentsQueryReq,
    AgentTraceChatReq,
    GenAIOTelExportReq,
)

_NOW_NS = 1_767_225_600_000_000_000
_MS_NS = 1_000_000
_TRACE_ID = (91).to_bytes(16, "big")
_SESSION_ID = "session-paris"
_MODEL = "gpt-4o-mini-2024-07-18"
_SYSTEM_PROMPT = "You are a weather assistant."
_QUESTION = "Weather in Paris?"
_ANSWER = "It is sunny and 21C in Paris."
_TOOL_RESULT = "Sunny, 21C in Paris"

_LLM_ATTRS: dict[str, Any] = {
    "openinference.span.kind": "LLM",
    "llm.provider": "openai",
    "llm.model_name": _MODEL,
    "llm.input_messages.0.message.role": "system",
    "llm.input_messages.0.message.content": _SYSTEM_PROMPT,
    "llm.input_messages.1.message.role": "user",
    "llm.input_messages.1.message.content": _QUESTION,
}
_TOOL_CALL_ATTRS: dict[str, Any] = {
    "message.role": "assistant",
    "message.tool_calls.0.tool_call.id": "call_1",
    "message.tool_calls.0.tool_call.function.name": "get_weather",
    "message.tool_calls.0.tool_call.function.arguments": '{"city": "Paris"}',
}

# (span_id, parent_id, name, start_ms, end_ms, attributes), as LangGraph nests them.
_LANGGRAPH_TURN: list[tuple[int, int | None, str, int, int, dict[str, Any]]] = [
    (1, None, "LangGraph", 0, 4000, {"openinference.span.kind": "CHAIN"}),
    (2, 1, "model", 100, 1000, {"openinference.span.kind": "CHAIN"}),
    (
        3,
        2,
        "ChatOpenAI",
        200,
        900,
        {
            **_LLM_ATTRS,
            "llm.token_count.prompt": 81,
            "llm.token_count.completion": 17,
            **{f"llm.output_messages.0.{k}": v for k, v in _TOOL_CALL_ATTRS.items()},
        },
    ),
    (4, 1, "tools", 1100, 1900, {"openinference.span.kind": "CHAIN"}),
    (
        5,
        4,
        "get_weather",
        1200,
        1800,
        {
            "openinference.span.kind": "TOOL",
            "tool.name": "get_weather",
            "input.value": "Paris",
            "output.value": json.dumps(
                {
                    "type": "tool",
                    "data": {
                        "content": _TOOL_RESULT,
                        "type": "tool",
                        "name": "get_weather",
                        "tool_call_id": "call_1",
                        "status": "success",
                    },
                }
            ),
        },
    ),
    (6, 1, "model", 2000, 3900, {"openinference.span.kind": "CHAIN"}),
    (
        7,
        6,
        "ChatOpenAI",
        2100,
        3800,
        {
            **_LLM_ATTRS,
            "llm.token_count.prompt": 118,
            "llm.token_count.completion": 11,
            **{f"llm.input_messages.2.{k}": v for k, v in _TOOL_CALL_ATTRS.items()},
            "llm.input_messages.3.message.role": "tool",
            "llm.input_messages.3.message.tool_call_id": "call_1",
            "llm.input_messages.3.message.content": _TOOL_RESULT,
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.content": _ANSWER,
        },
    ),
]


def _proto_span(
    span_id: int,
    parent_id: int | None,
    name: str,
    start_ms: int,
    end_ms: int,
    attrs: dict[str, Any],
) -> PbSpan:
    span = PbSpan()
    span.name = name
    span.trace_id = _TRACE_ID
    span.span_id = span_id.to_bytes(8, "big")
    if parent_id is not None:
        span.parent_span_id = parent_id.to_bytes(8, "big")
    span.start_time_unix_nano = _NOW_NS + start_ms * _MS_NS
    span.end_time_unix_nano = _NOW_NS + end_ms * _MS_NS
    span.status.code = 1  # OK
    for key, value in {**attrs, "session.id": _SESSION_ID}.items():
        kv = KeyValue()
        kv.key = key
        if isinstance(value, int):
            kv.value.int_value = value
        else:
            kv.value.string_value = value
        span.attributes.append(kv)
    return span


def _export_req(project_id: str) -> GenAIOTelExportReq:
    scope = InstrumentationScope()
    scope.name = "openinference.instrumentation.langchain"
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    for span in _LANGGRAPH_TURN:
        scope_spans.spans.append(_proto_span(*span))
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(PbResource())
    resource_spans.scope_spans.append(scope_spans)
    return GenAIOTelExportReq(
        processed_spans=[
            tsi.ProcessedResourceSpans(
                entity="test-entity",
                project="test-project",
                run_id=None,
                resource_spans=resource_spans,
            )
        ],
        project_id=project_id,
        wb_user_id="test-user",
    )


def _chat_line(message: AgentChatMessage) -> tuple[Any, ...]:
    if message.user_message is not None:
        return (message.type, message.agent_name, message.user_message.text)
    if message.agent_start is not None:
        return (
            message.type,
            message.agent_name,
            message.agent_start.system_instructions,
        )
    if message.tool_call is not None:
        return (
            message.type,
            message.agent_name,
            message.tool_call.tool_name,
            message.tool_call.tool_arguments,
            message.tool_call.tool_result,
        )
    if message.assistant_message is not None:
        return (
            message.type,
            message.agent_name,
            message.assistant_message.text,
            message.assistant_message.model,
        )
    raise AssertionError(f"unexpected chat message type: {message.type}")


def test_openinference_langgraph_turn_renders_in_agents_view(ch_server) -> None:
    project_id = make_project_id("openinference_langgraph")

    res = ch_server.genai_otel_export(_export_req(project_id))
    assert (res.accepted_spans, res.rejected_spans, res.error_message) == (7, 0, "")

    chat = ch_server.agent_traces_chat(
        AgentTraceChatReq(project_id=project_id, trace_id=_TRACE_ID.hex())
    )
    assert [_chat_line(m) for m in chat.messages] == [
        ("user_message", "User", _QUESTION),
        ("agent_start", "LangGraph", _SYSTEM_PROMPT),
        ("tool_call", "LangGraph", "get_weather", "Paris", _TOOL_RESULT),
        ("assistant_message", "LangGraph", _ANSWER, _MODEL),
    ]
    assert (
        chat.agent_name,
        chat.total_input_tokens,
        chat.total_output_tokens,
    ) == ("LangGraph", 199, 28)

    agents = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert [(a.agent_name, a.invocation_count) for a in agents.agents] == [
        ("LangGraph", 1)
    ]

    conversation = ch_server.agent_conversation_chat(
        AgentConversationChatReq(project_id=project_id, conversation_id=_SESSION_ID)
    )
    assert [turn.trace_id for turn in conversation.turns] == [_TRACE_ID.hex()]
