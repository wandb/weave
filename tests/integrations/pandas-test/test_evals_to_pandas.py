import pytest

from tests.trace.util import client_is_sqlite


def test_get_evaluation_calls_to_pandas(client, make_evals):
    evals_df = client.get_evaluation_calls().to_pandas(flatten=True)
    assert evals_df.loc[0, "output.score.mean"] == 3
    assert evals_df.loc[0, "output.score2.mean"] == 4
    assert evals_df.loc[0, "output.output.y"] == 5
    assert evals_df.loc[0, "inputs.self"].name == "def-evaluation"
    assert evals_df.loc[0, "inputs.model"].name == "abc"


def test_get_score_calls_to_pandas(client, make_evals):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    scores_df = client.get_score_calls().to_pandas(flatten=True)
    assert scores_df.loc[0, "inputs.self"].name == "score"
    assert scores_df.loc[0, "inputs.inputs.x"] == 1
    assert scores_df.loc[0, "inputs.output"] == 2
    assert scores_df.loc[0, "output"] == 3

    assert scores_df.loc[1, "inputs.self"].name == "score2"
    assert scores_df.loc[1, "inputs.inputs.x"] == 1
    assert scores_df.loc[1, "inputs.output"] == 2
    assert scores_df.loc[1, "output"] == 4
