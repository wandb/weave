"""Weave client for fetching trace data."""

import base64
import json
import os
import time
from dataclasses import dataclass
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

        query: dict[str, Any] = {
            "project_id": f"{self.config.entity}/{self.config.project}",
            "filter": {},
            "columns": columns,
            "sort_by": [{"field": "started_at", "direction": "asc"}],
        }

        expr_conditions = []

        # Add root traces filter
        if trace_roots_only:
            expr_conditions.append({
                "$eq": [
                    {"$getField": "parent_id"},
                    {"$literal": None}
                ]
            })

        # Convert Weave UI filters to API format
        if filters:
            filter_items = filters.get("items", [])
            for item in filter_items:
                field = item.get("field")
                operator = item.get("operator", "")
                value = item.get("value")

                condition = self._convert_filter_item(field, operator, value)
                if condition:
                    expr_conditions.append(condition)

        if expr_conditions:
            query["query"] = {"$expr": {"$and": expr_conditions}}

        if limit:
            query["limit"] = limit

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
        # Default equality
        return {
            "$eq": [
                {"$getField": field},
                {"$literal": value}
            ]
        }

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

