import asyncio
import json

import openai

import weave
from weave.trace.thread_host import ThreadPredictRequest, host_op

STATE_TYPE = list[dict]

thread_state: dict[str, STATE_TYPE] = {}

@weave.op
async def search_weather(location: str) -> str:
    await asyncio.sleep(1)
    return f"The weather in {location} is sunny and 72°F"

@weave.op
async def search_restaurants(cuisine: str, location: str) -> str:
    await asyncio.sleep(1)
    return f"Found 3 {cuisine} restaurants in {location}: Restaurant A, Restaurant B, Restaurant C"

@weave.op
async def get_directions(start: str, end: str) -> str:
    await asyncio.sleep(1)
    return f"Directions from {start} to {end}: Head north for 2 blocks, turn right..."

@weave.op
async def execute_function_call(function_name: str, function_args: dict) -> str:
    if function_name == "search_weather":
        return await search_weather(**function_args)
    elif function_name == "search_restaurants":
        return await search_restaurants(**function_args)
    elif function_name == "get_directions":
        return await get_directions(**function_args)
    return None

@weave.op()
async def predict(input: str, thread_id: str) -> str:
    curr_state = thread_state.get(thread_id, [])
    new_state = curr_state + [{"role": "user", "content": input}]
    thread_state[thread_id] = new_state

    functions = [
        {
            "name": "search_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        },
        {
            "name": "search_restaurants",
            "description": "Find restaurants of a specific cuisine type in a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "cuisine": {"type": "string", "description": "Type of cuisine"},
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["cuisine", "location"]
            }
        },
        {
            "name": "get_directions",
            "description": "Get directions between two locations",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Starting location"},
                    "end": {"type": "string", "description": "Destination location"}
                },
                "required": ["start", "end"]
            }
        }
    ]

    client = openai.OpenAI()
    max_steps = 10  # Maximum number of steps to prevent infinite loops
    current_step = 0
    final_response = None

    while current_step < max_steps:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=new_state,
            functions=functions,
            function_call="auto"
        )

        response_message = response.choices[0].message

        if not response_message.function_call:
            final_response = response_message.content
            break

        function_name = response_message.function_call.name
        function_args = json.loads(response_message.function_call.arguments)

        function_response = await execute_function_call(function_name, function_args)

        new_state.append({
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": function_name,
                "arguments": response_message.function_call.arguments
            }
        })
        new_state.append({
            "role": "function",
            "name": function_name,
            "content": function_response
        })

        # Check if the assistant wants to take another action
        followup = client.chat.completions.create(
            model="gpt-4",
            messages=new_state,
            functions=functions,
            function_call="auto"
        )

        if not followup.choices[0].message.function_call:
            final_response = followup.choices[0].message.content
            break

        current_step += 1

    if final_response is None:
        final_response = "I've taken too many steps and need to stop now. Here's what I've found so far."

    final_state = new_state + [{"role": "assistant", "content": final_response}]
    thread_state[thread_id] = final_state
    return final_response


class PredictRequest(ThreadPredictRequest):
    input: str

weave.init("threading-demo")
host_op(PredictRequest, predict)
