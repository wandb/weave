import datetime
import json

import pytest
from pydantic import BaseModel, ConfigDict

from weave.trace.refs import ObjectRef
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_converter import (
    InvalidInternalRef,
    make_int_to_ext_ref_mapper,
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


def test_make_int_to_ext_ref_mapper_shares_cache_across_items():
    """One mapper applied to N stream items reuses the project_id cache.

    The resolver should be hit exactly once per distinct internal
    project_id even when the mapper is applied to many items, and the
    rewrites for each item must land correctly when items reference
    different projects. Ref-free items must preserve identity (COW
    behavior inherited from `_map_values`), and a malformed internal ref
    must raise without poisoning the cache for subsequent items.
    """
    int_a, ext_a = "proj-a-internal", "ent-a/proj-a"
    int_b, ext_b = "proj-b-internal", "ent-b/proj-b"
    int_private = "proj-private"  # resolver returns None -> rewrites to private scheme

    resolver_calls: list[str] = []

    def resolver(project_id: str) -> str | None:
        resolver_calls.append(project_id)
        if project_id == int_a:
            return ext_a
        if project_id == int_b:
            return ext_b
        return None  # inaccessible -> private scheme

    mapper = make_int_to_ext_ref_mapper(resolver)

    # Item 1: hits project A. Resolver MUST be called.
    item_a = {"ref": f"weave-trace-internal:///{int_a}/op/foo:v1"}
    out_a = mapper(item_a)
    assert out_a == {"ref": f"weave:///{ext_a}/op/foo:v1"}
    assert resolver_calls == [int_a]

    # Item 2: same project as item 1. Resolver MUST NOT be called again
    # (this is the whole point of hoisting the mapper out of the loop).
    item_a2 = {"ref": f"weave-trace-internal:///{int_a}/op/bar:v2"}
    out_a2 = mapper(item_a2)
    assert out_a2 == {"ref": f"weave:///{ext_a}/op/bar:v2"}
    assert resolver_calls == [int_a]

    # Item 3: new project. Resolver called exactly once for B.
    item_b = {"ref": f"weave-trace-internal:///{int_b}/op/baz:v3"}
    out_b = mapper(item_b)
    assert out_b == {"ref": f"weave:///{ext_b}/op/baz:v3"}
    assert resolver_calls == [int_a, int_b]

    # Item 4: ref-free. Identity preserved (COW inherited), resolver untouched.
    item_plain: dict[str, object] = {"plain": ["a", "b", {"nested": 1}]}
    out_plain = mapper(item_plain)
    assert out_plain is item_plain
    assert resolver_calls == [int_a, int_b]

    # Item 5: inaccessible project (resolver returns None). Cached None is
    # honored on the next item without a second resolver call.
    item_private = {"ref": f"weave-trace-internal:///{int_private}/op/x:v1"}
    out_private = mapper(item_private)
    assert out_private == {"ref": "weave-private://///op/x:v1"}
    assert resolver_calls == [int_a, int_b, int_private]

    item_private2 = {"ref": f"weave-trace-internal:///{int_private}/op/y:v2"}
    out_private2 = mapper(item_private2)
    assert out_private2 == {"ref": "weave-private://///op/y:v2"}
    assert resolver_calls == [int_a, int_b, int_private]

    # Item 6: external ref appearing on the internal->external path is a
    # corruption signal and must raise. Cache from earlier items survives.
    item_bad = {"ref": f"weave:///{ext_a}/op/leaked:v1"}
    with pytest.raises(InvalidInternalRef):
        mapper(item_bad)

    item_a3 = {"ref": f"weave-trace-internal:///{int_a}/op/qux:v4"}
    out_a3 = mapper(item_a3)
    assert out_a3 == {"ref": f"weave:///{ext_a}/op/qux:v4"}
    assert resolver_calls == [int_a, int_b, int_private]
