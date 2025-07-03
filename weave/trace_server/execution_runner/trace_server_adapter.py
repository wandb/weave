from __future__ import annotations

from typing import Callable, TypeVar

from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_converter import universal_int_to_ext_ref_converter

SERVER_SIDE_ENTITY_PLACEHOLDER = "__SERVER__"
SERVER_SIDE_PROJECT_ID_PREFIX = SERVER_SIDE_ENTITY_PLACEHOLDER + "/"


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface, project_id: str, wb_user_id: str
) -> tsi.TraceServerInterface:
    return UserInjectingExternalTraceServer(
        trace_server,
        id_converter=IdConverter(project_id, wb_user_id),
        user_id=wb_user_id,
    )


T = TypeVar("T")


def make_externalize_ref_converter(project_id: str) -> Callable[[T], T]:
    def convert_project_id(internal_project_id: str) -> str:
        if project_id != internal_project_id:
            raise ValueError(
                f"Project ID mismatch: {project_id} != {internal_project_id}. This is a security issue."
            )
        return SERVER_SIDE_PROJECT_ID_PREFIX + internal_project_id

    def convert(obj: T) -> T:
        return universal_int_to_ext_ref_converter(obj, convert_project_id)

    return convert


class IdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self, project_id: str, user_id: str):
        self.user_id = user_id
        self.project_id = project_id

    def ext_to_int_project_id(self, project_id: str) -> str:
        if not project_id.startswith(SERVER_SIDE_PROJECT_ID_PREFIX):
            raise ValueError(
                f"Project ID does not start with {SERVER_SIDE_PROJECT_ID_PREFIX}: {project_id}"
            )
        found_project_id = project_id[len(SERVER_SIDE_PROJECT_ID_PREFIX) :]
        if found_project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {found_project_id} != {self.project_id}. This is a security issue."
            )
        return found_project_id

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        if project_id != self.project_id:
            raise ValueError(
                f"Project ID mismatch: {project_id} != {self.project_id}. This is a security issue."
            )
        return SERVER_SIDE_PROJECT_ID_PREFIX + project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def int_to_ext_run_id(self, run_id: str) -> str:
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def ext_to_int_user_id(self, user_id: str) -> str:
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. This is a security issue."
            )
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        if user_id != self.user_id:
            raise ValueError(
                f"User ID mismatch: {user_id} != {self.user_id}. This is a security issue."
            )
        return user_id


class UserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str | None,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

    async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id
        return await super().run_model(req)
