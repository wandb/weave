"""Integration: AgentWriteHandler.insert_otel_spans emits ScoreAgentSpansEvent on root span end."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from weave.trace_server.agents import clickhouse as ch_module
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.kafka_events import ScoreAgentSpansEvent
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.types import GenAIOTelExportReq
from weave.trace_server.kafka import KafkaProducer

# This test is intentionally stub-heavy because we only want to verify that
# the Kafka emission hook fires when a root span ends. It does NOT exercise
# the real OTel protobuf path.


def test_insert_otel_spans_emits_scorer_event_on_root_span_end(monkeypatch):
    # Stub Span.from_proto and extract_genai_span so we don't need real OTel bytes.
    # Datetimes must be tz-aware because from_row compares against SENTINEL_EPOCH (UTC).
    utc = datetime.timezone.utc
    stub_rows = [
        AgentSpanCHInsertable(
            project_id="p",
            trace_id="tr",
            span_id="root",
            parent_span_id="",
            span_name="root",
            started_at=datetime.datetime(2024, 1, 1, 11, 0, 0, tzinfo=utc),
            ended_at=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=utc),
            agent_name="a",
            operation_name="invoke_agent",
        ),
        AgentSpanCHInsertable(
            project_id="p",
            trace_id="tr",
            span_id="child",
            parent_span_id="root",
            span_name="child",
            started_at=datetime.datetime(2024, 1, 1, 11, 5, 0, tzinfo=utc),
            ended_at=datetime.datetime(2024, 1, 1, 11, 55, 0, tzinfo=utc),
        ),
    ]

    ch = MagicMock()
    # spec=KafkaProducer ensures typo'd attribute names raise AttributeError instead
    # of auto-vivifying — without this, asserting against the wrong method name silently passes.
    kafka_producer = MagicMock(spec=KafkaProducer)

    handler = AgentWriteHandler(ch, kafka_producer)

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
    res = handler.insert_otel_spans(req)

    assert res.accepted_spans == 2
    assert kafka_producer.produce_score_agent_spans.call_count == 1
    event = kafka_producer.produce_score_agent_spans.call_args.args[0]
    assert isinstance(event, ScoreAgentSpansEvent)
    assert event.event_type == "turn_ended"
    assert event.trace_id == "tr"
    assert event.root_span_id == "root"
    kafka_producer.flush.assert_called_once_with(0)
