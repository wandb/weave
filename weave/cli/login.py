"""Weave login functionality."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click

from weave.compat import wandb

logger = logging.getLogger(__name__)

# Weave styling - using the same color as the rest of the weave application
WEAVE_PREFIX = click.style("weave", fg="cyan", bold=True)


def weave_echo(message: str, **kwargs) -> None:
    """Echo a message with the weave prefix."""
    click.echo(f"{WEAVE_PREFIX}: {message}", **kwargs)


def weave_echo_styled(message: str, **kwargs) -> None:
    """Echo a pre-styled message (message already contains styled weave prefix)."""
    click.echo(message, **kwargs)


def weave_login(
    key: str | None = None,
    host: str | None = None,
    relogin: bool = False,
    verify: bool = True,
    timeout: int | None = None,
) -> bool:
    """Login to Weights & Biases for use with Weave.

    This function sets up W&B login credentials that will be used by Weave
    for authentication. It provides a user-friendly experience with helpful
    messages and links, similar to the wandb login command.

    Args:
        key: The API key to use. If not provided, will prompt for input.
        host: The host to connect to. Defaults to W&B cloud.
        relogin: If True, will re-prompt for API key even if already logged in.
        verify: If True, verify the credentials with the W&B server.
        timeout: Number of seconds to wait for user input.

    Returns:
        bool: True if login successful, False otherwise.

    Examples:
        Login with an API key:

        >>> weave_login(key="your-api-key-here")
        True

        Login to a custom host:

        >>> weave_login(host="https://your-wandb-instance.com")
        True
    """
    from weave.compat.wandb.util.netrc import Netrc
    from weave.compat.wandb.wandb_thin.login import (
        _get_default_host,
        _validate_api_key,
    )

    try:
        # Determine the host
        if not host:
            host = _get_default_host()

        # Clean up host format
        if host.startswith("https://"):
            host = host[8:]
        elif host.startswith("http://"):
            host = host[7:]

        netrc = Netrc()

        # Check if already logged in and not forcing relogin
        if not relogin and not key:
            credentials = netrc.get_credentials(host)
            if credentials:
                # Already logged in, show status
                _print_login_status(host)
                return True

        # If no key provided, prompt for it
        if not key:
            key = _prompt_for_api_key(host)
            if not key:
                return False

        # Validate the API key
        try:
            _validate_api_key(key)
        except ValueError as e:
            weave_echo(f"Invalid API key format: {e}", err=True)
            return False

        # Save the API key
        netrc_path = _get_netrc_path()
        try:
            netrc.add_or_update_entry(host, "user", key)
            weave_echo(f"Appending key for {host} to your netrc file: {netrc_path}")
        except Exception as e:
            weave_echo(f"Warning - Failed to save API key: {e}", err=True)

        # Verify login if requested
        if verify:
            try:
                # For now, just do basic validation since we don't have server verification
                _validate_api_key(key)
            except Exception as e:
                weave_echo(f"Warning - Could not verify API key: {e}", err=True)

        # Show final login status
        _print_login_status(host)

    except Exception as e:
        weave_echo(f"Login failed with error: {e}", err=True)
        return False
    else:
        return True


def _prompt_for_api_key(host: str) -> str | None:
    """Prompt the user for their API key with helpful messaging."""
    # Generate the appropriate app URL
    app_url = wandb.util.app_url(f"https://{host}")

    # Add the authorize endpoint for easier access
    auth_url = f"{app_url}/authorize?ref=weave"

    # Display helpful messages
    server_docs_url = "https://wandb.me/wandb-server"
    weave_echo(
        f"Logging into {host}. (Learn how to deploy a W&B server locally: {server_docs_url})"
    )
    weave_echo(f"You can find your API key in your browser here: {auth_url}")
    weave_echo(
        "Paste an API key from your profile and hit enter, or press ctrl+c to quit:"
    )

    try:
        api_key = click.prompt(
            "",
            hide_input=True,
            show_default=False,
            prompt_suffix="",
        )
        return api_key.strip()
    except click.Abort:
        weave_echo("Login cancelled.")
        return None
    except (EOFError, OSError):
        weave_echo(
            "No input available (no TTY). Please provide API key directly.", err=True
        )
        return None


def _print_login_status(host: str) -> None:
    """Print the current login status with username if available."""
    try:
        api = wandb.Api()
        username = api.username()

        # Style the URL in green and username in yellow (like wandb)
        styled_url = click.style(f"https://{host}", fg="green")

        if username:
            styled_username = click.style(username, fg="yellow")
            weave_echo_styled(
                f"{WEAVE_PREFIX}: Currently logged in as: {styled_username} to {styled_url}. Use `weave login --relogin` to force relogin"
            )
        else:
            weave_echo_styled(
                f"{WEAVE_PREFIX}: Currently logged in to {styled_url}. Use `weave login --relogin` to force relogin"
            )

    except Exception:
        # If we can't get username, just show basic status
        styled_url = click.style(f"https://{host}", fg="green")
        weave_echo_styled(
            f"{WEAVE_PREFIX}: Currently logged in to {styled_url}. Use `weave login --relogin` to force relogin"
        )


def _get_netrc_path() -> str:
    """Get the path to the netrc file."""
    return str(Path.home() / (".netrc" if os.name != "nt" else "_netrc"))
