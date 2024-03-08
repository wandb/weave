import asyncio
import pytest
import weave
from weave import ref_base
from weave.flow.scorer import MulticlassF1Score
from weave import Dataset, Model, Evaluation

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


def test_evaluate_basic():
    with weave.local_client():

        evaluation = Evaluation(
            dataset=dataset,
            scores=[score],
            preprocess_model_input=example_to_model_input,
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))

        assert result == expected_eval_result

        example_to_model_input0_run = evaluation.preprocess_model_input.runs()[0]
        example_to_model_input0_run_example = example_to_model_input0_run.inputs[
            "example"
        ]
        assert isinstance(example_to_model_input0_run_example, ref_base.Ref)
        assert example_to_model_input0_run_example.extra == [
            "atr",
            "dataset",
            "atr",
            "rows",
            "ndx",
            "0",
        ]
        assert example_to_model_input0_run_example.get() == {
            "input": "1 + 2",
            "target": 3,
        }

        predict0_run = EvalModel.predict.runs()[0]
        predict0_run_input = predict0_run.inputs["input"]
        assert isinstance(predict0_run_input, ref_base.Ref)
        assert predict0_run_input.extra == [
            "atr",
            "dataset",
            "atr",
            "rows",
            "ndx",
            "0",
            "key",
            "input",
        ]
        assert predict0_run_input.get() == "1 + 2"

        predict1_run = EvalModel.predict.runs()[1]
        predict1_run_input = predict1_run.inputs["input"]
        assert isinstance(predict1_run_input, ref_base.Ref)
        assert predict1_run_input.extra == [
            "atr",
            "dataset",
            "atr",
            "rows",
            "ndx",
            "1",
            "key",
            "input",
        ]
        assert predict1_run_input.get() == "2**4"

        # TODO: exhaustively check all graph relationships

        # TODO:
        #   - add row to dataset
        #     - fetch all preds from row
        #   - add col to dataset
        #   - update row in dataset


def test_evaluate_callable_as_model():
    @weave.op()
    async def model_predict(input) -> str:
        return eval(input)

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[score],
        )
        result = asyncio.run(evaluation.evaluate(model_predict))
        assert result == expected_eval_result


def test_predict_can_receive_other_params():
    @weave.op()
    async def model_predict(input, target) -> str:
        return eval(input) + target

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[score],
        )
        result = asyncio.run(evaluation.evaluate(model_predict))
        assert result == {
            "prediction": {"mean": 18.5},
            "score": {"true_count": 0, "true_fraction": 0.0},
        }


def test_can_preprocess_model_input():
    @weave.op()
    async def model_predict(x) -> str:
        return eval(x)

    @weave.op()
    def preprocess(example):
        return {"x": example["input"]}

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[score],
            preprocess_model_input=preprocess,
        )
        result = asyncio.run(evaluation.evaluate(model_predict))
        assert result == expected_eval_result


def test_evaluate_rows_only():
    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[score],
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))
        assert result == expected_eval_result


def test_evaluate_other_model_method_names():
    class EvalModel(Model):
        @weave.op()
        async def infer(self, input) -> str:
            return eval(input)

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[score],
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))
        assert result == expected_eval_result


def test_score_as_class():
    class MyScorer(weave.Scorer):
        def score(self, target, prediction):
            return target == prediction

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[MyScorer()],
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))
        assert result == {
            "prediction": {"mean": 9.5},
            "MyScorer": {"true_count": 1, "true_fraction": 0.5},
        }


def test_score_with_custom_summarize():
    class MyScorer(weave.Scorer):
        def summarize(self, score_rows):
            assert list(score_rows) == [True, False]
            return {"awesome": 3}

        def score(self, target, prediction):
            return target == prediction

    with weave.local_client():
        evaluation = Evaluation(
            dataset=dataset_rows,
            scores=[MyScorer()],
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))
        assert result == {
            "prediction": {"mean": 9.5},
            "MyScorer": {"awesome": 3},
        }


def test_multiclass_f1_score():
    with weave.local_client():
        evaluation = Evaluation(
            dataset=[
                {"target": {"a": False, "b": True}, "pred": {"a": True, "b": False}}
            ],
            scores=[MulticlassF1Score(class_names=["a", "b"])],
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
            "MulticlassF1Score": {
                "a": {"f1": 0, "precision": 0.0, "recall": 0},
                "b": {"f1": 0, "precision": 0, "recall": 0.0},
            },
        }
