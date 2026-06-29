"""Unit tests for rescore_worker.py and the EvalWorkerJob discriminated union.

Covers:
- EvalWorkerJob discriminated union parsing (evaluate_model and rescore job types)
- scorer_refs min_length=1 validation
- rescore_predictions pagination: score_create called once per prediction x scorer
- Summary keyed by scorer_name (not scorer ref URI)
- evaluation_run_finish called even on unexpected exception
"""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from weave.trace_server.trace_server_interface import (
    EvaluateModelArgs,
    EvalWorkerJob,
    PredictionReadRes,
    RescoringArgs,
)

# ---------------------------------------------------------------------------
# Discriminated union parsing
# ---------------------------------------------------------------------------


class TestEvalWorkerJobDiscriminator:
    def test_parse_evaluate_model_explicit_job_type(self):
        raw = {
            "job_type": "evaluate_model",
            "project_id": "entity/project",
            "evaluation_ref": "weave:///entity/project/object/eval:abc",
            "model_ref": "weave:///entity/project/object/model:def",
            "wb_user_id": "user1",
            "evaluation_call_id": "call-123",
        }
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EvalWorkerJob)
        job = adapter.validate_python(raw)
        assert isinstance(job, EvaluateModelArgs)
        assert job.project_id == "entity/project"
        assert job.evaluation_call_id == "call-123"

    def test_parse_rescore_job_type(self):
        raw = {
            "job_type": "rescore",
            "project_id": "entity/project",
            "source_evaluation_run_id": "run-abc",
            "scorer_refs": ["weave:///entity/project/object/scorer:xyz"],
            "new_evaluation_run_id": "run-new",
        }
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EvalWorkerJob)
        job = adapter.validate_python(raw)
        assert isinstance(job, RescoringArgs)
        assert job.source_evaluation_run_id == "run-abc"
        assert job.new_evaluation_run_id == "run-new"

    def test_rescore_args_wb_user_id_defaults_to_none(self):
        args = RescoringArgs(
            project_id="e/p",
            source_evaluation_run_id="src-run",
            scorer_refs=["weave:///e/p/object/scorer:abc"],
            new_evaluation_run_id="new-run",
        )
        assert args.wb_user_id is None

    def test_rescore_args_scorer_refs_min_length_enforced(self):
        with pytest.raises(ValidationError):
            RescoringArgs(
                project_id="e/p",
                source_evaluation_run_id="src-run",
                scorer_refs=[],  # violates min_length=1
                new_evaluation_run_id="new-run",
            )

    def test_evaluate_model_args_job_type_default(self):
        args = EvaluateModelArgs(
            project_id="e/p",
            evaluation_ref="weave:///e/p/object/eval:abc",
            model_ref="weave:///e/p/object/model:def",
            wb_user_id="user1",
            evaluation_call_id="call-1",
        )
        assert args.job_type == "evaluate_model"

    def test_rescore_args_job_type_default(self):
        args = RescoringArgs(
            project_id="e/p",
            source_evaluation_run_id="src-run",
            scorer_refs=["weave:///e/p/object/scorer:abc"],
            new_evaluation_run_id="new-run",
        )
        assert args.job_type == "rescore"


# ---------------------------------------------------------------------------
# rescore_predictions pagination and score_create call count
# ---------------------------------------------------------------------------


def _make_prediction(prediction_id: str, inputs: dict, output) -> PredictionReadRes:
    return PredictionReadRes(
        prediction_id=prediction_id,
        model="model://test",
        inputs=inputs,
        output=output,
        evaluation_run_id="src-run",
    )


def _make_fake_scorer(name: str, return_value):
    """Build a minimal fake Scorer-like object that passes isinstance check."""
    from weave.flow.scorer import Scorer

    class FakeScorer(Scorer):
        def score(self, output, **kwargs):
            return return_value

    scorer = FakeScorer()
    scorer.name = name
    return scorer


@pytest.mark.asyncio
async def test_rescore_predictions_score_create_called_per_prediction_per_scorer():
    """score_create must be called once per (prediction, scorer) pair."""
    predictions = [
        _make_prediction("pred-1", {"x": 1}, "out-1"),
        _make_prediction("pred-2", {"x": 2}, "out-2"),
    ]
    scorer_ref = "weave:///e/p/object/scorer:abc"
    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=[scorer_ref],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    mock_server = MagicMock()
    mock_server.prediction_list.return_value = iter(predictions)
    mock_server.score_create = MagicMock()
    mock_server.evaluation_run_finish = MagicMock()

    mock_client = MagicMock()
    mock_client.server = mock_server

    scorer_instance = MagicMock()

    class FakeApplyResult:
        result: ClassVar[dict] = {"correct": True}

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_secure_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=scorer_instance,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes"
        ) as mock_get_attrs,
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.apply_scorer_async",
            new=AsyncMock(return_value=FakeApplyResult()),
        ),
        patch("weave.attributes"),
    ):
        mock_scorer_attrs = MagicMock()
        mock_scorer_attrs.scorer_name = "my_scorer"
        mock_scorer_attrs.summarize_fn = MagicMock(return_value={"mean": 1.0})
        mock_get_attrs.return_value = mock_scorer_attrs

        from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
            rescore_predictions,
        )

        await rescore_predictions(args)

    # score_create should be called once per prediction (2 predictions, 1 scorer)
    assert mock_server.score_create.call_count == 2
    # evaluation_run_finish should be called exactly once
    assert mock_server.evaluation_run_finish.call_count == 1


@pytest.mark.asyncio
async def test_rescore_predictions_summary_keyed_by_scorer_name_not_ref():
    """Summary dict must use scorer_attrs.scorer_name as key, not the ref URI."""
    prediction = _make_prediction("pred-1", {"x": 1}, "out-1")
    scorer_ref = "weave:///e/p/object/scorer:abc"
    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=[scorer_ref],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    mock_server = MagicMock()
    mock_server.prediction_list.return_value = iter([prediction])
    mock_server.score_create = MagicMock()
    captured_finish_calls = []

    def capture_finish(req):
        captured_finish_calls.append(req)

    mock_server.evaluation_run_finish = capture_finish

    mock_client = MagicMock()
    mock_client.server = mock_server

    class FakeApplyResult:
        result = 0.9

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_secure_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=MagicMock(),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes"
        ) as mock_get_attrs,
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.apply_scorer_async",
            new=AsyncMock(return_value=FakeApplyResult()),
        ),
        patch("weave.attributes"),
    ):
        mock_scorer_attrs = MagicMock()
        mock_scorer_attrs.scorer_name = "human_readable_scorer_name"
        mock_scorer_attrs.summarize_fn = MagicMock(return_value={"mean": 0.9})
        mock_get_attrs.return_value = mock_scorer_attrs

        from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
            rescore_predictions,
        )

        await rescore_predictions(args)

    assert len(captured_finish_calls) == 1
    finish_req = captured_finish_calls[0]
    # Key must be the human-readable scorer_name, NOT the ref URI
    assert "human_readable_scorer_name" in finish_req.summary
    assert scorer_ref not in finish_req.summary


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_rescore_predictions_evaluation_run_finish_called_on_exception():
    """evaluation_run_finish must be called with an empty summary on unexpected error,
    and the exception must be swallowed so Kafka does not redeliver and double-write
    scores into the (already finished) new_evaluation_run_id.
    """
    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=["weave:///e/p/object/scorer:abc"],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    mock_server = MagicMock()
    # Make prediction_list raise an unexpected error
    mock_server.prediction_list.side_effect = RuntimeError("db error")
    mock_server.evaluation_run_finish = MagicMock()

    mock_client = MagicMock()
    mock_client.server = mock_server

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_secure_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=MagicMock(),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes"
        ) as mock_get_attrs,
        patch("weave.attributes"),
    ):
        mock_get_attrs.return_value = MagicMock(
            scorer_name="s", summarize_fn=MagicMock(return_value={})
        )

        from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
            rescore_predictions,
        )

        # Exception must be swallowed — no pytest.raises here.
        await rescore_predictions(args)

    # finish must still have been called (with empty summary)
    assert mock_server.evaluation_run_finish.call_count == 1
    finish_call = mock_server.evaluation_run_finish.call_args[0][0]
    assert finish_call.summary == {}
    assert finish_call.evaluation_run_id == "new-run"


@pytest.mark.asyncio
async def test_rescore_predictions_pagination_exhausts_all_pages():
    """Pagination: when first page is full (== PAGE_SIZE), a second request is made."""
    from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
        PREDICTION_PAGE_SIZE,
    )

    page1 = [
        _make_prediction(f"pred-{i}", {"x": i}, f"out-{i}")
        for i in range(PREDICTION_PAGE_SIZE)
    ]
    page2 = [_make_prediction("pred-last", {"x": 999}, "out-last")]

    call_count = 0

    def fake_prediction_list(req):
        nonlocal call_count
        call_count += 1
        if req.offset == 0:
            return iter(page1)
        return iter(page2)

    mock_server = MagicMock()
    mock_server.prediction_list.side_effect = fake_prediction_list
    mock_server.score_create = MagicMock()
    mock_server.evaluation_run_finish = MagicMock()

    mock_client = MagicMock()
    mock_client.server = mock_server

    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=["weave:///e/p/object/scorer:abc"],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    class FakeApplyResult:
        result = True

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_secure_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=MagicMock(),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes"
        ) as mock_get_attrs,
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.apply_scorer_async",
            new=AsyncMock(return_value=FakeApplyResult()),
        ),
        patch("weave.attributes"),
    ):
        mock_get_attrs.return_value = MagicMock(
            scorer_name="s",
            summarize_fn=MagicMock(return_value={"mean": 1.0}),
        )

        from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
            rescore_predictions,
        )

        await rescore_predictions(args)

    # prediction_list was called twice: once for page1, once for page2
    assert call_count == 2
    # score_create was called for all PAGE_SIZE + 1 predictions
    assert mock_server.score_create.call_count == PREDICTION_PAGE_SIZE + 1
