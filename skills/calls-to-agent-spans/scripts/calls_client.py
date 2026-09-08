"""Fetch calls from the trace server."""

from __future__ import annotations

import json

import requests
from payload_paths import Row
from span_builder import op_short, tool_ops


def fetch_calls(
    session: requests.Session,
    base_url: str,
    project: str,
    after: str,
    before: str,
    columns: list[str] | None,
    roots_only: bool = False,
    op_names: list[str] | None = None,
    max_rows: int | None = None,
) -> list[Row]:
    """Every call in the window, roots and children alike, so the trace tree survives."""
    terms: list[dict[str, object]] = [
        {"$gt": [{"$getField": "started_at"}, {"$literal": after}]}
    ]
    if before:
        terms.append({"$lt": [{"$getField": "started_at"}, {"$literal": before}]})
    calls: list[Row] = []
    offset = 0
    while True:
        body: dict[str, object] = {
            "project_id": project,
            "query": {"$expr": {"$and": terms} if len(terms) > 1 else terms[0]},
            "limit": min(PAGE_SIZE, max_rows) if max_rows else PAGE_SIZE,
            "offset": offset,
            "sort_by": [{"field": "started_at", "direction": "asc"}],
        }
        if columns:
            body["columns"] = columns
        if roots_only:
            body["filter"] = {"trace_roots_only": True}
        if op_names:
            body["filter"] = {"op_names": op_names}
        response = session.post(
            f"{base_url}/calls/stream_query", json=body, timeout=TIMEOUT, stream=True
        )
        response.raise_for_status()
        page = [json.loads(line) for line in response.iter_lines() if line.strip()]
        calls.extend(row for row in page if isinstance(row, dict))
        offset += len(page)
        if len(page) < PAGE_SIZE or (max_rows and len(calls) >= max_rows):
            return calls


def attach_tool_payloads(
    session: requests.Session,
    base_url: str,
    project: str,
    window: tuple[str, str],
    calls: list[Row],
) -> None:
    """Give tool calls their real arguments and result, in a second pass narrowed to those ops.

    A root call can carry the whole conversation history in `inputs`, so asking for that field
    across every call is what makes a naive fetch enormous. Tool calls are leaves and small.
    """
    tools = tool_ops(calls)
    refs = sorted({str(call["op_name"]) for call in calls if op_short(call) in tools})
    if not refs:
        return
    rows = fetch_calls(
        session, base_url, project, *window, ["id", "inputs", "output"], op_names=refs
    )
    payloads = {str(row.get("id")): row for row in rows}
    for call in calls:
        payload = payloads.get(str(call.get("id")))
        if payload:
            call["inputs"] = payload.get("inputs")
            call["output"] = payload.get("output")


def span_count(session: requests.Session, base_url: str, project: str) -> int:
    """How many agent spans the target already has. Used to refuse a non-empty project."""
    response = session.post(
        f"{base_url}/agents/spans/query",
        json={"project_id": project, "limit": 1},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    return int(body.get("total_count") or 0)


DEFAULT_BASE_URL = "https://trace.wandb.ai"

PAGE_SIZE = 1_000

TIMEOUT = 120

DETECTION_SAMPLE = 25

# `output.model` and `output.usage` decide what a call *is*, so they are never optional.
BASE_COLUMNS = [
    "id",
    "trace_id",
    "parent_id",
    "op_name",
    "started_at",
    "ended_at",
    "exception",
    "output.model",
    "inputs.model",
    "output.usage",
]
