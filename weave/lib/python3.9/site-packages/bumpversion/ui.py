"""Utilities for user interface."""

import logging

import click
from click import UsageError, secho
from rich.logging import RichHandler

from bumpversion.indented_logger import IndentedLoggerAdapter

logger = logging.getLogger("bumpversion")

VERBOSITY = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


def get_indented_logger(name: str) -> "IndentedLoggerAdapter":
    """Get a logger with indentation."""
    return IndentedLoggerAdapter(logging.getLogger(name))


def setup_logging(verbose: int = 0) -> None:
    """Configure the logging."""
    logging.basicConfig(
        level=VERBOSITY.get(verbose, logging.DEBUG),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True, show_level=False, show_path=False, show_time=False, tracebacks_suppress=[click]
            )
        ],
    )
    root_logger = get_indented_logger("")
    root_logger.setLevel(VERBOSITY.get(verbose, logging.DEBUG))


def print_info(msg: str) -> None:
    """Echo a message to the console."""
    secho(msg)


def print_error(msg: str) -> None:
    """Raise an error and exit."""
    raise UsageError(msg)


def print_warning(msg: str) -> None:
    """Echo a warning to the console."""
    secho(f"\nWARNING:\n\n{msg}\n", fg="yellow")
