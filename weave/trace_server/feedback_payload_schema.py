"""Feedback payload schema discovery from sample rows."""

from __future__ import annotations

import datetime
import json
import logging
from collections import defaultdict
from typing import Any

from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.feedback_stats_query_builder import (
    JSON_PATH_PATTERN,
    trigger_ref_where_clause,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    FeedbackPayloadPath,
    FeedbackPayloadSchemaReq,
)

logger = logging.getLogger(__name__)

_SAMPLE_LIMIT = 5000


def _discover_paths(obj: Any, prefix: str = "") -> dict[str, set[type]]:
    """Recursively discover leaf paths and collect value types.

    Returns:
        Mapping from dot path to set of Python types seen at that path.
    """
    out: dict[str, set[type]] = defaultdict(set)
    if obj is None:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or "." in k or not k.strip():
                continue
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)) and v is not None:
                out.update(_discover_paths(v, path))
            else:
                out[path].add(type(v))
        return out
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)) and v is not None:
                out.update(_discover_paths(v, f"{prefix}[{i}]"))
            else:
                out[prefix].add(type(v))
        return out
    out[prefix].add(type(obj))
    return out


def _infer_value_type(types_seen: set[type]) -> str:
    """Infer value_type from observed Python types."""
    if not types_seen:
        return "numeric"
    # bool must be checked before int (bool is subclass of int)
    if types_seen <= {bool, type(None)}:
        return "boolean"
    if types_seen <= {int, float, type(None)}:
        return "numeric"
    return "categorical"


def discover_payload_schema(payload_strs: list[str]) -> list[FeedbackPayloadPath]:
    """Discover schema from raw payload JSON strings.

    Parses each string as JSON, recursively discovers leaf paths, infers
    value_type from observed types, and returns unique paths.

    Args:
        payload_strs: List of JSON strings (payload_dump from feedback rows).

    Returns:
        Sorted list of FeedbackPayloadPath, deduplicated by json_path.

    Examples:
        >>> discover_payload_schema(['{"output": {"score": 0.9}}'])
        [FeedbackPayloadPath(json_path='output.score', value_type='numeric')]
    """
    path_to_types: dict[str, set[type]] = defaultdict(set)
    for s in payload_strs:
        if not s or not s.strip():
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        for path, types in _discover_paths(obj).items():
            # Skip array-index paths like "a[0]" for schema output
            if "[" in path:
                continue
            # Skip paths with chars not allowed by feedback_stats (e.g. spaces)
            if not JSON_PATH_PATTERN.match(path):
                continue
            path_to_types[path].update(types)

    result: list[FeedbackPayloadPath] = []
    for path in sorted(path_to_types.keys()):
        value_type = _infer_value_type(path_to_types[path])
        result.append(FeedbackPayloadPath(json_path=path, value_type=value_type))
    return result


def build_feedback_payload_sample_query(
    req: FeedbackPayloadSchemaReq,
    pb: ParamBuilder,
) -> tuple[str, dict[str, Any]]:
    """Build parameterized ClickHouse SQL to fetch sample payload_dump.

    Uses same filters as feedback_stats (project_id, created_at, feedback_type,
    trigger_ref). Returns one payload per unique trigger_ref (most recent per
    ref), since each trigger_ref has a unique payload schema.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start = req.start
    end = req.end if req.end is not None else now_utc
    limit = min(req.sample_limit, _SAMPLE_LIMIT)

    project_param = pb.add_param(req.project_id)
    start_epoch = start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    limit_param = pb.add_param(limit)

    where_clauses: list[str] = [
        f"project_id = {param_slot(project_param, 'String')}",
        f"created_at >= toDateTime({param_slot(start_param, 'Float64')}, 'UTC')",
        f"created_at < toDateTime({param_slot(end_param, 'Float64')}, 'UTC')",
        "payload_dump != ''",
        "payload_dump IS NOT NULL",
    ]
    if req.feedback_type is not None:
        feedback_type_param = pb.add_param(req.feedback_type)
        where_clauses.append(
            f"feedback_type = {param_slot(feedback_type_param, 'String')}"
        )
    if req.trigger_ref is not None:
        where_clauses.append(trigger_ref_where_clause(req.trigger_ref, pb))
    where_sql = " AND ".join(where_clauses)

    raw_sql = f"""
    SELECT argMax(payload_dump, created_at) AS payload_sample
    FROM feedback
    WHERE {where_sql}
    GROUP BY trigger_ref
    LIMIT {param_slot(limit_param, "Int64")}
    """
    return safely_format_sql(raw_sql, logger), pb.get_params()
