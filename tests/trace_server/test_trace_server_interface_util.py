import base64
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from weave.shared.trace_server_interface_util import extract_refs_from_values
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
    IdConverter,
)

REF_A = "weave-trace-internal:///test_project/object/obj_a:abc123"
REF_B = "weave-trace-internal:///test_project/object/obj_b:def456"


def test_extract_refs_from_values_deduplicates():
    """Requirement: input_refs/output_refs must not contain duplicate ref URIs.
    Interface: extract_refs_from_values(vals) -> list[str]
    Given: inputs containing the same ref URI multiple times via different structures
    When: extract_refs_from_values is called
    Then: each ref URI appears at most once in the result
    """
    # Same ref twice as sibling dict values
    assert extract_refs_from_values({"a": REF_A, "b": REF_A}) == [REF_A]

    # Same ref twice in a list
    assert extract_refs_from_values([REF_A, REF_A]) == [REF_A]

    # Same ref in nested structures
    assert extract_refs_from_values({"x": {"nested": REF_A}, "y": REF_A}) == [REF_A]

    # Multiple distinct refs — each appears exactly once
    result = extract_refs_from_values({"a": REF_A, "b": REF_B})
    assert sorted(result) == sorted([REF_A, REF_B])
    assert len(result) == 2

    # No refs — empty result
    assert extract_refs_from_values({"a": "hello", "b": 42}) == []


# --- ExternalTraceServer mutation-invariance regression (PR #6670) ---
# Before #6670, the adapter mutated `req.project_id` in place when
# translating external entity/project strings to internal base64 form.
# A retry layer above the adapter would re-invoke the same `req` — which
# now held an already-internal project_id — and the adapter would encode
# it a second time, producing base64(base64(...)) garbage and querying a
# nonexistent project. Parametrized across methods covering the distinct
# mutation shapes (flat, nested obj/table, filter-carrying).


class _EncodingIdConverter(IdConverter):
    """Base64 ext<->int just like the real converter, so double-encoding
    would be observable as a materially different string.
    """

    def ext_to_int_project_id(self, project_id: str) -> str:
        return base64.b64encode(project_id.encode()).decode()

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        try:
            return base64.b64decode(project_id.encode()).decode()
        except Exception:
            return None

    def ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


@pytest.mark.parametrize(
    ("method_name", "req_factory"),
    [
        (
            "obj_read",
            lambda: tsi.ObjReadReq(project_id="ent/proj", object_id="o", digest="d"),
        ),
        (
            "obj_create",
            lambda: tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id="ent/proj", object_id="o", val={}, wb_user_id="u"
                )
            ),
        ),
        (
            "table_create",
            lambda: tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(project_id="ent/proj", rows=[])
            ),
        ),
        (
            "file_content_read",
            lambda: tsi.FileContentReadReq(project_id="ent/proj", digest="d"),
        ),
        (
            "calls_query",
            lambda: tsi.CallsQueryReq(
                project_id="ent/proj",
                filter=tsi.CallsFilter(wb_user_ids=["user-x"], wb_run_ids=["run-y"]),
            ),
        ),
    ],
)
def test_adapter_does_not_mutate_req_when_inner_raises(
    method_name: str, req_factory: Callable[[], Any]
) -> None:
    """Regression for the adapter-mutates-req bug. On failure, the
    caller's `req` must be byte-identical so a retry layer above can
    re-invoke with the original external project_id.
    """
    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    getattr(inner, method_name).side_effect = NotFoundError("test")
    adapter = ExternalTraceServer(inner, _EncodingIdConverter())

    req = req_factory()
    snapshot = req.model_dump()

    with pytest.raises(NotFoundError):
        getattr(adapter, method_name)(req)

    assert req.model_dump() == snapshot


# --- genai_otel_export ext→int ref rewriting in OTel attribute values ---
# Refs in the typed `weave.{content,artifact,object}_refs` OTel attribute
# arrays are not reachable by the universal `_ref_apply` walker (the
# protobuf ResourceSpans is `arbitrary_types_allowed=True`), so the
# adapter rewrites them in place before forwarding to the inner server.


def _make_otel_export_req_with_ref_attrs(
    ext_refs_by_key: dict[str, list[str]],
    *,
    nest_under_kvlist: bool = False,
    project_id: str = "ent/proj",
) -> tsi.agent_types.GenAIOTelExportReq:
    """Build a `GenAIOTelExportReq` carrying `weave.*_refs` OTel attrs.

    When `nest_under_kvlist` is True, encodes attributes under a single
    `weave` kvlist parent (the form some OTel SDKs emit) instead of the
    flat-dotted `weave.object_refs` form.
    """
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.trace.v1.trace_pb2 import (
        ResourceSpans,
        ScopeSpans,
        Span,
    )

    def build_array_value(refs: list[str]) -> AnyValue:
        v = AnyValue()
        v.array_value.values.extend([AnyValue(string_value=ref) for ref in refs])
        return v

    span = Span()
    span.name = "test"
    if nest_under_kvlist:
        weave_kv = KeyValue(key="weave")
        for short_key, refs in ext_refs_by_key.items():
            child = KeyValue(key=short_key)
            child.value.CopyFrom(build_array_value(refs))
            weave_kv.value.kvlist_value.values.append(child)
        span.attributes.append(weave_kv)
    else:
        for full_key, refs in ext_refs_by_key.items():
            kv = KeyValue(key=full_key)
            kv.value.CopyFrom(build_array_value(refs))
            span.attributes.append(kv)
    # Non-ref attributes must survive unchanged.
    other = KeyValue(key="weave.raw_span_dump")
    other.value.string_value = "weave:///should/not/be/rewritten"
    span.attributes.append(other)

    scope_spans = ScopeSpans()
    scope_spans.spans.append(span)
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(Resource())
    resource_spans.scope_spans.append(scope_spans)

    processed = tsi.ProcessedResourceSpans(
        entity=project_id.split("/", maxsplit=1)[0],
        project=project_id.split("/")[1],
        run_id=None,
        resource_spans=resource_spans,
    )
    return tsi.agent_types.GenAIOTelExportReq(
        processed_spans=[processed], project_id=project_id, wb_user_id=None
    )


def _capture_genai_otel_export_req(
    req: tsi.agent_types.GenAIOTelExportReq,
) -> tsi.agent_types.GenAIOTelExportReq:
    """Run the request through the adapter and return the req the inner
    trace server actually received.
    """
    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    inner.genai_otel_export.return_value = tsi.agent_types.GenAIOTelExportRes()
    adapter = ExternalTraceServer(inner, _EncodingIdConverter())
    adapter.genai_otel_export(req)
    assert inner.genai_otel_export.call_count == 1
    return inner.genai_otel_export.call_args.args[0]


def _ref_attr_values(
    req: tsi.agent_types.GenAIOTelExportReq, attr_key: str
) -> list[str]:
    """Pull values out of a `weave.<short_key>` attribute, regardless of
    whether they were encoded flat-dotted or nested under a `weave`
    kvlist.
    """
    short_key = attr_key.split(".", 1)[1]
    span = req.processed_spans[0].resource_spans.scope_spans[0].spans[0]
    for kv in span.attributes:
        if kv.key == attr_key and kv.value.HasField("array_value"):
            return [v.string_value for v in kv.value.array_value.values]
        if kv.key == "weave" and kv.value.HasField("kvlist_value"):
            for child in kv.value.kvlist_value.values:
                if child.key == short_key and child.value.HasField("array_value"):
                    return [v.string_value for v in child.value.array_value.values]
    raise AssertionError(f"no values for {attr_key}")


def test_genai_otel_export_rewrites_ref_attrs() -> None:
    """ext->int rewriting of typed `weave.*_refs` OTel arrays: flat-dotted keys
    (object_refs + content_refs) and the nested `weave` kvlist form both get
    rewritten, while non-external array elements (already-internal, non-ref
    strings) pass through unchanged.
    """
    internal_proj = _EncodingIdConverter().ext_to_int_project_id("ent/proj")

    flat = _capture_genai_otel_export_req(
        _make_otel_export_req_with_ref_attrs(
            {
                "weave.object_refs": [
                    "weave:///ent/proj/object/a:v1",
                    "weave:///ent/proj/object/b:v1",
                ],
                "weave.content_refs": ["weave:///ent/proj/content/c"],
            }
        )
    )
    assert _ref_attr_values(flat, "weave.object_refs") == [
        f"weave-trace-internal:///{internal_proj}/object/a:v1",
        f"weave-trace-internal:///{internal_proj}/object/b:v1",
    ]
    assert _ref_attr_values(flat, "weave.content_refs") == [
        f"weave-trace-internal:///{internal_proj}/content/c"
    ]

    # Nested `weave` -> `object_refs` kvlist: walker descends and matches the dotted key.
    nested = _capture_genai_otel_export_req(
        _make_otel_export_req_with_ref_attrs(
            {"object_refs": ["weave:///ent/proj/object/a:v1"]},
            nest_under_kvlist=True,
        )
    )
    assert _ref_attr_values(nested, "weave.object_refs") == [
        f"weave-trace-internal:///{internal_proj}/object/a:v1"
    ]

    # Only matching external `weave:///` prefixes convert; others pass through.
    mixed = _capture_genai_otel_export_req(
        _make_otel_export_req_with_ref_attrs(
            {
                "weave.object_refs": [
                    "weave:///ent/proj/object/a:v1",
                    "weave-trace-internal:///already-internal/object/b:v1",
                    "not-a-ref-at-all",
                ]
            }
        )
    )
    assert _ref_attr_values(mixed, "weave.object_refs") == [
        f"weave-trace-internal:///{internal_proj}/object/a:v1",
        "weave-trace-internal:///already-internal/object/b:v1",
        "not-a-ref-at-all",
    ]


def test_genai_otel_export_leaves_non_ref_attrs_untouched() -> None:
    """Refs embedded in non-ref attributes (here `weave.raw_span_dump`)
    must survive byte-for-byte — only the three typed-array ref keys are
    rewritten.
    """
    req = _make_otel_export_req_with_ref_attrs(
        {"weave.object_refs": ["weave:///ent/proj/object/a:v1"]}
    )

    forwarded = _capture_genai_otel_export_req(req)
    span = forwarded.processed_spans[0].resource_spans.scope_spans[0].spans[0]
    dump_kv = next(kv for kv in span.attributes if kv.key == "weave.raw_span_dump")
    assert dump_kv.value.string_value == "weave:///should/not/be/rewritten"


def test_genai_otel_export_caches_project_id_lookup_across_batch() -> None:
    """A single per-request cache means ext→int_project_id runs once per
    distinct entity/project pair, even across many spans and many refs.
    """
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.trace.v1.trace_pb2 import (
        ResourceSpans,
        ScopeSpans,
        Span,
    )

    class CountingIdConverter(_EncodingIdConverter):
        def __init__(self) -> None:
            self.ext_to_int_calls: list[str] = []

        def ext_to_int_project_id(self, project_id: str) -> str:
            self.ext_to_int_calls.append(project_id)
            return super().ext_to_int_project_id(project_id)

    # Three spans, each carrying two refs for the same entity/project.
    scope_spans = ScopeSpans()
    for _ in range(3):
        span = Span()
        kv = KeyValue(key="weave.object_refs")
        kv.value.array_value.values.extend(
            [
                AnyValue(string_value="weave:///ent/proj/object/a:v1"),
                AnyValue(string_value="weave:///ent/proj/object/b:v1"),
            ]
        )
        span.attributes.append(kv)
        scope_spans.spans.append(span)
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(Resource())
    resource_spans.scope_spans.append(scope_spans)
    processed = tsi.ProcessedResourceSpans(
        entity="ent",
        project="proj",
        run_id=None,
        resource_spans=resource_spans,
    )
    req = tsi.agent_types.GenAIOTelExportReq(
        processed_spans=[processed], project_id="ent/proj", wb_user_id=None
    )

    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    inner.genai_otel_export.return_value = tsi.agent_types.GenAIOTelExportRes()
    converter = CountingIdConverter()
    ExternalTraceServer(inner, converter).genai_otel_export(req)

    # One call for `req.project_id` translation + exactly one more for the
    # rewrite cache (not 6 — one per ref).
    assert converter.ext_to_int_calls == ["ent/proj", "ent/proj"]
