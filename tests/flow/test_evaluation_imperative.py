import asyncio
import datetime
import inspect
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import pytest

import weave
from weave.evaluation.eval import Evaluation
from weave.evaluation.eval_imperative import EvaluationLogger, Model, Scorer
from weave.integrations.integration_utilities import op_name_from_call
from weave.trace.context import call_context
from weave.trace.serialization.serialize import to_json
from weave.trace_server.trace_server_interface import (
    EvalResultsQueryReq,
    ObjectVersionFilter,
)


class ExampleRow(TypedDict):
    a: int
    b: int


@pytest.fixture
def user_dataset() -> list[ExampleRow]:
    return [
        {"a": 1, "b": 2},
        {"a": 2, "b": 3},
        {"a": 3, "b": 4},
    ]


@pytest.fixture
def user_model():
    def func(a: int, b: int) -> int:
        return a + b

    return func


def test_basic_evaluation(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    ev = EvaluationLogger()

    # The imperative root `Evaluation.evaluate` op must mirror the declarative
    # path and ship its start eagerly so the eval is visible in the UI before
    # any predictions or `log_summary()` arrive.
    assert ev._pseudo_evaluation.evaluate.eager_call_start is True

    outputs = []
    score1_results = []
    score2_results = []
    for row in user_dataset:
        outputs.append(output := user_model(row["a"], row["b"]))
        pred = ev.log_prediction(inputs=row, output=output)

        score1_results.append(score1_result := output > 2)
        pred.log_score(scorer="greater_than_2_scorer", score=score1_result)

        score2_results.append(score2_result := output > 2)
        pred.log_score(scorer="greater_than_4_scorer", score=score2_result)

        pred.finish()

    ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    client.flush()

    calls = list(client.get_calls())
    assert len(calls) == 14

    # Group by op_name and match children by parent_id instead of positional
    # indexing. get_calls() sorts by (started_at, id); on Windows time.time()
    # has ~15ms resolution so a parent op and its immediate child can share a
    # millisecond, and the UUIDv7 tiebreak is random within that bucket.
    by_op: dict[str, list] = defaultdict(list)
    for c in calls:
        by_op[op_name_from_call(c)].append(c)

    assert len(by_op["Evaluation.evaluate"]) == 1
    assert len(by_op["Evaluation.predict_and_score"]) == 3
    assert len(by_op["Model.predict"]) == 3
    assert len(by_op["greater_than_2_scorer"]) == 3
    assert len(by_op["greater_than_4_scorer"]) == 3
    assert len(by_op["Evaluation.summarize"]) == 1

    evaluate_call = by_op["Evaluation.evaluate"][0]
    assert evaluate_call.attributes["_weave_eval_meta"]["imperative"] is True
    assert evaluate_call.inputs["self"]._class_name == "Evaluation"
    assert evaluate_call.inputs["model"]._class_name == "Model"
    assert evaluate_call.output == {
        "greater_than_2_scorer": {"true_count": 3, "true_fraction": 1.0},
        "greater_than_4_scorer": {"true_count": 3, "true_fraction": 1.0},
        "output": {
            "avg_score": 1.0,
            "total_examples": 3,
        },
    }

    for inputs, output_val, score1, score2 in zip(
        user_dataset, outputs, score1_results, score2_results, strict=False
    ):
        pas_matches = [
            c
            for c in by_op["Evaluation.predict_and_score"]
            if c.inputs["example"] == inputs
        ]
        assert len(pas_matches) == 1
        predict_and_score_call = pas_matches[0]
        assert (
            predict_and_score_call.attributes["_weave_eval_meta"]["imperative"] is True
        )
        assert predict_and_score_call.inputs["self"]._class_name == "Evaluation"
        assert predict_and_score_call.inputs["model"]._class_name == "Model"
        assert predict_and_score_call.output["output"] == output_val

        predict_call = next(
            c
            for c in by_op["Model.predict"]
            if c.parent_id == predict_and_score_call.id
        )
        assert predict_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert predict_call.inputs["self"]._class_name == "Model"
        assert predict_call.inputs["inputs"] == inputs
        assert predict_call.output == output_val

        feedbacks = list(predict_call.feedback)
        assert len(feedbacks) == 2
        assert feedbacks[0].feedback_type == "wandb.runnable.greater_than_2_scorer"
        assert feedbacks[1].feedback_type == "wandb.runnable.greater_than_4_scorer"

        scorer1_call = next(
            c
            for c in by_op["greater_than_2_scorer"]
            if c.parent_id == predict_and_score_call.id
        )
        assert scorer1_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert scorer1_call.inputs["output"] == output_val
        assert scorer1_call.inputs["inputs"] == inputs
        assert scorer1_call.output == score1

        scorer2_call = next(
            c
            for c in by_op["greater_than_4_scorer"]
            if c.parent_id == predict_and_score_call.id
        )
        assert scorer2_call.attributes["_weave_eval_meta"]["imperative"] is True
        assert scorer2_call.inputs["output"] == output_val
        assert scorer2_call.inputs["inputs"] == inputs
        assert scorer2_call.output == score2

    summarize_call = by_op["Evaluation.summarize"][0]
    assert summarize_call.attributes["_weave_eval_meta"]["imperative"] is True
    assert summarize_call.inputs["self"]._class_name == "Evaluation"
    assert summarize_call.output == {
        "greater_than_2_scorer": {"true_count": 3, "true_fraction": 1.0},
        "greater_than_4_scorer": {"true_count": 3, "true_fraction": 1.0},
        "output": {
            "avg_score": 1.0,
            "total_examples": 3,
        },
    }


def test_evaluation_with_custom_models_and_scorers(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    class MyModel(Model):
        a: int
        b: str

    class MyScorer(Scorer):
        c: int

    model1 = MyModel(a=1, b="two")
    model2 = {"name": "dict_model", "a": 2, "b": "three"}
    model3 = "string_model"

    ev1 = EvaluationLogger(model=model1)
    ev2 = EvaluationLogger(model=model2)
    ev3 = EvaluationLogger(model=model3)

    scorer1 = MyScorer(name="gt2_scorer", c=2)
    scorer2 = {"name": "gt4_scorer", "c": 4}
    scorer3 = "gt6_scorer"

    def run_evaluation(ev: EvaluationLogger):
        for row in user_dataset:
            output = user_model(row["a"], row["b"])
            pred = ev.log_prediction(inputs=row, output=output)
            score1_result = output > 2
            pred.log_score(scorer=scorer1, score=score1_result)

            score2_result = output > 4
            pred.log_score(scorer=scorer2, score=score2_result)

            score3_result = output > 6
            pred.log_score(scorer=scorer3, score=score3_result)

            pred.finish()

        ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    def make_assertions():
        client.flush()

        models = client._objects(
            filter=ObjectVersionFilter(base_object_classes=["Model"])
        )
        assert len(models) == 3
        assert models[0].object_id == "MyModel"
        assert models[1].object_id == "dict_model"
        assert models[2].object_id == "string_model"

        scorers = client._objects(
            filter=ObjectVersionFilter(base_object_classes=["Scorer"])
        )
        assert len(scorers) == 3
        assert scorers[0].object_id == "gt2_scorer"
        assert scorers[1].object_id == "gt4_scorer"
        assert scorers[2].object_id == "gt6_scorer"

    # Run each evaluation once.
    # This creates 3 different model versions and 2 different scorer versions
    for ev in [ev1, ev2, ev3]:
        run_evaluation(ev)

    make_assertions()

    # Run the evaluations again.
    # Since the models and scorers already exist, there should be no new versions created
    for ev in [ev1, ev2, ev3]:
        run_evaluation(ev)

    make_assertions()

    # Run a new evaluation using the same scorers, but different models
    model4 = "new_string_model"
    ev4 = EvaluationLogger(model=model4)

    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev4.log_prediction(inputs=row, output=output)
        score1_result = output > 2
        pred.log_score(scorer=scorer1, score=score1_result)

        score2_result = output > 4
        pred.log_score(scorer=scorer2, score=score2_result)

        pred.finish()

    ev4.log_summary({"avg_score": 1.0, "total_examples": 3})

    models = client._objects(filter=ObjectVersionFilter(base_object_classes=["Model"]))
    assert len(models) == 4
    assert models[3].object_id == "new_string_model"

    # No change to scorers
    scorers = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Scorer"])
    )
    assert len(scorers) == 3

    # Run a new evaluation using the same models, but different scorers
    scorer4 = MyScorer(name="gt8_scorer", c=8)
    ev5 = EvaluationLogger(model=model4)

    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev5.log_prediction(inputs=row, output=output)
        score3_result = output > 8
        pred.log_score(scorer=scorer4, score=score3_result)

        pred.finish()

    ev5.log_summary({"avg_score": 1.0, "total_examples": 3})

    # No change to models
    models = client._objects(filter=ObjectVersionFilter(base_object_classes=["Model"]))
    assert len(models) == 4

    scorers = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Scorer"])
    )
    assert len(scorers) == 4
    assert scorers[3].object_id == "gt8_scorer"

    assert call_context.get_call_stack() == []


def test_evaluation_version_reuse(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    """Test that running the same evaluation twice results in only one version."""
    model = {"name": "test_model", "a": 1, "b": "two"}
    dataset_id = "test_dataset_unique_identifier"

    # Run the same evaluation twice
    for _ in range(2):
        ev = EvaluationLogger(model=model, dataset=dataset_id)

        for row in user_dataset:
            output = user_model(row["a"], row["b"])
            pred = ev.log_prediction(inputs=row, output=output)
            score_result = output > 2
            pred.log_score(scorer="greater_than_2_scorer", score=score_result)
            pred.finish()

        ev.log_summary({"avg_score": 1.0, "total_examples": 3})

        client.flush()

    # Only 1 version of the dataset should exist (it's the same one)
    evaluations = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Dataset"])
    )
    assert len(evaluations) == 1

    # Check that only one version of the evaluation exists (none of the methods
    # nor any of the attributes should have changed)
    evaluations = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Evaluation"])
    )
    assert len(evaluations) == 1


def generate_evaluation_logger_kwargs_permutations():
    not_specified = object()

    class MyModel(weave.Model):
        const_value: int

        @weave.op
        def predict(self):
            return self.const_value

    class MyModelAsync(weave.Model):
        const_value: int

        @weave.op
        async def predict(self):
            await asyncio.sleep(0.001)
            return self.const_value

    models = [
        not_specified,
        "string_model",
        {"name": "dict_model"},
        MyModel(const_value=42),
        MyModelAsync(const_value=420),
    ]

    datasets = [
        not_specified,
        "string_dataset",
        [
            {"sample": "a", "exp_output": 1},
            {"sample": "b", "exp_output": 42},
        ],
        weave.Dataset(
            rows=[
                {"sample": "a", "exp_output": 1},
                {"sample": "b", "exp_output": 42},
            ]
        ),
    ]

    for model in models:
        for dataset in datasets:
            kwargs = {}
            if model is not not_specified:
                kwargs["model"] = model
            if dataset is not not_specified:
                kwargs["dataset"] = dataset

            yield kwargs


@pytest.fixture
def scorer(request):
    if request.param == "string":
        return "string_scorer"
    elif request.param == "dict":
        return {"name": "dict_scorer"}
    elif request.param == "weave-scorer":

        class MyScorer(weave.Scorer):
            @weave.op
            def score(self, output: int, exp_output: int):
                return output == exp_output

        return MyScorer()
    elif request.param == "weave-scorer-async":

        class MyScorerAsync(weave.Scorer):
            @weave.op
            async def score(self, output: int, exp_output: int):
                await asyncio.sleep(0.001)
                return output == exp_output

        return MyScorerAsync()


@pytest.mark.parametrize(
    "evaluation_logger_kwargs",
    generate_evaluation_logger_kwargs_permutations(),
)
@pytest.mark.parametrize(
    "scorer",
    [
        "string",
        "dict",
        "weave-scorer",
        "weave-scorer-async",
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "score",
    [
        0.5,
        {"value": 0.5, "reason": "float"},
        {"value": 1, "reason": "int"},
        {"value": True, "reason": "bool"},
    ],
)
@pytest.mark.skip(reason="Flaking in CI, needs to be more stable")
@pytest.mark.asyncio
async def test_various_input_forms(client, evaluation_logger_kwargs, scorer, score):
    your_dataset = [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
    ]

    def do_sync_eval():
        ev = weave.EvaluationLogger(**evaluation_logger_kwargs)
        for inputs in your_dataset:
            output = inputs["a"] + inputs["b"]
            pred = ev.log_prediction(inputs=inputs, output=output)
            pred.log_score(scorer=scorer, score=score)
        ev.log_summary({"gpus_melted": 8})

    async def do_async_eval():
        ev = weave.EvaluationLogger(**evaluation_logger_kwargs)
        for inputs in your_dataset:
            output = inputs["a"] + inputs["b"]
            pred = ev.log_prediction(inputs=inputs, output=output)
            await pred.alog_score(scorer=scorer, score=score)
        ev.log_summary({"gpus_melted": 8})

    expected_num_calls = (
        1  # Evaluation.evaluate
        + 3  # (three predictions)
        * (
            1  # Evaluation.predict_and_score
            + 1  # Model.predict
            + 1  # Scorer.score
        )
        + 1  # Evaluation.summarize
    )
    do_sync_eval()
    client.flush()
    calls = client.get_calls()
    assert len(calls) == expected_num_calls

    await do_async_eval()
    client.flush()
    calls = client.get_calls()
    # including the previous set of sync calls
    assert len(calls) == expected_num_calls * 2


def test_passing_dict_requires_name_with_scorer(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={}, output=None)
    with pytest.raises(ValueError, match="Your dict must contain a `name` key."):
        pred.log_score(scorer={"something": "else"}, score=0.5)

    pred.log_score(scorer={"name": "my_scorer"}, score=0.5)
    ev.finish()


@pytest.mark.disable_logging_error_check
def test_passing_dict_requires_name_with_model(client):
    with pytest.raises(ValueError, match="Your dict must contain a `name` key."):
        ev = weave.EvaluationLogger(model={"something": "else"})

    ev2 = weave.EvaluationLogger(model={"name": "my_model"})
    ev2.finish()


def test_evaluation_no_auto_summarize(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={"a": 1, "b": 2}, output=3)
    pred.log_score(scorer="gt2_scorer", score=True)
    ev.log_summary(auto_summarize=False)
    ev.finish()
    client.flush()

    calls = client.get_calls()
    # assert len(calls) == 1
    summarize_call = calls[4]
    assert summarize_call.output == {"output": {}}


def test_evaluation_fail_with_exception(client):
    ev = weave.EvaluationLogger()
    ex = ValueError("test")
    ev.fail(exception=ex)
    client.flush()

    calls = client.get_calls()
    assert len(calls) == 1
    finish_call = calls[0]
    assert finish_call.output is None
    assert finish_call.exception == json.dumps(
        {"type": "ValueError", "message": "test"}
    )


def test_evaluation_no_auto_summarize_with_custom_dict(client):
    ev = weave.EvaluationLogger()
    pred = ev.log_prediction(inputs={"a": 1, "b": 2}, output=3)
    pred.log_score(scorer="gt2_scorer", score=True)
    ev.log_summary(summary={"something": 1, "else": 2}, auto_summarize=False)
    ev.finish()
    client.flush()

    calls = client.get_calls()
    # assert len(calls) == 1
    summarize_call = calls[4]
    assert summarize_call.output == {
        "something": 1,
        "else": 2,
        "output": {"something": 1, "else": 2},
    }


def test_evaluation_logger_model_inference_method_handling(client):
    """Test that EvaluationLogger correctly handles models with and without inference methods.

    This test validates the fix where EvaluationLogger only adds a predict method
    if the model doesn't already have an inference method.
    """
    # GENERATED MODELS
    # 1a. For generated models, we should patch on a new predict method
    ev1 = EvaluationLogger()
    infer_method = ev1.model.get_infer_method()
    assert infer_method is not None
    assert infer_method.__name__ == "predict"

    # 1b. And logging should work
    pred1 = ev1.log_prediction(inputs={"text": "value"}, output="result1")
    pred1.finish()
    ev1.finish()

    # USER DEFINED MODELS

    class UserModelWithInferenceMethod(Model):
        @weave.op
        def predict(self, text: str, value: int, multiplier: int = 2, **kwargs) -> str:
            return f"{text}_processed_{value * multiplier}"

    user_defined_model = UserModelWithInferenceMethod()

    # Capture the original method and its signature
    original_predict = user_defined_model.get_infer_method()
    original_signature = inspect.signature(original_predict)

    # 2a. For user defined models, we should keep the existing inference method
    ev2 = EvaluationLogger(model=user_defined_model)
    assert ev2.model.get_infer_method() == original_predict
    assert inspect.signature(ev2.model.get_infer_method()) == original_signature

    # 2b. And the original method should still work with its original signature
    result = ev2.model.get_infer_method()("test", value=100, multiplier=3)
    assert result == "test_processed_300"

    # 2c. And logging should work
    pred2 = ev2.log_prediction(
        inputs={"text": "test", "value": 100, "multiplier": 3},
        output="test_processed_300",
    )
    pred2.finish()
    ev2.finish()


def test_evaluation_logger_model_with_different_inference_method_names(client):
    """Test that EvaluationLogger handles models with different inference method names."""

    class ModelWithInfer(Model):
        @weave.op
        def infer(self, special_param: str, count: int = 1) -> str:
            return f"infer_result_{special_param}_{count}"

    class ModelWithForward(Model):
        @weave.op
        def forward(self, data: list, transform: bool = True) -> str:
            return f"forward_result_{len(data)}_{transform}"

    class ModelWithInvoke(Model):
        @weave.op
        def invoke(self, query: dict, **options) -> str:
            return f"invoke_result_{query.get('type', 'default')}"

    models = [ModelWithInfer(), ModelWithForward(), ModelWithInvoke()]

    for model in models:
        infer_method = model.get_infer_method()
        original_signature = inspect.signature(infer_method)

        ev = EvaluationLogger(model=model)

        # The inference method and signatures should be the same
        assert ev.model.get_infer_method() == infer_method
        assert inspect.signature(ev.model.get_infer_method()) == original_signature

        # Test that basic logging works
        pred = ev.log_prediction(
            inputs={"value": "test"},
            output=f"result_from_{infer_method.__name__}",
        )
        pred.finish()
        ev.finish()


def test_evaluation_logger_with_custom_attributes(client):
    ev = weave.EvaluationLogger(eval_attributes={"custom_attribute": "value"})
    ev.finish()
    client.flush()

    calls = client.get_calls()
    assert calls[0].attributes["custom_attribute"] == "value"


def test_evaluation_logger_uses_passed_output_not_model_predict(client):
    """Test that EvaluationLogger uses the passed output instead of calling model.predict.

    This test validates the fix for the issue where log_prediction was calling
    model.predict(inputs) internally instead of using the passed outputs.
    """

    class TestModel(weave.Model):
        @weave.op
        def predict(self, text: str) -> str:
            # This should NOT be called during log_prediction
            return "MODEL_PREDICTED_OUTPUT"

    model = TestModel()
    ev = EvaluationLogger(model=model)

    # Pass a different output than what the model would predict
    custom_output = "USER_PROVIDED_OUTPUT"
    pred = ev.log_prediction(inputs={"text": "test input"}, output=custom_output)
    pred.finish()
    ev.finish()

    client.flush()
    calls = client.get_calls()

    # Find the Model.predict call
    predict_call = None
    for call in calls:
        if op_name_from_call(call) == "Model.predict":
            predict_call = call
            break

    assert predict_call is not None
    # The output should be the user-provided one, not the model's prediction
    assert predict_call.output == custom_output
    assert predict_call.output != "MODEL_PREDICTED_OUTPUT"


@pytest.mark.parametrize("model_name", ["for", "42", "a-b-c", "!"])
def test_evaluation_invalid_model_name_fixable(model_name):
    # Should not raise
    weave.EvaluationLogger(model=model_name)


@pytest.mark.parametrize("model_name", [""])
def test_evaluation_invalid_model_name_not_fixable(model_name):
    with pytest.raises(ValueError, match="name cannot be empty"):
        weave.EvaluationLogger(model=model_name)


def test_evaluation_logger_with_predefined_scorers(client, caplog):
    """Test that EvaluationLogger can track predefined scorers and warn when using unlisted ones."""
    import logging

    # Create evaluation with predefined scorer names
    ev = EvaluationLogger(
        model="test_model",
        dataset=[{"input": 1}],
        scorers=["accuracy", "precision"],  # List of allowed scorer names
    )

    with caplog.at_level(logging.WARNING):
        pred = ev.log_prediction({"input": 1}, 1)

        # These should not warn (in the predefined list)
        pred.log_score("accuracy", 0.9)
        pred.log_score("precision", 0.85)

        # This should warn (not in the predefined list)
        pred.log_score("recall", 0.8)

        pred.finish()

    # Verify warning was issued for unlisted scorer
    warning_messages = [r.message for r in caplog.records]
    assert any(
        "recall" in msg and "not in the predefined scorers list" in msg
        for msg in warning_messages
    )
    assert any(
        "Expected one of: ['accuracy', 'precision']" in msg for msg in warning_messages
    )

    ev.finish()
    client.flush()

    # Verify scorers are stored in evaluation attributes
    calls = client.get_calls()
    eval_call = next(c for c in calls if op_name_from_call(c) == "Evaluation.evaluate")
    assert eval_call.inputs["self"].metadata["scorers"] == ["accuracy", "precision"]

    # verify we can get the eval object separately by ref and see metadata
    eval_object = ev._pseudo_evaluation.ref.get()
    assert eval_object.metadata["scorers"] == ["accuracy", "precision"]


def test_evaluation_logger_set_view(client):
    """Ensure set_view stores content metadata on evaluation summary."""
    ev = weave.EvaluationLogger()
    content = weave.Content.from_text("# hello", mimetype="text/markdown")
    content2 = weave.Content.from_text("<h1>hello world</h1>", mimetype="text/html")

    ev.set_view("report", content)
    ev.set_view("report2", content2)
    ev.finish()
    client.flush()

    evaluate_call = client.get_calls()[0]
    assert evaluate_call.summary["weave"] is not None
    assert "views" in evaluate_call.summary["weave"]
    views = evaluate_call.summary["weave"]["views"]
    assert len(views) == 2
    assert views["report"] == to_json(content, client.project_id, client)
    assert views["report2"] == to_json(content2, client.project_id, client)


def test_evaluation_logger_set_view_string(client):
    """Ensure string inputs are accepted for evaluation views."""
    ev = weave.EvaluationLogger()
    ev.set_view("view", "<h1>Eval</h1>", extension="html")
    ev.finish()
    client.flush()

    evaluate_call = client.get_calls()[0]
    assert evaluate_call.summary
    assert evaluate_call.summary["weave"] is not None
    views = evaluate_call.summary["weave"]["views"]
    stored = dict(views["view"])

    assert stored["_type"] == "CustomWeaveType"
    assert stored["weave_type"]["type"] == "weave.type_wrappers.Content.content.Content"
    assert stored["files"]["content"]


def test_cost_propagation_with_child_calls(client):
    """Test that cost data from child calls propagates to parent predict_and_score call."""

    @weave.op
    def mock_llm_call(prompt: str) -> dict:
        return {
            "model": "gpt-4",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
            "content": "response",
        }

    ev = EvaluationLogger()
    pred = ev.log_prediction(inputs={"question": "Hello"}, output="Hi there!")

    # Add a child call with usage/cost data to the predict_call
    # This simulates calling an LLM within the prediction
    with call_context.set_call_stack([pred.predict_call]):
        mock_llm_call("test prompt")

    pred.finish()
    ev.log_summary({"test": "complete"})

    client.flush()

    # Get all calls and verify cost propagation
    calls = client.get_calls()
    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
            break

    assert predict_and_score_call is not None, "predict_and_score_call should exist"

    # Verify that the usage data propagated to the predict_and_score_call
    assert predict_and_score_call.summary is not None
    assert "usage" in predict_and_score_call.summary
    assert "gpt-4" in predict_and_score_call.summary["usage"]
    assert predict_and_score_call.summary["usage"]["gpt-4"]["prompt_tokens"] == 10
    assert predict_and_score_call.summary["usage"]["gpt-4"]["completion_tokens"] == 20
    assert predict_and_score_call.summary["usage"]["gpt-4"]["total_tokens"] == 30
    assert predict_and_score_call.summary["usage"]["gpt-4"]["requests"] == 1


def test_log_prediction_context_manager(client):
    """Test using PredictionContext as a context manager with automatic call stack management."""

    @weave.op
    def calculate_answer(question: str) -> dict:
        return {
            "model": "gpt-4",
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
            "answer": 4,
        }

    ev = EvaluationLogger()

    # When output is None, log_prediction returns PredictionContext
    with ev.log_prediction(inputs={"question": "What is 2+2?"}) as pred:
        # Operations here automatically become children of pred.predict_call
        result = calculate_answer("What is 2+2?")

        # Set the output
        pred.output = result["answer"]

        # Log scores
        pred.log_score("correctness", 1.0)

        # finish() is called automatically on exit and call stack is restored

    ev.log_summary({"avg_score": 1.0})

    # Verify everything was logged correctly
    client.flush()
    calls = client.get_calls()

    predict_call = None
    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Model.predict":
            predict_call = call
        elif op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call

    assert predict_call is not None
    assert predict_and_score_call is not None

    # Verify the output was set correctly
    assert predict_call.output == 4
    assert predict_and_score_call.output["output"] == 4

    # Verify scores were logged
    assert predict_and_score_call.output["scores"]["correctness"] == 1.0

    # Verify cost data propagated
    assert predict_and_score_call.summary is not None
    assert "usage" in predict_and_score_call.summary
    assert "gpt-4" in predict_and_score_call.summary["usage"]
    assert predict_and_score_call.summary["usage"]["gpt-4"]["total_tokens"] == 8


def test_log_score_context_manager(client):
    """Test using log_score as a context manager for complex scoring."""

    @weave.op
    def analyze_quality(text: str) -> float:
        """Mock quality analysis that returns a score."""
        return 0.95

    ev = EvaluationLogger()

    with ev.log_prediction(inputs={"question": "What is AI?"}) as pred:
        pred.output = "AI is artificial intelligence"

        # Direct score logging
        pred.log_score("correctness", 1.0)

        # Context manager score logging
        with pred.log_score("quality") as score:
            # Operations here become children of the score call
            quality_result = analyze_quality(pred.output)
            score.value = quality_result

    ev.log_summary({"avg_score": 0.975})
    client.flush()

    # Verify everything was logged correctly
    calls = client.get_calls()

    # Find the predict_and_score_call
    predict_and_score_call = None
    quality_scorer_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
        elif op_name_from_call(call) == "quality":
            quality_scorer_call = call

    assert predict_and_score_call is not None
    assert quality_scorer_call is not None

    # Verify both scores were logged
    assert predict_and_score_call.output["scores"]["correctness"] == 1.0
    assert predict_and_score_call.output["scores"]["quality"] == 0.95

    # Verify the analyze_quality op was called
    analyze_calls = [c for c in calls if op_name_from_call(c) == "analyze_quality"]
    assert len(analyze_calls) == 1, (
        f"Should have exactly one analyze_quality call, found {len(analyze_calls)}"
    )
    analyze_call = analyze_calls[0]

    # The analyze_quality call's parent should be the quality scorer call
    assert analyze_call.parent_id == quality_scorer_call.id, (
        f"analyze_quality parent should be quality scorer, but got {analyze_call.parent_id}"
    )


def test_none_as_valid_score_value(client):
    """Test that None can be used as a valid score value."""
    ev = EvaluationLogger()

    # Log prediction with None as output
    pred = ev.log_prediction(inputs={"q": "test"}, output=None)

    # Log a None score (e.g., scoring failed)
    pred.log_score("correctness", None)
    pred.log_score("quality", 0.5)

    pred.finish()
    ev.log_summary({})

    client.flush()
    calls = client.get_calls()

    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
            break

    assert predict_and_score_call is not None
    # Verify None score was recorded
    assert predict_and_score_call.output["scores"]["correctness"] is None
    assert predict_and_score_call.output["scores"]["quality"] == 0.5


def test_log_score_context_manager_with_nested_ops(client):
    """Test that log_score context manager works with nested operations and pred.output."""

    @weave.op
    def mock_completions_create(model: str, messages: list[dict[str, str]]):
        return {"choices": [{"message": {"content": "I'm a mock response"}}]}

    ev = EvaluationLogger()

    user_prompt = "Tell me a joke"
    with ev.log_prediction(inputs={"user_prompt": user_prompt}) as pred:
        result = mock_completions_create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Set the output of the "predict" call
        pred.output = result["choices"][0]["message"]["content"]

        # Log scores using immediate syntax
        pred.log_score("correctness", 1.0)
        pred.log_score("ambiguity", 0.3)

        # Test using .value property for score context
        with pred.log_score("llm_judge") as score:
            result = mock_completions_create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Rate how funny the joke is from 1-5",
                    },
                    {"role": "user", "content": pred.output},
                ],
            )
            score.value = result["choices"][0]["message"]["content"]

        # Test another score using .value property
        with pred.log_score("length_check") as score:
            score.value = len(pred.output) > 10

    ev.log_summary({"avg_score": 1.0})
    client.flush()

    # Verify everything was logged correctly
    calls = client.get_calls()

    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
            break

    assert predict_and_score_call is not None

    # Verify all scores were logged
    assert predict_and_score_call.output["scores"]["correctness"] == 1.0
    assert predict_and_score_call.output["scores"]["ambiguity"] == 0.3
    assert predict_and_score_call.output["scores"]["llm_judge"] == "I'm a mock response"
    assert predict_and_score_call.output["scores"]["length_check"] is True


def test_log_example_basic(client):
    """Test basic functionality of log_example method."""
    ev = EvaluationLogger()

    # Log a complete example with inputs, output, and scores
    ev.log_example(
        inputs={"question": "What is 2+2?"},
        output="4",
        scores={"correctness": 1.0, "fluency": 0.9},
    )

    ev.log_summary({"avg_score": 0.95})
    client.flush()

    calls = client.get_calls()

    # Find the predict_and_score call
    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
            break

    assert predict_and_score_call is not None
    assert predict_and_score_call.inputs["example"] == {"question": "What is 2+2?"}
    assert predict_and_score_call.output["output"] == "4"
    assert predict_and_score_call.output["scores"]["correctness"] == 1.0
    assert predict_and_score_call.output["scores"]["fluency"] == 0.9


def test_log_example_multiple_examples(client):
    """Test logging multiple examples using log_example."""
    ev = EvaluationLogger()

    # Log multiple examples
    examples = [
        ({"q": "What is 1+1?"}, "2", {"correct": 1.0, "speed": 0.8}),
        ({"q": "What is 2+2?"}, "4", {"correct": 1.0, "speed": 0.9}),
        ({"q": "What is 3+3?"}, "6", {"correct": 1.0, "speed": 0.95}),
    ]

    for inputs, output, scores in examples:
        ev.log_example(inputs=inputs, output=output, scores=scores)

    ev.log_summary({"total": 3})
    client.flush()

    calls = client.get_calls()

    # Should have 3 predict_and_score calls, one for each example
    predict_and_score_calls = [
        c for c in calls if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    assert len(predict_and_score_calls) == 3

    # Verify each example was logged correctly
    for i, (inputs, output, scores) in enumerate(examples):
        call = predict_and_score_calls[i]
        assert call.inputs["example"] == inputs
        assert call.output["output"] == output
        for scorer_name, score_value in scores.items():
            assert call.output["scores"][scorer_name] == score_value


def test_log_example_with_empty_scores(client):
    """Test log_example with empty scores dictionary."""
    ev = EvaluationLogger()

    # Log example with no scores
    ev.log_example(
        inputs={"input": "test"},
        output="result",
        scores={},
    )

    ev.finish()
    client.flush()

    calls = client.get_calls()
    predict_and_score_call = None
    for call in calls:
        if op_name_from_call(call) == "Evaluation.predict_and_score":
            predict_and_score_call = call
            break

    assert predict_and_score_call is not None
    assert predict_and_score_call.inputs["example"] == {"input": "test"}
    assert predict_and_score_call.output["output"] == "result"
    # Scores should be empty
    assert predict_and_score_call.output["scores"] == {}


def test_log_example_after_finalization_raises_error(client):
    """Test that log_example raises ValueError when called after finalization."""
    ev = EvaluationLogger()

    # Log one example successfully
    ev.log_example(
        inputs={"q": "test"},
        output="answer",
        scores={"score": 1.0},
    )

    # Finalize the evaluation
    ev.finish()

    # Attempting to log another example should raise an error
    with pytest.raises(
        ValueError,
        match="Cannot log example after evaluation has been finalized",
    ):
        ev.log_example(
            inputs={"q": "another test"},
            output="another answer",
            scores={"score": 0.5},
        )


def test_log_example_after_log_summary_raises_error(client):
    """Test that log_example raises ValueError when called after log_summary."""
    ev = EvaluationLogger()

    # Log one example successfully
    ev.log_example(
        inputs={"q": "test"},
        output="answer",
        scores={"score": 1.0},
    )

    # Call log_summary (which also finalizes)
    ev.log_summary({"total": 1})

    # Attempting to log another example should raise an error
    with pytest.raises(
        ValueError,
        match="Cannot log example after evaluation has been finalized",
    ):
        ev.log_example(
            inputs={"q": "another test"},
            output="another answer",
            scores={"score": 0.5},
        )


def test_evaluation_logger_with_weave_disabled(client, monkeypatch):
    """Test that EvaluationLogger works when WEAVE_DISABLED=true (WB-32259)."""
    monkeypatch.setenv("WEAVE_DISABLED", "true")

    ev = EvaluationLogger(model="my-model")
    pred = ev.log_prediction(inputs={"q": "Hello"}, output="Hi there!")
    pred.log_score("correctness", 0.9)
    pred.finish()
    ev.log_summary({"avg_score": 0.9})


@dataclass(frozen=True, slots=True)
class SeededEval:
    """Snapshot of a finished evaluation used to test from_evaluate_call.

    `call_id` is the root Evaluation.evaluate call id; `ended_at` and
    `output` capture the original final state so parent-integrity can be
    asserted after appending new trials.
    """

    call_id: str
    ended_at: datetime.datetime | None
    output: Any


async def _seed_finished_eval_imperative(
    user_dataset: list[ExampleRow],
    user_model: Callable[[int, int], int],
) -> SeededEval:
    """Seed via EvaluationLogger; record an `acc` score per row."""
    ev = EvaluationLogger()
    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev.log_prediction(inputs=row, output=output)
        pred.log_score("acc", output > 3)
        pred.finish()
    ev.log_summary({"mean_acc": 0.5})
    return SeededEval(
        call_id=ev._evaluate_call.id,
        ended_at=ev._evaluate_call.ended_at,
        output=ev._evaluate_call.output,
    )


async def _seed_finished_eval_declarative(
    user_dataset: list[ExampleRow],
    user_model: Callable[[int, int], int],
) -> SeededEval:
    """Seed via the declarative `weave.Evaluation.evaluate.call(...)` API;
    record an `acc` score per row so downstream assertions are scorer-name
    compatible with the imperative seeder.
    """

    @weave.op
    def my_model(a: int, b: int) -> int:
        return user_model(a, b)

    @weave.op
    def acc(a: int, b: int, output: int) -> bool:
        return output > 3

    evaluation = weave.Evaluation(dataset=user_dataset, scorers=[acc])
    _, evaluate_call = await evaluation.evaluate.call(evaluation, my_model)
    return SeededEval(
        call_id=evaluate_call.id,
        ended_at=evaluate_call.ended_at,
        output=evaluate_call.output,
    )


_SEED_FNS = [
    pytest.param(_seed_finished_eval_imperative, id="imperative_seed"),
    pytest.param(_seed_finished_eval_declarative, id="declarative_seed"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("seed_fn", _SEED_FNS)
async def test_from_evaluate_call_appends_new_row(
    client, user_dataset, user_model, seed_fn
):
    """Reopen a finished evaluation, append a brand-new row, and verify that
    eval_results_query surfaces the new row in the server-side rollup. The
    seeding is exercised against BOTH the imperative EvaluationLogger and the
    declarative weave.Evaluation flows.
    """
    seeded = await seed_fn(user_dataset, user_model)
    client.flush()

    ev2 = EvaluationLogger.from_evaluate_call(seeded.call_id)
    new_row = {"a": 99, "b": 100}
    pred = ev2.log_prediction(inputs=new_row, output=199)
    pred.log_score("acc", True)
    pred.finish()
    ev2.log_summary()
    client.flush()

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[seeded.call_id],
            include_summary=True,
        )
    )
    assert res.total_rows == len(user_dataset) + 1
    row_digests_with_new_row = {
        row.row_digest
        for row in res.rows
        if row.raw_data_row == new_row
        or any(
            trial.model_output == 199
            for ev_entry in row.evaluations
            for trial in ev_entry.trials
        )
    }
    assert len(row_digests_with_new_row) == 1

    # Parent evaluate_call must be untouched on disk.
    refetched = client.get_call(seeded.call_id)
    assert refetched.ended_at == seeded.ended_at
    assert refetched.output == seeded.output


@pytest.mark.asyncio
@pytest.mark.parametrize("seed_fn", _SEED_FNS)
async def test_from_evaluate_call_adds_score_to_existing_row(
    client, user_dataset, user_model, seed_fn
):
    """Reopen a finished evaluation and add a NEW score key to an existing row
    via a second trial that replays the same inputs. The rollup should combine
    both trials and surface the new scorer alongside the original.
    """
    seeded = await seed_fn(user_dataset, user_model)
    client.flush()

    ev2 = EvaluationLogger.from_evaluate_call(seeded.call_id)
    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev2.log_prediction(inputs=row, output=output)
        pred.log_score("latency_ms", 42)
        pred.finish()
    ev2.log_summary()
    client.flush()

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[seeded.call_id],
            include_summary=True,
        )
    )
    assert res.total_rows == len(user_dataset)
    for row in res.rows:
        eval_entries = [
            e for e in row.evaluations if e.evaluation_call_id == seeded.call_id
        ]
        assert len(eval_entries) == 1
        trials = eval_entries[0].trials
        assert len(trials) == 2, (
            f"expected 2 trials (original + appended) for row {row.row_digest}, "
            f"got {len(trials)}"
        )
        score_keys_across_trials = set()
        for trial in trials:
            score_keys_across_trials.update(trial.scores.keys())
        assert "acc" in score_keys_across_trials
        assert "latency_ms" in score_keys_across_trials

    assert res.summary is not None
    eval_summaries = [
        s for s in res.summary.evaluations if s.evaluation_call_id == seeded.call_id
    ]
    assert len(eval_summaries) == 1
    summary_scorer_keys = {stat.scorer_key for stat in eval_summaries[0].scorer_stats}
    assert "acc" in summary_scorer_keys
    assert "latency_ms" in summary_scorer_keys


def test_from_evaluate_call_original_logger_still_finalized(
    client, user_dataset, user_model
):
    """Reopening via from_evaluate_call must not un-finalize the original logger
    instance — its finalization guard stays in effect.
    """
    ev = EvaluationLogger()
    for row in user_dataset:
        output = user_model(row["a"], row["b"])
        pred = ev.log_prediction(inputs=row, output=output)
        pred.log_score("acc", output > 3)
        pred.finish()
    ev.log_summary({"mean_acc": 0.5})
    eval_call_id = ev._evaluate_call.id
    client.flush()

    EvaluationLogger.from_evaluate_call(eval_call_id)

    assert ev._is_finalized is True
    # Calling log_prediction on the original logger is a no-op warning on
    # log_summary but raises on log_example; exercise the stricter guard.
    with pytest.raises(ValueError, match="finalized"):
        ev.log_example(inputs={"a": 1, "b": 2}, output=3, scores={"acc": True})


def test_from_evaluate_call_rejects_non_evaluate_call(client, user_dataset, user_model):
    """from_evaluate_call must refuse to bind to calls that are not
    Evaluation.evaluate roots.
    """
    ev = EvaluationLogger()
    pred = ev.log_prediction(inputs={"a": 1, "b": 2}, output=3)
    pred.log_score("acc", True)
    pred.finish()
    ev.log_summary({"mean_acc": 1.0})
    client.flush()

    # Find a predict_and_score child — not a root evaluate call.
    calls = list(client.get_calls())
    pas_calls = [
        c for c in calls if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    assert len(pas_calls) >= 1

    with pytest.raises(
        ValueError, match="not a root Evaluation.evaluate|not an Evaluation.evaluate"
    ):
        EvaluationLogger.from_evaluate_call(pas_calls[0].id)


@pytest.mark.asyncio
async def test_from_evaluate_call_extends_declarative_evaluation(client):
    """Reopen a declarative weave.Evaluation (not imperative) and append a new
    prediction + score. The new trial must show up in the server-side rollup
    alongside the original scorer results.
    """
    dataset_rows = [{"a": 1, "b": 2}, {"a": 2, "b": 3}]

    @weave.op
    def my_model(a: int, b: int) -> int:
        return a + b

    @weave.op
    def accuracy_scorer(a: int, b: int, output: int) -> bool:
        return output == a + b

    evaluation = weave.Evaluation(dataset=dataset_rows, scorers=[accuracy_scorer])
    await evaluation.evaluate(my_model)
    client.flush()

    calls = list(client.get_calls())
    eval_calls = [c for c in calls if op_name_from_call(c) == "Evaluation.evaluate"]
    assert len(eval_calls) == 1
    eval_call = eval_calls[0]
    eval_call_id = eval_call.id
    original_ended_at = eval_call.ended_at
    original_output = eval_call.output

    ev2 = EvaluationLogger.from_evaluate_call(eval_call_id)
    new_row = {"a": 99, "b": 100}
    pred = ev2.log_prediction(inputs=new_row, output=199)
    pred.log_score("accuracy_scorer", True)
    pred.log_score("latency_ms", 42)
    pred.finish()
    # Also add a new score to an existing row by replaying its inputs.
    pred_replay = ev2.log_prediction(inputs=dataset_rows[0], output=3)
    pred_replay.log_score("latency_ms", 17)
    pred_replay.finish()
    ev2.log_summary()
    client.flush()

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_call_id],
            include_summary=True,
        )
    )
    assert res.total_rows == len(dataset_rows) + 1

    # The original row that we replayed should now have 2 trials, the other
    # original row 1 trial, and the new row 1 trial.
    trials_by_row = {
        row.row_digest: sum(
            len(ev_entry.trials)
            for ev_entry in row.evaluations
            if ev_entry.evaluation_call_id == eval_call_id
        )
        for row in res.rows
    }
    assert sorted(trials_by_row.values()) == [1, 1, 2]

    eval_summaries = [
        s for s in res.summary.evaluations if s.evaluation_call_id == eval_call_id
    ]
    assert len(eval_summaries) == 1
    summary_scorer_keys = {stat.scorer_key for stat in eval_summaries[0].scorer_stats}
    assert "accuracy_scorer" in summary_scorer_keys
    assert "latency_ms" in summary_scorer_keys

    # Declarative eval's original evaluate_call must be untouched.
    refetched = client.get_call(eval_call_id)
    assert refetched.ended_at == original_ended_at
    assert refetched.output == original_output


@pytest.mark.asyncio
async def test_from_evaluate_call_parent_id_after_declarative_eval_call_api(client):
    """Regression: after `.call()` on a declarative Evaluation, the appended
    predict_and_score's parent_id must be the evaluate_call, not the
    summarize call. (The UI had been showing the appended trial under
    summarize because the call stack wasn't set correctly.)
    """
    ev = weave.Evaluation(dataset=[{"a": 1}])

    @weave.op
    def model(a: int) -> int:
        return a + 1

    res, evaluate_call = await ev.evaluate.call(ev, model)

    ev2 = EvaluationLogger.from_evaluate_call(evaluate_call.id)
    ev2.log_example(inputs={"a": 2}, output=3, scores={})
    ev2.finish()
    client.flush()

    calls = list(client.get_calls())
    pas_calls = [
        c for c in calls if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    summarize_calls = [
        c for c in calls if op_name_from_call(c) == "Evaluation.summarize"
    ]
    pas_calls.sort(key=lambda c: c.started_at)
    new_pas = pas_calls[-1]

    assert new_pas.parent_id == evaluate_call.id, (
        f"new predict_and_score parent={new_pas.parent_id!r} should be "
        f"evaluate={evaluate_call.id!r}"
    )
    if summarize_calls:
        assert new_pas.parent_id != summarize_calls[0].id, (
            "new predict_and_score is incorrectly nested under summarize"
        )


def _ref_uri(x: Any) -> str:
    if hasattr(x, "uri"):
        return x.uri() if callable(x.uri) else x.uri
    if hasattr(x, "ref"):
        r = x.ref
        return r.uri() if callable(r.uri) else r.uri
    if isinstance(x, str):
        return x
    raise TypeError(f"cannot extract ref uri from {x!r}")


@pytest.mark.asyncio
async def test_from_evaluate_call_does_not_bump_evaluation_version(client):
    """Reopening and appending must not publish a new Evaluation version.
    (The Model ref is separately handled: if the original `model` was a
    real Model subclass we preserve it too, but if it was an @weave.op
    function a placeholder Model is substituted.)
    """
    ev = weave.Evaluation(dataset=[{"a": 1}])

    @weave.op
    def model(a: int) -> int:
        return a + 1

    _, evaluate_call = await ev.evaluate.call(ev, model)

    original_eval_ref = _ref_uri(evaluate_call.inputs["self"])

    ev2 = EvaluationLogger.from_evaluate_call(evaluate_call.id)
    ev2.log_example(inputs={"a": 2}, output=3, scores={})
    ev2.finish()
    client.flush()

    pas_calls = [
        c
        for c in client.get_calls()
        if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    pas_calls.sort(key=lambda c: c.started_at)
    new_pas = pas_calls[-1]

    new_eval_ref = _ref_uri(new_pas.inputs["self"])

    assert new_eval_ref == original_eval_ref, (
        f"appending bumped the Evaluation version: "
        f"{original_eval_ref} -> {new_eval_ref}"
    )


@pytest.mark.asyncio
async def test_from_evaluate_call_preserves_eval_ref_with_model_subclass(client):
    """The Evaluation ref must be preserved when reopening, regardless of the
    model's type. The Model ref is preserved only when wc.get() round-trips
    the original to a Model instance — otherwise (Op functions, unregistered
    Model subclasses surfaced as WeaveObject wrappers) we fall back to a
    placeholder Model, which bumps a Model version. That tradeoff is
    acceptable since the user-visible Evaluation identity stays stable.
    """

    class MyModel(Model):
        factor: int = 2

        @weave.op
        def predict(self, a: int) -> int:
            return a * self.factor

    original_model = MyModel()

    ev = weave.Evaluation(dataset=[{"a": 1}])
    _, evaluate_call = await ev.evaluate.call(ev, original_model)

    original_eval_ref = _ref_uri(evaluate_call.inputs["self"])

    ev2 = EvaluationLogger.from_evaluate_call(evaluate_call.id)
    ev2.log_example(inputs={"a": 2}, output=4, scores={})
    ev2.finish()
    client.flush()

    pas_calls = [
        c
        for c in client.get_calls()
        if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    pas_calls.sort(key=lambda c: c.started_at)
    new_pas = pas_calls[-1]

    assert _ref_uri(new_pas.inputs["self"]) == original_eval_ref


@pytest.mark.asyncio
async def test_from_evaluate_call_visible_via_query_apis(client):
    """After extending a declarative Evaluation via from_evaluate_call, every query
    surface that walks the eval tree must see the appended data:

      1. `client.get_call(eval_call_id)` — direct fetch.
      2. `evaluation.get_evaluate_calls()` — by-evaluation-ref query.
      3. `client.get_calls(filter=...)` — generic call query by op name.
      4. `client.server.eval_results_query(...)` — the v2 rollup endpoint.
      5. `evaluation.get_score_calls()` — descendent scorer calls per trace.
    """
    @weave.op
    def my_model(a: int) -> int:
        return a + 1

    @weave.op
    def is_even(a: int, output: int) -> bool:
        return output % 2 == 0

    evaluation = weave.Evaluation(dataset=[{"a": 1}, {"a": 2}], scorers=[is_even])
    _, evaluate_call = await evaluation.evaluate.call(evaluation, my_model)
    eval_call_id = evaluate_call.id
    eval_trace_id = evaluate_call.trace_id

    # --- extend ---
    ev2 = EvaluationLogger.from_evaluate_call(eval_call_id)
    pred = ev2.log_prediction(inputs={"a": 99}, output=100)
    pred.log_score("is_even", True)
    pred.finish()
    ev2.log_summary()
    client.flush()

    # 1) direct fetch by id
    refetched = client.get_call(eval_call_id)
    assert refetched.id == eval_call_id
    assert refetched.trace_id == eval_trace_id

    # 2) get_evaluate_calls — returns the same root call (input_refs filter
    #    matches because we preserved the Evaluation ref).
    eval_calls_via_method = list(evaluation.get_evaluate_calls())
    assert any(c.id == eval_call_id for c in eval_calls_via_method), (
        f"evaluation.get_evaluate_calls() did not surface "
        f"{eval_call_id} after extending"
    )

    # 3) generic calls_query for predict_and_score under this trace finds
    #    BOTH the original (2 rows) and the appended (1 new row) trials.
    pas_in_trace = [
        c
        for c in client.get_calls(filter={"trace_ids": [eval_trace_id]})
        if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    assert len(pas_in_trace) == 3, (
        f"expected 3 predict_and_score calls in trace, got {len(pas_in_trace)}"
    )
    appended_pas_inputs = {tuple(sorted(c.inputs["example"].items())) for c in pas_in_trace}
    assert (("a", 99),) in appended_pas_inputs, (
        f"appended row {{'a': 99}} not found in calls_query results: "
        f"{appended_pas_inputs}"
    )

    # 4) eval_results_query rollup includes the appended row.
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_call_id],
            include_summary=True,
        )
    )
    assert res.total_rows == 3
    new_row_present = any(
        any(t.model_output == 100 for ev in row.evaluations for t in ev.trials)
        for row in res.rows
    )
    assert new_row_present, "eval_results_query did not surface the appended row"

    # 5) get_score_calls finds scorer descendents under the eval's trace —
    #    must include the appended `is_even` scorer call.
    score_calls_by_trace = evaluation.get_score_calls()
    assert eval_trace_id in score_calls_by_trace, (
        f"trace {eval_trace_id} missing from get_score_calls keys: "
        f"{list(score_calls_by_trace.keys())}"
    )
    is_even_calls = [
        c
        for c in score_calls_by_trace[eval_trace_id]
        if c.summary.get("weave", {}).get("trace_name") == "is_even"
    ]
    # 2 originals + 1 from the reopen append.
    assert len(is_even_calls) == 3, (
        f"expected 3 `is_even` scorer calls (2 original + 1 appended), "
        f"got {len(is_even_calls)}"
    )


@pytest.mark.asyncio
async def test_evaluation_from_ref_preserves_digest(client):
    """`Evaluation.from_ref(ref)` must hydrate the Evaluation while
    preserving the ref's digest, so callers can pass the result back into
    op inputs without bumping a new object version.
    """

    @weave.op
    def m(a: int) -> int:
        return a + 1

    evaluation = weave.Evaluation(dataset=[{"a": 1}])
    await evaluation.evaluate.call(evaluation, m)
    eval_ref = evaluation.ref
    assert eval_ref is not None

    hydrated = Evaluation.from_ref(eval_ref)
    assert isinstance(hydrated, Evaluation)
    assert hydrated.ref is not None
    assert hydrated.ref.digest == eval_ref.digest


def test_model_from_ref_returns_none_for_non_model_ref(client):
    """`Model.from_ref` returns `None` when the ref doesn't resolve to a
    Model instance — for example, when the ref points at an `@weave.op`
    function. Callers like `EvaluationLogger.from_evaluate_call` rely on
    that None to know they need to substitute a placeholder.
    """

    @weave.op
    def m(a: int) -> int:
        return a + 1

    weave.publish(m)
    assert m.ref is not None
    assert Model.from_ref(m.ref) is None
