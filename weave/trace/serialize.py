import typing
from typing import Any

from weave.trace import custom_objs
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.trace_server.trace_server_interface_util import bytes_digest

if typing.TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


def to_json(obj: Any, project_id: str, client: "WeaveClient") -> Any:
    if isinstance(obj, TableRef):
        return obj.uri()
    elif isinstance(obj, ObjectRef):
        return obj.uri()
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            res[k] = to_json(v, project_id, client)
        return res
    elif isinstance_namedtuple(obj):
        return {k: to_json(v, project_id, client) for k, v in obj._asdict().items()}
    elif isinstance(obj, (list, tuple)):
        return [to_json(v, project_id, client) for v in obj]
    elif isinstance(obj, dict):
        return {k: to_json(v, project_id, client) for k, v in obj.items()}

    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj

    # This still blocks potentially on large-file i/o.
    encoded = custom_objs.encode_custom_obj(obj)
    if encoded is None:
        return fallback_encode(obj)
    result = _build_result_from_encoded(encoded, project_id, client)

    return result


def _build_result_from_encoded(
    encoded: dict, project_id: str, client: "WeaveClient"
) -> Any:
    file_digests = {}
    for name, val in encoded["files"].items():
        # Instead of waiting for the file to be created, we
        # calculate the digest directly. This makes sure that the
        # to_json procedure is not blocked on network requests.
        # Technically it is possible that the file creation request
        # fails.
        client._send_file_create(
            FileCreateReq(project_id=project_id, name=name, content=val)
        )
        contents_as_bytes = val
        if isinstance(contents_as_bytes, str):
            contents_as_bytes = contents_as_bytes.encode("utf-8")
        digest = bytes_digest(contents_as_bytes)
        file_digests[name] = digest
    result = {
        "_type": encoded["_type"],
        "weave_type": encoded["weave_type"],
        "files": file_digests,
    }
    load_op_uri = encoded.get("load_op")
    if load_op_uri:
        result["load_op"] = load_op_uri
    return result


STR_LENGTH_LIMIT = 1000


def stringify(obj: Any, limit: int = STR_LENGTH_LIMIT) -> str:
    """This is a fallback for objects that we don't have a better way to serialize."""
    rep = None
    try:
        rep = repr(obj)
    except Exception:
        try:
            rep = str(obj)
        except Exception:
            rep = f"<{type(obj).__name__}: {id(obj)}>"
    if isinstance(rep, str):
        if len(rep) > limit:
            rep = rep[: limit - 3] + "..."
    return rep


def dictify(obj: Any, maxdepth: int = 0, depth=1) -> Any:
    """Recursively compute a dictionary representation of an object."""
    if maxdepth > 0 and depth > maxdepth:
        # TODO: If obj at this point is a simple type,
        #       maybe we should just return it rather than stringify
        return stringify(obj)

    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    elif isinstance(obj, (list, tuple)):
        return [dictify(v, maxdepth, depth + 1) for v in obj]
    elif isinstance(obj, dict):
        return {k: dictify(v, maxdepth, depth + 1) for k, v in obj.items()}

    if hasattr(obj, "to_dict"):
        try:
            as_dict = obj.to_dict()
            if isinstance(as_dict, dict):
                result = {}
                for k, v in as_dict.items():
                    if maxdepth == 0 or depth < maxdepth:
                        result[k] = dictify(v, maxdepth, depth + 1)
                    else:
                        result[k] = stringify(v)
                return result
        except Exception:
            raise ValueError("to_dict failed")

    result = {}
    result["__class__"] = {
        "module": obj.__class__.__module__,
        "qualname": obj.__class__.__qualname__,
        "name": obj.__class__.__name__,
    }
    for attr in dir(obj):
        if attr.startswith("_"):
            continue
        try:
            val = getattr(obj, attr)
            if callable(val):
                continue
            if maxdepth == 0 or depth < maxdepth:
                result[attr] = dictify(val, maxdepth, depth + 1)
            else:
                result[attr] = stringify(val)
        except Exception:
            raise ValueError("fallback dictify failed")
    return result


def fallback_encode(obj: Any) -> Any:
    # TODO: Should we try to compute an object size and skip if too big?
    try:
        # Note: Max depth not picked scientifically, just trying to keep things under control.
        return dictify(obj, maxdepth=10)
    except Exception:
        return stringify(obj)


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
            files = _load_custom_obj_files(project_id, server, obj["files"])
            return custom_objs.decode_custom_obj(
                obj["weave_type"], files, obj.get("load_op")
            )
        else:
            return ObjectRecord(
                {k: from_json(v, project_id, server) for k, v in obj.items()}
            )
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

    return obj
