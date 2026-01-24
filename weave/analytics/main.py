"""Main CLI entry point for weave analytics."""

import click

from weave.analytics.commands.annotate import annotate
from weave.analytics.commands.cluster import cluster
from weave.analytics.commands.setup import setup
from weave.analytics.commands.summarize import summarize


@click.group()
@click.version_option()
def analytics() -> None:
    """Analyze traces with LLM-powered clustering.

    Run analytics queries against Weave traces using AI-powered categorization.

    \b
    Commands:
        setup     - Configure API keys and settings
        cluster   - Cluster traces into pattern categories
        annotate  - Add cluster annotations to traces
        summarize - Generate an LLM summary of a trace

    \b
    Examples:
        weave analytics setup
        weave analytics cluster "https://wandb.ai/entity/project/weave/traces?..."
        weave analytics annotate data.json
        weave analytics summarize "https://wandb.ai/entity/project/weave/calls/abc123"
    """
    pass


analytics.add_command(setup)
analytics.add_command(cluster)
analytics.add_command(annotate)
analytics.add_command(summarize)


@click.group()
@click.version_option()
def cli() -> None:
    """Weave CLI - Tools for working with Weave traces."""
    pass


cli.add_command(analytics)


if __name__ == "__main__":
    cli()

