"""Tests for ClickHouse version parsing and feature detection."""

from weave.trace_server.clickhouse_trace_server_settings import (
    parse_clickhouse_version,
    supports_lightweight_update,
)


def test_parse_clickhouse_version_positive():
    """Test parsing valid ClickHouse version strings."""
    assert parse_clickhouse_version("25.8.15.25") == (25, 8, 15, 25)
    assert parse_clickhouse_version("24.3.1.2672.altinity") == (24, 3, 1, 2672)


def test_parse_clickhouse_version_negative():
    """Test parsing invalid version strings."""
    assert parse_clickhouse_version("") == ()
    assert parse_clickhouse_version("invalid.version") == ()


def test_supports_lightweight_update_positive():
    """Test that version 25.8+ supports lightweight updates."""
    assert supports_lightweight_update("25.8.0") is True
    assert supports_lightweight_update("26.1.2.345") is True


def test_supports_lightweight_update_negative():
    """Test that version < 25.8 does not support lightweight updates."""
    assert supports_lightweight_update("25.7.99.999") is False
    assert supports_lightweight_update("24.3.1.2672") is False
    assert supports_lightweight_update("invalid") is False
