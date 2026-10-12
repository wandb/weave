"""Tests for eval metadata stamping via EvalLinkSpanProcessor."""

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import weave
from weave import Evaluation
from weave.conversation import start_conversation
from weave.evaluation.otel_eval_linker import EvalLinkSpanProcessor
from weave.shared.digest import compute_row_digest
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


def _emit_weave_operation_span(operation: str = "invoke_agent") -> None:
    """Create and end a Weave-semconv OTel span."""
    tracer = otel_trace.get_tracer("test")
    span = tracer.start_span(operation)
    span.set_attribute("weave.operation.name", operation)
    span.end()


@pytest.mark.asyncio
async def test_genai_span_ref_not_written_for_eval_spans(client, otel_setup):
    """A GenAI OTel span emitted during a prediction should be queryable via
    stamped eval attributes, not by mutating the eval call summary.
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
    span_attrs = dict(genai_spans[0].attributes)
    assert constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR in span_attrs
    assert constants.EVAL_RUN_ID_SPAN_ATTR in span_attrs

    # New SDK behavior does not write genai_span_ref. The UI should find agent
    # eval traces by querying spans with the stamped eval columns.
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
async def test_multiple_genai_spans_get_eval_metadata_without_refs(client, otel_setup):
    """All GenAI OTel spans emitted during a prediction should be stamped."""
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
    for span in genai_spans:
        attrs = dict(span.attributes)
        assert constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR in attrs
        assert constants.EVAL_RUN_ID_SPAN_ATTR in attrs

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
    assert constants.EVAL_RUN_ID_SPAN_ATTR in span_attrs
    assert constants.EVAL_PROJECT_ID_SPAN_ATTR in span_attrs
    assert span_attrs[constants.EVAL_KIND_SPAN_ATTR] == "standard"


@pytest.mark.asyncio
async def test_non_genai_span_gets_eval_metadata_but_no_span_ref(client, otel_setup):
    """Non-GenAI spans during eval get eval metadata and no GenAISpanRef."""
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

    # Eval results should NOT have a GenAISpanRef.
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


def test_imperative_eval_logger_stamps_explicit_eval_metadata(
    client,
    otel_setup,
):
    """EvaluationLogger should stamp explicit row/trial metadata on OTel spans."""
    exporter = otel_setup

    ev = weave.EvaluationLogger(name="agent-eval")
    with ev.log_prediction(
        {"prompt": "hello"},
        row_digest="row-explicit",
        example_id="example-1",
        trial_index=3,
        eval_kind="agent",
    ) as pred:
        _emit_genai_span()
        pred.output = "hi"
    ev.finish()

    spans = exporter.get_finished_spans()
    genai_span = next(s for s in spans if s.attributes.get("gen_ai.operation.name"))
    span_attrs = dict(genai_span.attributes)

    assert span_attrs[constants.EVAL_RUN_ID_SPAN_ATTR] == ev._evaluate_call.id
    assert (
        span_attrs[constants.EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR]
        == pred.predict_and_score_call.id
    )
    assert span_attrs[constants.EVAL_KIND_SPAN_ATTR] == "agent"
    assert span_attrs[constants.EVAL_ROW_DIGEST_SPAN_ATTR] == "row-explicit"
    assert span_attrs[constants.EVAL_EXAMPLE_ID_SPAN_ATTR] == "example-1"
    assert span_attrs[constants.EVAL_TRIAL_INDEX_SPAN_ATTR] == 3
    assert span_attrs[constants.EVAL_EVALUATION_NAME_SPAN_ATTR] == "agent-eval"

    client.flush()
    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[ev._evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )
    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is None


def test_imperative_eval_logger_derives_row_digest_and_trial_index(client, otel_setup):
    """Default row digest and zero-based trial indexes are deterministic."""
    exporter = otel_setup
    inputs = {"prompt": "same"}

    ev = weave.EvaluationLogger(name="agent-eval-trials")
    with ev.log_prediction(inputs) as pred:
        _emit_genai_span("gpt-4o")
        pred.output = "first"
    with ev.log_prediction(inputs) as pred:
        _emit_genai_span("gpt-4o-mini")
        pred.output = "second"
    ev.finish()
    client.flush()

    spans_by_model = {
        s.attributes["gen_ai.request.model"]: dict(s.attributes)
        for s in exporter.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name")
    }

    assert spans_by_model["gpt-4o"][constants.EVAL_ROW_DIGEST_SPAN_ATTR] == (
        compute_row_digest(inputs)
    )
    assert spans_by_model["gpt-4o-mini"][constants.EVAL_ROW_DIGEST_SPAN_ATTR] == (
        compute_row_digest(inputs)
    )
    assert spans_by_model["gpt-4o"][constants.EVAL_TRIAL_INDEX_SPAN_ATTR] == 0
    assert spans_by_model["gpt-4o-mini"][constants.EVAL_TRIAL_INDEX_SPAN_ATTR] == 1


def test_imperative_eval_logger_stamps_conversation_sdk_spans(
    client,
    otel_setup,
):
    """Conversation SDK agent spans should be stamped with eval metadata."""
    exporter = otel_setup

    ev = weave.EvaluationLogger(name="conversation-agent-eval")
    with ev.log_prediction(
        {"prompt": "weather"},
        row_digest="row-conversation",
        example_id="conversation-example",
    ) as pred:
        with start_conversation(
            agent_name="weather-bot",
            conversation_id="conversation-eval",
        ) as conversation:
            with conversation.start_turn() as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Sunny")
        pred.output = "Sunny"
    ev.finish()
    client.flush()

    genai_spans = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name")
    ]
    assert {s.name for s in genai_spans} == {
        "invoke_agent weather-bot",
        "chat gpt-4o",
    }
    for span in genai_spans:
        attrs = dict(span.attributes)
        assert attrs[constants.EVAL_RUN_ID_SPAN_ATTR] == ev._evaluate_call.id
        assert attrs[constants.EVAL_KIND_SPAN_ATTR] == "agent"
        assert attrs[constants.EVAL_ROW_DIGEST_SPAN_ATTR] == "row-conversation"
        assert attrs[constants.EVAL_EXAMPLE_ID_SPAN_ATTR] == "conversation-example"
        assert attrs[constants.EVAL_TRIAL_INDEX_SPAN_ATTR] == 0

    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[ev._evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )
    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is None


def test_imperative_eval_logger_stamps_weave_operation_spans(client, otel_setup):
    """Non-GenAI OTel integrations get eval metadata on Weave operation spans."""
    exporter = otel_setup

    ev = weave.EvaluationLogger(name="weave-operation-eval")
    with ev.log_prediction({"prompt": "hello"}) as pred:
        _emit_weave_operation_span()
        pred.output = "hi"
    ev.finish()
    client.flush()

    operation_span = next(
        s for s in exporter.get_finished_spans() if s.name == "invoke_agent"
    )
    attrs = dict(operation_span.attributes)
    assert attrs[constants.EVAL_KIND_SPAN_ATTR] == "agent"

    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[ev._evaluate_call.id],
            include_predict_and_score_children=False,
        )
    )
    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref is None
