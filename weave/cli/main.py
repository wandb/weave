"""Entry point for the Weave CLI."""

from __future__ import annotations

import logging

import click

from weave.cli.login import login as login_command


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


@click.group()
def main() -> None:
    """Weave command line interface."""
    _configure_logging()


main.add_command(login_command)
