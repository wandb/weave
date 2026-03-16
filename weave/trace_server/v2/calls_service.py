"""V2 service layer for calls (Tier 2).

Sits between the HTTP endpoints and raw storage.
Translates external IDs to internal, converts weave refs,
then delegates to a CallsStorageInterface.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from weave.trace_server.calls_storage_interface import CallsStorageInterface
from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
)
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndRes,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
)

A = TypeVar("A")
B = TypeVar("B")


class CallsService:
    """Business logic for calls: ID translation, ref conversion.

    Accepts external IDs (entity/project), translates to internal,
    converts weave refs, then delegates to storage.
    """

    def __init__(
        self,
        storage: CallsStorageInterface,
        id_converter: IdConverter,
    ) -> None:
        self._storage = storage
        self._idc = id_converter

    def _ref_apply(self, method: Callable[[A], B], req: A) -> B:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)
        return universal_int_to_ext_ref_converter(
            res, self._idc.int_to_ext_project_id
        )

    def call_start(self, req: CallStartReq) -> CallStartRes:
        req.start.project_id = self._idc.ext_to_int_project_id(
            req.start.project_id
        )
        if req.start.wb_run_id is not None:
            req.start.wb_run_id = self._idc.ext_to_int_run_id(
                req.start.wb_run_id
            )
        if req.start.wb_user_id is not None:
            req.start.wb_user_id = self._idc.ext_to_int_user_id(
                req.start.wb_user_id
            )
        return self._ref_apply(self._storage.call_start, req)

    def call_end(self, req: CallEndReq) -> CallEndRes:
        req.end.project_id = self._idc.ext_to_int_project_id(
            req.end.project_id
        )
        return self._ref_apply(self._storage.call_end, req)

    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res:
        req.start.project_id = self._idc.ext_to_int_project_id(
            req.start.project_id
        )
        if req.start.wb_run_id is not None:
            req.start.wb_run_id = self._idc.ext_to_int_run_id(
                req.start.wb_run_id
            )
        if req.start.wb_user_id is not None:
            req.start.wb_user_id = self._idc.ext_to_int_user_id(
                req.start.wb_user_id
            )
        return self._ref_apply(self._storage.call_start_v2, req)

    def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes:
        for item in req.batch:
            item.project_id = self._idc.ext_to_int_project_id(
                item.project_id
            )
            if item.wb_run_id is not None:
                item.wb_run_id = self._idc.ext_to_int_run_id(item.wb_run_id)
            if item.wb_user_id is not None:
                item.wb_user_id = self._idc.ext_to_int_user_id(
                    item.wb_user_id
                )
        return self._ref_apply(self._storage.calls_complete, req)
