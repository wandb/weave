import dataclasses
import random
from typing import Any, Optional

import pydantic
import pytest
from PIL import Image

import weave
from tests.trace.util import AnyIntMatcher, AnyStrMatcher
from weave import Evaluation, Model
from weave.trace.refs import CallRef
from weave.trace.weave_client import get_ref
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
        return {"generated_text": "Hello, " + question + self.prompt}


async def do_quickstart():
    """This is the basic example from the README/quickstart/docs"""
    examples = [
        {"question": "What is the capital of France?", "expected": "Paris"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
        {"question": "What is the square root of 64?", "expected": "8"},
    ]

    @weave.op()
    def match_score1(expected: str, output: dict) -> dict:
        return {"match": expected == output["generated_text"]}

    @weave.op()
    def match_score2(expected: dict, output: dict) -> dict:
        return {"match": expected == output["generated_text"]}

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

    predict_and_score_calls = [
        c
        for (c, d) in flattened_calls
        if op_name_from_ref(c.op_name) == "Evaluation.predict_and_score"
    ]
    assert len(predict_and_score_calls) == 3

    # Assert that all the inputs are unique
    inputs = set()
    for call in predict_and_score_calls:
        inputs.add(call.inputs["example"])
    assert len(inputs) == 3


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


def score_int(expected: str, output: dict) -> int:
    matches = 0
    for i in range(min(len(expected), len(output["response"]))):
        if expected[i] == output["response"][i]:
            matches += 1
    return matches


def score_float(expected: str, output: dict) -> float:
    matches = score_int(expected, output)
    return matches / max(len(expected), len(output["response"]))


def score_bool(expected: str, output: dict) -> bool:
    return score_float(expected, output) == 1.0


def score_dict(expected: str, output: dict) -> dict:
    return {
        "d_int": score_int(expected, output),
        "d_float": score_float(expected, output),
        "d_bool": score_bool(expected, output),
        "d_nested": {
            "d_int": score_int(expected, output),
            "d_float": score_float(expected, output),
            "d_bool": score_bool(expected, output),
        },
        "reason": "This is a test reason",
    }


class MyIntScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> int:
        return score_int(expected, output)


class MyFloatScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> float:
        return score_float(expected, output)


class MyBoolScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> bool:
        return score_bool(expected, output)


class MyDictScorer(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> dict:
        return score_dict(expected, output)


class MyDictScorerWithCustomFloatSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> dict:
        return score_dict(expected, output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum(row["d_float"] for row in score_rows) / len(score_rows)
        return float_avg


class MyDictScorerWithCustomBoolSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> dict:
        return score_dict(expected, output)

    @weave.op()
    def summarize(self, score_rows: list) -> Optional[dict]:
        float_avg = sum(row["d_float"] for row in score_rows) / len(score_rows)
        return float_avg > 0.5


class MyDictScorerWithCustomDictSummary(weave.Scorer):
    @weave.op()
    def score(self, expected: str, output: dict) -> dict:
        return score_dict(expected, output)

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


def with_empty_feedback(obj: Any) -> Any:
    if isinstance(obj, dict):
        new_dict = {**obj}
        if "weave" not in new_dict:
            new_dict["weave"] = {}
        new_dict["weave"] = {**new_dict["weave"], "feedback": []}
        return new_dict
    return obj


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
            include_feedback=True,
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
    output = {
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
        },
        "weave": {
            "latency_ms": AnyIntMatcher(),
            "trace_name": "SimpleModelWithConfidence.predict",
            "status": "success",
        },
    }

    # Prediction
    assert predict_call.output == output
    assert with_empty_feedback(predict_call.summary) == with_empty_feedback(
        predict_usage
    )

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
        "output": output,
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
    output_summary = {
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
        },
        "weave": {
            "display_name": AnyStrMatcher(),
            "latency_ms": AnyIntMatcher(),
            "status": "success",
        },
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
            "output": output_summary,
        }
    )
    assert evaluate_call.summary == with_empty_feedback(predict_usage_summary)

    # Test new Feeedback as Scores
    predict_calls_simple = [
        c for c in flat_calls if op_name_from_ref(c.op_name) == "SimpleModel.predict"
    ]
    predict_calls_with_confidence = [
        c
        for c in flat_calls
        if op_name_from_ref(c.op_name) == "SimpleModelWithConfidence.predict"
    ]
    assert len(predict_calls_simple) == len(predict_calls_with_confidence) == 2
    assert len(predict_calls_simple[0].summary["weave"]["feedback"]) == 7
    assert len(predict_calls_simple[1].summary["weave"]["feedback"]) == 7
    assert len(predict_calls_with_confidence[0].summary["weave"]["feedback"]) == 7
    assert len(predict_calls_with_confidence[1].summary["weave"]["feedback"]) == 7


def make_test_eval():
    def function_score(expected: str, output: dict) -> dict:
        return {"correct": expected == output["generated_text"]}

    evaluation = weave.Evaluation(
        name="fruit_eval",
        dataset=[
            {"id": "0", "sentence": "a", "expected": "b"},
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

    def function_score(scorer_res, output) -> dict:
        return resp[scorer_res]

    evaluation = weave.Evaluation(
        name="fruit_eval",
        dataset=[{"model_res": i, "scorer_res": i} for i in range(len(resp))],
        scorers=[function_score],
    )

    res = await evaluation.evaluate(model_func)
    assert res == {
        "output": {"a": {"mean": 3.0}, "b": {"c": {"mean": 2.0}}},
        "function_score": {"a": {"mean": 3.0}, "b": {"c": {"mean": 2.0}}},
        "model_latency": {"mean": pytest.approx(0, abs=1)},
    }


@pytest.mark.asyncio
async def test_eval_with_complex_types(client):
    client.project = "test_eval_with_complex_types"

    @dataclasses.dataclass(frozen=True)
    class MyDataclass:
        a_string: str

    class MyModel(pydantic.BaseModel):
        a_string: str

    class MyObj(weave.Object):
        a_string: str

    @weave.op
    def model_func(
        image: Image.Image, dc: MyDataclass, model: MyModel, obj: MyObj, text: str
    ) -> str:
        assert isinstance(image, Image.Image)

        # Note: when we start recursively saving dataset rows, this will
        # probably break. We need a way to deserialize back to the actual
        # classes for these assertions to maintain, else they will be
        # WeaveObjects here and not pass these checks. I suspect customers
        # will not be happy with WeaveObjects, so this is a good sanity check
        # for now.
        assert isinstance(dc, MyDataclass)
        assert isinstance(model, MyModel)
        assert isinstance(obj, MyObj)
        assert isinstance(text, str)

        return text

    def function_score(image, dc, model, obj, text, output) -> bool:
        assert isinstance(image, Image.Image)

        # Note: when we start recursively saving dataset rows, this will
        # probably break. We need a way to deserialize back to the actual
        # classes for these assertions to maintain, else they will be
        # WeaveObjects here and not pass these checks. I suspect customers
        # will not be happy with WeaveObjects, so this is a good sanity check
        # for now.
        assert isinstance(dc, MyDataclass)
        assert isinstance(model, MyModel)
        assert isinstance(obj, MyObj)
        assert isinstance(text, str)
        assert isinstance(output, str)

        return True

    evaluation = weave.Evaluation(
        name="fruit_eval",
        dataset=[
            {
                "image": Image.new("RGB", (100, 100), color=random.randint(0, 255)),
                "dc": MyDataclass(a_string="hello"),
                "model": MyModel(a_string="hello"),
                "obj": MyObj(a_string="hello"),
                "text": "A photo of a cat",
            }
        ],
        scorers=[function_score],
    )

    res = await evaluation.evaluate(model_func)
    assert res.get("function_score", {}).get("true_count") == 1

    # Before this test (and fix) we were making extra requests
    # to reconstruct the table and objects in the evaluation.\
    # These assertions ensure that we aren't making those extra requests.
    # There is no reason to query the table, objects, or files
    # as everything is in memory
    access_log = client.server.attribute_access_log
    assert "table_query" not in access_log
    assert "obj_read" not in access_log
    assert "file_content_read" not in access_log

    # Verify that the access log does record such requests
    dataset = evaluation.evaluate.calls()[0].inputs["self"].dataset
    row = dataset.rows[0]

    assert isinstance(row["image"], Image.Image)
    # Very SAD: Datasets do not resursively save objects
    # So this assertion is checking current state, but not
    # the correct behavior of the dataset (the should be the
    # MyDataclass, MyModel, and MyObj)
    assert isinstance(row["dc"], str)  #  MyDataclass
    assert row["model"] == {"a_string": "hello"}  # MyModel
    # MyObj
    assert row["obj"] == {
        "name": None,
        "description": None,
        "ref": None,
        "a_string": "hello",
    }
    assert isinstance(row["text"], str)

    access_log = client.server.attribute_access_log
    assert "table_query" in access_log
    assert "obj_read" in access_log
    assert "file_content_read" in access_log


@pytest.mark.asyncio
async def test_evaluation_with_column_map():
    # Define a dummy scorer that uses column_map
    class DummyScorer(weave.Scorer):
        @weave.op()
        def score(self, foo: str, bar: str, output: str, target: str) -> dict:
            # Return whether foo + bar equals output
            return {"match": (foo + bar) == output == target}

    # Create the scorer with column_map mapping 'foo'->'col1', 'bar'->'col2'
    dummy_scorer = DummyScorer(column_map={"foo": "col1", "bar": "col2"})

    @weave.op()
    def model_function(col1, col2):
        # For testing, return the concatenation of col1 and col2
        return col1 + col2

    dataset = [
        {"col1": "Hello", "col2": "World", "target": "HelloWorld"},
        {"col1": "Hi", "col2": "There", "target": "HiThere"},
        {"col1": "Good", "col2": "Morning", "target": "GoodMorning"},
        {"col1": "Bad", "col2": "Evening", "target": "GoodEvening"},
    ]

    evaluation = Evaluation(dataset=dataset, scorers=[dummy_scorer])

    # Run the evaluation
    eval_out = await evaluation.evaluate(model_function)

    # Check that 'DummyScorer' is in the results
    assert "DummyScorer" in eval_out

    # The expected summary should show that 3 out of 4 predictions matched
    expected_results = {"true_count": 3, "true_fraction": 0.75}
    assert (
        eval_out["DummyScorer"]["match"] == expected_results
    ), "The summary should reflect the correct number of matches"


@pytest.mark.asyncio
async def test_evaluation_with_wrong_column_map():
    # Define a dummy scorer that uses column_map
    class DummyScorer(weave.Scorer):
        @weave.op()
        def score(self, foo: str, bar: str, output: str, target: str) -> dict:
            # Return whether foo + bar equals output
            return {"match": (foo + bar) == output == target}

    @weave.op()
    def model_function(col1, col2):
        # For testing, return the concatenation of col1 and col2
        return col1 + col2

    dataset = [
        {"col1": "Hello", "col2": "World", "target": "HelloWorld"},  # True
        {"col1": "Hi", "col2": "There", "target": "HiThere"},  # True
        {"col1": "Good", "col2": "Morning", "target": "GoodMorning"},  # True
        {"col1": "Bad", "col2": "Evening", "target": "GoodEvening"},  # False
    ]

    # Test that the column map is correctly used
    dummy_scorer = DummyScorer(column_map={"foo": "col1", "bar": "col2"})
    evaluation = Evaluation(dataset=dataset, scorers=[dummy_scorer])
    eval_out = await evaluation.evaluate(model_function)
    assert "DummyScorer" in eval_out
    assert eval_out["DummyScorer"]["match"] == {"true_count": 3, "true_fraction": 0.75}

    with pytest.raises(ValueError) as excinfo:
        # Create the scorer with column_map mapping 'foo'->'col1', 'bar'->'col3'
        # this is wrong because col3 does not exist
        dummy_scorer = DummyScorer(column_map={"foo": "col1", "bar": "col3"})
        evaluation = Evaluation(dataset=dataset, scorers=[dummy_scorer])
        await evaluation.predict_and_score(model_function, dataset[0])
        assert "which is not in the scorer's argument names" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        # Create the scorer with column_map missing a column
        dummy_scorer = DummyScorer(column_map={"foo": "col1"})
        evaluation = Evaluation(dataset=dataset, scorers=[dummy_scorer])
        await evaluation.predict_and_score(model_function, dataset[0])
        assert "is not found in the dataset columns" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        # Create the scorer with wrong argument name
        dummy_scorer = DummyScorer(column_map={"jeez": "col1"})
        evaluation = Evaluation(dataset=dataset, scorers=[dummy_scorer])
        await evaluation.predict_and_score(model_function, dataset[0])
        assert "is not found in the dataset columns and is not mapped" in str(
            excinfo.value
        )


# Define another dummy scorer
@pytest.mark.asyncio
async def test_evaluation_with_multiple_column_maps():
    class DummyScorer(weave.Scorer):
        @weave.op()
        def score(self, foo: str, bar: str, output: str, target: str) -> dict:
            # Return whether foo + bar equals output
            return {"match": (foo + bar) == output == target}

    class AnotherDummyScorer(weave.Scorer):
        @weave.op()
        def score(self, input1: str, input2: str, output: str) -> dict:
            # Return whether input1 == output reversed
            return {"match": input1 == output[::-1]}

    # First scorer maps 'foo'->'col1', 'bar'->'col2'
    dummy_scorer = DummyScorer(column_map={"foo": "col1", "bar": "col2"})

    # Second scorer maps 'input1'->'col2', 'input2'->'col1'
    another_dummy_scorer = AnotherDummyScorer(
        column_map={"input1": "col2", "input2": "col1"}
    )

    @weave.op()
    def model_function(col1, col2):
        # For testing, return the concatenation of col1 and col2
        return col1 + col2

    dataset = [
        {"col1": "abc", "col2": "def", "target": "abcdef"},
        {"col1": "123", "col2": "456", "target": "1111"},
        {"col1": "xyz", "col2": "zyx", "target": "zzzzzz"},
    ]

    evaluation = Evaluation(
        dataset=dataset, scorers=[dummy_scorer, another_dummy_scorer]
    )

    # Run the evaluation
    eval_out = await evaluation.evaluate(model_function)

    # Check that both scorers are in the results
    assert "DummyScorer" in eval_out
    assert "AnotherDummyScorer" in eval_out

    # Assertions for the first scorer
    expected_results_dummy = {"true_count": 1, "true_fraction": 1.0 / 3}
    assert (
        eval_out["DummyScorer"]["match"] == expected_results_dummy
    ), "All concatenations should match the target"

    # Assertions for the second scorer
    # Since input1 == col2, and output is col1 + col2, we check if col2 == (col1 + col2)[::-1]
    # Evaluate manually:
    # First row: col2 = "def", output = "abcdef", output[::-1] = "fedcba" -> "def" != "fedcba"
    # Second row: col2 = "456", output = "123456", output[::-1] = "654321" -> "456" != "654321"
    # Third row: col2 = "zyx", output = "xyzzyx", output[::-1] = "xyzzyx" -> "zyx" == "xyzzyx" is False
    # So all matches are False
    expected_results_another_dummy = {"true_count": 0, "true_fraction": 0.0}
    assert (
        eval_out["AnotherDummyScorer"]["match"] == expected_results_another_dummy
    ), "No matches should be found for AnotherDummyScorer"


@pytest.mark.asyncio
async def test_feedback_is_correctly_linked(client):
    @weave.op
    def predict(text: str) -> str:
        return text

    @weave.op
    def score(text, model_output) -> bool:
        return text == model_output

    eval = weave.Evaluation(
        dataset=[{"text": "hello"}],
        scorers=[score],
    )
    res = await eval.evaluate(predict)
    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            include_feedback=True,
            filter=tsi.CallsFilter(op_names=[get_ref(predict).uri()]),
        )
    )
    assert len(calls.calls) == 1
    assert calls.calls[0].summary["weave"]["feedback"]
    feedbacks = calls.calls[0].summary["weave"]["feedback"]
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback["feedback_type"] == "wandb.runnable.score"
    assert feedback["payload"] == {"output": True}
    assert feedback["runnable_ref"] == get_ref(score).uri()
    assert (
        feedback["call_ref"]
        == CallRef(
            entity=client.entity,
            project=client.project,
            id=list(score.calls())[0].id,
        ).uri()
    )


@pytest.mark.asyncio
async def test_feedback_is_correctly_linked_with_scorer_subclass(client):
    @weave.op
    def predict(text: str) -> str:
        return text

    class MyScorer(weave.Scorer):
        @weave.op
        def score(self, text, output) -> bool:
            return text == output

    scorer = MyScorer()
    eval = weave.Evaluation(
        dataset=[{"text": "hello"}],
        scorers=[scorer],
    )
    res = await eval.evaluate(predict)
    calls = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            include_feedback=True,
            filter=tsi.CallsFilter(op_names=[get_ref(predict).uri()]),
        )
    )
    assert len(calls.calls) == 1
    assert calls.calls[0].summary["weave"]["feedback"]
    feedbacks = calls.calls[0].summary["weave"]["feedback"]
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback["feedback_type"] == "wandb.runnable.MyScorer"
    assert feedback["payload"] == {"output": True}
    assert feedback["runnable_ref"] == get_ref(scorer).uri()


def test_scorers_with_output_and_model_output_raise_error():
    class MyScorer(weave.Scorer):
        @weave.op
        def score(self, text, output, model_output):
            return text == output == model_output

    @weave.op
    def my_second_scorer(text, output, model_output):
        return text == output == model_output

    ds = [{"text": "hello"}]

    with pytest.raises(
        ValueError, match="cannot include both `output` and `model_output`"
    ):
        scorer = MyScorer()

    with pytest.raises(
        ValueError, match="cannot include both `output` and `model_output`"
    ):
        evaluation = weave.Evaluation(dataset=ds, scorers=[MyScorer()])

    with pytest.raises(
        ValueError, match="cannot include both `output` and `model_output`"
    ):
        evaluation = weave.Evaluation(dataset=ds, scorers=[my_second_scorer])


@pytest.mark.asyncio
async def test_evaluation_with_custom_name(client):
    dataset = weave.Dataset(rows=[{"input": "hi", "output": "hello"}])
    evaluation = weave.Evaluation(dataset=dataset, evaluation_name="wow-custom!")

    @weave.op()
    def model(input: str) -> str:
        return "hmmm"

    await evaluation.evaluate(model)

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) == 1

    call = calls[0]
    assert call.display_name == "wow-custom!"
