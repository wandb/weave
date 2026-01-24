"""Classify command for trace categorization using predefined categories."""

import asyncio
import json
import os
import sys
from asyncio import Semaphore
from pathlib import Path
from typing import Any

import click
import yaml

import weave
from weave.analytics.category_schemas import CategoriesConfig
from weave.analytics.category_scorer import create_category_scorer
from weave.analytics.classification import classify_trace_multi_label
from weave.analytics.clustering import extract_human_annotations, extract_metadata
from weave.analytics.commands.setup import get_config_path, load_config
from weave.analytics.header import get_header_for_rich
from weave.analytics.prompts import build_human_annotations_section
from weave.analytics.url_parser import build_trace_url, parse_weave_url
from weave.analytics.weave_client import AnalyticsWeaveClient, WeaveClientConfig


def load_env_from_config() -> None:
    """Load configuration into environment variables."""
    config = load_config()
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = value


def load_categories_yaml(yaml_path: Path) -> CategoriesConfig:
    """Load and validate categories from YAML file.

    Args:
        yaml_path: Path to the categories YAML file

    Returns:
        CategoriesConfig object

    Raises:
        ValueError: If the YAML file is invalid
    """
    if not yaml_path.exists():
        raise ValueError(f"Categories file not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    try:
        return CategoriesConfig(**data)
    except Exception as e:
        raise ValueError(f"Invalid categories YAML format: {e}") from e


@weave.op
async def run_classification_pipeline(
    traces: list[dict[str, Any]],
    categories: list[dict[str, str]],
    category_names: dict[str, str],  # name -> definition mapping
    weave_client: Any,  # WeaveClient for getting Call objects
    model: str,
    user_context: str,
    annotation_summary: dict[str, Any],
    deep_trace_analysis: bool = False,
    max_concurrent: int = 10,
) -> list[dict[str, Any]]:
    """Run multi-label classification on all traces and apply scorers to Weave calls.

    Args:
        traces: List of trace dictionaries to classify
        categories: List of category definitions (name and definition)
        category_names: Dict mapping category names to definitions
        weave_client: Weave client for getting Call objects
        model: LLM model to use for classification
        user_context: User context about the system
        annotation_summary: Summary of human annotations
        deep_trace_analysis: Whether to include execution traces
        max_concurrent: Maximum concurrent classifications

    Returns:
        List of classification results with scorer outputs
    """
    semaphore = Semaphore(max_concurrent)

    annotation_section = build_human_annotations_section(annotation_summary)

    # Step 1: Run LLM-based multi-label classification
    classification_tasks = [
        classify_trace_multi_label(
            trace_id=trace.get("id", ""),
            trace_input=trace.get("inputs", {}),
            trace_output=trace.get("output", {}),
            trace_metadata=extract_metadata(trace),
            categories=categories,
            model=model,
            user_context=user_context,
            annotation_section=annotation_section,
            execution_trace=trace.get("execution_trace") if deep_trace_analysis else None,
            semaphore=semaphore,
        )
        for trace in traces
    ]

    classification_results = await asyncio.gather(*classification_tasks)

    # Step 2: Get Call objects and apply scorers to attach scores to Weave
    final_results = []
    for i, classification in enumerate(classification_results):
        trace = traces[i]
        trace_id = classification["trace_id"]
        memberships = classification["memberships"]

        # Get the Call object from Weave
        try:
            call = weave_client.get_call(trace_id)
        except Exception as e:
            # If we can't get the call object, just record the results without attaching to Weave
            scorer_outputs = {}
            for category_name in category_names.keys():
                membership = memberships.get(category_name, {})
                scorer_outputs[category_name] = {
                    "scorer_result": membership.get("belongs", False),
                    "confidence": membership.get("confidence", 0.0),
                    "reason": membership.get("reason", ""),
                    "error": f"Could not attach score to trace: {e}",
                }
            final_results.append({
                "trace_id": trace_id,
                "thinking": classification["thinking"],
                "categories": scorer_outputs,
            })
            continue

        # Apply each scorer to the Call object (this attaches scores to Weave)
        # Create scorer classes with classification results baked in
        scorer_tasks = []
        scorer_outputs = {}

        for category_name, category_definition in category_names.items():
            membership = memberships.get(category_name, {})

            # Create a scorer class with the classification result baked in
            scorer_class = create_category_scorer(
                category_name=category_name,
                category_definition=category_definition,
                classification_result=membership.get("belongs", False),
                confidence=membership.get("confidence", 0.0),
                reason=membership.get("reason", ""),
            )

            scorer_instance = scorer_class()

            # Apply the scorer to the call - this will attach the score to Weave
            scorer_task = call.apply_scorer(scorer_instance)
            scorer_tasks.append((category_name, scorer_task, membership))

        # Wait for all scorers to be applied
        for category_name, scorer_task, membership in scorer_tasks:
            try:
                await scorer_task
                scorer_outputs[category_name] = {
                    "scorer_result": membership.get("belongs", False),
                    "confidence": membership.get("confidence", 0.0),
                    "reason": membership.get("reason", ""),
                    "attached_to_weave": True,
                }
            except Exception as e:
                scorer_outputs[category_name] = {
                    "scorer_result": membership.get("belongs", False),
                    "confidence": membership.get("confidence", 0.0),
                    "reason": membership.get("reason", ""),
                    "attached_to_weave": False,
                    "error": str(e),
                }

        final_results.append({
            "trace_id": trace_id,
            "thinking": classification["thinking"],
            "categories": scorer_outputs,
        })

    return final_results


@click.command()
@click.argument("url")
@click.option(
    "--categories",
    "-c",
    default="categories.yaml",
    type=click.Path(exists=True, path_type=Path),
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
    "--threshold",
    default=0.5,
    type=float,
    help="Confidence threshold for category membership (default: 0.5)",
)
@click.option(
    "--context",
    default="",
    help="User context about the AI system being analyzed",
)
def classify(
    url: str,
    categories: Path,
    model: str | None,
    limit: int | None,
    max_concurrent: int,
    pretty: bool,
    output: str | None,
    debug: bool,
    threshold: float,
    context: str,
) -> None:
    """Classify traces using predefined categories from a YAML file.

    Analyzes traces from the given Weave URL and classifies them into
    predefined categories using AI-powered scorers.

    \b
    URL can be either:
    - A trace list URL with filters: https://wandb.ai/entity/project/weave/traces?filter=...
    - An individual call URL: https://wandb.ai/entity/project/weave/calls/abc123

    \b
    The categories YAML file should have the following structure:
    name: Example Support Trace Clusters
    description: (Optional)
    weave_project: my-project
    weave_entity: my-entity
    last_clustering: 2025-12-12
    trace_list: <trace-url>
    clusters:
      - cluster_name: Authentication Issues
        cluster_definition: >
          Traces related to users being unable to log in...
        sample_traces:
          - <trace-url>

    \b
    Examples:
        # Classify traces using local categories.yaml
        weave analytics classify "https://wandb.ai/my-team/my-project/weave/traces?..."

    \b
        # Use specific categories file
        weave analytics classify "..." --categories my-categories.yaml

    \b
        # Limit to 50 traces with pretty output
        weave analytics classify "..." --limit 50 --pretty

    \b
        # Save to file
        weave analytics classify "..." -o results.json

    \b
        # Debug mode (traces LLM calls to Weave)
        weave analytics classify "..." --debug

    \b
        # Custom confidence threshold
        weave analytics classify "..." --threshold 0.7
    """
    # Import rich here to avoid slow startup for simple --help
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from weave.analytics.spinner import AnalyticsSpinner

    # Load config
    load_env_from_config()

    # Create console for stderr output
    console = Console(stderr=True)

    # Show header in pretty/debug mode
    if pretty or debug:
        console.print(get_header_for_rich())
        console.print()

    # Load categories from YAML
    try:
        categories_config = load_categories_yaml(categories)
    except ValueError as e:
        console.print(f"[red]Error loading categories:[/red] {e}")
        sys.exit(1)

    # Get model from config or use default
    config = load_config()
    if model is None:
        model = config.get("LLM_MODEL", "gemini/gemini-2.5-pro")

    # Debug mode: faster model, limited samples, Weave tracing
    if debug:
        console.print("[bold red]🔍 DEBUG MODE ENABLED[/bold red]")
        debug_model = "gemini/gemini-2.5-flash"
        console.print(f"[dim]  Switching to faster model: {debug_model}[/dim]")
        model = debug_model

        if limit is None:
            limit = 5
            console.print(f"[dim]  Limiting to {limit} traces[/dim]")

        # Initialize Weave tracing with suppressed output
        debug_entity = config.get("DEBUG_WEAVE_ENTITY")
        debug_project = config.get("DEBUG_WEAVE_PROJECT", "weave-analytics-debug")

        if debug_entity:
            import io
            import logging

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
        config_info = f"""[bold]Entity:[/bold] {parsed_url.entity}
[bold]Project:[/bold] {parsed_url.project}
[bold]Model:[/bold] {model}
[bold]Categories:[/bold] {len(categories_config.clusters)}
[bold]Limit:[/bold] {limit or 'all'}
[bold]Max Concurrent:[/bold] {max_concurrent}
[bold]Threshold:[/bold] {threshold}"""
        console.print(Panel(config_info, title="Configuration", border_style="cyan"))
        console.print()

        # Show categories
        categories_table = Table(show_header=True, header_style="bold cyan", box=None)
        categories_table.add_column("Category", style="bright_magenta")
        categories_table.add_column("Definition", style="white")

        for cluster in categories_config.clusters:
            definition_short = cluster.cluster_definition[:60] + "..." if len(cluster.cluster_definition) > 60 else cluster.cluster_definition
            categories_table.add_row(cluster.cluster_name, definition_short)

        console.print(Panel(
            categories_table,
            title=f"Categories from {categories_config.name}",
            border_style="cyan",
        ))
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

    # Step 1: Fetch traces
    if pretty or debug:
        console.print("[bold cyan]Step 1: Fetching Traces[/bold cyan]")
        spinner = AnalyticsSpinner("Fetching traces from Weave")
        spinner.start()

    try:
        if parsed_url.url_type == "call" and parsed_url.trace_id:
            traces = client.query_by_call_id(parsed_url.trace_id)
        else:
            traces = client.query_traces_with_filters(
                filters=parsed_url.filters,
                limit=limit,
            )
    except Exception as e:
        if pretty or debug:
            spinner.stop("Failed to fetch traces", success=False)
        console.print(f"[red]Error fetching traces:[/red] {e}")
        sys.exit(1)

    if pretty or debug:
        spinner.stop(f"Found {len(traces)} traces", success=True)

    if not traces:
        console.print("[yellow]No traces found matching the criteria.[/yellow]")
        sys.exit(1)

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

    # Step 3: Prepare categories (scorer classes will be created after classification)
    if pretty or debug:
        console.print("\n[bold cyan]Step 3: Preparing Categories[/bold cyan]")
        console.print(f"[bright_magenta]  Preparing {len(categories_config.clusters)} categories for classification...[/bright_magenta]")

    category_names = {}
    category_definitions = []

    for cluster in categories_config.clusters:
        # Create category name without whitespace
        category_name = cluster.cluster_name.replace(" ", "")
        category_names[category_name] = cluster.cluster_definition

        # Store category definition for classification
        category_definitions.append({
            "name": category_name,
            "definition": cluster.cluster_definition,
        })

    if pretty or debug:
        console.print(f"[dim]  Prepared {len(category_names)} categories[/dim]")
        for name in category_names.keys():
            console.print(f"[dim]    - {name}[/dim]")

    # Fetch feedback and prepare annotations
    if pretty or debug:
        console.print("\n[bold cyan]Step 4: Checking Feedback & Annotations[/bold cyan]")

    # Note: Feedback is included in traces via include_feedback=True in the query
    traces_with_feedback = sum(1 for t in traces if t.get("feedback"))
    if pretty or debug:
        console.print(f"[dim]Found feedback for {traces_with_feedback} traces[/dim]")

    # Extract annotations
    annotation_examples = []
    for trace in traces:
        annotations = extract_human_annotations(trace)
        if annotations:
            annotation_examples.append({"trace_id": trace.get("id"), "annotations": annotations})

    annotation_summary = {
        "has_annotations": len(annotation_examples) > 0,
        "examples": annotation_examples[:5],
    }

    if pretty or debug and annotation_examples:
        console.print(f"[dim]  Found annotations/feedback in {len(annotation_examples)} traces[/dim]")

    # Build user context if not provided
    if not context:
        context = (
            f"This is an AI system in the '{parsed_url.project}' project. "
            f"We are classifying traces into {len(category_definitions)} predefined categories."
        )

    # Step 5: Initialize Weave client for attaching scores
    if pretty or debug:
        console.print("\n[bold cyan]Step 5: Initializing Weave Client[/bold cyan]")

    # Initialize Weave client to attach scores to traces
    weave_client = weave.init(f"{parsed_url.entity}/{parsed_url.project}")

    if pretty or debug:
        console.print(f"[dim]  Connected to Weave project: {parsed_url.entity}/{parsed_url.project}[/dim]")

    # Step 6: Run classification and attach scores
    if pretty or debug:
        console.print("\n[bold cyan]Step 6: Multi-Label Classification & Score Attachment[/bold cyan]")
        console.print(f"[bright_magenta]  Classifying {len(traces)} traces using LLM...[/bright_magenta]")
        console.print(f"[bright_magenta]  Attaching {len(category_names)} scorers to each trace...[/bright_magenta]")
        spinner = AnalyticsSpinner("Running classification")
        spinner.start()

    try:
        results = asyncio.run(
            run_classification_pipeline(
                traces=traces,
                categories=category_definitions,
                category_names=category_names,
                weave_client=weave_client,
                model=model,
                user_context=context,
                annotation_summary=annotation_summary,
                deep_trace_analysis=False,  # Can be extended later
                max_concurrent=max_concurrent,
            )
        )
    except Exception as e:
        if pretty or debug:
            spinner.stop("Classification failed", success=False)
        console.print(f"[red]Error during classification:[/red] {e}")
        if debug:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    if pretty or debug:
        # Count how many scores were successfully attached
        scores_attached = sum(
            1
            for result in results
            for cat_data in result.get("categories", {}).values()
            if cat_data.get("attached_to_weave", False)
        )
        total_scores = len(results) * len(category_names)
        spinner.stop(
            f"Classified {len(results)} traces, attached {scores_attached}/{total_scores} scores to Weave",
            success=True
        )

    # Process results
    output_results = []
    category_counts: dict[str, int] = {name: 0 for name in category_names.keys()}
    scores_attached_count = 0
    scores_failed_count = 0

    for result in results:
        trace_id = result["trace_id"]
        categories_result = result["categories"]

        trace_result = {
            "trace_id": trace_id,
            "trace_url": build_trace_url(parsed_url.entity, parsed_url.project, trace_id),
            "thinking": result.get("thinking", ""),
            "categories": {},
        }

        for category_name, category_data in categories_result.items():
            scorer_result = category_data["scorer_result"]
            confidence = category_data["confidence"]
            reason = category_data["reason"]
            attached_to_weave = category_data.get("attached_to_weave", False)

            # Track attachment success
            if attached_to_weave:
                scores_attached_count += 1
            elif "error" in category_data:
                scores_failed_count += 1

            # Apply threshold
            final_result = scorer_result and confidence >= threshold

            if final_result:
                category_counts[category_name] += 1

            trace_result["categories"][category_name] = {
                "belongs": final_result,
                "confidence": confidence,
                "reason": reason,
                "attached_to_weave": attached_to_weave,
            }

            # Include error if present
            if "error" in category_data:
                trace_result["categories"][category_name]["error"] = category_data["error"]

        output_results.append(trace_result)

    # Build final output
    final_output = {
        "total_traces": len(traces),
        "entity": parsed_url.entity,
        "project": parsed_url.project,
        "threshold": threshold,
        "categories_file": str(categories),
        "scores_attached_to_weave": scores_attached_count,
        "scores_failed_to_attach": scores_failed_count,
        "weave_project_url": f"https://wandb.ai/{parsed_url.entity}/{parsed_url.project}/weave",
        "category_summary": [
            {
                "category_name": category_name,
                "count": count,
                "percentage": (count / len(traces)) * 100 if traces else 0,
            }
            for category_name, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "results": output_results,
    }

    # Output results
    result_json = json.dumps(final_output, indent=2 if pretty else None)

    if output:
        with open(output, "w") as f:
            f.write(result_json)
        if pretty or debug:
            console.print(f"\n[green]✓[/green] Results saved to [cyan]{output}[/cyan]")
    else:
        # Print JSON to stdout (console output goes to stderr)
        print(result_json)

    # Final summary panel in pretty/debug mode
    if pretty or debug:
        console.print()

        # Create summary table
        summary_table = Table(show_header=True, header_style="bold cyan", box=None)
        summary_table.add_column("Category", style="bright_magenta")
        summary_table.add_column("Count", justify="right")
        summary_table.add_column("Percentage", justify="right")

        for cat_summary in final_output["category_summary"]:
            # Color percentage based on value
            pct = cat_summary["percentage"]
            if pct >= 30:
                pct_style = "bright_magenta"
            elif pct >= 10:
                pct_style = "yellow"
            else:
                pct_style = "white"

            summary_table.add_row(
                cat_summary["category_name"],
                str(cat_summary["count"]),
                f"[{pct_style}]{pct:.1f}%[/{pct_style}]",
            )

        console.print(Panel(
            summary_table,
            title=f"[green]✓ Classification Complete - {len(category_names)} categories[/green]",
            border_style="green",
        ))

        # Show score attachment info
        console.print()
        if scores_attached_count > 0:
            console.print(f"[green]✓[/green] {scores_attached_count} scores attached to Weave traces")
            console.print(f"[dim]  View scores at: {final_output['weave_project_url']}[/dim]")
        if scores_failed_count > 0:
            console.print(f"[yellow]⚠[/yellow] {scores_failed_count} scores failed to attach")

