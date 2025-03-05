from typing import Literal

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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_predict_module(client: WeaveClient) -> None:
    dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", cache=False))
    qa = dspy.Predict("question: str -> response: str")
    response = qa(question="who is the creator of git?")
    assert "Linus Torvalds" in response.response

    calls = list(client.calls())
    assert len(calls) == 5

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.Predict"
    output = call.output
    assert "Linus Torvalds" in output["response"]

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.ChatAdapter"
    output = call.output
    assert "Linus Torvalds" in output[0]["response"]

    call = calls[2]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.LM"

    call = calls[3]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "litellm.completion"

    call = calls[4]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_cot(client: WeaveClient) -> None:
    dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", cache=False))
    math = dspy.ChainOfThought("question -> answer: float")
    response = math(
        question="Two dice are tossed. What is the probability that the sum equals two?"
    )
    assert response.answer > 0.027

    calls = list(client.calls())
    assert len(calls) == 6

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.ChainOfThought"
    output = call.output
    assert output["answer"] > 0.027

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.Predict"
    output = call.output
    assert output["answer"] > 0.027

    call = calls[2]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.ChatAdapter"
    output = call.output
    assert output[0]["answer"] > 0.027

    call = calls[3]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.LM"

    call = calls[4]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "litellm.completion"

    call = calls[5]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_custom_module(client: WeaveClient) -> None:
    dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", cache=False))

    class Classify(dspy.Signature):
        """Classify sentiment of a given sentence."""

        sentence: str = dspy.InputField()
        sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
        confidence: float = dspy.OutputField()

    classify = dspy.Predict(Classify)
    response = classify(
        sentence="This book was super fun to read, though not the last chapter."
    )
    assert response.sentiment == "positive"
    assert response.confidence > 0.5

    calls = list(client.calls())
    assert len(calls) == 5

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.Predict"
    output = call.output
    assert output["sentiment"] == "positive"
    assert output["confidence"] > 0.5

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.ChatAdapter"
    output = call.output
    assert output[0]["sentiment"] == "positive"
    assert output[0]["confidence"] > 0.5

    call = calls[2]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.LM"

    call = calls[3]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "litellm.completion"

    call = calls[4]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
