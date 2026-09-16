"""SQL helpers for conversation filters backed by Insights tables."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.types import AgentInsightFilter
from weave.trace_server.orm import ParamBuilder


def build_insight_filter_clause(
    pb: ParamBuilder,
    project_id: str,
    insight_filters: list[AgentInsightFilter],
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    conversation_col: str = "s.conversation_id",
) -> str | None:
    """Match conversations carrying every requested Insights filter.

    The request's span window also bounds matching Insights turns. Cluster IDs
    are resolved only against the latest successful run for their signature type.
    """
    if not insight_filters:
        return None

    clauses = [
        _single_insight_filter_clause(
            pb,
            project_id,
            insight_filter,
            started_after,
            started_before,
            conversation_col,
        )
        for insight_filter in insight_filters
    ]
    return " AND ".join(clauses)


def _single_insight_filter_clause(
    pb: ParamBuilder,
    project_id: str,
    insight_filter: AgentInsightFilter,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    conversation_col: str,
) -> str:
    pid_slot = pb.add(project_id, param_type="String")
    values_slot = pb.add(insight_filter.values, param_type="Array(String)")
    conditions = [f"project_id = {pid_slot}", "conversation_id != ''"]

    if started_after is not None:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at >= {after_slot}")
    if started_before is not None:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at < {before_slot}")

    if insight_filter.field == "cluster":
        signature_type = insight_filter.signature_type
        conditions.extend(
            [
                f"signature_type = '{signature_type}'",
                "cluster_run_id = ("
                "SELECT id FROM signature_cluster_runs "
                f"WHERE project_id = {pid_slot} "
                f"AND signature_type = '{signature_type}' "
                "AND status = 'succeeded' "
                "ORDER BY window_end DESC, completed_at DESC, id DESC LIMIT 1)",
                f"toString(cluster_id) IN {values_slot}",
            ]
        )
        table = "signature_cluster_assignments"
    else:
        table = f"{insight_filter.signature_type}_signatures"
        if insight_filter.field == "category":
            conditions.append(f"category IN {values_slot}")
        else:
            conditions.append(
                "if(empty(trimBoth(severity)), 'unknown', lower(severity)) "
                f"IN {values_slot}"
            )

    operator = "NOT IN" if insight_filter.exclude else "IN"
    return (
        f"{conversation_col} {operator} (SELECT conversation_id FROM {table} "
        f"WHERE {' AND '.join(conditions)} GROUP BY conversation_id)"
    )
