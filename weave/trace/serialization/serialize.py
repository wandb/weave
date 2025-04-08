from __future__ import annotations

import logging
from collections.abc import Sequence
from types import CoroutineType
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace.sanitize import REDACTED_VALUE, should_redact
from weave.trace.serialization import custom_objs
from weave.trace.serialization.dictifiable import try_to_dict
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY,
)
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.trace_server.trace_server_interface_util import bytes_digest

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


def is_pydantic_model_class(obj: Any) -> bool:
    """Determine if obj is a subclass of pydantic.BaseModel."""
    try:
        return (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
        )
    except TypeError:
        # Might be something like Iterable[CalendarEvent]
        return False


def _is_inline_custom_obj(encoded: dict) -> bool:
    """Custom object values may be inline or backed by a file.

    This separate function for readability checks which we are dealing with."""
    return "val" in encoded


def to_json(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool = False
) -> Any:
    if isinstance(obj, TableRef):
        return obj.uri()
    elif isinstance(obj, ObjectRef):
        return obj.uri()
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            res[k] = to_json(v, project_id, client, use_dictify)
        return res
    elif isinstance_namedtuple(obj):
        return {
            k: to_json(v, project_id, client, use_dictify)
            for k, v in obj._asdict().items()
        }
    elif isinstance(obj, (list, tuple)):
        return [to_json(v, project_id, client, use_dictify) for v in obj]
    elif isinstance(obj, dict):
        return {k: to_json(v, project_id, client, use_dictify) for k, v in obj.items()}
    elif is_pydantic_model_class(obj):
        return obj.model_json_schema()

    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj

    # Add explicit handling for WeaveScorerResult models
    from weave.flow.scorer import WeaveScorerResult

    if isinstance(obj, WeaveScorerResult):
        return {
            k: to_json(v, project_id, client, use_dictify)
            for k, v in obj.model_dump().items()
        }

    # This still blocks potentially on large-file i/o.
    encoded = custom_objs.encode_custom_obj(obj)
    if encoded is None:
        if (
            use_dictify
            and not isinstance(obj, ALWAYS_STRINGIFY)
            and not has_custom_repr(obj)
        ):
            return dictify(obj)

        # TODO: I would prefer to only have this once in dictify? Maybe dictify and to_json need to be merged?
        # However, even if dictify is false, i still want to try to convert to dict
        elif as_dict := try_to_dict(obj):
            return {
                k: to_json(v, project_id, client, use_dictify)
                for k, v in as_dict.items()
            }
        return fallback_encode(obj)
    if _is_inline_custom_obj(encoded):
        return encoded
    result = _build_result_from_encoded(encoded, project_id, client)
    return result


def _build_result_from_encoded(
    encoded: dict, project_id: str, client: WeaveClient
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


MAX_STR_LEN = 1000


def stringify(obj: Any, limit: int = MAX_STR_LEN) -> str:
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


def is_primitive(obj: Any) -> bool:
    """Check if an object is a known primitive type."""
    return isinstance(obj, (int, float, str, bool, type(None)))


def has_custom_repr(obj: Any) -> bool:
    """Return True if the object has a custom __repr__ method."""
    return obj.__class__.__repr__ is not object.__repr__


def dictify(
    obj: Any, maxdepth: int = 0, depth: int = 1, seen: set[int] | None = None
) -> Any:
    """Recursively compute a dictionary representation of an object."""
    if seen is None:
        seen = set()

    if not is_primitive(obj):
        obj_id = id(obj)
        if obj_id in seen:
            # Avoid infinite recursion with circular references
            return stringify(obj)
        else:
            seen.add(obj_id)

    if maxdepth > 0 and depth > maxdepth:
        # TODO: If obj at this point is a simple type,
        #       maybe we should just return it rather than stringify
        return stringify(obj)

    if is_primitive(obj):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [dictify(v, maxdepth, depth + 1, seen) for v in obj]
    elif isinstance(obj, dict):
        dict_result = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                dict_result[k] = REDACTED_VALUE
            else:
                dict_result[k] = dictify(v, maxdepth, depth + 1, seen)
        return dict_result

    if hasattr(obj, "to_dict"):
        try:
            as_dict = obj.to_dict()
            if isinstance(as_dict, dict):
                to_dict_result = {}
                for k, v in as_dict.items():
                    if isinstance(k, str) and should_redact(k):
                        to_dict_result[k] = REDACTED_VALUE
                    elif maxdepth == 0 or depth < maxdepth:
                        to_dict_result[k] = dictify(v, maxdepth, depth + 1)
                    else:
                        to_dict_result[k] = stringify(v)
                return to_dict_result
        except Exception:
            raise ValueError("to_dict failed")

    result: dict[Any, Any] = {}
    result["__class__"] = {
        "module": obj.__class__.__module__,
        "qualname": obj.__class__.__qualname__,
        "name": obj.__class__.__name__,
    }
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        # Custom list-like object
        try:
            for i, item in enumerate(obj):
                result[i] = dictify(item, maxdepth, depth + 1, seen)
        except Exception:
            return stringify(obj)
    else:
        for attr in dir(obj):
            if attr.startswith("_"):
                continue
            if should_redact(attr):
                result[attr] = REDACTED_VALUE
                continue
            try:
                val = getattr(obj, attr)
                if callable(val):
                    continue
                if maxdepth == 0 or depth < maxdepth:
                    result[attr] = dictify(val, maxdepth, depth + 1, seen)
                else:
                    result[attr] = stringify(val)
            except Exception:
                return stringify(obj)
    return result


# TODO: Investigate why dictifying Logger causes problems
ALWAYS_STRINGIFY = (logging.Logger, CoroutineType)


# Note: Max depth not picked scientifically, just trying to keep things under control.
DEFAULT_MAX_DICTIFY_DEPTH = 10


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
        if len(rep) > MAX_STR_LEN:
            rep = rep[:MAX_STR_LEN] + "..."
    return rep


def isinstance_namedtuple(obj: Any) -> bool:
    return (
        isinstance(obj, tuple) and hasattr(obj, "_asdict") and hasattr(obj, "_fields")
    )


def _load_custom_obj_files(
    project_id: str, server: TraceServerInterface, file_digests: dict
) -> dict[str, bytes]:
    loaded_files: dict[str, bytes] = {}
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
            if _is_inline_custom_obj(obj):
                return custom_objs.decode_custom_inline_obj(obj)
            files = _load_custom_obj_files(project_id, server, obj["files"])
            return custom_objs.decode_custom_files_obj(
                obj["weave_type"], files, obj.get("load_op")
            )
        elif (
            isinstance(val_type, str)
            and obj.get("_class_name") == val_type
            and (builtin_object_class := BUILTIN_OBJECT_REGISTRY.get(val_type))
        ):
            return builtin_object_class.model_validate(obj)
        else:
            return ObjectRecord(
                {k: from_json(v, project_id, server) for k, v in obj.items()}
            )
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

    return obj
