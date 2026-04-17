import os
import sys
import time
from unittest.mock import patch

import pytest
from pydantic import BaseModel

import weave
from tests.conftest import LATENCY_TOL
from weave import Dataset, Evaluation, Model
from weave.trace_server import trace_server_interface as tsi

dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]
dataset = Dataset(rows=dataset_rows)


expected_eval_result = {
    "output": {"mean": 9.5},
    "score": {"true_count": 1, "true_fraction": 0.5},
    "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
}


class EvalModel(Model):
    @weave.op
    async def predict(self, input) -> str:
        return eval(input)


@weave.op
def score(target, output):
    return target == output


@weave.op
def example_to_model_input(example):
    return {"input": example["input"]}


@pytest.mark.asyncio
async def test_evaluate_callable_as_model(client):
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_predict_can_receive_other_params(client):
    @weave.op
    async def model_predict(input, target) -> str:
        return eval(input) + target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == {
        "output": {"mean": 18.5},
        "score": {"true_count": 0, "true_fraction": 0.0},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
async def test_can_preprocess_model_input(client):
    @weave.op
    async def model_predict(x) -> str:
        return eval(x)

    @weave.op
    def preprocess(example):
        return {"x": example["input"]}

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
        preprocess_model_input=preprocess,
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_rows_only(client):
    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_other_model_method_names():
    class EvalModel(Model):
        @weave.op
        async def infer(self, input) -> str:
            return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_score_as_class(client):
    class MyScorer(weave.Scorer):
        @weave.op
        def score(self, target, output):
            return target == output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == {
        "output": {"mean": 9.5},
        "MyScorer": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
async def test_score_with_custom_summarize(client):
    class MyScorer(weave.Scorer):
        @weave.op
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        @weave.op
        def score(self, target, output):
            return target == output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == {
        "output": {"mean": 9.5},
        "MyScorer": {"awesome": 3},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scorers", "expected_output_key"),
    [
        # All scorer styles
        (
            ["fn_old", "fn_new", "class_old", "class_new"],
            "model_output",
        ),
        # Only old class style
        (
            ["fn_new", "class_old", "class_new"],
            "model_output",
        ),
        # Only old fn style
        (
            ["fn_old", "fn_new", "class_new"],
            "model_output",
        ),
        # Only new styles
        (
            ["fn_new", "class_new"],
            "output",
        ),
    ],
)
async def test_basic_evaluation_with_scorer_styles(
    client, scorers, expected_output_key
):
    # Define all possible scorers
    @weave.op
    def fn_scorer_with_old_style(col_a, col_b, model_output, target):
        return col_a + col_b == model_output == target

    @weave.op
    def fn_scorer_with_new_style(col_a, col_b, output, target):
        return col_a + col_b == output == target

    class ClassScorerWithOldStyle(weave.Scorer):
        @weave.op
        def score(self, col_a, col_b, model_output, target):
            return col_a + col_b == model_output == target

    class ClassScorerWithNewStyle(weave.Scorer):
        @weave.op
        def score(self, a, b, output, c):
            return a + b == output == c

    # Map scorer keys to actual scorer instances
    scorer_map = {
        "fn_old": fn_scorer_with_old_style,
        "fn_new": fn_scorer_with_new_style,
        "class_old": ClassScorerWithOldStyle(),
        "class_new": ClassScorerWithNewStyle(
            column_map={
                "a": "col_a",
                "b": "col_b",
                "c": "target",
            }
        ),
    }

    dataset = [
        {"col_a": 1, "col_b": 2, "target": 3},
        {"col_a": 1, "col_b": 2, "target": 3},
        {"col_a": 1, "col_b": 2, "target": 3},
    ]

    # Get actual scorer instances based on parameter
    actual_scorers = [scorer_map[s] for s in scorers]

    evaluation = Evaluation(
        dataset=dataset,
        scorers=actual_scorers,
    )

    @weave.op
    def model(col_a, col_b):
        return col_a + col_b

    result = await evaluation.evaluate(model)
    assert result.pop("model_latency").get("mean") == pytest.approx(0, abs=LATENCY_TOL)

    # Build expected result dynamically
    expected_result = {
        expected_output_key: {"mean": 3.0},
    }
    scorer_results = {
        "fn_old": "fn_scorer_with_old_style",
        "fn_new": "fn_scorer_with_new_style",
        "class_old": "ClassScorerWithOldStyle",
        "class_new": "ClassScorerWithNewStyle",
    }
    for s in scorers:
        expected_result[scorer_results[s]] = {"true_count": 3, "true_fraction": 1.0}

    assert result == expected_result

    # Verify individual prediction outputs
    predict_and_score_calls = list(evaluation.predict_and_score.calls())
    assert len(predict_and_score_calls) == 3
    outputs = [c.output for c in predict_and_score_calls]
    # Pop model_latency before structural comparison; value already checked in summary
    for o in outputs:
        o.pop("model_latency")

    # Build expected output dynamically
    expected_output = {
        expected_output_key: 3.0,
        "scores": {scorer_results[s]: True for s in scorers},
    }
    assert all(o == expected_output for o in outputs)


@pytest.mark.parametrize(
    "scorer_name",
    ["my scorer", "my-scorer()*&^%$@#/", "my-scorer", "       my scorer     "],
)
@pytest.mark.asyncio
async def test_scorer_name_sanitization(scorer_name):
    class MyScorer(weave.Scorer):
        name: str

        @weave.op
        def score(self, target, model_output):
            return target == model_output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer(name=scorer_name)],
    )
    model = EvalModel()

    result = await evaluation.evaluate(model)
    assert result["my-scorer"] == {"true_count": 1, "true_fraction": 0.5}


@pytest.mark.asyncio
async def test_sync_eval_parallelism(client):
    @weave.op
    def sync_op(a):
        time.sleep(1)
        return a

    @weave.op
    def score(output):
        return 1

    dataset = [
        {"a": 1},
        {"a": 2},
        {"a": 3},
        {"a": 4},
        {"a": 5},
        {"a": 6},
        {"a": 7},
        {"a": 8},
        {"a": 9},
        {"a": 10},
    ]

    # 10 rows, should complete in <8 seconds. if sync, 10+

    now = time.time()

    evaluation = Evaluation(dataset=dataset, scorers=[score])
    result = await evaluation.evaluate(sync_op)
    assert result == {
        "output": {"mean": 5.5},
        "score": {"mean": 1.0},
        "model_latency": {"mean": pytest.approx(1, abs=LATENCY_TOL)},
    }
    assert time.time() - now < (15 if sys.platform == "win32" else 8)


@pytest.mark.asyncio
async def test_evaluation_from_weaveobject_missing_evaluation_name(client):
    dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]
    dataset = Dataset(rows=dataset_rows)

    class EvalModel(Model):
        @weave.op
        async def predict(self, input) -> str:
            return eval(input)

    @weave.op
    def score(target, output):
        return target == output

    # Create and save an Evaluation object
    evaluation = Evaluation(
        dataset=dataset,
        scorers=[score],
        name="test-eval",
    )
    ref = weave.publish(evaluation)

    # To simulate it being an older object, we delete the evaluation_name attribute from
    # the gotten weave object.
    eval_obj = ref.get(objectify=False)
    del eval_obj._val.evaluation_name

    # We should still be able to load the Evaluation object even if this attr doesn't exist
    # and it should continue to work and produce expected results
    evaluation = Evaluation.from_obj(eval_obj)
    model = EvalModel()

    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_table_lazy_iter(client, monkeypatch):
    """The intention of this test is to show that an evaluation harness
    lazily fetches rows from a table rather than eagerly fetching all
    rows up front.
    """
    monkeypatch.setattr(weave.trace.vals, "REMOTE_ITER_PAGE_SIZE", 4)

    dataset = Dataset(rows=[{"input": i} for i in range(10)])
    ref = weave.publish(dataset)
    dataset = ref.get()

    @weave.op
    async def model_predict(input) -> int:
        return input * 1

    @weave.op
    def score_simple(input, output):
        return input == output

    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == [
        "get_call_processor",
        "get_call_processor",
        "get_feedback_processor",
        "get_feedback_processor",
        "table_create",
        "obj_create",
        "obj_read",
    ]
    client.server.attribute_access_log = []

    evaluation = Evaluation(
        dataset=dataset,
        scorers=[score_simple],
    )
    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == []

    # Make sure we have deterministic results
    with patch.dict(os.environ, {"WEAVE_PARALLELISM": "1"}):
        result = await evaluation.evaluate(model_predict)
        assert result["output"] == {"mean": 4.5}
        assert result["score_simple"] == {"true_count": 10, "true_fraction": 1.0}

    log = client.server.attribute_access_log
    log = [l for l in log if not l.startswith("_")]

    # Make sure that the length was figured out deterministically
    assert "table_query_stats" in log

    counts_split_by_table_query = [0]
    for log_entry in log:
        if log_entry == "table_query":
            counts_split_by_table_query.append(0)
        else:
            counts_split_by_table_query[-1] += 1

    # Note: these exact numbers might change if we change the way eval traces work.
    # However, the key part is that we have basically X + 2 splits, with the middle X
    # being equal. We want to ensure that the table_query is not called in sequence,
    # but rather lazily after each batch.
    assert counts_split_by_table_query[0] <= 13
    # Note: if this test suite is ran in a different order, then the low level eval ops will already be saved
    # so the first count can be different.
    count = counts_split_by_table_query[0]
    assert counts_split_by_table_query == [count, 28, 28, 14 + 5], log


@pytest.mark.asyncio
async def test_evaluate_table_order(client):
    """Test that evaluation results maintain the original order of the dataset
    when using a published dataset with images.
    """
    import random

    from PIL import Image

    def make_image(i):
        return Image.new(
            "RGB",
            (64, 64),
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        )

    # Create a dataset with ordered values
    dataset_rows = [{"input": i, "target": i, "image": make_image(i)} for i in range(5)]
    dataset = Dataset(rows=dataset_rows)
    ref = weave.publish(dataset)
    dataset = ref.get()

    @weave.op
    async def model_predict(input) -> int:
        return input

    @weave.op
    def score_simple(input, output, target):
        return input == output == target

    evaluation = Evaluation(
        dataset=dataset,
        scorers=[score_simple],
    )

    # Get all prediction and score calls to verify order
    result = await evaluation.evaluate(model_predict)

    # Verify the overall results
    assert result["output"] == {"mean": 2}  # Average of 0-99
    assert result["score_simple"] == {"true_count": 5, "true_fraction": 1.0}

    # Get all prediction calls and verify order
    predict_and_score_calls = list(evaluation.predict_and_score.calls())
    assert len(predict_and_score_calls) == 5

    # Extract inputs and outputs to verify order
    inputs = [c.inputs["example"]["input"] for c in predict_and_score_calls]
    outputs = [c.output["output"] for c in predict_and_score_calls]

    # Verify inputs and outputs are in order 0-99
    assert inputs == list(range(5))
    assert outputs == list(range(5))

    # Verify scores are all True and in order
    scores = [c.output["scores"]["score_simple"] for c in predict_and_score_calls]
    assert all(scores)
    assert len(scores) == 5


@pytest.mark.asyncio
async def test_evaluate_with_pydantic_summary(client):
    class MyScorerSummary(BaseModel):
        awesome: int

    class MyScorer(weave.Scorer):
        @weave.op
        def score(self, target, output):
            return target == output

        @weave.op
        def summarize(self, score_rows):
            return MyScorerSummary(awesome=3)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result["MyScorer"].awesome == 3


async def _assert_post_hoc_score_appears(client, evaluation, model_predict):
    """Shared assertion logic: run eval, add post-hoc scores, verify visibility."""
    project_id = client.project_id

    _, eval_call = await evaluation.evaluate.call(evaluation, model_predict)
    eval_call_id = eval_call.id

    predict_call_ids = client.get_eval_predict_call_ids(eval_call_id)
    assert len(predict_call_ids) == 2

    # Create a new scorer and add post-hoc scores
    scorer_res = client.server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="post_hoc_scorer",
            op_source_code="def score(output):\n    return 1.0",
        )
    )

    for predict_call_id in predict_call_ids:
        client.server.score_create(
            tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=predict_call_id,
                scorer=scorer_res.scorer,
                value=0.42,
                evaluation_run_id=eval_call_id,
            )
        )

    res = client.server.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[eval_call_id],
            include_summary=True,
        )
    )

    assert res.total_rows == 2
    for row in res.rows:
        trial = row.evaluations[0].trials[0]
        assert "post_hoc_scorer" in trial.scores
        assert trial.scores["post_hoc_scorer"] == 0.42

    assert res.summary is not None
    scorer_keys = {s.scorer_key for s in res.summary.evaluations[0].scorer_stats}
    assert "post_hoc_scorer" in scorer_keys


@pytest.mark.asyncio
async def test_post_hoc_score_appears_in_eval_results(client):
    """After running a normal Evaluation (function scorer), adding a score
    via score_create() should be picked up by eval_results_query rollups.
    """

    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    @weave.op
    def original_scorer(target, output):
        return target == output

    evaluation = Evaluation(
        dataset=[{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 16}],
        scorers=[original_scorer],
    )
    await _assert_post_hoc_score_appears(client, evaluation, model_predict)


@pytest.mark.asyncio
async def test_post_hoc_score_appears_in_eval_results_with_class_scorer(client):
    """Same as above but using a weave.Scorer subclass as the original scorer."""

    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    class MyScorer(weave.Scorer):
        @weave.op
        def score(self, target, output):
            return target == output

    evaluation = Evaluation(
        dataset=[{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 16}],
        scorers=[MyScorer()],
    )
    await _assert_post_hoc_score_appears(client, evaluation, model_predict)
