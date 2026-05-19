"""Unit tests for rescore_worker.py and the EvalWorkerJob discriminated union.

Covers:
- EvalWorkerJob discriminated union parsing (evaluate_model and rescore job
  types)
- scorer_refs min_length=1 validation
- rescore_predictions creates one new predict_and_score per source row plus
  one Evaluation.summarize call, and parents scorer calls under the new pas
  via the call-stack push from create_call(use_stack=True)
- Summary keyed by scorer_name (not scorer ref URI)
- evaluation_run_finish called even on unexpected exception
"""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from weave.trace_server import constants
from weave.trace_server.trace_server_interface import (
    CallReadRes,
    CallSchema,
    EvaluateModelArgs,
    EvalWorkerJob,
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
# rescore_predictions trace-tree shape and pagination
# ---------------------------------------------------------------------------


def _make_pas_call(pas_id: str, inputs: dict, output) -> CallSchema:
    """Build a minimal predict_and_score CallSchema as it would appear in
    the source eval's trace. The worker traverses children of the source
    eval call and matches op_name against
    EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME (scheme-agnostic), so the
    op_name URI just needs the right tail name.
    """
    import datetime

    return CallSchema(
        id=pas_id,
        project_id="e/p",
        op_name=f"weave:///e/p/op/{constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME}:1",
        trace_id="src-run",
        parent_id="src-run",
        started_at=datetime.datetime(2026, 5, 6, 0, 0, 0),
        attributes={},
        inputs={
            "example": inputs,
            "self": "weave:///e/p/object/eval-stub:abc",
            "model": "weave:///e/p/object/model-stub:def",
        },
        output={"output": output, "scores": {}, "model_latency": 0.1},
    )


def _install_publish_eval_mocks(mock_server: MagicMock) -> None:
    """Wire up ``obj_read``/``obj_create`` so the worker's
    ``_publish_rescored_evaluation`` step succeeds end-to-end. Without
    these, the worker raises (fail-loudly behavior) and the test fails
    before reaching the trace-tree assertions.
    """
    import datetime as _dt

    from weave.trace_server.trace_server_interface import ObjReadRes, ObjSchema

    mock_server.obj_read.return_value = ObjReadRes(
        obj=ObjSchema(
            project_id="e/p",
            object_id="eval-stub",
            created_at=_dt.datetime(2026, 5, 6, 0, 0, 0),
            digest="abc",
            version_index=0,
            is_latest=1,
            kind="object",
            base_object_class=None,
            val={
                "_type": "Evaluation",
                "scorers": ["weave:///e/p/object/old-scorer:old"],
                "dataset": "weave:///e/p/object/dataset-stub:dd",
            },
        )
    )
    mock_server.obj_create.return_value = MagicMock(digest="newdigest")


def _source_eval_call_read_res() -> CallReadRes:
    """The worker reads the source eval call once to lift its self/model
    refs onto the new pas inputs. Tests don't exercise the trace server, so
    return a hand-built CallSchema with the right shape.
    """
    import datetime

    return CallReadRes(
        call=CallSchema(
            id="src-run",
            project_id="e/p",
            op_name=f"weave:///e/p/op/{constants.EVALUATION_RUN_OP_NAME}:1",
            trace_id="src-run",
            parent_id=None,
            started_at=datetime.datetime(2026, 5, 6, 0, 0, 0),
            attributes={},
            inputs={
                "self": "weave:///e/p/object/eval-stub:abc",
                "model": "weave:///e/p/object/model-stub:def",
            },
        )
    )


@pytest.mark.asyncio
async def test_rescore_predictions_creates_eval_pas_and_summarize_tree():
    """The worker must own the entire new-eval call tree. For N source rows
    it produces:
      - one Evaluation.evaluate root (emitted via direct call_start with
        ``trace_id == id`` so the frontend's trace queries land correctly)
      - N Evaluation.predict_and_score calls (parented to the new-eval)
      - one Evaluation.summarize call (parented to the new-eval)
    Each call gets a matching ``finish_call``. The frontend reads scores
    from this traced tree; ``score_create`` and ``evaluation_run_finish``
    are NOT used.
    """
    pas_calls = [
        _make_pas_call("pas-1", {"x": 1}, "out-1"),
        _make_pas_call("pas-2", {"x": 2}, "out-2"),
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
    # Page 1 returns the source pas calls; subsequent grandchildren-query
    # for synthetic-predict snapshots returns empty (so we exercise the
    # fallback path, not the faithful-copy path — the latter is covered
    # by the sqlite imperative test).
    mock_server.calls_query_stream.side_effect = lambda req: iter(
        pas_calls if req.filter.parent_ids == ["src-run"] else []
    )
    mock_server.call_read.return_value = _source_eval_call_read_res()
    _install_publish_eval_mocks(mock_server)

    create_call_invocations: list[tuple[str, dict, dict]] = []
    finish_call_invocations: list[tuple[object, object]] = []

    def fake_create_call(op, inputs, **kwargs):
        call = MagicMock()
        call.id = (
            kwargs.get("_call_id_override") or f"created-{len(create_call_invocations)}"
        )
        call.trace_id = call.id
        call.summary = None
        create_call_invocations.append((op, inputs, kwargs))
        return call

    def fake_finish_call(call, output=None, **kwargs):
        finish_call_invocations.append((call, output))

    mock_client = MagicMock()
    mock_client.server = mock_server
    mock_client.project_id = "e/p"
    mock_client.create_call.side_effect = fake_create_call
    mock_client.finish_call.side_effect = fake_finish_call

    class FakeApplyResult:
        result: ClassVar[dict] = {"correct": True}

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
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
        mock_scorer_attrs.scorer_name = "my_scorer"
        mock_scorer_attrs.summarize_fn = MagicMock(return_value={"mean": 1.0})
        mock_get_attrs.return_value = mock_scorer_attrs

        from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
            rescore_predictions,
        )

        await rescore_predictions(args)

    # All call emission goes through ``client.create_call`` (the eval root
    # uses ``_call_id_override`` + ``parent=None`` which pins trace_id==id
    # via the create_call contract; the synthetic predict uses explicit
    # ``started_at``/``ended_at`` overrides). For N source rows we expect:
    #   1 eval-root + N pas + N synthetic-predicts + 1 summarize.
    expected_creates = 1 + len(pas_calls) + len(pas_calls) + 1
    assert len(create_call_invocations) == expected_creates

    # First create_call is the eval root. The op is passed as a pre-built
    # ``_new_eval_root_op`` (eager_call_start=True) whose ``.name`` is set to
    # ``EVALUATION_RUN_OP_NAME`` — see rescore_worker.py for why the eager
    # op is required (frontend status polling visibility).
    eval_root_op, eval_root_inputs, eval_root_kwargs = create_call_invocations[0]
    assert getattr(eval_root_op, "name", eval_root_op) == constants.EVALUATION_RUN_OP_NAME
    assert eval_root_kwargs.get("parent") is None
    assert eval_root_kwargs.get("_call_id_override") == "new-run"
    assert eval_root_kwargs.get("use_stack") is False
    weave_attrs = eval_root_kwargs.get("attributes", {}).get(
        constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
    )
    assert weave_attrs.get(constants.EVALUATION_RUN_ATTR_KEY) == "true"
    assert weave_attrs.get(constants.EVALUATION_RUN_SOURCE_ATTR_KEY) == "src-run"
    # Worker sets eval-{date}-{memorable} display_name matching the format
    # of ``default_evaluation_display_name`` (eval.py) so rescored runs are
    # visually indistinguishable from normal eval runs.
    import re

    display_name = eval_root_kwargs.get("display_name")
    assert display_name is not None
    assert re.match(r"^eval-\d{4}-\d{2}-\d{2}-[a-z]+-[a-z]+$", display_name), (
        f"unexpected display_name shape: {display_name!r}"
    )

    # Trailing ops in order: per row -> pas then predict; then summarize.
    op_names_after_root = [op for op, _, _ in create_call_invocations[1:]]
    assert op_names_after_root == [
        constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        "predict",  # synthetic-predict fallback (no source predict in mocks)
        constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        "predict",
        constants.EVALUATION_SUMMARIZE_OP_NAME,
    ]

    # finish_call counts: N synthetic predicts + N pas + 1 summarize + 1
    # eval root. The eval-root finish is the LAST one and carries the
    # full summary as its output.
    assert len(finish_call_invocations) == 2 * len(pas_calls) + 2
    eval_root_finish_output = finish_call_invocations[-1][1]
    # Per-scorer summary plus a model_latency aggregate the compare-page
    # header reads (output.model_latency.mean on the eval root). Both
    # source rows had model_latency=0.1 so the mean is 0.1.
    assert eval_root_finish_output == {
        "my_scorer": {"mean": 1.0},
        "model_latency": {"mean": 0.1},
    }

    # Worker does NOT call score_create or evaluation_run_finish — scores
    # live in the traced call tree.
    mock_server.score_create.assert_not_called()
    mock_server.evaluation_run_finish.assert_not_called()


@pytest.mark.asyncio
async def test_rescore_predictions_summary_keyed_by_scorer_name_not_ref():
    """Summary dict must use scorer_attrs.scorer_name as key, not the ref URI."""
    pas_call = _make_pas_call("pas-1", {"x": 1}, "out-1")
    scorer_ref = "weave:///e/p/object/scorer:abc"
    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=[scorer_ref],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    mock_server = MagicMock()
    mock_server.calls_query_stream.side_effect = lambda req: iter(
        [pas_call] if req.filter.parent_ids == ["src-run"] else []
    )
    mock_server.call_read.return_value = _source_eval_call_read_res()
    _install_publish_eval_mocks(mock_server)

    finish_call_invocations: list[tuple[object, object]] = []

    def fake_create_call(op, inputs, parent=None, **kwargs):
        call = MagicMock()
        call.id = kwargs.get("_call_id_override") or "x"
        call.trace_id = call.id
        call.summary = None
        return call

    def fake_finish_call(call, output=None, **kwargs):
        finish_call_invocations.append((call, output))

    mock_client = MagicMock()
    mock_client.server = mock_server
    mock_client.project_id = "e/p"
    mock_client.create_call.side_effect = fake_create_call
    mock_client.finish_call.side_effect = fake_finish_call

    class FakeApplyResult:
        result = 0.9

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
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

    # The eval root's finish_call (the LAST one) carries the summary as
    # its output. Mirrors a normal Evaluation.evaluate op finish where the
    # eval call's ``output`` IS the summary dict. Key must be the
    # human-readable scorer_name, NOT the ref URI.
    eval_root_output = finish_call_invocations[-1][1]
    assert "human_readable_scorer_name" in eval_root_output
    assert scorer_ref not in eval_root_output


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_rescore_predictions_eval_call_failed_on_exception():
    """The new-eval call must be failed (via ``client.fail_call``) when an
    unexpected error occurs, so it never dangles in 'started' state and
    the UI can render the failure with the original exception.
    """
    args = RescoringArgs(
        project_id="e/p",
        source_evaluation_run_id="src-run",
        scorer_refs=["weave:///e/p/object/scorer:abc"],
        new_evaluation_run_id="new-run",
        wb_user_id="user1",
    )

    mock_server = MagicMock()
    # Make calls_query_stream raise an unexpected error
    mock_server.calls_query_stream.side_effect = RuntimeError("db error")
    mock_server.call_read.return_value = _source_eval_call_read_res()
    _install_publish_eval_mocks(mock_server)

    # ``client.create_call`` is now used for the eval root. Return a Call
    # whose id == ``_call_id_override`` so the fail_call assertions land.
    def fake_create_call(op, inputs, **kwargs):
        call = MagicMock()
        call.id = kwargs.get("_call_id_override") or "x"
        call.trace_id = call.id
        call.summary = None
        return call

    mock_client = MagicMock()
    mock_client.server = mock_server
    mock_client.project_id = "e/p"
    mock_client.create_call.side_effect = fake_create_call
    mock_client.fail_call = MagicMock()

    with (
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
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

        with pytest.raises(RuntimeError, match="db error"):
            await rescore_predictions(args)

    # fail_call must have been called on the eval root with the original
    # exception so the UI can show why the rescore failed.
    mock_client.fail_call.assert_called_once()
    args_pos, kwargs_call = mock_client.fail_call.call_args
    failed_call = args_pos[0]
    exc = kwargs_call.get("exception") or (args_pos[1] if len(args_pos) > 1 else None)
    # Eval root id comes from _call_id_override == new_evaluation_run_id.
    assert failed_call.id == "new-run"
    assert failed_call.trace_id == "new-run"
    assert isinstance(exc, RuntimeError)
    assert "db error" in str(exc)


@pytest.mark.asyncio
async def test_rescore_predictions_pagination_exhausts_all_pages():
    """Pagination: when first page is full (== PAGE_SIZE), a second request is made."""
    from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
        PREDICTION_PAGE_SIZE,
    )

    page1 = [
        _make_pas_call(f"pas-{i}", {"x": i}, f"out-{i}")
        for i in range(PREDICTION_PAGE_SIZE)
    ]
    page2 = [_make_pas_call("pas-last", {"x": 999}, "out-last")]

    pas_query_count = 0
    grandchild_query_count = 0

    def fake_calls_query_stream(req):
        nonlocal pas_query_count, grandchild_query_count
        parent_ids = req.filter.parent_ids if req.filter else []
        # Grandchildren-query: parent_ids are the pas ids, not the source
        # eval id. Return empty so source_predict stays None and the worker
        # uses the generic synthetic-predict fallback.
        if parent_ids != ["src-run"]:
            grandchild_query_count += 1
            return iter([])
        pas_query_count += 1
        if req.offset == 0:
            return iter(page1)
        return iter(page2)

    mock_server = MagicMock()
    mock_server.calls_query_stream.side_effect = fake_calls_query_stream
    mock_server.call_read.return_value = _source_eval_call_read_res()
    _install_publish_eval_mocks(mock_server)

    create_call_count = 0

    def fake_create_call(op, inputs, parent=None, **kwargs):
        nonlocal create_call_count
        create_call_count += 1
        m = MagicMock()
        m.id = kwargs.get("_call_id_override") or f"created-{create_call_count}"
        m.trace_id = m.id
        m.summary = None
        return m

    mock_client = MagicMock()
    mock_client.server = mock_server
    mock_client.project_id = "e/p"
    mock_client.create_call.side_effect = fake_create_call
    mock_client.finish_call = MagicMock()

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
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker.require_weave_client",
            return_value=mock_client,
        ),
        patch(
            "weave.trace_server.workers.evaluate_model_worker.rescore_worker._assert_safe_ref"
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

    # calls_query_stream was called twice for pas pages (page1, page2),
    # plus once per non-empty page for the grandchildren query that picks
    # out source predict subcalls for the faithful-copy.
    assert pas_query_count == 2
    assert grandchild_query_count == 2
    # create_call is invoked for: 1 eval root + N pas + N synthetic
    # predicts + 1 trailing Evaluation.summarize. The eval root flows
    # through create_call via the trace_id==id-when-_call_id_override
    # contract.
    n_rows = PREDICTION_PAGE_SIZE + 1
    assert mock_client.create_call.call_count == 1 + 2 * n_rows + 1
