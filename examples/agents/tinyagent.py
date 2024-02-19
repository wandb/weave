import subprocess
from rich import print


import weave
from weave.flow import Agent, AgentState

SYSTEM_MESSAGE = """Assistant is an automonmous agent.
Agent likes to explore it's world, using any means necessary.
Agent never stops exploring, it is completely autonomous.
Agent documents its learnings in a file call "journal.txt".
"""


@weave.op()
def run_command(command: str) -> str:
    """Run a shell command and return its output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    return subprocess.check_output(command, shell=True).decode("utf-8")


if __name__ == "__main__":
    # weave.init("wf-agent5")

    agent = Agent(
        model_name="gpt-4-0125-preview",
        system_message=SYSTEM_MESSAGE,
        tools=[run_command],
    )

    initial_state = AgentState(
        history=[
            {
                "role": "user",
                "content": "Explore everything you can find. You are completely autonomous, so don't stop to ask for input, just keep exploring.",
            },
        ]
    )

    agent.run(initial_state)
