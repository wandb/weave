import pytest

from weave import ImperativeEvaluationLogger
from weave.integrations.integration_utilities import op_name_from_call


@pytest.fixture
def user_dataset():
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


def test_basic_evaluation(client, user_dataset, user_model):
    ev = ImperativeEvaluationLogger()

    model_outputs = []
    score1_results = []
    score2_results = []
    for row in user_dataset:
        model_outputs.append(model_output := user_model(row["a"], row["b"]))
        pred = ev.log_prediction(inputs=row, output=model_output)

        score1_results.append(score1_result := model_output > 2)
        pred.log_score(scorer_name="greater_than_2_scorer", score=score1_result)

        score2_results.append(score2_result := model_output > 2)
        pred.log_score(scorer_name="greater_than_4_scorer", score=score2_result)

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
        assert op_name_from_call(predict_and_score_call) == "predict_and_score"
        assert predict_and_score_call.inputs["self"]._class_name == "Evaluation"
        assert predict_and_score_call.inputs["model"]._class_name == "Model"
        assert predict_and_score_call.inputs["inputs"] == inputs
        assert predict_and_score_call.output["model_output"] == outputs

        feedbacks = list(predict_and_score_call.feedback)
        assert len(feedbacks) == 2
        assert feedbacks[0].feedback_type == "wandb.runnable.greater_than_2_scorer"
        assert feedbacks[1].feedback_type == "wandb.runnable.greater_than_4_scorer"

        predict_call = calls[predict_index + 1]
        assert op_name_from_call(predict_call) == "predict"
        assert predict_call.inputs["self"]._class_name == "Model"
        assert predict_call.inputs["inputs"] == inputs
        assert predict_call.output == outputs

        scorer1_call = calls[predict_index + 2]
        assert op_name_from_call(scorer1_call) == "score"
        assert scorer1_call.inputs["output"]["model_output"] == outputs
        assert scorer1_call.inputs["inputs"]["inputs"] == inputs
        assert scorer1_call.output == score1

        scorer2_call = calls[predict_index + 3]
        assert op_name_from_call(scorer2_call) == "score"
        assert scorer2_call.inputs["output"]["model_output"] == outputs
        assert scorer2_call.inputs["inputs"]["inputs"] == inputs
        assert scorer2_call.output == score2

    summarize_call = calls[13]
    assert op_name_from_call(summarize_call) == "summarize"
    assert summarize_call.inputs["self"]._class_name == "Evaluation"
    assert summarize_call.output == {"avg_score": 1.0, "total_examples": 3}
