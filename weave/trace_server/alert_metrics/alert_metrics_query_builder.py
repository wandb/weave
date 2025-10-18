from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface import query as tsi_query

"""Alert metrics query building utilities.

This module contains functions for building complex queries for alert metrics,
including filtering and condition construction.
"""


def build_alert_metrics_query_conditions(
    req: tsi.AlertMetricsQueryReq,
) -> tsi.Query | None:
    """Build query conditions for alert metrics filtering.

    Args:
        req: The alert metrics query request containing filter parameters.

    Returns:
        tsi.Query | None: Combined query conditions, or None if no filters applied.

    Examples:
        >>> req = AlertMetricsQueryReq(
        ...     project_id="test",
        ...     metric_keys=["accuracy", "latency"],
        ...     alert_ids=["alert1", "alert2"]
        ... )
        >>> query = build_alert_metrics_query_conditions(req)
        >>> assert query is not None
    """
    query_conditions = []

    if req.metric_keys:
        get_field = tsi_query.GetFieldOperator(**{"$getField": "metric_key"})
        key_literals = [
            tsi_query.LiteralOperation(**{"$literal": key}) for key in req.metric_keys
        ]
        in_op = tsi_query.InOperation(**{"$in": [get_field, key_literals]})
        query_conditions.append(tsi.Query(**{"$expr": in_op}))

    if req.alert_ids:
        get_field = tsi_query.GetFieldOperator(**{"$getField": "alert_ids"})
        id_literals = [
            tsi_query.LiteralOperation(**{"$literal": alert_id})
            for alert_id in req.alert_ids
        ]
        in_op = tsi_query.InOperation(**{"$in": [get_field, id_literals]})
        query_conditions.append(tsi.Query(**{"$expr": in_op}))

    if req.end_time:
        time_literal = tsi_query.LiteralOperation(**{"$literal": req.end_time})
        created_at = tsi_query.GetFieldOperator(**{"$getField": "created_at"})
        gte_op = tsi_query.GteOperation(**{"$gte": [time_literal, created_at]})
        query_conditions.append(tsi.Query(**{"$expr": gte_op}))

    # Combine all conditions with AND
    if len(query_conditions) == 1:
        return query_conditions[0]
    elif len(query_conditions) > 1:
        and_op = tsi_query.AndOperation(
            **{"$and": [cond.expr_ for cond in query_conditions]}
        )
        return tsi.Query(**{"$expr": and_op})
    else:
        return None
