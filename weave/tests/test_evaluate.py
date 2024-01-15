import asyncio
import pytest
import weave
from weave import weaveflow
from weave import ref_base


def test_evaluate_basic():
    with weave.local_client():
        dataset = weaveflow.Dataset(
            [{"input": "1 + 2", "output": "3"}, {"input": "2**4", "output": "16"}]
        )

        @weave.type()
        class EvalModel:
            @weave.op()
            async def predict(self, input: str) -> str:
                return eval(input)

        @weave.op()
        def score(example: dict, prediction: str) -> int:
            return int(example["output"] == prediction)

        @weave.op()
        def example_to_model_input(example):
            return example["input"]

        evaluation = weaveflow.evaluate2.Evaluation(
            dataset, [score], example_to_model_input=example_to_model_input
        )
        model = EvalModel()
        result = asyncio.run(evaluation.evaluate(model))

        predict0_run = EvalModel.predict.runs()[0]
        predict0_run_input = predict0_run.inputs["input"]
        assert isinstance(predict0_run_input, ref_base.Ref)
        assert predict0_run_input.extra == ["0", "input"]
        assert predict0_run_input.get() == "1 + 2"

        predict1_run = EvalModel.predict.runs()[1]
        predict1_run_input = predict1_run.inputs["input"]
        assert isinstance(predict1_run_input, ref_base.Ref)
        assert predict1_run_input.extra == ["1", "input"]
        assert predict1_run_input.get() == "2**4"

        # TODO: exhaustively check all graph relationships
