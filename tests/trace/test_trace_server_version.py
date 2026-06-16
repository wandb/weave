"""Tests for trace server version checking."""

import pytest

from weave.trace.init_message import check_min_trace_server_version

TEST_SERVER_URL = "https://test.trace.server"


@pytest.mark.parametrize(
    ("trace_server_version", "min_required_version", "expected"),
    [
        # Client has no requirement -> always compatible.
        (None, None, True),
        ("1.0.0", None, True),
        # Client requires a version.
        (None, "0.5.0", False),
        ("0.3.0", "0.5.0", False),
        ("0.5.0", "0.5.0", True),
        ("1.0.0", "0.5.0", True),
        # Pre-release ordering: 0.5.0-dev0 < 0.5.0.
        ("0.5.0-dev0", "0.5.0", False),
        ("0.5.0", "0.5.0-dev0", True),
    ],
)
def test_check_min_trace_server_version(
    trace_server_version: str | None,
    min_required_version: str | None,
    expected: bool,
) -> None:
    """Client/server version combinations resolve to the expected compatibility."""
    result = check_min_trace_server_version(
        trace_server_version=trace_server_version,
        min_required_version=min_required_version,
        trace_server_url=TEST_SERVER_URL,
    )
    assert result is expected
