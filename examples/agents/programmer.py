import subprocess
from rich import print
from rich.console import Console
import sys


import weave
from weave.flow import Agent, AgentState

WELCOME = """
Welcome to programmer.

What would you like to do?

"""

SYSTEM_MESSAGE = """Assistant is a programming assistant named "programmer".
programmer is fairly autonomous, and tries to proceed on its own to solve problems.
programmer always has access to a shell and local filesystem in perform tasks, via the run_command tool.
programmer is managed by the user. The user will provide guidance and feedback.
programmer's goal is contained in the spec.txt file.
programmer writes files using the provided tools.
"""

console = Console()

import json
import os

LENGTH_LIMIT = 1000


@weave.op()
def list_files(directory: str) -> str:
    """List names of all files in a directory.

    Args:
        directory: The directory to list.

    Returns:
        The list of files in the directory.
    """
    try:
        result = json.dumps(os.listdir(directory))
        if len(result) > LENGTH_LIMIT:
            result = result[:LENGTH_LIMIT]
            result += "\n... (truncated)"
        return result
    except Exception as e:
        return json.dumps([str(e)])


@weave.op()
def write_to_file(path: str, content: str) -> str:
    """Write text to a file at the tiven path.

    Args:
        path: The path to the file.
        content: The content to write to the file.

    Returns:
        A message indicating whether the file was written successfully.
    """
    try:
        with open(path, "w") as f:
            f.write(content)
        return "File written successfully."
    except Exception as e:
        return str(e)


@weave.op()
def read_from_file(path: str) -> str:
    """Read text from a file at the given path.

    Args:
        path: The path to the file.

    Returns:
        The content of the file.
    """
    try:
        with open(path, "r") as f:
            result = f.read()
            if len(result) > LENGTH_LIMIT:
                result = result[:LENGTH_LIMIT]
                result += "\n... (truncated)"
            return result
    except Exception as e:
        return str(e)


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
    # weave.init("wf-programmer1")
    console.rule("[bold blue]Programmer")
    console.print(WELCOME)

    agent = Agent(
        model_name="gpt-4-0125-preview",
        system_message=SYSTEM_MESSAGE,
        tools=[list_files, write_to_file, read_from_file, run_command],
    )

    # initial_prompt = input("Initial prompt: ")

    initial_prompt = " ".join(sys.argv[1:])
    print("Initial prompt:", initial_prompt)

    initial_state = AgentState(
        history=[
            {
                "role": "user",
                "content": initial_prompt,
            },
        ]
    )

    agent.run(initial_state)
