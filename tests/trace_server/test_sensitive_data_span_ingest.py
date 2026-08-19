"""End-to-end PII redaction on the agents OTel ingest path.

Runs the real ``genai_otel_export`` against ClickHouse via the ``ch_server``
fixture and reads the stored span details back, proving the ``pii-v1`` policy
reaches ``raw_span_dump`` and the attribute-derived columns, and that the
default ``off`` policy stores values unchanged.
"""

from __future__ import annotations

import json

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from tests.trace_server.helpers import make_project_id
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import AgentSpansQueryReq, GenAIOTelExportReq
from weave.trace_server.environment import SENSITIVE_DATA_POLICY_ENV

_NOW_NS = 1_767_225_600_000_000_000
_PII_ATTR_VALUE = "Email ada@example.com"
_PII_STATUS_MESSAGE = "card 4111 1111 1111 1111"
_PII_RESOURCE_VALUE = "call (415) 555-2671"


def _pii_proto_span(span_id: bytes) -> PbSpan:
    span = PbSpan()
    span.name = "agents_pii_ingest"
    span.trace_id = (77).to_bytes(16, "big")
    span.span_id = span_id
    span.start_time_unix_nano = _NOW_NS
    span.end_time_unix_nano = _NOW_NS + 1_000_000_000
    span.kind = 1  # CLIENT
    kv = KeyValue()
    kv.key = "gen_ai.prompt"
    kv.value.string_value = _PII_ATTR_VALUE
    span.attributes.append(kv)
    span.status.code = 2  # ERROR, so the status message persists
    span.status.message = _PII_STATUS_MESSAGE
    return span


def _export_req(project_id: str, span: PbSpan) -> GenAIOTelExportReq:
    scope = InstrumentationScope()
    scope.name = "test_instrumentation"
    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    scope_spans.spans.append(span)
    resource = PbResource()
    kv = KeyValue()
    kv.key = "service.owner"
    kv.value.string_value = _PII_RESOURCE_VALUE
    resource.attributes.append(kv)
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    resource_spans.scope_spans.append(scope_spans)
    return GenAIOTelExportReq(
        processed_spans=[
            tsi.ProcessedResourceSpans(
                entity="test-entity",
                project="test-project",
                run_id=None,
                resource_spans=resource_spans,
            )
        ],
        project_id=project_id,
        wb_user_id="test-user",
    )


def _stored_span_details(ch_server, project_id: str):
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, include_details=True)
    )
    assert len(res.spans) == 1
    return res.spans[0]


def test_pii_policy_redacts_stored_span_details(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SENSITIVE_DATA_POLICY_ENV, "pii-v1")
    project_id = make_project_id("span_pii_on")

    res = ch_server.genai_otel_export(
        _export_req(project_id, _pii_proto_span(b"\x41" * 8))
    )

    assert res.rejected_spans == 0
    row = _stored_span_details(ch_server, project_id)
    dump = json.loads(row.raw_span_dump)
    assert dump["attributes"] == {"gen_ai": {"prompt": "Email <EMAIL_ADDRESS>"}}
    assert dump["resource"]["attributes"] == {
        "service": {"owner": "call <PHONE_NUMBER>"}
    }
    assert dump["status"]["message"] == "card <CREDIT_CARD>"
    assert row.status_message == "card <CREDIT_CARD>"


def test_default_off_policy_stores_span_values_unchanged(
    ch_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SENSITIVE_DATA_POLICY_ENV, raising=False)
    project_id = make_project_id("span_pii_off")

    res = ch_server.genai_otel_export(
        _export_req(project_id, _pii_proto_span(b"\x42" * 8))
    )

    assert res.rejected_spans == 0
    row = _stored_span_details(ch_server, project_id)
    dump = json.loads(row.raw_span_dump)
    assert dump["attributes"] == {"gen_ai": {"prompt": _PII_ATTR_VALUE}}
    assert dump["resource"]["attributes"] == {"service": {"owner": _PII_RESOURCE_VALUE}}
    assert dump["status"]["message"] == _PII_STATUS_MESSAGE
