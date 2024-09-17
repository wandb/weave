import typing
from collections import defaultdict
from typing import (
    Any,
    DefaultDict,
)

from weave.trace import custom_objs
from weave.trace.custom_weave_type_serialization_cache import (
    CustomWeaveTypeSerializationCache,
)
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace.serializer import get_serializer_for_obj
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)


def to_json(obj: Any, project_id: str, server: TraceServerInterface) -> Any:
    if isinstance(obj, TableRef):
        return obj.uri()
    elif isinstance(obj, ObjectRef):
        return obj.uri()
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            res[k] = to_json(v, project_id, server)
        return res
    elif isinstance_namedtuple(obj):
        return {k: to_json(v, project_id, server) for k, v in obj._asdict().items()}
    elif isinstance(obj, (list, tuple)):
        return [to_json(v, project_id, server) for v in obj]
    elif isinstance(obj, dict):
        return {k: to_json(v, project_id, server) for k, v in obj.items()}
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    elif get_serializer_for_obj(obj) is not None:
        return _to_json_custom_weave_type(obj, project_id, server)
    else:
        return fallback_encode(obj)


REP_LIMIT = 1000


def fallback_encode(obj: Any) -> Any:
    rep = None
    try:
        rep = repr(obj)
    except Exception:
        try:
            rep = str(obj)
        except Exception:
            rep = f"<{type(obj).__name__}: {id(obj)}>"
    if isinstance(rep, str):
        if len(rep) > REP_LIMIT:
            rep = rep[:REP_LIMIT] + "..."
    return rep


def isinstance_namedtuple(obj: Any) -> bool:
    return (
        isinstance(obj, tuple) and hasattr(obj, "_asdict") and hasattr(obj, "_fields")
    )


def _load_custom_obj_files(
    project_id: str, server: TraceServerInterface, file_digests: dict
) -> typing.Dict[str, bytes]:
    loaded_files: typing.Dict[str, bytes] = {}
    for name, digest in file_digests.items():
        file_response = server.file_content_read(
            FileContentReadReq(project_id=project_id, digest=digest)
        )
        loaded_files[name] = file_response.content
    return loaded_files


def from_json(obj: Any, project_id: str, server: TraceServerInterface) -> Any:
    if isinstance(obj, list):
        return [from_json(v, project_id, server) for v in obj]
    elif isinstance(obj, dict):
        if (val_type := obj.pop("_type", None)) is None:
            return {k: from_json(v, project_id, server) for k, v in obj.items()}
        elif val_type == "ObjectRecord":
            return ObjectRecord(
                {k: from_json(v, project_id, server) for k, v in obj.items()}
            )
        elif val_type == "CustomWeaveType":
            return _from_json_custom_weave_type(obj, project_id, server)
        else:
            return ObjectRecord(
                {k: from_json(v, project_id, server) for k, v in obj.items()}
            )
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

    return obj


# _[to/from]_json_custom_weave_type are used to serialize and deserialize
# objects that have custom serialization logic. These are NOT weave.Objects,
# but rather things like PIL Images. These methods are inverses of each other.
# Importantly we can actually cache the results of both directions so that we
# don't have to do the work more than once.

# Initialize the global cache
_custom_weave_type_cache_map: DefaultDict[str, CustomWeaveTypeSerializationCache] = (
    defaultdict(CustomWeaveTypeSerializationCache)
)


def _to_json_custom_weave_type(
    obj: Any, project_id: str, server: TraceServerInterface
) -> dict:
    # Check if the object is already in the cache
    cached_result = _custom_weave_type_cache_map[project_id].get_serialized_dict(obj)
    if cached_result is not None:
        return cached_result

    encoded = custom_objs.encode_custom_obj(obj)
    if encoded is None:
        raise ValueError(f"No encoder for object: {obj}")

    file_digests: dict[str, str] = {}
    for name, val in encoded["files"].items():
        file_response = server.file_create(
            FileCreateReq(project_id=project_id, name=name, content=val)
        )
        file_digests[name] = file_response.digest

    result = {
        "_type": encoded["_type"],
        "weave_type": encoded["weave_type"],
        "files": file_digests,
    }

    load_op_uri = encoded.get("load_op")
    if load_op_uri:
        result["load_op"] = load_op_uri

    # Store the result in the cache
    _custom_weave_type_cache_map[project_id].store(obj, result)
    return result


def _from_json_custom_weave_type(
    obj: dict, project_id: str, server: TraceServerInterface
) -> Any:
    # Check if the serialized dict is already in the cache
    cached_result = _custom_weave_type_cache_map[project_id].get_deserialized_obj(obj)
    if cached_result is not None:
        return cached_result

    files = _load_custom_obj_files(project_id, server, obj["files"])
    result = custom_objs.decode_custom_obj(obj["weave_type"], files, obj.get("load_op"))

    # Store the result in the cache
    _custom_weave_type_cache_map[project_id].store(result, obj)
    return result
