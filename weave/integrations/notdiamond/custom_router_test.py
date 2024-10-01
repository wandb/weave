import os
from typing import Dict

import pandas as pd
import pytest

import weave
from weave.flow.eval import EvaluationResults
from weave.trace.weave_client import WeaveClient

from weave.integrations.notdiamond.custom_router import train_evaluations

@pytest.fixture
def model_evals():
    return get_model_evals()

def get_model_evals(file_path: str="integrations/notdiamond/test_data/humaneval.csv"):
    df = pd.read_csv(file_path)
    models = [
        "anthropic/claude-3-5-sonnet-20240620",
        "openai/gpt-4o-2024-05-13",
        "google/gemini-1.5-pro-latest",
        "openai/gpt-4-turbo-2024-04-09",
        "anthropic/claude-3-opus-20240229",
    ]

    model_evals = {}
    for model in models:
        input_score_col = f"{model}/final_score"
        input_response_col = f"{model}/response"
        columns = ["Input", input_response_col, input_score_col]
        eval_rows = (
            df[columns]
            .rename(columns={"Input": "prompt", input_response_col: "actual", input_score_col: "scores"})
        )
        eval_rows['scores'] = eval_rows['scores'].apply(lambda x: {"correctness": x})
        eval_rows = eval_rows.to_dict(orient="records")
        model_evals[model] = EvaluationResults(rows=weave.Table(eval_rows))

    return model_evals


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "api.notdiamond.ai"],
)
def test_custom_router_train_evaluations(client: WeaveClient, model_evals: Dict[str, EvaluationResults]):
    api_key = os.getenv("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    preference_id = train_evaluations(
        model_evals=model_evals,
        prompt_column="prompt",
        response_column="actual",
        language="en",
        maximize=True,
        api_key=api_key,
    )

    # confirm client was called
    assert len(list(client.calls())) > 0
    nd_calls = [call for call in client.calls() if 'train_evaluations' in call.op_name]
    assert len(nd_calls) == 1

    # confirm router was trained
    assert preference_id is not None
