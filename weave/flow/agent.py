import json
import inspect
from rich import print
from rich.console import Console
from rich.text import Text
from rich.padding import Padding

from pydantic import Field
from typing import Callable, get_type_hints, Any, Iterator, Optional

import openai
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
    ChatCompletionChunk,
)
from openai.types.chat.chat_completion import ChatCompletion

import weave
from weave.flow import Object

console = Console()


def generate_json_schema(func: Callable):
    """Given a function, generate an OpenAI tool compatible JSON schema.

    WIP: This function is very basic and hacky. It will not work in many
    scenarios.
    """
    # Extract function signature
    signature = inspect.signature(func)
    parameters = signature.parameters

    # Extract annotations
    type_hints = get_type_hints(func)

    # Initialize the schema structure
    schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__.split("\n")[0] if func.__doc__ else "",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }

    # Process each parameter
    for name, param in parameters.items():
        # Determine if this parameter is required (no default value)
        is_required = param.default == inspect.Parameter.empty

        # Extract parameter type and description
        param_type = type_hints[name].__name__ if name in type_hints else "string"
        if param_type == "str":
            param_type = "string"
        param_desc = ""

        # Attempt to extract description from docstring
        if func.__doc__:
            doc_lines = func.__doc__.split("\n")[1:]
            for line in doc_lines:
                if name in line:
                    param_desc = line.strip().split(":")[-1].strip()
                    break

        # Populate schema for this parameter
        param_schema = {"type": param_type, "description": param_desc}

        # Handle special case for enums
        if hasattr(type_hints[name], "__members__"):  # Check if it's an Enum
            param_schema["enum"] = [e.value for e in type_hints[name]]

        schema["function"]["parameters"]["properties"][name] = param_schema

        if is_required:
            schema["function"]["parameters"]["required"].append(name)

    return schema


class OpenAIStream:
    """
    A class that reconstructs a ChatCompletion from an OpenAI stream.

    Usage: initialize this class, iterate through all the chunks, then
    call final_response to get the final ChatCompletion.

    Args:
        chunk_iter: The output of an openai chat completion streaming=True call.
    """

    def __init__(self, chunk_iter: Iterator[ChatCompletionChunk]) -> None:
        self.chunk_iter = chunk_iter
        self.first_chunk: Optional[ChatCompletionChunk] = None
        self.output_choices: list[dict] = []

    def __iter__(self):
        for chunk in self.chunk_iter:
            yield chunk
            if self.first_chunk is None:
                self.first_chunk = chunk
            for chunk_choice in chunk.choices:
                for i in range(chunk_choice.index + 1 - len(self.output_choices)):
                    self.output_choices.append(
                        {
                            "index": len(self.output_choices),
                            "message": {
                                "content": None,
                                "tool_calls": None,
                            },
                            "finish_reason": None,
                            "logprobs": None,
                        }
                    )

                # choice fields
                choice = self.output_choices[chunk_choice.index]
                if chunk_choice.finish_reason:
                    choice["finish_reason"] = chunk_choice.finish_reason
                if chunk_choice.logprobs:
                    choice["logprobs"] = chunk_choice.logprobs

                # message
                if chunk_choice.delta.content:
                    if choice["message"]["content"] is None:
                        choice["message"]["content"] = ""
                    choice["message"]["content"] += chunk_choice.delta.content
                if chunk_choice.delta.role:
                    choice["message"]["role"] = chunk_choice.delta.role

                # function call
                if chunk_choice.delta.function_call:
                    raise NotImplementedError("Function calls not supported")

                # tool calls
                if chunk_choice.delta.tool_calls:
                    if choice["message"]["tool_calls"] is None:
                        choice["message"]["tool_calls"] = []
                    for tool_call_delta in chunk_choice.delta.tool_calls:
                        for i in range(
                            tool_call_delta.index
                            + 1
                            - len(choice["message"]["tool_calls"])
                        ):
                            choice["message"]["tool_calls"].append(
                                {
                                    "function": {"name": None, "arguments": ""},
                                }
                            )
                        tool_call = choice["message"]["tool_calls"][
                            tool_call_delta.index
                        ]
                        if tool_call_delta.id is not None:
                            tool_call["id"] = tool_call_delta.id
                        if tool_call_delta.type is not None:
                            tool_call["type"] = tool_call_delta.type
                        if tool_call_delta.function is not None:
                            if tool_call_delta.function.name is not None:
                                tool_call["function"][
                                    "name"
                                ] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments is not None:
                                tool_call["function"][
                                    "arguments"
                                ] += tool_call_delta.function.arguments

    def final_response(self):
        if self.first_chunk is None:
            raise ValueError("No chunks received")
        return ChatCompletion(
            id=self.first_chunk.id,
            choices=self.output_choices,  # type: ignore
            created=self.first_chunk.created,
            model=self.first_chunk.model,
            object="chat.completion",
        )


class AgentEvents:
    @staticmethod
    def agent_step_start():
        console.rule("[bold green]Begin agent step")

    @staticmethod
    def agent_response_start():
        pass

    @staticmethod
    def agent_message_content_delta(message_content_delta: str):
        console.print(message_content_delta, end="")

    @staticmethod
    def agent_response_complete(agent_response: str):
        console.print("\n")
        console.print("[bold green]Agent response:[/bold green]\n")
        console.print(Padding.indent(f"{agent_response}\n", 4))

    @staticmethod
    def tool_call_start(tool_call: str):
        console.print(f"[bold yellow]Tool call: [/bold yellow]{tool_call}\n")

    @staticmethod
    def tool_call_complete(tool_response: str):
        lines = tool_response.split("\n")
        if len(lines) > 4:
            lines = lines[:4]
            lines.append("...")
            tool_response = "\n".join(lines)
        console.print(
            Padding.indent(f"{tool_response}\n", 4),
            no_wrap=True,
            overflow="ellipsis",
        )

    @staticmethod
    def user_input_complete(user_input: str):
        console.print()


class AgentState(Object):
    status: str = "running"  # TODO: Enum
    history: list[Any] = Field(default_factory=list)


class Agent(Object):
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7

    # TODO: want Callable, but have an issue with type saving
    get_input: Any = lambda: input("User input: ")
    tools: list[Any] = Field(default_factory=list)

    system_message: str

    def get_tool(self, name: str) -> Callable:
        for t in self.tools:
            if t.__name__ == name:
                return t
        raise KeyError(f"No tool with name {name} found")

    @weave.op()
    def run(self, state: AgentState):
        while not state.status == "DONE":
            state = self.step(state)

    @weave.op()
    def step(self, state: AgentState) -> AgentState:
        """Run a step of the agent.

        Args:
            state: The current state of the environment.
            action: The action to take.

        Returns:
            The new state of the environment.
        """
        AgentEvents.agent_step_start()
        functions = [generate_json_schema(tool) for tool in self.tools]

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_message},
        ]
        messages += state.history

        # TODO: have to strip Nones, because reading list back from
        # Weave object injects them, due to type merging.
        # It's also odd that we're even reading back at all, I think that's
        # the auto-publish path, it doesn't put obj into created refs, so when
        # we go to deref in auth-publish, we don't get the original object.
        # This will incur significant API overhead.
        messages = [{k: v for k, v in m.items() if v is not None} for m in messages]  # type: ignore

        # Convert functions list to ChatCompletionToolParam objects
        tools = [ChatCompletionToolParam(**tool) for tool in functions]

        # So this returns a stream
        AgentEvents.agent_response_start()
        # with console.status("Calling LLM"):
        stream = openai.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=True,
        )
        wrapped_stream = OpenAIStream(stream)
        for chunk in wrapped_stream:
            if chunk.choices[0].delta.content:
                AgentEvents.agent_message_content_delta(chunk.choices[0].delta.content)

        response = wrapped_stream.final_response()
        response_message = response.choices[0].message
        if response_message.content:
            AgentEvents.agent_response_complete(response_message.content)

        new_messages = []
        new_messages.append(response_message.model_dump(exclude_none=True))
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                tool = self.get_tool(function_name)
                function_response = None
                tool_call_s = f"{function_name}({tool_call.function.arguments})"
                AgentEvents.tool_call_start(tool_call_s)
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    function_response = str(e)
                if not function_response:
                    try:
                        function_response = str(tool(**function_args))
                    except Exception as e:
                        function_response = str(e)

                AgentEvents.tool_call_complete(function_response)
                new_messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": function_response,
                    }
                )
        else:
            user_input = self.get_input()
            AgentEvents.user_input_complete(user_input)
            new_messages.append({"role": "user", "content": user_input})
        new_s = AgentState(status="RUNNING", history=state.history + new_messages)
        return new_s
