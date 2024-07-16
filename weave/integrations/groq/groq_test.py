import asyncio
import os
from typing import Any, Optional

import pytest

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
    from groq import Groq

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
    from groq import AsyncGroq

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
            model="llama3-8b-8192",
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
    assert output.model == "llama3-8b-8192"
    assert output.usage.completion_tokens == 152
    assert output.usage.prompt_tokens == 38
    assert output.usage.total_tokens == 190
    assert output.choices[0].finish_reason == "stop"
    assert (
        output.choices[0].message.content
        == """It sounds like you're feeling really frustrated and disappointed with yourself right now. It's completely normal to feel that way, especially when you're used to performing well and then suddenly feel like you've let yourself down.

Can you tell me more about what happened during the test? What was going through your mind when you started to feel panicked? Was it the pressure of the test itself, or was there something else that triggered your anxiety?

Also, have you experienced panic or anxiety during tests before? If so, what strategies have you used to cope with those feelings in the past?

Remember, as your psychiatrist, my goal is to help you understand what's going on and find ways to manage your anxiety so you can perform to the best of your ability."""
    )


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq_streaming_chat_completion(
    client: weave.weave_client.WeaveClient,
) -> None:
    from groq import Groq

    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", "DUMMY_API_KEY"))

    stream = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "you are a helpful assistant."},
            {
                "role": "user",
                "content": "Explain the importance of fast language models",
            },
        ],
        model="llama3-8b-8192",
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        stop=None,
        stream=True,
        seed=42,
    )

    all_content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            all_content += chunk.choices[0].delta.content

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
    assert output.model == "llama3-8b-8192"
    assert output.object == "chat.completion"
    assert output.usage.completion_tokens == 533
    assert output.usage.prompt_tokens == 29
    assert output.usage.total_tokens == 562
    assert output.usage.completion_time > 0
    assert output.usage.prompt_time > 0
    assert output.usage.queue_time > 0
    assert output.usage.total_time > 0

    assert len(output.choices) == 1
    assert output.choices[0].finish_reason == "stop"
    assert output.choices[0].index == 0
    assert output.choices[0].message.role == "assistant"
    assert (
        output.choices[0].message.content
        == """Fast language models have gained significant attention in recent years due to their ability to process and generate human-like language at incredibly high speeds. Here are some reasons why fast language models are important:

1. **Real-time Applications**: Fast language models can be used in real-time applications such as chatbots, virtual assistants, and language translation systems. They can quickly respond to user queries, making them more interactive and engaging.
2. **Efficient Processing**: Fast language models can process large amounts of text data quickly, making them ideal for tasks such as sentiment analysis, text classification, and topic modeling. This efficiency is particularly important in applications where speed is critical, such as in customer service or emergency response systems.
3. **Improved Responsiveness**: Fast language models can respond quickly to user input, reducing the latency and improving the overall user experience. This is particularly important in applications where users expect instant responses, such as in gaming or social media platforms.
4. **Scalability**: Fast language models can handle large volumes of data and scale up or down as needed, making them suitable for applications with varying traffic patterns.
5. **Advancements in AI Research**: Fast language models have enabled researchers to explore new areas of natural language processing (NLP), such as language generation, question answering, and dialogue systems. This has led to significant advancements in AI research and the development of more sophisticated language models.
6. **Improved Language Understanding**: Fast language models can be fine-tuned for specific tasks, such as named entity recognition, part-of-speech tagging, and dependency parsing. This has led to improved language understanding and better performance in various NLP tasks.
7. **Enhanced User Experience**: Fast language models can be used to create more personalized and engaging user experiences, such as recommending products or services based on user preferences and behavior.
8. **Cost-Effective**: Fast language models can be more cost-effective than traditional language models, as they require less computational resources and can be deployed on cloud-based infrastructure.
9. **Faster Development Cycles**: Fast language models can accelerate the development cycle of language-based applications, enabling developers to iterate and refine their models more quickly.
10. **Broader Adoption**: Fast language models have made NLP more accessible to a broader range of developers and organizations, enabling them to build language-based applications without requiring extensive expertise in NLP.

In summary, fast language models have revolutionized the field of NLP, enabling the development of more efficient, scalable, and responsive language-based applications. Their importance lies in their ability to process and generate human-like language at incredible speeds, making them a crucial component of many modern AI systems."""
    )


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq_async_streaming_chat_completion(
    client: weave.weave_client.WeaveClient,
) -> None:
    from groq import AsyncGroq

    groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "DUMMY_API_KEY"))

    async def generate_reponse() -> str:

        chat_streaming = await groq_client.chat.completions.create(
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
            model="llama3-8b-8192",
            temperature=0.3,
            max_tokens=360,
            top_p=1,
            stop=None,
            stream=True,
            seed=42,
        )

        all_content = ""
        async for chunk in chat_streaming:
            if chunk.choices[0].delta.content is not None:
                all_content += chunk.choices[0].delta.content

        return all_content

    asyncio.run(generate_reponse())

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
    assert output.model == "llama3-8b-8192"
    assert output.usage.completion_tokens == 152
    assert output.usage.prompt_tokens == 38
    assert output.usage.total_tokens == 190
    assert output.usage.completion_time > 0
    assert output.usage.prompt_time > 0
    assert output.usage.queue_time > 0
    assert output.usage.total_time > 0
    assert output.choices[0].finish_reason == "stop"
    assert (
        output.choices[0].message.content
        == """It sounds like you're feeling really frustrated and disappointed with yourself right now. It's completely normal to feel that way, especially when you're used to performing well and then suddenly feel like you've let yourself down.

Can you tell me more about what happened during the test? What was going through your mind when you started to feel panicked? Was it the pressure of the test itself, or was there something else that triggered your anxiety?

Also, have you experienced panic or anxiety during tests before? If so, what strategies have you used to cope with those feelings in the past?

Remember, as your psychiatrist, my goal is to help you understand what's going on and find ways to manage your anxiety so you can perform to the best of your ability."""
    )
