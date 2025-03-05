import dspy
import pytest

from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_language_models(client: WeaveClient) -> None:
    lm = dspy.LM("openai/gpt-4o-mini", cache=False)
    result = lm("Say this is a test! Don't say anything else.", temperature=0.7)
    assert len(result) == 1
    assert result[0].lower() == "this is a test!"

    calls = list(client.calls())
    assert len(calls) == 3

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.LM"
    output = call.output
    assert output[0].lower() == "this is a test!"

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "litellm.completion"
    output = call.output
    assert output["choices"][0]["message"]["content"].lower() == "this is a test!"

    call = calls[2]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
