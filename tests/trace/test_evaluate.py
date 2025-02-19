import asyncio
import time

import pytest

import weave
from weave import Dataset, Evaluation, Model

dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]
dataset = Dataset(rows=dataset_rows)


expected_eval_result = {
    "output": {"mean": 9.5},
    "score": {"true_count": 1, "true_fraction": 0.5},
    "model_latency": {"mean": pytest.approx(0, abs=1)},
}


class EvalModel(Model):
    @weave.op()
    async def predict(self, input) -> str:
        return eval(input)


@weave.op()
def score(target, output):
    return target == output


@weave.op()
def example_to_model_input(example):
    return {"input": example["input"]}


def test_evaluate_callable_as_model(client):
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    assert result == expected_eval_result


def test_predict_can_receive_other_params(client):
    @weave.op()
    async def model_predict(input, target) -> str:
        return eval(input) + target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    assert result == {
        "output": {"mean": 18.5},
        "score": {"true_count": 0, "true_fraction": 0.0},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


def test_can_preprocess_model_input(client):
    @weave.op()
    async def model_predict(x) -> str:
        return eval(x)

    @weave.op()
    def preprocess(example):
        return {"x": example["input"]}

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
        preprocess_model_input=preprocess,
    )
    result = asyncio.run(evaluation.evaluate(model_predict))
    assert result == expected_eval_result


def test_evaluate_rows_only(client):
    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == expected_eval_result


def test_evaluate_other_model_method_names():
    class EvalModel(Model):
        @weave.op()
        async def infer(self, input) -> str:
            return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == expected_eval_result


def test_score_as_class(client):
    class MyScorer(weave.Scorer):
        @weave.op()
        def score(self, target, output):
            return target == output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == {
        "output": {"mean": 9.5},
        "MyScorer": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


def test_score_with_custom_summarize(client):
    class MyScorer(weave.Scorer):
        @weave.op()
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        @weave.op()
        def score(self, target, output):
            return target == output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == {
        "output": {"mean": 9.5},
        "MyScorer": {"awesome": 3},
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scorers,expected_output_key",
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
    assert result.pop("model_latency").get("mean") == pytest.approx(0, abs=1)

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
    assert all(o.pop("model_latency") == pytest.approx(0, abs=1) for o in outputs)

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
def test_scorer_name_sanitization(scorer_name):
    class MyScorer(weave.Scorer):
        name: str

        @weave.op()
        def score(self, target, model_output):
            return target == model_output

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer(name=scorer_name)],
    )
    model = EvalModel()

    result = asyncio.run(evaluation.evaluate(model))
    assert result["my-scorer"] == {"true_count": 1, "true_fraction": 0.5}


def test_sync_eval_parallelism(client):
    @weave.op()
    def sync_op(a):
        time.sleep(1)
        return a

    @weave.op()
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

    # 10 rows, should complete in <5 seconds. if sync, 10+

    now = time.time()

    evaluation = Evaluation(dataset=dataset, scorers=[score])
    result = asyncio.run(evaluation.evaluate(sync_op))
    assert result == {
        "output": {"mean": 5.5},
        "score": {"mean": 1.0},
        "model_latency": {"mean": pytest.approx(1, abs=1)},
    }
    assert time.time() - now < 5


def test_evaluate_table_lazy_iter(client):
    """
    The intention of this test is to show that an evaluation harness
    lazily fetches rows from a table rather than eagerly fetching all
    rows up front.
    """
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    ref = weave.publish(dataset)
    dataset = ref.get()

    @weave.op()
    async def model_predict(input) -> int:
        return input * 1

    @weave.op()
    def score_simple(input, output):
        return input == output

    log = client.server.attribute_access_log
    assert [l for l in log if not l.startswith("_")] == [
        "ensure_project_exists",
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

    result = asyncio.run(evaluation.evaluate(model_predict))
    assert result["output"] == {"mean": 149.5}
    assert result["score_simple"] == {"true_count": 300, "true_fraction": 1.0}

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
    assert counts_split_by_table_query == [
        counts_split_by_table_query[0],
        700,
        700,
        700,
        5,
    ], log
