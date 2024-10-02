import json
import os
from typing import Dict
import yaml

import pandas as pd
import pytest

import weave
from weave.flow.eval import EvaluationResults
from weave.integrations.notdiamond.custom_router import train_evaluations, evaluate_router
from weave.trace.weave_client import WeaveClient

@pytest.fixture
def model_evals():
    return get_model_evals()

@pytest.fixture
def model_datasets(model_evals: Dict[str, EvaluationResults]):
    return get_model_datasets(model_evals)

def get_model_datasets(model_evals: Dict[str, EvaluationResults]):
    model_datasets = {}
    for model, eval_results in model_evals.items():

        table_rows = []
        for eval_idx, eval_row in enumerate(eval_results.rows):
            print(eval_row.keys())
            table_rows.append(
                {
                    "id": eval_idx,
                    "prompt": eval_row["prompt"],
                    "actual": eval_row["actual"],
                    "scores": eval_row["scores"],
                }
            )

        model_datasets[model] = weave.Table(table_rows)

    return model_datasets

@pytest.fixture
def preference_id():
    with open('integrations/notdiamond/cassettes/custom_router_test/test_custom_router_train_evaluations.yaml', 'r') as file:
        cassette = yaml.safe_load(file)

    response_body = cassette['interactions'][0]['response']['body']
    return json.loads(response_body['string'])['preference_id']

def get_model_evals(
    file_path: str = "integrations/notdiamond/test_data/humaneval.csv",
) -> Dict[str, EvaluationResults]:
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
        input_score_col = _get_score_column(model)
        input_response_col = _get_response_column(model)
        columns = ["Input", input_response_col, input_score_col]
        eval_rows = (
            df[columns]
            .rename(columns={"Input": "prompt", input_response_col: "actual", input_score_col: "scores"})
        )
        eval_rows['scores'] = eval_rows['scores'].apply(lambda x: {"correctness": x})
        eval_rows = eval_rows.to_dict(orient="records")
        model_evals[model] = EvaluationResults(rows=weave.Table(eval_rows))

    return model_evals

def _get_score_column(model: str) -> str:
    return f"{model}/final_score"

def _get_response_column(model: str) -> str:
    return f"{model}/response"

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

    assert len(list(client.calls())) > 0
    nd_calls = [call for call in client.calls() if 'train_evaluations' in call.op_name]
    assert len(nd_calls) == 1

    # confirm router was trained
    assert preference_id is not None


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "api.notdiamond.ai"],
)
def test_evaluate_router(client: WeaveClient, model_datasets: Dict[str, weave.Table], preference_id: str):
    api_key = os.getenv("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    eval_results, eval_stats = evaluate_router(
        model_datasets=model_datasets,
        preference_id=preference_id,
        prompt_column="prompt",
        response_column="actual",
        api_key=api_key,
    )

    assert len(list(client.calls())) > 0
    nd_calls = [call for call in client.calls() if 'evaluate_router' in call.op_name]
    assert len(nd_calls) == 1

    model_dataset = next(iter(model_datasets.values()))
    assert len(eval_results) == len(model_dataset.rows)
