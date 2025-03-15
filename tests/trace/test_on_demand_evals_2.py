"""
This test suite is inteded to test the end to end lifecycle of on demand evaluations.
The end goal is to enable the user to configure, run, and analyze evaluations purely through the API.
"""

import pytest

import weave
from weave.builtin_objects.models.CompletionModel import LiteLLMCompletionModel
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer
from weave.trace.weave_client import WeaveClient


@pytest.mark.asyncio
async def test_entire_eval_lifecycle(client: WeaveClient):
    # Create a dataset
    dataset = weave.Dataset(rows=[
        {"input": "United States", "output": "USA"},
        {"input": "Canada", "output": "CAN"},
        {"input": "Mexico", "output": "MEX"},
    ])

    scorer = LLMJudgeScorer(
        model="gpt-4o-mini",
        system_prompt="Judge the correctness of the output.",
        response_format={"type": "json_schema", "json_schema": {
            "name": "response",
            "schema": {
                    "type": "object",
                    "properties": {"passed": {"type": "boolean"}, "reason": {"type": "string"}},
                },
            },
        },
    )

    evaluation = weave.Evaluation(
        name="test_evaluation",
        dataset=dataset,
        scorers=[scorer],
    )

    model = LiteLLMCompletionModel(
        model="gpt-4o-mini",
        messages_template=[
            {"role": "system", "content": "Determine the abbreviation for the given country."},
            {"role": "user", "content": "{input}"},
        ]
    )

    eval_results = await evaluation.evaluate(model)

    true_count = eval_results['LLMJudgeScorer']['passed']['true_count']
    latency = eval_results['model_latency']['mean']
    assert eval_results == {'LLMJudgeScorer': {'passed': {'true_count': true_count, 'true_fraction': true_count/3}}, 'model_latency': {'mean': latency}}
