from typing import Any, Optional

import pytest

import weave
from weave import Evaluation, Model
from weave.trace_server import trace_server_interface as tsi


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

    def is_object_ref_with_name(val: Any, name: str):
        return isinstance(val, str) and val.startswith(
            f"weave:///shawn/test-project/object/{name}:"
        )

    def is_op_ref_with_name(val: Any, name: str):
        return isinstance(val, str) and val.startswith(
            f"weave:///shawn/test-project/op/{name}:"
        )

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

    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(base_object_classes=["Model"]),
        )
    )
    assert len(objs.objs) == 1
    model_obj = objs.objs[0]
    expected_predict_ref = model_obj.val["predict"]
    assert is_op_ref_with_name(expected_predict_ref, "MyModel.predict")


@weave.op
def gpt_mocker(question: str):
    return {
        "response": question,
        "model": "gpt-4o-2024-05-13",
        "usage": {
            "requests": 1,
            "completion_tokens": 28,
            "prompt_tokens": 11,
            "total_tokens": 39,
        },
    }


class SimpleModel(Model):
    @weave.op()
    def predict(self, question: str):
        res = gpt_mocker(question.strip(".") if len(question) % 2 == 1 else question)
        return {"response": res["response"]}


class SimpleModelWithConfidence(Model):
    @weave.op()
    def predict(self, question: str):
        res = gpt_mocker(question.strip(".") if len(question) % 2 == 0 else question)
        return {"response": res["response"], "confidence": 1 / (len(res) + 1)}


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
        float_avg = sum(row["d_float"] for row in score_rows) / len(score_rows)
        return float_avg


class MyDictScorerWithCustomBoolSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum(row["d_float"] for row in score_rows) / len(score_rows)
        return float_avg > 0.5


class MyDictScorerWithCustomDictSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, model_output: dict) -> dict:
        return score_dict(expected, model_output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum(row["d_float"] for row in score_rows) / len(score_rows)
        bool_avg = sum(1 if row["d_bool"] else 0 for row in score_rows) / len(
            score_rows
        )
        return {
            "float_avg": float_avg,
            "nested": {"bool_avg": bool_avg},
            "reason": "This is a custom test reason",
        }


@pytest.mark.asyncio
async def test_evaluation_data_topology(client):
    """We support a number of different types of scorers, and we want to ensure that
    the data stored matches the expected structure. This test is a bit more complex
    than the previous one, as it involves multiple models and scorers. Importantly,
    the construction of the Eval Comparison page relies on this structure.
    """
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
    await evaluation.evaluate(model1)

    model2 = SimpleModelWithConfidence()
    await evaluation.evaluate(model2)

    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )
    flattened = flatten_calls(calls.calls)
    assert len(flattened) == 50
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    predict_and_score_block = lambda model_pred_name: [
        ("Evaluation.predict_and_score", 1),
        (model_pred_name, 2),
        ("gpt_mocker", 3),
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
    eval_block = flat_calls[len(eval_block("")) :]
    evaluate_call = eval_block[0]
    predict_and_score_block = eval_block[1 : 1 + len(predict_and_score_block(""))]
    predict_and_score_call = predict_and_score_block[0]
    predict_call = predict_and_score_block[1]
    # gtp_mock_call = predict_and_score_block[2]
    score_int_call = predict_and_score_block[3]
    score_float_call = predict_and_score_block[4]
    score_bool_call = predict_and_score_block[5]
    score_dict_call = predict_and_score_block[6]
    my_dict_scorer_with_custom_float_score_call = predict_and_score_block[6]
    my_dict_scorer_with_custom_bool_score_call = predict_and_score_block[7]
    my_dict_scorer_with_custom_dict_score_call = predict_and_score_block[8]
    summary_block = eval_block[-len(summary_block) :]
    summary_call = summary_block[0]
    my_dict_scorer_with_custom_float_summary_call = summary_block[1]
    my_dict_scorer_with_custom_bool_summary_call = summary_block[2]
    my_dict_scorer_with_custom_dict_summary_call = summary_block[3]

    # Prediction Section
    confidence = 1 / 4
    model_output = {
        "response": "A",
        "confidence": confidence,
    }
    # BUG: latency reported includes weave internal latency
    # actual_latency = (predict_call.ended_at - predict_call.started_at).total_seconds()
    actual_latency = pytest.approx(0, abs=1)
    model_1_latency = {"mean": actual_latency}
    score_int_score = 1
    score_float_score = 1.0
    score_bool_score = True
    score_dict_score = {
        "d_int": score_int_score,
        "d_float": score_float_score,
        "d_bool": score_bool_score,
        "d_nested": {
            "d_int": score_int_score,
            "d_float": score_float_score,
            "d_bool": score_bool_score,
        },
        "reason": "This is a test reason",
    }
    predict_usage = {
        "usage": {
            "gpt-4o-2024-05-13": {
                "requests": 1,
                "completion_tokens": 28,
                "prompt_tokens": 11,
                "total_tokens": 39,
            }
        }
    }

    # Prediction
    assert predict_call.output == model_output
    assert predict_call.summary == predict_usage

    # Prediction Scores
    assert score_int_call.output == score_int_score
    assert score_float_call.output == score_float_score
    assert score_bool_call.output == score_bool_score
    assert (
        score_dict_call.output
        == my_dict_scorer_with_custom_float_score_call.output
        == my_dict_scorer_with_custom_dict_score_call.output
        == my_dict_scorer_with_custom_bool_score_call.output
        == {
            "d_int": 1,
            "d_float": 1.0,
            "d_bool": True,
            "d_nested": {"d_int": 1, "d_float": 1.0, "d_bool": True},
            "reason": "This is a test reason",
        }
    )

    # Predict And Score Group
    assert predict_and_score_call.output == {
        "model_output": model_output,
        "scores": {
            "score_int": score_int_score,
            "score_float": score_float_score,
            "score_bool": score_bool_score,
            "score_dict": score_dict_score,
            "MyDictScorerWithCustomFloatSummary": score_dict_score,
            "MyDictScorerWithCustomBoolSummary": score_dict_score,
            "MyDictScorerWithCustomDictSummary": score_dict_score,
        },
        "model_latency": actual_latency,
    }

    # Summary section
    model_output_summary = {
        "confidence": {"mean": confidence},
    }
    score_int_auto_summary = {"mean": 1.5}
    score_float_auto_summary = {"mean": 0.8333333333333333}
    score_bool_auto_summary = {"true_count": 1, "true_fraction": 0.5}
    dict_scorer_float_summary = 0.8333333333333333
    dict_scorer_bool_summary = True
    dict_scorer_dict_summary = {
        "float_avg": 0.8333333333333333,
        "nested": {"bool_avg": 0.5},
        "reason": "This is a custom test reason",
    }
    model_latency = {"mean": pytest.approx(0, abs=1)}
    predict_usage_summary = {
        "usage": {
            "gpt-4o-2024-05-13": {
                "requests": predict_usage["usage"]["gpt-4o-2024-05-13"]["requests"] * 2,
                "completion_tokens": predict_usage["usage"]["gpt-4o-2024-05-13"][
                    "completion_tokens"
                ]
                * 2,
                "prompt_tokens": predict_usage["usage"]["gpt-4o-2024-05-13"][
                    "prompt_tokens"
                ]
                * 2,
                "total_tokens": predict_usage["usage"]["gpt-4o-2024-05-13"][
                    "total_tokens"
                ]
                * 2,
            }
        }
    }

    # Summarizers
    assert (
        my_dict_scorer_with_custom_float_summary_call.output
        == dict_scorer_float_summary
    )
    assert (
        my_dict_scorer_with_custom_bool_summary_call.output == dict_scorer_bool_summary
    )
    assert (
        my_dict_scorer_with_custom_dict_summary_call.output == dict_scorer_dict_summary
    )

    # Final Summary
    assert (
        evaluate_call.output
        == summary_call.output
        == {
            "score_int": score_int_auto_summary,
            "score_float": score_float_auto_summary,
            "score_bool": score_bool_auto_summary,
            "score_dict": {
                "d_int": score_int_auto_summary,
                "d_float": score_float_auto_summary,
                "d_bool": score_bool_auto_summary,
                "d_nested": {
                    "d_int": score_int_auto_summary,
                    "d_float": score_float_auto_summary,
                    "d_bool": score_bool_auto_summary,
                },
            },
            "MyDictScorerWithCustomFloatSummary": dict_scorer_float_summary,
            "MyDictScorerWithCustomBoolSummary": dict_scorer_bool_summary,
            "MyDictScorerWithCustomDictSummary": dict_scorer_dict_summary,
            "model_latency": model_latency,
            "model_output": model_output_summary,
        }
    )
    assert evaluate_call.summary == predict_usage_summary


def make_test_eval():
    def function_score(target: dict, model_output: dict) -> dict:
        return {"correct": target == model_output}

    evaluation = weave.Evaluation(
        name="fruit_eval",
        dataset=[
            {"id": "0", "sentence": "a", "target": "b"},
        ],
        scorers=[function_score],
    )
    return evaluation


@pytest.mark.asyncio
async def test_eval_supports_model_as_op(client):
    @weave.op
    def function_model(sentence: str) -> dict:
        return ""

    evaluation = make_test_eval()

    res = await evaluation.evaluate(function_model)
    assert res != None

    gotten_op = weave.ref(function_model.ref.uri()).get()
    res = await evaluation.evaluate(gotten_op)
    assert res != None


class MyTestModel(Model):
    @weave.op
    def predict(self, sentence: str) -> dict:
        return ""


@pytest.mark.asyncio
async def test_eval_supports_model_class(client):
    evaluation = make_test_eval()

    model = MyTestModel()
    res = await evaluation.evaluate(model)
    assert res != None

    gotten_model = weave.ref(model.ref.uri()).get()
    res = await evaluation.evaluate(gotten_model)
    assert res != None


@pytest.mark.asyncio
async def test_eval_supports_non_op_funcs(client):
    def function_model(sentence: str) -> dict:
        return ""

    evaluation = make_test_eval()

    with pytest.raises(ValueError):
        res = await evaluation.evaluate(function_model)

    # In the future, if we want to auto-opify, then uncomment the following assertions:
    # assert res["function_score"] == {"correct": {"true_count": 0, "true_fraction": 0.0}}

    # calls = client.server.calls_query(
    #     tsi.CallsQueryReq(
    #         project_id=client._project_id(),
    #     )
    # )
    # assert len(calls.calls) == 4
    # shouldBeEvalRef = calls.calls[0].inputs["self"]
    # assert shouldBeEvalRef.startswith("weave:///")
    # gottenEval = weave.ref(shouldBeEvalRef).get()

    # # 1: Assert that the scorer was correctly oped
    # gottenEval.scorers[0].ref.name == "function_score"
    # shouldBeModelRef = calls.calls[0].inputs["model"]

    # # 2: Assert that the model was correctly oped
    # assert shouldBeModelRef.startswith("weave:///")


@pytest.mark.asyncio
async def test_eval_is_robust_to_missing_values(client):
    # At least 1 None
    # All dicts have "d": None
    resp = [
        None,
        {"a": 1, "b": {"c": 2}, "always_none": None},
        {"a": 2, "b": {"c": None}, "always_none": None},
        {"a": 3, "b": {}, "always_none": None},
        {"a": 4, "b": None, "always_none": None},
        {"a": 5, "always_none": None},
        {"a": None, "always_none": None},
        {"always_none": None},
        {},
    ]

    @weave.op
    def model_func(model_res) -> dict:
        return resp[model_res]

    def function_score(scorer_res, model_output) -> dict:
        return resp[scorer_res]

    evaluation = weave.Evaluation(
        name="fruit_eval",
        dataset=[{"model_res": i, "scorer_res": i} for i in range(len(resp))],
        scorers=[function_score],
    )

    res = await evaluation.evaluate(model_func)
    assert res == {
        "model_output": {"a": {"mean": 3.0}, "b": {"c": {"mean": 2.0}}},
        "function_score": {"a": {"mean": 3.0}, "b": {"c": {"mean": 2.0}}},
        "model_latency": {"mean": pytest.approx(0, abs=1)},
    }
