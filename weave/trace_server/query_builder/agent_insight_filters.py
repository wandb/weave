"""SQL helpers for entity filters backed by Insights tables."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.types import AgentInsightFilter, AgentInsightFilterScope
from weave.trace_server.orm import ParamBuilder


def build_insight_filter_clause(
    pb: ParamBuilder,
    project_id: str,
    insight_filters: list[AgentInsightFilter],
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    scope: AgentInsightFilterScope = "conversation",
) -> str | None:
    """Match entities carrying every requested Insights filter.

    The request's span window also bounds matching Insights turns. Stable topic
    IDs are resolved to concrete clusters across successful clustering runs.
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
            scope,
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
    scope: AgentInsightFilterScope,
) -> str:
    """Build one entity-membership predicate from an Insights filter."""
    pid_slot = pb.add(project_id, param_type="String")
    values_slot = pb.add(insight_filter.values, param_type="Array(String)")
    span_entity_column = "s.trace_id" if scope == "turn" else "s.conversation_id"
    signature_entity_column = "trace_id" if scope == "turn" else "conversation_id"
    conditions = [
        f"project_id = {pid_slot}",
        f"{signature_entity_column} != ''",
    ]

    if started_after is not None:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at >= {after_slot}")
    if started_before is not None:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at < {before_slot}")

    if insight_filter.field in {"intent_topic_id", "failure_topic_id"}:
        signature_type = (
            "intent" if insight_filter.field == "intent_topic_id" else "failure"
        )
        if scope == "turn" and signature_type == "failure":
            conditions[1] = "affected_trace_id != ''"
            return _failure_topic_turn_filter_clause(
                pid_slot,
                values_slot,
                insight_filter.exclude,
                conditions,
            )
        conditions.extend(
            [
                f"signature_type = '{signature_type}'",
                "(cluster_run_id, cluster_id) IN ("
                "SELECT cluster_run_id, id FROM signature_clusters "
                f"WHERE project_id = {pid_slot} "
                f"AND signature_type = '{signature_type}' "
                "AND cluster_run_id IN (SELECT id FROM signature_cluster_runs "
                f"WHERE project_id = {pid_slot} "
                f"AND signature_type = '{signature_type}' "
                "AND status = 'succeeded') "
                f"AND toString(topic_id) IN {values_slot})",
            ]
        )
        table = "signature_cluster_assignments"
    else:
        table = (
            "intent_signatures"
            if insight_filter.field in {"intent_category", "intent_sentiment"}
            else "failure_signatures"
        )
        if insight_filter.field == "intent_sentiment":
            conditions.append(f"sentiment IN {values_slot}")
        elif insight_filter.field != "failure_severity":
            conditions.append(f"category IN {values_slot}")
        else:
            conditions.append(
                "if(empty(trimBoth(severity)), 'unknown', lower(trimBoth(severity))) "
                f"IN {values_slot}"
            )
        if scope == "turn" and table == "failure_signatures":
            signature_entity_column = "affected_trace_id"
            conditions[1] = "affected_trace_id != ''"
            table += " ARRAY JOIN affected_trace_ids AS affected_trace_id"

    operator = "NOT IN" if insight_filter.exclude else "IN"
    return (
        f"{span_entity_column} {operator} (SELECT {signature_entity_column} "
        f"FROM {table} WHERE {' AND '.join(conditions)} "
        f"GROUP BY {signature_entity_column})"
    )


def _failure_topic_turn_filter_clause(
    pid_slot: str,
    values_slot: str,
    exclude: bool,
    conditions: list[str],
) -> str:
    conditions.append(
        "id IN (SELECT signature_record_id FROM signature_cluster_assignments "
        f"WHERE project_id = {pid_slot} AND signature_type = 'failure' "
        "AND (cluster_run_id, cluster_id) IN ("
        "SELECT cluster_run_id, id FROM signature_clusters "
        f"WHERE project_id = {pid_slot} AND signature_type = 'failure' "
        "AND cluster_run_id IN (SELECT id FROM signature_cluster_runs "
        f"WHERE project_id = {pid_slot} AND signature_type = 'failure' "
        "AND status = 'succeeded') "
        f"AND toString(topic_id) IN {values_slot}))"
    )
    operator = "NOT IN" if exclude else "IN"
    return (
        f"s.trace_id {operator} (SELECT affected_trace_id FROM failure_signatures "
        "ARRAY JOIN affected_trace_ids AS affected_trace_id "
        f"WHERE {' AND '.join(conditions)} GROUP BY affected_trace_id)"
    )
