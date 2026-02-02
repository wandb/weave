"""Login command for the Weave CLI."""

from __future__ import annotations

from typing import Literal

import click

from weave.compat import wandb
from weave.compat.wandb.wandb_thin.login import (
    _get_default_host as _compat_get_default_host,
)


def _get_default_host() -> str:
    return _compat_get_default_host()


@click.command("login")
@click.argument("key", required=False)
@click.option(
    "--anonymous",
    type=click.Choice(["allow", "must", "never"], case_sensitive=False),
    default=None,
    help="Control anonymous login behavior.",
)
@click.option(
    "--relogin",
    is_flag=True,
    default=False,
    help="Force a relogin even if an API key is already configured.",
)
@click.option(
    "--host",
    default=None,
    help="W&B host URL, e.g. https://api.wandb.ai",
)
@click.option(
    "--verify/--no-verify",
    default=False,
    help="Verify the API key with the server.",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Seconds to wait for user input.",
)
def login(
    key: str | None,
    anonymous: Literal["allow", "must", "never"] | None,
    relogin: bool,
    host: str | None,
    verify: bool,
    timeout: int | None,
) -> None:
    """Log in to Weights & Biases for Weave."""
    normalized_host = host
    if normalized_host is not None and not normalized_host.startswith(
        ("http://", "https://")
    ):
        normalized_host = f"https://{normalized_host}"

    try:
        success = wandb.login(
            anonymous=anonymous,
            key=key,
            relogin=relogin,
            host=normalized_host,
            force=relogin,
            timeout=timeout,
            verify=verify,
            referrer="cli",
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if not success:
        raise click.ClickException("Login failed.")
