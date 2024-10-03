import json
import os
from typing import Dict

import pytest
import yaml

import weave
from weave.flow.eval import EvaluationResults
from weave.integrations.notdiamond.custom_router import evaluate_router, train_router
from weave.integrations.notdiamond.util import get_model_evals
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def model_evals():
    return get_model_evals()


@pytest.fixture
def model_datasets(model_evals: Dict[str, EvaluationResults]):
    model_datasets = {}
    for model, eval_results in model_evals.items():
        table_rows = []
        for eval_idx, eval_row in enumerate(eval_results.rows):
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
    with open(
        "tests/integrations/notdiamond/cassettes/custom_router_test/test_custom_router_train_router.yaml",
        "r",
    ) as file:
        cassette = yaml.safe_load(file)

    response_body = cassette["interactions"][0]["response"]["body"]
    return json.loads(response_body["string"])["preference_id"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "api.notdiamond.ai"],
)
def test_custom_router_train_router(
    client: WeaveClient, model_evals: Dict[str, EvaluationResults]
):
    api_key = os.getenv("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    preference_id = train_router(
        model_evals=model_evals,
        prompt_column="prompt",
        response_column="actual",
        language="en",
        maximize=True,
        api_key=api_key,
    )

    assert len(list(client.calls())) > 0
    nd_calls = [call for call in client.calls() if "train_evaluations" in call.op_name]
    assert len(nd_calls) == 1

    # confirm router was trained
    assert preference_id is not None


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "api.notdiamond.ai"],
)
def test_evaluate_router(
    client: WeaveClient, model_datasets: Dict[str, weave.Table], preference_id: str
):
    api_key = os.getenv("NOTDIAMOND_API_KEY", "DUMMY_API_KEY")
    eval_results, eval_stats = evaluate_router(
        model_datasets=model_datasets,
        preference_id=preference_id,
        prompt_column="prompt",
        response_column="actual",
        api_key=api_key,
    )

    assert len(list(client.calls())) > 0
    nd_calls = [call for call in client.calls() if "evaluate_router" in call.op_name]
    assert len(nd_calls) == 1

    model_dataset = next(iter(model_datasets.values()))
    assert len(eval_results) == len(model_dataset.rows)
