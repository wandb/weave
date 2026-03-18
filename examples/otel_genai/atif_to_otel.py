"""atif_to_otel.py — Convert ATIF trajectory format to OTel GenAI span dicts.

ATIF (Agent Trajectory Interchange Format) uses a flat ordered steps array.
OTel GenAI uses a span tree with parent_span_id links. This module converts
an ATIF trajectory into a list of OTel GenAI span dicts that match the schema
expected by Weave's genai_spans table.

Mapping:
  ATIF session     → root invoke_agent span (covers the whole trajectory)
  ATIF agent step  → chat span (child of invoke_agent)
  ATIF tool_call   → execute_tool span (child of the chat span)
  ATIF system step → gen_ai.system_instructions on the invoke_agent span
  ATIF user step   → accumulated into the next chat span's input_messages

Fields that have no standard OTel GenAI convention are stored in the
span's ``attributes`` dict as custom attributes:

  metrics.cost_usd             → gen_ai.usage.cost_usd
  metrics.cached_tokens        → gen_ai.usage.cached_tokens
  step.reasoning_content       → gen_ai.response.reasoning_content
  step.reasoning_effort        → gen_ai.request.reasoning_effort
  metrics.logprobs             → gen_ai.response.logprobs (JSON string)
  metrics.completion_token_ids → gen_ai.response.completion_token_ids (JSON)
  metrics.prompt_token_ids     → gen_ai.response.prompt_token_ids (JSON)

Limitations vs. native OTel:
  - ATIF steps are sequential; parallel tool calls within a step share the
    same (start, end) times on their execute_tool spans.
  - ATIF has no span end times, so durations are synthesised from the gap
    between consecutive step timestamps (or DEFAULT_STEP_DURATION_MS).
  - Multi-agent ATIF trajectories linked via subagent_trajectory_ref are
    NOT followed by this converter — each file must be converted separately
    and the parent_span_id wired up manually if needed.

Usage:
    from atif_to_otel import atif_to_otel_spans

    with open("trajectory.json") as f:
        trajectory = json.load(f)

    spans = atif_to_otel_spans(trajectory)
    for span in spans:
        print(span["operation_name"], span["span_id"])
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

# Synthetic duration added to a step's start time when no next-step timestamp
# exists, giving that span a non-zero duration.
DEFAULT_STEP_DURATION_MS: int = 500


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _trace_id_from_session(session_id: str) -> str:
    """Derive a deterministic 32-hex-char trace ID from a session ID.

    Args:
        session_id (str): ATIF session identifier.

    Returns:
        str: 32-character hex string suitable for use as an OTel trace ID.

    Examples:
        >>> len(_trace_id_from_session("abc"))
        32
    """
    return hashlib.sha256(session_id.encode()).hexdigest()[:32]


def _span_id_from_seed(seed: str) -> str:
    """Derive a deterministic 16-hex-char span ID from an arbitrary seed.

    Args:
        seed (str): Unique seed string for this span.

    Returns:
        str: 16-character hex string suitable for use as an OTel span ID.

    Examples:
        >>> len(_span_id_from_seed("some:seed"))
        16
    """
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime.

    Args:
        ts (str | None): ISO 8601 string (e.g. "2025-10-11T10:30:00Z") or None.

    Returns:
        datetime | None: Parsed datetime, or None if input is None.

    Examples:
        >>> dt = _parse_timestamp("2025-10-11T10:30:00Z")
        >>> dt.year
        2025
        >>> _parse_timestamp(None) is None
        True
    """
    if ts is None:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _to_iso(dt: datetime) -> str:
    """Format a datetime as a millisecond-precision ISO 8601 UTC string.

    Args:
        dt (datetime): Datetime to format.

    Returns:
        str: ISO 8601 string ending in 'Z' with millisecond precision.

    Examples:
        >>> from datetime import timezone
        >>> dt = datetime(2025, 10, 11, 10, 30, 0, 123000, tzinfo=timezone.utc)
        >>> _to_iso(dt)
        '2025-10-11T10:30:00.123Z'
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _assign_step_times(
    steps: list[dict],
) -> tuple[list[datetime], list[datetime]]:
    """Assign start and end datetimes to each ATIF step.

    Steps with explicit timestamps use them; gaps between timestamps are
    divided evenly. Missing end times use DEFAULT_STEP_DURATION_MS.

    Args:
        steps (list[dict]): ATIF steps array.

    Returns:
        tuple[list[datetime], list[datetime]]: Parallel lists of (start, end)
            times for each step, with the same length as ``steps``.

    Examples:
        >>> starts, ends = _assign_step_times([{"timestamp": "2025-01-01T00:00:00Z"}])
        >>> starts[0].year
        2025
        >>> ends[0] > starts[0]
        True
    """
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    starts: list[datetime] = []
    current = base

    for step in steps:
        ts = _parse_timestamp(step.get("timestamp"))
        if ts is not None:
            current = ts
        starts.append(current)
        current = current + timedelta(milliseconds=DEFAULT_STEP_DURATION_MS)

    ends: list[datetime] = []
    for i, start in enumerate(starts):
        if i + 1 < len(starts):
            # Use the next step's start as this step's end (at minimum 1 ms)
            candidate = starts[i + 1]
            ends.append(candidate if candidate > start else start + timedelta(milliseconds=1))
        else:
            ends.append(start + timedelta(milliseconds=DEFAULT_STEP_DURATION_MS))

    return starts, ends


def _base_span(
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    span_name: str,
    started_at: datetime,
    ended_at: datetime,
) -> dict[str, Any]:
    """Build a span dict pre-populated with required fields set to safe defaults.

    Args:
        trace_id (str): 32-char hex trace ID.
        span_id (str): 16-char hex span ID.
        parent_span_id (str): 16-char hex parent span ID, or empty string for root.
        span_name (str): Human-readable span name.
        started_at (datetime): Span start time.
        ended_at (datetime): Span end time.

    Returns:
        dict[str, Any]: Span dict with all genai_spans fields at safe defaults.
    """
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "span_name": span_name,
        "span_kind": "CLIENT",
        "started_at": _to_iso(started_at),
        "ended_at": _to_iso(ended_at),
        "status_code": "OK",
        "status_message": "",
        "operation_name": "",
        "provider_name": "",
        "agent_name": "",
        "agent_id": "",
        "agent_description": "",
        "agent_version": "",
        "request_model": "",
        "response_model": "",
        "response_id": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "conversation_id": "",
        "tool_name": "",
        "tool_type": "",
        "tool_call_id": "",
        "tool_description": "",
        "tool_call_arguments": "",
        "tool_call_result": "",
        "finish_reasons": "[]",
        "request_temperature": None,
        "request_max_tokens": None,
        "request_top_p": None,
        "input_messages": "[]",
        "output_messages": "[]",
        "system_instructions": "",
        "tool_definitions": "",
        "attributes": {},
    }


def _message_to_str(message: str | list) -> str:
    """Normalise an ATIF message (string or ContentPart array) to a string.

    Args:
        message (str | list): ATIF message field value.

    Returns:
        str: Plain string or JSON-encoded ContentPart array.

    Examples:
        >>> _message_to_str("hello")
        'hello'
        >>> _message_to_str([{"type": "text", "text": "hi"}])
        '[{"type": "text", "text": "hi"}]'
    """
    if isinstance(message, str):
        return message
    return json.dumps(message)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def atif_to_otel_spans(trajectory: dict) -> list[dict[str, Any]]:
    """Convert an ATIF trajectory dict into a list of OTel GenAI span dicts.

    Each returned dict matches the column layout of Weave's ``genai_spans``
    table.  The list is ordered: root invoke_agent span first, then child
    spans in step order (chat spans before their execute_tool children).

    Args:
        trajectory (dict): Parsed ATIF trajectory document.  Must contain
            at minimum ``session_id`` and ``steps``.

    Returns:
        list[dict[str, Any]]: OTel GenAI span dicts.  The ``attributes``
            key on each dict holds custom attributes not yet part of the
            OTel GenAI semantic conventions.

    Examples:
        >>> traj = {
        ...     "schema_version": "ATIF-v1.5",
        ...     "session_id": "test-session",
        ...     "agent": {"name": "MyAgent", "version": "1.0"},
        ...     "steps": [
        ...         {"step_id": 1, "source": "user", "message": "Hello"},
        ...         {"step_id": 2, "source": "agent", "message": "Hi there"},
        ...     ],
        ... }
        >>> spans = atif_to_otel_spans(traj)
        >>> [s["operation_name"] for s in spans]
        ['invoke_agent', 'chat']
    """
    session_id: str = trajectory["session_id"]
    agent: dict = trajectory.get("agent") or {}
    steps: list[dict] = trajectory.get("steps") or []
    final_metrics: dict = trajectory.get("final_metrics") or {}

    trace_id = _trace_id_from_session(session_id)
    root_span_id = _span_id_from_seed(f"{session_id}:root")

    step_starts, step_ends = _assign_step_times(steps)

    # ------------------------------------------------------------------ #
    # Pass 1: gather system instructions from the first system step       #
    # ------------------------------------------------------------------ #
    system_instructions: str = ""
    for step in steps:
        if step.get("source") == "system":
            system_instructions = _message_to_str(step.get("message", ""))
            break

    # ------------------------------------------------------------------ #
    # Root invoke_agent span                                              #
    # ------------------------------------------------------------------ #
    root_start = step_starts[0] if step_starts else datetime(2025, 1, 1, tzinfo=timezone.utc)
    root_end = step_ends[-1] if step_ends else root_start + timedelta(seconds=1)

    root = _base_span(trace_id, root_span_id, "", f"invoke_agent {agent.get('name', 'agent')}", root_start, root_end)
    root.update(
        {
            "operation_name": "invoke_agent",
            "agent_name": agent.get("name", ""),
            "agent_version": agent.get("version", ""),
            "request_model": agent.get("model_name", ""),
            "conversation_id": session_id,
            "system_instructions": system_instructions,
            "tool_definitions": json.dumps(agent.get("tool_definitions") or []),
        }
    )

    # Aggregate token counts and cost from final_metrics
    if final_metrics:
        root["input_tokens"] = int(final_metrics.get("total_prompt_tokens") or 0)
        root["output_tokens"] = int(final_metrics.get("total_completion_tokens") or 0)
        root["total_tokens"] = root["input_tokens"] + root["output_tokens"]
        if final_metrics.get("total_cost_usd") is not None:
            root["attributes"]["gen_ai.usage.cost_usd"] = final_metrics["total_cost_usd"]
        if final_metrics.get("total_cached_tokens") is not None:
            root["attributes"]["gen_ai.usage.cached_tokens"] = final_metrics["total_cached_tokens"]

    root["attributes"]["atif.schema_version"] = trajectory.get("schema_version", "")
    root["attributes"]["atif.session_id"] = session_id

    spans: list[dict[str, Any]] = [root]

    # ------------------------------------------------------------------ #
    # Pass 2: per-step spans                                              #
    # ------------------------------------------------------------------ #
    pending_user_messages: list[dict] = []

    for idx, step in enumerate(steps):
        source: str = step.get("source", "")
        step_start = step_starts[idx]
        step_end = step_ends[idx]

        if source == "system":
            # Already consumed above.
            continue

        if source == "user":
            pending_user_messages.append(
                {
                    "role": "user",
                    "content": _message_to_str(step.get("message", "")),
                }
            )
            continue

        if source != "agent":
            # Unknown source; skip gracefully.
            continue

        # ---- chat span ------------------------------------------------ #
        step_key = step.get("step_id", idx)
        chat_span_id = _span_id_from_seed(f"{session_id}:step:{step_key}")
        metrics: dict = step.get("metrics") or {}
        tool_calls: list[dict] = step.get("tool_calls") or []
        observation: dict = step.get("observation") or {}
        obs_results: list[dict] = observation.get("results") or []
        model_name: str = step.get("model_name") or agent.get("model_name", "")

        input_msgs = list(pending_user_messages)
        pending_user_messages = []

        raw_msg = step.get("message", "")
        output_msgs = [{"role": "assistant", "content": _message_to_str(raw_msg)}] if raw_msg else []

        input_tokens = int(metrics.get("prompt_tokens") or 0)
        output_tokens = int(metrics.get("completion_tokens") or 0)

        chat_attrs: dict[str, Any] = {"atif.step_id": step_key}

        # Map ATIF-specific fields to proposed OTel custom attributes.
        if step.get("reasoning_content"):
            chat_attrs["gen_ai.response.reasoning_content"] = step["reasoning_content"]
        if step.get("reasoning_effort") is not None:
            chat_attrs["gen_ai.request.reasoning_effort"] = str(step["reasoning_effort"])
        if metrics.get("cost_usd") is not None:
            chat_attrs["gen_ai.usage.cost_usd"] = metrics["cost_usd"]
        if metrics.get("cached_tokens") is not None:
            chat_attrs["gen_ai.usage.cached_tokens"] = metrics["cached_tokens"]
        if metrics.get("logprobs") is not None:
            chat_attrs["gen_ai.response.logprobs"] = json.dumps(metrics["logprobs"])
        if metrics.get("completion_token_ids") is not None:
            chat_attrs["gen_ai.response.completion_token_ids"] = json.dumps(
                metrics["completion_token_ids"]
            )
        if metrics.get("prompt_token_ids") is not None:
            chat_attrs["gen_ai.response.prompt_token_ids"] = json.dumps(metrics["prompt_token_ids"])

        chat = _base_span(trace_id, chat_span_id, root_span_id, "chat", step_start, step_end)
        chat.update(
            {
                "operation_name": "chat",
                "agent_name": agent.get("name", ""),
                "agent_version": agent.get("version", ""),
                "request_model": model_name,
                "response_model": model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "conversation_id": session_id,
                "input_messages": json.dumps(input_msgs),
                "output_messages": json.dumps(output_msgs),
                "attributes": chat_attrs,
            }
        )
        spans.append(chat)

        # ---- execute_tool child spans --------------------------------- #
        obs_by_call_id: dict[str, Any] = {
            r["source_call_id"]: r.get("content", "")
            for r in obs_results
            if r.get("source_call_id")
        }

        for tc_idx, tc in enumerate(tool_calls):
            tc_key = tc.get("tool_call_id", f"tc{tc_idx}")
            tc_span_id = _span_id_from_seed(f"{session_id}:step:{step_key}:tc:{tc_key}")

            result_raw = obs_by_call_id.get(tc_key, "")
            result_str = result_raw if isinstance(result_raw, str) else json.dumps(result_raw)

            tc_span = _base_span(
                trace_id,
                tc_span_id,
                chat_span_id,
                f"execute_tool {tc.get('function_name', '')}",
                step_start,
                step_end,
            )
            tc_span.update(
                {
                    "operation_name": "execute_tool",
                    "agent_name": agent.get("name", ""),
                    "agent_version": agent.get("version", ""),
                    "conversation_id": session_id,
                    "tool_name": tc.get("function_name", ""),
                    "tool_type": "function",
                    "tool_call_id": tc_key,
                    "tool_call_arguments": json.dumps(tc.get("arguments") or {}),
                    "tool_call_result": result_str,
                    "attributes": {"atif.step_id": step_key, "atif.tool_call_id": tc_key},
                }
            )
            spans.append(tc_span)

    return spans


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python atif_to_otel.py <trajectory.json>")
        sys.exit(1)

    with open(sys.argv[1]) as fh:
        traj = json.load(fh)

    result = atif_to_otel_spans(traj)
    print(json.dumps(result, indent=2))
