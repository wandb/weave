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


def assert_calls_correct_for_quickstart(calls: list[tsi.CallSchema]) -> None:
    assert len(calls) == 9
    """ Next, the major thing to assert is the "shape" of the calls:
    llama_index.query
        llama_index.retrieve
            llama_index.embedding
        llama_index.synthesize
            llama_index.chunking
            llama_index.chunking
            llama_index.templating
            llama_index.llm
                openai.chat.completions.create
    """
    flattened = flatten_calls(calls)
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("llama_index.query", 0),
        ("llama_index.retrieve", 1),
        ("llama_index.embedding", 2),
        ("llama_index.synthesize", 1),
        ("llama_index.chunking", 2),
        ("llama_index.chunking", 2),
        ("llama_index.templating", 2),
        ("llama_index.llm", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert got == exp


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


def assert_calls(client: WeaveClient, expected_calls: List[Tuple[str, int]]):
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    flattened_call_response = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flattened_call_response == expected_calls


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
    response = summarize(document=document)
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
def test_dspy_custom_signature(client: WeaveClient, fake_api_key: None) -> None:
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
