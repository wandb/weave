import datetime
import json
import logging

import pytest
from pydantic import BaseModel, ConfigDict

from weave.trace.refs import ObjectRef
from weave.trace_server.errors import InvalidExternalRef
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_converter import (
    InvalidInternalRef,
    replace_external_weave_ref,
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)
from weave.trace_server.trace_server_interface import (
    CallStartReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    StartedCallSchemaForInsert,
)


def test_universal_ext_to_int_ref_converter_reuses_models_and_untouched_branches():
    """COW: identity is preserved on subtrees with no ref rewrites."""
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/op/some-op:latest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/op/some-op:latest"
    started_at = datetime.datetime.now(datetime.timezone.utc)

    # No-op request: every container object should be reused by identity.
    no_ref_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id=internal_project_id,
            op_name="plain-op",
            started_at=started_at,
            attributes={"status": "ok"},
            inputs={"nested": {"value": "plain"}},
            otel_dump={"span": "plain"},
        )
    )
    original_no_ref_start = no_ref_req.start
    original_no_ref_inputs = no_ref_req.start.inputs
    original_no_ref_nested = no_ref_req.start.inputs["nested"]

    converted_no_ref = universal_ext_to_int_ref_converter(
        no_ref_req, lambda project: internal_project_id
    )

    assert converted_no_ref is no_ref_req
    assert converted_no_ref.start is original_no_ref_start
    assert converted_no_ref.start.inputs is original_no_ref_inputs
    assert converted_no_ref.start.inputs["nested"] is original_no_ref_nested

    # One rewritten ref: only the path to the changed value rebuilds, the
    # sibling subtree keeps identity.
    changed_branch = {"payload": ["plain", external_ref]}
    untouched_branch = {"keep": ["still", {"plain": "value"}]}
    req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id=internal_project_id,
            op_name=external_ref,
            started_at=started_at,
            attributes={"status": "ok"},
            inputs={
                "changed": changed_branch,
                "untouched": untouched_branch,
            },
            otel_dump={"span": "plain"},
        )
    )
    original_start = req.start
    original_inputs = req.start.inputs
    original_changed_branch = req.start.inputs["changed"]
    original_payload = req.start.inputs["changed"]["payload"]
    original_untouched_branch = req.start.inputs["untouched"]
    original_attributes = req.start.attributes
    original_otel_dump = req.start.otel_dump

    converted = universal_ext_to_int_ref_converter(
        req, lambda project: internal_project_id
    )

    assert converted is req
    assert converted.start is original_start
    assert converted.start.attributes is original_attributes
    assert converted.start.otel_dump is original_otel_dump
    assert converted.start.inputs is not original_inputs
    assert converted.start.inputs["changed"] is not original_changed_branch
    assert converted.start.inputs["changed"]["payload"] is not original_payload
    assert converted.start.inputs["untouched"] is original_untouched_branch
    assert converted.start.op_name == internal_ref
    assert converted.start.inputs["changed"]["payload"] == ["plain", internal_ref]

    # The pre-walk objects must stay untouched (proves COW, not in-place edit).
    assert original_payload == ["plain", external_ref]


def test_universal_ext_to_int_ref_converter_handles_aliased_query_models():
    """Query models with `$`-prefixed aliases still serialize via by_alias."""
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/object/name:digest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/name:digest"

    query = Query.model_validate(
        {
            "$expr": {
                "$eq": [
                    {"$literal": external_ref},
                    {"$literal": "plain"},
                ]
            }
        }
    )
    original_expr = query.expr_
    original_eq = query.expr_.eq_
    original_left_literal = query.expr_.eq_[0]

    converted = universal_ext_to_int_ref_converter(
        query, lambda project: internal_project_id
    )

    assert converted is query
    assert converted.expr_ is original_expr
    assert converted.expr_.eq_ is not original_eq
    assert converted.expr_.eq_[0] is original_left_literal
    aliased_query = converted.model_dump(by_alias=True)
    assert aliased_query["$expr"]["$eq"][0]["$literal"] == internal_ref
    assert aliased_query["$expr"]["$eq"][1]["$literal"] == "plain"


def test_universal_ext_to_int_ref_converter_roundtrips_models_with_any_payloads():
    """Nested dataclasses inside an `Any` field force the legacy roundtrip path."""
    req = ObjCreateReq(
        obj=ObjSchemaForInsert(
            project_id="entity/project",
            object_id="thing",
            val={
                "ref": ObjectRef(
                    entity="entity",
                    project="project",
                    name="name",
                    _digest="digest",
                ).with_attr("_class_name")
            },
        )
    )

    converted = universal_ext_to_int_ref_converter(
        req, lambda project: "internal-project"
    )

    assert isinstance(converted.obj.val["ref"], dict)
    json.dumps(converted.obj.val)


def test_universal_ext_to_int_ref_converter_rewrites_refs_in_model_extras():
    """Refs stored on a `extra='allow'` BaseModel must still be rewritten.

    The legacy converter walked the `model_dump(by_alias=True)` output,
    which includes fields collected into `model_extra`. The COW fast path
    iterates `model_fields` only, so extras are silently skipped unless
    `_walk_model` also walks them.
    """
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/op/some-op:latest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/op/some-op:latest"

    class ExtraAllowed(BaseModel):
        model_config = ConfigDict(extra="allow")
        declared: str

    model = ExtraAllowed.model_validate(
        {"declared": "plain", "extra_ref": external_ref}
    )

    converted = universal_ext_to_int_ref_converter(
        model, lambda project: internal_project_id
    )

    assert converted.declared == "plain"
    extras = converted.model_extra or {}
    assert extras.get("extra_ref") == internal_ref


def test_replace_external_weave_ref_uses_cache():
    """Shared cache amortizes ext→int_project_id lookups across calls.

    Callers that walk many refs (e.g. an OTel batch with the same
    entity/project on every span) pass a per-request dict so the
    underlying converter runs once per distinct project_key.
    """
    calls: list[str] = []

    def converter(project_key: str) -> str:
        calls.append(project_key)
        return f"internal:{project_key}"

    cache: dict[str, str] = {}

    a = replace_external_weave_ref("weave:///ent/proj/object/a:v1", converter, cache)
    b = replace_external_weave_ref("weave:///ent/proj/object/b:v1", converter, cache)
    c = replace_external_weave_ref("weave:///other/proj/object/c:v1", converter, cache)

    assert a == "weave-trace-internal:///internal:ent/proj/object/a:v1"
    assert b == "weave-trace-internal:///internal:ent/proj/object/b:v1"
    assert c == "weave-trace-internal:///internal:other/proj/object/c:v1"
    # Same entity/project resolves once, distinct one resolves again.
    assert calls == ["ent/proj", "other/proj"]


def test_replace_external_weave_ref_rejects_non_external_scheme():
    """Inputs not on the external scheme are a contract violation; the
    caller must precheck `startswith(weave_prefix)` before invoking.
    """
    with pytest.raises(ValueError, match="Invalid URI"):
        replace_external_weave_ref(
            "weave-trace-internal:///proj/object/a:v1", lambda p: p
        )


def test_replace_external_weave_ref_rejects_malformed_tail():
    """Refs missing the `entity/project/tail` triplet trip InvalidExternalRef
    so the caller surfaces the bad payload rather than silently passing it
    through.
    """
    with pytest.raises(InvalidExternalRef):
        replace_external_weave_ref("weave:///just-entity", lambda p: p)


@pytest.mark.disable_logging_error_check
def test_universal_int_to_ext_ref_converter_tolerate_external_refs(caplog):
    """Egress: internal refs externalize and unresolvable projects fall back to
    a private ref. A stored external ref raises by default (surfacing
    corruption), but is logged and passed through when tolerate_external_refs is
    set, so agent reads don't 500 on a ref their ingest path left external.
    """
    internal_project_id = "internal-project"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/name:digest"
    external_ref = "weave:///entity/project/object/name:digest"
    private_internal_ref = "weave-trace-internal:///private-project/object/name:digest"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project" if project_id == internal_project_id else None

    # Strict default: a stored external ref is a contract violation -> raise.
    with pytest.raises(InvalidInternalRef):
        universal_int_to_ext_ref_converter({"bad": external_ref}, int_to_ext)

    payload = {
        "resolved": internal_ref,
        "private": private_internal_ref,
        "stored_external": external_ref,
        "plain": "no-ref-here",
    }

    with caplog.at_level(logging.ERROR):
        converted = universal_int_to_ext_ref_converter(
            payload, int_to_ext, tolerate_external_refs=True
        )

    assert converted == {
        "resolved": external_ref,
        "private": "weave-private://///object/name:digest",
        "stored_external": external_ref,
        "plain": "no-ref-here",
    }
    assert "Returning stored external ref unchanged" in caplog.text
    assert external_ref in caplog.text


# ---------------------------------------------------------------------------
# Embedded refs inside JSON-serialized string leaves
#
# Agent message payloads store content as a JSON string (e.g.
# NormalizedMessage.content, tool_call_arguments, raw_span_dump). Refs buried
# inside those strings must convert with the SAME semantics as top-level ref
# leaves, or internal refs leak to external consumers on read and external refs
# leak into the DB on write.
# ---------------------------------------------------------------------------


def test_universal_int_to_ext_converts_ref_embedded_in_json_string():
    """A ref inside a JSON-string content field converts int->ext and the
    surrounding non-ref JSON is preserved.
    """
    internal_project_id = "internal-project"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/img:abc"
    external_ref = "weave:///entity/project/object/img:abc"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project" if project_id == internal_project_id else None

    content = json.dumps(
        [
            {"type": "image", "url": internal_ref},
            {"type": "text", "text": "hello world"},
        ]
    )
    converted = universal_int_to_ext_ref_converter({"content": content}, int_to_ext)

    assert json.loads(converted["content"]) == [
        {"type": "image", "url": external_ref},
        {"type": "text", "text": "hello world"},
    ]


def test_universal_ext_to_int_converts_ref_embedded_in_json_string():
    """A ref inside a JSON-string content field converts ext->int and the
    surrounding non-ref JSON is preserved.
    """
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/object/img:abc"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/img:abc"

    content = json.dumps(
        [
            {"type": "image", "url": external_ref},
            {"type": "text", "text": "hello world"},
        ]
    )
    converted = universal_ext_to_int_ref_converter(
        {"content": content}, lambda project: internal_project_id
    )

    assert json.loads(converted["content"]) == [
        {"type": "image", "url": internal_ref},
        {"type": "text", "text": "hello world"},
    ]


def test_universal_int_to_ext_converts_all_refs_in_nested_json_containers():
    """Every ref in a nested list/dict inside a JSON string converts."""
    internal_project_id = "internal-project"
    ref_a = f"weave-trace-internal:///{internal_project_id}/object/a:1"
    ref_b = f"weave-trace-internal:///{internal_project_id}/object/b:2"
    ext_a = "weave:///entity/project/object/a:1"
    ext_b = "weave:///entity/project/object/b:2"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project" if project_id == internal_project_id else None

    content = json.dumps(
        {
            "parts": [
                {"type": "image", "url": ref_a},
                {"nested": {"deep": ref_b}},
                {"type": "text", "text": "plain"},
            ]
        }
    )
    converted = universal_int_to_ext_ref_converter({"content": content}, int_to_ext)

    assert json.loads(converted["content"]) == {
        "parts": [
            {"type": "image", "url": ext_a},
            {"nested": {"deep": ext_b}},
            {"type": "text", "text": "plain"},
        ]
    }


def test_universal_int_to_ext_converts_ref_nested_two_json_levels():
    """A ref buried in a JSON string nested inside another JSON string converts
    (JSON-in-JSON within the depth cap).
    """
    internal_project_id = "internal-project"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/x:d"
    external_ref = "weave:///entity/project/object/x:d"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project" if project_id == internal_project_id else None

    inner = json.dumps({"url": internal_ref})
    outer = json.dumps({"raw": inner})

    converted = universal_int_to_ext_ref_converter(
        {"attributes_dump": outer}, int_to_ext
    )

    result = json.loads(converted["attributes_dump"])
    assert json.loads(result["raw"]) == {"url": external_ref}


@pytest.mark.parametrize(
    "prose",
    [
        "see weave-trace-internal:///internal-project/object/x:d for the image",
        "see weave:///entity/project/object/x:d for the image",
    ],
)
def test_embedded_path_leaves_non_json_prose_unchanged(prose):
    """A plain (non-JSON) string that merely contains a ref-like substring does
    not parse as JSON, so it is passed through unchanged (identity preserved).
    """

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project"

    payload = {"note": prose}
    converted = universal_int_to_ext_ref_converter(payload, int_to_ext)

    assert converted is payload
    assert converted["note"] is prose


def test_json_string_without_refs_is_not_reserialized():
    """A JSON string with no ref never reaches json.loads (the substring guard
    fails) and is returned byte-identical (identity preserved, no re-dump).
    """

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project"

    blob = '[{"type": "text", "text": "hello"}]'
    payload = {"content": blob}
    converted = universal_int_to_ext_ref_converter(payload, int_to_ext)

    assert converted is payload
    assert converted["content"] is blob


@pytest.mark.disable_logging_error_check
def test_json_string_with_only_tolerated_external_ref_is_returned_unchanged(caplog):
    """When an embedded ref does not change (already-external + tolerate), the
    ORIGINAL string is returned with no re-serialization (spacing preserved).
    """
    external_ref = "weave:///entity/project/object/x:d"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project"

    # Non-canonical spacing (indent) so a gratuitous re-dump would change bytes.
    blob = json.dumps([{"type": "image", "url": external_ref}], indent=2)
    payload = {"content": blob}

    with caplog.at_level(logging.ERROR):
        converted = universal_int_to_ext_ref_converter(
            payload, int_to_ext, tolerate_external_refs=True
        )

    assert converted is payload
    assert converted["content"] is blob
    assert "Returning stored external ref unchanged" in caplog.text


@pytest.mark.disable_logging_error_check
def test_embedded_external_ref_respects_tolerate_flag_int_to_ext(caplog):
    """An embedded external ref obeys the same tolerate/raise policy as a
    top-level external ref on the int->ext path.
    """
    external_ref = "weave:///entity/project/object/x:d"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project"

    content = json.dumps([{"type": "image", "url": external_ref}])
    payload = {"content": content}

    # Strict default: embedded external ref raises, same as top-level.
    with pytest.raises(InvalidInternalRef):
        universal_int_to_ext_ref_converter(payload, int_to_ext)

    # Tolerant: passed through + logged, embedded JSON preserved unchanged.
    with caplog.at_level(logging.ERROR):
        converted = universal_int_to_ext_ref_converter(
            payload, int_to_ext, tolerate_external_refs=True
        )

    assert json.loads(converted["content"]) == [{"type": "image", "url": external_ref}]
    assert "Returning stored external ref unchanged" in caplog.text


def test_embedded_internal_ref_requires_verification_ext_to_int():
    """An embedded internal ref on the ext->int path goes through the same
    verify_internal_project_id gate as a top-level internal ref.
    """
    internal_project_id = "internal-project"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/x:d"
    content = json.dumps([{"type": "image", "url": internal_ref}])
    payload = {"content": content}

    # No verify callback -> embedded internal ref rejected, same as top-level.
    with pytest.raises(InvalidExternalRef):
        universal_ext_to_int_ref_converter(
            payload,
            lambda project: "should-not-be-called",
            verify_internal_project_id=None,
        )

    # verify accepts -> embedded internal ref passed through unchanged.
    converted = universal_ext_to_int_ref_converter(
        payload,
        lambda project: "unused",
        verify_internal_project_id=lambda pid: pid == internal_project_id,
    )
    assert json.loads(converted["content"]) == [{"type": "image", "url": internal_ref}]


def test_deeply_nested_json_in_json_terminates_without_recursion_error():
    """Deeply nested JSON-in-JSON hits the depth cap and terminates without
    raising RecursionError (a ref below the cap simply is not descended into).
    """
    internal_project_id = "internal-project"
    ref = f"weave-trace-internal:///{internal_project_id}/object/x:d"

    def int_to_ext(project_id: str) -> str | None:
        return "entity/project" if project_id == internal_project_id else None

    # Nest well beyond the depth cap. Each json.dumps of a string only escapes
    # quotes/backslashes, so this stays small while nesting deeply.
    nested = ref
    for _ in range(12):
        nested = json.dumps(nested)
    payload = {"content": nested}

    converted = universal_int_to_ext_ref_converter(payload, int_to_ext)

    # Termination + no RecursionError is the contract; the buried ref is below
    # the cap so the string comes back unchanged.
    assert converted["content"] == nested
