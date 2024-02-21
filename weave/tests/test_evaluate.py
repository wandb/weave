import asyncio
import pytest
import weave
from weave import ref_base
from weave.flow import Dataset, Model, Evaluation


def test_evaluate_basic():
    with weave.local_client():
        dataset = Dataset(
            rows=[{"input": "1 + 2", "output": "3"}, {"input": "2**4", "output": "16"}]
        )

        class EvalModel(Model):
            @weave.op()
            async def predict(self, input: str) -> str:
                return eval(input)

        @weave.op()
        def score(example: dict, prediction: str) -> int:
            return int(example["output"] == prediction)

        @weave.op()
        def example_to_model_input(example):
            return example["input"]

        evaluation = Evaluation(
            dataset=dataset,
            scores=[score],
            example_to_model_input=example_to_model_input,
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))

        assert result == {"prediction": {"mean": 9.5}, "score": {"mean": 0.0}}

        example_to_model_input0_run = evaluation.example_to_model_input.runs()[0]
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
            "output": "3",
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
