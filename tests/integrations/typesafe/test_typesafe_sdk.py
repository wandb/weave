"""TypeSafe system_one spans. HTTP is mocked; nothing here needs a trace server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Generator
from typing import Any

import httpx2
import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from pydantic import BaseModel
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Noul,
    RetryPolicy,
    TypeSafeAPIError,
    TypeSafeClient,
    TypeSafeError,
)

import weave.integrations.patch as patch_module
import weave.integrations.typesafe.typesafe_sdk as typesafe_integration
from weave.conversation import LLM, Conversation, Turn
from weave.integrations.patch import implicit_patch
from weave.integrations.typesafe.typesafe_sdk import (
    get_typesafe_patcher,
    set_capture_content,
)
from weave.trace.settings import override_settings

_SECRET = "SECRET_BODY_xyz"
_EMAIL = "alice@example.com"


class OnlyModel(BaseModel):
    model: str


def _ok_body(**overrides: Any) -> dict[str, Any]:
    body = {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 11, "output_tokens": 4},
        "answers": {"billing": {"type": "noul", "noul": 0.91}},
    }
    body.update(overrides)
    return body


def _response(
    status: int = 200,
    body: dict[str, Any] | None = None,
    *,
    request_id: str | None = "req_123",
) -> httpx2.Response:
    headers = {}
    if request_id is not None:
        headers["x-typesafe-request-id"] = request_id
    return httpx2.Response(
        status, json=body if body is not None else _ok_body(), headers=headers
    )


def _questions() -> dict[str, Any]:
    return {"billing": Noul(instructions="Is this about billing?")}


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@pytest.fixture(autouse=True)
def patch_typesafe() -> Generator[None]:
    typesafe_integration._typesafe_patcher = None
    set_capture_content(None)
    patcher = get_typesafe_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()
    typesafe_integration._typesafe_patcher = None
    set_capture_content(None)
    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")


@pytest.fixture(autouse=True)
def disable_capture_info() -> Generator[None]:
    with override_settings(capture_client_info=False, capture_system_info=False):
        yield


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> TypeSafeClient:
    return TypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )


def _async_client(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> AsyncTypeSafeClient:
    return AsyncTypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )


def _attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def _by_op(spans: list[Any], op: str) -> list[Any]:
    return [span for span in spans if _attrs(span).get("gen_ai.operation.name") == op]


def _messages(span: Any, key: str) -> list[dict[str, Any]]:
    raw = _attrs(span).get(key)
    return json.loads(raw) if raw else []


def _text(span: Any) -> str:
    payload = {
        "attributes": _attrs(span),
        "events": [
            {"name": event.name, "attributes": dict(event.attributes or {})}
            for event in span.events
        ],
        "status": span.status.description,
    }
    return json.dumps(payload)


def _chat(exporter: InMemorySpanExporter) -> Any:
    chats = _by_op(exporter.get_finished_spans(), "chat")
    assert len(chats) == 1
    return chats[0]


def test_system_one_records_one_chat_span_under_a_synthetic_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    result = client.system_one("I was charged twice.", _questions())

    assert result.model == "jev-1.13.0"
    spans = otel_spans.get_finished_spans()
    turns = [span for span in spans if span.name == "invoke_agent typesafe SDK"]
    assert len(turns) == 1
    chat = _chat(otel_spans)
    assert chat.name == "chat jev-latest"
    assert chat.parent is not None
    assert chat.parent.span_id == turns[0].context.span_id
    assert turns[0].parent is None

    attrs = _attrs(chat)
    assert attrs["gen_ai.provider.name"] == "typesafe"
    assert attrs["gen_ai.request.model"] == "jev-latest"
    assert attrs["gen_ai.response.model"] == "jev-1.13.0"
    assert attrs["gen_ai.response.id"] == "req_123"
    assert attrs["gen_ai.output.type"] == "json"
    assert attrs["gen_ai.usage.input_tokens"] == 11
    assert attrs["gen_ai.usage.output_tokens"] == 4
    assert "gen_ai.usage.total_tokens" not in attrs
    assert attrs["integration.name"] == "typesafe"
    assert attrs["integration.meta.package_name"] == "typesafe-sdk"
    assert attrs["weave.integration.operation"] == "typesafe.system_one"
    assert "gen_ai.provider.name" not in _attrs(turns[0])

    assert _messages(chat, "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "I was charged twice."}],
        }
    ]
    output = _messages(chat, "gen_ai.output.messages")
    assert json.loads(output[0]["parts"][0]["content"]) == {
        "billing": {"noul": 0.91, "type": "noul"}
    }
    questions = json.loads(attrs["typesafe.questions"])
    assert questions == [
        {
            "id": "billing",
            "instructions": "Is this about billing?",
            "type": "noul",
        }
    ]


def test_explicit_model_and_extra_body_describe_the_effective_request(
    otel_spans: InMemorySpanExporter,
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return _response()

    client = _client(handler)
    client.system_one(
        {"ticket": 7},
        _questions(),
        model="jev-latest",
        extra_body={"model": "jev-preview", "state": ["replaced"]},
    )

    assert seen["body"]["model"] == "jev-preview"
    assert seen["body"]["state"] == ["replaced"]
    chat = _chat(otel_spans)
    assert _attrs(chat)["gen_ai.request.model"] == "jev-preview"
    assert chat.name == "chat jev-preview"
    content = _messages(chat, "gen_ai.input.messages")[0]["parts"][0]["content"]
    assert json.loads(content) == ["replaced"]


def test_object_state_is_a_text_part_not_a_bare_json_array(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    client.system_one(["a", "b"], _questions())
    message = _messages(_chat(otel_spans), "gen_ai.input.messages")[0]
    assert message["parts"][0] == {"type": "text", "content": '["a", "b"]'}
    assert "content" not in message


def test_content_off_omits_state_questions_and_answers(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
    client = _client(lambda request: _response())
    client.system_one(f"mail {_EMAIL}", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "gen_ai.output.messages" not in attrs
    assert "typesafe.questions" not in attrs
    assert attrs["gen_ai.request.model"] == "jev-latest"
    assert attrs["gen_ai.usage.input_tokens"] == 11


def test_patch_capture_content_false_overrides_the_environment(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", raising=False
    )
    set_capture_content(False)
    client = _client(lambda request: _response())
    client.system_one("hello", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "typesafe.questions" not in attrs


def test_conversation_include_content_false_wins(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    with Conversation(include_content=False), Turn(agent_name="app"):
        client.system_one("hello", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "gen_ai.output.messages" not in attrs
    assert "typesafe.questions" not in attrs


def test_user_turn_is_the_parent_even_when_another_llm_is_active(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    with Turn(agent_name="app") as turn:
        with turn.start_llm(model="other", provider_name="openai"):
            client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    turn_span = next(span for span in spans if span.name == "invoke_agent app")
    typesafe_chat = next(
        span for span in spans if _attrs(span).get("gen_ai.provider.name") == "typesafe"
    )
    other_chat = next(span for span in spans if span.name == "chat other")
    assert typesafe_chat.parent is not None
    assert typesafe_chat.parent.span_id == turn_span.context.span_id
    assert typesafe_chat.parent.span_id != other_chat.context.span_id
    assert not any(span.name == "invoke_agent typesafe SDK" for span in spans)


def test_ambient_recording_span_is_the_parent_without_a_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    tracer = otel_trace.get_tracer("test")
    with tracer.start_as_current_span("outer"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    outer = next(span for span in spans if span.name == "outer")
    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == outer.context.span_id
    assert not any(span.name == "invoke_agent typesafe SDK" for span in spans)


def test_standalone_llm_is_an_ambient_parent(otel_spans: InMemorySpanExporter) -> None:
    client = _client(lambda request: _response())
    with LLM(model="other", provider_name="openai"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    other = next(span for span in spans if span.name == "chat other")
    chat = next(
        span for span in _by_op(spans, "chat") if span.name == "chat jev-latest"
    )
    assert chat.parent is not None
    assert chat.parent.span_id == other.context.span_id


def test_remote_sampled_parent_is_accepted(otel_spans: InMemorySpanExporter) -> None:
    remote = SpanContext(
        trace_id=int("1" * 32, 16),
        span_id=int("2" * 16, 16),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    token = otel_context.attach(
        otel_trace.set_span_in_context(NonRecordingSpan(remote))
    )
    try:
        client = _client(lambda request: _response())
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)

    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == remote.span_id
    assert not any(
        span.name == "invoke_agent typesafe SDK"
        for span in otel_spans.get_finished_spans()
    )


def test_unsampled_and_ended_local_parents_get_a_root_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    unsampled = SpanContext(
        trace_id=int("3" * 32, 16),
        span_id=int("4" * 16, 16),
        is_remote=True,
        trace_flags=TraceFlags(0),
    )
    token = otel_context.attach(
        otel_trace.set_span_in_context(NonRecordingSpan(unsampled))
    )
    try:
        client = _client(lambda request: _response())
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)

    spans = otel_spans.get_finished_spans()
    turn = next(span for span in spans if span.name == "invoke_agent typesafe SDK")
    assert turn.parent is None
    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == turn.context.span_id

    otel_spans.clear()
    tracer = otel_trace.get_tracer("test")
    with tracer.start_as_current_span("done") as done:
        ended = done
    token = otel_context.attach(otel_trace.set_span_in_context(ended))
    try:
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)
    spans = otel_spans.get_finished_spans()
    turn = next(span for span in spans if span.name == "invoke_agent typesafe SDK")
    chat = next(span for span in spans if span.name == "chat jev-latest")
    assert chat.parent is not None
    assert chat.parent.span_id == turn.context.span_id
    assert chat.parent.span_id != ended.context.span_id


def test_error_span_keeps_status_and_drops_the_body(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(
        lambda request: _response(400, {"error": _SECRET}, request_id="req_err")
    )
    with pytest.raises(TypeSafeAPIError) as caught:
        client.system_one("hello", _questions())
    assert caught.value.status == 400
    assert _SECRET in str(caught.value)

    spans = otel_spans.get_finished_spans()
    for span in spans:
        assert _SECRET not in _text(span)
        assert span.status.status_code.name == "ERROR"
        assert not span.status.description
        assert span.events == ()
    chat = _chat(otel_spans)
    attrs = _attrs(chat)
    assert attrs["http.response.status_code"] == 400
    assert attrs["gen_ai.response.id"] == "req_err"
    assert "TypeSafe" in attrs["error.type"]
    assert "gen_ai.output.messages" not in attrs


def test_user_turn_exit_records_the_original_error_and_the_llm_span_does_not(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response(400, {"error": _SECRET}))
    with pytest.raises(TypeSafeAPIError), Turn(agent_name="app"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    chat = next(
        span for span in spans if _attrs(span).get("gen_ai.provider.name") == "typesafe"
    )
    turn = next(span for span in spans if span.name == "invoke_agent app")
    assert _SECRET not in _text(chat)
    assert _SECRET in _text(turn)


def test_missing_request_id_and_custom_model_record_only_available_fields(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response(request_id=None))
    client.system_one("hello", _questions())
    assert "gen_ai.response.id" not in _attrs(_chat(otel_spans))

    otel_spans.clear()

    def handler(request: httpx2.Request) -> httpx2.Response:
        return _response(body={"model": "jev-preview"}, request_id=None)

    client = _client(handler)
    result = client.system_one("hello", _questions(), response_model=OnlyModel)
    assert result.model == "jev-preview"
    attrs = _attrs(_chat(otel_spans))
    assert attrs["gen_ai.response.model"] == "jev-preview"
    assert "gen_ai.usage.input_tokens" not in attrs
    assert "gen_ai.usage.output_tokens" not in attrs
    assert "gen_ai.response.id" not in attrs
    assert "gen_ai.output.messages" not in attrs


def test_pii_redaction_applies_to_messages_and_questions(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def redact(value: str) -> str:
        return value.replace(_EMAIL, "<EMAIL>")

    def redact_tree(value: Any) -> Any:
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, dict):
            return {key: redact_tree(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact_tree(item) for item in value]
        return value

    monkeypatch.setattr(
        "weave.conversation.conversation.should_redact_pii", lambda: True
    )
    # Message redaction goes through redact_pii, which calls Presidio itself.
    # Questions are one string and go through redact_pii_string.
    monkeypatch.setattr("weave.utils.pii_redaction.redact_pii", redact_tree)
    monkeypatch.setattr(typesafe_integration, "should_redact_pii", lambda: True)
    monkeypatch.setattr(typesafe_integration, "redact_pii_string", redact)

    client = _client(lambda request: _response())
    client.system_one(
        f"contact {_EMAIL}",
        {"billing": Noul(instructions=f"Email {_EMAIL}?")},
    )
    chat = _chat(otel_spans)
    attrs = _attrs(chat)
    assert _EMAIL not in _text(chat)
    assert "<EMAIL>" in attrs["gen_ai.input.messages"]
    assert "<EMAIL>" in attrs["typesafe.questions"]


def test_models_list_is_not_instrumented(otel_spans: InMemorySpanExporter) -> None:
    client = _client(lambda request: _response())
    with pytest.raises(TypeSafeError):
        client.models.list()
    assert _by_op(otel_spans.get_finished_spans(), "chat") == []


def test_retries_stay_inside_one_span(otel_spans: InMemorySpanExporter) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _response(500, {"error": _SECRET})
        return _response()

    client = TypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=1),
    )
    client.system_one("hello", _questions())
    assert calls["n"] == 2
    assert len(_by_op(otel_spans.get_finished_spans(), "chat")) == 1
    assert _SECRET not in _text(_chat(otel_spans))


def test_second_patch_does_not_double_span(otel_spans: InMemorySpanExporter) -> None:
    get_typesafe_patcher().attempt_patch()
    client = _client(lambda request: _response())
    client.system_one("hello", _questions())
    assert len(_by_op(otel_spans.get_finished_spans(), "chat")) == 1


def test_import_mapping_patches_an_already_imported_sdk() -> None:
    assert (
        patch_module.INTEGRATION_MODULE_MAPPING["typesafe_sdk"]
        is patch_module.patch_typesafe
    )
    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")
    patch_module._patch_if_needed("typesafe_sdk")
    assert "typesafe_sdk" in patch_module._PATCHED_INTEGRATIONS

    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")
    implicit_patch()
    assert "typesafe_sdk" in patch_module._PATCHED_INTEGRATIONS


@pytest.mark.asyncio
async def test_async_parallel_calls_do_not_share_a_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _async_client(lambda request: _response())

    async def one(state: str) -> None:
        await client.system_one(state, _questions())

    await asyncio.gather(one("left"), one("right"))
    spans = otel_spans.get_finished_spans()
    chats = _by_op(spans, "chat")
    turns = [span for span in spans if span.name == "invoke_agent typesafe SDK"]
    assert len(chats) == 2
    assert len(turns) == 2
    parents = {chat.parent.span_id for chat in chats if chat.parent is not None}
    assert parents == {turn.context.span_id for turn in turns}
