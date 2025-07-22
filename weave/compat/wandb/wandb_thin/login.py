from __future__ import annotations

import logging
from typing import Literal

import click

from weave.compat.wandb.util.netrc import Netrc
from weave.compat.wandb.wandb_thin import util

logger = logging.getLogger(__name__)


def login(
    anonymous: Literal["must", "allow", "never"] | None = None,
    key: str | None = None,
    relogin: bool | None = None,
    host: str | None = None,
    force: bool | None = None,
    timeout: int | None = None,
    verify: bool = False,
    referrer: str | None = None,
) -> None:
    """Login to Weights & Biases.

    This shape is kept to conform with the interface of the original wandb.login.
    We don't use all of the settings.
    """
    return _login(host=host)


def _login(host: str | None = None) -> None:
    if host is None:
        host = "api.wandb.ai"
    else:
        host = _parse_wandb_host(host)

    netrc = Netrc()
    credentials = netrc.get_credentials(host)
    if credentials is None:
        app_url = util.app_url(host)
        logger.info("Logging into Weights & Biases")
        logger.info(f"You can find your API key in your browser here: {app_url}")
        logger.info("Paste an API key from your profile and hit enter:")
        api_key = click.prompt(
            "Enter your Weights & Biases API key", hide_input=True, err=True
        )
        logger.info("")
        _validate_api_key(api_key)
        netrc.add_or_update_entry(host, "user", api_key)
    else:
        api_key = credentials["password"]


def _validate_api_key(api_key: str) -> None:
    if "-" in api_key:  # on-prem style
        _, key = api_key.split("-", 1)
    else:  # normal style
        key = api_key

    if len(key) != 40:
        raise ValueError(
            f"API key must be 40 characters long, yours was {len(key)}"
        ) from None


def _parse_wandb_host(host: str) -> str:
    """
    Parse a W&B host URL to extract the hostname.

    Args:
        host (str): The host URL (e.g., 'https://api.wandb.ai/' or 'api.wandb.ai').

    Returns:
        str: The hostname without protocol or trailing slash (e.g., 'api.wandb.ai').

    Examples:
        >>> _parse_wandb_host('https://api.wandb.ai/')
        'api.wandb.ai'
        >>> _parse_wandb_host('http://localhost:8080')
        'localhost:8080'
        >>> _parse_wandb_host('api.wandb.ai')
        'api.wandb.ai'
    """
    # Remove protocol if present
    if host.startswith(("http://", "https://")):
        host = host.split("://", 1)[1]

    # Remove trailing slash if present
    if host.endswith("/"):
        host = host[:-1]

    return host
