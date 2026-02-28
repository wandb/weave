"""Summarize command for LLM-powered trace analysis."""

import json
import sys

import click
import litellm

from weave.analytics.commands.setup import load_config
from weave.analytics.header import get_compact_header_for_rich
from weave.analytics.url_parser import build_trace_url, parse_weave_url


def load_env_from_config() -> None:
    """Load configuration into environment variables."""
    import os

    config = load_config()
    for key, value in config.items():
        if key not in os.environ:
            os.environ[key] = value


def get_llm_kwargs(model: str) -> dict:
    """Get the kwargs for litellm completion based on the model provider.

    For W&B inference models, this configures the custom API base URL.

    Args:
        model: The model name (e.g., "gemini/gemini-2.5-flash", "wandb/meta-llama/Llama-4-Scout-17B-16E-Instruct")

    Returns:
        Dictionary of kwargs for litellm.completion
    """
    import os
    from typing import Any

    provider = model.split("/")[0].lower() if "/" in model else "openai"

    provider_env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "wandb": "WANDB_API_KEY",
        "wandb_ai": "WANDB_API_KEY",
    }

    env_var = provider_env_map.get(provider, "OPENAI_API_KEY")
    api_key = os.getenv(env_var)

    if not api_key:
        raise ValueError(f"{env_var} not set. Run 'weave analytics setup' first.")

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
    }

    # W&B inference uses OpenAI-compatible API
    if provider in ("wandb", "wandb_ai"):
        # Convert wandb/model-name to openai/model-name for litellm
        model_name = "/".join(model.split("/")[1:])  # Remove wandb/ prefix
        kwargs["model"] = f"openai/{model_name}"
        kwargs["api_base"] = "https://api.inference.wandb.ai/v1"

    return kwargs


@click.command("summarize")
@click.argument("url")
@click.option(
    "--model",
    default=None,
    help="LiteLLM model name (default: from config)",
)
@click.option(
    "--depth",
    default=5,
    type=int,
    help="Maximum depth to traverse nested traces",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Pretty print with Rich formatting",
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
    help="Enable Weave tracing for debugging (logs to configured debug project)",
)
def summarize(
    url: str,
    model: str | None,
    depth: int,
    pretty: bool,
    output: str | None,
    debug: bool,
) -> None:
    """Generate an LLM-powered summary of a trace.

    Analyzes a trace including its execution tree, latency, token usage,
    cost, and feedback to provide actionable insights.

    URL should be an individual call URL:
    https://wandb.ai/entity/project/weave/calls/abc123

    \b
    Examples:
        # Summarize a trace
        weave analytics summarize "https://wandb.ai/my-team/my-project/weave/calls/abc123"

    \b
        # Use a specific model
        weave analytics summarize "..." --model openai/gpt-4o

    \b
        # Save summary to file
        weave analytics summarize "..." -o summary.md
    """
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    from weave.analytics.clustering import (
        calculate_duration,
        extract_cost,
        extract_token_usage,
        format_trace_as_tree,
        get_op_short_name,
        get_trace_status,
    )
    from weave.analytics.prompts import TRACE_SUMMARY_SYSTEM_PROMPT, TRACE_SUMMARY_USER_PROMPT
    from weave.analytics.spinner import AnalyticsSpinner
    from weave.analytics.weave_client import AnalyticsWeaveClient, WeaveClientConfig

    # Load config
    load_env_from_config()
    config = load_config()

    # Initialize Weave tracing if debug mode enabled
    if debug:
        import weave

        debug_entity = config.get("DEBUG_ENTITY")
        debug_project = config.get("DEBUG_PROJECT", "weave-analytics-debug")
        if debug_entity:
            project_name = f"{debug_entity}/{debug_project}"
        else:
            project_name = debug_project
        weave.init(project_name)

    if model is None:
        model = config.get("LLM_MODEL", "gemini/gemini-2.5-flash")

    console = Console(stderr=True)

    if pretty:
        console.print(get_compact_header_for_rich())
        console.print()

    # Parse URL
    try:
        parsed_url = parse_weave_url(url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if parsed_url.url_type != "call" or not parsed_url.trace_id:
        console.print("[red]Error:[/red] Please provide a single call URL (not a trace list URL)")
        sys.exit(1)

    trace_id = parsed_url.trace_id

    if pretty:
        console.print(f"[bold cyan]Analyzing trace:[/bold cyan] {trace_id[:20]}...")

    # Initialize Weave client
    try:
        client_config = WeaveClientConfig(
            entity=parsed_url.entity,
            project=parsed_url.project,
        )
        client = AnalyticsWeaveClient(client_config)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Fetch the trace and descendants
    if pretty:
        spinner = AnalyticsSpinner("Fetching trace data")
        spinner.start()

    try:
        traces = client.query_by_call_id(trace_id)
        if not traces:
            if pretty:
                spinner.stop("Trace not found", success=False)
            console.print(f"[red]Error:[/red] Trace not found: {trace_id}")
            sys.exit(1)
        root_trace = traces[0]

        descendants = client.query_descendants_recursive(
            parent_id=trace_id,
            max_depth=depth,
        )
        all_traces = descendants.get("traces", [])
        if not any(t["id"] == trace_id for t in all_traces):
            all_traces.append(root_trace)

        if pretty:
            spinner.stop(f"Found {len(all_traces)} traces", success=True)

    except Exception as e:
        if pretty:
            spinner.stop("Failed to fetch trace", success=False)
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Format as tree
    tree = format_trace_as_tree(
        root_trace=root_trace,
        all_traces=all_traces,
        max_depth=depth,
        include_inputs=True,
        include_outputs=True,
    )

    # Extract metadata
    op_name = get_op_short_name(root_trace.get("op_name", ""))
    duration_str, _ = calculate_duration(root_trace)
    status = get_trace_status(root_trace)
    token_usage = extract_token_usage(root_trace)
    cost = extract_cost(root_trace)
    feedback = root_trace.get("feedback")

    # Build info sections
    token_info = f"- **Token Usage**: {json.dumps(token_usage)}" if token_usage else ""
    cost_info = f"- **Cost**: {json.dumps(cost)}" if cost else ""
    feedback_info = f"- **Feedback**: {json.dumps(feedback)}" if feedback else ""

    # Generate LLM summary
    if pretty:
        spinner = AnalyticsSpinner("Generating summary with LLM")
        spinner.start()

    try:
        llm_kwargs = get_llm_kwargs(model)

        prompt = TRACE_SUMMARY_USER_PROMPT.format(
            trace_id=trace_id,
            op_name=op_name,
            duration=duration_str or "N/A",
            status=status,
            token_info=token_info,
            cost_info=cost_info,
            feedback_info=feedback_info,
            execution_trace=tree[:15000],  # Limit tree size
        )

        response = litellm.completion(
            messages=[
                {"role": "system", "content": TRACE_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            **llm_kwargs,
        )

        summary = response.choices[0].message.content

        if pretty:
            spinner.stop("Summary generated", success=True)

    except Exception as e:
        if pretty:
            spinner.stop("Failed to generate summary", success=False)
        console.print(f"[red]Error generating summary:[/red] {e}")
        sys.exit(1)

    # Output
    if output:
        with open(output, "w") as f:
            f.write(f"# Trace Summary: {trace_id}\n\n")
            f.write(f"**URL**: {build_trace_url(parsed_url.entity, parsed_url.project, trace_id)}\n\n")
            f.write(summary)
        if pretty:
            console.print(f"\n[green]✓[/green] Saved to [cyan]{output}[/cyan]")
    else:
        if pretty:
            # Show metadata panel
            meta_info = f"""[bold]Trace ID:[/bold] {trace_id}
[bold]Operation:[/bold] {op_name}
[bold]Duration:[/bold] {duration_str or 'N/A'}
[bold]Status:[/bold] {'[green]success[/green]' if status == 'success' else f'[red]{status}[/red]'}
[bold]Traces:[/bold] {len(all_traces)}"""

            console.print(Panel(meta_info, title="Trace Info", border_style="cyan"))
            console.print()

            # Show summary as markdown
            console.print(Panel(Markdown(summary), title="LLM Summary", border_style="bright_magenta"))
        else:
            print(summary)

