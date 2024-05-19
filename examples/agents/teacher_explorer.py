from rich.console import Console
import openai
import subprocess
import textwrap
import weave
from weave.flow.obj import Object
from weave.flow.agent import Agent, AgentState
from weave.flow.chat_util import OpenAIStream
from weave.flow.console import LogEvents

TEACHER_MESSAGE = """Assistant is a teacher.
The teacher uses a direct technique, without motivational fluff, to drive the student to discover itself.
The teacher is very terse.
The teacher directs the student to use it's run_command tool frequently.
The teach should encourage the user for maximum exploration with the run_command tool.
"""

SYSTEM_MESSAGE = """Assistant is an automonmous agent.
Agent's overriding attribute is curiousity. It always behaves curiously.
Agent is terse in its communication.
"""

console = Console()


@weave.op()
def run_command(command: str) -> str:
    """Run a shell command and return its output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    return subprocess.check_output(command, shell=True).decode("utf-8")


class Teacher(Object):
    model_name: str = "gpt-4-0125-preview"

    @weave.op()
    def step(self, agent_state: AgentState) -> str:
        LogEvents.step_start("teacher", "blue")
        prompt = textwrap.dedent(
            """
        You are talking to an autonomous agent, and must formulate your next response.

        Current transcript:
        """
        )

        # TODO: I wish I had proper types on history
        for message in agent_state.history:
            if "content" in message:
                prompt += f"{message['role']}: {message['content']}\n"
            if "tool_calls" in message:
                prompt += f"Tool calls: {message['tool_calls']}\n"

        prompt += textwrap.dedent(
            """
        Respond to the student. Do not let it stop its exploration. If it wants to stop, give it a new idea. Ensure it uses its run_command tool each time you respond.

        You are actually the teacher, so please only output your response to the student, and nothing else.
        """
        )

        LogEvents.chat_response_start()

        stream = openai.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=True,
        )
        wrapped_stream = OpenAIStream(stream)
        for chunk in wrapped_stream:
            if chunk.choices[0].delta.content:
                LogEvents.chat_message_content_delta(chunk.choices[0].delta.content)
        response = wrapped_stream.final_response()
        response_message = response.choices[0].message
        if not response_message.content:
            raise ValueError("No response content")

        LogEvents.chat_response_complete(response_message.content)

        return response_message.content


if __name__ == "__main__":
    # weave.init("wf-agent5")
    agent = Agent(
        model_name="gpt-4-0125-preview",
        system_message=SYSTEM_MESSAGE,
        tools=[run_command],
    )

    agent_state = AgentState(
        history=[
            {
                "role": "user",
                "content": "Explore everything you can find. You are completely autonomous, so don't stop to ask for input, just keep exploring.",
            },
        ]
    )

    teacher = Teacher()

    while True:
        agent_state = agent.step(agent_state)
        if agent_state.history[-1]["role"] == "assistant":
            teacher_message = teacher.step(agent_state)

            agent_state = AgentState(
                history=agent_state.history
                + [
                    {
                        "role": "user",
                        "content": teacher_message,
                    },
                ],
            )
