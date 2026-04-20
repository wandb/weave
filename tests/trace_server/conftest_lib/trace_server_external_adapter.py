import base64
import time
from collections.abc import Callable

from weave.trace_server import (
    external_to_internal_trace_server_adapter,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server.service_interface import (
    ProjectsInfoReq,
    ProjectsInfoRes,
)


class TwoWayMapping:
    def __init__(self):
        self._ext_to_int_map = {}
        self._int_to_ext_map = {}

        # Useful for testing to ensure caching is working
        self.stats = {
            "ext_to_int": {
                "hits": 0,
                "misses": 0,
            },
            "int_to_ext": {
                "hits": 0,
                "misses": 0,
            },
        }

    def ext_to_int(self, key, default=None):
        if key not in self._ext_to_int_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._int_to_ext_map:
                raise ValueError(f"Default {default} already in use")
            self._ext_to_int_map[key] = default
            self._int_to_ext_map[default] = key
            self.stats["ext_to_int"]["misses"] += 1
        else:
            self.stats["ext_to_int"]["hits"] += 1
        return self._ext_to_int_map[key]

    def int_to_ext(self, key, default):
        if key not in self._int_to_ext_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._ext_to_int_map:
                raise ValueError(f"Default {default} already in use")
            self._int_to_ext_map[key] = default
            self._ext_to_int_map[default] = key
            self.stats["int_to_ext"]["misses"] += 1
        else:
            self.stats["int_to_ext"]["hits"] += 1
        return self._int_to_ext_map[key]


def b64(s: str) -> str:
    # Base64 encode the string
    return base64.b64encode(s.encode("ascii")).decode("ascii")


class DummyIdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self):
        self._project_map = TwoWayMapping()
        self._run_map = TwoWayMapping()
        self._user_map = TwoWayMapping()

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.ext_to_int(project_id, b64(project_id))

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return self._project_map.int_to_ext(project_id, b64(project_id))

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.ext_to_int(run_id, b64(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        exp = run_id.split(":")[1]
        return self._run_map.int_to_ext(run_id, exp)

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.ext_to_int(user_id, b64(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        return self._user_map.int_to_ext(user_id, b64(user_id))


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

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

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


class EventuallyConsistentUserInjectingExternalTraceServer(
    UserInjectingExternalTraceServer
):
    """Tests-only ClickHouse adapter that waits for write visibility.

    ClickHouse tests already force synchronous batch flushing, but that only
    guarantees the write request has been sent. It does not guarantee the write
    is immediately query-visible on subsequent reads. This wrapper keeps the
    workaround in one place by waiting for a small set of object/tag/alias
    mutations to become externally readable before returning.
    """

    _settle_timeout_s = 2.0
    _settle_poll_interval_s = 0.05

    def _should_settle(self) -> bool:
        return isinstance(self._internal_trace_server, ClickHouseTraceServer)

    def _wait_until(self, check: Callable[[], bool]) -> None:
        if not self._should_settle():
            return

        deadline = time.monotonic() + self._settle_timeout_s
        while time.monotonic() < deadline:
            try:
                if check():
                    return
            except (NotFoundError, ObjectDeletedError):
                pass
            time.sleep(self._settle_poll_interval_s)

        try:
            check()
        except (NotFoundError, ObjectDeletedError):
            pass

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        project_id = req.obj.project_id
        object_id = req.obj.object_id
        res = super().obj_create(req)
        self._wait_until(
            lambda: (
                self.obj_read(
                    tsi.ObjReadReq(
                        project_id=project_id,
                        object_id=object_id,
                        digest=res.digest,
                    )
                ).obj.digest
                == res.digest
            )
        )
        return res

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        project_id = req.project_id
        object_id = req.object_id
        digests = list(req.digests or [])
        res = super().obj_delete(req)

        if digests:

            def deleted() -> bool:
                for digest in digests:
                    try:
                        self.obj_read(
                            tsi.ObjReadReq(
                                project_id=project_id,
                                object_id=object_id,
                                digest=digest,
                            )
                        )
                    except (NotFoundError, ObjectDeletedError):
                        continue
                    else:
                        return False
                return True

            self._wait_until(deleted)
        else:
            self._wait_until(
                lambda: (
                    len(
                        self.objs_query(
                            tsi.ObjQueryReq(
                                project_id=project_id,
                                filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
                            )
                        ).objs
                    )
                    == 0
                )
            )
        return res

    def obj_add_tags(self, req: tsi.ObjAddTagsReq) -> tsi.ObjAddTagsRes:
        project_id = req.project_id
        object_id = req.object_id
        digest = req.digest
        tags = set(req.tags)
        res = super().obj_add_tags(req)
        self._wait_until(
            lambda: tags.issubset(
                set(
                    self.obj_read(
                        tsi.ObjReadReq(
                            project_id=project_id,
                            object_id=object_id,
                            digest=digest,
                            include_tags_and_aliases=True,
                        )
                    ).obj.tags
                    or []
                )
            )
        )
        return res

    def obj_remove_tags(self, req: tsi.ObjRemoveTagsReq) -> tsi.ObjRemoveTagsRes:
        project_id = req.project_id
        object_id = req.object_id
        digest = req.digest
        tags = set(req.tags)
        res = super().obj_remove_tags(req)
        self._wait_until(
            lambda: tags.isdisjoint(
                set(
                    self.obj_read(
                        tsi.ObjReadReq(
                            project_id=project_id,
                            object_id=object_id,
                            digest=digest,
                            include_tags_and_aliases=True,
                        )
                    ).obj.tags
                    or []
                )
            )
        )
        return res

    def obj_set_aliases(self, req: tsi.ObjSetAliasesReq) -> tsi.ObjSetAliasesRes:
        project_id = req.project_id
        object_id = req.object_id
        digest = req.digest
        aliases = list(req.aliases)
        res = super().obj_set_aliases(req)

        def aliases_visible() -> bool:
            read_res = self.obj_read(
                tsi.ObjReadReq(
                    project_id=project_id,
                    object_id=object_id,
                    digest=digest,
                    include_tags_and_aliases=True,
                )
            )
            existing_aliases = set(read_res.obj.aliases or [])
            if not set(aliases).issubset(existing_aliases):
                return False
            for alias in aliases:
                alias_res = self.obj_read(
                    tsi.ObjReadReq(
                        project_id=project_id,
                        object_id=object_id,
                        digest=alias,
                    )
                )
                if alias_res.obj.digest != digest:
                    return False
            return True

        self._wait_until(aliases_visible)
        return res

    def obj_remove_aliases(
        self, req: tsi.ObjRemoveAliasesReq
    ) -> tsi.ObjRemoveAliasesRes:
        project_id = req.project_id
        object_id = req.object_id
        aliases = list(req.aliases)
        res = super().obj_remove_aliases(req)

        def aliases_removed() -> bool:
            query_res = self.objs_query(
                tsi.ObjQueryReq(
                    project_id=project_id,
                    filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
                    include_tags_and_aliases=True,
                )
            )
            if any(
                not set(aliases).isdisjoint(set(obj.aliases or []))
                for obj in query_res.objs
            ):
                return False
            for alias in aliases:
                try:
                    self.obj_read(
                        tsi.ObjReadReq(
                            project_id=project_id,
                            object_id=object_id,
                            digest=alias,
                        )
                    )
                except (NotFoundError, ObjectDeletedError):
                    continue
                else:
                    return False
            return True

        self._wait_until(aliases_removed)
        return res


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
