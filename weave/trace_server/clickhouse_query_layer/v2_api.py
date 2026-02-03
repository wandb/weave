# ClickHouse V2 API - High-level API operations (ops, datasets, scorers, evaluations, etc.)
#
# This module consolidates all V2 API operations that build on top of the core
# CRUD operations (calls, objects, tables, files). These are higher-level
# domain-specific operations.

import datetime
import json
import logging
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from weave.trace_server import constants, object_creation_utils
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ensure_datetimes_have_tz
from weave.trace_server.clickhouse_query_layer.query_builders.objects import (
    ObjectMetadataQueryBuilder,
)
from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.feedback_types import RUNNABLE_FEEDBACK_TYPE_PREFIX
from weave.trace_server.trace_server_common import (
    determine_call_status,
    op_name_matches,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class V2ApiRepository:
    """Repository for V2 API operations.

    This class provides high-level domain operations that build on core CRUD:
    - Op CRUD (create, read, list, delete)
    - Dataset CRUD
    - Scorer CRUD
    - Evaluation CRUD
    - Model CRUD
    - Evaluation Run CRUD
    - Prediction CRUD
    - Score CRUD
    """

    def __init__(
        self,
        # Core operation functions from trace server
        obj_create_func: Callable[[tsi.ObjCreateReq], tsi.ObjCreateRes],
        obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
        objs_query_func: Callable[[tsi.ObjQueryReq], tsi.ObjQueryRes],
        obj_delete_func: Callable[[tsi.ObjDeleteReq], tsi.ObjDeleteRes],
        file_create_func: Callable[[tsi.FileCreateReq], tsi.FileCreateRes],
        file_content_read_func: Callable[
            [tsi.FileContentReadReq], tsi.FileContentReadRes
        ],
        table_create_func: Callable[[tsi.TableCreateReq], tsi.TableCreateRes],
        call_start_func: Callable[[tsi.CallStartReq], tsi.CallStartRes],
        call_end_func: Callable[[tsi.CallEndReq], tsi.CallEndRes],
        call_read_func: Callable[[tsi.CallReadReq], tsi.CallReadRes],
        calls_query_stream_func: Callable[
            [tsi.CallsQueryReq], Iterator[tsi.CallSchema]
        ],
        calls_delete_func: Callable[[tsi.CallsDeleteReq], tsi.CallsDeleteRes],
        feedback_create_func: Callable[[tsi.FeedbackCreateReq], tsi.FeedbackCreateRes],
        select_objs_query_func: Callable[[ObjectMetadataQueryBuilder, bool], list[Any]],
        obj_read_with_retry_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
    ):
        self._obj_create = obj_create_func
        self._obj_read = obj_read_func
        self._objs_query = objs_query_func
        self._obj_delete = obj_delete_func
        self._file_create = file_create_func
        self._file_content_read = file_content_read_func
        self._table_create = table_create_func
        self._call_start = call_start_func
        self._call_end = call_end_func
        self._call_read = call_read_func
        self._calls_query_stream = calls_query_stream_func
        self._calls_delete = calls_delete_func
        self._feedback_create = feedback_create_func
        self._select_objs_query = select_objs_query_func
        self._obj_read_with_retry = obj_read_with_retry_func

    # =========================================================================
    # Op Operations
    # =========================================================================

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an op object."""
        # Create the obj.py file
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self._file_create(source_file_req)

        # Create the op object
        op_val = object_creation_utils.build_op_val(source_file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=op_val,
                wb_user_id=None,
            )
        )
        obj_result = self._obj_create(obj_req)

        # Query back to get version index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        return tsi.OpCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Get a specific op object."""
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_object_ids_condition([req.object_id])
        object_query_builder.add_digests_conditions(req.digest)
        object_query_builder.set_include_deleted(include_deleted=True)
        objs = self._select_objs_query(object_query_builder, False)
        if len(objs) == 0:
            raise NotFoundError(f"Op {req.object_id}:{req.digest} not found")

        obj = objs[0]
        if obj.deleted_at is not None:
            raise ObjectDeletedError(
                f"Op {req.object_id}:v{obj.version_index} was deleted at {obj.deleted_at}",
                deleted_at=obj.deleted_at,
            )

        code = self._extract_op_code(req.project_id, obj.val_dump)

        return tsi.OpReadRes(
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=ensure_datetimes_have_tz(obj.created_at),
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List op objects in a project."""
        op_filter = tsi.ObjectVersionFilter(is_op=True)

        complex_query = req.limit is not None or req.offset is not None
        if complex_query:
            object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
            object_query_builder.add_is_op_condition(True)
            object_query_builder.set_include_deleted(include_deleted=False)
            if req.limit is not None:
                object_query_builder.set_limit(req.limit)
            if req.offset is not None:
                object_query_builder.set_offset(req.offset)
            object_query_builder.add_order("object_id", "asc")
            object_query_builder.add_order("version_index", "desc")
            objs = self._select_objs_query(object_query_builder, False)
        else:
            obj_query_req = tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=op_filter,
                metadata_only=False,
            )
            obj_res = self._objs_query(obj_query_req)
            objs = obj_res.objs

        for obj in objs:
            code = ""
            try:
                if complex_query:
                    val = json.loads(obj.val_dump)
                else:
                    val = obj.val
                if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
                    code = self._extract_op_code_from_val(req.project_id, val)
            except Exception:
                pass

            yield tsi.OpReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=ensure_datetimes_have_tz(obj.created_at),
                code=code,
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op object versions."""
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_object_ids_condition([req.object_id])
        metadata_only = True
        if req.digests:
            object_query_builder.add_digests_conditions(*req.digests)
            metadata_only = False

        object_versions = self._select_objs_query(object_query_builder, metadata_only)

        if len(object_versions) == 0:
            raise NotFoundError(
                f"Op object {req.object_id} ({req.digests}) not found when deleting."
            )

        if req.digests:
            given_digests = set(req.digests)
            found_digests = {obj.digest for obj in object_versions}
            if len(given_digests) != len(found_digests):
                raise NotFoundError(
                    f"Delete request contains {len(req.digests)} digests, "
                    f"but found {len(found_digests)} objects to delete."
                )

        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        obj_delete_res = self._obj_delete(obj_delete_req)

        return tsi.OpDeleteRes(num_deleted=obj_delete_res.num_deleted)

    # =========================================================================
    # Dataset Operations
    # =========================================================================

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        """Create a dataset object."""
        dataset_id = object_creation_utils.make_object_id(req.name, "Dataset")

        # Create a table for rows
        table_req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=req.project_id,
                rows=req.rows,
            )
        )
        table_res = self._table_create(table_req)
        table_ref = ri.InternalTableRef(
            project_id=req.project_id,
            digest=table_res.digest,
        ).uri()

        # Create the dataset object
        dataset_val = object_creation_utils.build_dataset_val(
            name=req.name,
            description=req.description,
            table_ref=table_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=dataset_id,
                val=dataset_val,
                wb_user_id=None,
            )
        )
        obj_result = self._obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=dataset_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        return tsi.DatasetCreateRes(
            digest=obj_result.digest,
            object_id=dataset_id,
            version_index=obj_read_res.obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Get a dataset object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        return tsi.DatasetReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=val.get("name"),
            description=val.get("description"),
            rows=val.get("rows", ""),
        )

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        """List dataset objects."""
        dataset_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Dataset"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=dataset_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self._objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            yield tsi.DatasetReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name"),
                description=val.get("description"),
                rows=val.get("rows", ""),
            )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        """Delete dataset objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self._obj_delete(obj_delete_req)
        return tsi.DatasetDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # Scorer Operations
    # =========================================================================

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create a scorer object."""
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        # Create the score op
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_score",
            source_code=req.op_source_code,
        )
        score_op_res = self.op_create(score_op_req)

        # Create the summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)

        # Create the scorer object
        scorer_val = object_creation_utils.build_scorer_val(
            name=req.name,
            description=req.description,
            score_op_ref=score_op_res.digest,
            summarize_op_ref=summarize_op_res.digest,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=scorer_id,
                val=scorer_val,
                wb_user_id=None,
            )
        )
        obj_result = self._obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        # Build the scorer reference using InternalObjectRef
        scorer_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=scorer_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Read a scorer object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name", result.obj.object_id)
        description = val.get("description")

        return tsi.ScorerReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            score_op=val.get("score", ""),
        )

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects."""
        scorer_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Scorer"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=scorer_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self._objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            # Extract name, description, and score_op from val data
            name = val.get("name", obj.object_id)
            description = val.get("description")
            score_op = val.get("score", "")

            yield tsi.ScorerReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                score_op=score_op,
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_op_code(self, project_id: str, val_dump: str) -> str:
        """Extract source code from an op's val_dump."""
        try:
            val = json.loads(val_dump)
            return self._extract_op_code_from_val(project_id, val)
        except Exception:
            return ""

    def _extract_op_code_from_val(self, project_id: str, val: dict) -> str:
        """Extract source code from an op's val dict."""
        if not isinstance(val, dict):
            return ""
        if val.get("_type") != "CustomWeaveType":
            return ""

        files = val.get("files", {})
        if object_creation_utils.OP_SOURCE_FILE_NAME not in files:
            return ""

        file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]
        try:
            file_content_res = self._file_content_read(
                tsi.FileContentReadReq(project_id=project_id, digest=file_digest)
            )
            return file_content_res.content.decode("utf-8")
        except Exception:
            return ""

    # =========================================================================
    # Scorer Delete
    # =========================================================================

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self._obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # Evaluation Operations
    # =========================================================================

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object."""
        evaluation_id = object_creation_utils.make_object_id(req.name, "Evaluation")

        # Create placeholder ops
        evaluate_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_evaluate",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        evaluate_op_res = self.op_create(evaluate_op_req)

        predict_and_score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_predict_and_score",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
        )
        predict_and_score_op_res = self.op_create(predict_and_score_op_req)

        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)

        # Build evaluation value
        evaluation_val = object_creation_utils.build_evaluation_val(
            name=req.name,
            dataset_ref=req.dataset,
            trials=req.trials or 1,
            description=req.description,
            scorer_refs=req.scorers,
            evaluation_name=req.evaluation_name,
            metadata=req.metadata,
            preprocess_model_input=req.preprocess_model_input,
            evaluate_ref=evaluate_op_res.digest,
            predict_and_score_ref=predict_and_score_op_res.digest,
            summarize_ref=summarize_op_res.digest,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=evaluation_id,
                val=evaluation_val,
                wb_user_id=None,
            )
        )
        obj_result = self._obj_create(obj_req)

        obj_read_res = self._obj_read_with_retry(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=evaluation_id,
                digest=obj_result.digest,
            )
        )

        # Build the evaluation reference using InternalObjectRef
        evaluation_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=evaluation_id,
            version=obj_result.digest,
        ).uri()

        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
            evaluation_ref=evaluation_ref,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Read an evaluation object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        return tsi.EvaluationReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=val.get("name"),
            description=val.get("description"),
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
        )

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluation objects."""
        eval_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Evaluation"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=eval_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self._objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            yield tsi.EvaluationReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name"),
                description=val.get("description"),
                dataset=val.get("dataset", ""),
                scorers=val.get("scorers", []),
                trials=val.get("trials", 1),
                evaluation_name=val.get("evaluation_name"),
                evaluate_op=val.get("evaluate", ""),
                predict_and_score_op=val.get("predict_and_score", ""),
                summarize_op=val.get("summarize", ""),
            )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self._obj_delete(obj_delete_req)
        return tsi.EvaluationDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # Model Operations
    # =========================================================================

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create a model object."""
        model_id = object_creation_utils.make_object_id(req.name, "Model")

        # Create the source file
        source_code = (
            req.source_code or object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE
        )
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self._file_create(source_file_req)

        # Build model value
        model_val = object_creation_utils.build_model_val(
            name=req.name,
            description=req.description,
            source_file_digest=source_file_res.digest,
            attributes=req.attributes,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=model_id,
                val=model_val,
                wb_user_id=None,
            )
        )
        obj_result = self._obj_create(obj_req)

        obj_read_res = self._obj_read_with_retry(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=model_id,
                digest=obj_result.digest,
            )
        )

        # Build the model reference using InternalObjectRef
        model_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=model_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=model_id,
            version_index=obj_read_res.obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read(obj_req)
        val = result.obj.val
        name = val.get("name", req.object_id)
        description = val.get("description")

        # Get source code from file
        files = val.get("files", {})
        source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
        if not source_file_digest:
            raise ValueError(f"Model {req.object_id} has no source file")

        file_content_req = tsi.FileContentReadReq(
            project_id=req.project_id,
            digest=source_file_digest,
        )
        file_content_res = self._file_content_read(file_content_req)
        source_code = file_content_res.content.decode("utf-8")

        # Extract additional attributes (exclude system fields)
        excluded_fields = {
            "_type",
            "_class_name",
            "_bases",
            "name",
            "description",
            "files",
        }
        attributes = {k: v for k, v in val.items() if k not in excluded_fields}

        return tsi.ModelReadRes(
            object_id=req.object_id,
            digest=req.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            source_code=source_code,
            attributes=attributes if attributes else None,
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List model objects."""
        model_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Model"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=model_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self._objs_query(obj_query_req)

        for obj in obj_res.objs:
            val = obj.val
            name = val.get("name", obj.object_id)
            description = val.get("description")

            # Get source code from file
            files = val.get("files", {})
            source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
            if source_file_digest:
                file_content_req = tsi.FileContentReadReq(
                    project_id=req.project_id,
                    digest=source_file_digest,
                )
                file_content_res = self._file_content_read(file_content_req)
                source_code = file_content_res.content.decode("utf-8")
            else:
                source_code = ""

            # Extract additional attributes
            excluded_fields = {
                "_type",
                "_class_name",
                "_bases",
                "name",
                "description",
                "files",
            }
            attributes = {k: v for k, v in val.items() if k not in excluded_fields}

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                source_code=source_code,
                attributes=attributes if attributes else None,
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self._obj_delete(obj_delete_req)
        return tsi.ModelDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # Evaluation Run Operations
    # =========================================================================

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run as a call with special attributes."""
        evaluation_run_id = generate_id()

        # Create the evaluation run op
        op_create_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        op_create_res = self.op_create(op_create_req)

        # Build the op ref
        op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            version=op_create_res.digest,
        )

        # Start a call to represent the evaluation run
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={
                    constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                        constants.EVALUATION_RUN_ATTR_KEY: "true",
                        constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: req.evaluation,
                        constants.EVALUATION_RUN_MODEL_ATTR_KEY: req.model,
                    }
                },
                inputs={
                    "self": req.evaluation,
                    "model": req.model,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self._call_start(call_start_req)

        return tsi.EvaluationRunCreateRes(evaluation_run_id=evaluation_run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        call_res = self._call_read(call_read_req)

        if (call := call_res.call) is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )
        status = determine_call_status(call)

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=call.id,
            evaluation=attributes.get(constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""),
            model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
            status=status,
            started_at=call.started_at,
            finished_at=call.ended_at,
            summary=call.summary,
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs by querying calls with evaluation_run attribute."""
        # Build query to filter for calls with evaluation_run attribute
        eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_ATTR_KEY}"
        conditions: list[dict[str, Any]] = [
            {
                "$eq": [
                    {"$getField": eval_run_attr_path},
                    {"$literal": "true"},
                ]
            }
        ]

        # Apply additional filters if specified
        if req.filter:
            if req.filter.evaluations:
                eval_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_EVALUATION_ATTR_KEY}"
                conditions.append(
                    {
                        "$in": [
                            {"$getField": eval_attr_path},
                            [
                                {"$literal": eval_ref}
                                for eval_ref in req.filter.evaluations
                            ],
                        ]
                    }
                )
            if req.filter.models:
                model_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_MODEL_ATTR_KEY}"
                conditions.append(
                    {
                        "$in": [
                            {"$getField": model_attr_path},
                            [
                                {"$literal": model_ref}
                                for model_ref in req.filter.models
                            ],
                        ]
                    }
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    {
                        "$in": [
                            {"$getField": "id"},
                            [
                                {"$literal": run_id}
                                for run_id in req.filter.evaluation_run_ids
                            ],
                        ]
                    }
                )

        # Combine conditions with AND
        if len(conditions) == 1:
            query_expr = {"$expr": conditions[0]}
        else:
            query_expr = {"$expr": {"$and": conditions}}

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**query_expr),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self._calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            status = determine_call_status(call)

            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=attributes.get(
                    constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""
                ),
                model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
                status=status,
                started_at=call.started_at,
                finished_at=call.ended_at,
                summary=call.summary,
            )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.evaluation_run_ids,
            wb_user_id=req.wb_user_id,
        )
        result = self._calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=result.num_deleted)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run."""
        end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.evaluation_run_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={},
                summary={},
            )
        )
        self._call_end(end_req)
        return tsi.EvaluationRunFinishRes(success=True)

    # =========================================================================
    # Prediction Operations
    # =========================================================================

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction as a call with special attributes."""
        prediction_id = generate_id()

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, create a predict_and_score parent call
            trace_id = req.evaluation_run_id
            predict_and_score_id = generate_id()

            # Read the evaluation run call to get the evaluation reference
            evaluation_run_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=req.evaluation_run_id,
            )
            eval_run_read_res = self._call_read(evaluation_run_read_req)

            call = eval_run_read_res.call
            if call is None:
                raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
            evaluation_ref = (call.inputs or {}).get("self")

            # Create the predict_and_score op
            predict_and_score_op_req = tsi.OpCreateReq(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
            )
            predict_and_score_op_res = self.op_create(predict_and_score_op_req)

            # Build the predict_and_score op ref
            predict_and_score_op_ref = ri.InternalOpRef(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                version=predict_and_score_op_res.digest,
            )

            # Create the predict_and_score call as a child of the evaluation run
            predict_and_score_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=predict_and_score_id,
                    trace_id=trace_id,
                    parent_id=req.evaluation_run_id,
                    op_name=predict_and_score_op_ref.uri(),
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
                        }
                    },
                    inputs={
                        "self": evaluation_ref,
                        "model": req.model,
                        "example": req.inputs,
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
            self._call_start(predict_and_score_start_req)

            # The prediction will be a child of predict_and_score
            parent_id = predict_and_score_id
        else:
            # Standalone prediction (not part of an evaluation)
            trace_id = prediction_id
            parent_id = None

        # Parse the model ref to get the model name
        try:
            model_ref = ri.parse_internal_uri(req.model)
            if isinstance(model_ref, (ri.InternalObjectRef, ri.InternalOpRef)):
                model_name = model_ref.name
            else:
                model_name = "Model"
        except ri.InvalidInternalRef:
            model_name = "Model"

        # Create the predict op with the model-specific name
        predict_op_name = f"{model_name}.predict"
        predict_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=predict_op_name,
            source_code=object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
        )
        predict_op_res = self.op_create(predict_op_req)

        # Build the predict op ref
        predict_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=predict_op_name,
            version=predict_op_res.digest,
        )

        # Start a call to represent the prediction
        prediction_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        if req.evaluation_run_id:
            prediction_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=predict_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=prediction_attributes,
                inputs={
                    "self": req.model,
                    "inputs": req.inputs,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self._call_start(call_start_req)

        # End the call immediately with the output
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.output,
                summary={},
            )
        )
        self._call_end(call_end_req)

        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        call_res = self._call_read(call_read_req)

        call = call_res.call
        if call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )

        # Get evaluation_run_id from attributes
        evaluation_run_id = attributes.get(
            constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
        )

        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=(call.inputs or {}).get("inputs", {}),
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions by querying calls with prediction attribute."""
        # Build query to filter for calls with prediction attribute
        prediction_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_ATTR_KEY}"
        conditions: list[dict[str, Any]] = [
            {
                "$eq": [
                    {"$getField": prediction_attr_path},
                    {"$literal": "true"},
                ]
            }
        ]

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY}"
            conditions.append(
                {
                    "$eq": [
                        {"$getField": eval_run_attr_path},
                        {"$literal": req.evaluation_run_id},
                    ]
                }
            )

        # Combine conditions with AND
        if len(conditions) == 1:
            query_expr = {"$expr": conditions[0]}
        else:
            query_expr = {"$expr": {"$and": conditions}}

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**query_expr),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self._calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )

            evaluation_run_id = attributes.get(
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            )

            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
                inputs=(call.inputs or {}).get("inputs", {}),
                output=call.output,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.prediction_ids,
            wb_user_id=req.wb_user_id,
        )
        result = self._calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=result.num_deleted)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction by ending the underlying call.

        If the prediction is part of an evaluation (has a predict_and_score parent),
        this will also finish the predict_and_score parent call.
        """
        # Read the prediction to check if it has a parent (predict_and_score call)
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self._call_read(prediction_read_req)

        # Finish the prediction call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=None,
                summary={},
            )
        )
        self._call_end(call_end_req)

        # If this prediction has a parent (predict_and_score call), finish that too
        prediction_call = prediction_res.call
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        parent_id = prediction_call.parent_id

        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self._call_read(parent_read_req)
        parent_call = parent_res.call
        if not parent_call or not op_name_matches(
            parent_call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        # Build the scores dict by querying all score children of predict_and_score
        scores_dict: dict[str, Any] = {}

        score_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
        score_query = tsi.Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": score_attr_path},
                        {"$literal": "true"},
                    ]
                }
            }
        )

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[parent_id],
            ),
            query=score_query,
            columns=["output", "attributes"],
        )

        for score_call in self._calls_query_stream(calls_query_req):
            if score_call.output is None:
                continue

            # Get scorer name from the scorer ref in attributes
            weave_attrs = (score_call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            scorer_ref = weave_attrs.get(constants.SCORE_SCORER_ATTR_KEY)

            # Extract scorer name from ref
            scorer_name = "unknown"
            if scorer_ref and isinstance(scorer_ref, str):
                parts = scorer_ref.split("/")
                if parts:
                    name_and_digest = parts[-1]
                    if ":" in name_and_digest:
                        scorer_name = name_and_digest.split(":")[0]

            scores_dict[scorer_name] = score_call.output

        # Calculate model latency from the prediction call's timestamps
        model_latency = None
        if prediction_call.started_at and prediction_call.ended_at:
            latency_seconds = (
                prediction_call.ended_at - prediction_call.started_at
            ).total_seconds()
            model_latency = {"mean": latency_seconds}

        # Finish the predict_and_score parent call with proper output
        parent_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=parent_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={
                    "output": prediction_call.output,
                    "scores": scores_dict,
                    "model_latency": model_latency,
                },
                summary={},
            )
        )
        self._call_end(parent_end_req)

        return tsi.PredictionFinishRes(success=True)

    # =========================================================================
    # Score Operations
    # =========================================================================

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score as a call with special attributes."""
        score_id = generate_id()

        # Read the prediction to get its inputs and output
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self._call_read(prediction_read_req)

        # Extract inputs and output from the prediction call
        prediction_inputs = {}
        prediction_output = None
        prediction_call = prediction_res.call
        if prediction_call:
            # The prediction call has inputs structured as {"self": model_ref, "inputs": actual_inputs}
            if isinstance(prediction_call.inputs, dict):
                prediction_inputs = prediction_call.inputs.get("inputs", {})
            prediction_output = prediction_call.output

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            trace_id = req.evaluation_run_id
            if prediction_call and prediction_call.parent_id:
                parent_id = prediction_call.parent_id
            else:
                parent_id = req.evaluation_run_id
        else:
            trace_id = score_id
            parent_id = None

        # Parse the scorer ref to get the scorer name
        scorer_ref = ri.parse_internal_uri(req.scorer)
        if not isinstance(scorer_ref, ri.InternalObjectRef):
            raise TypeError(f"Invalid scorer ref: {req.scorer}")
        scorer_name = scorer_ref.name

        # Create the score op with scorer-specific name
        score_op_name = f"{scorer_name}.score"
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=score_op_name,
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
        )
        score_op_res = self.op_create(score_op_req)

        # Build the score op ref
        score_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=score_op_name,
            version=score_op_res.digest,
        )

        # Start a call to represent the score
        score_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        if req.evaluation_run_id:
            score_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=score_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=score_attributes,
                inputs={
                    "self": req.scorer,
                    "inputs": prediction_inputs,
                    "output": prediction_output,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self._call_start(call_start_req)

        # End the call immediately with the score value
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.value,
                summary={},
            )
        )
        self._call_end(call_end_req)

        # Also create feedback on the prediction call for UI visibility
        prediction_call_ref = ri.InternalCallRef(
            project_id=req.project_id,
            id=req.prediction_id,
        )

        wb_user_id = (
            req.wb_user_id
            or (prediction_call.wb_user_id if prediction_call else None)
            or "unknown"
        )

        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=prediction_call_ref.uri(),
            feedback_type=f"{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{scorer_name}",
            payload={"output": req.value},
            runnable_ref=req.scorer,
            wb_user_id=wb_user_id,
        )
        self._feedback_create(feedback_req)

        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.score_id,
        )
        call_res = self._call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Score {req.score_id} not found")

        call = call_res.call
        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )

        # Extract score value from output
        value = call.output if call.output is not None else 0.0

        # Get evaluation_run_id from attributes
        evaluation_run_id = attributes.get(constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY)

        return tsi.ScoreReadRes(
            score_id=call.id,
            scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
            value=value,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores by querying calls with score attribute."""
        # Build query to filter for calls with score attribute
        score_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
        expr: dict[str, Any] = {
            "$eq": [
                {"$getField": score_attr_path},
                {"$literal": "true"},
            ]
        }

        if req.evaluation_run_id:
            eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY}"
            expr = {
                "$and": [
                    expr,
                    {
                        "$eq": [
                            {"$getField": eval_run_attr_path},
                            {"$literal": req.evaluation_run_id},
                        ]
                    },
                ]
            }

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**{"$expr": expr}),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self._calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            value = call.output if call.output is not None else 0.0

            evaluation_run_id = attributes.get(
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            )

            yield tsi.ScoreReadRes(
                score_id=call.id,
                scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
                value=value,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores by deleting the underlying calls."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.score_ids,
            wb_user_id=req.wb_user_id,
        )
        res = self._calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=res.num_deleted)
