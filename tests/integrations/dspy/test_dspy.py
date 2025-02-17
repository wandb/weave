import os
from typing import Literal

import pytest

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
def test_dspy_lm_call(client) -> None:
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
def test_dspy_chain_of_thought_call(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        )
    )

    math = dspy.ChainOfThought("question -> answer: float")
    response = math(
        question="Two dice are tossed. What is the probability that the sum equals two?"
    )
    assert (
        0.025 <= response.answer <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {response.answer}"

    calls = list(client.calls())
    assert len(calls) == 8

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.ChainOfThought"
    assert (
        0.025 <= call.output["answer"] <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {call.output['answer']}"

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Module"
    assert (
        0.025 <= call.output["answer"] <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {call.output['answer']}"

    call = calls[2]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.ChainOfThought.forward"
    assert (
        0.025 <= call.output["answer"] <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {call.output['answer']}"

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert (
        0.025 <= call.output["answer"] <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {call.output['answer']}"

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict.forward"
    assert (
        0.025 <= call.output["answer"] <= 0.03
    ), f"Expected probability around 0.0277 (1/36), got {call.output['answer']}"


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
def test_dspy_classification(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        )
    )

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
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert response.sentiment == call.output["sentiment"]
    assert response.confidence == call.output["confidence"]

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict.forward"
    assert response.sentiment == call.output["sentiment"]
    assert response.confidence == call.output["confidence"]

    call = calls[2]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"


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
def test_dspy_information_extraction(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        )
    )

    class ExtractInfo(dspy.Signature):
        """Extract structured information from text."""

        text: str = dspy.InputField()
        title: str = dspy.OutputField()
        headings: list[str] = dspy.OutputField()
        entities: list[dict[str, str]] = dspy.OutputField(
            desc="a list of entities and their metadata"
        )

    module = dspy.Predict(ExtractInfo)

    text = (
        "Apple Inc. announced its latest iPhone 14 today."
        "The CEO, Tim Cook, highlighted its new features in a press release."
    )
    response = module(text=text)
    assert "apple" in response.title.lower()
    assert "iphone" in response.title.lower()

    calls = list(client.calls())
    assert len(calls) == 5

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert response.title == call.output["title"]
    assert response.headings == call.output["headings"]
    assert response.entities == call.output["entities"]

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict.forward"
    assert response.title == call.output["title"]
    assert response.headings == call.output["headings"]
    assert response.entities == call.output["entities"]

    call = calls[2]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"
