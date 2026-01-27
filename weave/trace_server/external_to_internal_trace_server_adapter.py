import abc
import typing
from collections.abc import Callable, Iterator
from typing import TypeVar

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)


class IdConverter:
    @abc.abstractmethod
    def ext_to_int_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_project_id(self, project_id: str) -> str | None:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_user_id(self, user_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_user_id(self, user_id: str) -> str:
        raise NotImplementedError()


A = TypeVar("A")
B = TypeVar("B")


class ExternalTraceServer(tsi.FullTraceServerInterface):
    """Used to adapt the internal trace server to the external trace server.
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: tsi.FullTraceServerInterface
    _idc: IdConverter

    def __init__(
        self,
        internal_trace_server: tsi.FullTraceServerInterface,
        id_converter: IdConverter,
    ):
        super().__init__()
        self._internal_trace_server = internal_trace_server
        self._idc = id_converter

    _STREAM_METHOD_SUFFIXES = ("_stream", "_list")
    _AUTO_SKIP_REF_METHODS = {"completions_create_stream"}

    def __getattr__(self, name: str) -> typing.Any:
        attr = getattr(self._internal_trace_server, name)
        if not callable(attr):
            return attr

        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            if len(args) == 1 and not kwargs and isinstance(args[0], BaseModel):
                return self._auto_forward(
                    attr,
                    args[0],
                    stream=name.endswith(self._STREAM_METHOD_SUFFIXES),
                    convert_refs=name not in self._AUTO_SKIP_REF_METHODS,
                )
            return attr(*args, **kwargs)

        return wrapper

    def _convert_ids(
        self,
        value: typing.Any,
        *,
        project_id_converter: Callable[[str], str],
        run_id_converter: Callable[[str], str],
        user_id_converter: Callable[[str], str],
    ) -> None:
        if isinstance(value, BaseModel):
            for field_name in value.model_fields:
                field_value = getattr(value, field_name)
                if field_name == "project_id" and isinstance(field_value, str):
                    setattr(value, field_name, project_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_run_id" and field_value is not None:
                    setattr(value, field_name, run_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_user_id" and field_value is not None:
                    setattr(value, field_name, user_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_run_ids" and isinstance(field_value, list):
                    setattr(
                        value,
                        field_name,
                        [run_id_converter(item) for item in field_value],
                    )
                elif field_name == "wb_user_ids" and isinstance(field_value, list):
                    setattr(
                        value,
                        field_name,
                        [user_id_converter(item) for item in field_value],
                    )

                if isinstance(field_value, BaseModel):
                    self._convert_ids(
                        field_value,
                        project_id_converter=project_id_converter,
                        run_id_converter=run_id_converter,
                        user_id_converter=user_id_converter,
                    )
                elif isinstance(field_value, list):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
                elif isinstance(field_value, tuple):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
                elif isinstance(field_value, set):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, BaseModel):
                    self._convert_ids(
                        item,
                        project_id_converter=project_id_converter,
                        run_id_converter=run_id_converter,
                        user_id_converter=user_id_converter,
                    )

    def _convert_request_ids(self, req: BaseModel) -> dict[str, str]:
        project_id_map: dict[str, str] = {}

        def convert_project_id(project_id: str) -> str:
            internal_id = self._idc.ext_to_int_project_id(project_id)
            project_id_map[internal_id] = project_id
            return internal_id

        self._convert_ids(
            req,
            project_id_converter=convert_project_id,
            run_id_converter=self._idc.ext_to_int_run_id,
            user_id_converter=self._idc.ext_to_int_user_id,
        )
        return project_id_map

    def _convert_response_ids(
        self,
        res: typing.Any,
        *,
        project_id_map: dict[str, str],
        strict_project_match: bool = False,
    ) -> None:
        def convert_project_id(project_id: str) -> str:
            if project_id in project_id_map:
                return project_id_map[project_id]
            if strict_project_match and project_id_map:
                raise ValueError("Internal Error - Project Mismatch")
            external_id = self._idc.int_to_ext_project_id(project_id)
            return external_id if external_id is not None else project_id

        self._convert_ids(
            res,
            project_id_converter=convert_project_id,
            run_id_converter=self._idc.int_to_ext_run_id,
            user_id_converter=self._idc.int_to_ext_user_id,
        )

    def _prepare_request(
        self, req: A, *, convert_refs: bool = True
    ) -> tuple[A, dict[str, str]]:
        project_id_map: dict[str, str] = {}
        if isinstance(req, BaseModel):
            project_id_map = self._convert_request_ids(req)
            if convert_refs:
                req = universal_ext_to_int_ref_converter(
                    req, self._idc.ext_to_int_project_id
                )
        return req, project_id_map

    def _finalize_response(
        self,
        res: B,
        *,
        project_id_map: dict[str, str],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> B:
        if convert_refs:
            res = universal_int_to_ext_ref_converter(
                res, self._idc.int_to_ext_project_id
            )
        self._convert_response_ids(
            res,
            project_id_map=project_id_map,
            strict_project_match=strict_project_match,
        )
        return res

    def _finalize_stream_response(
        self,
        res: Iterator[B],
        *,
        project_id_map: dict[str, str],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> Iterator[B]:
        int_to_ext_project_cache: dict[str, str | None] = {}

        def cached_int_to_ext_project_id(project_id: str) -> str | None:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = self._idc.int_to_ext_project_id(
                    project_id
                )
            return int_to_ext_project_cache[project_id]

        for item in res:
            if convert_refs:
                item = universal_int_to_ext_ref_converter(
                    item, cached_int_to_ext_project_id
                )
            self._convert_response_ids(
                item,
                project_id_map=project_id_map,
                strict_project_match=strict_project_match,
            )
            yield item

    @typing.overload
    def _auto_forward(
        self,
        method: Callable[[A], Iterator[B]],
        req: A,
        *,
        stream: typing.Literal[True],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> Iterator[B]: ...

    @typing.overload
    def _auto_forward(
        self,
        method: Callable[[A], B],
        req: A,
        *,
        stream: typing.Literal[False] = False,
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> B: ...

    def _auto_forward(
        self,
        method: Callable[[A], B] | Callable[[A], Iterator[B]],
        req: A,
        *,
        stream: bool = False,
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> B | Iterator[B]:
        req_conv, project_id_map = self._prepare_request(req, convert_refs=convert_refs)
        res = method(req_conv)
        if stream:
            return self._finalize_stream_response(
                res,
                project_id_map=project_id_map,
                convert_refs=convert_refs,
                strict_project_match=strict_project_match,
            )
        return self._finalize_response(
            res,
            project_id_map=project_id_map,
            convert_refs=convert_refs,
            strict_project_match=strict_project_match,
        )

    # Standard API Below:
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        return self._internal_trace_server.ensure_project_exists(entity, project)

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self._auto_forward(self._internal_trace_server.otel_export, req)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._auto_forward(self._internal_trace_server.call_start, req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._auto_forward(self._internal_trace_server.call_end, req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._auto_forward(
            self._internal_trace_server.call_read,
            req,
            strict_project_match=True,
        )

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._auto_forward(
            self._internal_trace_server.calls_query,
            req,
            strict_project_match=True,
        )

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._auto_forward(
            self._internal_trace_server.calls_query_stream,
            req,
            stream=True,
            strict_project_match=True,
        )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._auto_forward(self._internal_trace_server.calls_delete, req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._auto_forward(self._internal_trace_server.calls_query_stats, req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._auto_forward(self._internal_trace_server.call_update, req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._auto_forward(self._internal_trace_server.obj_create, req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._auto_forward(
            self._internal_trace_server.obj_read,
            req,
            strict_project_match=True,
        )

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._auto_forward(
            self._internal_trace_server.objs_query,
            req,
            strict_project_match=True,
        )

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._auto_forward(self._internal_trace_server.obj_delete, req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._auto_forward(self._internal_trace_server.table_create, req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self._auto_forward(self._internal_trace_server.table_update, req)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        return self._auto_forward(
            self._internal_trace_server.table_create_from_digests, req
        )

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._auto_forward(self._internal_trace_server.table_query, req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self._auto_forward(
            self._internal_trace_server.table_query_stream, req, stream=True
        )

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._auto_forward(self._internal_trace_server.table_query_stats, req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return self._auto_forward(
            self._internal_trace_server.table_query_stats_batch, req
        )

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._auto_forward(self._internal_trace_server.refs_read_batch, req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        # Special case where refs can never be part of the request
        return self._auto_forward(
            self._internal_trace_server.file_create, req, convert_refs=False
        )

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        # Special case where refs can never be part of the request
        return self._auto_forward(
            self._internal_trace_server.file_content_read, req, convert_refs=False
        )

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._auto_forward(self._internal_trace_server.files_stats, req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        res = self._auto_forward(self._internal_trace_server.feedback_create, req)
        if res.wb_user_id != original_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        return self._auto_forward(
            self._internal_trace_server.feedback_create_batch, req
        )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        original_project_id = req.project_id
        req_conv, project_id_map = self._prepare_request(req)
        # TODO: How to handle wb_user_id and wb_run_id in the query filters?
        res = self._internal_trace_server.feedback_query(req_conv)
        res = self._finalize_response(res, project_id_map=project_id_map)
        for feedback in res.result:
            if "project_id" in feedback:
                if feedback["project_id"] != req_conv.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                feedback["project_id"] = original_project_id
            if "wb_user_id" in feedback and feedback["wb_user_id"] is not None:
                feedback["wb_user_id"] = self._idc.int_to_ext_user_id(
                    feedback["wb_user_id"]
                )
        return res

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._auto_forward(self._internal_trace_server.feedback_purge, req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        res = self._auto_forward(self._internal_trace_server.feedback_replace, req)
        if res.wb_user_id != original_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._auto_forward(self._internal_trace_server.cost_create, req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._auto_forward(self._internal_trace_server.cost_purge, req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        original_project_id = req.project_id
        req_conv, project_id_map = self._prepare_request(req)
        res = self._internal_trace_server.cost_query(req_conv)
        res = self._finalize_response(res, project_id_map=project_id_map)
        # Extend this to account for ORG ID when org level costs are implemented
        for cost in res.results:
            if "pricing_level_id" in cost:
                if cost["pricing_level_id"] != req_conv.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                cost["pricing_level_id"] = original_project_id
        return res

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        if req.wb_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        return self._auto_forward(self._internal_trace_server.actions_execute_batch, req)

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._auto_forward(self._internal_trace_server.completions_create, req)

    # Streaming completions – simply proxy through after converting project ID.
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> typing.Iterator[dict[str, typing.Any]]:
        # Convert IDs and any refs in the request (e.g., prompt) to internal format
        req, _ = self._prepare_request(req)
        # The streamed chunks contain no project-scoped references, so we can
        # forward directly without additional ref conversion.
        return self._internal_trace_server.completions_create_stream(req)

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        return self._auto_forward(self._internal_trace_server.image_create, req)

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self._auto_forward(self._internal_trace_server.project_stats, req)

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        return self._auto_forward(
            self._internal_trace_server.threads_query_stream, req, stream=True
        )

    # Annotation Queue API
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        return self._auto_forward(
            self._internal_trace_server.annotation_queue_create, req
        )

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        return self._auto_forward(
            self._internal_trace_server.annotation_queues_query_stream,
            req,
            stream=True,
        )

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        return self._auto_forward(
            self._internal_trace_server.annotation_queue_read, req
        )

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        return self._auto_forward(
            self._internal_trace_server.annotation_queue_add_calls, req
        )

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        return self._auto_forward(
            self._internal_trace_server.annotation_queue_items_query, req
        )

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        return self._auto_forward(
            self._internal_trace_server.annotation_queues_stats, req
        )

    def annotator_queue_items_progress_update(
        self, req: tsi.AnnotatorQueueItemsProgressUpdateReq
    ) -> tsi.AnnotatorQueueItemsProgressUpdateRes:
        return self._auto_forward(
            self._internal_trace_server.annotator_queue_items_progress_update, req
        )

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return self._auto_forward(self._internal_trace_server.evaluate_model, req)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return self._auto_forward(self._internal_trace_server.evaluation_status, req)

    # === V2 APIs ===

    def call_stats(self, req: tsi.CallStatsReq) -> tsi.CallStatsRes:
        return self._auto_forward(self._internal_trace_server.call_stats, req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._auto_forward(self._internal_trace_server.op_create, req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._auto_forward(self._internal_trace_server.op_read, req)

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        return self._auto_forward(self._internal_trace_server.op_list, req, stream=True)

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        return self._auto_forward(self._internal_trace_server.op_delete, req)

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        return self._auto_forward(self._internal_trace_server.dataset_create, req)

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        return self._auto_forward(self._internal_trace_server.dataset_read, req)

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        return self._auto_forward(
            self._internal_trace_server.dataset_list, req, stream=True
        )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        return self._auto_forward(self._internal_trace_server.dataset_delete, req)

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        return self._auto_forward(self._internal_trace_server.scorer_create, req)

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        return self._auto_forward(self._internal_trace_server.scorer_read, req)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        return self._auto_forward(
            self._internal_trace_server.scorer_list, req, stream=True
        )

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        return self._auto_forward(self._internal_trace_server.scorer_delete, req)

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        return self._auto_forward(self._internal_trace_server.evaluation_create, req)

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        return self._auto_forward(self._internal_trace_server.evaluation_read, req)

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        return self._auto_forward(
            self._internal_trace_server.evaluation_list, req, stream=True
        )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        return self._auto_forward(self._internal_trace_server.evaluation_delete, req)

    # Model V2 API

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        return self._auto_forward(self._internal_trace_server.model_create, req)

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        return self._auto_forward(self._internal_trace_server.model_read, req)

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        return self._auto_forward(
            self._internal_trace_server.model_list, req, stream=True
        )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        return self._auto_forward(self._internal_trace_server.model_delete, req)

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        return self._auto_forward(
            self._internal_trace_server.evaluation_run_create, req
        )

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        return self._auto_forward(
            self._internal_trace_server.evaluation_run_read, req
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        return self._auto_forward(
            self._internal_trace_server.evaluation_run_list, req, stream=True
        )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        return self._auto_forward(
            self._internal_trace_server.evaluation_run_delete, req
        )

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run, converting project_id."""
        return self._auto_forward(
            self._internal_trace_server.evaluation_run_finish, req
        )

    # Prediction V2 API

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction, converting project_id and model ref."""
        return self._auto_forward(self._internal_trace_server.prediction_create, req)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction, converting project_id and model ref."""
        return self._auto_forward(self._internal_trace_server.prediction_read, req)

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions, converting project_id and model refs."""
        return self._auto_forward(
            self._internal_trace_server.prediction_list, req, stream=True
        )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions, converting project_id."""
        return self._auto_forward(self._internal_trace_server.prediction_delete, req)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction, converting project_id."""
        return self._auto_forward(self._internal_trace_server.prediction_finish, req)

    # Score V2 API

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score, converting project_id and scorer ref."""
        return self._auto_forward(self._internal_trace_server.score_create, req)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score, converting project_id and scorer ref."""
        return self._auto_forward(self._internal_trace_server.score_read, req)

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores, converting project_id and scorer refs."""
        return self._auto_forward(
            self._internal_trace_server.score_list, req, stream=True
        )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete a score, converting project_id."""
        return self._auto_forward(self._internal_trace_server.score_delete, req)

    # Calls V2 API
    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        """Batch complete calls, converting project_id."""
        return self._auto_forward(self._internal_trace_server.calls_complete, req)

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        """Start a single call (v2), converting project_id."""
        return self._auto_forward(self._internal_trace_server.call_start_v2, req)

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
        """End a single call (v2), converting project_id."""
        return self._auto_forward(self._internal_trace_server.call_end_v2, req)
