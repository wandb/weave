import typing
from typing import Any

from weave.legacy import box
from weave.trace import custom_objs
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
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

    if isinstance(obj, (int, float, str, bool, box.BoxedNone)) or obj is None:
        return obj

    encoded = custom_objs.encode_custom_obj(obj)
    if encoded is None:
        return fallback_encode(obj)
    file_digests = {}
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
    return result


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
        val_type = obj.get("_type")
        if val_type is not None:
            del obj["_type"]
            if val_type == "ObjectRecord":
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
        return {k: from_json(v, project_id, server) for k, v in obj.items()}
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

    return obj
