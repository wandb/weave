import pytest

import weave
from tests.conftest import LATENCY_TOL
from weave import Dataset, Evaluation, Model
from weave.scorers import MultiTaskBinaryClassificationF1

dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]
dataset = Dataset(rows=dataset_rows)


expected_eval_result = {
    "model_output": {"mean": 9.5},
    "score_oldstyle": {"true_count": 1, "true_fraction": 0.5},
    "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
}


class EvalModel(Model):
    @weave.op
    async def predict(self, input) -> str:
        return eval(input)


@weave.op
def score_oldstyle(model_output, target):
    return model_output == target


@weave.op
def score_newstyle(output, target):
    return output == target


@weave.op
def example_to_model_input(example):
    return {"input": example["input"]}


@pytest.mark.asyncio
async def test_evaluate_callable_as_model(weave_active):
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_predict_can_receive_other_params(weave_active):
    @weave.op
    async def model_predict(input, target) -> str:
        return eval(input) + target

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    result = await evaluation.evaluate(model_predict)
    assert result == {
        "model_output": {"mean": 18.5},
        "score_oldstyle": {"true_count": 0, "true_fraction": 0.0},
        "model_latency": {
            "mean": pytest.approx(0, abs=LATENCY_TOL),
        },
    }


@pytest.mark.asyncio
async def test_can_preprocess_model_input(weave_active):
    @weave.op
    async def model_predict(x) -> str:
        return eval(x)

    @weave.op
    def preprocess(example):
        return {"x": example["input"]}

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
        preprocess_model_input=preprocess,
    )
    result = await evaluation.evaluate(model_predict)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_evaluate_model_with_scorers(weave_active):
    # EvalModel against a rows dataset: single oldstyle scorer, then both styles.
    model = EvalModel()

    oldstyle_only = Evaluation(dataset=dataset_rows, scorers=[score_oldstyle])
    result = await oldstyle_only.evaluate(model)
    assert result == expected_eval_result

    both = Evaluation(dataset=dataset_rows, scorers=[score_oldstyle, score_newstyle])
    result = await both.evaluate(model)
    assert result == {
        "model_output": {"mean": 9.5},
        "score_oldstyle": {"true_count": 1, "true_fraction": 0.5},
        "score_newstyle": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
    }


@pytest.mark.asyncio
async def test_evaluate_other_model_method_names():
    class EvalModel(Model):
        @weave.op
        async def infer(self, input) -> str:
            return eval(input)

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[score_oldstyle],
    )
    model = EvalModel()
    result = await evaluation.evaluate(model)
    assert result == expected_eval_result


@pytest.mark.asyncio
async def test_score_as_class(weave_active):
    # Scorer subclass: default summarize, then a custom summarize override.
    class MyScorerOldstyle(weave.Scorer):
        @weave.op
        def score(self, model_output, target):
            return model_output == target

    class MyScorerCustomSummarize(weave.Scorer):
        @weave.op
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        @weave.op
        def score(self, model_output, target):
            return model_output == target

    model = EvalModel()

    default_eval = Evaluation(dataset=dataset_rows, scorers=[MyScorerOldstyle()])
    result = await default_eval.evaluate(model)
    assert result == {
        "model_output": {"mean": 9.5},
        "MyScorerOldstyle": {"true_count": 1, "true_fraction": 0.5},
        "model_latency": {
            "mean": pytest.approx(0, abs=LATENCY_TOL),
        },
    }

    custom_eval = Evaluation(
        dataset=dataset_rows, scorers=[MyScorerCustomSummarize()]
    )
    result = await custom_eval.evaluate(model)
    assert result == {
        "model_output": {"mean": 9.5},
        "MyScorerCustomSummarize": {"awesome": 3},
        "model_latency": {
            "mean": pytest.approx(0, abs=LATENCY_TOL),
        },
    }


@pytest.mark.asyncio
async def test_multiclass_f1_score(weave_active):
    evaluation = Evaluation(
        dataset=[{"target": {"a": False, "b": True}, "pred": {"a": True, "b": False}}],
        scorers=[MultiTaskBinaryClassificationF1(class_names=["a", "b"])],
    )

    @weave.op
    def return_pred(pred):
        return pred

    result = await evaluation.evaluate(return_pred)
    assert result == {
        "model_output": {
            "a": {"true_count": 1, "true_fraction": 1.0},
            "b": {"true_count": 0, "true_fraction": 0.0},
        },
        "MultiTaskBinaryClassificationF1": {
            "a": {"f1": 0, "precision": 0.0, "recall": 0},
            "b": {"f1": 0, "precision": 0, "recall": 0.0},
        },
        "model_latency": {
            "mean": pytest.approx(0, abs=LATENCY_TOL),
        },
    }
