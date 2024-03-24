import json
import subprocess
from rich import print


import weave
from weave.flow.agent import Agent, AgentState

SYSTEM_MESSAGE = """Assistant is an automonmous agent.
Agent likes to explore it's world, using any means necessary.
Agent never stops exploring, it is completely autonomous.
Agent documents its learnings in a file call "journal.txt".
"""

LENGTH_LIMIT = 1000


@weave.op()
def run_command(command: str) -> str:
    """Run a shell command and return its output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    try:
        completed_process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        exit_code = completed_process.returncode
        stdout = completed_process.stdout.strip()
        stderr = completed_process.stderr.strip()
    except Exception as e:
        exit_code = -1
        stdout = ""
        stderr = str(e)

    if len(stdout) > LENGTH_LIMIT:
        stdout = stdout[:LENGTH_LIMIT]
        stdout += "\n... (truncated)"
    if len(stderr) > LENGTH_LIMIT:
        stderr = stderr[:LENGTH_LIMIT]
        stderr += "\n... (truncated)"

    return json.dumps({"exit_code": exit_code, "stdout": stdout, "stderr": stderr})


if __name__ == "__main__":
    # weave.init("wf-explorer1")

    agent = Agent(
        model_name="gpt-4-0125-preview",
        system_message=SYSTEM_MESSAGE,
        tools=[run_command],
    )

    state = AgentState(
        history=[
            {
                "role": "user",
                "content": "Explore everything you can find, using your tools. You are completely autonomous, so don't stop to ask for input, just keep exploring.",
            },
        ]
    )

    while True:
        state = agent.step(state)
        last_message = state.history[-1]
        if last_message["role"] == "assistant" and "tool_calls" not in last_message:
            user_input = input("User input: ")
            state = AgentState(
                history=state.history
                + [
                    {
                        "role": "user",
                        "content": user_input,
                    }
                ]
            )
