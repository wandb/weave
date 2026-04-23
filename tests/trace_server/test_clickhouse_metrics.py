"""Tests for ClickHouse OTEL metrics instrumentation.

Deliberately does not depend on ``opentelemetry-sdk`` — the wrapper
must work correctly against the no-op meter that ``opentelemetry-api``
ships by default. That is also the path most SDK consumers of ``weave``
will exercise.
"""

from __future__ import annotations

from typing import Any

import pytest

from weave.trace_server.clickhouse.metrics import (
    WRAPPED_METHODS,
    install_metrics,
)


class FakeClient:
    """Minimal stand-in for clickhouse_connect.driver.client.Client.

    Exposes the four wrapped methods plus one unrelated method so we
    can verify unwrapped methods remain untouched.
    """

    def __init__(self) -> None:
        self.query_calls = 0
        self.insert_calls = 0
        self.command_calls = 0
        self.query_rows_stream_calls = 0
        self.untouched_calls = 0

    def query(self, *args: Any, **kwargs: Any) -> str:
        self.query_calls += 1
        return "ok"

    def insert(self, *args: Any, **kwargs: Any) -> int:
        self.insert_calls += 1
        return 1

    def command(self, *args: Any, **kwargs: Any) -> None:
        self.command_calls += 1

    def query_rows_stream(self, *args: Any, **kwargs: Any) -> list:
        self.query_rows_stream_calls += 1
        return []

    def untouched(self) -> None:
        self.untouched_calls += 1

    def raise_boom(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")


def test_install_metrics_wraps_hot_methods_and_passes_through() -> None:
    """install_metrics rebinds every hot method, passes success + args
    through, leaves unrelated methods alone, is idempotent, and still
    propagates exceptions to the caller.
    """
    client = FakeClient()
    install_metrics(client)  # type: ignore[arg-type]

    for op in WRAPPED_METHODS:
        assert getattr(getattr(client, op), "_weave_metrics_wrapped", False), op

    assert client.query("SELECT 1") == "ok"
    assert client.insert("tbl", [[1]]) == 1
    client.command("OPTIMIZE TABLE foo")
    assert client.query_rows_stream("SELECT 1") == []
    client.untouched()

    assert client.query_calls == 1
    assert client.insert_calls == 1
    assert client.command_calls == 1
    assert client.query_rows_stream_calls == 1
    assert client.untouched_calls == 1

    # Idempotent: second install does not double-wrap, and calls still work.
    install_metrics(client)  # type: ignore[arg-type]
    client.query("SELECT 2")
    assert client.query_calls == 2

    # Errors in wrapped methods propagate unchanged.
    client.query = client.raise_boom  # type: ignore[method-assign]
    install_metrics(client)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="boom"):
        client.query()


def test_install_metrics_skips_missing_methods() -> None:
    """Clients without a given hot method (e.g. a cut-down mock) are
    wrapped only for the methods they have. No AttributeError.
    """

    class PartialClient:
        def query(self, *args: Any, **kwargs: Any) -> str:
            return "ok"

    partial = PartialClient()
    install_metrics(partial)  # type: ignore[arg-type]
    assert getattr(partial.query, "_weave_metrics_wrapped", False)
    assert not hasattr(partial, "insert")
