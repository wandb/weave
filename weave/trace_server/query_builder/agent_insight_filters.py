"""SQL helpers for entity filters backed by Insights tables."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.types import (
    INTENT_SIGNATURE_FIELDS,
    TOPIC_INSIGHT_FIELDS,
    AgentInsightFilter,
    AgentInsightFilterScope,
    AgentSignatureType,
)
from weave.trace_server.orm import ParamBuilder

# Runs that predate topic reconciliation left topic_id at the UUID default.
NIL_TOPIC_ID = "toUUID('00000000-0000-0000-0000-000000000000')"
# window_end sorts first so a backfill over old dates cannot outrank newer coverage.
SUCCEEDED_RUNS_BY_RECENCY = (
    "arraySort(run -> tuple(run.2, run.3, run.4), "
    "groupArray(tuple(window_start, window_end, inserted_at, id)))"
)
# No covering run yields the zero tuple, so cluster_run_id compares to the nil UUID.
COVERING_RUN_ID = (
    "tupleElement(arrayLast(run -> run.1 <= trace_started_at "
    "AND trace_started_at < run.2, succeeded_runs_by_recency), 4)"
)


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
    IDs are resolved per turn through the newest successful run covering it.
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
    operator = "NOT IN" if insight_filter.exclude else "IN"
    span_entity_column = "s.trace_id" if scope == "turn" else "s.conversation_id"
    signature_entity_column = "trace_id" if scope == "turn" else "conversation_id"
    conditions = _turn_conditions(
        pb,
        pid_slot,
        started_after,
        started_before,
        signature_entity_column,
    )

    if insight_filter.field in TOPIC_INSIGHT_FIELDS:
        signature_type: AgentSignatureType = (
            "intent" if insight_filter.field == "intent_topic_id" else "failure"
        )
        if scope == "turn" and signature_type == "failure":
            signature_ids = _topic_assignments_subquery(
                pid_slot,
                values_slot,
                signature_type,
                conditions,
                "signature_record_id",
            )
            failure_conditions = [*conditions]
            failure_conditions[1] = "affected_trace_id != ''"
            failure_conditions.append(f"id IN ({signature_ids})")
            subquery = (
                "SELECT affected_trace_id FROM failure_signatures "
                "ARRAY JOIN affected_trace_ids AS affected_trace_id "
                f"WHERE {' AND '.join(failure_conditions)} "
                "GROUP BY affected_trace_id"
            )
        else:
            subquery = _topic_assignments_subquery(
                pid_slot,
                values_slot,
                signature_type,
                conditions,
                signature_entity_column,
            )
        return f"{span_entity_column} {operator} ({subquery})"

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

    if scope == "turn" and table == "failure_signatures":
        signature_entity_column = "affected_trace_id"
        conditions[1] = "affected_trace_id != ''"
        table += " ARRAY JOIN affected_trace_ids AS affected_trace_id"

    return (
        f"{span_entity_column} {operator} (SELECT {signature_entity_column} "
        f"FROM {table} WHERE {' AND '.join(conditions)} "
        f"GROUP BY {signature_entity_column})"
    )


def _turn_conditions(
    pb: ParamBuilder,
    pid_slot: str,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    entity_column: str,
) -> list[str]:
    """Scope Insights turns to the project and the request's span window."""
    conditions = [f"project_id = {pid_slot}", f"{entity_column} != ''"]

    if started_after is not None:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at >= {after_slot}")
    if started_before is not None:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at < {before_slot}")

    return conditions


def _topic_assignments_subquery(
    pid_slot: str,
    values_slot: str,
    signature_type: AgentSignatureType,
    conditions: list[str],
    result_column: str,
) -> str:
    """Entities whose newest covering run files the turn under a requested topic.

    Only the assignment rows of matching clusters are read, pruned through the
    (project_id, cluster_run_id) sort key. A turn the newest covering run left
    unclustered has no matching row and so matches no topic; a turn no succeeded
    run covers resolves to the nil run id and matches nothing.
    """
    succeeded_runs = (
        "SELECT window_start, window_end, inserted_at, id "
        f"FROM signature_cluster_runs WHERE project_id = {pid_slot} "
        f"AND signature_type = '{signature_type}' AND status = 'succeeded'"
    )
    matching_clusters = (
        "SELECT cluster_run_id, id FROM signature_clusters "
        f"WHERE project_id = {pid_slot} AND signature_type = '{signature_type}' "
        "AND cluster_run_id IN (SELECT id FROM succeeded_runs) "
        f"AND topic_id != {NIL_TOPIC_ID} "
        f"AND toString(topic_id) IN {values_slot}"
    )
    assignment_conditions = [
        *conditions,
        f"signature_type = '{signature_type}'",
        f"(cluster_run_id, cluster_id) IN ({matching_clusters})",
        f"cluster_run_id = {COVERING_RUN_ID}",
    ]

    return (
        f"WITH succeeded_runs AS ({succeeded_runs}), "
        f"(SELECT {SUCCEEDED_RUNS_BY_RECENCY} FROM succeeded_runs) "
        "AS succeeded_runs_by_recency "
        f"SELECT {result_column} FROM signature_cluster_assignments "
        f"WHERE {' AND '.join(assignment_conditions)} GROUP BY {result_column}"
    )
