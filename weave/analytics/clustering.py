"""Clustering pipeline for trace analysis - based on FAILS pipeline."""

import asyncio
import json
import os
import sys
import threading
from asyncio import Semaphore
from datetime import datetime
from typing import Any, Callable

import litellm

import weave


# ============================================================================
# Progress tracking for async operations
# ============================================================================


class ProgressTracker:
    """Thread-safe progress tracker for async operations with console output."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        console: Any = None,
        show_ids: bool = True,
    ) -> None:
        """Initialize the progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the operation
            console: Rich console for output (optional)
            show_ids: Whether to show trace IDs in progress
        """
        self.total = total
        self.description = description
        self.console = console
        self.show_ids = show_ids
        self.completed = 0
        self.current_id: str | None = None
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """Start the progress display."""
        if self.console:
            self._started = True
            self._print_progress()

    def update(self, trace_id: str | None = None) -> None:
        """Update progress after completing an item.

        Args:
            trace_id: Optional trace ID that was just completed
        """
        with self._lock:
            self.completed += 1
            self.current_id = trace_id

        if self._started and self.console:
            self._print_progress()

    def _print_progress(self) -> None:
        """Print the current progress to console."""
        pct = (self.completed / self.total * 100) if self.total > 0 else 0

        # Build progress bar
        bar_width = 20
        filled = int(bar_width * self.completed / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        # Build status line
        if self.show_ids and self.current_id and self.completed < self.total:
            id_preview = self.current_id[:8] if len(self.current_id) > 8 else self.current_id
            status = f"  {self.description} [{bar}] {self.completed}/{self.total} ({pct:.0f}%) - {id_preview}..."
        else:
            status = f"  {self.description} [{bar}] {self.completed}/{self.total} ({pct:.0f}%)"

        # Clear line and print
        sys.stderr.write(f"\r{' ' * 80}\r{status}")
        sys.stderr.flush()

    def finish(self, message: str | None = None) -> None:
        """Finish progress tracking and print final message.

        Args:
            message: Optional completion message
        """
        if self._started and self.console:
            # Clear the progress line
            sys.stderr.write(f"\r{' ' * 80}\r")
            sys.stderr.flush()

            if message:
                sys.stderr.write(f"  \033[92m✓\033[0m {message}\n")
                sys.stderr.flush()


def with_progress(
    tracker: ProgressTracker | None,
) -> Callable:
    """Decorator factory to track progress for async tasks.

    Args:
        tracker: ProgressTracker instance

    Returns:
        Decorator that wraps async functions to report progress
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            if tracker:
                # Try to extract trace_id from result or kwargs
                trace_id = None
                if isinstance(result, dict):
                    trace_id = result.get("trace_id")
                elif "trace_id" in kwargs:
                    trace_id = kwargs["trace_id"]
                tracker.update(trace_id)
            return result
        return wrapper
    return decorator

from weave.analytics.models import (
    Category,
    ClusterGroup,
    ClusteringCategories,
    ClusterOutput,
    ClusterResult,
    FinalClassification,
    FirstPassCategorization,
)
from weave.analytics.prompts import (
    CLUSTERING_PROMPT,
    CLUSTERING_SYSTEM_PROMPT,
    FINAL_CLASSIFICATION_PROMPT,
    FINAL_CLASSIFICATION_SYSTEM_PROMPT,
    FIRST_PASS_PROMPT,
    FIRST_PASS_SYSTEM_PROMPT,
    MAX_N_PATTERN_CATEGORIES,
    TRACE_COMPACTION_SYSTEM_PROMPT,
    TRACE_COMPACTION_USER_PROMPT,
    build_execution_trace_section,
    build_existing_clusters_section,
    build_human_annotations_section,
)
from weave.analytics.spinner import AnalyticsSpinner
from weave.analytics.url_parser import build_trace_url


# ============================================================================
# Deep trace utilities (formerly in deep_trace.py)
# ============================================================================


def estimate_token_count(text: str) -> int:
    """Quick heuristic for token estimation (~4 chars per token)."""
    return len(text) // 4


def get_op_short_name(op_name: str) -> str:
    """Extract a clean operation name from the full Weave op_name.

    Args:
        op_name: Full Weave op_name (e.g., "weave:///entity/project/op/MyAgent.call:abc123")

    Returns:
        Short name (e.g., "MyAgent.call")
    """
    if not op_name:
        return "Unknown"

    if "/op/" in op_name:
        name = op_name.split("/op/")[-1]
        if ":" in name:
            name = name.split(":")[0]
        return name

    return op_name


def calculate_duration(trace: dict[str, Any]) -> tuple[str, float | None]:
    """Calculate and format the duration of a trace.

    Args:
        trace: Trace dictionary with started_at and ended_at fields

    Returns:
        Tuple of (formatted duration string, duration in ms)
    """
    started = trace.get("started_at")
    ended = trace.get("ended_at")

    if not started or not ended:
        return "", None

    try:
        if isinstance(started, str):
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        else:
            start_dt = started

        if isinstance(ended, str):
            end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        else:
            end_dt = ended

        duration_ms = (end_dt - start_dt).total_seconds() * 1000

        if duration_ms >= 1000:
            return f"{duration_ms / 1000:.2f}s", duration_ms
        else:
            return f"{duration_ms:.0f}ms", duration_ms
    except Exception:
        return "", None


def _clean_value_for_tree(
    value: Any,
    seen_tools: set | None = None,
    seen_system_prompt: list | None = None,
) -> Any:
    """Clean a value before formatting for the trace tree."""
    if seen_tools is None:
        seen_tools = set()
    if seen_system_prompt is None:
        seen_system_prompt = []

    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith("weave:///"):
            parts = value.split("/")
            if len(parts) >= 5:
                name_part = parts[-1].split(":")[0]
                return f"[{name_part}]"
        return value

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            if k in ("_type", "_class_name", "_bases"):
                continue
            if k == "assistant_message" and "tool_calls" in value:
                continue
            cleaned[k] = _clean_value_for_tree(v, seen_tools, seen_system_prompt)
        return cleaned

    if isinstance(value, list):
        if value and isinstance(value[0], dict) and value[0].get("type") == "function":
            tool_count = len(value)
            tool_sig = f"tools_{tool_count}"
            if tool_sig in seen_tools:
                return f"[{tool_count} tools - same as above]"
            seen_tools.add(tool_sig)
            return [{"tool": t.get("function", {}).get("name", "unknown")} for t in value]

        if value and isinstance(value[0], dict) and value[0].get("role"):
            cleaned_messages = []
            for msg in value:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "system":
                    if seen_system_prompt:
                        cleaned_messages.append(
                            {"role": "system", "content": "[system prompt - same as root]"}
                        )
                        continue
                    seen_system_prompt.append(True)

                if role == "assistant" and msg.get("tool_calls"):
                    tool_calls_info = []
                    for tc in msg.get("tool_calls", []):
                        func = tc.get("function", {})
                        tool_calls_info.append(
                            {
                                "name": func.get("name", "?"),
                                "args": func.get("arguments", ""),
                            }
                        )
                    cleaned_messages.append(
                        {"role": "assistant", "tool_calls": tool_calls_info}
                    )
                    continue

                if role == "tool":
                    cleaned_messages.append(
                        {
                            "role": "tool",
                            "name": msg.get("name", ""),
                            "content": content,
                        }
                    )
                    continue

                cleaned_messages.append(
                    {
                        "role": role,
                        "content": content[:2000] + "..." if len(content) > 2000 else content,
                    }
                )

            return cleaned_messages

        return [_clean_value_for_tree(item, seen_tools, seen_system_prompt) for item in value]

    return value


def _format_value_for_tree(
    value: Any,
    indent: str = "",
    clean: bool = True,
    seen_tools: set | None = None,
    seen_system_prompt: list | None = None,
) -> str:
    """Format a value for display in the trace tree."""
    if clean:
        value = _clean_value_for_tree(value, seen_tools, seen_system_prompt)

    if value is None:
        return "null"

    if isinstance(value, str):
        return f'"{value}"'

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        if not value:
            return "{}"
        try:
            return json.dumps(value, indent=2, default=str)
        except Exception:
            return str(value)

    if isinstance(value, list):
        if not value:
            return "[]"
        try:
            return json.dumps(value, indent=2, default=str)
        except Exception:
            return str(value)

    return str(value)


def format_trace_as_tree(
    root_trace: dict[str, Any],
    all_traces: list[dict[str, Any]],
    max_depth: int | None = None,
    include_inputs: bool = True,
    include_outputs: bool = True,
) -> str:
    """Format a list of traces as an ASCII tree structure.

    Args:
        root_trace: The root trace to start from
        all_traces: All traces (including root and descendants)
        max_depth: Maximum depth to display (None for unlimited)
        include_inputs: Whether to include input details
        include_outputs: Whether to include output details

    Returns:
        ASCII tree representation of the trace hierarchy
    """
    children_map: dict[str, list[dict[str, Any]]] = {}
    trace_by_id: dict[str, dict[str, Any]] = {}

    for trace in all_traces:
        trace_id = trace.get("id")
        parent_id = trace.get("parent_id")

        if trace_id:
            trace_by_id[trace_id] = trace

        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(trace)

    for parent_id in children_map:
        children_map[parent_id].sort(key=lambda t: t.get("started_at", ""))

    lines: list[str] = []
    seen_tools: set = set()
    seen_system_prompt: list = []

    def add_trace_to_tree(
        trace: dict[str, Any],
        prefix: str = "",
        is_last: bool = True,
        depth: int = 0,
    ) -> None:
        if max_depth is not None and depth > max_depth:
            return

        trace_id = trace.get("id", "")
        op_name = get_op_short_name(trace.get("op_name", ""))
        duration_str, _ = calculate_duration(trace)

        connector = "└── " if is_last else "├── "
        duration_part = f" ({duration_str})" if duration_str else ""
        lines.append(f"{prefix}{connector}{op_name}{duration_part}")

        child_prefix = prefix + ("    " if is_last else "│   ")

        if include_inputs and trace.get("inputs"):
            inputs = trace.get("inputs", {})
            if inputs:
                formatted_inputs = _format_value_for_tree(
                    inputs, child_prefix, clean=True,
                    seen_tools=seen_tools, seen_system_prompt=seen_system_prompt,
                )
                if "\n" in formatted_inputs:
                    lines.append(f"{child_prefix}├── inputs:")
                    for input_line in formatted_inputs.split("\n"):
                        lines.append(f"{child_prefix}│   {input_line}")
                else:
                    lines.append(f"{child_prefix}├── inputs: {formatted_inputs}")

        if include_outputs and trace.get("output"):
            output = trace.get("output")
            if output:
                formatted_output = _format_value_for_tree(
                    output, child_prefix, clean=True,
                    seen_tools=seen_tools, seen_system_prompt=seen_system_prompt,
                )
                if "\n" in formatted_output:
                    lines.append(f"{child_prefix}├── output:")
                    for output_line in formatted_output.split("\n"):
                        lines.append(f"{child_prefix}│   {output_line}")
                else:
                    lines.append(f"{child_prefix}├── output: {formatted_output}")

        if exc := trace.get("exception"):
            lines.append(f"{child_prefix}├── [ERROR] {str(exc)[:200]}")

        children = children_map.get(trace_id, [])
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            add_trace_to_tree(child, child_prefix, is_last_child, depth + 1)

    root_op = get_op_short_name(root_trace.get("op_name", ""))
    root_duration_str, _ = calculate_duration(root_trace)
    duration_part = f" ({root_duration_str})" if root_duration_str else ""
    lines.append(f"{root_op}{duration_part}")

    if include_inputs and root_trace.get("inputs"):
        inputs = root_trace.get("inputs", {})
        if inputs:
            formatted_inputs = _format_value_for_tree(
                inputs, "", clean=True,
                seen_tools=seen_tools, seen_system_prompt=seen_system_prompt,
            )
            if "\n" in formatted_inputs:
                lines.append("├── inputs:")
                for input_line in formatted_inputs.split("\n"):
                    lines.append(f"│   {input_line}")
            else:
                lines.append(f"├── inputs: {formatted_inputs}")

    if include_outputs and root_trace.get("output"):
        output = root_trace.get("output")
        if output:
            formatted_output = _format_value_for_tree(
                output, "", clean=True,
                seen_tools=seen_tools, seen_system_prompt=seen_system_prompt,
            )
            if "\n" in formatted_output:
                lines.append("├── output:")
                for output_line in formatted_output.split("\n"):
                    lines.append(f"│   {output_line}")
            else:
                lines.append(f"├── output: {formatted_output}")

    if exc := root_trace.get("exception"):
        lines.append(f"├── [ERROR] {str(exc)[:200]}")

    root_id = root_trace.get("id", "")
    children = children_map.get(root_id, [])
    for i, child in enumerate(children):
        is_last_child = i == len(children) - 1
        add_trace_to_tree(child, "", is_last_child, 1)

    return "\n".join(lines)


def compact_execution_trace(
    trace_tree: str,
    model: str,
    api_key: str,
    max_tokens: int = 10000,
) -> str:
    """Compact an execution trace using an LLM if it exceeds the token threshold.

    Args:
        trace_tree: The formatted trace tree string
        model: LLM model to use for compaction
        api_key: API key for the LLM provider
        max_tokens: Token threshold - if exceeded, compaction is triggered

    Returns:
        Original trace if under threshold, or compacted version
    """
    estimated_tokens = estimate_token_count(trace_tree)

    if estimated_tokens <= max_tokens:
        return trace_tree

    target_tokens = int(max_tokens * 0.7)

    try:
        llm_kwargs = get_llm_kwargs(model)
        response = litellm.completion(
            messages=[
                {"role": "system", "content": TRACE_COMPACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TRACE_COMPACTION_USER_PROMPT.format(
                        target_tokens=target_tokens, trace_tree=trace_tree
                    ),
                },
            ],
            temperature=0.0,
            **llm_kwargs,
        )

        compacted = response.choices[0].message.content
        return compacted if compacted else trace_tree

    except Exception:
        max_chars = max_tokens * 4
        if len(trace_tree) > max_chars:
            return trace_tree[:max_chars] + "\n... [truncated]"
        return trace_tree


def extract_token_usage(trace: dict[str, Any]) -> dict | None:
    """Extract token usage from trace summary."""
    summary = trace.get("summary", {})
    weave_summary = summary.get("weave", {})

    if "token_usage" in weave_summary:
        return weave_summary["token_usage"]

    if "usage" in summary:
        return summary["usage"]

    return None


def extract_cost(trace: dict[str, Any]) -> dict | None:
    """Extract cost information from trace summary."""
    summary = trace.get("summary", {})
    weave_summary = summary.get("weave", {})

    if "costs" in weave_summary:
        return weave_summary["costs"]

    return None


def get_trace_status(trace: dict[str, Any]) -> str:
    """Get the status of a trace."""
    if trace.get("exception"):
        return "error"

    summary = trace.get("summary", {})
    weave_summary = summary.get("weave", {})

    if "status" in weave_summary:
        return weave_summary["status"]

    if trace.get("ended_at"):
        return "success"

    return "unknown"


# ============================================================================
# Main clustering pipeline
# ============================================================================


def get_api_key_for_model(model: str) -> str:
    """Get the appropriate API key based on the model provider."""
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

    return api_key


def get_llm_kwargs(model: str) -> dict[str, Any]:
    """Get the kwargs for litellm completion based on the model provider.

    For W&B inference models, this configures the custom API base URL.

    Args:
        model: The model name (e.g., "gemini/gemini-2.5-flash", "wandb/meta-llama/Llama-4-Scout-17B-16E-Instruct")

    Returns:
        Dictionary of kwargs for litellm.completion
    """
    provider = model.split("/")[0].lower() if "/" in model else "openai"
    api_key = get_api_key_for_model(model)

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


def extract_human_annotations(trace: dict[str, Any]) -> dict[str, Any]:
    """Extract human annotations from a trace.

    Checks common annotation locations:
    - attributes.weave.user_feedback
    - attributes.annotation
    - annotation
    - feedback
    - summary.weave.status (for annotation status)
    """
    annotations = {}

    # Check attributes.weave for user_feedback and annotations
    if "attributes" in trace and "weave" in trace["attributes"]:
        weave_attrs = trace["attributes"]["weave"]

        if "user_feedback" in weave_attrs:
            annotations["user_feedback"] = weave_attrs["user_feedback"]

        for key in weave_attrs.keys():
            if "annotation" in key.lower() or "feedback" in key.lower():
                annotations[f"weave.{key}"] = weave_attrs[key]

    # Check attributes for annotation field
    if trace.get("attributes", {}).get("annotation"):
        annotations["annotation"] = trace["attributes"]["annotation"]

    # Check top-level annotation field
    if trace.get("annotation"):
        annotations["annotation"] = trace["annotation"]

    # Check top-level feedback field
    if trace.get("feedback"):
        annotations["feedback"] = trace["feedback"]

    # Check summary for weave status
    if trace.get("summary", {}).get("weave", {}).get("status"):
        annotations["weave_status"] = trace["summary"]["weave"]["status"]

    return annotations


def extract_metadata(trace: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata from a trace including scores, timestamps, etc."""
    metadata = {}

    # Extract scores if they exist
    output = trace.get("output")
    if isinstance(output, dict) and output.get("scores"):
        metadata["scores"] = output["scores"]

    # Extract timestamps
    if trace.get("started_at"):
        metadata["started_at"] = trace["started_at"]
    if trace.get("ended_at"):
        metadata["ended_at"] = trace["ended_at"]

    # Extract summary if available
    if trace.get("summary"):
        metadata["summary"] = trace["summary"]

    # Extract exception if any
    if trace.get("exception"):
        metadata["exception"] = trace["exception"]

    return metadata


@weave.op
async def draft_categorization(
    trace_id: str,
    trace_input: dict | str,
    trace_output: dict | str,
    trace_metadata: dict | str,
    user_context: str,
    annotation_section: str,
    execution_trace: str | None,
    model: str,
    semaphore: Semaphore,
    debug: bool = False,
    console: Any = None,
    existing_clusters: dict | None = None,
) -> dict[str, Any]:
    """Perform first-pass categorization of a single trace."""
    async with semaphore:
        if isinstance(trace_input, dict):
            trace_input = json.dumps(trace_input, indent=2, default=str)
        if isinstance(trace_output, dict):
            trace_output = json.dumps(trace_output, indent=2, default=str)
        if isinstance(trace_metadata, dict):
            trace_metadata = json.dumps(trace_metadata, indent=2, default=str)

        execution_trace_section = build_execution_trace_section(execution_trace)
        existing_clusters_section = build_existing_clusters_section(existing_clusters)

        prompt = FIRST_PASS_PROMPT.format(
            trace_input=trace_input,
            trace_output=trace_output,
            trace_metadata=trace_metadata,
            user_context=user_context,
            existing_clusters_section=existing_clusters_section,
            execution_trace_section=execution_trace_section,
        )

        llm_kwargs = get_llm_kwargs(model)
        response = await litellm.acompletion(
            messages=[
                {"role": "system", "content": FIRST_PASS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format=FirstPassCategorization,
            **llm_kwargs,
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "trace_id": trace_id,
            "categories": result.get("first_pass_categories", []),
            "thinking": result.get("thinking", ""),
        }


@weave.op
async def run_draft_categorization(
    traces: list[dict[str, Any]],
    model: str,
    user_context: str,
    annotation_summary: dict[str, Any],
    deep_trace_analysis: bool = False,
    max_concurrent: int = 10,
    debug: bool = False,
    console: Any = None,
    existing_clusters: dict | None = None,
    progress_tracker: ProgressTracker | None = None,
) -> list[dict[str, Any]]:
    """Run first-pass categorization on all traces."""
    semaphore = Semaphore(max_concurrent)

    annotation_section = build_human_annotations_section(annotation_summary)

    if debug and console:
        console.print(f"[dim]Starting draft categorization for {len(traces)} traces with max_concurrent={max_concurrent}[/dim]")
        if existing_clusters and "clusters" in existing_clusters:
            console.print(f"[dim]Using {len(existing_clusters['clusters'])} existing cluster definitions[/dim]")

    async def categorize_with_progress(trace: dict[str, Any]) -> dict[str, Any]:
        """Wrapper to track progress."""
        result = await draft_categorization(
            trace_id=trace.get("id", ""),
            trace_input=trace.get("inputs", {}),
            trace_output=trace.get("output", {}),
            trace_metadata=extract_metadata(trace),
            user_context=user_context,
            annotation_section=annotation_section,
            execution_trace=trace.get("execution_trace") if deep_trace_analysis else None,
            model=model,
            semaphore=semaphore,
            debug=debug,
            console=console,
            existing_clusters=existing_clusters,
        )
        if progress_tracker:
            progress_tracker.update(result.get("trace_id"))
        return result

    tasks = [categorize_with_progress(trace) for trace in traces]

    return await asyncio.gather(*tasks)


@weave.op
async def aggregate_categorizations(
    draft_results: list[dict[str, Any]],
    model: str,
    debug: bool = False,
    console: Any = None,
) -> ClusteringCategories:
    """Aggregate draft categorizations into clusters."""
    # Build the draft categorizations string
    draft_str = ""
    for result in draft_results:
        draft_str += f"\n### Trace ID: {result['trace_id']}\n"
        for cat in result.get("categories", []):
            draft_str += f"- Category: {cat.get('category_name', 'unknown')}\n"
            draft_str += f"  Description: {cat.get('category_description', '')}\n"
            draft_str += f"  Note: {cat.get('trace_note', '')}\n"
        draft_str += "\n"

    num_traces = len(draft_results)

    if debug and console:
        console.print(f"[dim]Aggregating categorizations from {num_traces} traces...[/dim]")

    system_prompt = CLUSTERING_SYSTEM_PROMPT.format(num_traces=num_traces)
    prompt = CLUSTERING_PROMPT.format(
        num_traces=num_traces,
        draft_categorizations_and_notes=draft_str,
    )

    if debug and console:
        console.print(f"[dim]Calling LLM for clustering aggregation...[/dim]")

    try:
        llm_kwargs = get_llm_kwargs(model)
        response = await litellm.acompletion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format=ClusteringCategories,
            **llm_kwargs,
        )

        if debug and console:
            console.print(f"[dim]✓ Clustering aggregation complete[/dim]")

        result = json.loads(response.choices[0].message.content)
        return ClusteringCategories(**result)
    except Exception as e:
        if debug and console:
            console.print(f"[red]✗ Error during clustering aggregation: {e}[/red]")
        raise


@weave.op
async def final_classification(
    trace_id: str,
    trace_input: dict | str,
    trace_output: dict | str,
    trace_metadata: dict | str,
    user_context: str,
    annotation_section: str,
    execution_trace: str | None,
    categories_str: str,
    model: str,
    semaphore: Semaphore,
    debug: bool = False,
    console: Any = None,
) -> dict[str, Any]:
    """Perform final classification of a trace into categories."""
    async with semaphore:
        if debug and console:
            console.print(f"[dim]  → Classifying trace {trace_id[:8]}...[/dim]")

        if isinstance(trace_input, dict):
            trace_input = json.dumps(trace_input, indent=2, default=str)
        if isinstance(trace_output, dict):
            trace_output = json.dumps(trace_output, indent=2, default=str)
        if isinstance(trace_metadata, dict):
            trace_metadata = json.dumps(trace_metadata, indent=2, default=str)

        execution_trace_section = build_execution_trace_section(execution_trace)

        prompt = FINAL_CLASSIFICATION_PROMPT.format(
            trace_input=trace_input,
            trace_output=trace_output,
            trace_metadata=trace_metadata,
            user_context=user_context,
            human_annotations_section=annotation_section,
            execution_trace_section=execution_trace_section,
            available_pattern_categories=categories_str,
        )

        llm_kwargs = get_llm_kwargs(model)
        response = await litellm.acompletion(
            messages=[
                {"role": "system", "content": FINAL_CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format=FinalClassification,
            **llm_kwargs,
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "trace_id": trace_id,
            "pattern_categories": result.get("pattern_categories", []),
            "categorization_reason": result.get("categorization_reason", ""),
            "thinking": result.get("thinking", ""),
        }


@weave.op
async def run_final_classification(
    traces: list[dict[str, Any]],
    categories: list[Category],
    model: str,
    user_context: str,
    annotation_summary: dict[str, Any],
    deep_trace_analysis: bool = False,
    max_concurrent: int = 10,
    debug: bool = False,
    console: Any = None,
    progress_tracker: ProgressTracker | None = None,
) -> list[dict[str, Any]]:
    """Run final classification on all traces."""
    semaphore = Semaphore(max_concurrent)

    annotation_section = build_human_annotations_section(annotation_summary)

    # Build categories string
    categories_str = ""
    for i, cat in enumerate(categories):
        categories_str += f"\n### Category {i + 1}: {cat.pattern_category_name}\n"
        categories_str += f"**Definition:** {cat.pattern_category_definition}\n"
        categories_str += f"**Notes:** {cat.pattern_category_notes}\n"

    if debug and console:
        console.print(f"[dim]Starting final classification for {len(traces)} traces with {len(categories)} categories[/dim]")

    async def classify_with_progress(trace: dict[str, Any]) -> dict[str, Any]:
        """Wrapper to track progress."""
        result = await final_classification(
            trace_id=trace.get("id", ""),
            trace_input=trace.get("inputs", {}),
            trace_output=trace.get("output", {}),
            trace_metadata=extract_metadata(trace),
            user_context=user_context,
            annotation_section=annotation_section,
            execution_trace=trace.get("execution_trace") if deep_trace_analysis else None,
            categories_str=categories_str,
            model=model,
            semaphore=semaphore,
            debug=debug,
            console=console,
        )
        if progress_tracker:
            progress_tracker.update(result.get("trace_id"))
        return result

    tasks = [classify_with_progress(trace) for trace in traces]

    return await asyncio.gather(*tasks)


async def fetch_deep_traces(
    traces: list[dict[str, Any]],
    client: Any,
    nesting_depth: int,
    compaction_model: str,
    max_trace_tokens: int,
    console: Any = None,
    progress_tracker: ProgressTracker | None = None,
) -> list[dict[str, Any]]:
    """Fetch and format deep execution traces for all traces.

    Args:
        traces: List of trace dictionaries
        client: AnalyticsWeaveClient instance
        nesting_depth: How deep to traverse when fetching nested traces
        compaction_model: LLM model for trace compaction
        max_trace_tokens: Token threshold before triggering compaction
        console: Rich console for output
        progress_tracker: Optional progress tracker

    Returns:
        List of traces with execution_trace field populated
    """
    api_key = get_api_key_for_model(compaction_model)

    for i, trace in enumerate(traces):
        trace_id = trace.get("id", "")

        try:
            # Fetch descendants
            descendants = client.query_descendants_recursive(
                parent_id=trace_id,
                max_depth=nesting_depth,
            )

            all_traces = descendants.get("traces", [])
            if not all_traces:
                trace["execution_trace"] = None
                continue

            # Find root trace
            root_trace = next((t for t in all_traces if t["id"] == trace_id), None)
            if not root_trace:
                root_trace = {
                    "id": trace_id,
                    "op_name": trace.get("op_name", "Root"),
                    "inputs": trace.get("inputs", {}),
                    "output": trace.get("output", {}),
                    "started_at": trace.get("started_at"),
                    "ended_at": trace.get("ended_at"),
                }
                all_traces.append(root_trace)

            # Format as tree
            execution_tree = format_trace_as_tree(
                root_trace=root_trace,
                all_traces=all_traces,
                max_depth=nesting_depth,
                include_inputs=True,
                include_outputs=True,
            )

            # Compact if too large
            execution_tree = compact_execution_trace(
                trace_tree=execution_tree,
                model=compaction_model,
                api_key=api_key,
                max_tokens=max_trace_tokens,
            )

            trace["execution_trace"] = execution_tree

        except Exception as e:
            if console:
                console.print(f"[yellow]    Warning: Could not fetch deep trace: {e}[/yellow]")
            trace["execution_trace"] = None

        if progress_tracker:
            progress_tracker.update(trace_id)

    return traces


@weave.op
async def run_clustering_pipeline(
    traces: list[dict[str, Any]],
    model: str,
    entity: str,
    project: str,
    max_concurrent: int = 10,
    debug: bool = False,
    console: Any = None,
    user_context: str = "",
    deep_trace_analysis: bool = False,
    client: Any = None,
    nesting_depth: int = 3,
    compaction_model: str | None = None,
    max_trace_tokens: int = 10000,
    existing_clusters: dict | None = None,
    url: str = "",
) -> ClusterOutput:
    """Run the full clustering pipeline.

    Args:
        traces: List of trace dictionaries to analyze
        model: LiteLLM model name
        entity: W&B entity
        project: W&B project
        max_concurrent: Max concurrent LLM calls
        debug: Enable debug output
        console: Rich console for output (optional)
        user_context: User context about the AI system being analyzed
        deep_trace_analysis: Whether to include deep trace execution trees
        client: AnalyticsWeaveClient instance (required for deep_trace_analysis)
        nesting_depth: How deep to traverse nested traces
        compaction_model: LLM model for trace compaction (defaults to main model)
        max_trace_tokens: Token threshold before compaction

    Returns:
        ClusterOutput with all clustering results
    """
    use_console = console is not None
    compaction_model = compaction_model or model

    # Debug output for configuration
    if debug and console:
        console.print(f"\n[dim]═══ Clustering Pipeline Configuration ═══[/dim]")
        console.print(f"[dim]Model: {model}[/dim]")
        console.print(f"[dim]Max concurrent: {max_concurrent}[/dim]")
        console.print(f"[dim]Deep trace analysis: {deep_trace_analysis}[/dim]")
        if existing_clusters:
            console.print(f"[dim]Existing clusters loaded: {len(existing_clusters.get('clusters', []))}[/dim]")
        console.print(f"[dim]═══════════════════════════════════════[/dim]\n")

    # If no user context provided, use a generic one
    if not user_context:
        user_context = (
            f"This is an AI system in the '{project}' project. "
            "We are analyzing traces to identify patterns and potential issues."
        )

    # Extract annotations from traces
    annotation_examples = []
    for trace in traces:
        annotations = extract_human_annotations(trace)
        if annotations:
            annotation_examples.append({"trace_id": trace.get("id"), "annotations": annotations})

    annotation_summary = {
        "has_annotations": len(annotation_examples) > 0,
        "examples": annotation_examples[:5],
    }

    # Step 0: Deep trace analysis (if enabled)
    if deep_trace_analysis and client:
        deep_progress = None
        if use_console:
            console.print("\n[bold cyan]Step 0: Deep Trace Analysis[/bold cyan]")
            console.print("  [dim]Fetching execution trees...[/dim]")
            deep_progress = ProgressTracker(
                total=len(traces),
                description="Fetching trees",
                console=console,
                show_ids=True,
            )
            deep_progress.start()

        traces = await fetch_deep_traces(
            traces=traces,
            client=client,
            nesting_depth=nesting_depth,
            compaction_model=compaction_model,
            max_trace_tokens=max_trace_tokens,
            console=console if debug else None,
            progress_tracker=deep_progress,
        )

        if deep_progress:
            traces_with_trees = sum(1 for t in traces if t.get("execution_trace"))
            deep_progress.finish(f"Fetched {traces_with_trees} execution trees")

    # Step 1: Draft categorization
    draft_progress = None
    if use_console:
        console.print("  [dim]Draft categorization...[/dim]")
        draft_progress = ProgressTracker(
            total=len(traces),
            description="Categorizing",
            console=console,
            show_ids=True,
        )
        draft_progress.start()

    draft_results = await run_draft_categorization(
        traces=traces,
        model=model,
        user_context=user_context,
        annotation_summary=annotation_summary,
        deep_trace_analysis=deep_trace_analysis,
        max_concurrent=max_concurrent,
        debug=debug,
        console=console if debug else None,
        existing_clusters=existing_clusters,
        progress_tracker=draft_progress,
    )

    if draft_progress:
        draft_progress.finish(f"Completed {len(draft_results)} draft categorizations")

    # Load existing cluster definitions if provided
    existing_categories = []
    if existing_clusters and "clusters" in existing_clusters:
        for cluster in existing_clusters["clusters"]:
            existing_categories.append(
                Category(
                    thinking="Existing cluster definition from input file",
                    pattern_category_name=cluster.get("cluster_name", ""),
                    pattern_category_definition=cluster.get("cluster_definition", ""),
                    pattern_category_notes=f"Predefined cluster from {existing_clusters.get('name', 'input file')}",
                )
            )

    # Collect unique candidate categories
    unique_categories: set[str] = set()
    for result in draft_results:
        for cat in result.get("categories", []):
            unique_categories.add(cat.get("category_name", "unknown"))

    # Step 2: Aggregate into clusters (to discover new categories)
    if use_console:
        console.print("\n[bold cyan]Step 4: Review & Clustering[/bold cyan]")
        console.print(
            f"[bright_magenta]  Clustering {len(unique_categories)} candidate categories...[/bright_magenta]"
        )
        spinner = AnalyticsSpinner("Clustering and reviewing categories")
        spinner.start()

    clustering_result = await aggregate_categorizations(
        draft_results=draft_results,
        model=model,
        debug=debug,
        console=console if debug else None,
    )

    if use_console:
        spinner.stop("Review completed successfully", success=True)

    # Merge existing and newly discovered categories
    all_categories = existing_categories + clustering_result.pattern_categories

    # Show discovered categories in debug mode
    if debug and use_console:
        console.print("\n[dim]Discovered pattern categories:[/dim]")
        for i, cat in enumerate(clustering_result.pattern_categories):
            console.print(f"  [cyan]{i + 1}.[/cyan] {cat.pattern_category_name}")
            console.print(f"     [dim]{cat.pattern_category_definition[:80]}...[/dim]")

    # Step 3: Final classification
    classification_progress = None
    if use_console:
        console.print("\n[bold cyan]Step 5: Final Classification[/bold cyan]")
        console.print(f"  [dim]Classifying into {len(all_categories)} categories...[/dim]")
        classification_progress = ProgressTracker(
            total=len(traces),
            description="Classifying",
            console=console,
            show_ids=True,
        )
        classification_progress.start()

    classification_results = await run_final_classification(
        traces=traces,
        categories=all_categories,
        model=model,
        user_context=user_context,
        annotation_summary=annotation_summary,
        deep_trace_analysis=deep_trace_analysis,
        max_concurrent=max_concurrent,
        debug=debug,
        console=console if debug else None,
        progress_tracker=classification_progress,
    )

    if classification_progress:
        classification_progress.finish("Classification complete")

    # Build output structure - traces can belong to multiple clusters
    clusters_by_category: dict[str, list[ClusterResult]] = {}
    category_info: dict[str, Category] = {cat.pattern_category_name: cat for cat in all_categories}

    for result in classification_results:
        # Each trace can have multiple categories
        categories = result.get("pattern_categories", [])

        # If the trace has categories, add it to each one
        for cat_name in categories:
            if cat_name not in clusters_by_category:
                clusters_by_category[cat_name] = []

            clusters_by_category[cat_name].append(
                ClusterResult(
                    trace_id=result["trace_id"],
                    pattern_category=cat_name,
                    categorization_reason=result["categorization_reason"],
                    trace_url=build_trace_url(entity, project, result["trace_id"]),
                )
            )

    # Create cluster groups sorted by count
    total_traces = len(traces)
    cluster_groups = []

    for cat_name, cat_traces in sorted(
        clusters_by_category.items(),
        key=lambda x: len(x[1]),
        reverse=True,
    ):
        cat_info = category_info.get(cat_name)
        cluster_groups.append(
            ClusterGroup(
                category_name=cat_name,
                category_definition=cat_info.pattern_category_definition if cat_info else "",
                count=len(cat_traces),
                percentage=(len(cat_traces) / total_traces) * 100 if total_traces > 0 else 0,
                traces=cat_traces,
            )
        )

    return ClusterOutput(
        total_traces=total_traces,
        entity=entity,
        project=project,
        clusters=cluster_groups,
    )
