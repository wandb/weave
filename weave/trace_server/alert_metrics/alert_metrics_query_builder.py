"""Alert metrics query building utilities.

This module contains functions for building complex queries for alert metrics,
including filtering and condition construction.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def build_alert_metrics_query_conditions(
    req: Any,  # tsi.AlertMetricsQueryReq - avoid circular import
) -> Any:  # tsi.Query | None
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
    # Import at runtime to avoid circular imports
    from weave.trace_server import trace_server_interface as tsi
    from weave.trace_server.interface import query as tsi_query

    query_conditions = []

    if req.metric_keys:
        # Create IN operation for metric_keys
        in_op = tsi_query.InOperation(
            **{
                "$in": [
                    tsi_query.GetFieldOperator(**{"$getField": "metric_key"}),
                    [
                        tsi_query.LiteralOperation(**{"$literal": key})
                        for key in req.metric_keys
                    ],
                ]
            }
        )
        query_conditions.append(tsi.Query(**{"$expr": in_op}))

    if req.alert_ids:
        # For alert_ids array filtering, use a simplified approach
        # This may need to be enhanced based on the actual ClickHouse array operations needed
        alert_conditions = []
        for alert_id in req.alert_ids:
            contains_op = tsi_query.ContainsOperation(
                **{
                    "$contains": {
                        "input": tsi_query.GetFieldOperator(
                            **{"$getField": "alert_ids"}
                        ),
                        "substr": tsi_query.LiteralOperation(**{"$literal": alert_id}),
                        "case_insensitive": False,
                    }
                }
            )
            alert_conditions.append(contains_op)

        if len(alert_conditions) == 1:
            query_conditions.append(tsi.Query(**{"$expr": alert_conditions[0]}))
        else:
            or_op = tsi_query.OrOperation(**{"$or": alert_conditions})
            query_conditions.append(tsi.Query(**{"$expr": or_op}))

    if req.end_time:
        # end_time should filter for records created before or at the end_time
        gte_op = tsi_query.GteOperation(
            **{
                "$gte": [
                    tsi_query.LiteralOperation(**{"$literal": req.end_time}),
                    tsi_query.GetFieldOperator(**{"$getField": "created_at"}),
                ]
            }
        )
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
