"""Main Weave CLI implementation."""

from __future__ import annotations

import sys

import click

from weave.cli.login import weave_login


@click.group()
def cli() -> None:
    """Weave CLI - A toolkit for building composable interactive data driven applications."""


@cli.command()  # pyright: ignore[reportFunctionMemberAccess]
@click.argument("key", required=False)
@click.option("--cloud", is_flag=True, help="Login to the cloud instead of local")
@click.option("--host", "--base-url", help="Login to a specific instance of W&B")
@click.option("--relogin", is_flag=True, help="Force relogin if already logged in.")
@click.option("--verify/--no-verify", default=True, help="Verify login credentials")
def login(
    key: str | None = None,
    cloud: bool = False,
    host: str | None = None,
    relogin: bool = False,
    verify: bool = True,
) -> None:
    """Login to Weights & Biases."""
    # Handle cloud option - if cloud is True, use default W&B cloud host
    if cloud and not host:
        host = "https://api.wandb.ai"

    success = weave_login(
        key=key,
        host=host,
        relogin=relogin,
        verify=verify,
    )

    if not success:
        # Use the same styling as the rest of the weave application
        weave_prefix = click.style("weave", fg="cyan", bold=True)
        click.echo(f"{weave_prefix}: Login failed!", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the weave CLI."""
    cli()


if __name__ == "__main__":
    main()
