import json
import typing
import weakref
from typing import Any, Generic, Iterator, Optional, Tuple, Union, ValuesView

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

K = typing.TypeVar("K")
V = typing.TypeVar("V")


class WeakKeyDictionarySupportingNonHashableKeys(Generic[K, V]):
    def __init__(self) -> None:
        self._id_to_data: dict[int, V] = {}
        self._id_to_key: dict[int, K] = {}

    def clear(self) -> None:
        self._id_to_data.clear()
        self._id_to_key.clear()

    def get(self, key: K, default: Any = None) -> Union[V, Any]:
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __getitem__(self, key: K) -> V:
        item_id = id(key)
        return self._id_to_data[item_id]

    def __delitem__(self, key: K) -> None:
        item_id = id(key)
        if item_id in self._id_to_data:
            del self._id_to_data[item_id]
            del self._id_to_key[item_id]

    def __setitem__(self, key: K, value: V) -> None:
        item_id = id(key)
        self._id_to_data[item_id] = value
        self._id_to_key[item_id] = key
        weakref.finalize(key, self._remove_item, item_id)

    def _remove_item(self, item_id: int) -> None:
        self._id_to_data.pop(item_id, None)
        self._id_to_key.pop(item_id, None)

    def __iter__(self) -> Iterator[K]:
        return iter(self._id_to_key.values())

    def __len__(self) -> int:
        return len(self._id_to_data)

    def keys(self) -> ValuesView[K]:
        return self._id_to_key.values()

    def values(self) -> ValuesView[V]:
        return self._id_to_data.values()

    def items(self) -> Iterator[Tuple[K, V]]:
        return ((self._id_to_key[id], value) for id, value in self._id_to_data.items())


class CustomWeaveTypeSerializationCache:
    """Cache for custom weave type serialization.

    Specifically, a dev can:
    - store a serialization tuple of (deserialized object, serialized dict)
    - retrieve the serialized dict for a deserialized object
    - retrieve the deserialized object for a serialized dict

    """

    def __init__(self) -> None:
        self._obj_to_dict: WeakKeyDictionarySupportingNonHashableKeys[Any, dict] = (
            WeakKeyDictionarySupportingNonHashableKeys()
        )
        self._dict_to_obj: weakref.WeakValueDictionary[str, Any] = (
            weakref.WeakValueDictionary()
        )

    def reset(self) -> None:
        self._obj_to_dict.clear()
        self._dict_to_obj.clear()

    def store(self, obj: Any, serialized_dict: dict) -> None:
        try:
            self._store(obj, serialized_dict)
        except Exception:
            # Consider logging the exception here
            pass

    def _store(self, obj: Any, serialized_dict: dict) -> None:
        self._obj_to_dict[obj] = serialized_dict
        dict_key = self._get_dict_key(serialized_dict)
        if dict_key is not None:
            self._dict_to_obj[dict_key] = obj

    def get_serialized_dict(self, obj: Any) -> Optional[dict]:
        try:
            return self._get_serialized_dict(obj)
        except Exception:
            # Consider logging the exception here
            return None

    def _get_serialized_dict(self, obj: Any) -> Optional[dict]:
        return self._obj_to_dict.get(obj)

    def get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        try:
            return self._get_deserialized_obj(serialized_dict)
        except Exception:
            # Consider logging the exception here
            return None

    def _get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        dict_key = self._get_dict_key(serialized_dict)
        return None if dict_key is None else self._dict_to_obj.get(dict_key)

    def _get_dict_key(self, d: dict) -> Optional[str]:
        try:
            return json.dumps(d, sort_keys=True)
        except Exception:
            return None


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
