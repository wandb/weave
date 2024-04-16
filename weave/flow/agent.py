from typing import Any
from pydantic import Field

import openai
from openai._types import NotGiven
from openai.types.chat import (
    ChatCompletionMessageParam,
)

import weave
from weave.flow.obj import Object
from weave.flow.tools import chat_call_tool_params, perform_tool_calls
from weave.flow.console import LogEvents
from weave.flow.chat_util import OpenAIStream

def get_knowledge():
    knowledge_prefix = """Anytime programmer learns something new that could be useful in the future, automatically save that information in a file called "agent_knowledge.txt" in the same directory.
    When saving, rewrite the whole file, but make sure not to lose any previous knowledge.
    Types of information worth remembering:
    - Preferences and Customizations: How certain tasks should be performed.
    - Locations of Important Files or Directories: The paths to frequently accessed files or directories, especially those related to projects or development environment.
    - Common Errors and Their Solutions: Solutions to common errors or problems that you encounter during your work, which can help in troubleshooting similar issues in the future.
    - Project-Specific Information: Details specific to your projects, such as architecture decisions, important variables, or custom scripts, that are crucial for development and maintenance.
    - Best Practices and Guidelines: Any best practices or guidelines you follow in your work, which could be related to coding standards, security measures, or project management.
    - Learning and Feedback: Insights or feedback from completed tasks that could improve how future tasks are approached or executed.
    
    Whenever possible, use the following learnings to solve problems before resorting to the use of tools:"""

    knowledge_path = "agent_knowledge.txt"
    with open(knowledge_path, "r") as f:
        knowledge_content = f.read()
    return f'{knowledge_prefix}\n{knowledge_content}'


class AgentState(Object):
    # TODO: want openai types here.
    history: list[Any] = Field(default_factory=list)


class Agent(Object):
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.3
    system_message: str
    tools: list[Any] = Field(default_factory=list)

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
            {"role": "system", "content": self.system_message + get_knowledge()},
        ]
        messages += state.history

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
        # we always store the dict representations of messages in agent state
        # instead of mixing in some pydantic objects.
        new_messages.append(response_message.model_dump(exclude_none=True))
        if response_message.tool_calls:
            new_messages.extend(
                perform_tool_calls(self.tools, response_message.tool_calls)
            )

        # TODO: doesn't really belong here.
        # find distance from end to last system message in state.history
        # if distance > 10, append system message
        for distance in range(len(state.history)):
            if state.history[-(distance + 1)]["role"] == "system":
                break
        if distance > 10:
            new_messages.append({"role": "system", "content": get_knowledge()})

        return AgentState(history=state.history + new_messages)
    
    
