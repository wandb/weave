from collections.abc import Callable

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
    sanitize_name_for_object_id,
)


def apply_custom_runtime(
    req: tsi.CustomRuntimeApplyReq,
    obj_create: Callable[[tsi.ObjCreateReq], tsi.ObjCreateRes],
    objs_query: Callable[[tsi.ObjQueryReq], tsi.ObjQueryRes],
    obj_delete: Callable[[tsi.ObjDeleteReq], tsi.ObjDeleteRes],
) -> tsi.CustomRuntimeApplyRes:
    """Apply a runtime's complete desired state using existing object storage."""
    provider_object_id = sanitize_name_for_object_id(req.runtime_name)
    desired_model_ids = _build_desired_model_ids(provider_object_id, req.runtime_ids)
    provider_digests, existing_model_object_ids = _load_current_runtime_state(
        req.project_id,
        provider_object_id,
        objs_query,
    )
    _validate_storage_identities(
        req,
        provider_object_id,
        desired_model_ids,
        provider_digests,
        objs_query,
    )

    provider = Provider(
        name=req.runtime_name,
        base_url=req.base_url,
        api_key_name=req.api_key_secret or "",
        extra_headers=req.headers,
    )
    provider_result = obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=provider_object_id,
                val=provider.model_dump(exclude_none=True),
                builtin_object_class="Provider",
                wb_user_id=req.wb_user_id,
            )
        )
    )
    result_ids = _create_provider_models(
        req,
        provider_object_id,
        provider_result.digest,
        obj_create,
    )

    desired_model_object_ids = set(desired_model_ids)
    # Preserve existing IDs if a desired write fails; removals happen only after
    # the complete desired configuration has been stored successfully.
    for object_id in existing_model_object_ids - desired_model_object_ids:
        obj_delete(tsi.ObjDeleteReq(project_id=req.project_id, object_id=object_id))

    return tsi.CustomRuntimeApplyRes(
        name=req.runtime_name,
        base_url=req.base_url,
        api_key_secret=req.api_key_secret,
        headers=req.headers,
        runtime_ids=result_ids,
    )


def _build_desired_model_ids(
    provider_object_id: str,
    runtime_ids: list[tsi.CustomRuntimeID],
) -> dict[str, str]:
    desired_model_ids: dict[str, str] = {}
    for runtime_id in runtime_ids:
        object_id = _provider_model_object_id(provider_object_id, runtime_id.id)
        previous_id = desired_model_ids.setdefault(object_id, runtime_id.id)
        if previous_id != runtime_id.id:
            raise InvalidRequest(
                f"Runtime IDs {previous_id!r} and {runtime_id.id!r} map to the same storage identity"
            )
    return desired_model_ids


def _validate_storage_identities(
    req: tsi.CustomRuntimeApplyReq,
    provider_object_id: str,
    desired_model_ids: dict[str, str],
    provider_digests: set[str],
    objs_query: Callable[[tsi.ObjQueryReq], tsi.ObjQueryRes],
) -> None:
    # Sanitized IDs share the project object namespace, so detect aliases before
    # writing rather than overwriting an unrelated object.
    occupied_slots = objs_query(
        tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                object_ids=[provider_object_id, *desired_model_ids],
                latest_only=True,
            ),
        )
    ).objs
    for obj in occupied_slots:
        if obj.object_id == provider_object_id:
            if obj.base_object_class != "Provider" or obj.val.get("name") not in {
                None,
                req.runtime_name,
            }:
                raise InvalidRequest(
                    f"Runtime name {req.runtime_name!r} conflicts with existing object {provider_object_id!r}"
                )
            continue

        expected_id = desired_model_ids[obj.object_id]
        if (
            obj.base_object_class != "ProviderModel"
            or obj.val.get("name") != expected_id
            or not _references_provider_digest(
                obj.val.get("provider"), provider_digests
            )
        ):
            raise InvalidRequest(
                f"Runtime ID {expected_id!r} conflicts with existing object {obj.object_id!r}"
            )


def _load_current_runtime_state(
    project_id: str,
    provider_object_id: str,
    objs_query: Callable[[tsi.ObjQueryReq], tsi.ObjQueryRes],
) -> tuple[set[str], set[str]]:
    # A previous apply may have written a new Provider before all of its models.
    # Include every historical digest so a retry can reconcile that partial state.
    provider_versions = objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(
                object_ids=[provider_object_id],
                base_object_classes=["Provider"],
            ),
        )
    ).objs
    provider_digests = {obj.digest for obj in provider_versions}
    existing_models = objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["ProviderModel"],
                latest_only=True,
            ),
        )
    ).objs
    model_object_ids = {
        obj.object_id
        for obj in existing_models
        if _references_provider_digest(obj.val.get("provider"), provider_digests)
    }
    return provider_digests, model_object_ids


def _create_provider_models(
    req: tsi.CustomRuntimeApplyReq,
    provider_object_id: str,
    provider_digest: str,
    obj_create: Callable[[tsi.ObjCreateReq], tsi.ObjCreateRes],
) -> list[tsi.CustomRuntimeIDRes]:
    result_ids: list[tsi.CustomRuntimeIDRes] = []
    for runtime_id in req.runtime_ids:
        model_object_id = _provider_model_object_id(provider_object_id, runtime_id.id)
        provider_model = ProviderModel(
            name=runtime_id.id,
            provider=provider_digest,
            max_tokens=runtime_id.max_tokens,
        )
        obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=model_object_id,
                    val=provider_model.model_dump(exclude_none=True),
                    builtin_object_class="ProviderModel",
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        result_ids.append(
            tsi.CustomRuntimeIDRes(
                id=runtime_id.id,
                max_tokens=runtime_id.max_tokens,
                playground_id=f"custom::{req.runtime_name}::{runtime_id.id}",
            )
        )
    return result_ids


def _provider_model_object_id(provider_object_id: str, runtime_id: str) -> str:
    return f"{provider_object_id}-{sanitize_name_for_object_id(runtime_id)}"


def _references_provider_digest(
    provider_ref: object,
    provider_digests: set[str],
) -> bool:
    if not isinstance(provider_ref, str):
        return False
    return provider_ref in provider_digests
