"""Annotate command for adding cluster results to traces."""

import json
import sys

import click

from weave.analytics.commands.setup import load_config
from weave.analytics.models import ClusterOutput


def load_env_from_config() -> None:
    """Load configuration into environment variables."""
    import os

    config = load_config()
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = value


@click.command()
@click.argument("cluster_output_file", type=click.Path(exists=True))
@click.option(
    "--annotation-name",
    default="cluster_category",
    help="Name for the annotation field (default: cluster_category)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be annotated without making changes",
)
@click.option(
    "--include-reason",
    is_flag=True,
    help="Include categorization reason in annotation payload",
)
def annotate(
    cluster_output_file: str,
    annotation_name: str,
    dry_run: bool,
    include_reason: bool,
) -> None:
    """Add structured annotations from cluster output to traces.

    Reads cluster output (from cluster command) and adds annotations
    to each trace with its assigned category and metadata.

    \b
    Examples:
        # Annotate traces with cluster categories
        weave analytics annotate data.json

    \b
        # Dry run to preview annotations
        weave analytics annotate data.json --dry-run

    \b
        # Include categorization reason in annotations
        weave analytics annotate data.json --include-reason

    \b
        # Custom annotation name
        weave analytics annotate data.json --annotation-name "failure_pattern"
    """
    # Import rich here to avoid slow startup
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    import weave
    from weave.analytics.header import get_header_for_rich
    from weave.analytics.spinner import AnalyticsSpinner

    # Load config
    load_env_from_config()

    # Create console
    console = Console(stderr=True)
    console.print(get_header_for_rich())
    console.print()

    # Load cluster output
    try:
        with open(cluster_output_file) as f:
            cluster_data = json.load(f)
        cluster_output = ClusterOutput(**cluster_data)
    except Exception as e:
        console.print(f"[red]Error loading cluster output:[/red] {e}")
        sys.exit(1)

    # Show configuration
    config_info = f"""[bold]Entity:[/bold] {cluster_output.entity}
[bold]Project:[/bold] {cluster_output.project}
[bold]Total Traces:[/bold] {cluster_output.total_traces}
[bold]Annotation Name:[/bold] {annotation_name}
[bold]Include Reason:[/bold] {include_reason}
[bold]Dry Run:[/bold] {dry_run}"""
    console.print(Panel(config_info, title="Configuration", border_style="cyan"))
    console.print()

    # Show cluster summary
    console.print("[bold cyan]Cluster Summary[/bold cyan]")
    summary_table = Table(show_header=True, header_style="bold cyan", box=None)
    summary_table.add_column("Category", style="bright_magenta")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Percentage", justify="right")

    for cluster_group in cluster_output.clusters:
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

    console.print(summary_table)
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print()

        # Show sample annotations for each cluster
        for cluster_group in cluster_output.clusters[:3]:
            console.print(f"[bold]{cluster_group.category_name}[/bold]")
            console.print(f"[dim]{cluster_group.category_definition}[/dim]")

            for trace in cluster_group.traces[:2]:
                console.print(f"  • Trace: {trace.trace_id}")
                console.print(f"    URL: {trace.trace_url}")

                annotation_payload = {
                    "category": cluster_group.category_name,
                    "category_definition": cluster_group.category_definition,
                }
                if include_reason:
                    annotation_payload["categorization_reason"] = trace.categorization_reason

                console.print(f"    Annotation: {json.dumps(annotation_payload, indent=2)}")
            console.print()

        console.print("[green]✓[/green] Dry run complete. Use without --dry-run to apply annotations.")
        return

    # Initialize Weave client
    try:
        project_path = f"{cluster_output.entity}/{cluster_output.project}"
        client = weave.init(project_path)
    except Exception as e:
        console.print(f"[red]Error initializing Weave client:[/red] {e}")
        console.print("[dim]Run 'weave analytics setup' to configure your credentials.[/dim]")
        sys.exit(1)

    # Create AnnotationSpec objects for human annotations
    console.print("[bold cyan]Creating Annotation Specs[/bold cyan]")
    spinner = AnalyticsSpinner("Creating annotation specs")
    spinner.start()

    try:
        from weave import AnnotationSpec

        # Get all unique categories from the cluster output
        all_categories = sorted(set(
            cluster_group.category_name
            for cluster_group in cluster_output.clusters
        ))

        # Create annotation spec for category (enum of all categories)
        category_spec = AnnotationSpec(
            field_schema={
                "type": "string",
                "enum": all_categories,
                "description": "The cluster category this trace belongs to",
            }
        )

        # Create annotation spec for definition (string)
        definition_spec = AnnotationSpec(
            field_schema={
                "type": "string",
                "description": "Definition of the cluster category",
            }
        )

        # Publish annotation specs
        category_ref = weave.publish(category_spec, name=f"{annotation_name}_category")
        definition_ref = weave.publish(definition_spec, name=f"{annotation_name}_definition")

        annotation_refs = {
            "category": category_ref,
            "definition": definition_ref,
        }

        if include_reason:
            # Create annotation spec for reason (string)
            reason_spec = AnnotationSpec(
                field_schema={
                    "type": "string",
                    "description": "Explanation for why this trace was categorized this way",
                }
            )
            reason_ref = weave.publish(reason_spec, name=f"{annotation_name}_reason")
            annotation_refs["reason"] = reason_ref

        spinner.stop(
            f"Created {len(annotation_refs)} annotation spec(s): {', '.join(annotation_refs.keys())}",
            success=True,
        )
    except Exception as e:
        spinner.stop(f"Failed to create annotation specs: {e}", success=False)
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Add annotations
    console.print("\n[bold cyan]Adding Annotations[/bold cyan]")
    spinner = AnalyticsSpinner(f"Annotating {cluster_output.total_traces} traces")
    spinner.start()

    success_count = 0
    error_count = 0

    from weave.trace_server.interface.feedback_types import ANNOTATION_FEEDBACK_TYPE_PREFIX
    from weave.trace_server.trace_server_interface import FeedbackCreateReq

    # Prepare annotation data for each field
    annotation_data = {
        "category": {},
        "definition": {},
    }
    if include_reason:
        annotation_data["reason"] = {}

    for cluster_group in cluster_output.clusters:
        for trace in cluster_group.traces:
            annotation_data["category"][trace.trace_id] = cluster_group.category_name
            annotation_data["definition"][trace.trace_id] = cluster_group.category_definition
            if include_reason:
                annotation_data["reason"][trace.trace_id] = trace.categorization_reason

    # Create feedback for each field/annotation spec separately
    for field_name, annotation_ref in annotation_refs.items():
        annotation_ref_uri = str(annotation_ref.uri())
        feedback_type = f"{ANNOTATION_FEEDBACK_TYPE_PREFIX}.{annotation_name}_{field_name}"

        for trace_id, value in annotation_data[field_name].items():
            try:
                # Payload for annotation feedback - must use {"value": ...} format
                payload = {"value": value}

                # Build weave ref for the trace
                weave_ref = (
                    f"weave:///{cluster_output.entity}/{cluster_output.project}/call/{trace_id}"
                )

                # Create feedback as annotation (shows up in Annotations/Feedback)
                feedback_req = FeedbackCreateReq(
                    project_id=project_path,
                    weave_ref=weave_ref,
                    feedback_type=feedback_type,
                    payload=payload,
                    annotation_ref=annotation_ref_uri,
                )

                client.server.feedback_create(feedback_req)
                success_count += 1

            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    console.print(
                        f"[yellow]Warning: Failed to annotate {trace_id} for {field_name}: {e}[/yellow]"
                    )

    total_feedbacks = success_count
    total_traces = cluster_output.total_traces
    fields_per_trace = len(annotation_refs)

    spinner.stop(
        f"Created {total_feedbacks} annotation entries ({error_count} errors)",
        success=error_count == 0,
    )

    # Final summary
    console.print()
    if error_count == 0:
        console.print(
            Panel(
                f"[green]✓ Successfully added {fields_per_trace} annotation field(s) to {total_traces} traces[/green]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[yellow]⚠ Created {success_count} annotation entries with {error_count} errors[/yellow]",
                border_style="yellow",
            )
        )
        console.print(
            "[dim]Some traces may already have annotations or may no longer exist.[/dim]"
        )

    console.print(
        f"\n[dim]View annotated traces at: https://wandb.ai/{cluster_output.entity}/{cluster_output.project}/weave/traces[/dim]"
    )
