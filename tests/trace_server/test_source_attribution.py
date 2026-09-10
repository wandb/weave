"""Unit tests for the source-attribution resolution ladder."""

import datetime
import uuid

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ScopeSpans as PbScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from weave.trace_server import source_attribution
from weave.trace_server.agents import semconv
from weave.trace_server.opentelemetry.python_spans import (
    Resource,
    ScopeSpans,
    Span,
)
from weave.trace_server.source_attribution import (
    INGEST_SOURCE_OTLP,
    INGEST_SOURCE_WEAVE,
    resolve_for_call,
    resolve_for_otel_span,
)

# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "attributes", "scope", "expected"),
    [
        (
            "nested_integration_wins",
            {"integration": {"name": "openai", "version": "0.53.1"}},
            ("opentelemetry.instrumentation.openai", "0.62b1"),
            ("openai", "0.53.1"),
        ),
        (
            "flat_integration_keys",
            {"integration.name": "langchain", "integration.version": "0.54.0"},
            ("", ""),
            ("langchain", "0.54.0"),
        ),
        (
            "node_weave_integration_keys",
            {
                "weave.integration.name": "openai",
                "weave.integration.version": "0.9.2",
            },
            ("should-not-win", "9.9"),
            ("openai", "0.9.2"),
        ),
        (
            "canonical_key_beats_alias",
            {
                "weave.source.name": "claude_code",
                "weave.source.version": "2.1",
                "integration.name": "openai",
                "integration.version": "0.1",
            },
            ("", ""),
            ("claude_code", "2.1"),
        ),
        (
            "version_never_crosses_rungs",
            {"integration.name": "custom_harness"},
            ("codex", "1.4.0"),
            ("custom_harness", ""),
        ),
        (
            "scope_used_when_no_integration",
            {"gen_ai.operation.name": "chat"},
            ("codex", "1.4.0"),
            ("codex", "1.4.0"),
        ),
        (
            "scope_strips_python_instrumentation_prefix",
            {},
            ("opentelemetry.instrumentation.anthropic", "0.40.1"),
            ("anthropic", "0.40.1"),
        ),
        (
            "scope_strips_js_instrumentation_prefix",
            {},
            ("@opentelemetry/instrumentation-http", "0.57.0"),
            ("http", "0.57.0"),
        ),
        (
            "scope_strips_openinference_prefix",
            {},
            ("openinference.instrumentation.openai", "0.1.2"),
            ("openai", "0.1.2"),
        ),
        (
            "scope_strips_weave_prefix",
            {},
            ("weave.claude_agent_sdk", "0.53.1"),
            ("claude_agent_sdk", "0.53.1"),
        ),
        (
            "scope_prefix_only_is_kept",
            {},
            ("weave.", ""),
            ("weave.", ""),
        ),
        (
            "nothing_resolves_to_empty",
            {"gen_ai.request.model": "gpt-5"},
            ("", ""),
            ("", ""),
        ),
        (
            "blank_values_fall_through",
            {"integration.name": "   "},
            ("  ", "1.0"),
            ("", ""),
        ),
        (
            "non_scalar_name_ignored",
            {"integration": {"name": {"nope": 1}, "version": "1"}},
            ("", ""),
            ("", ""),
        ),
    ],
)
def test_ladder_resolves_name_and_version(
    case: str,
    attributes: dict | None,
    scope: tuple[str, str],
    expected: tuple[str, str],
):
    resolved = resolve_for_otel_span(
        attributes=attributes,
        scope_name=scope[0],
        scope_version=scope[1],
    )
    assert (resolved.name, resolved.version) == expected, case
    assert resolved.ingest_source == INGEST_SOURCE_OTLP, case


def test_resolve_for_call_distinguishes_ingest_surface():
    """`ingest_source` records the surface, and is never read off the wire."""
    weave_call = resolve_for_call(
        attributes={"integration": {"name": "openai", "version": "0.53.1"}},
        ingest_source=INGEST_SOURCE_WEAVE,
    )
    assert weave_call == source_attribution.SourceAttribution(
        name="openai",
        version="0.53.1",
        ingest_source=INGEST_SOURCE_WEAVE,
    )

    otel_call = resolve_for_call(
        attributes={},
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump={
            "scope": {"name": "opentelemetry.instrumentation.openai", "version": "0.6"},
        },
    )
    assert otel_call == source_attribution.SourceAttribution(
        name="openai",
        version="0.6",
        ingest_source=INGEST_SOURCE_OTLP,
    )

    normalized_call = resolve_for_call(
        attributes={"integration": {"name": "weave", "version": "1.0"}},
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump={
            "attributes": {
                "integration.name": "raw-otel",
                "integration.version": "2.0",
            }
        },
    )
    assert normalized_call == source_attribution.SourceAttribution(
        name="weave",
        version="1.0",
        ingest_source=INGEST_SOURCE_OTLP,
    )

    spoofed = resolve_for_call(
        attributes={"weave.ingest_source": "otlp"},
        ingest_source=INGEST_SOURCE_WEAVE,
        otel_dump={"name": "chat"},
    )
    assert spoofed.ingest_source == INGEST_SOURCE_WEAVE


def test_integration_attribute_key_matches_the_sdk_producer():
    from weave.integrations.integration_metadata import INTEGRATION_ATTRIBUTE_KEY

    assert f"{INTEGRATION_ATTRIBUTE_KEY}.name" in semconv.SOURCE_NAME.lookup_keys
    assert f"{INTEGRATION_ATTRIBUTE_KEY}.version" in semconv.SOURCE_VERSION.lookup_keys


# ---------------------------------------------------------------------------
# Spans path
# ---------------------------------------------------------------------------


def _pb_span(attributes: dict[str, str]) -> PbSpan:
    span = PbSpan()
    span.name = "chat gpt-5"
    span.trace_id = uuid.uuid4().bytes
    span.span_id = uuid.uuid4().bytes[:8]
    now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    span.start_time_unix_nano = now_ns
    span.end_time_unix_nano = now_ns + 1_000_000_000
    span.kind = 3
    for key, value in attributes.items():
        kv = KeyValue()
        kv.key = key
        kv.value.string_value = value
        span.attributes.append(kv)
    return span


def _pb_resource(attributes: dict[str, str]) -> PbResource:
    resource = PbResource()
    for key, value in attributes.items():
        kv = KeyValue()
        kv.key = key
        kv.value.string_value = value
        resource.attributes.append(kv)
    return resource


def _parsed_span(
    *,
    attributes: dict[str, str] | None = None,
    scope_name: str = "",
    scope_version: str = "",
    resource_attributes: dict[str, str] | None = None,
) -> Span:
    scope = InstrumentationScope()
    scope.name = scope_name
    scope.version = scope_version
    proto_scope_spans = PbScopeSpans()
    proto_scope_spans.scope.CopyFrom(scope)
    proto_scope_spans.spans.append(_pb_span(attributes or {}))
    resource = Resource.from_proto(_pb_resource(resource_attributes or {}))
    return ScopeSpans.from_proto(proto_scope_spans, resource).spans[0]


def test_scope_survives_proto_parsing_into_the_span():
    span = _parsed_span(scope_name="codex", scope_version="1.4.0")
    assert (span.scope_name, span.scope_version) == ("codex", "1.4.0")

    bare = Span.from_proto(_pb_span({}))
    assert (bare.scope_name, bare.scope_version) == ("", "")


def test_span_as_dict_threads_scope_for_call_resolution():
    span = _parsed_span(scope_name="codex", scope_version="1.4.0")
    otel_dump = span.as_dict()
    assert otel_dump["scope"] == {"name": "codex", "version": "1.4.0"}

    resolved = resolve_for_call(
        attributes={},
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump=otel_dump,
    )
    assert (resolved.name, resolved.version) == ("codex", "1.4.0")
