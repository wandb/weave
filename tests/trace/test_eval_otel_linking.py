"""Tests for automatic GenAI span -> eval prediction linking via EvalLinkSpanProcessor."""

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import weave
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave import Evaluation
from weave.evaluation.otel_eval_linker import EvalLinkSpanProcessor
from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture
def otel_setup(monkeypatch: pytest.MonkeyPatch):
    """Install an isolated OTel provider for each test.

    OTel only allows set_tracer_provider once per process, so we add our
    processors to a temporary provider via monkeypatch instead of mutating
    whatever provider is already active.
    """
    exporter = InMemorySpanExporter()

    provider = SDKTracerProvider()
    span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    provider.add_span_processor(EvalLinkSpanProcessor())
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)

    yield exporter

    provider.shutdown()


def _emit_genai_span(model: str = "gpt-4o") -> None:
    """Create and end a GenAI OTel span, simulating an LLM call."""
    tracer = otel_trace.get_tracer("test")
    span = tracer.start_span("chat")
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", model)
    span.end()


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
@pytest.mark.asyncio
async def test_genai_span_ref_attached_to_eval_call(client, otel_setup):
    """A GenAI OTel span emitted during a prediction should produce a
    GenAISpanRef on the predict_and_score call summary.
    """
    exporter = otel_setup

    @weave.op
    async def model_predict(input) -> str:
        _emit_genai_span()
        return input

    evaluation = Evaluation(
        dataset=[{"input": "1 + 1"}],
        scorers=[],
    )
    await evaluation.evaluate(model_predict)
    client.flush()

    # Verify the OTel span was emitted
    spans = exporter.get_finished_spans()
    genai_spans = [s for s in spans if s.attributes.get("gen_ai.operation.name")]
    assert len(genai_spans) == 1

    # Verify the GenAISpanRef was attached to the eval results
    evaluate_call = next(iter(evaluation.evaluate.calls()))
    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )

    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is not None
    assert len(trial.genai_span_ref) == 1
    # OTel stores trace/span IDs as integers; W3C Trace Context represents them
    # as zero-padded hex: 32 hex chars for 128-bit trace IDs, 16 for 64-bit span IDs.
    assert trial.genai_span_ref[0].trace_id == format(
        genai_spans[0].context.trace_id, "032x"
    )
    assert trial.genai_span_ref[0].span_id == format(
        genai_spans[0].context.span_id, "016x"
    )


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
@pytest.mark.asyncio
async def test_multiple_genai_span_refs_attached_to_eval_call(client, otel_setup):
    """All GenAI OTel spans emitted during a prediction should be linked."""
    exporter = otel_setup

    @weave.op
    async def model_predict(input) -> str:
        _emit_genai_span("gpt-4o")
        _emit_genai_span("gpt-4o-mini")
        return input

    evaluation = Evaluation(
        dataset=[{"input": "1 + 1"}],
        scorers=[],
    )
    await evaluation.evaluate(model_predict)
    client.flush()

    genai_spans = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name")
    ]
    assert len(genai_spans) == 2

    evaluate_call = next(iter(evaluation.evaluate.calls()))
    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )

    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is not None
    assert {(r.trace_id, r.span_id) for r in trial.genai_span_ref} == {
        (format(s.context.trace_id, "032x"), format(s.context.span_id, "016x"))
        for s in genai_spans
    }


@pytest.mark.asyncio
async def test_eval_metadata_injected_onto_spans(client, otel_setup):
    """Eval context attributes should be injected onto all spans created
    during a predict_and_score context for reverse lookup in the agent traces UI.
    """
    exporter = otel_setup

    @weave.op
    async def model_predict(input) -> str:
        _emit_genai_span()
        return input

    evaluation = Evaluation(
        dataset=[{"input": "1 + 1"}],
        scorers=[],
    )
    await evaluation.evaluate(model_predict)

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1

    span_attrs = dict(spans[0].attributes)
    assert constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR in span_attrs
    assert constants.EVAL_PROJECT_ID_SPAN_ATTR in span_attrs


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
@pytest.mark.asyncio
async def test_non_genai_span_gets_eval_metadata_but_no_span_ref(client, otel_setup):
    """Non-GenAI spans during eval get eval metadata (on_start) but no
    GenAISpanRef (on_end only links spans with gen_ai.operation.name).
    """
    exporter = otel_setup

    @weave.op
    async def model_predict(input) -> str:
        tracer = otel_trace.get_tracer("test")
        span = tracer.start_span("some-other-work")
        span.end()
        return input

    evaluation = Evaluation(
        dataset=[{"input": "1 + 1"}],
        scorers=[],
    )
    await evaluation.evaluate(model_predict)
    client.flush()

    # The span should have eval metadata from on_start
    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    span_attrs = dict(spans[0].attributes)
    assert constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR in span_attrs

    # But the eval results should NOT have a GenAISpanRef
    evaluate_call = next(iter(evaluation.evaluate.calls()))
    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )

    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is None


@pytest.mark.asyncio
async def test_genai_span_outside_eval_does_not_crash(otel_setup):
    """A GenAI span emitted outside of an eval context should be silently ignored."""
    _emit_genai_span()

    spans = otel_setup.get_finished_spans()
    assert len(spans) == 1
    assert constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR not in dict(
        spans[0].attributes
    )
