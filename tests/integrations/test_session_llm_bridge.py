"""Tests for the autopatch → Session SDK LLM-span bridge.

These tests use mock callables in place of real OpenAI / Anthropic SDK
methods so they run without network or VCR cassettes. The integration
modules import the same helpers (``session_aware_sync`` /
``session_aware_async``) on top of their existing accumulator wrappers,
so verifying the helpers in isolation covers the load-bearing path
without coupling tests to OpenAI/Anthropic response-pydantic shape.

Span verification uses an in-memory OTel span exporter; assertions are
at the OTel attribute level — the same shape consumers will see on the
wire.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.integrations._session_llm_bridge import (
    session_aware_async,
    session_aware_sync,
)
from weave.session import (
    LLM,
    Message,
    Usage,
    get_current_llm,
    get_current_session,
    get_current_turn,
    start_session,
)


@pytest.fixture(autouse=True)
def _reset_contextvars():
    yield
    if (llm := get_current_llm()) is not None:
        llm.end()
    if (turn := get_current_turn()) is not None:
        turn.end()
    if (session := get_current_session()) is not None:
        session.end()


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


def _populate_input(llm: LLM, kwargs: dict) -> None:
    llm.input_messages = [Message(role="user", content=kwargs.get("prompt", ""))]


def _populate_output(llm: LLM, response: Any) -> None:
    llm.record(
        output_messages=[Message.assistant(getattr(response, "text", ""))],
        usage=Usage(input_tokens=10, output_tokens=20),
        response_id=getattr(response, "id", ""),
        finish_reasons=["stop"],
    )


def _model_from_kwargs(kwargs: dict) -> str:
    return kwargs.get("model", "")


@dataclass
class _Resp:
    text: str = "hi"
    id: str = "r-1"


class TestSessionAwareSyncNoTurn:
    """When no Turn is active, the bridge must be a transparent passthrough."""

    def test_passthrough_no_turn(self) -> None:
        marker = object()
        called_with: dict[str, Any] = {}

        def fn(**kwargs: Any) -> object:
            called_with.update(kwargs)
            return marker

        wrapped = session_aware_sync(
            fn,
            provider_name="openai",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
        )
        result = wrapped(model="gpt-x", prompt="hi")
        assert result is marker
        assert called_with == {"model": "gpt-x", "prompt": "hi"}


class TestSessionAwareSyncNonStreaming:
    """With an active Turn, non-streaming responses produce a closed LLM span."""

    def test_llm_span_lifecycle(self, otel_spans: InMemorySpanExporter) -> None:
        resp = _Resp(text="hello", id="r-42")

        def fn(**kwargs: Any) -> _Resp:
            return resp

        wrapped = session_aware_sync(
            fn,
            provider_name="openai",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
        )
        with (
            start_session(agent_name="bot", session_id="s1") as session,
            session.start_turn(),
        ):
            result = wrapped(model="gpt-x", prompt="hi")
        assert result is resp

        chat_spans = [
            sp for sp in otel_spans.get_finished_spans() if sp.name == "chat gpt-x"
        ]
        assert len(chat_spans) == 1
        attrs = dict(chat_spans[0].attributes or {})
        assert attrs.get("gen_ai.provider.name") == "openai"
        assert attrs.get("gen_ai.response.id") == "r-42"
        assert attrs.get("gen_ai.usage.input_tokens") == 10
        assert attrs.get("gen_ai.usage.output_tokens") == 20

    def test_exception_records_error_and_closes_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        class Boom(RuntimeError):
            pass

        def fn(**kwargs: Any) -> _Resp:
            raise Boom("nope")

        wrapped = session_aware_sync(
            fn,
            provider_name="openai",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
        )
        with (
            pytest.raises(Boom),
            start_session(agent_name="bot", session_id="s1") as s,
            s.start_turn(),
        ):
            wrapped(model="gpt-x", prompt="hi")

        chat_spans = [
            sp for sp in otel_spans.get_finished_spans() if sp.name == "chat gpt-x"
        ]
        assert len(chat_spans) == 1
        assert chat_spans[0].status.status_code.name == "ERROR"


class TestSessionAwareSyncStreaming:
    """Streaming responses keep the LLM span open until iterator exhaustion."""

    def test_stream_closes_span_at_end(self, otel_spans: InMemorySpanExporter) -> None:
        chunks = [_Resp(text=f"chunk-{i}", id=f"r-{i}") for i in range(3)]

        def fn(**kwargs: Any) -> Iterator[_Resp]:
            yield from chunks

        def acc(state: Any, value: _Resp) -> _Resp:
            # accumulate by keeping the last value seen
            return value

        wrapped = session_aware_sync(
            fn,
            provider_name="openai",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
            is_streaming=lambda kwargs: bool(kwargs.get("stream")),
            accumulator=acc,
        )
        seen: list[_Resp] = []
        with start_session(agent_name="bot", session_id="s1") as s, s.start_turn():
            for chunk in wrapped(model="gpt-x", prompt="hi", stream=True):
                seen.append(chunk)
        assert [c.text for c in seen] == ["chunk-0", "chunk-1", "chunk-2"]
        chat_spans = [
            sp for sp in otel_spans.get_finished_spans() if sp.name == "chat gpt-x"
        ]
        assert len(chat_spans) == 1
        attrs = dict(chat_spans[0].attributes or {})
        # ``on_output`` ran with the last accumulated chunk.
        assert attrs.get("gen_ai.response.id") == "r-2"


class TestSessionAwareAsync:
    """Async variant: same lifecycle invariants, awaited rather than called."""

    @pytest.mark.asyncio
    async def test_async_non_streaming(self, otel_spans: InMemorySpanExporter) -> None:
        resp = _Resp(text="hello", id="r-7")

        async def fn(**kwargs: Any) -> _Resp:
            return resp

        wrapped = session_aware_async(
            fn,
            provider_name="anthropic",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
        )
        with start_session(agent_name="bot", session_id="s1") as s, s.start_turn():
            result = await wrapped(model="claude-x", prompt="hi")
        assert result is resp
        chat_spans = [
            sp for sp in otel_spans.get_finished_spans() if sp.name == "chat claude-x"
        ]
        assert len(chat_spans) == 1
        attrs = dict(chat_spans[0].attributes or {})
        assert attrs.get("gen_ai.provider.name") == "anthropic"
        assert attrs.get("gen_ai.response.id") == "r-7"

    @pytest.mark.asyncio
    async def test_async_streaming_closes_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        chunks = [_Resp(text=f"c{i}", id=f"r-{i}") for i in range(2)]

        async def fn(**kwargs: Any) -> AsyncIterator[_Resp]:
            async def _gen() -> AsyncIterator[_Resp]:
                for c in chunks:
                    yield c

            return _gen()

        def acc(state: Any, value: _Resp) -> _Resp:
            return value

        wrapped = session_aware_async(
            fn,
            provider_name="anthropic",
            model_from_kwargs=_model_from_kwargs,
            on_input=_populate_input,
            on_output=_populate_output,
            is_streaming=lambda kwargs: bool(kwargs.get("stream")),
            accumulator=acc,
        )
        seen: list[_Resp] = []
        with start_session(agent_name="bot", session_id="s1") as s, s.start_turn():
            stream = await wrapped(model="claude-x", prompt="hi", stream=True)
            async for chunk in stream:
                seen.append(chunk)
        assert [c.text for c in seen] == ["c0", "c1"]
        chat_spans = [
            sp for sp in otel_spans.get_finished_spans() if sp.name == "chat claude-x"
        ]
        assert len(chat_spans) == 1
        attrs = dict(chat_spans[0].attributes or {})
        assert attrs.get("gen_ai.response.id") == "r-1"
