"""URL parser for Weave trace URLs."""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


@dataclass
class ParsedWeaveURL:
    """Parsed components from a Weave trace URL."""

    entity: str
    project: str
    trace_id: str | None = None
    filters: dict[str, Any] | None = None
    url_type: str = "traces"  # "traces" or "call"


def parse_weave_url(url: str) -> ParsedWeaveURL:
    """Parse a Weave trace URL and extract components.

    Supports both trace list URLs with filters and individual call URLs.

    Args:
        url: The Weave URL to parse

    Returns:
        ParsedWeaveURL with extracted components

    Raises:
        ValueError: If URL format is not recognized

    Examples:
        # Trace list with filters
        >>> parse_weave_url("https://wandb.ai/entity/project/weave/traces?filter=...")

        # Individual call URL
        >>> parse_weave_url("https://wandb.ai/entity/project/weave/calls/abc123")
    """
    parsed = urlparse(url)

    # Extract entity and project from path
    # Path format: /{entity}/{project}/weave/traces or /{entity}/{project}/weave/calls/{id}
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) < 3:
        raise ValueError(f"Invalid Weave URL path: {parsed.path}")

    entity = path_parts[0]
    project = path_parts[1]

    # Check if it's a weave URL
    if path_parts[2] != "weave":
        raise ValueError(f"Not a Weave URL: expected 'weave' in path, got {path_parts[2]}")

    # Determine URL type and extract relevant info
    if len(path_parts) >= 4:
        if path_parts[3] == "traces":
            # Trace list URL - parse filters from query string
            filters = _parse_trace_filters(parsed.query)
            return ParsedWeaveURL(
                entity=entity,
                project=project,
                filters=filters,
                url_type="traces",
            )
        elif path_parts[3] == "calls" and len(path_parts) >= 5:
            # Individual call URL
            trace_id = path_parts[4]
            return ParsedWeaveURL(
                entity=entity,
                project=project,
                trace_id=trace_id,
                url_type="call",
            )

    raise ValueError(f"Could not parse Weave URL: {url}")


def _parse_trace_filters(query_string: str) -> dict[str, Any] | None:
    """Parse filter parameters from query string.

    Args:
        query_string: The URL query string

    Returns:
        Parsed filter dictionary or None if no filters
    """
    if not query_string:
        return None

    params = parse_qs(query_string)
    result: dict[str, Any] = {}

    # Check for 'filter' parameter (singular - contains opVersionRefs, etc.)
    # Format: ?filter={"opVersionRefs":["weave:///..."]}
    if "filter" in params:
        try:
            filter_json = unquote(params["filter"][0])
            filter_data = json.loads(filter_json)
            result.update(filter_data)
        except (json.JSONDecodeError, IndexError):
            pass

    # Check for 'filters' parameter (plural - used by Weave UI for filter items)
    # Format: ?filters={"items":[{"field":"...", "operator":"...", "value":"..."}], "logicOperator":"and"}
    if "filters" in params:
        try:
            filters_json = unquote(params["filters"][0])
            filters_data = json.loads(filters_json)
            # Merge with existing result
            if "items" in filters_data:
                if "items" not in result:
                    result["items"] = []
                result["items"].extend(filters_data["items"])
            if "logicOperator" in filters_data:
                result["logicOperator"] = filters_data["logicOperator"]
            # Copy any other keys
            for key, value in filters_data.items():
                if key not in result:
                    result[key] = value
        except (json.JSONDecodeError, IndexError):
            pass

    # Check for individual filter items (alternative format)
    # Format: ?traceFilter=[{"field":"op_name","operator":"=","value":"MyOp"}]
    if "traceFilter" in params and not result:
        try:
            filter_json = unquote(params["traceFilter"][0])
            return json.loads(filter_json)
        except (json.JSONDecodeError, IndexError):
            pass

    return result if result else None


def build_trace_url(entity: str, project: str, trace_id: str) -> str:
    """Build a Weave trace URL from components.

    Args:
        entity: W&B entity name
        project: W&B project name
        trace_id: The trace/call ID

    Returns:
        Full URL to the trace in Weave
    """
    return f"https://wandb.ai/{entity}/{project}/weave/calls/{trace_id}"

