"""Wire-format and config-resolution tests for `weave.trace_server.datadog`.

The byte-identical DogStatsD wire format and the env-var fallback chain
are the load-bearing claims of the migration (existing dashboards filter
on the metric name + tag shape). These tests pin both so a future edit
can't silently drift them.
"""

from __future__ import annotations

import socket

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
# Address resolution — env-var fallback chain
# ---------------------------------------------------------------------------


def test_resolve_addr_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env vars set → `localhost:8125`."""
    monkeypatch.delenv("DD_DOGSTATSD_URL", raising=False)
    monkeypatch.delenv("DD_AGENT_HOST", raising=False)
    monkeypatch.delenv("DD_DOGSTATSD_PORT", raising=False)
    assert datadog._resolve_dogstatsd_addr() == ("localhost", 8125)


def test_resolve_addr_url_with_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DD_DOGSTATSD_URL=udp://host:port` is the documented prod form."""
    monkeypatch.setenv("DD_DOGSTATSD_URL", "udp://datadog.datadog:8125")
    assert datadog._resolve_dogstatsd_addr() == ("datadog.datadog", 8125)


def test_resolve_addr_url_without_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bare `host:port` (no `udp://`) is also accepted."""
    monkeypatch.setenv("DD_DOGSTATSD_URL", "my-agent:9125")
    assert datadog._resolve_dogstatsd_addr() == ("my-agent", 9125)


def test_resolve_addr_url_no_port_defaults_to_8125(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DD_DOGSTATSD_URL", "udp://datadog.datadog")
    assert datadog._resolve_dogstatsd_addr() == ("datadog.datadog", 8125)


def test_resolve_addr_url_malformed_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A garbage URL must NOT raise; fall back to localhost."""
    monkeypatch.setenv("DD_DOGSTATSD_URL", "://this-is-broken::")
    monkeypatch.delenv("DD_AGENT_HOST", raising=False)
    monkeypatch.delenv("DD_DOGSTATSD_PORT", raising=False)
    assert datadog._resolve_dogstatsd_addr() == ("localhost", 8125)


def test_resolve_addr_falls_back_to_host_and_port_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No URL set → `DD_AGENT_HOST` + `DD_DOGSTATSD_PORT`."""
    monkeypatch.delenv("DD_DOGSTATSD_URL", raising=False)
    monkeypatch.setenv("DD_AGENT_HOST", "agent.example.com")
    monkeypatch.setenv("DD_DOGSTATSD_PORT", "9999")
    assert datadog._resolve_dogstatsd_addr() == ("agent.example.com", 9999)


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


def test_parse_port_non_numeric_does_not_raise_at_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole resolution path stays safe even with a bad port env var."""
    monkeypatch.delenv("DD_DOGSTATSD_URL", raising=False)
    monkeypatch.setenv("DD_AGENT_HOST", "agent.example.com")
    monkeypatch.setenv("DD_DOGSTATSD_PORT", "abc")
    # Must not raise.
    host, port = datadog._resolve_dogstatsd_addr()
    assert host == "agent.example.com"
    assert port == 8125  # fell back to default


# ---------------------------------------------------------------------------
# Unified service tags — service/env/version attached to every counter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        # Nothing set → no unified tags.
        ({}, []),
        # Only DD_SERVICE set.
        ({"DD_SERVICE": "weave-trace"}, ["service:weave-trace"]),
        # All three set, in service/env/version order.
        (
            {"DD_SERVICE": "weave-trace", "DD_ENV": "qa", "DD_VERSION": "abc123"},
            ["service:weave-trace", "env:qa", "version:abc123"],
        ),
        # Empty-string values are skipped (unset, not `service:`).
        ({"DD_SERVICE": "", "DD_ENV": "prod"}, ["env:prod"]),
    ],
)
def test_resolve_unified_tags(
    env: dict[str, str], expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in ("DD_SERVICE", "DD_ENV", "DD_VERSION"):
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert datadog._resolve_unified_tags() == expected


def test_record_db_insert_emits_full_packet_with_unified_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real UDP server receives table/path + service/env/version in order.

    This is the regression guard: over UDP host-port (QA + the prod
    fallback) there is no agent origin detection, so the counter must
    carry service/version itself or it drops off service-scoped dashboards.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    monkeypatch.setattr(
        datadog, "_client", datadog._StatsDClient(*server.getsockname())
    )
    monkeypatch.setattr(
        datadog, "_UNIFIED_TAGS", ["service:weave-trace", "env:qa", "version:abc123"]
    )
    try:
        datadog.record_db_insert(table="calls_complete", count=3, path="otel")
        assert server.recv(4096) == (
            b"weave_trace_server.db_inserts:3|c"
            b"|#table:calls_complete,path:otel,service:weave-trace,env:qa,version:abc123"
        )
    finally:
        server.close()
