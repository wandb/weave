from typing import Literal

import dspy
import pytest

from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient

SAMPLE_EVAL_DATASET = [
    dspy.Example(
        {
            "question": """How would a typical person answer each of the following questions about causation?
A machine is set up in such a way that it will short circuit if both the black wire and the red wire touch the battery at the same time. The machine will not short circuit if just one of these wires touches the battery. The black wire is designated as the one that is supposed to touch the battery, while the red wire is supposed to remain in some other part of the machine. One day, the black wire and the red wire both end up touching the battery at the same time. There is a short circuit. Did the black wire cause the short circuit?
Options:
- Yes
- No""",
            "answer": "No",
        }
    ).with_inputs("question"),
    dspy.Example(
        {
            "question": """How would a typical person answer each of the following questions about causation?
Long ago, when John was only 17 years old, he got a job working for a large manufacturing company. He started out working on an assembly line for minimum wage, but after a few years at the company, he was given a choice between two line manager positions. He could stay in the woodwork division, which is where he was currently working. Or he could move to the plastics division. John was unsure what to do because he liked working in the woodwork division, but he also thought it might be worth trying something different. He finally decided to switch to the plastics division and try something new. For the last 30 years, John has worked as a production line supervisor in the plastics division. After the first year there, the plastics division was moved to a different building with more space. Unfortunately, through the many years he worked there, John was exposed to asbestos, a highly carcinogenic substance. Most of the plastics division was quite safe, but the small part in which John worked was exposed to asbestos fibers. And now, although John has never smoked a cigarette in his life and otherwise lives a healthy lifestyle, he has a highly progressed and incurable case of lung cancer at the age of 50. John had seen three cancer specialists, all of whom confirmed the worst: that, except for pain, John's cancer was untreatable and he was absolutely certain to die from it very soon (the doctors estimated no more than 2 months). Yesterday, while John was in the hospital for a routine medical appointment, a new nurse accidentally administered the wrong medication to him. John was allergic to the drug and he immediately went into shock and experienced cardiac arrest (a heart attack). Doctors attempted to resuscitate him but he died minutes after the medication was administered. Did John's job cause his premature death?
Options:
- Yes
- No""",
            "answer": "No",
        }
    ).with_inputs("question"),
    dspy.Example(
        {
            "question": """How would a typical person answer each of the following questions about causation?
Long ago, when John was only 17 years old, he got a job working for a large manufacturing company. He started out working on an assembly line for minimum wage, but after a few years at the company, he was given a choice between two line manager positions. He could stay in the woodwork division, which is where he was currently working. Or he could move to the plastics division. John was unsure what to do because he liked working in the woodwork division, but he also thought it might be worth trying something different. He finally decided to switch to the plastics division and try something new. For the last 30 years, John has worked as a production line supervisor in the plastics division. After the first year there, the plastics division was moved to a different building with more space. Unfortunately, through the many years he worked there, John was exposed to asbestos, a highly carcinogenic substance. Most of the plastics division was quite safe, but the small part in which John worked was exposed to asbestos fibers. And now, although John has never smoked a cigarette in his life and otherwise lives a healthy lifestyle, he has a highly progressed and incurable case of lung cancer at the age of 50. John had seen three cancer specialists, all of whom confirmed the worst: that, except for pain, John's cancer was untreatable and he was absolutely certain to die from it very soon (the doctors estimated no more than 2 months). Yesterday, while John was in the hospital for a routine medical appointment, a new nurse accidentally administered the wrong medication to him. John was allergic to the drug and he immediately went into shock and experienced cardiac arrest (a heart attack). Doctors attempted to resuscitate him but he died minutes after the medication was administered. Did misadministration of medication cause John's premature death?
Options:
- Yes
- No""",
            "answer": "Yes",
        }
    ).with_inputs("question"),
]


def accuracy_metric(answer, model_output, trace=None):
    predicted_answer = model_output["answer"].lower()
    return answer["answer"].lower() == predicted_answer


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
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
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
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
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
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
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_evaluate(client: WeaveClient) -> None:
    dspy.configure(lm=dspy.LM("openai/gpt-4o-mini", cache=False))
    module = dspy.ChainOfThought("question -> answer: str, explanation: str")
    evaluate = dspy.Evaluate(devset=SAMPLE_EVAL_DATASET, metric=accuracy_metric)
    accuracy = evaluate(module)
    assert accuracy > 50

    calls = list(client.calls())
    assert len(calls) == 22

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.Evaluate"
    output = call.output
    assert output > 50


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=[
        "authorization",
        "organization",
        "cookie",
        "x-request-id",
        "x-rate-limit",
    ],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_optimizer_bootstrap_fewshot(client: WeaveClient) -> None:
    dspy.configure(lm=dspy.LM("openai/gpt-4o", cache=False))
    module = dspy.ChainOfThought("question -> answer: str, explanation: str")
    optimizer = dspy.BootstrapFewShot(metric=accuracy_metric)
    _ = optimizer.compile(module, trainset=SAMPLE_EVAL_DATASET)

    calls = list(client.calls())
    assert len(calls) == 20

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "dspy.BootstrapFewShot.compile"
    output = call.output
    assert len(output["predict"]["demos"]) > 0
