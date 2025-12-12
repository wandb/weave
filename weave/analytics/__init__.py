"""Weave Analytics CLI - Analyze traces with LLM-powered clustering.

This module provides a CLI for analyzing Weave traces using LLM-powered
clustering. The main commands are:

- `weave analytics setup`: Configure API keys
- `weave analytics cluster <url>`: Cluster traces from a Weave URL

Example usage:

    $ weave analytics setup
    $ weave analytics cluster "https://wandb.ai/entity/project/weave/traces?..."

For programmatic usage:

    >>> from weave.analytics.clustering import run_clustering_pipeline
    >>> from weave.analytics.weave_client import AnalyticsWeaveClient
"""

from weave.analytics.main import analytics, cli

__all__ = ["analytics", "cli"]
