import os
from typing import Any, Optional

import pytest

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.
    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    def children_of_parent_id(id: Optional[str]) -> list[tsi.CallSchema]:
        return [call for call in calls if call.parent_id == id]

    children = children_of_parent_id(parent_id)
    res = []
    for child in children:
        res.append((child, depth))
        res.extend(flatten_calls(calls, child.id, depth + 1))

    return res


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_language_models(client: WeaveClient) -> None:
    import dspy

    os.environ["DSP_CACHEBOOL"] = "False"

    gpt3_turbo = dspy.OpenAI(
        model="gpt-3.5-turbo-1106",
        max_tokens=300,
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
    )
    dspy.configure(lm=gpt3_turbo)
    prediction = gpt3_turbo("hello! this is a raw prompt to GPT-3.5")
    expected_prediction = "Hello! How can I assist you today?"
    assert prediction == [expected_prediction]
    calls = list(client.calls())
    assert len(calls) == 4

    calls_list = [_get_call_output(c.op_name) for c in calls]
    assert calls_list == [
        "dspy.OpenAI",
        "dspy.OpenAI.request",
        "dspy.OpenAI.basic_request",
        "openai.chat.completions.create",
    ]

    call_1 = calls[0]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = _get_call_output(call_1)
    assert output_1[0] == expected_prediction

    call_2 = calls[1]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = _get_call_output(call_2)
    assert output_2["choices"][0]["finish_reason"] == "stop"
    assert output_2["choices"][0]["message"]["content"] == expected_prediction
    assert output_2["choices"][0]["message"]["role"] == "assistant"
    assert output_2["model"] == "gpt-3.5-turbo-1106"
    assert output_2["usage"]["completion_tokens"] == 9
    assert output_2["usage"]["prompt_tokens"] == 21
    assert output_2["usage"]["total_tokens"] == 30

    call_3 = calls[2]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = _get_call_output(call_3)
    assert output_3["choices"][0]["finish_reason"] == "stop"
    assert output_3["choices"][0]["message"]["content"] == expected_prediction
    assert output_3["choices"][0]["message"]["role"] == "assistant"
    assert output_3["model"] == "gpt-3.5-turbo-1106"
    assert output_3["usage"]["completion_tokens"] == 9
    assert output_3["usage"]["prompt_tokens"] == 21
    assert output_3["usage"]["total_tokens"] == 30
    assert output_2["id"] == output_3["id"]
    assert output_2["created"] == output_3["created"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_inline_signatures(client: WeaveClient) -> None:
    import dspy

    os.environ["DSP_CACHEBOOL"] = "False"

    turbo = dspy.OpenAI(
        model="gpt-3.5-turbo", api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    )
    dspy.settings.configure(lm=turbo)
    classify = dspy.Predict("sentence -> sentiment")
    prediction = classify(
        sentence="it's a charming and often affecting journey."
    ).sentiment
    expected_prediction = "Positive"
    assert prediction == expected_prediction
    calls = list(client.calls())
    assert len(calls) == 4

    calls_list = [c.op_name for c in calls]
    assert calls_list == [
        "dspy.Predict",
        "dspy.Predict.forward",
        "dspy.OpenAI",
        "dspy.OpenAI.request",
        "dspy.OpenAI.basic_request",
        "openai.chat.completions.create",
    ]

    call_1 = calls[0]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = _get_call_output(call_1)
    assert (
        output_1
        == """Prediction(
    sentiment='Positive'
)"""
    )

    call_2 = calls[1]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = _get_call_output(call_2)
    assert (
        output_2
        == """Prediction(
    sentiment='Positive'
)"""
    )

    call_3 = calls[2]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = _get_call_output(call_3)
    assert output_3[0] == expected_prediction

    call_4 = calls[3]
    assert call_4.exception is None and call_4.ended_at is not None
    output_4 = _get_call_output(call_4)
    assert output_4["choices"][0]["finish_reason"] == "stop"
    assert output_4["choices"][0]["message"]["content"] == expected_prediction
    assert output_4["choices"][0]["message"]["role"] == "assistant"
    assert output_4["model"] == "gpt-3.5-turbo-0125"
    assert output_4["usage"]["completion_tokens"] == 1
    assert output_4["usage"]["prompt_tokens"] == 53
    assert output_4["usage"]["total_tokens"] == 54

    call_5 = calls[4]
    assert call_5.exception is None and call_5.ended_at is not None
    output_5 = _get_call_output(call_5)
    assert output_5["choices"][0]["finish_reason"] == "stop"
    assert output_5["choices"][0]["message"]["content"] == expected_prediction
    assert output_5["choices"][0]["message"]["role"] == "assistant"
    assert output_5["model"] == "gpt-3.5-turbo-0125"
    assert output_5["usage"]["completion_tokens"] == 1
    assert output_5["usage"]["prompt_tokens"] == 53
    assert output_5["usage"]["total_tokens"] == 54
    assert output_5["id"] == output_4["id"]
    assert output_5["created"] == output_4["created"]
