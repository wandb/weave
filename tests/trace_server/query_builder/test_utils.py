"""Tests for weave.trace_server.calls_query_builder.utils."""

import pytest

from weave.trace_server.calls_query_builder.utils import (
    parse_string_to_utc_timestamp,
    timestamp_to_datetime_str,
)


@pytest.mark.parametrize(
    ("raw", "expected_ch_str"),
    [
        ("2024-03-01", "2024-03-01 00:00:00.000000"),
        ("  2024-03-01  ", "2024-03-01 00:00:00.000000"),
        ("2024-03-01T12:00:00", "2024-03-01 12:00:00.000000"),
        ("2024-03-01T12:00:00Z", "2024-03-01 12:00:00.000000"),
        ("2024-03-01T12:00:00z", "2024-03-01 12:00:00.000000"),
        ("2024-03-01T12:00:00+00:00", "2024-03-01 12:00:00.000000"),
        ("2024-03-01T12:00:00-05:00", "2024-03-01 17:00:00.000000"),
        # Canonical ClickHouse-style strings (from timestamp_to_datetime_str) round-trip unchanged.
        ("2024-03-01 00:00:00.000000", "2024-03-01 00:00:00.000000"),
        ("2024-03-01 12:00:00.000000", "2024-03-01 12:00:00.000000"),
        ("  2024-03-01 12:00:00.000000  ", "2024-03-01 12:00:00.000000"),
        ("2024-03-01 00:00:00", "2024-03-01 00:00:00.000000"),
    ],
)
def test_parse_string_to_utc_timestamp_matches_ch_format(
    raw: str, expected_ch_str: str
) -> None:
    """Parse + timestamp_to_datetime_str yields the canonical CH datetime string."""
    ts = parse_string_to_utc_timestamp(raw)
    assert ts is not None
    assert timestamp_to_datetime_str(ts) == expected_ch_str


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "not a date", "2024-13-01", "2024-01-15T", "display_name"],
)
def test_parse_string_to_utc_timestamp_rejects(raw: str) -> None:
    assert parse_string_to_utc_timestamp(raw) is None
