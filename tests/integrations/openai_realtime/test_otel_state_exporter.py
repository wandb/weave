"""Tests for the OTel GenAI variant of the OpenAI Realtime integration.

Sibling of ``test_state_exporter.py`` — same delta-driven state machine, but
asserts on emitted OTel GenAI spans (and their normalization into the
``spans`` ClickHouse schema) instead of legacy Weave calls.

Two layers of validation:

1. Span shape — drive the exporter with realtime events and assert the
   emitted invoke_agent / chat / execute_tool spans carry the right semconv
   attributes, parenting, audio refs, and timing (via an in-memory exporter).
2. Schema population — round-trip the emitted spans through the *real* ingest
   path (OTLP protobuf -> ``Span.from_proto`` -> ``extract_genai_span``) and
   assert they populate ``AgentSpanCHInsertable`` columns correctly.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.integrations.openai_realtime.conversation_manager import ConversationManager
from weave.integrations.openai_realtime.otel_state_exporter import OTelStateExporter
from weave.integrations.openai_realtime.state_exporter import StateExporter

_MODEL = "gpt-4o-realtime-preview"
_SESSION_ID = "sess_1"


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    """Install an in-memory OTel exporter as the global provider.

    Mirrors the claude_agent_sdk / openai_agents OTel fixtures: overrides the
    private ``_TRACER_PROVIDER`` so prior state restores cleanly.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@dataclass
class _FakeRef:
    uri: str


@pytest.fixture
def fake_publish(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Stub ``weave.trace.api.publish`` so audio publishing needs no client.

    Returns the list of published Content objects (for assertions) and hands
    back a deterministic ``weave://`` ref per call.
    """
    from weave.trace import api

    published: list[Any] = []

    def _publish(obj: Any, *args: Any, **kwargs: Any) -> _FakeRef:
        published.append(obj)
        return _FakeRef(f"weave:///entity/proj/object/content:{len(published)}")

    monkeypatch.setattr(api, "publish", _publish)
    return published


# --- helpers ----------------------------------------------------------------


def make_session(*, modalities: list[str] | None = None) -> dict:
    return {
        "id": _SESSION_ID,
        "model": _MODEL,
        "modalities": modalities or ["audio"],
        "voice": "alloy",
        "temperature": 0.8,
        "max_response_output_tokens": 4096,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {"type": "server_vad"},
    }


def make_user_audio_item(item_id: str, transcript: str | None = None) -> dict:
    return {
        "id": item_id,
        "type": "message",
        "role": "user",
        "content": [{"type": "input_audio", "audio": "", "transcript": transcript}],
    }


def make_assistant_audio_item(item_id: str, transcript: str) -> dict:
    return {
        "id": item_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "audio", "transcript": transcript}],
    }


def make_function_call_item(item_id: str, name: str, arguments: str, call_id: str) -> dict:
    return {
        "id": item_id,
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": arguments,
        "status": "completed",
    }


def make_response(
    resp_id: str,
    output: list[dict],
    *,
    conversation_id: str | None = None,
    usage: dict | None = None,
    status: str = "completed",
) -> dict:
    return {
        "id": resp_id,
        "status": status,
        "status_details": None,
        "output": output,
        "usage": usage,
        "conversation_id": conversation_id,
    }


def drive_response(
    exp: OTelStateExporter,
    response: dict,
    *,
    input_items: list[dict] | None = None,
    response_audio: dict[str, bytes] | None = None,
) -> None:
    """Register input items, link the output to them, and run a full turn."""
    output_items = response.get("output", [])
    for item in input_items or []:
        exp.items[item["id"]] = item
    # Link the (single) output item to the most recent input item so
    # _get_input_item_list can walk the thread back to it.
    if output_items and input_items:
        exp.prev_by_item[output_items[0]["id"]] = input_items[-1]["id"]
    for item_id, audio in (response_audio or {}).items():
        exp.response_audio[item_id] = audio

    exp.handle_response_created(
        {"type": "response.created", "response": response}
    )
    exp.handle_response_done({"type": "response.done", "response": response})


def get_attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def by_op(spans: list[Any], op: str) -> list[Any]:
    return [s for s in spans if get_attrs(s).get("gen_ai.operation.name") == op]


def messages(span: Any, key: str) -> list[dict[str, Any]]:
    raw = get_attrs(span).get(key)
    return json.loads(raw) if raw else []


def part_types(msgs: list[dict[str, Any]]) -> set[str]:
    return {p.get("type") for m in msgs for p in m.get("parts", [])}


# --- exporter selection -----------------------------------------------------


def test_conversation_manager_selects_exporter_by_flag() -> None:
    """The dispatcher flag picks the destination; legacy path is untouched."""
    assert isinstance(ConversationManager(use_otel=True).state, OTelStateExporter)
    legacy = ConversationManager(use_otel=False).state
    assert isinstance(legacy, StateExporter)
    assert not isinstance(legacy, OTelStateExporter)


# --- span shape -------------------------------------------------------------


def test_basic_response_emits_invoke_agent_chat_tree(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    user = make_user_audio_item("item_u1", transcript="What's the weather?")
    out = make_assistant_audio_item("item_a1", transcript="It's sunny.")
    resp = make_response("resp_1", [out], conversation_id="conv_abc")
    drive_response(
        exp, resp, input_items=[user], response_audio={"item_a1": b"\x10\x20\x30\x40"}
    )

    time.sleep(0.12)
    exp.on_exit()
    spans = otel_spans.get_finished_spans()

    agents = by_op(spans, "invoke_agent")
    chats = by_op(spans, "chat")
    assert len(agents) == 1
    assert len(chats) == 1

    root = agents[0]
    chat = chats[0]
    assert root.name == "invoke_agent openai_realtime"
    root_attrs = get_attrs(root)
    assert root_attrs["gen_ai.agent.name"] == "openai_realtime"
    assert root_attrs["gen_ai.provider.name"] == "openai"
    # conversation.id is the realtime conversation_id, not the session id.
    assert root_attrs["gen_ai.conversation.id"] == "conv_abc"

    chat_attrs = get_attrs(chat)
    assert chat.name == f"chat {_MODEL}"
    assert chat_attrs["gen_ai.provider.name"] == "openai"
    assert chat_attrs["gen_ai.request.model"] == _MODEL
    assert chat_attrs["gen_ai.conversation.id"] == "conv_abc"
    # Audio output -> speech modality + published ref.
    assert chat_attrs["gen_ai.output.type"] == "speech"
    assert list(chat_attrs["weave.content_refs"]) == [
        "weave:///entity/proj/object/content:1"
    ]

    # Output message carries the transcript (text) + audio (uri) parts.
    out_msgs = messages(chat, "gen_ai.output.messages")
    assert part_types(out_msgs) == {"text", "uri"}
    uri_part = next(
        p for m in out_msgs for p in m["parts"] if p["type"] == "uri"
    )
    assert uri_part["modality"] == "audio"
    assert uri_part["mime_type"] == "audio/wav"
    assert uri_part["uri"] == "weave:///entity/proj/object/content:1"

    # Input transcript is captured as a user text part.
    in_msgs = messages(chat, "gen_ai.input.messages")
    assert any(
        p.get("content") == "What's the weather?"
        for m in in_msgs
        for p in m.get("parts", [])
    )

    # chat nests under the invoke_agent root, same trace.
    assert chat.parent.span_id == root.context.span_id
    assert chat.context.trace_id == root.context.trace_id


def test_input_audio_published_as_uri(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    """User speech is sliced from the input buffer and published as a uri."""
    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    user = make_user_audio_item("item_u1")
    # 20ms @ 24kHz/16-bit mono = 960 bytes.
    exp.handle_speech_started({"item_id": "item_u1", "audio_start_ms": 0})
    exp.handle_input_audio_append({"audio": base64.b64encode(b"\x01" * 960).decode()})
    exp.handle_speech_stopped({"item_id": "item_u1", "audio_end_ms": 20})

    out = make_assistant_audio_item("item_a1", transcript="ok")
    resp = make_response("resp_1", [out], conversation_id="conv_x")
    drive_response(
        exp, resp, input_items=[user], response_audio={"item_a1": b"\xaa\xbb"}
    )

    time.sleep(0.12)
    exp.on_exit()
    chat = by_op(otel_spans.get_finished_spans(), "chat")[0]

    in_msgs = messages(chat, "gen_ai.input.messages")
    uri_parts = [p for m in in_msgs for p in m.get("parts", []) if p["type"] == "uri"]
    assert len(uri_parts) == 1
    assert uri_parts[0]["modality"] == "audio"
    # Both input and output audio were published (2 refs total).
    assert len(fake_publish) == 2
    assert len(get_attrs(chat)["weave.content_refs"]) == 2


def test_function_call_emits_execute_tool_span(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    user = make_user_audio_item("item_u1", transcript="weather in Paris?")
    fc = make_function_call_item(
        "item_fc1",
        name="get_weather",
        arguments='{"location": "Paris"}',
        call_id="call_123",
    )
    resp = make_response("resp_1", [fc], conversation_id="conv_t")
    drive_response(exp, resp, input_items=[user])

    time.sleep(0.12)
    exp.on_exit()
    spans = otel_spans.get_finished_spans()

    chat = by_op(spans, "chat")[0]
    tools = by_op(spans, "execute_tool")
    assert len(tools) == 1
    tool = tools[0]
    tool_attrs = get_attrs(tool)
    assert tool.name == "execute_tool get_weather"
    assert tool_attrs["gen_ai.tool.name"] == "get_weather"
    assert tool_attrs["gen_ai.tool.call.id"] == "call_123"
    assert json.loads(tool_attrs["gen_ai.tool.call.arguments"]) == {"location": "Paris"}
    # execute_tool nests under its chat span.
    assert tool.parent.span_id == chat.context.span_id

    # The chat output records the tool call request.
    assert "tool_call" in part_types(messages(chat, "gen_ai.output.messages"))


def test_usage_mapped_onto_chat_span(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    out = make_assistant_audio_item("item_a1", transcript="hi")
    usage = {
        "input_tokens": 120,
        "output_tokens": 80,
        "input_token_details": {"audio_tokens": 100, "cached_tokens": 30},
        "output_token_details": {"audio_tokens": 70},
    }
    resp = make_response("resp_1", [out], conversation_id="conv_u", usage=usage)
    drive_response(exp, resp, response_audio={"item_a1": b"\x01\x02"})

    time.sleep(0.12)
    exp.on_exit()
    chat = by_op(otel_spans.get_finished_spans(), "chat")[0]
    attrs = get_attrs(chat)
    assert attrs["gen_ai.usage.input_tokens"] == 120
    assert attrs["gen_ai.usage.output_tokens"] == 80
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 30


def test_multiple_responses_share_session_root(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    # Each response carries a DIFFERENT realtime conversation_id, yet they all
    # belong to one session — so they must nest under a single root.
    for i in range(3):
        out = make_assistant_audio_item(f"item_a{i}", transcript=f"reply {i}")
        resp = make_response(f"resp_{i}", [out], conversation_id=f"conv_{i}")
        drive_response(exp, resp, response_audio={f"item_a{i}": b"\x00"})
        time.sleep(0.08)

    exp.on_exit()
    spans = otel_spans.get_finished_spans()

    agents = by_op(spans, "invoke_agent")
    chats = by_op(spans, "chat")
    assert len(agents) == 1
    assert len(chats) == 3
    # All chats nest under the single session root, sharing one trace — the
    # session is the grouping unit even though each response carries its own
    # realtime conversation_id (preserved on gen_ai.conversation.id).
    root = agents[0]
    assert {c.parent.span_id for c in chats} == {root.context.span_id}
    assert {c.context.trace_id for c in chats} == {root.context.trace_id}
    assert {get_attrs(c)["gen_ai.conversation.id"] for c in chats} == {
        "conv_0",
        "conv_1",
        "conv_2",
    }
    # The root takes the conversation_id of the session's first response.
    assert get_attrs(root)["gen_ai.conversation.id"] == "conv_0"


def test_failed_response_sets_error_status(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    from opentelemetry.trace import StatusCode

    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )
    resp = make_response("resp_1", [], conversation_id="conv_e", status="failed")
    resp["status_details"] = {"error": {"message": "boom"}}
    drive_response(exp, resp)

    time.sleep(0.12)
    exp.on_exit()
    chat = by_op(otel_spans.get_finished_spans(), "chat")[0]
    assert chat.status.status_code == StatusCode.ERROR


# --- schema population (real ingest path) -----------------------------------


def _readable_to_ts_spans(readable_spans: list[Any]) -> list[Any]:
    """Round-trip in-memory spans through OTLP protobuf into trace_server Spans.

    This is the exact transformation the ingest endpoint performs, so the
    resulting Spans feed ``extract_genai_span`` precisely as production does.
    """
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans

    from weave.trace_server.opentelemetry.python_spans import Resource, Span

    req = encode_spans(readable_spans)
    out: list[Any] = []
    for rs in req.resource_spans:
        resource = Resource.from_proto(rs.resource) if rs.HasField("resource") else None
        for ss in rs.scope_spans:
            for sp in ss.spans:
                out.append(Span.from_proto(sp, resource))
    return out


def test_spans_populate_clickhouse_schema_via_extraction(
    otel_spans: InMemorySpanExporter, fake_publish: list[Any]
) -> None:
    from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span

    exp = OTelStateExporter()
    exp.handle_session_updated(
        {"type": "session.updated", "session": make_session()}
    )

    # Turn 1: a spoken response to spoken input — exercises audio publishing on
    # both sides, usage, and the message columns.
    user1 = make_user_audio_item("item_u1", transcript="weather in Paris?")
    exp.handle_speech_started({"item_id": "item_u1", "audio_start_ms": 0})
    exp.handle_input_audio_append({"audio": base64.b64encode(b"\x01" * 960).decode()})
    exp.handle_speech_stopped({"item_id": "item_u1", "audio_end_ms": 20})
    out1 = make_assistant_audio_item("item_a1", transcript="It is sunny in Paris.")
    usage = {
        "input_tokens": 200,
        "output_tokens": 50,
        "input_token_details": {"cached_tokens": 40},
    }
    resp1 = make_response("resp_1", [out1], conversation_id="conv_a", usage=usage)
    drive_response(
        exp, resp1, input_items=[user1], response_audio={"item_a1": b"\xaa\xbb"}
    )
    time.sleep(0.1)

    # Turn 2: a tool call — exercises the execute_tool columns.
    user2 = make_user_audio_item("item_u2", transcript="book it")
    fc = make_function_call_item(
        "item_fc1",
        name="get_weather",
        arguments='{"location": "Paris"}',
        call_id="call_xyz",
    )
    resp2 = make_response("resp_2", [fc], conversation_id="conv_b")
    drive_response(exp, resp2, input_items=[user2])
    time.sleep(0.1)

    exp.on_exit()

    ts_spans = _readable_to_ts_spans(otel_spans.get_finished_spans())
    rows = [extract_genai_span(s, project_id="entity/proj") for s in ts_spans]
    chat_rows = [r for r in rows if r.operation_name == "chat"]
    tool_rows = [r for r in rows if r.operation_name == "execute_tool"]
    agent_rows = [r for r in rows if r.operation_name == "invoke_agent"]
    assert len(agent_rows) == 1
    assert len(chat_rows) == 2
    assert len(tool_rows) == 1

    # Each turn keeps its own realtime conversation_id in the column; the two
    # turns are one session (one invoke_agent root, asserted below).
    assert {r.conversation_id for r in chat_rows} == {"conv_a", "conv_b"}
    speech_chat = next(r for r in chat_rows if r.output_type == "speech")
    assert speech_chat.provider_name == "openai"
    assert speech_chat.request_model == _MODEL
    assert speech_chat.response_model == _MODEL
    assert speech_chat.conversation_id == "conv_a"
    assert speech_chat.input_tokens == 200
    assert speech_chat.output_tokens == 50
    assert speech_chat.cache_read_input_tokens == 40
    # Input + output speech each published a ref into the content_refs column.
    assert len(speech_chat.content_refs) == 2
    assert all(ref.startswith("weave:///") for ref in speech_chat.content_refs)
    # Messages normalize into the Tuple(role, content, finish_reason) column shape.
    assert speech_chat.input_messages[0].role == "user"
    assert speech_chat.output_messages[0].role == "assistant"
    assert "It is sunny in Paris." in speech_chat.output_messages[0].content

    tool_row = tool_rows[0]
    assert tool_row.tool_name == "get_weather"
    assert tool_row.tool_call_id == "call_xyz"
    assert json.loads(tool_row.tool_call_arguments) == {"location": "Paris"}

    agent_row = agent_rows[0]
    assert agent_row.agent_name == "openai_realtime"
    assert agent_row.provider_name == "openai"
    assert agent_row.conversation_id == "conv_a"
