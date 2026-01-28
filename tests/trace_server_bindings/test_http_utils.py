"""Tests for http_utils 413 handling."""

from unittest.mock import Mock

import httpx

from weave.trace_server_bindings.http_utils import process_batch_with_retry


def test_413_splits_batch_and_retries():
    """When server returns 413, split batch in half and retry both halves."""
    sent_batches = []
    first_call = True

    def mock_send(data: bytes) -> None:
        nonlocal first_call
        if first_call:
            first_call = False
            raise httpx.HTTPStatusError(
                "413", request=Mock(), response=Mock(status_code=413)
            )
        sent_batches.append(data)

    process_batch_with_retry(
        list(range(100)),
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=mock_send,
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
    )

    assert len(sent_batches) == 2
