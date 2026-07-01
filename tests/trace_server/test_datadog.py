"""Wire-format and config-resolution tests for `weave.trace_server.datadog`.

The byte-identical DogStatsD wire format and the env-var fallback chain
are the load-bearing claims of the migration (existing dashboards filter
on the metric name + tag shape). These tests pin both so a future edit
can't silently drift them.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from weave.trace_server import datadog

# ---------------------------------------------------------------------------
# Packet wire format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metric", "value", "tags", "expected"),
    [
        # No tags — bare `metric:value|c`.
        ("weave_trace_server.db_inserts", 1, [], b"weave_trace_server.db_inserts:1|c"),
        # Single tag.
        (
            "weave_trace_server.db_inserts",
            7,
            ["table:calls"],
            b"weave_trace_server.db_inserts:7|c|#table:calls",
        ),
        # Multiple tags, preserved in order.
        (
            "weave_trace_server.db_inserts",
            42,
            ["table:calls", "path:otel"],
            b"weave_trace_server.db_inserts:42|c|#table:calls,path:otel",
        ),
        # Zero value still emits (caller is responsible for skipping zeros).
        ("m", 0, ["k:v"], b"m:0|c|#k:v"),
    ],
)
def test_format_packet_wire_format(
    metric: str, value: int, tags: list[str], expected: bytes
) -> None:
    assert datadog.format_packet(metric, value, tags) == expected


# ---------------------------------------------------------------------------
# Target resolution — family + address from the env-var fallback chain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        # No env vars → localhost UDP default.
        ({}, (socket.AF_INET, ("localhost", 8125))),
        # `udp://host:port` is the documented single-tenant prod form.
        (
            {"DD_DOGSTATSD_URL": "udp://datadog.datadog:8125"},
            (socket.AF_INET, ("datadog.datadog", 8125)),
        ),
        # Bare `host:port` (no scheme) is accepted as UDP.
        ({"DD_DOGSTATSD_URL": "my-agent:9125"}, (socket.AF_INET, ("my-agent", 9125))),
        # UDP URL without a port defaults to 8125.
        (
            {"DD_DOGSTATSD_URL": "udp://datadog.datadog"},
            (socket.AF_INET, ("datadog.datadog", 8125)),
        ),
        # Garbage URL must NOT raise; falls back to localhost.
        (
            {"DD_DOGSTATSD_URL": "://this-is-broken::"},
            (socket.AF_INET, ("localhost", 8125)),
        ),
        # No URL → DD_AGENT_HOST + DD_DOGSTATSD_PORT.
        (
            {"DD_AGENT_HOST": "agent.example.com", "DD_DOGSTATSD_PORT": "9999"},
            (socket.AF_INET, ("agent.example.com", 9999)),
        ),
        # Non-numeric port must NOT crash import; falls back to the default.
        (
            {"DD_AGENT_HOST": "agent.example.com", "DD_DOGSTATSD_PORT": "abc"},
            (socket.AF_INET, ("agent.example.com", 8125)),
        ),
        # UDS schemes → AF_UNIX with the socket path. This is the SaaS-prod
        # Agent form that PR #7268 regressed (its UDP-only client dropped it).
        (
            {"DD_DOGSTATSD_URL": "unix:///var/run/datadog/dsd.socket"},
            (socket.AF_UNIX, "/var/run/datadog/dsd.socket"),
        ),
        (
            {"DD_DOGSTATSD_URL": "unixgram:///var/run/datadog/dsd.socket"},
            (socket.AF_UNIX, "/var/run/datadog/dsd.socket"),
        ),
        (
            {"DD_DOGSTATSD_URL": "uds:///var/run/datadog/dsd.socket"},
            (socket.AF_UNIX, "/var/run/datadog/dsd.socket"),
        ),
    ],
)
def test_resolve_dogstatsd_target(
    env: dict[str, str],
    expected: tuple[int, str | tuple[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("DD_DOGSTATSD_URL", "DD_AGENT_HOST", "DD_DOGSTATSD_PORT"):
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert datadog._resolve_dogstatsd_target() == expected


# ---------------------------------------------------------------------------
# Port parsing — must not crash on bad input
# ---------------------------------------------------------------------------


def test_parse_port_valid() -> None:
    assert datadog._parse_port("8125") == 8125


def test_parse_port_none_uses_default() -> None:
    assert datadog._parse_port(None) == 8125


def test_parse_port_non_numeric_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-numeric port must NOT raise — this module is imported by ~11
    other modules and a single bad env var would take the whole trace
    server down at import time. Falls back to the default + warns.
    """
    assert datadog._parse_port("not-a-port") == 8125


# ---------------------------------------------------------------------------
# Unix-domain-socket emit — the path PR #7268 regressed in SaaS prod
# ---------------------------------------------------------------------------


def test_statsd_client_emits_over_unix_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real AF_UNIX datagram server receives the exact wire bytes.

    Uses a relative socket name under a chdir'd tmp dir to stay well under
    the platform's AF_UNIX path-length limit.
    """
    monkeypatch.chdir(tmp_path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind("dsd.socket")
    server.settimeout(2.0)
    try:
        client = datadog._StatsDClient(socket.AF_UNIX, "dsd.socket")
        client.emit("weave_trace_server.db_inserts", 3, ["table:calls", "path:otel"])
        assert (
            server.recv(4096)
            == b"weave_trace_server.db_inserts:3|c|#table:calls,path:otel"
        )
    finally:
        server.close()
