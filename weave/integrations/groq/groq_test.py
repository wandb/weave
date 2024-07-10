import asyncio
import os
from typing import Any, Optional

import pytest
from groq import AsyncGroq, Groq

import weave
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq_quickstart(
    client: weave.weave_client.WeaveClient,
) -> None:
    groq_client = Groq(
        api_key=os.environ.get("GROQ_API_KEY", "DUMMY_API_KEY"),
    )
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "What is the capital of India?",
            }
        ],
        model="llama3-8b-8192",
        seed=42,
    )

    assert (
        chat_completion.choices[0].message.content
        == "The capital of India is New Delhi."
    )
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_respose.calls) == 1

    flatened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flatened_calls_list == [
        ("groq.resources.chat.completions.Completions.create", 0),
    ]

    call = weave_server_respose.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.id == chat_completion.id
    assert output.model == chat_completion.model
    assert output.usage.completion_tokens == 9
    assert output.usage.prompt_tokens == 17
    assert output.usage.total_tokens == 26
    assert output.choices[0].finish_reason == "stop"
    assert output.choices[0].message.content == "The capital of India is New Delhi."


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq_async_chat_completion(
    client: weave.weave_client.WeaveClient,
) -> None:
    groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "DUMMY_API_KEY"))

    async def complete_chat() -> None:
        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a psychiatrist helping young minds",
                },
                {
                    "role": "user",
                    "content": "I panicked during the test, even though I knew everything on the test paper.",
                },
            ],
            model="llama3-70b-8192",
            temperature=0.3,
            max_tokens=360,
            top_p=1,
            stop=None,
            stream=False,
            seed=42,
        )

    asyncio.run(complete_chat())

    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_respose.calls) == 1

    flatened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flatened_calls_list == [
        ("groq.resources.chat.completions.AsyncCompletions.create", 0),
    ]

    call = weave_server_respose.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.model == "llama3-70b-8192"
    assert output.usage.completion_tokens == 126
    assert output.usage.prompt_tokens == 38
    assert output.usage.total_tokens == 164
    assert output.choices[0].finish_reason == "stop"
    assert (
        output.choices[0].message.content
        == """I totally understand. It can be really frustrating when you feel like you're well-prepared, but your nerves get the better of you during the test. This is actually a very common experience for many students.

Can you tell me more about what happened during the test? What were some of the thoughts that were going through your mind when you started to feel panicked? Was it a specific question that triggered your anxiety, or was it more of a general feeling of overwhelm?

Also, how did you prepare for the test beforehand? Did you feel confident about the material, or were there any areas where you felt a bit uncertain?"""
    )
