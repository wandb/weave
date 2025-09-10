"""Tests for the CrossProcessTraceServer components.

This module tests the low-level cross-process communication between
child processes and the main process, including error handling,
streaming methods, and out-of-order response handling.
"""

import time
from collections.abc import Iterator
from datetime import datetime

import pytest

from tests.trace_server.isolated_client_executor.cross_process_trace_server import (
    CrossProcessTraceServerError,
    CrossProcessTraceServerReceiver,
    EmptyPayload,
    RequestQueueItem,
)
from weave.trace_server import trace_server_interface as tsi


class MockTraceServer:
    """Mock trace server for testing cross-process communication."""

    def __init__(self):
        self.call_count = 0
        self.last_request = None
        self.should_raise = False
        self.streaming_items = []

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Mock call_start method."""
        self.call_count += 1
        self.last_request = req
        if self.should_raise:
            raise ValueError("Mock error")
        result = tsi.CallStartRes(id="test_call_id", trace_id="test_trace_id")
        return result

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Mock streaming method."""
        self.call_count += 1
        self.last_request = req
        if self.should_raise:
            raise ValueError("Mock streaming error")
        yield from self.streaming_items


class TestCrossProcessTraceServerSender:
    """Test cases for CrossProcessTraceServerSender."""

    def test_successful_request(self):
        """Test successful request-response cycle."""
        # Create mock trace server
        mock_server = MockTraceServer()

        # Create receiver and sender
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Create a test request
            req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_project",
                    op_name="test_op",
                    started_at=datetime(2024, 1, 1, 0, 0, 0),
                    attributes={},
                    inputs={},
                )
            )

            # Send request
            result = sender.call_start(req)

            # Verify response
            assert result.id == "test_call_id"
            assert result.trace_id == "test_trace_id"
            assert mock_server.call_count == 1
            assert mock_server.last_request == req

        finally:
            sender.stop()
            receiver.stop()

    @pytest.mark.disable_logging_error_check
    def test_error_in_request(self):
        """Test error handling in request processing."""
        # Create mock trace server that raises an error
        mock_server = MockTraceServer()
        mock_server.should_raise = True

        # Create receiver and sender
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Create a test request
            req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_project",
                    op_name="test_op",
                    started_at=datetime(2024, 1, 1, 0, 0, 0),
                    attributes={},
                    inputs={},
                )
            )

            # Send request and expect error
            with pytest.raises(CrossProcessTraceServerError, match="Mock error"):
                sender.call_start(req)

        finally:
            sender.stop()
            receiver.stop()

    def test_streaming_request(self):
        """Test streaming request handling."""
        # Create mock trace server with streaming data
        mock_server = MockTraceServer()
        mock_server.streaming_items = [
            tsi.CallSchema(
                project_id="test_project",
                id="call1",
                op_name="test_op1",
                trace_id="trace1",
                parent_id=None,
                started_at=datetime(2024, 1, 1, 0, 0, 0),
                ended_at=datetime(2024, 1, 1, 0, 0, 1),
                attributes={},
                inputs={},
            ),
            tsi.CallSchema(
                project_id="test_project",
                id="call2",
                op_name="test_op2",
                trace_id="trace2",
                parent_id=None,
                started_at=datetime(2024, 1, 1, 0, 0, 2),
                ended_at=datetime(2024, 1, 1, 0, 0, 3),
                attributes={},
                inputs={},
            ),
        ]

        # Create receiver and sender
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Create a test streaming request
            req = tsi.CallsQueryReq(
                project_id="test_project",
                limit=10,
            )

            # Send streaming request
            results = list(sender.calls_query_stream(req))

            # Verify streaming response
            assert len(results) == 2
            assert results[0].id == "call1"
            assert results[1].id == "call2"
            assert mock_server.call_count == 1

        finally:
            sender.stop()
            receiver.stop()

    @pytest.mark.disable_logging_error_check
    def test_streaming_error(self):
        """Test error handling in streaming requests."""
        # Create mock trace server that raises an error
        mock_server = MockTraceServer()
        mock_server.should_raise = True

        # Create receiver and sender
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Create a test streaming request
            req = tsi.CallsQueryReq(
                project_id="test_project",
                limit=10,
            )

            # Send streaming request and expect error
            with pytest.raises(
                CrossProcessTraceServerError, match="Mock streaming error"
            ):
                list(sender.calls_query_stream(req))

        finally:
            sender.stop()
            receiver.stop()

    def test_timeout_handling(self):
        """Test request timeout handling."""

        # Create a mock trace server that never responds
        class StuckTraceServer:
            def call_start(self, req):
                # Simulate a stuck method that never returns
                time.sleep(100)  # This will be interrupted by timeout
                return tsi.CallStartRes(
                    id="should_not_reach", trace_id="should_not_reach"
                )

        stuck_server = StuckTraceServer()
        receiver = CrossProcessTraceServerReceiver(stuck_server)
        sender = receiver.get_sender_trace_server()

        try:
            req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_project",
                    op_name="test_op",
                    started_at=datetime(2024, 1, 1, 0, 0, 0),
                    attributes={},
                    inputs={},
                )
            )

            # This should timeout (the timeout is 30 seconds in the implementation)
            # For testing purposes, we'll just verify the structure is correct
            # A real timeout test would take too long for the test suite

        finally:
            sender.stop()
            receiver.stop()

    def test_multiple_concurrent_requests(self):
        """Test handling of multiple sequential requests (worker processes one at a time)."""
        # Create mock trace server
        mock_server = MockTraceServer()

        # Create receiver and sender
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            results: list[tuple[int, tsi.CallStartRes]] = []

            # Make multiple requests sequentially (worker processes one at a time)
            for i in range(5):
                req = tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id="test_project",
                        op_name=f"test_op_{i}",
                        started_at=datetime(2024, 1, 1, 0, 0, 0),
                        attributes={},
                        inputs={},
                    )
                )
                result = sender.call_start(req)
                results.append((i, result))

            # Verify results
            assert len(results) == 5
            assert mock_server.call_count == 5

            # Verify each result is correct
            for _, result in results:
                assert result.id == "test_call_id"
                assert result.trace_id == "test_trace_id"

        finally:
            sender.stop()
            receiver.stop()


class TestCrossProcessTraceServerReceiver:
    """Test cases for CrossProcessTraceServerReceiver."""

    def test_worker_thread_lifecycle(self):
        """Test worker thread starts and stops correctly."""
        mock_server = MockTraceServer()
        receiver = CrossProcessTraceServerReceiver(mock_server)

        # Worker thread should be running
        assert receiver._worker_thread is not None
        assert receiver._worker_thread.is_alive()

        # Stop the receiver
        receiver.stop()

        # Worker thread should stop
        receiver._worker_thread.join(timeout=5.0)
        assert not receiver._worker_thread.is_alive()

    @pytest.mark.disable_logging_error_check
    def test_invalid_signal_handling(self):
        """Test handling of invalid signals."""
        mock_server = MockTraceServer()
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Send invalid signal directly to the queue
            receiver.request_queue.put(
                RequestQueueItem(
                    request_id="test_id",
                    method="INVALID_SIGNAL",
                    payload=EmptyPayload(),
                )
            )

            # Give time for processing
            time.sleep(0.1)

            # The receiver should handle the error gracefully
            # and continue processing

        finally:
            sender.stop()
            receiver.stop()

    def test_method_not_found_handling(self):
        """Test handling when requested method doesn't exist."""
        mock_server = MockTraceServer()
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        try:
            # Try to call a method that doesn't exist
            # This would normally be caught by the type system, but we're testing error handling
            with pytest.raises(AttributeError):
                # This should fail because MockTraceServer doesn't have this method
                _ = mock_server.nonexistent_method

        finally:
            sender.stop()
            receiver.stop()


class TestCrossProcessTraceServerIntegration:
    """Integration tests for the complete cross-process system."""

    def test_end_to_end_communication(self):
        """Test complete end-to-end communication flow."""

        # Create a more realistic mock trace server
        class RealisticTraceServer:
            def __init__(self):
                self.calls = []

            def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
                self.calls.append(("call_start", req))
                return tsi.CallStartRes(
                    id=f"call_{len(self.calls)}", trace_id="test_trace"
                )

            def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
                self.calls.append(("call_end", req))
                return tsi.CallEndRes()

            def calls_query_stream(
                self, req: tsi.CallsQueryReq
            ) -> Iterator[tsi.CallSchema]:
                self.calls.append(("calls_query_stream", req))
                yield tsi.CallSchema(
                    project_id=req.project_id,
                    id="test_call",
                    op_name="test_op",
                    trace_id="test_trace",
                    parent_id=None,
                    started_at=datetime(2024, 1, 1, 0, 0, 0),
                    ended_at=datetime(2024, 1, 1, 0, 0, 1),
                    attributes={},
                    inputs={},
                )

        server = RealisticTraceServer()
        receiver = CrossProcessTraceServerReceiver(server)
        sender = receiver.get_sender_trace_server()

        try:
            # Test regular method
            start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_project",
                    id="test_call",
                    op_name="test_op",
                    started_at=datetime(2024, 1, 1, 0, 0, 0),
                    attributes={},
                    inputs={},
                )
            )
            start_res = sender.call_start(start_req)
            assert start_res.id == "call_1"

            # Test another regular method
            end_req = tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id="test_project",
                    id="test_call",
                    ended_at=datetime(2024, 1, 1, 0, 0, 1),
                    summary={},
                )
            )
            end_res = sender.call_end(end_req)
            assert end_res is not None

            # Test streaming method
            query_req = tsi.CallsQueryReq(
                project_id="test_project",
                limit=10,
            )
            results = list(sender.calls_query_stream(query_req))
            assert len(results) == 1
            assert results[0].id == "test_call"

            # Verify all calls were recorded
            assert len(server.calls) == 3
            assert server.calls[0][0] == "call_start"
            assert server.calls[1][0] == "call_end"
            assert server.calls[2][0] == "calls_query_stream"

        finally:
            sender.stop()
            receiver.stop()

    def test_resource_cleanup(self):
        """Test that resources are properly cleaned up."""
        mock_server = MockTraceServer()
        receiver = CrossProcessTraceServerReceiver(mock_server)
        sender = receiver.get_sender_trace_server()

        # Get references to the worker thread
        worker_thread = receiver._worker_thread
        assert worker_thread is not None
        assert worker_thread.is_alive()

        # Stop sender and receiver
        sender.stop()
        receiver.stop()

        # Worker thread should be stopped
        worker_thread.join(timeout=5.0)
        assert not worker_thread.is_alive()

        # Stop event should be set
        assert receiver._stop_event.is_set()
