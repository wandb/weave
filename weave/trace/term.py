# Inspired from `wandb` terminal logging (eg. /wandb/errors/term.py)

import logging

import click

from weave.trace.settings import should_be_silent

LOG_STRING = click.style("weave", fg="yellow", bold=True)

_logger = logging.getLogger("weave")


def weave_print(
    string: str,
    *,
    # Defaulting to `False` for now, but I think we should enable this by default.
    prefix: bool = False,
) -> None:
    _log(
        string=string,
        prefix=prefix,
        silent=should_be_silent(),
        level=logging.INFO,
    )


def _log(
    string: str = "",
    prefix: bool = True,
    silent: bool = False,
    level: int = logging.INFO,
) -> None:
    if string:
        if prefix:
            line = "\n".join([f"{LOG_STRING}: {s}" for s in string.split("\n")])
        else:
            line = string
    else:
        line = ""

    if silent:
        if level == logging.ERROR:
            _logger.error(line)
        elif level == logging.WARNING:
            _logger.warning(line)
        else:
            _logger.info(line)
    else:
        click.echo(line)
