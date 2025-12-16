"""Annotate command for classifying traces and adding failure analysis annotations."""

import asyncio
import json
import os
import random
import sys
from asyncio import Semaphore
from pathlib import Path
from typing import Any

import click
import yaml

import weave
from weave.analytics.clustering import (
    ProgressTracker,
    extract_human_annotations,
    extract_metadata,
    final_classification,
    get_api_key_for_model,
)
from weave.analytics.commands.setup import load_config
from weave.analytics.header import get_header_for_rich
from weave.analytics.models import YAMLCluster
from weave.analytics.prompts import build_human_annotations_section
from weave.analytics.spinner import AnalyticsSpinner
from weave.analytics.url_parser import build_trace_url, parse_weave_url
from weave.analytics.weave_client import AnalyticsWeaveClient, WeaveClientConfig


def load_env_from_config() -> None:
    """Load configuration into environment variables."""
    config = load_config()
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = value


def load_categories_yaml(yaml_path: Path) -> dict[str, Any]:
    """Load and validate categories from YAML file.

    Args:
        yaml_path: Path to the categories YAML file

    Returns:
        Dictionary with categories config

    Raises:
        ValueError: If the YAML file is invalid or doesn't exist
    """
    if not yaml_path.exists():
        raise ValueError(f"Categories file not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    # Validate required fields
    if "clusters" not in data:
        raise ValueError("Categories YAML must contain 'clusters' field")

    if not isinstance(data["clusters"], list):
        raise ValueError("'clusters' must be a list")

    # Validate each cluster
    for i, cluster in enumerate(data["clusters"]):
        if "cluster_name" not in cluster:
            raise ValueError(f"Cluster {i} missing 'cluster_name'")
        if "cluster_definition" not in cluster:
            raise ValueError(f"Cluster {i} missing 'cluster_definition'")

    return data


@weave.op
async def classify_trace_into_category(
    trace_id: str,
    trace_input: dict | str,
    trace_output: dict | str,
    trace_metadata: dict | str,
    user_context: str,
    annotation_section: str,
    categories_str: str,
    model: str,
    semaphore: Semaphore,
) -> dict[str, Any]:
    """Classify a single trace into one of the predefined categories.

    Args:
        trace_id: The trace ID
        trace_input: Input data for the trace
        trace_output: Output data for the trace
        trace_metadata: Metadata for the trace
        user_context: User-provided context
        annotation_section: Human annotation summary
        categories_str: String representation of available categories
        model: LLM model to use
        semaphore: Concurrency limiter

    Returns:
        Dictionary with trace_id and assigned category
    """
    # Use the existing final_classification function
    result = await final_classification(
        trace_id=trace_id,
        trace_input=trace_input,
        trace_output=trace_output,
        trace_metadata=trace_metadata,
        user_context=user_context,
        annotation_section=annotation_section,
        execution_trace=None,
        categories_str=categories_str,
        model=model,
        semaphore=semaphore,
    )

    # Get the primary category (first one if multiple)
    pattern_categories = result.get("pattern_categories", [])
    primary_category = pattern_categories[0] if pattern_categories else "uncategorized"

    return {
        "trace_id": trace_id,
        "category": primary_category,
        "all_categories": pattern_categories,
        "reason": result.get("categorization_reason", ""),
        "thinking": result.get("thinking", ""),
    }


async def run_classification_for_annotation(
    traces: list[dict[str, Any]],
    categories: list[dict[str, str]],
    model: str,
    user_context: str,
    annotation_summary: dict[str, Any],
    max_concurrent: int = 10,
    progress_tracker: ProgressTracker | None = None,
) -> list[dict[str, Any]]:
    """Run classification on all traces for annotation.

    Args:
        traces: List of trace dictionaries
        categories: List of category definitions
        model: LLM model to use
        user_context: User-provided context
        annotation_summary: Human annotation summary
        max_concurrent: Maximum concurrent LLM calls
        progress_tracker: Optional progress tracker for feedback

    Returns:
        List of classification results
    """
    semaphore = Semaphore(max_concurrent)
    annotation_section = build_human_annotations_section(annotation_summary)

    # Build categories string for LLM prompt
    categories_str = ""
    for i, cat in enumerate(categories):
        categories_str += f"\n### Category {i + 1}: {cat['name']}\n"
        categories_str += f"**Definition:** {cat['definition']}\n"

    async def classify_with_progress(trace: dict[str, Any]) -> dict[str, Any]:
        """Wrapper to track progress."""
        result = await classify_trace_into_category(
            trace_id=trace.get("id", ""),
            trace_input=trace.get("inputs", {}),
            trace_output=trace.get("output", {}),
            trace_metadata=extract_metadata(trace),
            user_context=user_context,
            annotation_section=annotation_section,
            categories_str=categories_str,
            model=model,
            semaphore=semaphore,
        )
        if progress_tracker:
            progress_tracker.update(result.get("trace_id"))
        return result

    tasks = [classify_with_progress(trace) for trace in traces]

    return await asyncio.gather(*tasks)


@click.command()
@click.argument("url")
@click.option(
    "--categories",
    "-c",
    default="categories.yaml",
    type=click.Path(path_type=Path),
    help="Path to categories YAML file (default: categories.yaml in current directory)",
)
@click.option(
    "--model",
    default=None,
    help="LiteLLM model name (default: from config or gemini/gemini-2.5-pro)",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Maximum number of traces to annotate",
)
@click.option(
    "--max-concurrent",
    default=10,
    type=int,
    help="Maximum concurrent LLM calls",
)
@click.option(
    "--annotation-name",
    default="failure_analysis",
    help="Name for the annotation field (default: failure_analysis)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be annotated without making changes",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Enable structured console output",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path for results JSON (default: stdout)",
)
@click.option(
    "--context",
    default="",
    help="User context about the AI system being analyzed",
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
def annotate(
    url: str,
    categories: Path,
    model: str | None,
    limit: int | None,
    max_concurrent: int,
    annotation_name: str,
    dry_run: bool,
    pretty: bool,
    output: str | None,
    context: str,
    sample_size: int | None,
    no_sampling: bool,
) -> None:
    """Classify traces and add failure analysis annotations.

    Fetches traces from the given URL, classifies each into one of the
    predefined categories from the YAML file, and adds annotations to Weave.

    \b
    URL can be either:
    - A trace list URL with filters: https://wandb.ai/entity/project/weave/traces?filter=...
    - An individual call URL: https://wandb.ai/entity/project/weave/calls/abc123

    \b
    The categories YAML file should have the structure output by 'weave analytics cluster':
    name: Project Trace Clusters
    weave_project: my-project
    weave_entity: my-entity
    last_clustering: '2025-12-12'
    trace_list: <trace-url>
    clusters:
      - cluster_name: authentication_issues
        cluster_definition: >
          Traces related to users being unable to log in...
        sample_traces:
          - <trace-url>

    \b
    Examples:
        # Annotate traces using local categories.yaml
        weave analytics annotate "https://wandb.ai/my-team/my-project/weave/traces?..."

    \b
        # Use specific categories file
        weave analytics annotate "..." --categories my-categories.yaml

    \b
        # Dry run to preview classifications
        weave analytics annotate "..." --dry-run

    \b
        # Limit to 20 traces
        weave analytics annotate "..." --limit 20 --pretty

    \b
        # Sample 200 random traces from a large dataset
        weave analytics annotate "..." --sample-size 200

    \b
        # Disable sampling to annotate all traces
        weave analytics annotate "..." --no-sampling --limit 1000
    """
    # Import rich here to avoid slow startup
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    # Load config
    load_env_from_config()

    # Create console
    console = Console(stderr=True)

    if pretty or dry_run:
        console.print(get_header_for_rich())
        console.print()

    # Load categories
    try:
        categories_config = load_categories_yaml(categories)
    except ValueError as e:
        console.print(f"[red]Error loading categories:[/red] {e}")
        sys.exit(1)

    # Get model from config or use default
    config = load_config()
    if model is None:
        model = config.get("LLM_MODEL", "gemini/gemini-2.5-pro")

    # Get sample size from config or use default
    effective_sample_size = sample_size
    if effective_sample_size is None and not no_sampling:
        effective_sample_size = int(config.get("MAX_SAMPLE_SIZE", "500"))

    # Parse URL
    try:
        parsed_url = parse_weave_url(url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Build category list
    category_list = []
    category_definitions = {}
    for cluster in categories_config["clusters"]:
        name = cluster["cluster_name"]
        definition = cluster["cluster_definition"]
        category_list.append({"name": name, "definition": definition})
        category_definitions[name] = definition

    # Show configuration
    if pretty or dry_run:
        sampling_info = "disabled" if no_sampling else f"{effective_sample_size} traces"
        config_info = f"""[bold]Entity:[/bold] {parsed_url.entity}
[bold]Project:[/bold] {parsed_url.project}
[bold]Model:[/bold] {model}
[bold]Categories:[/bold] {len(category_list)}
[bold]Annotation Name:[/bold] {annotation_name}
[bold]Sampling:[/bold] {sampling_info}
[bold]Limit:[/bold] {limit or 'none'}
[bold]Dry Run:[/bold] {dry_run}"""
        console.print(Panel(config_info, title="Configuration", border_style="cyan"))
        console.print()

        # Show categories
        categories_table = Table(show_header=True, header_style="bold cyan", box=None)
        categories_table.add_column("Category", style="bright_magenta")
        categories_table.add_column("Definition", style="white")

        for cat in category_list:
            definition_short = cat["definition"][:60] + "..." if len(cat["definition"]) > 60 else cat["definition"]
            categories_table.add_row(cat["name"], definition_short)

        console.print(Panel(
            categories_table,
            title=f"Categories from {categories}",
            border_style="cyan",
        ))
        console.print()

    # Initialize analytics client for fetching traces
    try:
        client_config = WeaveClientConfig(
            entity=parsed_url.entity,
            project=parsed_url.project,
        )
        analytics_client = AnalyticsWeaveClient(client_config)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[dim]Run 'weave analytics setup' to configure your credentials.[/dim]")
        sys.exit(1)

    # Step 1: Fetch traces (with sampling for large datasets)
    total_traces = 0
    sampled = False

    if pretty or dry_run:
        console.print("[bold cyan]Step 1: Fetching Traces[/bold cyan]")
        spinner = AnalyticsSpinner("Counting traces")
        spinner.start()

    try:
        if parsed_url.url_type == "call" and parsed_url.trace_id:
            # Single trace - no sampling needed
            traces = analytics_client.query_by_call_id(parsed_url.trace_id)
            total_traces = len(traces)
            if pretty or dry_run:
                spinner.stop(f"Found {len(traces)} trace(s)", success=True)
        else:
            # Check if sampling is needed
            if not no_sampling and effective_sample_size is not None:
                # Count total traces first
                total_traces = analytics_client.count_traces_with_filters(
                    filters=parsed_url.filters,
                )
                if pretty or dry_run:
                    spinner.stop(f"Found {total_traces} total traces", success=True)

                # Apply limit if specified
                effective_total = min(total_traces, limit) if limit else total_traces

                if effective_total > effective_sample_size:
                    # Need to sample
                    sampled = True
                    if pretty or dry_run:
                        pct = (effective_sample_size / effective_total) * 100
                        console.print(f"[dim]  Sampling {effective_sample_size} of {effective_total} traces ({pct:.1f}%)[/dim]")
                        spinner = AnalyticsSpinner("Fetching trace IDs for sampling")
                        spinner.start()

                    # Fetch all trace IDs (minimal data)
                    all_trace_ids = analytics_client.query_trace_ids_with_filters(
                        filters=parsed_url.filters,
                    )

                    # Apply limit if specified
                    if limit and len(all_trace_ids) > limit:
                        all_trace_ids = all_trace_ids[:limit]

                    if pretty or dry_run:
                        spinner.stop(f"Fetched {len(all_trace_ids)} trace IDs", success=True)

                    # Random sample
                    sampled_ids = random.sample(all_trace_ids, min(effective_sample_size, len(all_trace_ids)))

                    if pretty or dry_run:
                        spinner = AnalyticsSpinner(f"Fetching full data for {len(sampled_ids)} sampled traces")
                        spinner.start()

                    # Fetch full trace data for sampled IDs
                    traces = analytics_client.query_traces_by_ids(sampled_ids)

                    if pretty or dry_run:
                        spinner.stop(f"Sampled {len(traces)} of {effective_total} traces", success=True)
                else:
                    # No sampling needed - fetch all
                    if pretty or dry_run:
                        spinner = AnalyticsSpinner("Fetching traces")
                        spinner.start()
                    traces = analytics_client.query_traces_with_filters(
                        filters=parsed_url.filters,
                        limit=limit,
                    )
                    total_traces = len(traces)
                    if pretty or dry_run:
                        spinner.stop(f"Fetched {len(traces)} traces", success=True)
            else:
                # No sampling - fetch directly
                if pretty or dry_run:
                    spinner.stop("Sampling disabled", success=True)
                    spinner = AnalyticsSpinner("Fetching traces")
                    spinner.start()
                traces = analytics_client.query_traces_with_filters(
                    filters=parsed_url.filters,
                    limit=limit,
                )
                total_traces = len(traces)
                if pretty or dry_run:
                    spinner.stop(f"Fetched {len(traces)} traces", success=True)
    except Exception as e:
        if pretty or dry_run:
            spinner.stop("Failed to fetch traces", success=False)
        console.print(f"[red]Error fetching traces:[/red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    if not traces:
        console.print("[yellow]No traces found matching the criteria.[/yellow]")
        sys.exit(1)

    # Show sampling summary
    if sampled and (pretty or dry_run):
        console.print(f"\n[dim]  ℹ️  Annotating a random sample. Use --no-sampling to annotate all traces.[/dim]")

    # Step 2: Resolve references
    if pretty or dry_run:
        console.print("\n[bold cyan]Step 2: Resolving References[/bold cyan]")
        spinner = AnalyticsSpinner("Resolving Weave references")
        spinner.start()

    all_refs = []
    for trace in traces:
        all_refs.extend(analytics_client.collect_refs(trace))

    if all_refs:
        try:
            resolved = analytics_client.read_refs_batch(list(set(all_refs)))
            ref_map = dict(zip(set(all_refs), resolved))
            traces = [analytics_client.replace_refs(t, ref_map) for t in traces]
            if pretty or dry_run:
                spinner.stop(f"Resolved {len(set(all_refs))} references", success=True)
        except Exception as e:
            if pretty or dry_run:
                spinner.stop(f"Warning: Could not resolve refs: {e}", success=False)
    elif pretty or dry_run:
        spinner.stop("No references to resolve", success=True)

    # Fetch feedback for annotations
    # Note: Feedback is included in traces via include_feedback=True in the query
    traces_with_feedback = sum(1 for t in traces if t.get("feedback"))
    if pretty or dry_run:
        console.print(f"\n[dim]Found feedback for {traces_with_feedback} traces[/dim]")

    # Extract human annotations
    annotation_examples = []
    for trace in traces:
        annotations = extract_human_annotations(trace)
        if annotations:
            annotation_examples.append({"trace_id": trace.get("id"), "annotations": annotations})

    annotation_summary = {
        "has_annotations": len(annotation_examples) > 0,
        "examples": annotation_examples[:5],
    }

    # Build user context
    if not context:
        context = (
            f"This is an AI system in the '{parsed_url.project}' project. "
            f"We are classifying traces into {len(category_list)} predefined failure categories."
        )

    # Step 4: Classify traces using LLM
    classification_progress = None
    if pretty or dry_run:
        console.print("\n[bold cyan]Step 4: Classifying Traces[/bold cyan]")
        console.print(f"  [dim]Classifying into {len(category_list)} categories...[/dim]")
        classification_progress = ProgressTracker(
            total=len(traces),
            description="Classifying",
            console=console,
            show_ids=True,
        )
        classification_progress.start()

    try:
        classifications = asyncio.run(
            run_classification_for_annotation(
                traces=traces,
                categories=category_list,
                model=model,
                user_context=context,
                annotation_summary=annotation_summary,
                max_concurrent=max_concurrent,
                progress_tracker=classification_progress,
            )
        )
    except Exception as e:
        if classification_progress:
            classification_progress.finish("Classification failed")
        console.print(f"[red]Error during classification:[/red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    if classification_progress:
        classification_progress.finish(f"Classified {len(classifications)} traces")

    # Build histogram of categories
    category_counts: dict[str, int] = {}
    classification_map: dict[str, dict[str, Any]] = {}

    for classification in classifications:
        trace_id = classification["trace_id"]
        category = classification["category"]
        classification_map[trace_id] = classification

        if category not in category_counts:
            category_counts[category] = 0
        category_counts[category] += 1

    # Sort by count descending
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    # Display histogram
    if pretty or dry_run:
        console.print("\n[bold cyan]Classification Distribution (Histogram)[/bold cyan]")

        histogram_table = Table(show_header=True, header_style="bold cyan", box=None)
        histogram_table.add_column("Category", style="bright_magenta")
        histogram_table.add_column("Count", justify="right")
        histogram_table.add_column("Percentage", justify="right")
        histogram_table.add_column("Bar", style="green")

        max_count = max(category_counts.values()) if category_counts else 1

        for category, count in sorted_categories:
            pct = (count / len(traces)) * 100
            bar_length = int((count / max_count) * 30)
            bar = "█" * bar_length

            if pct >= 30:
                pct_style = "bright_magenta"
            elif pct >= 10:
                pct_style = "yellow"
            else:
                pct_style = "white"

            histogram_table.add_row(
                category,
                str(count),
                f"[{pct_style}]{pct:.1f}%[/{pct_style}]",
                bar,
            )

        console.print(histogram_table)
        console.print()

    # Dry run - show sample annotations
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print()

        # Show sample classifications
        console.print("[bold]Sample Classifications:[/bold]")
        for i, classification in enumerate(classifications[:5]):
            trace_id = classification["trace_id"]
            category = classification["category"]
            reason = classification["reason"]

            console.print(f"\n  [bold]Trace {i + 1}:[/bold] {trace_id[:16]}...")
            console.print(f"    [bright_magenta]Category:[/bright_magenta] {category}")
            console.print(f"    [dim]Reason:[/dim] {reason[:100]}..." if len(reason) > 100 else f"    [dim]Reason:[/dim] {reason}")

        console.print("\n[green]✓[/green] Dry run complete. Remove --dry-run to apply annotations.")
        return

    # Step 5: Apply annotations to Weave
    if pretty:
        console.print("\n[bold cyan]Step 5: Applying Annotations to Weave[/bold cyan]")

    # Initialize Weave client for annotations
    try:
        project_path = f"{parsed_url.entity}/{parsed_url.project}"
        weave_client = weave.init(project_path)
    except Exception as e:
        console.print(f"[red]Error initializing Weave client:[/red] {e}")
        sys.exit(1)

    # Create AnnotationSpec for the failure analysis field
    spinner = None
    if pretty:
        spinner = AnalyticsSpinner("Creating annotation spec")
        spinner.start()

    try:
        from weave import AnnotationSpec

        # Get all unique categories
        all_categories = sorted(set(category_counts.keys()))

        # Build description with category definitions for reference
        category_descriptions = "\n".join([
            f"• {cat['name']}: {cat['definition'][:100]}..."
            if len(cat['definition']) > 100
            else f"• {cat['name']}: {cat['definition']}"
            for cat in category_list
        ])

        # Create annotation spec with name, description, and enum schema
        # Following the pattern from Weave docs:
        # https://docs.wandb.ai/weave/guides/tracking/feedback#create-a-human-annotation-scorer-using-the-api
        failure_spec = AnnotationSpec(
            name="Failure Analysis",
            description=(
                f"AI-powered failure categorization generated by `weave analytics annotate`. "
                f"Categories were discovered using `weave analytics cluster` on {categories_config.get('last_clustering', 'unknown date')}. "
                f"Source categories file: {categories}. "
                f"\n\nAvailable categories:\n{category_descriptions}"
            ),
            field_schema={
                "type": "string",
                "enum": all_categories,
            },
        )

        # Publish the annotation spec
        failure_ref = weave.publish(failure_spec, name=annotation_name)

        if spinner:
            spinner.stop(f"Created annotation spec: {annotation_name}", success=True)
    except Exception as e:
        if spinner:
            spinner.stop(f"Failed: {e}", success=False)
        console.print(f"[red]Error creating annotation spec:[/red] {e}")
        sys.exit(1)

    # Apply annotations to each trace
    if pretty:
        spinner = AnalyticsSpinner(f"Annotating {len(traces)} traces")
        spinner.start()

    from weave.trace_server.interface.feedback_types import ANNOTATION_FEEDBACK_TYPE_PREFIX
    from weave.trace_server.trace_server_interface import FeedbackCreateReq

    success_count = 0
    error_count = 0
    annotation_ref_uri = str(failure_ref.uri())
    feedback_type = f"{ANNOTATION_FEEDBACK_TYPE_PREFIX}.{annotation_name}"

    for trace in traces:
        trace_id = trace.get("id", "")
        classification = classification_map.get(trace_id, {})
        category = classification.get("category", "uncategorized")

        try:
            # Build weave ref for the trace
            weave_ref = f"weave:///{parsed_url.entity}/{parsed_url.project}/call/{trace_id}"

            # Create feedback payload with the category value
            payload = {"value": category}

            # Create feedback as annotation
            feedback_req = FeedbackCreateReq(
                project_id=project_path,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                annotation_ref=annotation_ref_uri,
            )

            weave_client.server.feedback_create(feedback_req)
            success_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 3:
                console.print(f"[yellow]Warning: Failed to annotate {trace_id}: {e}[/yellow]")

    if pretty and spinner:
        spinner.stop(
            f"Annotated {success_count} traces ({error_count} errors)",
            success=error_count == 0,
        )

    # Build output results
    output_results = []
    for trace in traces:
        trace_id = trace.get("id", "")
        classification = classification_map.get(trace_id, {})

        output_results.append({
            "trace_id": trace_id,
            "trace_url": build_trace_url(parsed_url.entity, parsed_url.project, trace_id),
            "category": classification.get("category", "uncategorized"),
            "all_categories": classification.get("all_categories", []),
            "reason": classification.get("reason", ""),
        })

    final_output = {
        "total_traces": len(traces),
        "entity": parsed_url.entity,
        "project": parsed_url.project,
        "annotation_name": annotation_name,
        "annotations_created": success_count,
        "annotations_failed": error_count,
        "category_distribution": [
            {
                "category": cat,
                "count": count,
                "percentage": (count / len(traces)) * 100,
            }
            for cat, count in sorted_categories
        ],
        "results": output_results,
    }

    # Output results
    result_json = json.dumps(final_output, indent=2 if pretty else None)

    if output:
        with open(output, "w") as f:
            f.write(result_json)
        if pretty:
            console.print(f"\n[green]✓[/green] Results saved to [cyan]{output}[/cyan]")
    else:
        # Print JSON to stdout
        print(result_json)

    # Final summary
    if pretty:
        console.print()
        console.print(Panel(
            f"""[green]✓ Annotation Complete[/green]

[bold]Traces Annotated:[/bold] {success_count}/{len(traces)}
[bold]Annotation Field:[/bold] {annotation_name}
[bold]Categories Found:[/bold] {len(category_counts)}

[bold]Top Categories:[/bold]""" + "".join([
                f"\n  • {cat}: {count} ({(count/len(traces))*100:.1f}%)"
                for cat, count in sorted_categories[:5]
            ]),
            title="Summary",
            border_style="green",
        ))

        console.print(
            f"\n[dim]View annotated traces at: https://wandb.ai/{parsed_url.entity}/{parsed_url.project}/weave/traces[/dim]"
        )
