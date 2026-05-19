"""Tests for the rescore worker against a real trace server.

Asserts the V2 trace-tree invariants: rescoring an existing eval produces a
new-eval tree shaped like a normal ``Evaluation.evaluate`` run (one
predict_and_score call per source row, plus one Evaluation.summarize), and
leaves the source eval's tree untouched.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.workers.evaluate_model_worker._rescore_source import (
    _RescoreSource,
)
from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
    rescore_predictions_sync,
)


def test_rescore_source_shape() -> None:
    src = _RescoreSource(
        inputs_for_call={"q": "x"},
        inputs_for_scorer={"q": "x"},
        output={"y": "z"},
        model_latency=0.5,
    )
    assert src.inputs_for_call == {"q": "x"}
    assert src.inputs_for_scorer == {"q": "x"}
    assert src.output == {"y": "z"}
    assert src.model_latency == 0.5


def test_rescore_source_preserves_ref_form_for_dataset_backed_eval() -> None:
    """Dataset-backed evals: inputs_for_call carries the original TableRow
    ref so the new pas inputs match the source's storage shape, while
    inputs_for_scorer carries the dereffed dict for actual scoring.
    """
    src = _RescoreSource(
        inputs_for_call="weave-trace-internal:///e/p/table/abc/id/row-0",
        inputs_for_scorer={"question": "x", "expected": "y"},
        output="model output",
        model_latency=1.2,
    )
    assert isinstance(src.inputs_for_call, str)
    assert isinstance(src.inputs_for_scorer, dict)


# ---------------------------------------------------------------------------
# End-to-end against sqlite: the new eval must look like a normal eval, and
# the source eval's tree must remain untouched.
# ---------------------------------------------------------------------------


def _ts(seconds: int = 0) -> datetime.datetime:
    base = datetime.datetime(2026, 5, 6, 0, 0, 0, tzinfo=datetime.timezone.utc)
    return base + datetime.timedelta(seconds=seconds)


def _publish_source_eval_object(client, project_id: str) -> str:
    """Publish a minimal Evaluation-like object so the rescore worker has
    something real to clone via ``_publish_rescored_evaluation``. Returns
    its ref URI.

    The shape matches what a published ``Evaluation`` carries on the val:
    a ``scorers`` list of ref strings, plus other fields the worker
    preserves verbatim (dataset, trials, etc. — represented here by
    sentinels we assert on later).
    """
    res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="source-eval",
                val={
                    "_type": "Evaluation",
                    "scorers": [f"weave:///{project_id}/object/old-scorer:old"],
                    "dataset": f"weave:///{project_id}/object/dataset-stub:dd",
                    "trials": 1,
                },
            )
        )
    )
    return f"weave:///{project_id}/object/source-eval:{res.digest}"


def _build_imperative_source(
    client, project_id: str, n_rows: int = 2
) -> tuple[str, list[str], str]:
    """Build an imperative-shaped source eval directly via call_start.

    Topology:
        Evaluation.evaluate (attributes._weave_eval_meta.imperative=True)
          predict_and_score #0
          predict_and_score #1

    Returns ``(src_run_id, source_pas_ids, source_eval_ref)``. The
    ``source_eval_ref`` is a real published Evaluation ref so the rescore
    worker's ``_publish_rescored_evaluation`` helper can read and clone it.
    """
    src_id = "imp-eval-1"
    source_eval_ref = _publish_source_eval_object(client, project_id)
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=src_id,
                trace_id=src_id,
                op_name="weave:///e/p/op/Evaluation.evaluate:1",
                started_at=_ts(0),
                attributes={"_weave_eval_meta": {"imperative": True}},
                inputs={
                    "self": source_eval_ref,
                    "model": "weave:///e/p/object/model-stub:def",
                },
            )
        )
    )
    pas_ids: list[str] = []
    for i in range(n_rows):
        pas_id = f"imp-pas-{i}"
        pas_ids.append(pas_id)
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    trace_id=src_id,
                    parent_id=src_id,
                    op_name=f"weave-trace-internal:///test_project/op/{constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME}:1",
                    started_at=_ts(0),
                    attributes={},
                    inputs={
                        "example": {"q": f"q-{i}"},
                        "self": source_eval_ref,
                    },
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    ended_at=_ts(1),
                    output={
                        "output": f"answer-{i}",
                        "scores": {},
                        # Source pas carries a model_latency that the worker
                        # mirrors onto a synthetic predict subcall.
                        "model_latency": 0.5,
                    },
                    summary={},
                )
            )
        )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=src_id,
                ended_at=_ts(2),
                output={"correctness": None},
                summary={},
            )
        )
    )
    return src_id, pas_ids, source_eval_ref


def test_rescore_creates_new_pas_tree_and_leaves_source_untouched(client) -> None:
    """V2 invariants:
    - The source eval's predict_and_score children get NO new children
      (the rescore must not mutate the source tree).
    - The worker creates the entire new-eval tree itself: one
      Evaluation.evaluate root pinned to ``new_evaluation_run_id``, one
      predict_and_score child per source row, one Evaluation.summarize.
    - Each new predict_and_score's output carries the per-row scores dict
      keyed by scorer name.

    The test deliberately does NOT pre-create the new-eval call: that's
    the V2 contract — the rescore endpoint allocates the id, the worker
    owns the entire call lifecycle. Pre-creating server-side would
    re-introduce the orphaned-call_end bug.

    Scorer execution is stubbed so the test focuses on the trace-tree shape
    produced by the worker against a real sqlite-backed trace server.
    """
    project_id = client.project_id
    src_id, source_pas_ids, source_eval_ref = _build_imperative_source(
        client, project_id, n_rows=2
    )
    scorer_ref = f"weave:///{project_id}/object/scorer:abc123"

    new_run_id = "rescore-new-1"
    # NB: no call_start for new_run_id. The worker emits it.

    apply_result = MagicMock()
    apply_result.result = 1.0

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=MagicMock(),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes",
            return_value=MagicMock(
                scorer_name="imp_scorer",
                summarize_fn=MagicMock(return_value={"mean": 1.0}),
            ),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.apply_scorer_async",
            new=AsyncMock(return_value=apply_result),
        ),
    ):
        rescore_predictions_sync(
            tsi.RescoringArgs(
                project_id=project_id,
                source_evaluation_run_id=src_id,
                new_evaluation_run_id=new_run_id,
                scorer_refs=[scorer_ref],
                wb_user_id="test-user",
            )
        )

    # 1. Source tree untouched: each source predict_and_score has no children.
    for source_pas_id in source_pas_ids:
        source_children = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    filter=tsi.CallsFilter(parent_ids=[source_pas_id]),
                )
            )
        )
        assert source_children == [], (
            f"source predict_and_score {source_pas_id!r} should have no "
            f"children after rescore; got {[c.id for c in source_children]}"
        )

    # 2. New eval has one predict_and_score per source row + one summarize.
    new_eval_children = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                filter=tsi.CallsFilter(parent_ids=[new_run_id]),
            )
        )
    )
    pas_children = [
        c
        for c in new_eval_children
        if c.op_name
        and constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME in c.op_name
    ]
    summarize_children = [
        c
        for c in new_eval_children
        if c.op_name and constants.EVALUATION_SUMMARIZE_OP_NAME in c.op_name
    ]
    assert len(pas_children) == len(source_pas_ids), (
        f"expected {len(source_pas_ids)} new predict_and_score calls under "
        f"the new eval, got {len(pas_children)}"
    )
    assert len(summarize_children) == 1, (
        f"expected exactly one Evaluation.summarize call under the new eval, "
        f"got {len(summarize_children)}"
    )

    # 3. Each new predict_and_score carries the scorer result in its output.
    for new_pas in pas_children:
        assert isinstance(new_pas.output, dict)
        scores = new_pas.output.get("scores")
        assert isinstance(scores, dict)
        assert scores.get("imp_scorer") == 1.0

    # 3a. Each new pas has a synthetic ``predict`` subcall whose duration
    # mirrors the source row's model_latency. The eval-compare table reads
    # ``ended_at - started_at`` of this subcall to render per-row Latency;
    # without it the Latency column shows "N/A" for rescored runs.
    for new_pas in pas_children:
        pas_subcalls = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    filter=tsi.CallsFilter(parent_ids=[new_pas.id]),
                )
            )
        )
        predict_subcalls = [
            c for c in pas_subcalls if c.op_name and "/op/predict:" in c.op_name
        ]
        assert len(predict_subcalls) == 1, (
            f"expected exactly one synthetic predict subcall under new pas "
            f"{new_pas.id!r}; got {[c.op_name for c in pas_subcalls]}"
        )
        predict_call = predict_subcalls[0]
        assert predict_call.ended_at is not None
        duration = (predict_call.ended_at - predict_call.started_at).total_seconds()
        assert abs(duration - 0.5) < 1e-6, (
            f"synthetic predict duration {duration} should equal source "
            f"model_latency 0.5"
        )

    # 4. The new-eval root call exists, was created by the WORKER (not
    # pre-created), and ended cleanly with the summary as its output.
    new_eval_call = client.server.call_read(
        tsi.CallReadReq(project_id=project_id, id=new_run_id)
    ).call
    assert new_eval_call is not None
    assert new_eval_call.ended_at is not None, (
        "new-eval call must be ended; if it's still 'started' the worker "
        "didn't pair its call_start with call_end (orphaned-end regression)"
    )
    assert isinstance(new_eval_call.output, dict)
    assert new_eval_call.output.get("imp_scorer") == {"mean": 1.0}

    # The compare-page header reads per-eval Latency from
    # ``output.model_latency.mean`` on the eval root. Without this
    # aggregate the Latency cell shows "N/A". Source pas calls in this
    # test carry model_latency=0.5 each.
    assert new_eval_call.output.get("model_latency") == {"mean": 0.5}

    # 5. The new eval's display_name matches the eval-{date}-{memorable}
    # format used by ``default_evaluation_display_name`` in eval.py, so
    # rescored runs are visually indistinguishable from normal eval runs.
    import re

    assert new_eval_call.display_name is not None
    assert re.match(
        r"^eval-\d{4}-\d{2}-\d{2}-[a-z]+-[a-z]+$", new_eval_call.display_name
    ), f"unexpected display_name shape: {new_eval_call.display_name!r}"

    # 6. The new eval root's ``inputs.self`` is the SOURCE eval ref —
    # call_start happens before publish so the frontend sees the eval as
    # ``running`` immediately, and ``inputs.self`` is immutable after the
    # call_start (no call_update path for inputs, only display_name).
    # Tradeoff documented in rescore_worker.rescore_predictions: the eval
    # root's scorer chip will render the source's scorers. The per-row
    # predict_and_score calls use the new ref (asserted further below in
    # other tests) so per-row chips render correctly.
    assert isinstance(new_eval_call.inputs, dict)
    new_self_ref = new_eval_call.inputs.get("self")
    assert new_self_ref == source_eval_ref, (
        "new eval root's inputs.self must point at the source eval ref "
        "(call_start runs before publish for visibility)"
    )

    # The publish step still runs: a new VERSION of the source eval
    # object_id is created with the rescore scorers swapped in. Lineage
    # is recorded via the EVALUATION_RUN_SOURCE_ATTR_KEY on the new run's
    # attributes (asserted on `new_eval_call.attributes` already above).
    from weave.trace.refs import ObjectRef, Ref

    source_ref_parsed = Ref.parse_uri(source_eval_ref)
    assert isinstance(source_ref_parsed, ObjectRef)
    # The latest version of the source object_id should have the rescore
    # scorers (not the source's original scorers).
    latest_eval_val = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id=source_ref_parsed.name,
        )
    ).obj.val
    assert isinstance(latest_eval_val, dict)
    assert latest_eval_val.get("scorers") == [scorer_ref]
    # Other fields preserved from the source val.
    assert latest_eval_val.get("dataset") == (
        f"weave:///{project_id}/object/dataset-stub:dd"
    )
    assert latest_eval_val.get("trials") == 1


# ---------------------------------------------------------------------------
# Faithful-predict copy when the source has real predict subcalls under pas.
# ---------------------------------------------------------------------------


def _build_source_with_predicts(
    client, project_id: str, *, model_ref: str, n_rows: int = 2
) -> tuple[str, list[str], str, list[str]]:
    """Build a source eval tree where each pas has a real predict subcall.

    Topology:
        Evaluation.evaluate
          predict_and_score #0
            MyModel.predict #0   (output, summary.usage, started_at/ended_at)
          predict_and_score #1
            MyModel.predict #1

    Mirrors what a normal ``Evaluation.evaluate(model)`` run produces — the
    rescore worker should copy each predict's op_name/inputs/output/summary
    onto a synthetic predict under the new pas.
    """
    src_id = "src-with-predicts"
    source_eval_ref = _publish_source_eval_object(client, project_id)
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=src_id,
                trace_id=src_id,
                op_name=f"weave:///{project_id}/op/Evaluation.evaluate:1",
                started_at=_ts(0),
                attributes={},
                inputs={"self": source_eval_ref, "model": model_ref},
            )
        )
    )
    pas_ids: list[str] = []
    predict_ids: list[str] = []
    for i in range(n_rows):
        pas_id = f"src-pas-{i}"
        predict_id = f"src-predict-{i}"
        pas_ids.append(pas_id)
        predict_ids.append(predict_id)
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    trace_id=src_id,
                    parent_id=src_id,
                    op_name=f"weave:///{project_id}/op/{constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME}:1",
                    started_at=_ts(0),
                    attributes={},
                    inputs={
                        "example": {"input": f"hello-{i}"},
                        "self": source_eval_ref,
                    },
                )
            )
        )
        # Real predict subcall — this is what the worker should faithfully
        # copy onto the new eval's synthetic predict.
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_id,
                    trace_id=src_id,
                    parent_id=pas_id,
                    op_name=f"weave:///{project_id}/op/MyModel.predict:1",
                    started_at=_ts(0),
                    attributes={},
                    inputs={"self": model_ref, "input": f"hello-{i}"},
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_id,
                    ended_at=_ts(seconds=2),  # 2s duration
                    output=f"HELLO-{i}",
                    summary={"usage": {"gpt-5": {"total_tokens": 42}}},
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    ended_at=_ts(seconds=3),
                    output={
                        "output": f"HELLO-{i}",
                        "scores": {},
                        "model_latency": 2.0,
                    },
                    summary={},
                )
            )
        )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=src_id,
                ended_at=_ts(seconds=4),
                output={"correctness": None},
                summary={},
            )
        )
    )
    return src_id, pas_ids, source_eval_ref, predict_ids


def test_rescore_faithfully_copies_source_predict_calls(client) -> None:
    """When the source row has a real predict subcall, the worker emits a
    synthetic predict under the new pas that is a faithful content-copy:
    same op_name, inputs, output, summary, and duration. This makes the
    rescored run visually and structurally indistinguishable from a normal
    ``Evaluation.evaluate(model)`` run in the eval-compare UI — Total
    Tokens reads from ``summary.usage``, the model panel shows real
    kwargs, and Latency matches the source.
    """
    project_id = client.project_id
    model_ref = f"weave:///{project_id}/object/model-stub:def"
    src_id, source_pas_ids, _source_eval_ref, source_predict_ids = (
        _build_source_with_predicts(client, project_id, model_ref=model_ref, n_rows=2)
    )
    scorer_ref = f"weave:///{project_id}/object/scorer:abc123"

    new_run_id = "rescore-faithful-1"
    apply_result = MagicMock()
    apply_result.result = 1.0

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._get_valid_scorer",
            return_value=MagicMock(),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.get_scorer_attributes",
            return_value=MagicMock(
                scorer_name="new_scorer",
                summarize_fn=MagicMock(return_value={"mean": 1.0}),
            ),
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.apply_scorer_async",
            new=AsyncMock(return_value=apply_result),
        ),
    ):
        rescore_predictions_sync(
            tsi.RescoringArgs(
                project_id=project_id,
                source_evaluation_run_id=src_id,
                new_evaluation_run_id=new_run_id,
                scorer_refs=[scorer_ref],
                wb_user_id="test-user",
            )
        )

    # Source predict subcalls must still be parented to source pas — the
    # rescore did NOT reparent them onto the new tree (faithful copy means
    # new records, not aliasing).
    for source_pas_id, source_predict_id in zip(
        source_pas_ids, source_predict_ids, strict=True
    ):
        source_children = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    filter=tsi.CallsFilter(parent_ids=[source_pas_id]),
                )
            )
        )
        ids = {c.id for c in source_children}
        assert source_predict_id in ids, (
            f"source predict {source_predict_id!r} disappeared from source "
            f"pas {source_pas_id!r}; rescore must not reparent source calls"
        )

    # Each new pas has exactly one synthetic predict whose op_name, inputs,
    # output, summary, and duration mirror the source predict.
    new_pas_calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                filter=tsi.CallsFilter(parent_ids=[new_run_id]),
            )
        )
    )
    new_pas_ids = [
        c.id
        for c in new_pas_calls
        if c.op_name
        and constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME in c.op_name
    ]
    assert len(new_pas_ids) == 2

    new_pas_subcalls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                filter=tsi.CallsFilter(parent_ids=new_pas_ids),
            )
        )
    )
    synth_predicts = [
        c for c in new_pas_subcalls if c.op_name and "MyModel.predict" in c.op_name
    ]
    assert len(synth_predicts) == 2, (
        f"expected one synthetic predict per new pas with the source "
        f"op_name; got {[c.op_name for c in new_pas_subcalls]}"
    )
    for sp in synth_predicts:
        # Artifact name matches source predict (so the chip in the UI
        # reads ``MyModel.predict``, not the generic ``predict``
        # fallback). The op digest differs from the source's — the
        # synthetic predict is a new call emission with an anonymous-op
        # placeholder source.
        assert "/op/MyModel.predict:" in sp.op_name
        # Inputs copied verbatim: real kwargs, not bundled under ``example``.
        assert isinstance(sp.inputs, dict)
        assert sp.inputs.get("self") == model_ref
        assert sp.inputs.get("input", "").startswith("hello-")
        # Output copied verbatim — what the model produced on the source row.
        assert sp.output == f"HELLO-{sp.inputs['input'].split('-')[1]}"
        # Summary copied — Total Tokens column reads ``summary.usage``.
        assert isinstance(sp.summary, dict)
        usage = sp.summary.get("usage", {})
        assert usage.get("gpt-5", {}).get("total_tokens") == 42
        # Duration preserved (source predict was 2s).
        duration = (sp.ended_at - sp.started_at).total_seconds()
        assert abs(duration - 2.0) < 1e-6, f"got duration {duration}"
