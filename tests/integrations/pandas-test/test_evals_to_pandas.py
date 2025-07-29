import pytest

import weave
from tests.trace.util import client_is_sqlite


@pytest.fixture
def make_evals(client):
    ev = weave.EvaluationLogger(model="abc", dataset="def")
    pred = ev.log_prediction(inputs={"x": 1}, output=2)
    pred.log_score("score", 3)
    pred.log_score("score2", 4)
    ev.log_summary(summary={"y": 5})
    return


def test_get_evaluations_to_pandas(client, make_evals):
    evals_df = client.get_evaluations().to_pandas(flatten=True)
    assert evals_df.loc[0, "output.score.mean"] == 3
    assert evals_df.loc[0, "output.score2.mean"] == 4
    assert evals_df.loc[0, "output.output.y"] == 5
    assert evals_df.loc[0, "inputs.self"].name == "def-evaluation"
    assert evals_df.loc[0, "inputs.model"].name == "abc"


def test_get_scores_to_pandas(client, make_evals):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    scores_df = client.get_scores().to_pandas(flatten=True)
    assert scores_df.loc[0, "inputs.self"].name == "score"
    assert scores_df.loc[0, "inputs.inputs.x"] == 1
    assert scores_df.loc[0, "inputs.output"] == 2
    assert scores_df.loc[0, "output"] == 3

    assert scores_df.loc[1, "inputs.self"].name == "score2"
    assert scores_df.loc[1, "inputs.inputs.x"] == 1
    assert scores_df.loc[1, "inputs.output"] == 2
    assert scores_df.loc[1, "output"] == 4
