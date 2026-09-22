"""SQL helpers for conversation filters backed by Insights tables."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.types import AgentInsightFilter
from weave.trace_server.orm import ParamBuilder

TOPIC_FIELDS = {"intent_topic_id", "failure_topic_id"}
INTENT_SIGNATURE_FIELDS = {"intent_category", "intent_sentiment"}
# Runs that predate topic reconciliation left topic_id at the UUID default.
NIL_TOPIC_ID = "toUUID('00000000-0000-0000-0000-000000000000')"
# Successful runs sorted oldest to newest by window end, completion time, then id.
NEWEST_RUNS_ARRAY = (
    "arraySort(run -> tuple(run.2, run.3, run.4), "
    "groupArray(tuple(window_start, window_end, completed_at, id)))"
)
# The newest run whose window covers the turn decides the turn's topic.
COVERING_RUN_ID = (
    "tupleElement(arrayLast(run -> run.1 <= trace_started_at "
    "AND trace_started_at < run.2, newest_runs), 4)"
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
    conditions = _turn_conditions(pb, pid_slot, started_after, started_before)

    if insight_filter.field in TOPIC_FIELDS:
        signature_type = (
            "intent" if insight_filter.field == "intent_topic_id" else "failure"
        )
        subquery = _topic_conversations_subquery(
            pid_slot, values_slot, signature_type, conditions
        )

        return f"s.conversation_id {operator} ({subquery})"

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
) -> list[str]:
    """Scope Insights turns to the project and the request's span window."""
    conditions = [f"project_id = {pid_slot}", "conversation_id != ''"]

    if started_after is not None:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at >= {after_slot}")
    if started_before is not None:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"trace_started_at < {before_slot}")

    return conditions


def _topic_conversations_subquery(
    pid_slot: str,
    values_slot: str,
    signature_type: str,
    conditions: list[str],
) -> str:
    """Conversations with a turn its newest covering run files under a requested topic.

    Only the assignment rows of matching clusters are read, pruned through the
    (project_id, cluster_run_id) sort key. A turn the newest covering run left
    unclustered has no matching row and so matches no topic.
    """
    run_source = (
        f"FROM signature_cluster_runs WHERE project_id = {pid_slot} "
        f"AND signature_type = '{signature_type}' AND status = 'succeeded'"
    )
    succeeded_run_ids = f"SELECT id {run_source}"
    succeeded_runs = f"SELECT window_start, window_end, completed_at, id {run_source}"
    matching_clusters = (
        "SELECT cluster_run_id, id FROM signature_clusters "
        f"WHERE project_id = {pid_slot} AND signature_type = '{signature_type}' "
        f"AND cluster_run_id IN ({succeeded_run_ids}) "
        f"AND topic_id != {NIL_TOPIC_ID} "
        f"AND toString(topic_id) IN {values_slot}"
    )
    conditions = [
        *conditions,
        f"signature_type = '{signature_type}'",
        f"(cluster_run_id, cluster_id) IN ({matching_clusters})",
        f"cluster_run_id = {COVERING_RUN_ID}",
    ]

    return (
        f"WITH (SELECT {NEWEST_RUNS_ARRAY} FROM ({succeeded_runs})) AS newest_runs "
        "SELECT conversation_id FROM signature_cluster_assignments "
        f"WHERE {' AND '.join(conditions)} GROUP BY conversation_id"
    )
