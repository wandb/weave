"""Regression test for the adapter-mutates-req bug.

Before the fix, `ExternalTraceServer.obj_read` mutated `req.project_id` in
place when translating external entity/project strings to internal
base64-encoded project_ids. A retry layer above the adapter would re-invoke
the same `req`, now holding an already-internal project_id, and the adapter
would encode it a second time. By attempt 3 the project_id was
base64(base64(base64(...))) — a nonexistent project.

`obj_read` is the proven-bug method from the original investigation; two
tests exercise the mutation invariant on it. Every other method in the
adapter uses the same `req = req.model_copy(deep=True)` pattern at entry,
so these two tests cover the shared invariant.
"""

from __future__ import annotations

import base64
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


def _make_adapter_and_inner() -> tuple[ExternalTraceServer, MagicMock]:
    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    return ExternalTraceServer(inner, _EncodingIdConverter()), inner


def test_adapter_does_not_mutate_req_when_inner_raises() -> None:
    """On failure, caller's req must be unchanged so a retry layer can
    re-invoke with the original external project_id.
    """
    adapter, inner = _make_adapter_and_inner()
    inner.obj_read.side_effect = NotFoundError("test")

    req = tsi.ObjReadReq(project_id="ent/proj", object_id="o", digest="d")
    snapshot = req.model_dump()

    with pytest.raises(NotFoundError):
        adapter.obj_read(req)

    assert req.model_dump() == snapshot


def test_adapter_retries_resolve_to_same_internal_project_id() -> None:
    """Two consecutive adapter calls on the same req object must send the
    inner server structurally identical requests. The original bug produced
    a doubly-encoded project_id on the second call.
    """
    adapter, inner = _make_adapter_and_inner()
    inner.obj_read.side_effect = NotFoundError("test")

    req = tsi.ObjReadReq(project_id="ent/proj", object_id="o", digest="d")

    with pytest.raises(NotFoundError):
        adapter.obj_read(req)
    first = inner.obj_read.call_args.args[0].model_dump()

    with pytest.raises(NotFoundError):
        adapter.obj_read(req)
    second = inner.obj_read.call_args.args[0].model_dump()

    assert first == second
