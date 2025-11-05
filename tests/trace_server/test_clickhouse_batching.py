"""Tests for ClickHouse batching behavior in the trace server.

This module verifies that multiple calls are properly batched into a single
ClickHouse insert operation for performance optimization.
"""

import base64
import datetime
from unittest.mock import MagicMock, patch

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer


def make_base_64_content(content: str) -> str:
    """Helper function to create base64 encoded content.

    Args:
        content (str): The content to encode.

    Returns:
        str: Base64 encoded content with data URI prefix.
    """
    return "data:text/plain;base64," + base64.b64encode(content.encode()).decode()


string_suffix = "a" * AUTO_CONVERSION_MIN_SIZE


def test_clickhouse_batching():
    """Test that batched calls are properly sent to ClickHouse with correct parameters."""
    # Create a mock ClickHouse client
    mock_ch_client = MagicMock()

    # Mock the command method to avoid actual database operations
    mock_ch_client.command.return_value = None

    # Mock the insert method to track calls
    mock_ch_client.insert.return_value = MagicMock()

    # Create a ClickHouseTraceServer instance and patch _mint_client
    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")

        # Use properly base64 encoded project_id (entity/project format)
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

        # Create a batch of call start requests
        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_1",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 1" + string_suffix
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_2",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 2" + string_suffix
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_3",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 3" + string_suffix
                                )
                            },
                        )
                    ),
                ),
            ]
        )

        # Execute the batch
        trace_server.call_start_batch(batch_req)

        # THE KEY ASSERTION:
        # Verify that there are exactly 2 inserts:
        # 1 for files and 1 for call_parts (order may vary)
        insert_call_count = mock_ch_client.insert.call_count
        assert insert_call_count == 2, (
            f"Expected exactly 2 ClickHouse insert calls for 3 batched calls "
            f"(and 3 base64 content objects, which are stored in files), "
            f"but got {insert_call_count} insert calls"
        )

        # Check that both files and call_parts were inserted (order may vary)
        insert_tables = [
            mock_ch_client.insert.call_args_list[0][0][0],
            mock_ch_client.insert.call_args_list[1][0][0],
        ]
        assert set(insert_tables) == {"files", "call_parts"}, (
            f"Expected inserts to files and call_parts tables, "
            f"but got inserts to: {insert_tables}"
        )
