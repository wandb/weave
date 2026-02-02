# ClickHouse V2 API - High-level API operations (ops, datasets, scorers, evaluations, etc.)
#
# This module consolidates all V2 API operations that build on top of the core
# CRUD operations (calls, objects, tables, files). These are higher-level
# domain-specific operations.

import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from weave.trace_server import object_creation_utils
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ensure_datetimes_have_tz
from weave.trace_server.clickhouse_query_layer.query_builders.objects import (
    ObjectMetadataQueryBuilder,
)
from weave.trace_server.errors import NotFoundError, ObjectDeletedError

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
    - Prediction CRUD
    - Score CRUD
    """

    def __init__(
        self,
        # Core operation functions from trace server
        obj_create_func: "callable[[tsi.ObjCreateReq], tsi.ObjCreateRes]",
        obj_read_func: "callable[[tsi.ObjReadReq], tsi.ObjReadRes]",
        objs_query_func: "callable[[tsi.ObjQueryReq], tsi.ObjQueryRes]",
        obj_delete_func: "callable[[tsi.ObjDeleteReq], tsi.ObjDeleteRes]",
        file_create_func: "callable[[tsi.FileCreateReq], tsi.FileCreateRes]",
        file_content_read_func: "callable[[tsi.FileContentReadReq], tsi.FileContentReadRes]",
        table_create_func: "callable[[tsi.TableCreateReq], tsi.TableCreateRes]",
        call_start_func: "callable[[tsi.CallStartReq], tsi.CallStartRes]",
        call_end_func: "callable[[tsi.CallEndReq], tsi.CallEndRes]",
        call_read_func: "callable[[tsi.CallReadReq], tsi.CallReadRes]",
        calls_query_stream_func: "callable[[tsi.CallsQueryReq], Iterator[tsi.CallSchema]]",
        feedback_create_func: "callable[[tsi.FeedbackCreateReq], tsi.FeedbackCreateRes]",
        select_objs_query_func: "callable[[ObjectMetadataQueryBuilder, bool], list[Any]]",
        obj_read_with_retry_func: "callable[[tsi.ObjReadReq], tsi.ObjReadRes]",
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

        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
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
