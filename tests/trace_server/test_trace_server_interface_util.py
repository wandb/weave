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
