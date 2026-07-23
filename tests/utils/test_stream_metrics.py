"""Tests for stream metrics utilities, focusing on time-to-first-token (TTFT) functionality."""

import time
from dataclasses import dataclass
from unittest.mock import patch

from weave.utils.stream_metrics import (
    WEAVE_STREAM_START_TIME,
    calculate_time_to_first_token,
    extract_time_to_first_token,
    init_stream_tracking,
    preserve_stream_attributes,
)


class MockAccumulator: ...


@dataclass
class MockChunk:
    """Mock chunk object to simulate individual stream chunks."""

    content: str = ""


def simple_content_detector(chunk: MockChunk) -> bool:
    """Simple content detector for testing."""
    return bool(chunk.content)


def test_ttft_computed_once_on_first_content_chunk():
    """TTFT ignores empty chunks, fires on the first content chunk, and never recalculates."""
    accumulator = MockAccumulator()
    init_stream_tracking(accumulator, 1000.0)

    # Empty chunks never trigger TTFT.
    with patch("time.time", return_value=1001.0):
        assert (
            calculate_time_to_first_token(
                accumulator, MockChunk(content=""), simple_content_detector
            )
            is None
        )
        assert (
            calculate_time_to_first_token(
                accumulator, MockChunk(content=""), simple_content_detector
            )
            is None
        )
    assert extract_time_to_first_token(accumulator) is None

    # First content chunk computes TTFT as now - start.
    with patch("time.time", return_value=1001.5):
        ttft = calculate_time_to_first_token(
            accumulator, MockChunk(content="Hello"), simple_content_detector
        )
    assert ttft == 1.5
    assert extract_time_to_first_token(accumulator) == 1.5

    # Subsequent content chunks do not recalculate.
    with patch("time.time", return_value=1002.0):
        ttft2 = calculate_time_to_first_token(
            accumulator, MockChunk(content=" World"), simple_content_detector
        )
    assert ttft2 is None
    assert extract_time_to_first_token(accumulator) == 1.5


def test_streaming_response():
    """Test TTFT calculation with actual streaming generator."""

    def _mock_streaming_response():
        """Simulate a streaming API response with realistic timing."""
        # First yield: metadata chunk (no content)
        time.sleep(0.005)  # 5ms delay
        yield MockChunk(content="")

        # Second yield: another metadata chunk
        time.sleep(0.003)  # 3ms delay
        yield MockChunk(content="")

        # Third yield: first content chunk - this should trigger TTFT calculation
        time.sleep(0.007)  # 7ms delay
        yield MockChunk(content="Hello")

        # Fourth yield: more content - should not change TTFT
        time.sleep(0.010)  # 10ms delay
        yield MockChunk(content=" world")

        # Fifth yield: final content
        time.sleep(0.005)  # 5ms delay
        yield MockChunk(content="!")

    # Initialize stream tracking
    accumulator = MockAccumulator()
    init_stream_tracking(accumulator)

    # Process the streaming response
    ttft_results = []

    for chunk in _mock_streaming_response():
        # Calculate TTFT for this chunk
        ttft = calculate_time_to_first_token(
            accumulator, chunk, simple_content_detector
        )
        ttft_results.append(ttft)

        # Simulate accumulator recreation (like in real streaming)
        if hasattr(accumulator, WEAVE_STREAM_START_TIME):
            old_accumulator = accumulator
            accumulator = MockAccumulator()
            preserve_stream_attributes(old_accumulator, accumulator)

    # Verify results
    assert ttft_results[0] is None, "First chunk (metadata) should not calculate TTFT"
    assert ttft_results[1] is None, "Second chunk (metadata) should not calculate TTFT"
    assert ttft_results[2] is not None, (
        "Third chunk (first content) should calculate TTFT"
    )
    assert ttft_results[3] is None, "Fourth chunk should not recalculate TTFT"
    assert ttft_results[4] is None, "Fifth chunk should not recalculate TTFT"

    # TTFT should be reasonable (at least 15ms due to our delays: 5+3+7=15ms)
    first_content_ttft = ttft_results[2]
    assert first_content_ttft >= 0.015
    assert first_content_ttft < 0.1

    # Final accumulator should have the same TTFT value
    final_ttft = extract_time_to_first_token(accumulator)
    assert final_ttft == first_content_ttft
