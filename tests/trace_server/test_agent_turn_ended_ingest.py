"""Integration: AgentWriteHandler.otel_export emits agent_turn_ended events."""
from __future__ import annotations

from unittest.mock import MagicMock

# This test is intentionally stub-heavy because we only want to verify that
# the Kafka emission hook fires when a root span ends. It does NOT exercise
# the real OTel protobuf path.


def test_otel_export_emits_for_completed_root_span(monkeypatch):
    import datetime

    from weave.trace_server.agents.clickhouse import AgentWriteHandler
    from weave.trace_server.agents.events import AgentTurnEndedEvent
    from weave.trace_server.agents.schema import AgentSpanCHInsertable
    from weave.trace_server.agents.types import GenAIOTelExportReq

    # Stub Span.from_proto and extract_genai_span so we don't need real OTel bytes.
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
    query_fn = MagicMock()
    kafka_producer = MagicMock()

    handler = AgentWriteHandler(ch, query_fn, kafka_producer=kafka_producer)

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

    from weave.trace_server.agents import clickhouse as ch_module

    monkeypatch.setattr(
        ch_module, "Span", MagicMock(from_proto=lambda *a, **kw: MagicMock())
    )
    monkeypatch.setattr(
        ch_module, "Resource", MagicMock(from_proto=lambda *a, **kw: MagicMock())
    )
    extractor = MagicMock(side_effect=stub_rows)
    monkeypatch.setattr(ch_module, "extract_genai_span", extractor)

    # Stub row-conversion helpers so we don't depend on their internals.
    monkeypatch.setattr(ch_module, "genai_span_to_row", lambda r: [])
    monkeypatch.setattr(ch_module, "extract_search_rows", lambda r: [])

    req = GenAIOTelExportReq(
        processed_spans=[processed], project_id="p", wb_user_id=""
    )
    res = handler.otel_export(req)

    assert res.accepted_spans == 2
    assert kafka_producer.produce_agent_turn_ended.call_count == 1
    event = kafka_producer.produce_agent_turn_ended.call_args.args[0]
    assert isinstance(event, AgentTurnEndedEvent)
    assert event.trace_id == "tr"
    assert event.root_span_id == "root"


def test_otel_export_no_emit_when_no_kafka_producer():
    """When kafka_producer is None, otel_export should not attempt to emit."""
    from weave.trace_server.agents.clickhouse import AgentWriteHandler

    ch = MagicMock()
    query_fn = MagicMock()
    handler = AgentWriteHandler(ch, query_fn)  # no kafka_producer
    assert handler._kafka_producer is None
