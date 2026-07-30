"""Unit tests for the source-attribution resolution ladder.

Covers `source_attribution` in isolation, its use by the spans extraction path,
and the `Span.as_dict` -> `resolve_for_call` handoff that lets the calls path
reach a span's scope.
"""

import datetime
import uuid
from pathlib import Path

import pytest
from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource as PbResource
from opentelemetry.proto.trace.v1.trace_pb2 import ScopeSpans as PbScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan

from weave.trace_server import source_attribution
from weave.trace_server.agents import semconv
from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span
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
            # Rung 1, nested: the integration block beats scope.
            "nested_integration_wins",
            {"integration": {"name": "openai", "version": "0.53.1"}},
            ("opentelemetry.instrumentation.openai", "0.62b1"),
            ("openai", "0.53.1"),
        ),
        (
            # Rung 1, flat: what `as_otel_attributes()` actually puts on a span.
            "flat_integration_keys",
            {"integration.name": "langchain", "integration.version": "0.54.0"},
            ("", ""),
            ("langchain", "0.54.0"),
        ),
        (
            # The canonical weave.* key outranks the integration.* alias.
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
            # Version does not cross rungs: rung 1 resolved the name, so the
            # scope's version must not be borrowed.
            "version_never_crosses_rungs",
            {"integration.name": "custom_harness"},
            ("codex", "1.4.0"),
            ("custom_harness", ""),
        ),
        (
            # Rung 2: raw-OTel senders get attributed for free.
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
            # A bare prefix with nothing after it is not stripped to ''.
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
            # Whitespace-only values count as absent at every rung.
            "blank_values_fall_through",
            {"integration.name": "   "},
            ("  ", "1.0"),
            ("", ""),
        ),
        (
            # A non-scalar integration name is not stringified into a column.
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
    # Every OTLP-ingested row is tagged with its surface regardless of rung.
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

    # An OTel-converted call can resolve scope from otel_dump.
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

    # Normalized call attributes take precedence over the raw OTel fallback.
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

    # Client attributes and otel_dump cannot override authoritative context.
    spoofed = resolve_for_call(
        attributes={"weave.ingest_source": "otlp"},
        ingest_source=INGEST_SOURCE_WEAVE,
        otel_dump={"name": "chat"},
    )
    assert spoofed.ingest_source == INGEST_SOURCE_WEAVE


def test_source_keys_registered_in_semconv():
    """The columns are filterable and excluded from the custom-attr overflow maps."""
    for attribute, column in (
        (semconv.SOURCE_NAME, "source_name"),
        (semconv.SOURCE_VERSION, "source_version"),
        (semconv.INGEST_SOURCE, "ingest_source"),
    ):
        assert semconv.CANONICAL_KEY_TO_COLUMN[attribute.key] == column
        assert semconv.FILTERABLE_KEY_TO_COLUMN[attribute.key] == column
        # Short-form, with the weave. prefix stripped.
        assert (
            semconv.FILTERABLE_KEY_TO_COLUMN[attribute.key[len("weave.") :]] == column
        )

    # The integration.* aliases resolve to the same columns and are known keys,
    # so `_extract_custom_attrs` skips them.
    assert semconv.resolve_alias_to_canonical("integration.name") == (
        semconv.SOURCE_NAME.key
    )
    assert "integration.name" in semconv.KNOWN_KEYS
    assert "integration.version" in semconv.KNOWN_KEYS
    # `integration.meta.*` is dynamic and deliberately stays in custom attrs.
    assert "integration.meta.package_name" not in semconv.KNOWN_KEYS


def test_integration_attribute_key_matches_the_sdk_producer():
    """Pin the client/server contract the import-linter stops us from sharing.

    The trace server may not import `weave.integrations`, so the integration key
    is restated in semconv. If the SDK ever renames it, the ladder would silently
    stop attributing every stamped integration.
    """
    from weave.integrations.integration_metadata import (
        INTEGRATION_ATTRIBUTE_KEY,
        IntegrationMetadata,
    )

    assert f"{INTEGRATION_ATTRIBUTE_KEY}.name" in semconv.SOURCE_NAME.lookup_keys
    assert f"{INTEGRATION_ATTRIBUTE_KEY}.version" in semconv.SOURCE_VERSION.lookup_keys

    # Both renderings the Python SDK emits resolve through the ladder identically.
    metadata = IntegrationMetadata(
        name="openai", version="0.53.1", meta={"package_name": "openai"}
    )
    nested = resolve_for_otel_span(attributes=metadata.as_attributes())
    flat = resolve_for_otel_span(attributes=metadata.as_otel_attributes())
    assert (nested.name, nested.version) == ("openai", "0.53.1")
    assert flat == nested


def test_node_sdk_integration_keys_are_accepted():
    """The node SDK emits a different spelling; both must land in the columns.

    `sdks/node/src/genai/semconv.ts` uses `weave.integration.*` where the Python
    SDK uses `integration.*`. Until the two converge the server accepts either,
    so node-emitted OTel spans are attributed without a client release.
    """
    node_keys_path = "sdks/node/src/genai/semconv.ts"
    source = (Path(__file__).parents[2] / node_keys_path).read_text()
    for const, expected in (
        ("WEAVE_INTEGRATION_NAME", "weave.integration.name"),
        ("WEAVE_INTEGRATION_VERSION", "weave.integration.version"),
    ):
        assert f"export const {const} = '{expected}';" in source, (
            f"{node_keys_path} no longer defines {const} as {expected!r}"
        )

    assert "weave.integration.name" in semconv.SOURCE_NAME.lookup_keys
    assert "weave.integration.version" in semconv.SOURCE_VERSION.lookup_keys

    resolved = resolve_for_otel_span(
        attributes={
            "weave.integration.name": "openai",
            "weave.integration.version": "0.9.2",
            "weave.integration.meta.package_name": "openai",
        }
    )
    assert (resolved.name, resolved.version) == ("openai", "0.9.2")


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
    """Parse a real OTel proto span through ScopeSpans, as ingest does."""
    scope = InstrumentationScope()
    scope.name = scope_name
    scope.version = scope_version
    proto_scope_spans = PbScopeSpans()
    proto_scope_spans.scope.CopyFrom(scope)
    proto_scope_spans.spans.append(_pb_span(attributes or {}))
    resource = Resource.from_proto(_pb_resource(resource_attributes or {}))
    return ScopeSpans.from_proto(proto_scope_spans, resource).spans[0]


def test_scope_survives_proto_parsing_into_the_span():
    """`ScopeSpans.from_proto` threads scope identity onto each Span."""
    span = _parsed_span(scope_name="codex", scope_version="1.4.0")
    assert (span.scope_name, span.scope_version) == ("codex", "1.4.0")

    # A span parsed without a scope is not a crash and not attributed by rung 2.
    bare = Span.from_proto(_pb_span({}))
    assert (bare.scope_name, bare.scope_version) == ("", "")


def test_extract_genai_span_fills_source_columns_from_scope():
    """A raw-OTel sender that stamps nothing is still attributed via its scope."""
    span = _parsed_span(
        attributes={"gen_ai.operation.name": "chat"},
        scope_name="opentelemetry.instrumentation.openai",
        scope_version="0.62b1",
        resource_attributes={"service.name": "codex"},
    )
    row = extract_genai_span(span, project_id="proj")

    assert (row.source_name, row.source_version, row.ingest_source) == (
        "openai",
        "0.62b1",
        INGEST_SOURCE_OTLP,
    )


def test_extract_genai_span_promotes_integration_attrs_out_of_custom_attrs():
    """`integration.{name,version}` become columns; only `meta.*` stays a custom attr."""
    span = _parsed_span(
        attributes={
            "integration.name": "openai",
            "integration.version": "0.53.1",
            "integration.meta.package_name": "openai",
            "integration.meta.package_version": "1.99.0",
        },
        scope_name="should-not-win",
    )
    row = extract_genai_span(span, project_id="proj")

    assert (row.source_name, row.source_version) == ("openai", "0.53.1")
    assert "integration.name" not in row.custom_attrs_string
    assert "integration.version" not in row.custom_attrs_string
    assert row.custom_attrs_string["integration.meta.package_name"] == "openai"
    assert row.custom_attrs_string["integration.meta.package_version"] == "1.99.0"


def test_extract_genai_span_unattributable_leaves_name_empty():
    span = _parsed_span(attributes={"gen_ai.request.model": "gpt-5"})
    row = extract_genai_span(span, project_id="proj")

    assert (row.source_name, row.source_version) == ("", "")
    # The surface is still recorded, so `ingest_source` can size raw-OTLP traffic
    # even for rows nothing else identifies.
    assert row.ingest_source == INGEST_SOURCE_OTLP


def test_otel_dump_carries_scope_so_the_calls_path_agrees_with_the_spans_path():
    """`Span.as_dict` is the calls path's only route to scope; keep it in sync.

    Both paths must reach the same name/version for the same span, or a call and
    its sibling span would disagree about who produced them.
    """
    span = _parsed_span(
        attributes={"gen_ai.operation.name": "chat"},
        scope_name="openinference.instrumentation.bedrock",
        scope_version="0.3.1",
        resource_attributes={"service.name": "svc", "service.version": "2"},
    )
    otel_dump = span.as_dict()

    assert otel_dump["scope"] == {
        "name": "openinference.instrumentation.bedrock",
        "version": "0.3.1",
    }

    span_row = extract_genai_span(span, project_id="proj")
    call_resolved = resolve_for_call(
        attributes={},
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump=otel_dump,
    )
    assert (call_resolved.name, call_resolved.version) == (
        span_row.source_name,
        span_row.source_version,
    )
    assert call_resolved.name == "bedrock"

    # Resource service identity is not instrumentation attribution.
    scopeless = _parsed_span(
        resource_attributes={"service.name": "svc", "service.version": "2"}
    )
    scopeless_row = extract_genai_span(scopeless, project_id="proj")
    scopeless_call = resolve_for_call(
        attributes={},
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump=scopeless.as_dict(),
    )
    assert (scopeless_call.name, scopeless_call.version) == ("", "")
    assert (scopeless_row.source_name, scopeless_row.source_version) == ("", "")

    # Explicit OTel attrs survive only in otel_dump after Span.to_call narrows them.
    explicit = _parsed_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt-5",
            "integration.name": "openai",
            "integration.version": "0.53.1",
        },
        scope_name="opentelemetry.instrumentation.httpx",
        scope_version="0.1.0",
    )
    explicit_row = extract_genai_span(explicit, project_id="proj")
    start, _ = explicit.to_call("proj")
    explicit_call = resolve_for_call(
        attributes=start.attributes,
        ingest_source=INGEST_SOURCE_OTLP,
        otel_dump=start.otel_dump,
    )
    assert (
        (explicit_call.name, explicit_call.version)
        == (
            explicit_row.source_name,
            explicit_row.source_version,
        )
        == ("openai", "0.53.1")
    )
