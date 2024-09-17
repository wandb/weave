import json
import typing
import weakref
from typing import Any, Optional

from weave.trace import custom_objs
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


class CustomWeaveTypeSerializationCache:
    """Cache for custom weave type serialization.

    Specifically, a dev can:
    - store a serialization tuple of (deserialized object, serialized dict)
    - retrieve the serialized dict for a deserialized object
    - retrieve the deserialized object for a serialized dict

    When keying by object:
    In addition to weak references, the cache will also attempt to call the object's `__hash__` method if it
    has one, and include that hash in the cache key. This will allow the cache
    to be effectively invalidated if the object is updated.

    When keying by dict:
    We will stringify the dict (deterministically) to create a key. This lets
    us cache the results of deserializing the same dict with different objects.
    """

    _obj_to_dict: weakref.WeakValueDictionary[str, dict]
    _dict_to_obj: weakref.WeakValueDictionary[str, Any]

    def __init__(self) -> None:
        self._obj_to_dict = weakref.WeakValueDictionary()
        self._dict_to_obj = weakref.WeakValueDictionary()

    def store(self, obj: Any, serialized_dict: dict) -> None:
        obj_key = self._get_obj_key(obj)
        dict_key = self._get_dict_key(serialized_dict)
        self._obj_to_dict[obj_key] = serialized_dict
        self._dict_to_obj[dict_key] = obj

    def get_serialized_dict(self, obj: Any) -> Optional[dict]:
        obj_key = self._get_obj_key(obj)
        return self._obj_to_dict.get(obj_key)

    def get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        dict_key = self._get_dict_key(serialized_dict)
        return self._dict_to_obj.get(dict_key)

    def _get_obj_key(self, obj: Any) -> Any:
        try:
            return (id(obj), hash(obj))
        except TypeError:
            return id(obj)

    def _get_dict_key(self, d: dict) -> str:
        return json.dumps(d, sort_keys=True)


# Initialize the global cache
_custom_weave_type_cache = CustomWeaveTypeSerializationCache()


def _to_json_custom_weave_type(
    obj: Any, project_id: str, server: TraceServerInterface
) -> dict:
    # Check if the object is already in the cache
    cached_result = _custom_weave_type_cache.get_serialized_dict(obj)
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
    _custom_weave_type_cache.store(obj, result)
    return result


def _from_json_custom_weave_type(
    obj: dict, project_id: str, server: TraceServerInterface
) -> Any:
    # Check if the serialized dict is already in the cache
    cached_result = _custom_weave_type_cache.get_deserialized_obj(obj)
    if cached_result is not None:
        return cached_result

    files = _load_custom_obj_files(project_id, server, obj["files"])
    result = custom_objs.decode_custom_obj(obj["weave_type"], files, obj.get("load_op"))

    # Store the result in the cache
    _custom_weave_type_cache.store(result, obj)
    return result
