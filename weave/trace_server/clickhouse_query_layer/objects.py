# ClickHouse Objects - Object CRUD operations

import datetime
import json
from typing import Any

import ddtrace

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import (
    ClickHouseClient,
    ensure_datetimes_have_tz,
    ensure_datetimes_have_tz_strict,
)
from weave.trace_server.clickhouse_query_layer.query_builders.objects import (
    ObjectMetadataQueryBuilder,
    format_metadata_objects_from_query_result,
    make_objects_val_query_and_parameters,
)
from weave.trace_server.clickhouse_query_layer.schema import (
    ALL_OBJ_INSERT_COLUMNS,
    ObjCHInsertable,
    ObjDeleteCHInsertable,
    SelectableCHObjSchema,
)
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import InvalidRequest, NotFoundError, ObjectDeletedError
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.trace_server_interface_util import (
    extract_refs_from_values,
    str_digest,
)


class ObjectsRepository:
    """Repository for object CRUD operations."""

    def __init__(self, ch_client: ClickHouseClient):
        self._ch_client = ch_client

    @ddtrace.tracer.wrap(name="objects_repository.obj_create")
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create a new object version."""
        processed_result = process_incoming_object_val(
            req.obj.val, req.obj.builtin_object_class
        )
        processed_val = processed_result["val"]
        json_val = json.dumps(processed_val)
        digest = str_digest(json_val)

        ch_obj = ObjCHInsertable(
            project_id=req.obj.project_id,
            object_id=req.obj.object_id,
            wb_user_id=req.obj.wb_user_id,
            kind=get_kind(processed_val),
            base_object_class=processed_result["base_object_class"],
            leaf_object_class=processed_result["leaf_object_class"],
            refs=extract_refs_from_values(processed_val),
            val_dump=json_val,
            digest=digest,
        )

        self._ch_client.insert(
            "object_versions",
            data=[list(ch_obj.model_dump().values())],
            column_names=list(ch_obj.model_fields.keys()),
        )

        return tsi.ObjCreateRes(
            digest=digest,
            object_id=req.obj.object_id,
        )

    @ddtrace.tracer.wrap(name="objects_repository.obj_create_batch")
    def obj_create_batch(
        self, batch: list[tsi.ObjSchemaForInsert]
    ) -> list[tsi.ObjCreateRes]:
        """Create multiple objects in a batch.

        This method is for the special case where all objects are known to use
        a placeholder. We lose any knowledge of what version the created object
        is in return for an enormous performance increase for operations like
        OTel ingest.

        This should **ONLY** be used when we know an object will never have
        more than one version.
        """
        set_current_span_dd_tags(
            {"objects_repository.obj_create_batch.count": str(len(batch))}
        )

        if not batch:
            return []

        obj_results = []
        ch_insert_batch = []

        unique_projects = {obj.project_id for obj in batch}
        if len(unique_projects) > 1:
            raise InvalidRequest(
                f"obj_create_batch only supports updating a single project. "
                f"Supplied projects: {unique_projects}"
            )

        for obj in batch:
            processed_result = process_incoming_object_val(
                obj.val, obj.builtin_object_class
            )
            processed_val = processed_result["val"]
            json_val = json.dumps(processed_val)
            digest = str_digest(json_val)
            ch_obj = ObjCHInsertable(
                project_id=obj.project_id,
                object_id=obj.object_id,
                wb_user_id=obj.wb_user_id,
                kind=get_kind(processed_val),
                base_object_class=processed_result["base_object_class"],
                leaf_object_class=processed_result["leaf_object_class"],
                refs=extract_refs_from_values(processed_val),
                val_dump=json_val,
                digest=digest,
            )
            insert_data = list(ch_obj.model_dump().values())
            ch_insert_batch.append(insert_data)

            obj_results.append(
                tsi.ObjCreateRes(
                    digest=digest,
                    object_id=obj.object_id,
                )
            )

        self._ch_client.insert(
            "object_versions",
            data=ch_insert_batch,
            column_names=ALL_OBJ_INSERT_COLUMNS,
        )

        return obj_results

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read a specific object version."""
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_digests_conditions(req.digest)
        object_query_builder.add_object_ids_condition([req.object_id])
        object_query_builder.set_include_deleted(include_deleted=True)
        metadata_only = req.metadata_only or False

        objs = self._select_objs_query(object_query_builder, metadata_only)
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")

        obj = objs[0]
        if obj.deleted_at is not None:
            raise ObjectDeletedError(
                f"{req.object_id}:v{obj.version_index} was deleted at {obj.deleted_at}",
                deleted_at=obj.deleted_at,
            )

        return tsi.ObjReadRes(obj=ch_obj_to_obj_schema(obj))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects with filtering."""
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        if req.filter:
            if req.filter.is_op is not None:
                object_query_builder.add_is_op_condition(req.filter.is_op)
            if req.filter.object_ids:
                object_query_builder.add_object_ids_condition(
                    req.filter.object_ids, "object_ids"
                )
            if req.filter.latest_only:
                object_query_builder.add_is_latest_condition()
            if req.filter.base_object_classes:
                object_query_builder.add_base_object_classes_condition(
                    req.filter.base_object_classes
                )
            if req.filter.exclude_base_object_classes:
                object_query_builder.add_exclude_base_object_classes_condition(
                    req.filter.exclude_base_object_classes
                )
            if req.filter.leaf_object_classes:
                object_query_builder.add_leaf_object_classes_condition(
                    req.filter.leaf_object_classes
                )
        if req.limit is not None:
            object_query_builder.set_limit(req.limit)
        if req.offset is not None:
            object_query_builder.set_offset(req.offset)
        if req.sort_by:
            for sort in req.sort_by:
                object_query_builder.add_order(sort.field, sort.direction)
        metadata_only = req.metadata_only or False
        object_query_builder.set_include_deleted(include_deleted=False)
        object_query_builder.include_storage_size = req.include_storage_size or False
        objs = self._select_objs_query(object_query_builder, metadata_only)
        return tsi.ObjQueryRes(objs=[ch_obj_to_obj_schema(obj) for obj in objs])

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """Delete object versions by digest.

        All deletion is "soft". Deletion occurs by inserting a new row into
        the object_versions table with the deleted_at field set. Inserted rows
        share identical primary keys with original rows, and will be combined
        by the ReplacingMergeTree engine at database merge time.
        """
        max_objects_to_delete = 100
        if req.digests and len(req.digests) > max_objects_to_delete:
            raise ValueError(
                f"Object delete request contains {len(req.digests)} objects. "
                f"Please delete {max_objects_to_delete} or fewer objects at a time."
            )

        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_object_ids_condition([req.object_id])
        metadata_only = True
        if req.digests:
            object_query_builder.add_digests_conditions(*req.digests)
            metadata_only = False

        object_versions = self._select_objs_query(object_query_builder, metadata_only)

        delete_insertables = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for obj in object_versions:
            original_created_at = ensure_datetimes_have_tz_strict(obj.created_at)
            delete_insertables.append(
                ObjDeleteCHInsertable(
                    project_id=obj.project_id,
                    object_id=obj.object_id,
                    digest=obj.digest,
                    kind=obj.kind,
                    val_dump=obj.val_dump,
                    refs=obj.refs,
                    base_object_class=obj.base_object_class,
                    leaf_object_class=obj.leaf_object_class,
                    deleted_at=now,
                    wb_user_id=obj.wb_user_id,
                    created_at=original_created_at,
                )
            )

        if len(delete_insertables) == 0:
            raise NotFoundError(
                f"Object {req.object_id} ({req.digests}) not found when deleting."
            )

        if req.digests:
            given_digests = set(req.digests)
            found_digests = {obj.digest for obj in delete_insertables}
            if len(given_digests) != len(found_digests):
                raise NotFoundError(
                    f"Delete request contains {len(req.digests)} digests, "
                    f"but found {len(found_digests)} objects to delete. "
                    f"Diff digests: {given_digests - found_digests}"
                )

        data = [list(obj.model_dump().values()) for obj in delete_insertables]
        column_names = list(delete_insertables[0].model_fields.keys())

        self._ch_client.insert("object_versions", data=data, column_names=column_names)
        num_deleted = len(delete_insertables)

        return tsi.ObjDeleteRes(num_deleted=num_deleted)

    def _select_objs_query(
        self,
        object_query_builder: ObjectMetadataQueryBuilder,
        metadata_only: bool = False,
    ) -> list[SelectableCHObjSchema]:
        """Main query for fetching objects.

        Args:
            object_query_builder: Query builder with conditions.
            metadata_only: If True, return early without fetching val_dump.

        Returns:
            List of SelectableCHObjSchema objects.
        """
        obj_metadata_query = object_query_builder.make_metadata_query()
        parameters = object_query_builder.parameters or {}
        query_result = self._ch_client.query_stream(obj_metadata_query, parameters)
        metadata_result = format_metadata_objects_from_query_result(
            query_result, object_query_builder.include_storage_size
        )

        if metadata_only or len(metadata_result) == 0:
            return metadata_result

        value_query, value_parameters = make_objects_val_query_and_parameters(
            project_id=object_query_builder.project_id,
            object_ids=list({row.object_id for row in metadata_result}),
            digests=list({row.digest for row in metadata_result}),
        )
        query_result = self._ch_client.query_stream(value_query, value_parameters)
        object_values: dict[tuple[str, str], Any] = {}
        for row in query_result:
            (object_id, digest, val_dump) = row
            object_values[object_id, digest] = val_dump

        for obj in metadata_result:
            obj.val_dump = object_values.get((obj.object_id, obj.digest), "{}")
        return metadata_result


# =============================================================================
# Converters and Helpers
# =============================================================================


def ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    """Convert a CH object to ObjSchema."""
    return tsi.ObjSchema(
        project_id=ch_obj.project_id,
        object_id=ch_obj.object_id,
        created_at=ensure_datetimes_have_tz(ch_obj.created_at),
        wb_user_id=ch_obj.wb_user_id,
        version_index=ch_obj.version_index,
        is_latest=ch_obj.is_latest,
        digest=ch_obj.digest,
        kind=ch_obj.kind,
        base_object_class=ch_obj.base_object_class,
        leaf_object_class=ch_obj.leaf_object_class,
        val=json.loads(ch_obj.val_dump),
        size_bytes=ch_obj.size_bytes,
    )


def get_type(val: Any) -> str:
    """Get the type string for a value."""
    if val is None:
        return "none"
    elif isinstance(val, dict):
        if "_type" in val:
            if "weave_type" in val:
                return val["weave_type"]["type"]
            return val["_type"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"


def get_kind(val: Any) -> str:
    """Get the kind (op or object) for a value."""
    val_type = get_type(val)
    if val_type == "Op":
        return "op"
    return "object"
