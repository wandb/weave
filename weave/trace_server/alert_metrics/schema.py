"""Alert metrics schema definitions, constants, and basic formatting functions.

This module contains table definitions, column constants, and basic data formatting
functions that don't require complex dependencies to avoid circular imports.
"""

import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import Column, Row, Table

ALERT_METRICS_CREATE_COLUMNS = [
    "project_id",
    "id",
    "alert_ids",
    "created_at",
    "metric_key",
    "metric_value",
    "metric_type",
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
    "metric_type",
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
        Column("metric_type", "string"),
        Column("wb_user_id", "string", nullable=True),
    ],
)


def format_row_to_alert_metric_schema(row: Row) -> tsi.AlertMetricSchema:
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
        ...     "metric_value": 0.95,
        ...     "metric_type": "float"
        ... }
        >>> schema = format_row_to_alert_metric_schema(row)
        >>> assert schema.id == "test_id"
        >>> assert schema.metric_key == "accuracy"
        >>> assert schema.metric_type == "float"
    """
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
    assert row["metric_type"] is not None
    assert isinstance(row["metric_type"], str)
    assert row["call_id"] is not None
    assert isinstance(row["call_id"], str)
    assert row["wb_user_id"] is not None
    assert isinstance(row["wb_user_id"], str)

    # Ensure alert_ids is a list of strings
    alert_ids = row["alert_ids"]
    if not isinstance(alert_ids, list):
        alert_ids = []
    else:
        alert_ids = [str(item) for item in alert_ids]

    return tsi.AlertMetricSchema(
        id=row["id"],
        project_id=row["project_id"],
        alert_ids=alert_ids,
        created_at=row["created_at"],
        metric_key=row["metric_key"],
        metric_value=row["metric_value"],
        metric_type=row["metric_type"],
        call_id=row["call_id"],
        wb_user_id=row["wb_user_id"],
    )
