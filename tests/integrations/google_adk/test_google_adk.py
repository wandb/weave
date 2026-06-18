"""Tests for the Google ADK ↔ Weave OTel integration.

Organised by the layer each class exercises:

- :class:`TestExtractors` drives the attribute extractors in
  :mod:`weave.integrations.google_adk.extractors` against lightweight
  dataclass mocks of ``google.genai.types`` shapes. Fast, no ADK runner.
- :class:`TestWrappers` drives the patcher wrappers directly to verify
  edge-case behaviours that are awkward to observe end-to-end.
- :class:`TestAdkRunnerE2E` runs a real ADK ``InMemoryRunner`` with a stub
  ``BaseLlm`` so ADK itself opens every span, tees an
  ``InMemorySpanExporter`` onto the global ``TracerProvider``, and asserts
  the patched attributes land where they should.
"""

from __future__ import annotations

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

from weave.integrations.google_adk import _semconv
from weave.integrations.google_adk.extractors import (
    _provider_name,
    set_llm_request_attributes,
    set_llm_response_attributes,
)
from weave.integrations.google_adk.google_adk_sdk import (
    _wrap_trace_inference_result,
    _wrap_trace_tool_call,
    get_google_adk_patcher,
)
from weave.trace_server.agents import semconv as server_semconv

# The mocks below mirror the duck-typed surface our extractors inspect on
# ``google.genai.types.*`` objects and ADK's ``LlmRequest`` / ``LlmResponse``
# wrappers. Using real pydantic objects would be heavier (full
# ``google-genai`` import + validation) for no extra coverage; the E2E
# class drives the real types.
#
# ``_AttrSpan`` records every ``set_attribute`` call so tests can assert on
# the literal semconv keys without an OTel SDK in scope.


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


class TestExtractors:
    """Cover the attribute extractors in isolation, without ADK's runner."""

    def test_set_llm_request_attributes_full_payload(self) -> None:
        """Every request-side attribute the patch promises lands on the span."""
        # Build a request that exercises every decoding-param field Weave's
        # schema cares about, plus the system-instruction envelope and the
        # ADK→GenAI role mapping ("model" → "assistant").
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

        set_llm_request_attributes(span, llm_request)

        # Decoding params: ADK natively emits only ``top_p`` and
        # ``max_output_tokens``, so every other key here is one the
        # integration is on the hook for. If a downstream Weave column
        # silently goes empty, this block fails first.
        a = span.attributes
        assert a["gen_ai.request.temperature"] == 0.4
        assert a["gen_ai.request.top_p"] == 0.9
        assert a["gen_ai.request.max_tokens"] == 512
        assert a["gen_ai.request.frequency_penalty"] == 0.1
        assert a["gen_ai.request.presence_penalty"] == 0.2
        assert a["gen_ai.request.seed"] == 42
        assert a["gen_ai.request.stop_sequences"] == ["END"]
        assert a["gen_ai.request.choice.count"] == 1

        # System instructions are wrapped in the parts-model envelope so
        # the same wire shape works across text and (future) multimodal
        # instructions.
        instructions = json.loads(a["gen_ai.system_instructions"])
        assert instructions == [{"type": "text", "content": "you are helpful"}]

        # Role mapping: ADK uses "model" for the assistant turn; the Weave
        # UI expects "assistant". This is the line a user sees first if it
        # drifts.
        input_messages = json.loads(a["gen_ai.input.messages"])
        assert input_messages[0]["role"] == "user"
        assert input_messages[1]["role"] == "assistant"

    def test_set_llm_response_attributes_full_payload(self) -> None:
        """Every response-side attribute the patch promises lands on the span."""
        # Build a response with the full usage payload plus a text output;
        # exercises the canonical reasoning-tokens key, the Gemini-only
        # cache-read tokens, the parts-model output envelope, and the
        # "model" → "assistant" role mapping on the response side.
        span = _AttrSpan()
        llm_response = _MockLlmResponse(
            content=_MockContent(role="model", parts=[_MockPart(text="cool answer")]),
            finish_reason=types.FinishReason.STOP,
            usage_metadata=_MockUsageMetadata(
                prompt_token_count=120,
                candidates_token_count=42,
                thoughts_token_count=8,
                cached_content_token_count=15,
            ),
            interaction_id="resp-9988",
            model_version="gemini-2.0-flash-2025-01",
        )

        set_llm_response_attributes(span, llm_response)

        # Response identity and modality. ``output.type`` is what Weave's
        # column-extractor uses to route the response into the right UI.
        a = span.attributes
        assert a["gen_ai.response.id"] == "resp-9988"
        assert a["gen_ai.response.model"] == "gemini-2.0-flash-2025-01"
        assert a["gen_ai.output.type"] == "text"

        # Usage metrics. ``gen_ai.usage.reasoning.output_tokens`` is the
        # canonical OTel name from semantic-conventions#3383 (merged
        # 2026-04-27); ``cache_read.input_tokens`` is the Gemini-specific
        # cached-prefix counter ADK omits.
        assert a["gen_ai.usage.reasoning.output_tokens"] == 8
        assert a["gen_ai.usage.cache_read.input_tokens"] == 15

        # Output envelope mirrors the request side's role mapping.
        output_messages = json.loads(a["gen_ai.output.messages"])
        assert output_messages[0]["role"] == "assistant"
        assert output_messages[0]["parts"][0]["content"] == "cool answer"

    def test_set_llm_response_attributes_skips_empty_fields(self) -> None:
        """Empty optional fields don't leak as attributes on the span."""
        # A bare response (no content, no usage) should still surface
        # whatever metadata we do have, without writing empty/None values
        # that would clutter the Weave UI.
        span = _AttrSpan()
        set_llm_response_attributes(
            span,
            _MockLlmResponse(content=None, model_version="m"),
        )
        assert "gen_ai.response.id" not in span.attributes
        assert "gen_ai.output.messages" not in span.attributes
        assert span.attributes["gen_ai.response.model"] == "m"

    def test_provider_name_vertex(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``GOOGLE_GENAI_USE_VERTEXAI`` flips the provider to ``vertex_ai``."""
        # The integration must re-read the env var per span — notebooks
        # and tests flip it between runs and ``gen_ai.provider.name`` has
        # to follow.
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
        assert _provider_name() == "vertex_ai"
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")
        assert _provider_name() == "gemini"
        monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
        assert _provider_name() == "gemini"

    def test_capture_message_content_disabled_hides_request_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`` hides request content.

        Decoding params and tool definitions stay on — they're not user data.
        """
        # PHI/PII opt-out: when ADK's own capture switch is off, the
        # integration must not be the leak that puts message bodies on
        # spans anyway. Non-content metadata (decoding params, tool
        # schemas) stays — it's not user data.
        monkeypatch.setenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")
        span = _AttrSpan()
        llm_request = _MockLlmRequest(
            model="gemini-2.0-flash",
            contents=[_MockContent(role="user", parts=[_MockPart(text="hi")])],
            config=_MockGenerateContentConfig(
                temperature=0.4,
                system_instruction="secret",
            ),
        )

        set_llm_request_attributes(span, llm_request)

        assert "gen_ai.input.messages" not in span.attributes
        assert "gen_ai.system_instructions" not in span.attributes
        assert span.attributes["gen_ai.request.temperature"] == 0.4

    def test_capture_message_content_disabled_hides_response_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`` hides response content.

        Response metadata (id, model, usage) stays on — only the parts-model
        payload is gated.
        """
        # Mirror of the request-side gate, but for the response. Metadata
        # the user needs to debug (id, model, usage counts) stays on;
        # only the parts-model body is suppressed.
        monkeypatch.setenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")
        span = _AttrSpan()
        llm_response = _MockLlmResponse(
            content=_MockContent(role="model", parts=[_MockPart(text="secret")]),
            finish_reason=types.FinishReason.STOP,
            usage_metadata=_MockUsageMetadata(prompt_token_count=10),
            interaction_id="resp-1",
            model_version="m",
        )

        set_llm_response_attributes(span, llm_response)

        assert "gen_ai.output.messages" not in span.attributes
        assert "gen_ai.output.type" not in span.attributes
        assert span.attributes["gen_ai.response.id"] == "resp-1"
        assert span.attributes["gen_ai.response.model"] == "m"


class TestWrappers:
    """Drive the patcher wrappers directly to verify edge-case behaviour."""

    def test_trace_inference_result_skips_partial_chunks(self) -> None:
        """Partial streaming chunks must not stomp the span.

        ADK's own ``trace_inference_result`` returns early on
        ``llm_response.partial``; the wrapper mirrors that contract.
        """
        # The wrapper fires once per streamed chunk. Without the partial
        # guard, every intermediate chunk would overwrite the span's
        # parts-model with a half-built payload — the final span would
        # then reflect the last partial, not the aggregated response.
        # This test locks in the "only the final chunk wins" contract.
        original_calls: list[LlmResponse] = []

        def fake_original(span: Any, llm_response: LlmResponse) -> None:
            original_calls.append(llm_response)

        wrapped = _wrap_trace_inference_result(fake_original)

        # First, a partial chunk: ADK's own body bails on partials, and
        # the wrapper must too — nothing supplemental should land.
        partial_span = _AttrSpan()
        partial = LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="half-built")]),
            partial=True,
            interaction_id="partial-1",
            model_version="m",
        )
        wrapped(partial_span, partial)
        assert partial_span.attributes == {}, (
            "partial chunks should not write supplemental attributes"
        )

        # Then a final chunk: the aggregated response now lands fully.
        final_span = _AttrSpan()
        final = LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part(text="final answer")]
            ),
            partial=False,
            finish_reason=types.FinishReason.STOP,
            interaction_id="final-1",
            model_version="m",
        )
        wrapped(final_span, final)
        assert final_span.attributes["gen_ai.response.id"] == "final-1"
        assert "gen_ai.output.messages" in final_span.attributes

        # We mirror ADK's gate, we don't skip its body — the original
        # must still see every chunk so it can record streaming metrics.
        assert len(original_calls) == 2

    def test_trace_tool_call_error_keeps_arguments_omits_result(self) -> None:
        """Tool errors land an args-only span — never a half-built result.

        ADK calls ``trace_tool_call`` with ``function_response_event=None``
        and ``error=<exc>`` on tool failure. The wrapper writes the args
        (they exist regardless of outcome) but must not synthesise a
        ``gen_ai.tool.call.result``.
        """
        # On tool failure the user still needs to see what arguments
        # were passed — that's debugging signal. But a synthesised
        # ``result`` would be a lie, so this test pins the args-yes /
        # result-no shape.
        called: list[tuple[Any, ...]] = []

        def fake_original(*args: Any, **kwargs: Any) -> None:
            called.append((args, kwargs))

        wrapped = _wrap_trace_tool_call(fake_original)
        span = _AttrSpan()
        tool = object()  # signature only; the wrapper does not introspect it
        wrapped(
            tool,
            {"city": "Paris"},
            None,
            error=RuntimeError("kaboom"),
            span=span,
        )

        assert span.attributes["gen_ai.tool.call.arguments"] == json.dumps(
            {"city": "Paris"}, ensure_ascii=False
        )
        assert "gen_ai.tool.call.result" not in span.attributes
        # ADK's own body still has to run so it can set ``error.type`` on
        # the span — the wrapper enriches, it doesn't replace.
        assert called, "original must still run so ADK's error.type lands"

    def test_trace_tool_call_respects_capture_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`` hides tool args/result."""
        # Same PHI/PII opt-out as the request/response gates, but on the
        # tool side. Tool args and result are user data; provider name
        # is not.
        monkeypatch.setenv("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

        def fake_original(*args: Any, **kwargs: Any) -> None:
            pass

        wrapped = _wrap_trace_tool_call(fake_original)
        span = _AttrSpan()
        wrapped(object(), {"city": "Paris"}, None, error=None, span=span)

        assert "gen_ai.tool.call.arguments" not in span.attributes
        assert "gen_ai.tool.call.result" not in span.attributes
        # Provider metadata is not content, so it still lands.
        assert span.attributes["gen_ai.provider.name"] == "gemini"

    def test_trace_tool_call_forwards_added_trailing_kwargs(self) -> None:
        """ADK adds trailing optional params to ``trace_tool_call`` over
        releases — ``error_type`` landed in 2.2.0, where ADK calls the function
        with all-keyword args. The wrapper must forward the unknown kwarg
        verbatim (so ADK's own body still sets ``error.type``) instead of
        raising ``TypeError``, while still enriching the span.
        """
        called: list[tuple[Any, ...]] = []

        def fake_original(*args: Any, **kwargs: Any) -> None:
            called.append((args, kwargs))

        wrapped = _wrap_trace_tool_call(fake_original)
        span = _AttrSpan()
        # Mirror ADK 2.2.0's call shape: all keywords, ``error_type`` present.
        wrapped(
            object(),
            {"city": "Paris"},
            None,
            error=None,
            span=span,
            error_type="HTTP_ERROR",
        )

        assert called, "original must still run so ADK's own attributes land"
        _, forwarded_kwargs = called[0]
        assert forwarded_kwargs.get("error_type") == "HTTP_ERROR"
        # The wrapper still enriched the span despite the unknown kwarg.
        assert span.attributes["gen_ai.provider.name"] == "gemini"


class TestPatchInteraction:
    """Verify how the ADK patcher interacts with other Weave integrations."""

    def test_patch_google_adk_blocks_subsequent_patch_google_genai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After ``patch_google_adk``, ``patch_google_genai`` is a no-op.

        ADK already wraps the google-genai calls it makes internally and
        emits the corresponding OTel spans. Letting Weave's separate
        ``google_genai`` integration *also* patch the SDK would double-log
        every Gemini request/response. Observe the suppression at the
        patcher-factory seam: after ADK patches, the google-genai
        patcher factory must not be reached, no matter how
        ``patch_google_genai`` is invoked.
        """
        from unittest.mock import MagicMock

        from weave.integrations import patch as patch_module

        patch_module.reset_patched_integrations()
        try:
            patch_module.patch_google_adk()

            # Spy on the google-genai patcher factory. After ADK is
            # patched, no path through ``patch_google_genai`` may invoke
            # it.
            spy = MagicMock()
            monkeypatch.setattr(
                "weave.integrations.google_genai.google_genai_sdk.get_google_genai_patcher",
                spy,
            )
            patch_module.patch_google_genai()
            assert spy.call_count == 0
        finally:
            patch_module.reset_patched_integrations()


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


@dataclass(frozen=True, slots=True)
class _AdkTestHarness:
    """In-memory OTel plumbing for one e2e test run.

    Yielded by the :func:`adk_test_harness` fixture so tests can read the
    provider (for ``force_flush``) and the exporter (for asserting on the
    captured spans) without depending on tuple-unpacking order.
    """

    provider: TracerProvider
    exporter: InMemorySpanExporter


@pytest.fixture
def adk_test_harness() -> Generator[_AdkTestHarness, None, None]:
    """Install a fresh in-memory ``TracerProvider`` for one test.

    Restores the prior provider on teardown so this test can run alongside
    others in the same process without leaking patched state.
    """
    prev_provider = otel_trace.get_tracer_provider()
    provider = TracerProvider(resource=Resource.create({"service.name": "adk-test"}))
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)

    patcher = get_google_adk_patcher()
    assert patcher.attempt_patch()
    try:
        yield _AdkTestHarness(provider=provider, exporter=exporter)
    finally:
        patcher.undo_patch()
        otel_trace.set_tracer_provider(prev_provider)


class TestAdkRunnerE2E:
    """Drive ADK's real ``InMemoryRunner`` and assert on the spans it emits."""

    @pytest.mark.asyncio
    async def test_emits_all_otel_attributes(
        self, adk_test_harness: _AdkTestHarness
    ) -> None:
        # Drive a real two-turn ADK agent loop (tool call → final answer)
        # against an in-memory tracer provider, then assert the three span
        # kinds ADK actually emits (invoke_agent, execute_tool,
        # generate_content) all carry the patched Weave-superset
        # attributes. This is the regression test that catches the
        # integration silently going dark.
        agent = LlmAgent(
            name="trip_planner",
            description="Tests the Weave ADK integration end-to-end.",
            model=_StubLlm(model="stub-llm"),
            tools=[FunctionTool(_get_weather)],
        )
        runner = InMemoryRunner(agent=agent, app_name="adk-test-app")

        await runner.session_service.create_session(
            app_name="adk-test-app", user_id="u1", session_id="s1"
        )
        msg = types.Content(role="user", parts=[types.Part(text="Weather in Paris?")])
        async for _ in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
            pass

        # Group spans by GenAI operation name so each block below can
        # assert on the shape of one span kind in isolation.
        adk_test_harness.provider.force_flush()
        by_op: dict[str, list[Any]] = {}
        for span in adk_test_harness.exporter.get_finished_spans():
            op = (span.attributes or {}).get("gen_ai.operation.name", "")
            by_op.setdefault(str(op), []).append(span)

        # Integration-tracking provenance is stamped (flattened) on the ADK spans.
        stamped = [
            span.attributes
            for span in adk_test_harness.exporter.get_finished_spans()
            if "integration.name" in (span.attributes or {})
        ]
        assert stamped, "expected >=1 ADK span to carry integration metadata"
        assert all(a["integration.name"] == "google_adk" for a in stamped)
        assert all(a["integration.meta.package_name"] == "google-adk" for a in stamped)

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
        # multiple (one per model invocation); every one of them should
        # carry the patched attributes.
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


class TestVendoredSemconv:
    """The integration vendors its GenAI semconv keys (``_semconv``) instead of
    importing them from ``opentelemetry.semconv._incubating`` so ``weave`` stays
    installable alongside ``google-adk`` (which pins an older
    ``opentelemetry-sdk``). These guard the two ways the vendored literals could
    silently go wrong: drifting from the server's extraction keys, or drifting
    from the upstream spec values.
    """

    def test_every_vendored_key_is_a_server_extraction_key(self) -> None:
        """Each ``gen_ai.*`` key the integration emits must be one the trace
        server recognises, or the attribute silently never lands in a column.
        """
        vendored = {
            name: value
            for name, value in vars(_semconv).items()
            if name.startswith("GEN_AI_")
        }
        assert vendored, "no vendored GEN_AI_* constants found"
        for name, value in vendored.items():
            assert server_semconv.resolve_alias_to_canonical(value) is not None, (
                f"{name}={value!r} is not a recognised server extraction key"
            )

    def test_vendored_values_match_upstream_when_available(self) -> None:
        """When the upstream package defines a GenAI constant, our vendored
        literal must match it exactly — a drift detector and proof the vendoring
        is faithful. Constants absent from the installed semconv (e.g.
        ``gen_ai.usage.reasoning.output_tokens``, which is missing from the
        0.62b1 that ships with ``google-adk``) are simply not compared.
        """
        upstream = pytest.importorskip(
            "opentelemetry.semconv._incubating.attributes.gen_ai_attributes"
        )
        # Genuine introspection: compare our namespace to upstream's by name so
        # the test covers every overlapping key without a stale hand-kept list.
        # Membership varies by version, hence the ``in`` guard rather than a
        # blind attribute read.
        upstream_names = vars(upstream)
        compared = 0
        for name, value in vars(_semconv).items():
            if name.startswith("GEN_AI_") and name in upstream_names:
                assert value == upstream_names[name], (
                    f"vendored {name}={value!r} drifted from upstream "
                    f"{upstream_names[name]!r}"
                )
                compared += 1
        assert compared, "no vendored keys overlapped upstream — wrong module?"
        # Enum members we replaced with plain string constants. These are the
        # churn-prone values — provider/operation spellings the server stores
        # verbatim — so pin them against upstream when the enum is present.
        op_values = upstream_names.get("GenAiOperationNameValues")
        system_values = upstream_names.get("GenAiSystemValues")
        output_values = upstream_names.get("GenAiOutputTypeValues")
        if op_values is not None:
            assert _semconv.OPERATION_INVOKE_AGENT == op_values.INVOKE_AGENT.value
        if system_values is not None:
            assert _semconv.PROVIDER_VERTEX_AI == system_values.VERTEX_AI.value
            assert _semconv.PROVIDER_GEMINI == system_values.GEMINI.value
        if output_values is not None:
            assert _semconv.OUTPUT_TYPE_TEXT == output_values.TEXT.value
