"""Tests for trace server version checking."""

from weave.trace.init_message import check_min_trace_server_version

TEST_SERVER_URL = "https://test.trace.server"


class TestCheckMinTraceServerVersion:
    """Test check_min_trace_server_version with various client/server version combinations."""

    # Client has no requirement (MIN_TRACE_SERVER_VERSION = None)

    def test_client_none_server_none(self):
        """Client has no requirement, server doesn't report version -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version=None,
            min_required_version=None,
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    def test_client_none_server_has_value(self):
        """Client has no requirement, server reports a version -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version=None,
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    # Client has a requirement (MIN_TRACE_SERVER_VERSION = "0.5.0")

    def test_client_has_value_server_none(self):
        """Client requires version, server doesn't report -> incompatible."""
        result = check_min_trace_server_version(
            trace_server_version=None,
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_client_has_value_server_too_low(self):
        """Client requires version, server version is too low -> incompatible."""
        result = check_min_trace_server_version(
            trace_server_version="0.3.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_client_has_value_server_exact_match(self):
        """Client requires version, server version matches exactly -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    def test_client_has_value_server_higher(self):
        """Client requires version, server version exceeds requirement -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    # Edge cases

    def test_prerelease_version_comparison(self):
        """Pre-release versions are lower than release versions."""
        # 0.5.0-dev0 < 0.5.0, so if client requires 0.5.0, server at 0.5.0-dev0 should fail
        result = check_min_trace_server_version(
            trace_server_version="0.5.0-dev0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_prerelease_requirement_satisfied_by_release(self):
        """Release version satisfies pre-release requirement."""
        # 0.5.0 > 0.5.0-dev0, so server at 0.5.0 satisfies client requiring 0.5.0-dev0
        result = check_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0-dev0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True
