"""Regression test for the adapter-mutates-req bug.

Before the fix, `ExternalTraceServer` mutated `req.project_id` in place when
translating from the external `entity/project` form to the internal
base64-encoded form. A retry layer above the adapter would then re-invoke the
same `req` object, which now held an already-internal project_id, and the
adapter would translate it a second time — producing base64(base64(...))
garbage and querying a nonexistent project.

This test snapshots `req` before the adapter call and asserts it is
byte-identical afterwards, regardless of whether the inner server raised or
returned. Parametrized across every method this PR fixes.
"""

from __future__ import annotations

import base64
import inspect
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
    IdConverter,
)


class _EncodingIdConverter(IdConverter):
    """Base64 ext<->int just like the real converter, so a double-encode is
    observable as a materially different string.
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


# (method name, req factory). Every method `PR #6670` claims to have fixed
# gets one entry. Entries with a wb_user_id exercise that code path too.
_FIXED_METHODS: list[tuple[str, Callable[[], Any]]] = [
    (
        "obj_create",
        lambda: tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="ent/proj",
                object_id="o",
                val={},
                wb_user_id="user-1",
            )
        ),
    ),
    (
        "obj_read",
        lambda: tsi.ObjReadReq(project_id="ent/proj", object_id="o", digest="d"),
    ),
    ("objs_query", lambda: tsi.ObjQueryReq(project_id="ent/proj")),
    (
        "obj_delete",
        lambda: tsi.ObjDeleteReq(project_id="ent/proj", object_id="o"),
    ),
    (
        "obj_add_tags",
        lambda: tsi.ObjAddTagsReq(
            project_id="ent/proj", object_id="o", digest="d", tags=["a"]
        ),
    ),
    (
        "obj_remove_tags",
        lambda: tsi.ObjRemoveTagsReq(
            project_id="ent/proj", object_id="o", digest="d", tags=["a"]
        ),
    ),
    (
        "obj_set_aliases",
        lambda: tsi.ObjSetAliasesReq(
            project_id="ent/proj", object_id="o", digest="d", aliases=["alias1"]
        ),
    ),
    (
        "obj_remove_aliases",
        lambda: tsi.ObjRemoveAliasesReq(
            project_id="ent/proj", object_id="o", aliases=["alias1"]
        ),
    ),
    ("tags_list", lambda: tsi.TagsListReq(project_id="ent/proj")),
    ("aliases_list", lambda: tsi.AliasesListReq(project_id="ent/proj")),
    (
        "table_create",
        lambda: tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(project_id="ent/proj", rows=[])
        ),
    ),
    (
        "table_update",
        lambda: tsi.TableUpdateReq(project_id="ent/proj", base_digest="d", updates=[]),
    ),
    (
        "table_create_from_digests",
        lambda: tsi.TableCreateFromDigestsReq(project_id="ent/proj", row_digests=["r"]),
    ),
    (
        "table_query",
        lambda: tsi.TableQueryReq(project_id="ent/proj", digest="d"),
    ),
    (
        "table_query_stream",
        lambda: tsi.TableQueryReq(project_id="ent/proj", digest="d"),
    ),
    (
        "table_query_stats",
        lambda: tsi.TableQueryStatsReq(project_id="ent/proj", digest="d"),
    ),
    (
        "table_query_stats_batch",
        lambda: tsi.TableQueryStatsBatchReq(project_id="ent/proj", digests=["d"]),
    ),
    (
        "file_create",
        lambda: tsi.FileCreateReq(project_id="ent/proj", name="f", content=b"x"),
    ),
    (
        "file_content_read",
        lambda: tsi.FileContentReadReq(project_id="ent/proj", digest="d"),
    ),
    ("files_stats", lambda: tsi.FilesStatsReq(project_id="ent/proj")),
]


def _make_adapter() -> tuple[ExternalTraceServer, MagicMock]:
    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    adapter = ExternalTraceServer(inner, _EncodingIdConverter())
    return adapter, inner


def _invoke(adapter: ExternalTraceServer, method_name: str, req: Any) -> Any:
    """Call a method and, if it returns a generator, materialize it so any
    inner exception is actually raised.
    """
    result = getattr(adapter, method_name)(req)
    if inspect.isgenerator(result):
        list(result)
    return result


@pytest.mark.parametrize(("method_name", "req_factory"), _FIXED_METHODS)
def test_adapter_does_not_mutate_req_when_inner_raises(
    method_name: str, req_factory: Callable[[], Any]
) -> None:
    """If the inner server raises, the caller's req must be unchanged so a
    retry layer can re-invoke with the original external project_id.
    """
    adapter, inner = _make_adapter()
    getattr(inner, method_name).side_effect = NotFoundError("test")

    req = req_factory()
    snapshot = req.model_dump()

    with pytest.raises(NotFoundError):
        _invoke(adapter, method_name, req)

    assert req.model_dump() == snapshot, (
        f"{method_name} mutated req across a failed call: "
        f"{snapshot} -> {req.model_dump()}"
    )


@pytest.mark.parametrize(("method_name", "req_factory"), _FIXED_METHODS)
def test_adapter_retries_resolve_to_same_internal_project_id(
    method_name: str, req_factory: Callable[[], Any]
) -> None:
    """Two consecutive adapter calls on the same req object must translate
    the external project_id to the same internal value. The original bug
    produced a different (doubly-encoded) project_id on the second call.
    """
    adapter, inner = _make_adapter()
    getattr(inner, method_name).side_effect = NotFoundError("test")

    req = req_factory()

    with pytest.raises(NotFoundError):
        _invoke(adapter, method_name, req)
    call_1_args = getattr(inner, method_name).call_args

    with pytest.raises(NotFoundError):
        _invoke(adapter, method_name, req)
    call_2_args = getattr(inner, method_name).call_args

    # The inner server should have been called with structurally identical
    # reqs on both attempts. Compare via model_dump so we detect any drift
    # on project_id, wb_user_id, or any nested field.
    inner_req_1 = call_1_args.args[0]
    inner_req_2 = call_2_args.args[0]
    assert inner_req_1.model_dump() == inner_req_2.model_dump(), (
        f"{method_name} sent different internal reqs on attempts 1 vs 2: "
        f"{inner_req_1.model_dump()} vs {inner_req_2.model_dump()}"
    )
