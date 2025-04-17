from typing import Callable, TypedDict

import pytest

from weave import ImperativeEvaluationLogger, Model, Scorer
from weave.integrations.integration_utilities import op_name_from_call
from weave.trace.context import call_context
from weave.trace_server.trace_server_interface import ObjectVersionFilter


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
    ev = ImperativeEvaluationLogger()

    model_outputs = []
    score1_results = []
    score2_results = []
    for row in user_dataset:
        model_outputs.append(model_output := user_model(row["a"], row["b"]))
        pred = ev.log_prediction(inputs=row, output=model_output)

        score1_results.append(score1_result := model_output > 2)
        pred.log_score(scorer="greater_than_2_scorer", score=score1_result)

        score2_results.append(score2_result := model_output > 2)
        pred.log_score(scorer="greater_than_4_scorer", score=score2_result)

        pred.finish()

    ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    client.flush()

    calls = client.get_calls()
    assert len(calls) == 14

    evaluate_call = calls[0]
    assert op_name_from_call(evaluate_call) == "Evaluation.evaluate"
    assert evaluate_call.inputs["self"]._class_name == "Evaluation"
    assert evaluate_call.inputs["model"]._class_name == "Model"
    assert evaluate_call.output == {"avg_score": 1.0, "total_examples": 3}

    for i, (inputs, outputs, score1, score2) in enumerate(
        zip(user_dataset, model_outputs, score1_results, score2_results)
    ):
        predict_index = 1 + i * 4

        predict_and_score_call = calls[predict_index]
        assert (
            op_name_from_call(predict_and_score_call) == "Evaluation.predict_and_score"
        )
        assert predict_and_score_call.inputs["self"]._class_name == "Evaluation"
        assert predict_and_score_call.inputs["model"]._class_name == "Model"
        assert predict_and_score_call.inputs["example"] == inputs
        assert predict_and_score_call.output["model_output"] == outputs

        predict_call = calls[predict_index + 1]
        assert op_name_from_call(predict_call) == "Model.predict"
        assert predict_call.inputs["self"]._class_name == "Model"
        assert predict_call.inputs["inputs"] == inputs
        assert predict_call.output == outputs

        feedbacks = list(predict_call.feedback)
        assert len(feedbacks) == 2
        assert feedbacks[0].feedback_type == "wandb.runnable.greater_than_2_scorer"
        assert feedbacks[1].feedback_type == "wandb.runnable.greater_than_4_scorer"

        scorer1_call = calls[predict_index + 2]
        assert op_name_from_call(scorer1_call) == "greater_than_2_scorer"
        assert scorer1_call.inputs["output"] == outputs
        assert scorer1_call.inputs["inputs"] == inputs
        assert scorer1_call.output == score1

        scorer2_call = calls[predict_index + 3]
        assert op_name_from_call(scorer2_call) == "greater_than_4_scorer"
        assert scorer2_call.inputs["output"] == outputs
        assert scorer2_call.inputs["inputs"] == inputs
        assert scorer2_call.output == score2

    summarize_call = calls[13]
    assert op_name_from_call(summarize_call) == "Evaluation.summarize"
    assert summarize_call.inputs["self"]._class_name == "Evaluation"
    assert summarize_call.output == {"avg_score": 1.0, "total_examples": 3}


def test_evaluation_with_custom_models_and_scorers(
    client, user_dataset: list[ExampleRow], user_model: Callable[[int, int], int]
):
    class MyModel(Model):
        a: int
        b: str

    class MyScorer(Scorer):
        c: int

    model1 = MyModel(a=1, b="two")
    model2 = {"a": 2, "b": "three"}
    model3 = "string_model"

    ev1 = ImperativeEvaluationLogger(model=model1)
    ev2 = ImperativeEvaluationLogger(model=model2)
    ev3 = ImperativeEvaluationLogger(model=model3)

    scorer1 = MyScorer(name="gt2_scorer", c=2)
    scorer2 = {"name": "gt4_scorer", "c": 4}
    scorer3 = "gt6_scorer"

    def run_evaluation(ev: ImperativeEvaluationLogger):
        for row in user_dataset:
            model_output = user_model(row["a"], row["b"])
            pred = ev.log_prediction(inputs=row, output=model_output)
            score1_result = model_output > 2
            pred.log_score(scorer=scorer1, score=score1_result)

            score2_result = model_output > 4
            pred.log_score(scorer=scorer2, score=score2_result)

            score3_result = model_output > 6
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
        assert models[0].version_index == 0
        assert models[1].object_id == "DynamicModel"
        assert models[1].version_index == 0
        assert models[2].object_id == "string_model"
        assert models[2].version_index == 0

        scorers = client._objects(
            filter=ObjectVersionFilter(base_object_classes=["Scorer"])
        )
        assert len(scorers) == 3
        # The patching we do on Scorers triggers a version bump.
        # Since we always do this, the min version will always be 1
        assert scorers[0].object_id == "gt2_scorer"
        assert scorers[0].version_index == 1

        assert scorers[1].object_id == "gt4_scorer"
        assert scorers[1].version_index == 1
        assert scorers[2].object_id == "gt6_scorer"
        assert scorers[2].version_index == 1

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
    ev4 = ImperativeEvaluationLogger(model=model4)

    for row in user_dataset:
        model_output = user_model(row["a"], row["b"])
        pred = ev4.log_prediction(inputs=row, output=model_output)
        score1_result = model_output > 2
        pred.log_score(scorer=scorer1, score=score1_result)

        score2_result = model_output > 4
        pred.log_score(scorer=scorer2, score=score2_result)

        pred.finish()

    ev4.log_summary({"avg_score": 1.0, "total_examples": 3})

    models = client._objects(filter=ObjectVersionFilter(base_object_classes=["Model"]))
    assert len(models) == 4
    assert models[3].object_id == "new_string_model"
    assert models[3].version_index == 0

    # No change to scorers
    scorers = client._objects(
        filter=ObjectVersionFilter(base_object_classes=["Scorer"])
    )
    assert len(scorers) == 3

    # Run a new evaluation using the same models, but different scorers
    scorer4 = MyScorer(name="gt8_scorer", c=8)
    ev5 = ImperativeEvaluationLogger(model=model4)

    for row in user_dataset:
        model_output = user_model(row["a"], row["b"])
        pred = ev5.log_prediction(inputs=row, output=model_output)
        score3_result = model_output > 8
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
    assert scorers[3].version_index == 1

    assert call_context.get_call_stack() == []
