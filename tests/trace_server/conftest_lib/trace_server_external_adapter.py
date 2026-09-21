from tests.trace.id_converter import DummyIdConverter as _PortableIdConverter
from tests.trace.id_converter import TwoWayMapping, b64
from weave.trace_server import (
    external_to_internal_trace_server_adapter,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.service_interface import (
    ProjectsInfoReq,
    ProjectsInfoRes,
)


class DummyIdConverter(
    _PortableIdConverter, external_to_internal_trace_server_adapter.IdConverter
):
    pass


class UserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    # Tests-only adapter that injects a fixed user id into external-facing requests.

    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def set_user_id(self, user_id: str) -> None:
        """Set the user identity for subsequent requests.

        This is a test utility — use it instead of reaching through
        internal layers to mutate _user_id directly.
        """
        self._user_id = user_id

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        for item in req.batch:
            if isinstance(item, tsi.CallBatchStartMode):
                item.req.start.wb_user_id = self._user_id
        return super().call_start_batch(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        for feedback_req in req.batch:
            feedback_req.wb_user_id = self._user_id
        return super().feedback_create_batch(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        req.wb_user_id = req.wb_user_id or self._user_id
        return super().annotation_queue_create(req)

    def annotation_queue_update(
        self, req: tsi.AnnotationQueueUpdateReq
    ) -> tsi.AnnotationQueueUpdateRes:
        req.wb_user_id = req.wb_user_id or self._user_id
        return super().annotation_queue_update(req)

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        req.wb_user_id = req.wb_user_id or self._user_id
        return super().annotation_queue_add_calls(req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.wb_user_id = self._user_id
        return super().obj_create(req)

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        req.wb_user_id = self._user_id
        return super().evaluate_model(req)

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        req.wb_user_id = self._user_id
        return super().evaluation_run_delete(req)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        req.wb_user_id = self._user_id
        return super().evaluation_run_finish(req)

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        req.wb_user_id = self._user_id
        return super().prediction_delete(req)

    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]:
        return [
            ProjectsInfoRes(
                external_project_id=pid,
                internal_project_id=self._idc.ext_to_int_project_id(pid),
            )
            for pid in req.project_ids
        ]

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        req.wb_user_id = self._user_id
        return super().score_delete(req)

    def obj_add_tags(self, req: tsi.ObjAddTagsReq) -> tsi.ObjAddTagsRes:
        req.wb_user_id = self._user_id
        return super().obj_add_tags(req)

    def obj_remove_tags(self, req: tsi.ObjRemoveTagsReq) -> tsi.ObjRemoveTagsRes:
        req.wb_user_id = self._user_id
        return super().obj_remove_tags(req)

    def obj_set_aliases(self, req: tsi.ObjSetAliasesReq) -> tsi.ObjSetAliasesRes:
        req.wb_user_id = self._user_id
        return super().obj_set_aliases(req)

    def obj_remove_aliases(
        self, req: tsi.ObjRemoveAliasesReq
    ) -> tsi.ObjRemoveAliasesRes:
        req.wb_user_id = self._user_id
        return super().obj_remove_aliases(req)


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface,
    user_id: str = "test_user",
    id_converter: external_to_internal_trace_server_adapter.IdConverter | None = None,
) -> UserInjectingExternalTraceServer:
    return UserInjectingExternalTraceServer(
        trace_server,
        id_converter or DummyIdConverter(),
        user_id,
    )


__all__ = [
    "DummyIdConverter",
    "TwoWayMapping",
    "UserInjectingExternalTraceServer",
    "b64",
]
