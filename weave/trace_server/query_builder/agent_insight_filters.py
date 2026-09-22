"""SQL helpers for conversation filters backed by Insights tables."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.types import AgentInsightFilter
from weave.trace_server.orm import ParamBuilder

TOPIC_FIELDS = {"intent_topic_id", "failure_topic_id"}
INTENT_SIGNATURE_FIELDS = {"intent_category", "intent_sentiment"}
# Overlapping clustering runs each assign a turn; the newest run's topic wins.
NEWEST_RUN_ORDER = (
    "tuple(runs.window_end, runs.completed_at, assignments.cluster_run_id)"
)


def build_insight_filter_clause(
    pb: ParamBuilder,
    project_id: str,
    insight_filters: list[AgentInsightFilter],
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
) -> str | None:
    """Match conversations carrying every requested Insights filter.

    The request's span window also bounds matching Insights turns. Stable topic
    IDs are resolved per turn to the newest successful clustering run's topic.
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
) -> str:
    """Build one conversation-membership predicate from an Insights filter."""
    pid_slot = pb.add(project_id, param_type="String")
    values_slot = pb.add(insight_filter.values, param_type="Array(String)")
    operator = "NOT IN" if insight_filter.exclude else "IN"

    if insight_filter.field in TOPIC_FIELDS:
        signature_type = (
            "intent" if insight_filter.field == "intent_topic_id" else "failure"
        )
        conditions = _turn_conditions(
            pb, pid_slot, started_after, started_before, table="assignments"
        )
        subquery = _topic_conversations_subquery(
            pid_slot, values_slot, signature_type, conditions
        )

        return f"s.conversation_id {operator} ({subquery})"

    conditions = _turn_conditions(pb, pid_slot, started_after, started_before)
    if insight_filter.field in INTENT_SIGNATURE_FIELDS:
        table = "intent_signatures"
    else:
        table = "failure_signatures"

    if insight_filter.field == "intent_sentiment":
        conditions.append(f"sentiment IN {values_slot}")
    elif insight_filter.field != "failure_severity":
        conditions.append(f"category IN {values_slot}")
    else:
        conditions.append(
            "if(empty(trimBoth(severity)), 'unknown', lower(trimBoth(severity))) "
            f"IN {values_slot}"
        )

    return (
        f"s.conversation_id {operator} (SELECT conversation_id FROM {table} "
        f"WHERE {' AND '.join(conditions)} GROUP BY conversation_id)"
    )


def _turn_conditions(
    pb: ParamBuilder,
    pid_slot: str,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    table: str | None = None,
) -> list[str]:
    """Scope Insights turns to the project and the request's span window."""
    prefix = f"{table}." if table else ""
    conditions = [
        f"{prefix}project_id = {pid_slot}",
        f"{prefix}conversation_id != ''",
    ]

    if started_after is not None:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"{prefix}trace_started_at >= {after_slot}")
    if started_before is not None:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"{prefix}trace_started_at < {before_slot}")

    return conditions


def _topic_conversations_subquery(
    pid_slot: str,
    values_slot: str,
    signature_type: str,
    conditions: list[str],
) -> str:
    """Conversations with a turn whose newest-run topic is one of the requested topics."""
    conditions = [
        *conditions,
        f"assignments.signature_type = '{signature_type}'",
        f"clusters.project_id = {pid_slot}",
        f"clusters.signature_type = '{signature_type}'",
        f"runs.project_id = {pid_slot}",
        f"runs.signature_type = '{signature_type}'",
        "runs.status = 'succeeded'",
    ]

    return (
        "SELECT conversation_id FROM ("
        "SELECT any(assignments.conversation_id) AS conversation_id, "
        f"argMax(clusters.topic_id, {NEWEST_RUN_ORDER}) AS topic_id "
        "FROM signature_cluster_assignments AS assignments "
        "INNER JOIN signature_clusters AS clusters "
        "ON assignments.cluster_run_id = clusters.cluster_run_id "
        "AND assignments.cluster_id = clusters.id "
        "INNER JOIN signature_cluster_runs AS runs "
        "ON assignments.cluster_run_id = runs.id "
        f"WHERE {' AND '.join(conditions)} "
        "GROUP BY assignments.signature_record_id) "
        f"WHERE toString(topic_id) IN {values_slot} "
        "GROUP BY conversation_id"
    )
