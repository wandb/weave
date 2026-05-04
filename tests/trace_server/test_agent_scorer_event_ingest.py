"""Integration: AgentWriteHandler.insert_otel_spans returns the accepted rows so callers can emit downstream events."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from weave.trace_server.agents import clickhouse as ch_module
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.types import GenAIOTelExportReq


def test_insert_otel_spans_returns_accepted_rows(monkeypatch):
    # Stub Span.from_proto and extract_genai_span so we don't need real OTel bytes.
    # Datetimes are naive to match what the OTel ingest path produces (Span.end_time
    # is built from a unix epoch via datetime.fromtimestamp without a tz).
    stub_rows = [
        AgentSpanCHInsertable(
            project_id="p",
            trace_id="tr",
            span_id="root",
            parent_span_id="",
            span_name="root",
            started_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
            ended_at=datetime.datetime(2024, 1, 1, 12, 0, 0),
            agent_name="a",
            operation_name="invoke_agent",
        ),
        AgentSpanCHInsertable(
            project_id="p",
            trace_id="tr",
            span_id="child",
            parent_span_id="root",
            span_name="child",
            started_at=datetime.datetime(2024, 1, 1, 11, 5, 0),
            ended_at=datetime.datetime(2024, 1, 1, 11, 55, 0),
        ),
    ]

    ch = MagicMock()
    handler = AgentWriteHandler(ch)

    # Build a fake processed_span with one scope_spans containing two proto_spans.
    # We stub Span.from_proto + extract_genai_span to return our stub rows in
    # order. (The inner loop calls these per proto_span.)
    proto_span_a = MagicMock()
    proto_span_b = MagicMock()
    scope_spans = MagicMock()
    scope_spans.spans = [proto_span_a, proto_span_b]
    resource_spans = MagicMock()
    resource_spans.scope_spans = [scope_spans]
    resource_spans.resource = MagicMock()
    processed = MagicMock()
    processed.resource_spans = resource_spans
    processed.run_id = ""

    monkeypatch.setattr(
        ch_module, "Span", MagicMock(from_proto=lambda *a, **kw: MagicMock())
    )
    monkeypatch.setattr(
        ch_module, "Resource", MagicMock(from_proto=lambda *a, **kw: MagicMock())
    )
    extractor = MagicMock(side_effect=stub_rows)
    monkeypatch.setattr(ch_module, "extract_genai_span", extractor)

    # Stub row-conversion helper so we don't depend on its internals.
    monkeypatch.setattr(ch_module, "genai_span_to_row", lambda r: [])

    req = GenAIOTelExportReq(processed_spans=[processed], project_id="p", wb_user_id="")
    res, accepted_rows = handler.insert_otel_spans(req)

    assert res.accepted_spans == 2
    assert [r.span_id for r in accepted_rows] == ["root", "child"]
    assert all(isinstance(r, AgentSpanCHInsertable) for r in accepted_rows)
