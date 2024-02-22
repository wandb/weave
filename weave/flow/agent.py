from typing import Any
from pydantic import Field

import openai
from openai._types import NotGiven
from openai.types.chat import (
    ChatCompletionMessageParam,
)

import weave
from weave.flow import Object
from weave.flow.tools import chat_call_tool_params, perform_tool_calls
from weave.flow.logs import LogEvents
from weave.flow.chat_util import OpenAIStream


class AgentState(Object):
    status: str = "running"  # TODO: Enum
    # TODO: want openai types here.
    history: list[Any] = Field(default_factory=list)


class Agent(Object):
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7

    # TODO: want Callable, but have an issue with type saving
    get_input: Any = lambda: input("User input: ")
    tools: list[Any] = Field(default_factory=list)

    system_message: str

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
        LogEvents.step_start("agent", "green")

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

        # make type checkers happy by passing NotGiven instead of None
        tools = NotGiven()
        if self.tools:
            tools = chat_call_tool_params(self.tools)

        LogEvents.chat_response_start()
        stream = openai.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=messages,
            tools=tools,
            stream=True,
        )
        wrapped_stream = OpenAIStream(stream)
        # with console.status("Streaming LLM response..."):
        for chunk in wrapped_stream:
            if chunk.choices[0].delta.content:
                LogEvents.chat_message_content_delta(chunk.choices[0].delta.content)

        response = wrapped_stream.final_response()
        response_message = response.choices[0].message
        if response_message.content:
            LogEvents.chat_response_complete(response_message.content)

        new_messages = []
        new_messages.append(response_message.model_dump(exclude_none=True))
        if response_message.tool_calls:
            new_messages.extend(
                perform_tool_calls(self.tools, response_message.tool_calls)
            )
        else:
            user_input = self.get_input()
            LogEvents.user_input_complete(user_input)
            new_messages.append({"role": "user", "content": user_input})

        # find distance from end to last system message in state.history
        # if distance > 10, append system message
        for distance in range(len(state.history)):
            if state.history[-(distance + 1)]["role"] == "system":
                break
        if distance > 10:
            new_messages.append({"role": "system", "content": self.system_message})

        return AgentState(status="RUNNING", history=state.history + new_messages)
