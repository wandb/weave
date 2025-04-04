import pytest

from weave.flow.eval2 import BetaEvaluationLogger


@pytest.fixture
def user_dataset():
    return [{"a": 1, "b": 2}, {"a": 2, "b": 3}, {"a": 3, "b": 4}]


@pytest.fixture
def user_model():
    def func(a: int, b: int) -> int:
        return a + b

    return func


def test_basic_evaluation(client, user_dataset, user_model):
    ev = BetaEvaluationLogger()

    for row in user_dataset:
        model_output = user_model(row["a"], row["b"])
        ev.log_prediction(inputs=row, output=model_output)

    ev.log_summary({"avg_score": 1.0, "total_examples": 3})

    client.flush()
