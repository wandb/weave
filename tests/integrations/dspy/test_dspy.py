import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "cookie", "set-cookie"],
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
    filter_headers=["authorization", "x-api-key", "cookie", "set-cookie"],
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
    filter_headers=["authorization", "x-api-key", "cookie", "set-cookie"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_rag(client) -> None:
    import dspy

    def search_wikipedia(query: str) -> list[str]:
        results = dspy.ColBERTv2(url="http://20.102.90.50:2017/wiki17_abstracts")(
            query, k=3
        )
        return [x["text"] for x in results]

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        )
    )

    rag = dspy.ChainOfThought("context, question -> response")
    question = "What's the name of the city Mahatma Gandhi was born in?"
    response = rag(context=search_wikipedia(question), question=question)
    assert "porbandar" in response.response.lower()

    calls = list(client.calls())
    assert len(calls) == 9

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.ChainOfThought"
    assert "porbandar" in call.output["response"].lower()
