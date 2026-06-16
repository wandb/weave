"""Integration tests for the rescore evaluation feature at the trace-server layer.

These tests exercise evaluation_run_create/read with source_evaluation_run_id, and
the rescore() method on the trace server (ClickHouse via client fixture).

Tests do NOT invoke the Kafka worker or real scorer objects — the rescore() path is
tested only up to dispatcher dispatch, which is mocked out.
"""

from unittest.mock import MagicMock

import pytest

from tests.trace.server_utils import find_server_layer
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.trace_server_interface import (
    CallReadReq,
    EvaluationRunCreateReq,
    EvaluationRunReadReq,
    PredictionCreateReq,
    PredictionFinishReq,
    PredictionListReq,
    RescoreReq,
    RescoringArgs,
)
from weave.utils.project_id import from_project_id

# ---------------------------------------------------------------------------
# evaluation_run_create / read round-trip with source_evaluation_run_id
# ---------------------------------------------------------------------------


def test_evaluation_run_source_id_round_trip(client):
    """source_evaluation_run_id written at create time survives a read; a run
    created without one reads back None.
    """
    project_id = client.project_id

    source_run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://source",
            model="model://source",
        )
    )
    # A run that is a rescore of the source preserves the link.
    rescore_run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://source",
            model="model://source",
            source_evaluation_run_id=source_run.evaluation_run_id,
        )
    )
    rescore_read = client.server.evaluation_run_read(
        EvaluationRunReadReq(
            project_id=project_id,
            evaluation_run_id=rescore_run.evaluation_run_id,
        )
    )
    assert rescore_read.source_evaluation_run_id == source_run.evaluation_run_id

    # The source run itself has no source -> None on read.
    source_read = client.server.evaluation_run_read(
        EvaluationRunReadReq(
            project_id=project_id,
            evaluation_run_id=source_run.evaluation_run_id,
        )
    )
    assert source_read.source_evaluation_run_id is None


# ---------------------------------------------------------------------------
# rescore() creates a new EvaluationRun and dispatches RescoringArgs
# ---------------------------------------------------------------------------


def _setup_server_with_dispatcher(server):
    """Replace the dispatcher on the underlying ClickHouse server with a mock.

    Uses find_server_layer to locate the ClickHouseTraceServer that owns
    _evaluate_model_dispatcher, then swaps it for a MagicMock so rescore()
    can be tested without real worker invocation.
    """
    target = find_server_layer(server, ClickHouseTraceServer)
    mock_dispatcher = MagicMock()
    target._evaluate_model_dispatcher = mock_dispatcher
    return mock_dispatcher


def test_rescore_allocates_new_id_and_dispatches_without_precreating_call(client):
    """rescore() must allocate a fresh evaluation_run_id and dispatch the
    worker, but must NOT pre-create the call row. Call ownership lives
    entirely with the worker — pre-creating a call_start server-side
    while the worker emits the call_end downstream is what produces the
    'orphaned call ends' bug in the worker's CallBatchProcessor.
    """
    project_id = client.project_id
    entity, _ = from_project_id(project_id)

    # Create source evaluation run
    source_run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://rescore-test",
            model="model://rescore-test",
        )
    )

    mock_dispatcher = _setup_server_with_dispatcher(client.server)
    scorer_ref = f"weave:///{project_id}/object/scorer:abc123"

    res = client.server.rescore(
        RescoreReq(
            project_id=project_id,
            source_evaluation_run_id=source_run.evaluation_run_id,
            scorer_refs=[scorer_ref],
            wb_user_id=entity,
        )
    )

    # call_id and evaluation_run_id must be the same (so /evaluations/status can poll)
    assert res.call_id == res.evaluation_run_id
    assert res.evaluation_run_id != source_run.evaluation_run_id

    # The new id must NOT correspond to an existing call yet — the worker
    # will emit call_start when it picks up the dispatch.
    read_res = client.server.call_read(
        CallReadReq(project_id=project_id, id=res.evaluation_run_id)
    )
    assert read_res.call is None, (
        "rescore() must NOT pre-create the eval call; the worker is the "
        "sole owner of call_start/call_end for this id"
    )

    # Dispatcher was called with a RescoringArgs containing the right IDs
    mock_dispatcher.dispatch.assert_called_once()
    dispatched = mock_dispatcher.dispatch.call_args[0][0]
    assert isinstance(dispatched, RescoringArgs)
    assert dispatched.source_evaluation_run_id == source_run.evaluation_run_id
    assert dispatched.new_evaluation_run_id == res.evaluation_run_id
    # scorer_refs are converted to internal format by the adapter — just check
    # that one ref was passed and it contains the expected object name and digest
    assert len(dispatched.scorer_refs) == 1
    assert "scorer" in dispatched.scorer_refs[0]
    assert "abc123" in dispatched.scorer_refs[0]


def test_rescore_without_wb_user_id_raises(client):
    """rescore() must reject requests with wb_user_id=None at the server layer."""
    project_id = client.project_id

    source_run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://user-check",
            model="model://user-check",
        )
    )

    _setup_server_with_dispatcher(client.server)

    with pytest.raises(ValueError, match="wb_user_id"):
        client.server.rescore(
            RescoreReq(
                project_id=project_id,
                source_evaluation_run_id=source_run.evaluation_run_id,
                scorer_refs=["weave:///e/p/object/scorer:abc"],
                wb_user_id=None,  # must be rejected
            )
        )


# ---------------------------------------------------------------------------
# prediction_list — basic sanity check used by rescore_worker
# ---------------------------------------------------------------------------


def test_prediction_list_filters_by_run_and_paginates(client):
    """prediction_list returns only the requested run's predictions and honors
    limit/offset (non-overlapping pages) within that run.
    """
    project_id = client.project_id

    run_a = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://list-a",
            model="model://list-a",
        )
    )
    run_b = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://list-b",
            model="model://list-b",
        )
    )

    # 5 predictions for run_a (enough to paginate), 1 for run_b.
    for i in range(5):
        _create_finished_prediction(
            client, project_id, "model://list-a", run_a.evaluation_run_id, i
        )
    _create_finished_prediction(
        client, project_id, "model://list-b", run_b.evaluation_run_id, 99
    )

    # Filtering: each run sees only its own predictions.
    preds_a = list(
        client.server.prediction_list(
            PredictionListReq(
                project_id=project_id, evaluation_run_id=run_a.evaluation_run_id
            )
        )
    )
    assert len(preds_a) == 5
    assert all(p.evaluation_run_id == run_a.evaluation_run_id for p in preds_a)

    preds_b = list(
        client.server.prediction_list(
            PredictionListReq(
                project_id=project_id, evaluation_run_id=run_b.evaluation_run_id
            )
        )
    )
    assert len(preds_b) == 1
    assert preds_b[0].evaluation_run_id == run_b.evaluation_run_id

    # Pagination over run_a: limit/offset return non-overlapping pages.
    page1 = list(
        client.server.prediction_list(
            PredictionListReq(
                project_id=project_id,
                evaluation_run_id=run_a.evaluation_run_id,
                limit=3,
                offset=0,
            )
        )
    )
    assert len(page1) == 3
    page2 = list(
        client.server.prediction_list(
            PredictionListReq(
                project_id=project_id,
                evaluation_run_id=run_a.evaluation_run_id,
                limit=3,
                offset=3,
            )
        )
    )
    assert len(page2) == 2
    assert {p.prediction_id for p in page1}.isdisjoint({p.prediction_id for p in page2})


def _create_finished_prediction(
    client, project_id: str, model: str, evaluation_run_id: str, i: int
) -> None:
    pred = client.server.prediction_create(
        PredictionCreateReq(
            project_id=project_id,
            model=model,
            inputs={"i": i},
            output=f"out-{i}",
            evaluation_run_id=evaluation_run_id,
        )
    )
    client.server.prediction_finish(
        PredictionFinishReq(project_id=project_id, prediction_id=pred.prediction_id)
    )
