"""
This test suite is inteded to test the end to end lifecycle of on demand evaluations.
The end goal is to enable the user to configure, run, and analyze evaluations purely through the API.
"""

import pytest

import weave
from weave.builtin_objects.models.CompletionModel import LiteLLMCompletionModel
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import EvaluateReq


@pytest.mark.asyncio
async def test_entire_eval_lifecycle(client: WeaveClient):
    # Create a dataset
    dataset = weave.Dataset(
        rows=[
            {"input": "United States", "output": "USA"},
            {"input": "Canada", "output": "CAN"},
            {"input": "Mexico", "output": "MEX"},
        ]
    )

    scorer = LLMJudgeScorer(
        model="gpt-4o-mini",
        system_prompt="Judge the correctness of the output.",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "passed": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
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
            {
                "role": "system",
                "content": "Determine the abbreviation for the given country.",
            },
            {"role": "user", "content": "{input}"},
        ],
    )

    # LOCAL EXECUTION
    on_start_called = 0
    on_row_complete_called = []

    def on_start():
        nonlocal on_start_called
        on_start_called += 1

    def on_row_complete(call_id, eval_row: dict):
        nonlocal on_row_complete_called
        on_row_complete_called.append((call_id, eval_row))

    eval_results = await evaluation.evaluate(model, on_start, on_row_complete)
    assert on_start_called == 1
    assert len(on_row_complete_called) == 3

    true_count = eval_results["LLMJudgeScorer"]["passed"]["true_count"]
    latency = eval_results["model_latency"]["mean"]
    assert eval_results == {
        "LLMJudgeScorer": {
            "passed": {"true_count": true_count, "true_fraction": true_count / 3}
        },
        "model_latency": {"mean": latency},
    }

    # REMOTE EXECUTION (not user-facing right now, using low level server)
    server = client.server
    evaluate_stream_fn = server.evaluate_stream
    evaluate_stream_arg = EvaluateReq(
        project_id=client._project_id(),
        evaluation_ref=evaluation.ref.uri(),
        model_ref=model.ref.uri(),
    )
    coro = evaluate_stream_fn(evaluate_stream_arg)
    stream = await coro

    index = 0

    async for event in stream:
        if event.step_type == "start":
            assert index == 0
            index += 1
        elif event.step_type == "predict_and_score":
            assert index == 1
            index += 1
        elif event.step_type == "summary":
            assert index == 1 + 3
            index += 1
        else:
            raise ValueError(f"Unknown event type: {event.step_type}")

    assert index == 1 + 3 + 1
