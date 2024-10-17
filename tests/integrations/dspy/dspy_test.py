import os

import pytest

from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter


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
    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    assert len(flattened_calls) == 4

    assert flattened_calls_to_names(flattened_calls) == [
        ("dspy.OpenAI", 0),
        ("dspy.OpenAI.request", 1),
        ("dspy.OpenAI.basic_request", 2),
        ("openai.chat.completions.create", 3),
    ]

    call_1, _ = flattened_calls[0]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = call_1.output
    assert output_1[0] == expected_prediction

    call_2, _ = flattened_calls[1]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = call_2.output
    assert output_2["choices"][0]["finish_reason"] == "stop"
    assert output_2["choices"][0]["message"]["content"] == expected_prediction
    assert output_2["choices"][0]["message"]["role"] == "assistant"
    assert output_2["model"] == "gpt-3.5-turbo-1106"
    assert output_2["usage"]["completion_tokens"] == 9
    assert output_2["usage"]["prompt_tokens"] == 21
    assert output_2["usage"]["total_tokens"] == 30

    call_3, _ = flattened_calls[2]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = call_3.output
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
    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    assert len(flattened_calls) == 6

    assert flattened_calls_to_names(flattened_calls) == [
        ("dspy.Predict", 0),
        ("dspy.Predict.forward", 1),
        ("dspy.OpenAI", 2),
        ("dspy.OpenAI.request", 3),
        ("dspy.OpenAI.basic_request", 4),
        ("openai.chat.completions.create", 5),
    ]

    call_1, _ = flattened_calls[0]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = call_1.output
    assert (
        output_1
        == """Prediction(
    sentiment='Positive'
)"""
    )

    call_2, _ = flattened_calls[1]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = call_2.output
    assert (
        output_2
        == """Prediction(
    sentiment='Positive'
)"""
    )

    call_3, _ = flattened_calls[2]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = call_3.output
    assert output_3[0] == expected_prediction

    call_4, _ = flattened_calls[3]
    assert call_4.exception is None and call_4.ended_at is not None
    output_4 = call_4.output
    assert output_4["choices"][0]["finish_reason"] == "stop"
    assert output_4["choices"][0]["message"]["content"] == expected_prediction
    assert output_4["choices"][0]["message"]["role"] == "assistant"
    assert output_4["model"] == "gpt-3.5-turbo-0125"
    assert output_4["usage"]["completion_tokens"] == 1
    assert output_4["usage"]["prompt_tokens"] == 53
    assert output_4["usage"]["total_tokens"] == 54

    call_5, _ = flattened_calls[4]
    assert call_5.exception is None and call_5.ended_at is not None
    output_5 = call_5.output
    assert output_5["choices"][0]["finish_reason"] == "stop"
    assert output_5["choices"][0]["message"]["content"] == expected_prediction
    assert output_5["choices"][0]["message"]["role"] == "assistant"
    assert output_5["model"] == "gpt-3.5-turbo-0125"
    assert output_5["usage"]["completion_tokens"] == 1
    assert output_5["usage"]["prompt_tokens"] == 53
    assert output_5["usage"]["total_tokens"] == 54
    assert output_5["id"] == output_4["id"]
    assert output_5["created"] == output_4["created"]
