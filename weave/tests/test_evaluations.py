import asyncio
from typing import Optional

import pytest

import weave
from weave import Evaluation, Model

from ..trace_server import trace_server_interface as tsi


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    def children_of_parent_id(id: Optional[str]) -> list[tsi.CallSchema]:
        return [call for call in calls if call.parent_id == id]

    children = children_of_parent_id(parent_id)
    res = []
    for child in children:
        res.append((child, depth))
        res.extend(flatten_calls(calls, child.id, depth + 1))

    return res


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


async def do_quickstart():
    """
    This is the basic example from the README/quickstart/docs
    """
    examples = [
        {"question": "What is the capital of France?", "expected": "Paris"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
        {"question": "What is the square root of 64?", "expected": "8"},
    ]

    @weave.op()
    def match_score1(expected: str, model_output: dict) -> dict:
        return {"match": expected == model_output["generated_text"]}

    @weave.op()
    def match_score2(expected: dict, model_output: dict) -> dict:
        return {"match": expected == model_output["generated_text"]}

    class MyModel(Model):
        prompt: str

        @weave.op()
        def predict(self, question: str):
            # here's where you would add your LLM call and return the output
            return {"generated_text": "Hello, " + question + self.prompt}

    model = MyModel(prompt="World")
    evaluation = Evaluation(dataset=examples, scorers=[match_score1, match_score2])

    return await evaluation.evaluate(model)


@pytest.mark.asyncio
async def test_basic_evaluation(client):
    res = await do_quickstart()

    # Assert basic results - these are pretty boring, should probably add more interesting examples
    assert res["match_score1"] == {"match": {"true_count": 0, "true_fraction": 0.0}}
    assert res["match_score2"] == {"match": {"true_count": 0, "true_fraction": 0.0}}

    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    flattened_calls = flatten_calls(calls.calls)

    assert len(flattened_calls) == 14

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened_calls]
    exp = [
        ("Evaluation.evaluate", 0),
        ("Evaluation.predict_and_score", 1),
        ("MyModel.predict", 2),
        ("match_score1", 2),
        ("match_score2", 2),
        ("Evaluation.predict_and_score", 1),
        ("MyModel.predict", 2),
        ("match_score1", 2),
        ("match_score2", 2),
        ("Evaluation.predict_and_score", 1),
        ("MyModel.predict", 2),
        ("match_score1", 2),
        ("match_score2", 2),
        ("Evaluation.summarize", 1),
    ]
    assert got == exp

    assert flattened_calls[1][0].inputs == {
        "self": "weave:///shawn/test-project/object/Evaluation:kaQkkylnWlltlYaXYpT0IRpmlmbevcBBQUvIdaT8lF4",
        "model": "weave:///shawn/test-project/object/MyModel:YCUen3Cmgo72cPqJiXH9HzXlCT2H1sVfwOEidsmvHK4",
        "example": "weave:///shawn/test-project/object/Dataset:JYbPm92vzb3zl6YjQpXPotL13Xwh0L6bDLcXYrwJEYk/attr/rows/id/F2inb5rPfF4JnyHlEAfdzRATQgGWTDpNYF25WuidjP4",
    }
