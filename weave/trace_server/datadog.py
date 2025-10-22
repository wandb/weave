"""Datadog metrics utilities for the trace server.

This module provides a simple interface for emitting custom metrics to Datadog
using the DogStatsD protocol. It automatically handles Datadog initialization,
environment detection, and tag management for consistency with distributed tracing.

Examples:
    Basic usage for emitting metrics:

    >>> from weave.trace_server.datadog import emit_gauge, emit_increment
    >>>
    >>> # Emit a gauge metric with custom tags
    >>> emit_gauge("kafka.producer.queue.size", 42, tags=["topic:events"])
    >>>
    >>> # Increment a counter
    >>> emit_increment("kafka.messages.processed", tags=["status:success"])
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import datadog - it may not be available in test/dev environments
try:
    from datadog import initialize, statsd
    from ddtrace import tracer

    # Initialize DogStatsD client at module import time
    # The datadog library reads DD_DOGSTATSD_HOST and DD_DOGSTATSD_PORT from environment
    # If not set, defaults to localhost:8125
    initialize()
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False
    tracer = None  # type: ignore
    statsd = None  # type: ignore


def _is_datadog_enabled() -> bool:
    """Check if Datadog monitoring is enabled via environment variables."""
    return DATADOG_AVAILABLE and bool(os.getenv("DD_ENV"))


def get_base_tags() -> list[str]:
    """Get base tags from the distributed tracer for consistency across metrics.

    Retrieves global tags from the ddtrace tracer (like service name, environment,
    version, etc.) to ensure metrics have the same tags as distributed traces.

    Returns:
        list[str]: List of tag strings in the format "key:value". Returns an empty
            list if Datadog is not enabled or no tracer tags are available.

    Examples:
        >>> tags = get_base_tags()
        >>> # Returns tags like ["env:prod", "service:weave-trace-server", "version:1.2.3"]
        >>> emit_gauge("my.metric", 100, tags=tags + ["custom:tag"])
    """
    if not _is_datadog_enabled():
        return []

    tags = []
    # Get global tags from tracer if available
    if tracer and hasattr(tracer, "tags") and tracer.tags:
        tags.extend([f"{k}:{v}" for k, v in tracer.tags.items()])

    return tags


def emit_gauge(
    metric_name: str,
    value: float,
    tags: Optional[list[str]] = None,
    include_base_tags: bool = True,
) -> None:
    """Emit a gauge metric to Datadog.

    A gauge is a metric that represents a single value that can go up or down.

    Args:
        metric_name (str): The name of the metric (e.g., "kafka.producer.queue.size").
        value (float): The value to set the gauge to.
        tags (Optional[list[str]]): Additional tags in "key:value" format. Defaults to None.
        include_base_tags (bool): Whether to include base tags from the tracer. Defaults to True.

    Examples:
        >>> # Simple gauge
        >>> emit_gauge("queue.size", 42)
        >>>
        >>> # Gauge with custom tags
        >>> emit_gauge("queue.size", 42, tags=["queue:high_priority"])
        >>>
        >>> # Gauge without base tags
        >>> emit_gauge("queue.size", 42, include_base_tags=False)
    """
    if not _is_datadog_enabled() or not statsd:
        return

    try:
        all_tags = get_base_tags() if include_base_tags else []
        if tags:
            all_tags.extend(tags)

        statsd.gauge(metric_name, value=value, tags=all_tags)
    except Exception as e:
        logger.warning(f"Failed to emit gauge metric {metric_name}: {e}")


def emit_increment(
    metric_name: str,
    value: int = 1,
    tags: Optional[list[str]] = None,
    include_base_tags: bool = True,
) -> None:
    """Emit an increment (counter) metric to Datadog.

    Increments a counter by the specified value. Use this for counting events.

    Args:
        metric_name (str): The name of the metric (e.g., "kafka.messages.processed").
        value (int): The value to increment by. Defaults to 1.
        tags (Optional[list[str]]): Additional tags in "key:value" format. Defaults to None.
        include_base_tags (bool): Whether to include base tags from the tracer. Defaults to True.

    Examples:
        >>> # Increment by 1
        >>> emit_increment("messages.processed")
        >>>
        >>> # Increment by a specific amount
        >>> emit_increment("messages.processed", value=10)
        >>>
        >>> # Increment with custom tags
        >>> emit_increment("errors", tags=["error_type:timeout"])
    """
    if not _is_datadog_enabled() or not statsd:
        return

    try:
        all_tags = get_base_tags() if include_base_tags else []
        if tags:
            all_tags.extend(tags)

        statsd.increment(metric_name, value=value, tags=all_tags)
    except Exception as e:
        logger.warning(f"Failed to emit increment metric {metric_name}: {e}")


def emit_histogram(
    metric_name: str,
    value: float,
    tags: Optional[list[str]] = None,
    include_base_tags: bool = True,
) -> None:
    """Emit a histogram metric to Datadog.

    Histograms track the statistical distribution of a set of values (avg, count,
    median, 95th percentile, max, etc.).

    Args:
        metric_name (str): The name of the metric (e.g., "request.duration").
        value (float): The value to add to the histogram.
        tags (Optional[list[str]]): Additional tags in "key:value" format. Defaults to None.
        include_base_tags (bool): Whether to include base tags from the tracer. Defaults to True.

    Examples:
        >>> # Track request duration
        >>> emit_histogram("request.duration", 0.234)
        >>>
        >>> # Track with custom tags
        >>> emit_histogram("request.duration", 0.234, tags=["endpoint:/api/v1"])
    """
    if not _is_datadog_enabled() or not statsd:
        return

    try:
        all_tags = get_base_tags() if include_base_tags else []
        if tags:
            all_tags.extend(tags)

        statsd.histogram(metric_name, value=value, tags=all_tags)
    except Exception as e:
        logger.warning(f"Failed to emit histogram metric {metric_name}: {e}")
