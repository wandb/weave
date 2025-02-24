import os

import pytest

from weave.integrations.dspy.callbacks import WeaveCallback
from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie",
        "x-request-id",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-remaining-tokens",
    ],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_predict_module(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )
    question_answering_module = dspy.Predict("question: str -> response: str")
    response = question_answering_module(question="what is the capital of france?")
    assert "paris" in response.response.lower()

    calls = list(client.calls())
    assert len(calls) == 6

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert "paris" in call.output["response"].lower()
    assert (
        call.inputs["self"]["signature"]["description"]
        == "Given the fields `question`, produce the fields `response`."
    )

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"
    assert "paris" in call.output[0].lower()

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()

    call = calls[5]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()
