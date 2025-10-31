"""Utilities for tracking streaming metrics like time-to-first-token (TTFT)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

WEAVE_STREAM_START_TIME = "_weave_stream_start_time"
WEAVE_TTFT = "_weave_time_to_first_token"


def init_stream_tracking(obj: Any, start_time: float | None = None) -> None:
    """Initialize stream tracking on an object with a specific start time.

    Args:
        obj: The object to track streaming metrics on.
        start_time: The pre-recorded start time, or None to use current time.

    Examples:
        >>> # Most common usage - track with current time
        >>> accumulator = ChatCompletionChunk(...)
        >>> init_stream_tracking(accumulator)
        >>>
        >>> # Or with a specific pre-recorded start time
        >>> start_time = time.time()
        >>> # ... make API call ...
        >>> accumulator = ChatCompletionChunk(...)
        >>> init_stream_tracking(accumulator, start_time)
    """
    if start_time is not None:
        setattr(obj, WEAVE_STREAM_START_TIME, start_time)
    else:
        setattr(obj, WEAVE_STREAM_START_TIME, time.time())
    setattr(obj, WEAVE_TTFT, None)


def calculate_time_to_first_token(
    accumulator: Any,
    current_chunk: Any,
    content_detector: Callable,
) -> float | None:
    """Calculate time to first token if this is the first chunk with content.

    Args:
        accumulator: The accumulated stream object with tracking attributes.
        current_chunk: The current chunk being processed.
        content_detector: A function that takes a chunk and returns True if it contains content.

    Returns:
        The time to first token in seconds, or None if not the first token.

    Examples:
        >>> def has_content(chunk):
        ...     return any(choice.delta and choice.delta.content for choice in chunk.choices)
        >>> ttft = calculate_time_to_first_token(acc, chunk, has_content)
    """
    if not hasattr(accumulator, WEAVE_TTFT):
        return None

    if getattr(accumulator, WEAVE_TTFT) is not None:
        return None  # Already calculated

    if not content_detector(current_chunk):
        return None  # No content in this chunk

    if not hasattr(accumulator, WEAVE_STREAM_START_TIME):
        return None  # No start time recorded

    # Calculate and store the time to first token
    ttft = time.time() - getattr(accumulator, WEAVE_STREAM_START_TIME)
    setattr(accumulator, WEAVE_TTFT, ttft)
    return ttft


def preserve_stream_attributes(source_obj: Any, target_obj: Any) -> None:
    """Preserve stream tracking attributes from source to target object.

    Args:
        source_obj: The object to copy attributes from.
        target_obj: The object to copy attributes to.

    Examples:
        >>> preserve_stream_attributes(old_accumulator, new_accumulator)
    """
    # Preserve start time if it exists
    if hasattr(source_obj, WEAVE_STREAM_START_TIME):
        setattr(
            target_obj,
            WEAVE_STREAM_START_TIME,
            getattr(source_obj, WEAVE_STREAM_START_TIME),
        )

    # Preserve TTFT if attribute exists (even if the value is None)
    if hasattr(source_obj, WEAVE_TTFT):
        setattr(target_obj, WEAVE_TTFT, getattr(source_obj, WEAVE_TTFT))


def extract_time_to_first_token(obj: Any) -> float | None:
    """Extract the time to first token from an object.

    Args:
        obj: The object to extract TTFT from.

    Returns:
        The time to first token in seconds, or None if not available.

    Examples:
        >>> ttft = extract_time_to_first_token(response)
        >>> if ttft:
        ...     print(f"Time to first token: {ttft:.3f}s")
    """
    if hasattr(obj, WEAVE_TTFT):
        return getattr(obj, WEAVE_TTFT, None)
    return None


def add_time_to_first_token_to_dict(data_dict: dict, obj: Any) -> dict:
    """Add time to first token to a dictionary if available.

    Args:
        data_dict: The dictionary to add TTFT to. Creates empty dict if None.
        obj: The object to extract TTFT from.

    Returns:
        The updated dictionary with TTFT if available.

    Examples:
        >>> result_dict = add_time_to_first_token_to_dict(response_dict, accumulator)
    """
    time_to_first_token = extract_time_to_first_token(obj)
    if time_to_first_token is not None:
        if data_dict is None:
            data_dict = {}
        data_dict["time_to_first_token"] = time_to_first_token
    return data_dict
