import json
import os
from typing import Any, Optional

import pytest
from groq import Groq

import weave
from weave.trace_server import trace_server_interface as tsi

from .groq import groq_patcher


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
def test_groq_function_calling_example(client: weave.weave_client.WeaveClient) -> None:
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    MODEL = "llama3-70b-8192"
    SEED = 42

    @weave.op()
    def get_game_score(team_name):
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
    def run_conversation(user_prompt):
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
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
            seed=SEED,
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
                model=MODEL, messages=messages, seed=SEED
            )  # get a new response from the model where it can see the function response
            return second_response.choices[0].message.content

    user_prompt = "What was the score of the Warriors game?"
    result = run_conversation(user_prompt)
    assert "128-121" in result
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_respose.calls) == 4

    call_1 = weave_server_respose.calls[1]
    assert call_1.exception is None and call_1.ended_at is not None
    output_1 = _get_call_output(call_1)
    assert output_1.model == MODEL
    assert output_1.usage.completion_tokens == 47
    assert output_1.usage.prompt_tokens == 973
    assert output_1.usage.total_tokens == 1020
    assert (
        output_1.choices[0].message.tool_calls[0].function.arguments
        == '{"team_name":"Golden State Warriors"}'
    )

    call_2 = weave_server_respose.calls[2]
    assert call_2.exception is None and call_2.ended_at is not None
    output_2 = _get_call_output(call_2)
    assert (
        output_2
        == '{"game_id": "401585601", "status": "Final", "home_team": "Los Angeles Lakers", "home_team_score": 121, "away_team": "Golden State Warriors", "away_team_score": 128}'
    )

    call_3 = weave_server_respose.calls[3]
    assert call_3.exception is None and call_3.ended_at is not None
    output_3 = _get_call_output(call_3)
    assert output_3.model == MODEL
    assert output_3.usage.completion_tokens == 20
    assert output_3.usage.prompt_tokens == 175
    assert output_3.usage.total_tokens == 195
    assert (
        output_3.choices[0].message.content
        == "The Golden State Warriors played against the Los Angeles Lakers and won the game 128-121."
    )
