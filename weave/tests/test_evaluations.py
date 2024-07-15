from typing import Optional

import pytest

import weave
from weave import Evaluation, Model

from ..trace_server import trace_server_interface as tsi


class Nearly:
    def __init__(self, v: float, tol: float = 0.01) -> None:
        self.v = v
        self.tol = tol

    def __eq__(self, other: float) -> bool:
        return abs(self.v - other) < self.tol


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    """
    Flatten calls is a technique we use in the integration tests to assert the correct
    ordering of calls. This is used to assert that the calls are in the correct order
    as well as nested in the correct way. The returned list is the ordered list of calls
    with the depth of each call.
    """

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


class MyModel(Model):
    prompt: str

    @weave.op()
    def predict(self, question: str):
        # Here's where you would add your LLM call and return the output
        return {"generated_text": "Hello, " + question + self.prompt}


async def do_quickstart():
    """This is the basic example from the README/quickstart/docs"""
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

    def is_object_ref_with_name(val: str, name: str):
        return val.startswith(f"weave:///shawn/test-project/object/{name}:")

    ## Assertion Category 1: Here we make some application-specific assertions about the
    # structure of the calls, specifically for evaluation-specific UI elements

    # The `Evaluation.evaluate` call is expected to have the correct inputs as refs
    assert op_name_from_ref(flattened_calls[0][0].op_name) == "Evaluation.evaluate"
    assert is_object_ref_with_name(flattened_calls[0][0].inputs["self"], "Evaluation")
    assert is_object_ref_with_name(flattened_calls[0][0].inputs["model"], "MyModel")

    # The UI depends on "example", "model" and "self" being refs, so we make that
    # specific assertion here
    for i in [1, 5, 9]:  # The indexes of the predict_and_score calls
        assert (
            op_name_from_ref(flattened_calls[i][0].op_name)
            == "Evaluation.predict_and_score"
        )
        assert is_object_ref_with_name(
            flattened_calls[i][0].inputs["self"], "Evaluation"
        )
        assert is_object_ref_with_name(flattened_calls[i][0].inputs["model"], "MyModel")
        assert is_object_ref_with_name(
            flattened_calls[i][0].inputs["example"], "Dataset"
        )


class SimpleModel(Model):
    @weave.op()
    def predict(self, question: str):
        question = question.strip(".") if len(question) % 2 == 0 else question
        return {"response": question}


class SimpleModelWithConfidence(Model):
    @weave.op()
    def predict(self, question: str):
        question = question.strip(".") if len(question) % 2 == 1 else question
        return {"response": question, "confidence": 1 / len(question)}


def score_int(expected: str, model_output: dict) -> int:
    matches = 0
    for i in range(min(len(expected), len(model_output["response"]))):
        if expected[i] == model_output["response"][i]:
            matches += 1
    return matches


def score_float(expected: str, model_output: dict) -> float:
    matches = score_int(expected, model_output)
    return matches / max(len(expected), len(model_output["response"]))


def score_bool(expected: str, model_output: dict) -> bool:
    return score_float(expected, model_output) == 1.0


def score_dict(expected: str, model_output: dict) -> dict:
    return {
        "d_int": score_int(expected, model_output),
        "d_float": score_float(expected, model_output),
        "d_bool": score_bool(expected, model_output),
        "d_nested": {
            "d_int": score_int(expected, model_output),
            "d_float": score_float(expected, model_output),
            "d_bool": score_bool(expected, model_output),
        },
        "reason": "This is a test reason",
    }


class MyIntScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> int:
        return score_int(expected, model_output)


class MyFloatScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> float:
        return score_float(expected, model_output)


class MyBoolScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> bool:
        return score_bool(expected, model_output)


class MyDictScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)


class MyDictScorerWithCustomFloatSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum([row["d_float"] for row in score_rows]) / len(score_rows)
        return float_avg


class MyDictScorerWithCustomBoolSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum([row["d_float"] for row in score_rows]) / len(score_rows)
        return float_avg > 0.5


class MyDictScorerWithCustomDictSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum([row["d_float"] for row in score_rows]) / len(score_rows)
        bool_avg = sum([1 if row["d_bool"] else 0 for row in score_rows]) / len(
            score_rows
        )
        return {
            "float_avg": float_avg,
            "nested": {"bool_avg": bool_avg},
            "reason": "This is a custom test reason",
        }


@pytest.mark.asyncio
async def test_evaluation_summary_styles(client):
    examples = [
        {"question": "A.", "expected": "A"},
        {"question": "BB.", "expected": "BB"},
    ]

    evaluation = Evaluation(
        dataset=examples,
        scorers=[
            score_int,
            score_float,
            score_bool,
            score_dict,
            MyDictScorerWithCustomFloatSummary(),
            MyDictScorerWithCustomBoolSummary(),
            MyDictScorerWithCustomDictSummary(),
        ],
    )

    model1 = SimpleModel()
    res1 = await evaluation.evaluate(model1)

    model2 = SimpleModelWithConfidence()
    res2 = await evaluation.evaluate(model2)

    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )
    flattened = flatten_calls(calls.calls)
    assert len(flattened) == 46
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    predict_and_score_block = lambda model_pred_name: [
        ("Evaluation.predict_and_score", 1),
        (model_pred_name, 2),
        ("score_int", 2),
        ("score_float", 2),
        ("score_bool", 2),
        ("score_dict", 2),
        ("MyDictScorerWithCustomFloatSummary.score", 2),
        ("MyDictScorerWithCustomBoolSummary.score", 2),
        ("MyDictScorerWithCustomDictSummary.score", 2),
    ]
    summary_block = [
        ("Evaluation.summarize", 1),
        ("MyDictScorerWithCustomFloatSummary.summarize", 2),
        ("MyDictScorerWithCustomBoolSummary.summarize", 2),
        ("MyDictScorerWithCustomDictSummary.summarize", 2),
    ]
    eval_block = lambda model_pred_name: [
        ("Evaluation.evaluate", 0),
        *predict_and_score_block(model_pred_name),
        *predict_and_score_block(model_pred_name),
        *summary_block,
    ]

    exp = [
        *eval_block("SimpleModel.predict"),
        *eval_block("SimpleModelWithConfidence.predict"),
    ]

    # First, let's assert the topology of the calls
    assert got == exp
    flat_calls = [c[0] for c in flattened]

    # Next, we will assert some application-specific details about the calls
    eval_block_0 = flat_calls[: len(eval_block(""))]
    evaluate_call_0_0 = eval_block_0[0]
    predict_and_score_block_0_0 = eval_block_0[1 : 1 + len(predict_and_score_block(""))]
    predict_and_score_call_0_0 = predict_and_score_block_0_0[0]
    predict_call_0_0 = predict_and_score_block_0_0[1]
    score_int_call_0_0 = predict_and_score_block_0_0[2]
    score_float_call_0_0 = predict_and_score_block_0_0[3]
    score_bool_call_0_0 = predict_and_score_block_0_0[4]
    score_dict_call_0_0 = predict_and_score_block_0_0[5]
    my_dict_scorer_with_custom_float_score_call_0_0 = predict_and_score_block_0_0[6]
    my_dict_scorer_with_custom_bool_score_call_0_0 = predict_and_score_block_0_0[7]
    my_dict_scorer_with_custom_dict_score_call_0_0 = predict_and_score_block_0_0[8]
    summary_block_0_0 = eval_block_0[-len(summary_block) :]
    summary_call_0_0 = summary_block_0_0[0]
    my_dict_scorer_with_custom_float_summary_call_0_0 = summary_block_0_0[1]
    my_dict_scorer_with_custom_bool_summary_call_0_0 = summary_block_0_0[2]
    my_dict_scorer_with_custom_dict_summary_call_0_0 = summary_block_0_0[3]

    assert evaluate_call_0_0.output == {
        "score_int": {"mean": 1.5},
        "score_float": {"mean": 0.8333333333333333},
        "score_bool": {"true_count": 1, "true_fraction": 0.5},
        "score_dict": {
            "d_int": {"mean": 1.5},
            "d_float": {"mean": 0.8333333333333333},
            "d_bool": {"true_count": 1, "true_fraction": 0.5},
            "d_nested": {
                "d_int": {"mean": 1.5},
                "d_float": {"mean": 0.8333333333333333},
                "d_bool": {"true_count": 1, "true_fraction": 0.5},
            },
        },
        "MyDictScorerWithCustomFloatSummary": 0.8333333333333333,
        "MyDictScorerWithCustomBoolSummary": True,
        "MyDictScorerWithCustomDictSummary": {
            "float_avg": 0.8333333333333333,
            "nested": {"bool_avg": 0.5},
            "reason": "This is a custom test reason",
        },
        "model_latency": {"mean": Nearly(0, 1)},  # 0.005481123924255371
    }

    assert predict_and_score_call_0_0.output == {
        "model_output": {"response": "A"},
        "scores": {
            "score_int": 1,
            "score_float": 1.0,
            "score_bool": True,
            "score_dict": {
                "d_int": 1,
                "d_float": 1.0,
                "d_bool": True,
                "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
                "reason": "This is a test reason",
            },
            "MyDictScorerWithCustomFloatSummary": {
                "d_int": 1,
                "d_float": 1.0,
                "d_bool": True,
                "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
                "reason": "This is a test reason",
            },
            "MyDictScorerWithCustomBoolSummary": {
                "d_int": 1,
                "d_float": 1.0,
                "d_bool": True,
                "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
                "reason": "This is a test reason",
            },
            "MyDictScorerWithCustomDictSummary": {
                "d_int": 1,
                "d_float": 1.0,
                "d_bool": True,
                "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
                "reason": "This is a test reason",
            },
        },
        "model_latency": Nearly(0, 1),
    }

    assert predict_call_0_0.output == {"response": "A"}

    assert score_int_call_0_0.output == 1

    assert score_float_call_0_0.output == 1.0

    assert score_bool_call_0_0.output == True

    assert (
        score_dict_call_0_0.output
        == my_dict_scorer_with_custom_float_score_call_0_0.output
        == my_dict_scorer_with_custom_dict_score_call_0_0.output
        == my_dict_scorer_with_custom_bool_score_call_0_0.output
        == {
            "d_int": 1,
            "d_float": 1.0,
            "d_bool": True,
            "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
            "reason": "This is a test reason",
        }
    )

    assert summary_call_0_0.output == {
        "score_int": {"mean": 1.5},
        "score_float": {"mean": 0.8333333333333333},
        "score_bool": {"true_count": 1, "true_fraction": 0.5},
        "score_dict": {
            "d_int": {"mean": 1.5},
            "d_float": {"mean": 0.8333333333333333},
            "d_bool": {"true_count": 1, "true_fraction": 0.5},
            "d_nested": {
                "d_int": {"mean": 1.5},
                "d_float": {"mean": 0.8333333333333333},
                "d_bool": {"true_count": 1, "true_fraction": 0.5},
            },
        },
        "MyDictScorerWithCustomFloatSummary": 0.8333333333333333,
        "MyDictScorerWithCustomBoolSummary": True,
        "MyDictScorerWithCustomDictSummary": {
            "float_avg": 0.8333333333333333,
            "nested": {"bool_avg": 0.5},
            "reason": "This is a custom test reason",
        },
        "model_latency": {"mean": Nearly(0, 1)},
    }

    assert (
        my_dict_scorer_with_custom_float_summary_call_0_0.output == 0.8333333333333333
    )
    assert my_dict_scorer_with_custom_bool_summary_call_0_0.output == True
    assert my_dict_scorer_with_custom_dict_summary_call_0_0.output == {
        "float_avg": 0.8333333333333333,
        "nested": {"bool_avg": 0.5},
        "reason": "This is a custom test reason",
    }
