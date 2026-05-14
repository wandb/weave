"""Tests for the Google ADK ↔ Weave OTel integration.

Two layers:

- ``test_unit_*`` cover the attribute extractors in
  ``weave.integrations.google_adk.google_adk_sdk`` against lightweight
  dataclass mocks. Fast, no ADK runner.
- ``test_e2e_*`` drive a real ADK ``InMemoryRunner`` with a stub
  ``BaseLlm`` so ADK itself opens every span. We tee an
  ``InMemorySpanExporter`` onto the global ``TracerProvider`` and
  assert the patched attributes land where they should.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass, field
from typing import Any

import pytest
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.genai import types
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from weave.integrations.google_adk import google_adk_sdk as adk_sdk
from weave.integrations.google_adk.google_adk_sdk import (
    _set_llm_request_attributes,
    _set_llm_response_attributes,
    get_google_adk_patcher,
)

# --------------------------------------------------------------------------
# Mock fixtures for the unit tests. These shapes mirror the duck-typed
# surface our extractors inspect; ``_AttrSpan`` records every
# ``set_attribute`` call so we can assert on the literal semconv keys.
# --------------------------------------------------------------------------


@dataclass
class _MockPart:
    text: str | None = None
    function_call: Any = None
    function_response: Any = None
    inline_data: Any = None
    file_data: Any = None


@dataclass
class _MockContent:
    role: str
    parts: list[_MockPart]


@dataclass
class _MockGenerateContentConfig:
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    stop_sequences: list[str] | None = None
    candidate_count: int | None = None
    system_instruction: Any = None
    tools: list[Any] | None = None


@dataclass
class _MockLlmRequest:
    model: str
    contents: list[_MockContent]
    config: _MockGenerateContentConfig


@dataclass
class _MockUsageMetadata:
    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    thoughts_token_count: int | None = None
    cached_content_token_count: int | None = None
    cache_creation_token_count: int | None = None


@dataclass
class _MockLlmResponse:
    content: _MockContent | None = None
    finish_reason: Any = None
    usage_metadata: _MockUsageMetadata | None = None
    interaction_id: str | None = None
    model_version: str | None = None


@dataclass
class _AttrSpan:
    """Stand-in for a real OTel ``Span`` — only records ``set_attribute``."""

    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


# --------------------------------------------------------------------------
# Unit tests — extractors operate on duck-typed objects.
# --------------------------------------------------------------------------


def test_unit_set_llm_request_attributes_full_payload() -> None:
    """Every request-side attribute the patch promises lands on the span."""
    span = _AttrSpan()
    llm_request = _MockLlmRequest(
        model="gemini-2.0-flash",
        contents=[
            _MockContent(role="user", parts=[_MockPart(text="hi")]),
            _MockContent(role="model", parts=[_MockPart(text="hello back")]),
        ],
        config=_MockGenerateContentConfig(
            temperature=0.4,
            top_p=0.9,
            max_output_tokens=512,
            frequency_penalty=0.1,
            presence_penalty=0.2,
            seed=42,
            stop_sequences=["END"],
            candidate_count=1,
            system_instruction="you are helpful",
        ),
    )

    _set_llm_request_attributes(span, llm_request)

    a = span.attributes
    assert a["gen_ai.request.temperature"] == 0.4
    assert a["gen_ai.request.top_p"] == 0.9
    assert a["gen_ai.request.max_tokens"] == 512
    assert a["gen_ai.request.frequency_penalty"] == 0.1
    assert a["gen_ai.request.presence_penalty"] == 0.2
    assert a["gen_ai.request.seed"] == 42
    assert a["gen_ai.request.stop_sequences"] == ["END"]
    assert a["gen_ai.request.choice.count"] == 1

    instructions = json.loads(a["gen_ai.system_instructions"])
    assert instructions == [{"type": "text", "content": "you are helpful"}]

    input_messages = json.loads(a["gen_ai.input.messages"])
    assert input_messages[0]["role"] == "user"
    assert input_messages[1]["role"] == "assistant"  # ``model`` → ``assistant``


def test_unit_set_llm_response_attributes_full_payload() -> None:
    """Every response-side attribute the patch promises lands on the span."""
    span = _AttrSpan()
    llm_response = _MockLlmResponse(
        content=_MockContent(role="model", parts=[_MockPart(text="cool answer")]),
        finish_reason=types.FinishReason.STOP,
        usage_metadata=_MockUsageMetadata(
            prompt_token_count=120,
            candidates_token_count=42,
            thoughts_token_count=8,
            cached_content_token_count=15,
            cache_creation_token_count=5,
        ),
        interaction_id="resp-9988",
        model_version="gemini-2.0-flash-2025-01",
    )

    _set_llm_response_attributes(span, llm_response)

    a = span.attributes
    assert a["gen_ai.response.id"] == "resp-9988"
    assert a["gen_ai.response.model"] == "gemini-2.0-flash-2025-01"
    assert a["gen_ai.output.type"] == "text"
    assert a["gen_ai.usage.reasoning_tokens"] == 8
    assert a["gen_ai.usage.cache_read.input_tokens"] == 15
    assert a["gen_ai.usage.cache_creation.input_tokens"] == 5

    output_messages = json.loads(a["gen_ai.output.messages"])
    assert output_messages[0]["role"] == "assistant"
    assert output_messages[0]["parts"][0]["content"] == "cool answer"


def test_unit_set_llm_response_attributes_skips_empty_fields() -> None:
    """Empty optional fields don't leak as attributes on the span."""
    span = _AttrSpan()
    _set_llm_response_attributes(
        span, _MockLlmResponse(content=None, model_version="m"),
    )
    assert "gen_ai.response.id" not in span.attributes
    assert "gen_ai.output.messages" not in span.attributes
    assert span.attributes["gen_ai.response.model"] == "m"


# --------------------------------------------------------------------------
# E2E test — drive ADK's runner, verify every expected attribute lands on
# the spans ADK actually emits.
# --------------------------------------------------------------------------


def _get_weather(city: str) -> dict[str, Any]:
    """Look up the weather for a city."""
    return {"city": city, "temperature": 18, "unit": "C", "conditions": "cloudy"}


class _StubLlm(BaseLlm):
    """Two-turn scripted LLM: function call → final text answer."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["stub-llm"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        has_tool_response = any(
            part.function_response is not None
            for content in llm_request.contents
            for part in (content.parts or [])
        )

        if not has_tool_response:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="call-1",
                                name="_get_weather",
                                args={"city": "Paris"},
                            )
                        )
                    ],
                ),
                finish_reason=types.FinishReason.STOP,
                model_version="stub-v1",
                interaction_id="stub-resp-1",
            )
            return

        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="Paris is 18C and cloudy.")],
            ),
            finish_reason=types.FinishReason.STOP,
            model_version="stub-v1",
            interaction_id="stub-resp-2",
        )


@pytest.fixture
def adk_provider_and_exporter() -> (
    Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]
):
    """Install a fresh in-memory TracerProvider for the duration of one test.

    Restores the prior provider on teardown so this test can run alongside
    others in the same process without leaking patched state.
    """
    prev_provider = otel_trace.get_tracer_provider()
    provider = TracerProvider(resource=Resource.create({"service.name": "adk-test"}))
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)

    # Force re-evaluation of cached patcher state between tests.
    adk_sdk._google_adk_patcher = None
    patcher = get_google_adk_patcher()
    assert patcher.attempt_patch()
    try:
        yield provider, exporter
    finally:
        patcher.undo_patch()
        adk_sdk._google_adk_patcher = None
        otel_trace.set_tracer_provider(prev_provider)


def test_e2e_adk_runner_emits_all_otlv2_attributes(
    adk_provider_and_exporter: tuple[TracerProvider, InMemorySpanExporter],
) -> None:
    provider, exporter = adk_provider_and_exporter

    agent = LlmAgent(
        name="trip_planner",
        description="Tests the Weave ADK integration end-to-end.",
        model=_StubLlm(model="stub-llm"),
        tools=[FunctionTool(_get_weather)],
    )
    runner = InMemoryRunner(agent=agent, app_name="adk-test-app")

    async def _drive() -> None:
        await runner.session_service.create_session(
            app_name="adk-test-app", user_id="u1", session_id="s1"
        )
        msg = types.Content(role="user", parts=[types.Part(text="Weather in Paris?")])
        async for _ in runner.run_async(
            user_id="u1", session_id="s1", new_message=msg
        ):
            pass

    asyncio.run(_drive())
    provider.force_flush()

    by_op: dict[str, list[Any]] = {}
    for span in exporter.get_finished_spans():
        op = (span.attributes or {}).get("gen_ai.operation.name", "")
        by_op.setdefault(str(op), []).append(span)

    # ADK opens exactly one invoke_agent span per turn.
    invoke_spans = by_op.get("invoke_agent", [])
    assert invoke_spans, "ADK did not emit an invoke_agent span"
    invoke_attrs = invoke_spans[0].attributes
    for key in (
        "gen_ai.provider.name",
        "gen_ai.agent.name",
        "gen_ai.agent.description",
        "gen_ai.agent.id",
        "gen_ai.conversation.id",
    ):
        assert key in invoke_attrs, f"invoke_agent span missing {key}"

    # Exactly one execute_tool span for our custom tool.
    tool_spans = by_op.get("execute_tool", [])
    assert tool_spans, "ADK did not emit an execute_tool span"
    tool_attrs = tool_spans[0].attributes
    assert tool_attrs["gen_ai.provider.name"] == "gemini"
    assert tool_attrs["gen_ai.tool.call.arguments"] == json.dumps(
        {"city": "Paris"}, ensure_ascii=False
    )
    assert tool_attrs["gen_ai.tool.call.result"] == json.dumps(
        _get_weather("Paris"), ensure_ascii=False, default=str
    )

    # ``generate_content`` is the modern LLM-call op name. There may be
    # multiple (one per model invocation); every one of them should carry
    # the patched attributes.
    llm_spans = by_op.get("generate_content", [])
    assert llm_spans, "ADK did not emit a generate_content span"
    for span in llm_spans:
        attrs = span.attributes
        for key in (
            "gen_ai.provider.name",
            "gen_ai.response.model",
            "gen_ai.response.id",
            "gen_ai.input.messages",
            "gen_ai.output.messages",
            "gen_ai.output.type",
            "gen_ai.tool.definitions",
        ):
            assert key in attrs, f"generate_content span missing {key}"
