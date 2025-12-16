"""Weave client for fetching trace data."""

import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout


def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (ConnectionError, Timeout, HTTPError),
) -> Callable:
    """Decorator to retry a function on failure with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    # Don't retry on 4xx errors except 429
                    if isinstance(e, HTTPError) and e.response is not None:
                        if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                            raise
                    delay = backoff_factor * (2 ** attempt)
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


@dataclass
class WeaveClientConfig:
    """Configuration for Weave client."""

    entity: str
    project: str
    api_key: str | None = None
    base_url: str = "https://trace.wandb.ai"

    def __post_init__(self) -> None:
        """Load API key from environment if not provided."""
        if not self.api_key:
            self.api_key = os.environ.get("WANDB_API_KEY")
            if not self.api_key:
                raise ValueError("WANDB_API_KEY not found. Run 'weave analytics setup' first.")


class AnalyticsWeaveClient:
    """Client for fetching Weave traces for analytics."""

    def __init__(self, config: WeaveClientConfig) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self._setup_headers()

    def _setup_headers(self) -> None:
        """Set up authentication headers."""
        auth_string = base64.b64encode(f":{self.config.api_key}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/json",
            "Accept": "application/jsonl",
        }

    @retry_on_failure()
    def _execute_query(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a query to the Weave API."""
        endpoint = f"{self.config.base_url}/calls/stream_query"
        response = requests.post(
            endpoint,
            headers=self.headers,
            json=query,
            timeout=60,
            stream=True,
        )
        response.raise_for_status()

        # Parse JSONL response
        results = []
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    results.append(data)
                except json.JSONDecodeError:
                    continue
        return results

    def query_traces_with_filters(
        self,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        trace_roots_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Query traces using Weave UI-style filters.

        Args:
            filters: Filter object from Weave UI (from trace URL)
            limit: Maximum number of traces to return
            trace_roots_only: If True, only return root traces

        Returns:
            List of trace dictionaries
        """
        columns = [
            "id",
            "trace_id",
            "parent_id",
            "started_at",
            "ended_at",
            "op_name",
            "display_name",
            "inputs",
            "output",
            "summary",
            "exception",
            "attributes",
        ]

        # Build the filter object (server-side filtering per API spec)
        api_filter: dict[str, Any] = {
            "trace_roots_only": trace_roots_only,
        }

        query: dict[str, Any] = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "filter": api_filter,
            "columns": columns,
            "sort_by": [{"field": "started_at", "direction": "desc"}],
            "include_feedback": False,
            "include_costs": False,
        }

        expr_conditions = []

        # Convert Weave UI filters to API format
        if filters:
            # Handle opVersionRefs filter - pass directly to filter.op_names
            # The API accepts full refs like "weave:///entity/project/op/OpName:*"
            op_version_refs = filters.get("opVersionRefs", [])
            if op_version_refs:
                api_filter["op_names"] = op_version_refs

            # Handle filter items (field/operator/value format)
            filter_items = filters.get("items", [])
            for item in filter_items:
                field = item.get("field")
                operator = item.get("operator", "")
                value = item.get("value")

                condition = self._convert_filter_item(field, operator, value)
                if condition:
                    expr_conditions.append(condition)

        if expr_conditions:
            if len(expr_conditions) == 1:
                query["query"] = {"$expr": expr_conditions[0]}
            else:
                query["query"] = {"$expr": {"$and": expr_conditions}}

        if limit:
            query["limit"] = limit

        return self._execute_query(query)

    def _build_filter_and_query(
        self,
        filters: dict[str, Any] | None = None,
        trace_roots_only: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Build API filter and query expression from Weave UI filters.

        Args:
            filters: Filter object from Weave UI (from trace URL)
            trace_roots_only: If True, only return root traces

        Returns:
            Tuple of (api_filter dict, query dict or None)
        """
        api_filter: dict[str, Any] = {
            "trace_roots_only": trace_roots_only,
        }

        expr_conditions = []

        if filters:
            # Handle opVersionRefs filter
            op_version_refs = filters.get("opVersionRefs", [])
            if op_version_refs:
                api_filter["op_names"] = op_version_refs

            # Handle filter items (field/operator/value format)
            filter_items = filters.get("items", [])
            for item in filter_items:
                field = item.get("field")
                operator = item.get("operator", "")
                value = item.get("value")

                condition = self._convert_filter_item(field, operator, value)
                if condition:
                    expr_conditions.append(condition)

        query_expr = None
        if expr_conditions:
            if len(expr_conditions) == 1:
                query_expr = {"$expr": expr_conditions[0]}
            else:
                query_expr = {"$expr": {"$and": expr_conditions}}

        return api_filter, query_expr

    @retry_on_failure()
    def count_traces_with_filters(
        self,
        filters: dict[str, Any] | None = None,
        trace_roots_only: bool = True,
    ) -> int:
        """Count traces matching the given filters efficiently.

        Uses the calls/query_stats endpoint which is optimized for counting
        without fetching full trace data.

        Args:
            filters: Filter object from Weave UI (from trace URL)
            trace_roots_only: If True, only count root traces

        Returns:
            Number of traces matching the filters
        """
        api_filter, query_expr = self._build_filter_and_query(filters, trace_roots_only)

        request_body: dict[str, Any] = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "filter": api_filter,
        }

        if query_expr:
            request_body["query"] = query_expr

        endpoint = f"{self.config.base_url}/calls/query_stats"
        headers = {
            "Authorization": self.headers["Authorization"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json=request_body,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        return result.get("count", 0)

    def query_trace_ids_with_filters(
        self,
        filters: dict[str, Any] | None = None,
        trace_roots_only: bool = True,
    ) -> list[str]:
        """Query only trace IDs matching the given filters.

        This is more efficient than fetching full traces when you only need IDs
        for sampling purposes.

        Args:
            filters: Filter object from Weave UI (from trace URL)
            trace_roots_only: If True, only return root trace IDs

        Returns:
            List of trace IDs matching the filters
        """
        api_filter, query_expr = self._build_filter_and_query(filters, trace_roots_only)

        query: dict[str, Any] = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "filter": api_filter,
            "columns": ["id"],  # Only fetch ID column
            "sort_by": [{"field": "started_at", "direction": "desc"}],
            "include_feedback": False,
            "include_costs": False,
        }

        if query_expr:
            query["query"] = query_expr

        results = self._execute_query(query)
        return [r["id"] for r in results if r.get("id")]

    def query_traces_by_ids(
        self,
        trace_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch full trace data for specific trace IDs.

        Args:
            trace_ids: List of trace IDs to fetch

        Returns:
            List of trace dictionaries with full data
        """
        if not trace_ids:
            return []

        columns = [
            "id",
            "trace_id",
            "parent_id",
            "started_at",
            "ended_at",
            "op_name",
            "display_name",
            "inputs",
            "output",
            "summary",
            "exception",
            "attributes",
        ]

        # Build OR condition for all trace IDs
        id_conditions = [
            {"$eq": [{"$getField": "id"}, {"$literal": tid}]}
            for tid in trace_ids
        ]

        query: dict[str, Any] = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "query": {"$expr": {"$or": id_conditions}},
            "columns": columns,
            "sort_by": [{"field": "started_at", "direction": "desc"}],
            "include_feedback": False,
            "include_costs": False,
        }

        return self._execute_query(query)

    def _convert_filter_item(
        self,
        field: str,
        operator: str,
        value: Any,
    ) -> dict[str, Any] | None:
        """Convert a single filter item to API format."""
        if "(bool): is" in operator:
            bool_value = str(value).lower() == "true"
            return {
                "$eq": [
                    {"$getField": field},
                    {"$literal": str(bool_value).lower()}
                ]
            }
        elif "(string): contains" in operator:
            return {
                "$contains": {
                    "input": {"$getField": field},
                    "substr": {"$literal": value}
                }
            }
        elif "(string): in" in operator:
            # Handle 'in' operator - value can be a single string or comma-separated list
            if isinstance(value, str):
                # Check if it's a comma-separated list
                values = [v.strip() for v in value.split(",")]
                if len(values) == 1:
                    # Single value - use equality
                    return {
                        "$eq": [
                            {"$getField": field},
                            {"$literal": value}
                        ]
                    }
                else:
                    # Multiple values - use $or with equality checks
                    return {
                        "$or": [
                            {"$eq": [{"$getField": field}, {"$literal": v}]}
                            for v in values
                        ]
                    }
            elif isinstance(value, list):
                if len(value) == 1:
                    return {
                        "$eq": [
                            {"$getField": field},
                            {"$literal": value[0]}
                        ]
                    }
                else:
                    return {
                        "$or": [
                            {"$eq": [{"$getField": field}, {"$literal": v}]}
                            for v in value
                        ]
                    }
            # Fallback to equality
            return {
                "$eq": [
                    {"$getField": field},
                    {"$literal": value}
                ]
            }
        elif "(string): equals" in operator or operator == "=":
            return {
                "$eq": [
                    {"$getField": field},
                    {"$literal": value}
                ]
            }
        elif "(number): >" in operator or operator == ">":
            return {
                "$gt": [
                    {"$convert": {"input": {"$getField": field}, "to": "double"}},
                    {"$literal": float(value)}
                ]
            }
        elif "(number): <" in operator or operator == "<":
            return {
                "$not": [{
                    "$gte": [
                        {"$convert": {"input": {"$getField": field}, "to": "double"}},
                        {"$literal": float(value)}
                    ]
                }]
            }
        elif "(date): before" in operator:
            # Convert ISO date to Unix timestamp (seconds)
            timestamp = self._iso_to_unix_timestamp(value)
            if timestamp is not None:
                # "before" = NOT greater than timestamp
                return {
                    "$not": [{
                        "$gt": [
                            {"$getField": field},
                            {"$literal": timestamp}
                        ]
                    }]
                }
            return None
        elif "(date): after" in operator:
            # Convert ISO date to Unix timestamp (seconds)
            timestamp = self._iso_to_unix_timestamp(value)
            if timestamp is not None:
                # "after" = greater than timestamp
                return {
                    "$gt": [
                        {"$getField": field},
                        {"$literal": timestamp}
                    ]
                }
            return None
        elif "(date): on" in operator or "(date): equals" in operator:
            # For date equality - this would need range queries for a full day
            # For now, use exact timestamp match
            timestamp = self._iso_to_unix_timestamp(value)
            if timestamp is not None:
                return {
                    "$eq": [
                        {"$getField": field},
                        {"$literal": timestamp}
                    ]
                }
            return None
        # Default equality
        return {
            "$eq": [
                {"$getField": field},
                {"$literal": value}
            ]
        }

    @staticmethod
    def _iso_to_unix_timestamp(iso_string: str) -> int | None:
        """Convert an ISO datetime string to Unix timestamp (seconds).

        Args:
            iso_string: ISO format datetime string (e.g., "2025-04-21T22:00:00.000Z")

        Returns:
            Unix timestamp in seconds, or None if parsing fails
        """
        try:
            # Handle various ISO formats
            iso_string = iso_string.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_string)
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            return None

    def query_by_call_id(
        self,
        call_id: str,
    ) -> list[dict[str, Any]]:
        """Query a specific trace by call ID."""
        columns = [
            "id",
            "trace_id",
            "parent_id",
            "started_at",
            "ended_at",
            "op_name",
            "display_name",
            "inputs",
            "output",
            "summary",
            "exception",
            "attributes",
        ]

        query = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "query": {
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": call_id}
                    ]
                }
            },
            "columns": columns,
            "limit": 1,
        }

        return self._execute_query(query)

    @retry_on_failure()
    def read_refs_batch(self, refs: list[str]) -> list[Any]:
        """Resolve Weave references in batch."""
        if not refs:
            return []

        # Deduplicate
        unique_refs = list(dict.fromkeys(refs))

        endpoint = f"{self.config.base_url}/refs/read_batch"
        headers = {
            "Authorization": self.headers["Authorization"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json={"refs": unique_refs},
            timeout=30,
        )
        response.raise_for_status()

        result_values = response.json()["vals"]
        ref_to_value = dict(zip(unique_refs, result_values))
        return [ref_to_value[ref] for ref in refs]

    @staticmethod
    def collect_refs(obj: Any) -> list[str]:
        """Recursively collect all Weave references."""
        refs: set[str] = set()

        def _collect(item: Any) -> None:
            if isinstance(item, str):
                if item.startswith("weave:///"):
                    refs.add(item)
            elif isinstance(item, dict):
                for value in item.values():
                    _collect(value)
            elif isinstance(item, (list, tuple, set)):
                for value in item:
                    _collect(value)

        _collect(obj)
        return list(refs)

    @staticmethod
    def replace_refs(obj: Any, resolved_refs: dict[str, Any]) -> Any:
        """Recursively replace Weave refs with resolved values."""
        if isinstance(obj, str):
            if obj.startswith("weave:///") and obj in resolved_refs:
                return resolved_refs[obj]
            return obj
        elif isinstance(obj, dict):
            return {k: AnalyticsWeaveClient.replace_refs(v, resolved_refs) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [AnalyticsWeaveClient.replace_refs(item, resolved_refs) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(AnalyticsWeaveClient.replace_refs(item, resolved_refs) for item in obj)
        return obj

    def query_descendants_recursive(
        self,
        parent_id: str,
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """Query all descendants of a trace recursively.

        Args:
            parent_id: The parent trace ID to query descendants for
            max_depth: Maximum depth to traverse

        Returns:
            Dictionary with "traces" list containing all descendant traces
        """
        columns = [
            "id",
            "trace_id",
            "parent_id",
            "started_at",
            "ended_at",
            "op_name",
            "display_name",
            "inputs",
            "output",
            "summary",
            "exception",
            "attributes",
        ]

        all_traces: list[dict[str, Any]] = []
        visited_ids: set[str] = set()
        current_parents = [parent_id]

        for _ in range(max_depth):
            if not current_parents:
                break

            # Query children for all current parents
            parent_conditions = [
                {"$eq": [{"$getField": "parent_id"}, {"$literal": pid}]}
                for pid in current_parents
                if pid not in visited_ids
            ]

            if not parent_conditions:
                break

            # Mark parents as visited
            visited_ids.update(current_parents)

            query: dict[str, Any] = {
                "project_id": f"{self.config.entity}/{self.config.project}",
                "query": {"$expr": {"$or": parent_conditions}},
                "columns": columns,
                "sort_by": [{"field": "started_at", "direction": "asc"}],
            }

            children = self._execute_query(query)
            all_traces.extend(children)

            # Set up next level
            current_parents = [c["id"] for c in children if c.get("id")]

        return {"traces": all_traces}

