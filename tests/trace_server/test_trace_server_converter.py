import datetime
import json

import pytest
from pydantic import BaseModel, ConfigDict

from weave.trace.refs import ObjectRef
from weave.trace_server.errors import InvalidExternalRef
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_converter import (
    replace_external_weave_ref,
    universal_ext_to_int_ref_converter,
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


def test_universal_ext_to_int_ref_converter_variant_payloads():
    """Converter handles aliased Query models, `Any`-field dataclass roundtrips,
    and refs stored in `extra='allow'` model extras.
    """
    internal_project_id = "internal-project"
    external_ref = "weave:///entity/project/object/name:digest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/name:digest"

    # `$`-prefixed query aliases still serialize via by_alias; the rewritten
    # literal rebuilds while the untouched literal keeps identity.
    query = Query.model_validate(
        {"$expr": {"$eq": [{"$literal": external_ref}, {"$literal": "plain"}]}}
    )
    original_expr = query.expr_
    original_eq = query.expr_.eq_
    original_left_literal = query.expr_.eq_[0]

    converted_query = universal_ext_to_int_ref_converter(
        query, lambda project: internal_project_id
    )
    assert converted_query is query
    assert converted_query.expr_ is original_expr
    assert converted_query.expr_.eq_ is not original_eq
    assert converted_query.expr_.eq_[0] is original_left_literal
    aliased_query = converted_query.model_dump(by_alias=True)
    assert aliased_query["$expr"]["$eq"][0]["$literal"] == internal_ref
    assert aliased_query["$expr"]["$eq"][1]["$literal"] == "plain"

    # Nested dataclasses inside an `Any` field force the legacy roundtrip path.
    any_req = ObjCreateReq(
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
    converted_any = universal_ext_to_int_ref_converter(
        any_req, lambda project: "internal-project"
    )
    assert isinstance(converted_any.obj.val["ref"], dict)
    json.dumps(converted_any.obj.val)

    # Refs collected into `model_extra` must still be rewritten.
    op_external = "weave:///entity/project/op/some-op:latest"
    op_internal = f"weave-trace-internal:///{internal_project_id}/op/some-op:latest"
    model = _ExtraAllowed.model_validate(
        {"declared": "plain", "extra_ref": op_external}
    )
    converted_extra = universal_ext_to_int_ref_converter(
        model, lambda project: internal_project_id
    )
    assert converted_extra.declared == "plain"
    extras = converted_extra.model_extra or {}
    assert extras.get("extra_ref") == op_internal


def test_replace_external_weave_ref_cache_and_rejections():
    """Shared cache amortizes ext->int lookups; non-external scheme and
    malformed tails are contract violations that raise.
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

    with pytest.raises(ValueError, match="Invalid URI"):
        replace_external_weave_ref(
            "weave-trace-internal:///proj/object/a:v1", lambda p: p
        )

    with pytest.raises(InvalidExternalRef):
        replace_external_weave_ref("weave:///just-entity", lambda p: p)


class _ExtraAllowed(BaseModel):
    model_config = ConfigDict(extra="allow")
    declared: str
