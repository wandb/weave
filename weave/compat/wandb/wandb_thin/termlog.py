"""
This file is largely copied from the wandb library, with a few changes to make
the file more standalone."""

import sys
from typing import Any

import click

LOG_STRING = click.style("wandb", fg="blue", bold=True)
LOG_STRING_NOCOLOR = "wandb"
ERROR_STRING = click.style("ERROR", bg="red", fg="green")
WARN_STRING = click.style("WARNING", fg="yellow")
PRINTED_MESSAGES = set()  # type: ignore


def termlog(
    string: str = "",
    newline: bool = True,
    repeat: bool = True,
    prefix: bool = True,
) -> None:
    """Log to standard error with formatting.

    Arguments:
        string (str, optional): The string to print
        newline (bool, optional): Print a newline at the end of the string
        repeat (bool, optional): If set to False only prints the string once per process
        prefix (bool, optional): If set to False, the prefix is not printed
    """
    _log(
        string=string,
        newline=newline,
        repeat=repeat,
        prefix=prefix,
    )


def termwarn(string: str, **kwargs: Any) -> None:
    string = "\n".join([f"{WARN_STRING} {s}" for s in string.split("\n")])
    _log(
        string=string,
        newline=True,
        **kwargs,
    )


def termerror(string: str, **kwargs: Any) -> None:
    string = "\n".join([f"{ERROR_STRING} {s}" for s in string.split("\n")])
    _log(
        string=string,
        newline=True,
        **kwargs,
    )


def _log(
    string: str = "",
    newline: bool = True,
    repeat: bool = True,
    prefix: bool = True,
) -> None:
    if string:
        if prefix:
            line = "\n".join([f"{LOG_STRING}: {s}" for s in string.split("\n")])
        else:
            line = string
    else:
        line = ""
    if not repeat and line in PRINTED_MESSAGES:
        return
    # Repeated line tracking limited to 1k messages
    if len(PRINTED_MESSAGES) < 1000:
        PRINTED_MESSAGES.add(line)
    click.echo(line, file=sys.stderr, nl=newline)
