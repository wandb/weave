import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_2_lm_call(client) -> None:
    import dspy

    lm = dspy.LM(
        "openai/gpt-4o-mini",
        cache=False,
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
    )
    response = lm("Say this is a test!", temperature=0.7)
    assert "this is a test" in response[0].lower()

    calls = list(client.calls())
    assert len(calls) == 3

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"
    assert "this is a test" in call.output[0].lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"
    assert "this is a test" in call.output["choices"][0]["message"]["content"].lower()

    call = calls[2]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"
    assert "this is a test" in call.output["choices"][0]["message"]["content"].lower()
