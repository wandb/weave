"""Alert metrics schema definitions, constants, and basic formatting functions.

This module contains table definitions, column constants, and basic data formatting
functions that don't require complex dependencies to avoid circular imports.
"""

import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from weave.trace_server.ids import generate_id
from weave.trace_server.orm import Column, Row, Table

if TYPE_CHECKING:
    pass

# Column name constants for consistency across create/query operations
ALERT_METRICS_CREATE_COLUMNS = [
    "project_id",
    "id",
    "alert_ids",
    "created_at",
    "metric_key",
    "metric_value",
    "call_id",
    "wb_user_id",
]

ALERT_METRICS_QUERY_COLUMNS = [
    "id",
    "project_id",
    "alert_ids",
    "created_at",
    "metric_key",
    "metric_value",
]

TABLE_ALERT_METRICS = Table(
    "alert_metrics",
    [
        Column("id", "string"),
        Column("project_id", "string"),
        Column("call_id", "string", nullable=True),
        Column("alert_ids", "array"),
        Column("created_at", "datetime"),
        Column("metric_key", "string"),
        Column("metric_value", "float"),
        Column("wb_user_id", "string", nullable=True),
    ],
)


def format_alert_metric_to_row(
    alert_metric_req: Any,  # tsi.AlertMetricCreateReq - avoid circular import
) -> Row:
    """Create an alert metric row from a create request.

    Args:
        alert_metric_req: The alert metric create request.

    Returns:
        Row: The alert metric row ready for insertion.

    Examples:
        >>> req = AlertMetricCreateReq(project_id="test", metric_key="accuracy", metric_value=0.95)
        >>> row = format_alert_metric_to_row(req)
        >>> assert row["project_id"] == "test"
        >>> assert row["metric_key"] == "accuracy"
    """
    alert_metric_id = alert_metric_req.id or generate_id()
    created_at = datetime.datetime.now(ZoneInfo("UTC"))

    return {
        "id": alert_metric_id,
        "project_id": alert_metric_req.project_id,
        "call_id": alert_metric_req.call_id,
        "alert_ids": alert_metric_req.alert_ids,
        "created_at": created_at,
        "metric_key": alert_metric_req.metric_key,
        "metric_value": alert_metric_req.metric_value,
    }


def format_alert_metric_to_res(row: Row) -> Any:  # tsi.AlertMetricsCreateRes
    """Format a database row to an AlertMetricCreateRes.

    Args:
        row: Database row containing alert metric data.

    Returns:
        tsi.AlertMetricCreateRes: The formatted response.

    Examples:
        >>> row = {"id": "test_id", "created_at": datetime.now(ZoneInfo("UTC"))}
        >>> res = format_alert_metric_to_res(row)
        >>> assert res.id == "test_id"
    """
    # Import at runtime to avoid circular imports
    from weave.trace_server import trace_server_interface as tsi

    assert row["id"] is not None
    assert isinstance(row["id"], str)
    assert row["created_at"] is not None
    assert isinstance(row["created_at"], datetime.datetime)

    return tsi.AlertMetricsCreateRes(
        ids=[row["id"]],  # AlertMetricsCreateRes expects a list of IDs
    )


def format_row_to_alert_metric_schema(row: Row) -> Any:  # tsi.AlertMetricSchema
    """Format a database row to an AlertMetricSchema.

    Args:
        row: Database row containing alert metric data.

    Returns:
        tsi.AlertMetricSchema: The formatted alert metric schema.

    Examples:
        >>> row = {
        ...     "id": "test_id",
        ...     "project_id": "test_project",
        ...     "alert_ids": ["alert1", "alert2"],
        ...     "created_at": datetime.now(ZoneInfo("UTC")),
        ...     "metric_key": "accuracy",
        ...     "metric_value": 0.95
        ... }
        >>> schema = format_row_to_alert_metric_schema(row)
        >>> assert schema.id == "test_id"
        >>> assert schema.metric_key == "accuracy"
    """
    # Import at runtime to avoid circular imports
    from weave.trace_server import trace_server_interface as tsi

    assert row["id"] is not None
    assert isinstance(row["id"], str)
    assert row["project_id"] is not None
    assert isinstance(row["project_id"], str)
    assert row["created_at"] is not None
    assert isinstance(row["created_at"], datetime.datetime)
    assert row["metric_key"] is not None
    assert isinstance(row["metric_key"], str)
    assert row["metric_value"] is not None
    assert isinstance(row["metric_value"], (int, float))

    # Ensure alert_ids is a list of strings
    alert_ids = row["alert_ids"]
    if not isinstance(alert_ids, list):
        alert_ids = []
    else:
        # Ensure all elements are strings
        alert_ids = [str(item) for item in alert_ids]

    return tsi.AlertMetricSchema(
        id=row["id"],
        project_id=row["project_id"],
        alert_ids=alert_ids,
        created_at=row["created_at"],
        metric_key=row["metric_key"],
        metric_value=row["metric_value"],
    )
