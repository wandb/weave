import asyncio
import os
from typing import Any, Optional, Union

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
    client: weave.trace.weave_client.WeaveClient,
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
        ("groq.chat.completions.create", 0),
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
    client: weave.trace.weave_client.WeaveClient,
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
        ("groq.async.chat.completions.create", 0),
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
    client: weave.trace.weave_client.WeaveClient,
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
        ("groq.chat.completions.create", 0),
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
    client: weave.trace.weave_client.WeaveClient,
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
        ("groq.async.chat.completions.create", 0),
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq_tool_call(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import json

    from groq import Groq

    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "DUMMY_API_KEY"))

    @weave.op()
    def get_game_score(team_name: str) -> str:
        """Get the current score for a given NBA game"""
        if "warriors" in team_name.lower():
            return json.dumps(
                {
                    "game_id": "401585601",
                    "status": "Final",
                    "home_team": "Los Angeles Lakers",
                    "home_team_score": 121,
                    "away_team": "Golden State Warriors",
                    "away_team_score": 128,
                }
            )
        elif "lakers" in team_name.lower():
            return json.dumps(
                {
                    "game_id": "401585601",
                    "status": "Final",
                    "home_team": "Los Angeles Lakers",
                    "home_team_score": 121,
                    "away_team": "Golden State Warriors",
                    "away_team_score": 128,
                }
            )
        elif "nuggets" in team_name.lower():
            return json.dumps(
                {
                    "game_id": "401585577",
                    "status": "Final",
                    "home_team": "Miami Heat",
                    "home_team_score": 88,
                    "away_team": "Denver Nuggets",
                    "away_team_score": 100,
                }
            )
        elif "heat" in team_name.lower():
            return json.dumps(
                {
                    "game_id": "401585577",
                    "status": "Final",
                    "home_team": "Miami Heat",
                    "home_team_score": 88,
                    "away_team": "Denver Nuggets",
                    "away_team_score": 100,
                }
            )
        else:
            return json.dumps({"team_name": team_name, "score": "unknown"})

    @weave.op()
    def run_conversation(user_prompt: str) -> Union[str, None]:
        # Step 1: send the conversation and available functions to the model
        messages = [
            {
                "role": "system",
                "content": "You are a function calling LLM that uses the data extracted from the get_game_score function to answer questions around NBA game scores. Include the team and their opponent in your response.",
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_game_score",
                    "description": "Get the score for a given NBA game",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_name": {
                                "type": "string",
                                "description": "The name of the NBA team (e.g. 'Golden State Warriors')",
                            }
                        },
                        "required": ["team_name"],
                    },
                },
            }
        ]
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
            seed=42,
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        # Step 2: check if the model wanted to call a function
        if tool_calls:
            # Step 3: call the function
            # Note: the JSON response may not always be valid; be sure to handle errors
            available_functions = {
                "get_game_score": get_game_score,
            }  # only one function in this example, but you can have multiple
            messages.append(
                response_message
            )  # extend conversation with assistant's reply
            # Step 4: send the info for each function call and function response to the model
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_functions[function_name]
                function_args = json.loads(tool_call.function.arguments)
                function_response = function_to_call(
                    team_name=function_args.get("team_name")
                )
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )  # extend conversation with function response
            second_response = groq_client.chat.completions.create(
                model="llama3-70b-8192", messages=messages, seed=42
            )  # get a new response from the model where it can see the function response
            return second_response.choices[0].message.content
        return None

    response = run_conversation("What was the score of the Warriors game?")

    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_respose.calls) == 4

    flatened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flatened_calls_list == [
        ("run_conversation", 0),
        ("groq.chat.completions.create", 1),
        ("get_game_score", 1),
        ("groq.chat.completions.create", 1),
    ]

    call_0 = weave_server_respose.calls[0]
    assert call_0.exception is None and call_0.ended_at is not None
    output_0 = _get_call_output(call_0)
    assert output_0 == response

    call_1 = weave_server_respose.calls[1]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = _get_call_output(call_1)
    assert output_1.usage.completion_tokens == 47
    assert output_1.usage.prompt_tokens == 973
    assert output_1.usage.total_tokens == 1020
    assert output_1.usage.completion_time > 0
    assert output_1.usage.prompt_time > 0
    assert output_1.usage.total_time > 0
    assert output_1.model == "llama3-70b-8192"
    assert len(output_1.choices) == 1
    assert output_1.choices[0].finish_reason == "tool_calls"
    assert output_1.choices[0].index == 0
    assert output_1.choices[0].message.role == "assistant"
    assert len(output_1.choices[0].message.tool_calls) == 1
    assert (
        output_1.choices[0].message.tool_calls[0].function.arguments
        == '{"team_name":"Golden State Warriors"}'
    )
    assert output_1.choices[0].message.tool_calls[0].type == "function"

    call_2 = weave_server_respose.calls[2]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = _get_call_output(call_2)
    game_score_data = json.loads(output_2)
    assert game_score_data["game_id"] == "401585601"
    assert game_score_data["status"] == "Final"
    assert game_score_data["home_team"] == "Los Angeles Lakers"
    assert game_score_data["home_team_score"] == 121
    assert game_score_data["away_team"] == "Golden State Warriors"
    assert game_score_data["away_team_score"] == 128

    call_3 = weave_server_respose.calls[3]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = _get_call_output(call_3)
    assert output_3.usage.completion_tokens == 20
    assert output_3.usage.prompt_tokens == 177
    assert output_3.usage.total_tokens == 197
    assert output_3.usage.completion_time > 0
    assert output_3.usage.prompt_time > 0
    assert output_3.usage.total_time > 0
    assert output_3.model == "llama3-70b-8192"
    assert len(output_3.choices) == 1
    assert output_3.choices[0].finish_reason == "stop"
    assert output_3.choices[0].index == 0
    assert output_3.choices[0].message.role == "assistant"
    assert (
        output_3.choices[0].message.content
        == "The Golden State Warriors played against the Los Angeles Lakers and won the game 128-121."
    )
