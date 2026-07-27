"""In-memory store for captured calls. Project-id scoped so concurrent tests
running with different project_ids don't see each other's data.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any


class CallStore:
    """In-memory call capture, partitioned by project_id.

    Calls are stored in a per-project dict keyed by call id; start/end events
    for the same call_id are merged on `add_end()`. The captured shape mirrors
    the production CallSchema closely enough for assertion purposes — the SDK
    sends real `tsi.StartedCallSchemaForInsert` / `tsi.EndedCallSchemaForInsert`
    payloads via the production wrapper types, and we project the relevant
    fields into a single dict per call.
    """

    def __init__(self) -> None:
        self._calls: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._lock = Lock()

    def add_start(self, payload: dict[str, Any]) -> None:
        """Record a call-start payload."""
        project_id = payload.get("project_id", "<unknown>")
        call_id = payload.get("id", "<unknown>")
        with self._lock:
            existing = self._calls[project_id].get(call_id, {})
            existing.update(payload)
            self._calls[project_id][call_id] = existing

    def add_end(self, payload: dict[str, Any]) -> None:
        """Record a call-end payload, merging into any existing start record."""
        project_id = payload.get("project_id", "<unknown>")
        call_id = payload.get("id", "<unknown>")
        with self._lock:
            existing = self._calls[project_id].get(call_id, {})
            existing.update(payload)
            self._calls[project_id][call_id] = existing

    def add_complete(self, payload: dict[str, Any]) -> None:
        """Record a completed call (start + end fields together)."""
        project_id = payload.get("project_id", "<unknown>")
        call_id = payload.get("id", "<unknown>")
        with self._lock:
            existing = self._calls[project_id].get(call_id, {})
            existing.update(payload)
            self._calls[project_id][call_id] = existing

    def get_calls(self, project_id: str) -> list[dict[str, Any]]:
        """Return all captured calls for a project, in insertion order."""
        with self._lock:
            return list(self._calls.get(project_id, {}).values())

    def reset(self, project_id: str | None = None) -> None:
        """Clear all calls (or just one project's calls if specified)."""
        with self._lock:
            if project_id is None:
                self._calls.clear()
            else:
                self._calls.pop(project_id, None)
