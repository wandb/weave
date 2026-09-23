"""SQL helpers for entity filters backed by Insights tables."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

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


@dataclass(frozen=True)
class _InsightFilterContext:
    """Reuse one filter's slots when failure topics require nested subqueries."""

    project_id_slot: str
    started_after_slot: str | None
    started_before_slot: str | None

    def conditions_for(self, entity_column: str) -> list[str]:
        conditions = [
            f"project_id = {self.project_id_slot}",
            f"{entity_column} != ''",
        ]
        if self.started_after_slot is not None:
            conditions.append(f"trace_started_at >= {self.started_after_slot}")
        if self.started_before_slot is not None:
            conditions.append(f"trace_started_at < {self.started_before_slot}")
        return conditions


@dataclass(frozen=True)
class _SignatureEntitySource:
    from_expression: str
    entity_column: str


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
    context = _insight_filter_context(
        pb,
        pid_slot,
        started_after,
        started_before,
    )
    operator = "NOT IN" if insight_filter.exclude else "IN"
    span_entity_column = "s.trace_id" if scope == "turn" else "s.conversation_id"

    if insight_filter.field in TOPIC_INSIGHT_FIELDS:
        signature_type: AgentSignatureType = (
            "intent" if insight_filter.field == "intent_topic_id" else "failure"
        )
        subquery = _topic_entities_subquery(
            context,
            values_slot,
            signature_type,
            scope,
        )
    else:
        subquery = _signature_entities_subquery(
            context,
            values_slot,
            insight_filter.field,
            scope,
        )

    return f"{span_entity_column} {operator} ({subquery})"


def _insight_filter_context(
    pb: ParamBuilder,
    project_id_slot: str,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
) -> _InsightFilterContext:
    return _InsightFilterContext(
        project_id_slot=project_id_slot,
        started_after_slot=(
            pb.add(started_after, param_type="DateTime64(6)")
            if started_after is not None
            else None
        ),
        started_before_slot=(
            pb.add(started_before, param_type="DateTime64(6)")
            if started_before is not None
            else None
        ),
    )


def _signature_entities_subquery(
    context: _InsightFilterContext,
    values_slot: str,
    field: str,
    scope: AgentInsightFilterScope,
) -> str:
    signature_type: AgentSignatureType = (
        "intent" if field in INTENT_SIGNATURE_FIELDS else "failure"
    )
    source = _signature_entity_source(signature_type, scope)
    conditions = context.conditions_for(source.entity_column)
    conditions.append(_signature_value_condition(field, values_slot))

    return (
        f"SELECT {source.entity_column} FROM {source.from_expression} "
        f"WHERE {' AND '.join(conditions)} GROUP BY {source.entity_column}"
    )


def _signature_entity_source(
    signature_type: AgentSignatureType,
    scope: AgentInsightFilterScope,
) -> _SignatureEntitySource:
    if scope == "conversation":
        return _SignatureEntitySource(
            from_expression=f"{signature_type}_signatures",
            entity_column="conversation_id",
        )
    if signature_type == "intent":
        return _SignatureEntitySource(
            from_expression="intent_signatures",
            entity_column="trace_id",
        )

    # A failure signature may cover several turns, not just its current trace.
    return _SignatureEntitySource(
        from_expression=(
            "failure_signatures ARRAY JOIN affected_trace_ids AS affected_trace_id"
        ),
        entity_column="affected_trace_id",
    )


def _signature_value_condition(field: str, values_slot: str) -> str:
    if field == "intent_sentiment":
        return f"sentiment IN {values_slot}"
    if field == "failure_severity":
        return (
            "if(empty(trimBoth(severity)), 'unknown', lower(trimBoth(severity))) "
            f"IN {values_slot}"
        )
    return f"category IN {values_slot}"


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


def _topic_entities_subquery(
    context: _InsightFilterContext,
    values_slot: str,
    signature_type: AgentSignatureType,
    scope: AgentInsightFilterScope,
) -> str:
    if scope == "conversation":
        result_column = "conversation_id"
    elif signature_type == "intent":
        result_column = "trace_id"
    else:
        # Cluster assignments identify a failure by its current trace, but the
        # failure may cover several turns. Resolve matching failure records first,
        # then expand each record's affected traces.
        signature_ids = _topic_assignments_subquery(
            context.project_id_slot,
            values_slot,
            signature_type,
            context.conditions_for("trace_id"),
            "signature_record_id",
        )
        failure_conditions = context.conditions_for("affected_trace_id")
        failure_conditions.append(f"id IN ({signature_ids})")
        return (
            "SELECT affected_trace_id FROM failure_signatures "
            "ARRAY JOIN affected_trace_ids AS affected_trace_id "
            f"WHERE {' AND '.join(failure_conditions)} "
            "GROUP BY affected_trace_id"
        )

    return _topic_assignments_subquery(
        context.project_id_slot,
        values_slot,
        signature_type,
        context.conditions_for(result_column),
        result_column,
    )
