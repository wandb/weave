"""Cluster command for trace pattern analysis."""

import asyncio
import json
import os
import random
import sys
from datetime import datetime

import click
import yaml

from weave.analytics.commands.setup import get_config_path, load_config
from weave.analytics.header import get_header_for_rich
from weave.analytics.url_parser import parse_weave_url
from weave.analytics.weave_client import AnalyticsWeaveClient, WeaveClientConfig


def load_env_from_config() -> None:
    """Load configuration into environment variables."""
    config = load_config()
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = value


def load_existing_clusters(clusters_file: str) -> dict | None:
    """Load existing clusters from YAML file.

    Args:
        clusters_file: Path to the YAML file containing existing clusters

    Returns:
        Dictionary containing the cluster definitions or None if file doesn't exist
    """
    if not clusters_file:
        return None

    try:
        with open(clusters_file, "r") as f:
            data = yaml.safe_load(f)
            return data
    except Exception as e:
        raise ValueError(f"Failed to load clusters file: {e}")


@click.command()
@click.argument("url")
@click.option(
    "--model",
    default=None,
    help="LiteLLM model name (default: from config or gemini/gemini-2.5-flash)",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Maximum number of traces to analyze",
)
@click.option(
    "--max-concurrent",
    default=10,
    type=int,
    help="Maximum concurrent LLM calls",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Pretty print the JSON output (also enables structured console output)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with Weave tracing and verbose output",
)
@click.option(
    "--depth",
    default=0,
    type=int,
    help="Enable deep trace analysis with specified depth (0=disabled, default: 0)",
)
@click.option(
    "--context",
    default="",
    help="User context about the AI system being analyzed",
)
@click.option(
    "--clusters-file",
    type=click.Path(exists=True),
    help="Path to existing clusters YAML file to use as base definitions",
)
@click.option(
    "--sample-size",
    default=None,
    type=int,
    help="Maximum number of traces to randomly sample (default: from config or 500)",
)
@click.option(
    "--no-sampling",
    is_flag=True,
    help="Disable random sampling (fetch all traces up to --limit)",
)
def cluster(
    url: str,
    model: str | None,
    limit: int | None,
    max_concurrent: int,
    pretty: bool,
    output: str | None,
    debug: bool,
    depth: int,
    context: str,
    clusters_file: str | None,
    sample_size: int | None,
    no_sampling: bool,
) -> None:
    """Cluster traces from a Weave URL into pattern categories.

    Analyzes traces from the given Weave URL using AI-powered clustering
    to identify common patterns, failure modes, or behaviors.

    \b
    URL can be either:
    - A trace list URL with filters: https://wandb.ai/entity/project/weave/traces?filter=...
    - An individual call URL: https://wandb.ai/entity/project/weave/calls/abc123

    \b
    Examples:
        # Cluster traces from a filtered URL
        weave analytics cluster "https://wandb.ai/my-team/my-project/weave/traces?..."

    \b
        # Limit to 50 traces with pretty output
        weave analytics cluster "..." --limit 50 --pretty

    \b
        # Save to YAML file
        weave analytics cluster "..." -o clusters.yaml

    \b
        # Use existing cluster definitions and discover new ones
        weave analytics cluster "..." --clusters-file existing_clusters.yaml -o updated_clusters.yaml

    \b
        # Debug mode (traces LLM calls to Weave)
        weave analytics cluster "..." --debug

    \b
        # Deep trace analysis (analyzes execution trees, depth=3)
        weave analytics cluster "..." --depth 3

    \b
        # With user context for better categorization
        weave analytics cluster "..." --context "This is a customer service chatbot"

    \b
        # Sample 200 random traces from a large dataset
        weave analytics cluster "..." --sample-size 200

    \b
        # Disable sampling to analyze all traces (up to --limit)
        weave analytics cluster "..." --no-sampling --limit 1000
    """
    # Import rich here to avoid slow startup for simple --help
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from weave.analytics.clustering import run_clustering_pipeline
    from weave.analytics.spinner import AnalyticsSpinner

    # Load config
    load_env_from_config()

    # Load existing clusters if provided
    existing_clusters_data = None
    if clusters_file:
        try:
            existing_clusters_data = load_existing_clusters(clusters_file)
        except ValueError as e:
            console = Console(stderr=True)
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    # Create console for stderr output
    console = Console(stderr=True)

    # Show header in pretty/debug mode
    if pretty or debug:
        console.print(get_header_for_rich())
        console.print()

    # Get model from config or use default
    config = load_config()
    if model is None:
        model = config.get("LLM_MODEL", "gemini/gemini-2.5-flash")

    # Get sample size from config or use default
    effective_sample_size = sample_size
    if effective_sample_size is None and not no_sampling:
        effective_sample_size = int(config.get("MAX_SAMPLE_SIZE", "500"))

    # Debug mode: limited samples, Weave tracing
    if debug:
        console.print("[bold red]🔍 DEBUG MODE ENABLED[/bold red]")

        if limit is None:
            limit = 5
            console.print(f"[dim]  Limiting to {limit} traces[/dim]")

        # Initialize Weave tracing with suppressed output
        debug_entity = config.get("DEBUG_WEAVE_ENTITY")
        debug_project = config.get("DEBUG_WEAVE_PROJECT", "weave-analytics-debug")

        if debug_entity:
            import io
            import logging

            import weave
            from weave.trace.settings import UserSettings

            # Suppress weave's automatic printouts during init
            weave_logger = logging.getLogger("weave")
            old_level = weave_logger.level
            weave_logger.setLevel(logging.ERROR)

            # Also suppress any direct prints during init (weave logs to stdout)
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            try:
                weave_project = f"{debug_entity}/{debug_project}"
                weave.init(
                    weave_project,
                    settings=UserSettings(print_call_link=False, log_level="ERROR"),
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                weave_logger.setLevel(old_level)

            console.print(f"[dim]  Weave tracing: https://wandb.ai/{weave_project}/weave[/dim]")
        else:
            console.print("[yellow]  Warning: Debug entity not configured. Run 'weave analytics setup' to set it.[/yellow]")

        console.print()

    # Parse URL
    try:
        parsed_url = parse_weave_url(url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Show configuration panel in pretty/debug mode
    if pretty or debug:
        sampling_info = "disabled" if no_sampling else f"{effective_sample_size} traces"
        config_info = f"""[bold]Entity:[/bold] {parsed_url.entity}
[bold]Project:[/bold] {parsed_url.project}
[bold]Model:[/bold] {model}
[bold]Sampling:[/bold] {sampling_info}
[bold]Limit:[/bold] {limit or 'none'}
[bold]Max Concurrent:[/bold] {max_concurrent}
[bold]Deep Analysis:[/bold] {'enabled (depth=' + str(depth) + ')' if depth > 0 else 'disabled'}"""
        if context:
            config_info += f"\n[bold]Context:[/bold] {context[:50]}..."
        console.print(Panel(config_info, title="Configuration", border_style="cyan"))
        console.print()

    # Initialize Weave client
    try:
        client_config = WeaveClientConfig(
            entity=parsed_url.entity,
            project=parsed_url.project,
        )
        client = AnalyticsWeaveClient(client_config)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[dim]Run 'weave analytics setup' to configure your credentials.[/dim]")
        sys.exit(1)

    # Step 1: Fetch traces (with sampling for large datasets)
    total_traces = 0
    sampled = False

    if pretty or debug:
        console.print("[bold cyan]Step 1: Fetching Traces[/bold cyan]")
        spinner = AnalyticsSpinner("Counting traces")
        spinner.start()

    try:
        if parsed_url.url_type == "call" and parsed_url.trace_id:
            # Single trace - no sampling needed
            traces = client.query_by_call_id(parsed_url.trace_id)
            total_traces = len(traces)
            if pretty or debug:
                spinner.stop(f"Found {len(traces)} trace(s)", success=True)
        else:
            # Check if sampling is needed
            if not no_sampling and effective_sample_size is not None:
                # Count total traces first
                total_traces = client.count_traces_with_filters(
                    filters=parsed_url.filters,
                )
                if pretty or debug:
                    spinner.stop(f"Found {total_traces} total traces", success=True)

                # Apply limit if specified
                effective_total = min(total_traces, limit) if limit else total_traces

                if effective_total > effective_sample_size:
                    # Need to sample
                    sampled = True
                    if pretty or debug:
                        pct = (effective_sample_size / effective_total) * 100
                        console.print(f"[dim]  Sampling {effective_sample_size} of {effective_total} traces ({pct:.1f}%)[/dim]")
                        spinner = AnalyticsSpinner("Fetching trace IDs for sampling")
                        spinner.start()

                    # Fetch all trace IDs (minimal data)
                    all_trace_ids = client.query_trace_ids_with_filters(
                        filters=parsed_url.filters,
                    )

                    # Apply limit if specified
                    if limit and len(all_trace_ids) > limit:
                        all_trace_ids = all_trace_ids[:limit]

                    if pretty or debug:
                        spinner.stop(f"Fetched {len(all_trace_ids)} trace IDs", success=True)

                    # Random sample
                    sampled_ids = random.sample(all_trace_ids, min(effective_sample_size, len(all_trace_ids)))

                    if pretty or debug:
                        spinner = AnalyticsSpinner(f"Fetching full data for {len(sampled_ids)} sampled traces")
                        spinner.start()

                    # Fetch full trace data for sampled IDs
                    traces = client.query_traces_by_ids(sampled_ids)

                    if pretty or debug:
                        spinner.stop(f"Sampled {len(traces)} of {effective_total} traces", success=True)
                else:
                    # No sampling needed - fetch all
                    if pretty or debug:
                        spinner = AnalyticsSpinner("Fetching traces")
                        spinner.start()
                    traces = client.query_traces_with_filters(
                        filters=parsed_url.filters,
                        limit=limit,
                    )
                    total_traces = len(traces)
                    if pretty or debug:
                        spinner.stop(f"Fetched {len(traces)} traces", success=True)
            else:
                # No sampling - fetch directly
                if pretty or debug:
                    spinner.stop("Sampling disabled", success=True)
                    spinner = AnalyticsSpinner("Fetching traces")
                    spinner.start()
                traces = client.query_traces_with_filters(
                    filters=parsed_url.filters,
                    limit=limit,
                )
                total_traces = len(traces)
                if pretty or debug:
                    spinner.stop(f"Fetched {len(traces)} traces", success=True)
    except Exception as e:
        if pretty or debug:
            spinner.stop("Failed to fetch traces", success=False)
        console.print(f"[red]Error fetching traces:[/red] {e}")
        if debug:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    if not traces:
        console.print("[yellow]No traces found matching the criteria.[/yellow]")
        sys.exit(1)

    # Show sampling summary
    if sampled and (pretty or debug):
        console.print(f"\n[dim]  ℹ️  Analyzing a random sample. Use --no-sampling to analyze all traces.[/dim]")

    # Step 2: Resolve references
    if pretty or debug:
        console.print("\n[bold cyan]Step 2: Resolving References[/bold cyan]")
        spinner = AnalyticsSpinner("Resolving Weave references")
        spinner.start()

    all_refs = []
    for trace in traces:
        all_refs.extend(client.collect_refs(trace))

    if all_refs:
        try:
            resolved = client.read_refs_batch(list(set(all_refs)))
            ref_map = dict(zip(set(all_refs), resolved))
            traces = [client.replace_refs(t, ref_map) for t in traces]
            if pretty or debug:
                spinner.stop(f"Resolved {len(set(all_refs))} references", success=True)
        except Exception as e:
            if pretty or debug:
                spinner.stop(f"Warning: Could not resolve refs: {e}", success=False)
    elif pretty or debug:
        spinner.stop("No references to resolve", success=True)

    # Step 3: Run clustering pipeline
    if pretty or debug:
        console.print("\n[bold cyan]Step 3: Draft Categorization[/bold cyan]")
        console.print(f"[bright_magenta]  Starting draft categorization for {len(traces)} traces...[/bright_magenta]")

    try:
        result = asyncio.run(
            run_clustering_pipeline(
                traces=traces,
                model=model,
                entity=parsed_url.entity,
                project=parsed_url.project,
                max_concurrent=max_concurrent,
                debug=debug,
                console=console if (pretty or debug) else None,
                user_context=context,
                deep_trace_analysis=depth > 0,
                client=client if depth > 0 else None,
                nesting_depth=depth,
                existing_clusters=existing_clusters_data,
                url=url,
            )
        )
    except Exception as e:
        console.print(f"[red]Error during clustering:[/red] {e}")
        if debug:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    # Output results in YAML format
    from weave.analytics.models import YAMLClustersOutput, YAMLCluster

    # Convert result to YAML format
    yaml_clusters = []
    for cluster_group in result.clusters:
        # Get sample traces (up to 3)
        sample_traces = [trace.trace_url for trace in cluster_group.traces[:3]]
        yaml_clusters.append(YAMLCluster(
            cluster_name=cluster_group.category_name,
            cluster_definition=cluster_group.category_definition,
            sample_traces=sample_traces,
        ))

    yaml_output = YAMLClustersOutput(
        name=existing_clusters_data.get("name", f"{parsed_url.project} Trace Clusters") if existing_clusters_data else f"{parsed_url.project} Trace Clusters",
        description=existing_clusters_data.get("description") if existing_clusters_data else None,
        weave_project=parsed_url.project,
        weave_entity=parsed_url.entity,
        last_clustering=datetime.now().strftime("%Y-%m-%d"),
        trace_list=url,
        clusters=yaml_clusters,
    )

    # Convert to dict and then to YAML
    yaml_dict = yaml_output.model_dump(exclude_none=True)
    result_output = yaml.dump(yaml_dict, default_flow_style=False, sort_keys=False)

    if output:
        with open(output, "w") as f:
            f.write(result_output)
        if pretty or debug:
            console.print(f"\n[green]✓[/green] Results saved to [cyan]{output}[/cyan]")
    else:
        # Print to stdout (console output goes to stderr)
        print(result_output)

    # Final summary panel in pretty/debug mode
    if pretty or debug:
        console.print()

        # Create summary table
        summary_table = Table(show_header=True, header_style="bold cyan", box=None)
        summary_table.add_column("Category", style="bright_magenta")
        summary_table.add_column("Count", justify="right")
        summary_table.add_column("Percentage", justify="right")

        for cluster_group in result.clusters:
            # Color percentage based on value
            pct = cluster_group.percentage
            if pct >= 30:
                pct_style = "bright_magenta"
            elif pct >= 10:
                pct_style = "yellow"
            else:
                pct_style = "white"

            summary_table.add_row(
                cluster_group.category_name.replace("_", " ").title(),
                str(cluster_group.count),
                f"[{pct_style}]{pct:.1f}%[/{pct_style}]",
            )

        console.print(Panel(
            summary_table,
            title=f"[green]✓ Clustering Complete - {len(result.clusters)} clusters found[/green]",
            border_style="green",
        ))

        # Show sample traces from each cluster
        if result.clusters:
            console.print("\n[bold cyan]Sample Traces by Cluster[/bold cyan]")
            for cluster_group in result.clusters:
                console.print(f"\n[bold bright_magenta]{cluster_group.category_name.replace('_', ' ').title()}[/bold bright_magenta] ({cluster_group.count} traces)")
                console.print(f"[dim]{cluster_group.category_definition}[/dim]")
                for trace in cluster_group.traces[:3]:
                    console.print(f"  • [link={trace.trace_url}]{trace.trace_id[:20]}...[/link]")
                    reason_preview = trace.categorization_reason[:80] + "..." if len(trace.categorization_reason) > 80 else trace.categorization_reason
                    console.print(f"    [dim]{reason_preview}[/dim]")
