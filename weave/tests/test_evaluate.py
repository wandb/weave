import asyncio
import pytest
import weave
from weave import ref_base
from weave.flow.scorer import MultiTaskBinaryClassificationF1
from weave import Dataset, Model, Evaluation

pytestmark = pytest.mark.webtest


dataset_rows = [{"input": "1 + 2", "target": 3}, {"input": "2**4", "target": 15}]
dataset = Dataset(rows=dataset_rows)

expected_eval_result = {
    "prediction": {"mean": 9.5},
    "score": {"true_count": 1, "true_fraction": 0.5},
}


class EvalModel(Model):
    @weave.op()
    async def predict(self, input) -> str:
        return eval(input)


@weave.op()
def score(target, prediction):
    return target == prediction


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
        "prediction": {"mean": 18.5},
        "score": {"true_count": 0, "true_fraction": 0.0},
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


def test_evaluate_other_model_method_names(eager_mode):
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
        def score(self, target, prediction):
            return target == prediction

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == {
        "prediction": {"mean": 9.5},
        "MyScorer": {"true_count": 1, "true_fraction": 0.5},
    }


def test_score_with_custom_summarize(client):
    class MyScorer(weave.Scorer):
        @weave.op()
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        @weave.op()
        def score(self, target, prediction):
            return target == prediction

    evaluation = Evaluation(
        dataset=dataset_rows,
        scorers=[MyScorer()],
    )
    model = EvalModel()
    result = asyncio.run(evaluation.evaluate(model))
    assert result == {
        "prediction": {"mean": 9.5},
        "MyScorer": {"awesome": 3},
    }


def test_multiclass_f1_score(client):
    evaluation = Evaluation(
        dataset=[{"target": {"a": False, "b": True}, "pred": {"a": True, "b": False}}],
        scorers=[MultiTaskBinaryClassificationF1(class_names=["a", "b"])],
    )

    @weave.op()
    def return_pred(pred):
        return pred

    result = asyncio.run(evaluation.evaluate(return_pred))
    assert result == {
        "prediction": {
            "a": {"true_count": 1, "true_fraction": 1.0},
            "b": {"true_count": 0, "true_fraction": 0.0},
        },
        "MultiTaskBinaryClassificationF1": {
            "a": {"f1": 0, "precision": 0.0, "recall": 0},
            "b": {"f1": 0, "precision": 0, "recall": 0.0},
        },
    }
