#!/usr/bin/env python
"""Simple test script for SQLite alert metrics implementation."""

import datetime
import os

# Add parent directory to path for imports
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_alert_metrics():
    """Test alert metrics create and query functionality."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Initialize the server
        server = SqliteTraceServer(db_path)
        server.setup_tables()

        project_id = "test_project"

        # Test 1: Create a metric
        print("Testing alert_metric_create...")
        create_req = tsi.AlertMetricCreateReq(
            project_id=project_id,
            alert_ids=["alert1", "alert2"],
            metric_key="test_metric",
            metric_value=42.5,
            call_id="call123",
            wb_user_id="user123",
        )

        create_res = server.alert_metric_create(create_req)
        assert create_res.id is not None
        print(f"✓ Created metric with ID: {create_res.id}")

        # Test 2: Create more metrics for testing queries
        for i in range(3):
            req = tsi.AlertMetricCreateReq(
                project_id=project_id,
                alert_ids=[f"alert{i}"],
                metric_key=f"metric_{i % 2}",  # Two different metric keys
                metric_value=10.0 * i,
                call_id=f"call_{i}",
                wb_user_id="user123",
            )
            server.alert_metric_create(req)

        # Test 3: Query all metrics
        print("\nTesting alert_metrics_query (all metrics)...")
        query_req = tsi.AlertMetricsQueryReq(project_id=project_id)
        query_res = server.alert_metrics_query(query_req)
        assert len(query_res.metrics) == 4
        print(f"✓ Found {len(query_res.metrics)} metrics")

        # Test 4: Query with metric_keys filter
        print("\nTesting query with metric_keys filter...")
        query_req = tsi.AlertMetricsQueryReq(
            project_id=project_id, metric_keys=["test_metric"]
        )
        query_res = server.alert_metrics_query(query_req)
        assert len(query_res.metrics) == 1
        assert query_res.metrics[0].metric_key == "test_metric"
        print(f"✓ Filtered by metric_key, found {len(query_res.metrics)} metric(s)")

        # Test 5: Query with alert_ids filter
        print("\nTesting query with alert_ids filter...")
        query_req = tsi.AlertMetricsQueryReq(
            project_id=project_id, alert_ids=["alert1"]
        )
        query_res = server.alert_metrics_query(query_req)
        assert len(query_res.metrics) >= 1  # Should find metrics with alert1
        print(f"✓ Filtered by alert_id, found {len(query_res.metrics)} metric(s)")

        # Test 6: Query with limit
        print("\nTesting query with limit...")
        query_req = tsi.AlertMetricsQueryReq(project_id=project_id, limit=2)
        query_res = server.alert_metrics_query(query_req)
        assert len(query_res.metrics) == 2
        print(f"✓ Limited results to {len(query_res.metrics)} metrics")

        # Test 7: Query with time range
        print("\nTesting query with time range...")
        start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=1
        )
        end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=1
        )
        query_req = tsi.AlertMetricsQueryReq(
            project_id=project_id, start_time=start_time, end_time=end_time
        )
        query_res = server.alert_metrics_query(query_req)
        assert len(query_res.metrics) == 4  # All metrics should be within this range
        print(f"✓ Time range query found {len(query_res.metrics)} metrics")

        print("\n✅ All tests passed!")

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    test_alert_metrics()
