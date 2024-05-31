import pytest
from typing import Any, Generator, List, Optional, Tuple

import dspy
from weave.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def filter_body(r: Any) -> Any:
    r.body = ""
    return r


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


@pytest.fixture
def fake_api_key() -> Generator[None, None, None]:
    import os

    orig_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "sk-DUMMY_KEY"
    try:
        yield
    finally:
        if orig_key is None:
            del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = orig_key


def assert_calls(
    client: WeaveClient,
    expected_calls: List[Tuple[str, int]],
    partial_assertion: bool = False,
):
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    flattened_call_response = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    if not partial_assertion:
        assert flattened_call_response == expected_calls
    else:
        for call in expected_calls:
            assert call in flattened_call_response


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_language_models(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)
    gpt3_turbo("hello! this is a raw prompt to GPT-3.5")
    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("GPT3.__call__", 0),
            ("GPT3.request", 1),
            ("GPT3.basic_request", 2),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_signature(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)
    sentence = "it's a charming and often affecting journey."  # example from the SST-2 dataset.
    dspy.Predict("sentence -> sentiment")
    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__call__", 0),
            ("Predict.forward", 1),
            ("GPT3.__call__", 2),
            ("GPT3.request", 3),
            ("GPT3.basic_request", 4),
            ("openai.chat.completions.create", 5),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_inline_signature(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)
    document = """The 21-year-old made seven appearances for the Hammers and netted his only goal for them in a Europa League qualification round match against Andorran side FC Lustrains last season. Lee had two loan spells in League One last term, with Blackpool and then Colchester United. He scored twice for the U's but was unable to save them from relegation. The length of Lee's contract with the promoted Tykes has not been revealed. Find all the latest football transfers on our dedicated page."""
    summarize = dspy.ChainOfThought("document -> summary")
    summarize(document=document)
    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("ChainOfThought.__init__", 0),
            ("ChainOfThought.__call__", 0),
            ("ChainOfThought.forward", 1),
            ("GPT3.__call__", 2),
            ("GPT3.request", 3),
            ("GPT3.basic_request", 4),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_cot(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class Emotion(dspy.Signature):
        """Classify emotion among sadness, joy, love, anger, fear, surprise."""

        sentence = dspy.InputField()
        sentiment = dspy.OutputField()

    sentence = "i started feeling a little vulnerable when the giant spotlight started blinding me"  # from dair-ai/emotion

    classify = dspy.Predict(Emotion)
    classify(sentence=sentence)

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__call__", 0),
            ("Predict.forward", 1),
            ("GPT3.__call__", 2),
            ("GPT3.request", 3),
            ("GPT3.basic_request", 4),
            ("openai.chat.completions.create", 5),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_cot_with_hint(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class BasicQA(dspy.Signature):
        """Answer questions with short factoid answers."""

        question = dspy.InputField()
        answer = dspy.OutputField(desc="often between 1 and 5 words")

    generate_answer = dspy.ChainOfThoughtWithHint(BasicQA)
    question = "What is the color of the sky?"
    hint = "It's what you often see during a sunny day."
    generate_answer(question=question, hint=hint)

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("ChainOfThoughtWithHint.__init__", 0),
            ("ChainOfThoughtWithHint.__call__", 0),
            ("ChainOfThoughtWithHint.forward", 1),
            ("GPT3.__call__", 2),
            ("GPT3.request", 3),
            ("GPT3.basic_request", 4),
            ("openai.chat.completions.create", 5),
            ("GPT3.__call__", 2),
            ("GPT3.request", 3),
            ("GPT3.basic_request", 4),
            ("openai.chat.completions.create", 5),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_multi_chain_comparison(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class BasicQA(dspy.Signature):
        """Answer questions with short factoid answers."""

        question = dspy.InputField()
        answer = dspy.OutputField(desc="often between 1 and 5 words")

    completions = [
        dspy.Prediction(
            rationale="I recall that during clear days, the sky often appears this color.",
            answer="blue",
        ),
        dspy.Prediction(
            rationale="Based on common knowledge, I believe the sky is typically seen as this color.",
            answer="green",
        ),
        dspy.Prediction(
            rationale="From images and depictions in media, the sky is frequently represented with this hue.",
            answer="blue",
        ),
    ]
    compare_answers = dspy.MultiChainComparison(BasicQA)
    compare_answers(completions, question="What is the color of the sky?")

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("MultiChainComparison", 0),
            ("Predict.__init__", 0),
            ("MultiChainComparison.__call__", 0),
            ("Predict.__call__", 1),
            ("Predict.forward", 2),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_pot(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class GenerateAnswer(dspy.Signature):
        """Answer questions with short factoid answers."""

        question = dspy.InputField()
        answer = dspy.OutputField(desc="often between 1 and 5 words")

    pot = dspy.ProgramOfThought(GenerateAnswer)
    pot(
        question="Sarah has 5 apples. She buys 7 more apples from the store. How many apples does Sarah have now?"
    )

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("ProgramOfThought.__init__", 0),
            ("ChainOfThought.__init__", 0),
            ("ChainOfThought.__init__", 0),
            ("ChainOfThought.__init__", 0),
            ("ProgramOfThought.__call__", 0),
            ("ChainOfThought.__call__", 1),
            ("ChainOfThought.forward", 2),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
            ("openai.chat.completions.create", 6),
            ("ChainOfThought.__call__", 1),
            ("ChainOfThought.forward", 2),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
            ("openai.chat.completions.create", 6),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_react(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class BasicQA(dspy.Signature):
        """Answer questions with short factoid answers."""

        question = dspy.InputField()
        answer = dspy.OutputField(desc="often between 1 and 5 words")

    react_module = dspy.ReAct(BasicQA)
    react_module(question="What is the color of the sky?")

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("ReAct.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__init__", 0),
            ("Predict.__init__", 0),
            ("ReAct.__call__", 0),
            ("Predict.__call__", 1),
            ("Predict.forward", 2),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
            ("openai.chat.completions.create", 6),
        ],
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_dspy_react(client: WeaveClient, fake_api_key: None) -> None:
    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)

    class BasicQA(dspy.Signature):
        """Answer questions with short factoid answers."""

        question = dspy.InputField()
        answer = dspy.OutputField(desc="often between 1 and 5 words")

    react_module = dspy.ReAct(BasicQA)
    react_module(question="What is the color of the sky?")

    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__init__", 0),
            ("BootstrapFewShot.__init__", 0),
            ("RAG.__init__", 0),
            ("Retrieve.__init__", 0),
            ("ChainOfThought.__init__", 0),
            ("BootstrapFewShot.compile", 0),
            ("RAG.__call__", 1),
            ("Retrieve.__call__", 2),
            ("Retrieve.forward", 3),
            ("ChainOfThought.__call__", 1),
            ("ChainOfThought.forward", 2),
            ("GPT3.__call__", 3),
            ("GPT3.request", 4),
            ("GPT3.basic_request", 5),
            ("validate_context_and_answer", 1),
        ],
        partial_assertion=True,
    )
