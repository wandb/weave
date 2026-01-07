"""Tests for trace server version checking."""

import pytest

from weave.trace.init_message import assert_min_trace_server_version


class TestAssertMinTraceServerVersion:
    """Test assert_min_trace_server_version with various client/server version combinations."""

    # Client has no requirement (MIN_TRACE_SERVER_VERSION = None)

    def test_client_none_server_none(self):
        """Client has no requirement, server doesn't report version -> OK."""
        assert_min_trace_server_version(
            trace_server_version=None,
            min_required_version=None,
        )

    def test_client_none_server_has_value(self):
        """Client has no requirement, server reports a version -> OK."""
        assert_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version=None,
        )

    # Client has a requirement (MIN_TRACE_SERVER_VERSION = "0.5.0")

    def test_client_has_value_server_none(self):
        """Client requires version, server doesn't report -> ERROR."""
        with pytest.raises(ValueError, match="does not report its version"):
            assert_min_trace_server_version(
                trace_server_version=None,
                min_required_version="0.5.0",
            )

    def test_client_has_value_server_too_low(self):
        """Client requires version, server version is too low -> ERROR."""
        with pytest.raises(ValueError, match="requires version >= 0.5.0"):
            assert_min_trace_server_version(
                trace_server_version="0.3.0",
                min_required_version="0.5.0",
            )

    def test_client_has_value_server_exact_match(self):
        """Client requires version, server version matches exactly -> OK."""
        assert_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0",
        )

    def test_client_has_value_server_higher(self):
        """Client requires version, server version exceeds requirement -> OK."""
        assert_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version="0.5.0",
        )

    # Edge cases

    def test_prerelease_version_comparison(self):
        """Pre-release versions are lower than release versions."""
        # 0.5.0-dev0 < 0.5.0, so if client requires 0.5.0, server at 0.5.0-dev0 should fail
        with pytest.raises(ValueError, match="requires version >= 0.5.0"):
            assert_min_trace_server_version(
                trace_server_version="0.5.0-dev0",
                min_required_version="0.5.0",
            )

    def test_prerelease_requirement_satisfied_by_release(self):
        """Release version satisfies pre-release requirement."""
        # 0.5.0 > 0.5.0-dev0, so server at 0.5.0 satisfies client requiring 0.5.0-dev0
        assert_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0-dev0",
        )

    def test_error_message_contains_server_host(self):
        """Error message includes the trace server host."""
        with pytest.raises(ValueError, match="https://custom.server.com"):
            assert_min_trace_server_version(
                trace_server_version="0.1.0",
                min_required_version="0.5.0",
                trace_server_host="https://custom.server.com",
            )

    def test_error_message_for_none_server_contains_host(self):
        """Error message for None server version includes the trace server host."""
        with pytest.raises(ValueError, match="https://custom.server.com"):
            assert_min_trace_server_version(
                trace_server_version=None,
                min_required_version="0.5.0",
                trace_server_host="https://custom.server.com",
            )
