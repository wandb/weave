from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from types import CoroutineType
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from pydantic import BaseModel

from weave.shared.digest import bytes_digest
from weave.shared.refs_internal import WEAVE_INTERNAL_SCHEME, WEAVE_SCHEME
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, Ref, TableRef
from weave.trace.serialization import custom_objs
from weave.trace.serialization.dictifiable import try_to_dict
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.utils.sanitize import REDACTED_VALUE, should_redact

if TYPE_CHECKING:
    from collections.abc import Callable

    from weave.trace.weave_client import WeaveClient

    # Type alias for a function that converts an external ref URI string to
    # an alternative form (e.g. internal format).  When ``None`` is used in
    # place of a converter the URI is left unchanged (slow-path behaviour).
    RefConverter = Callable[[str], str]


def _convert_ext_ref_string(
    ref_str: str,
    project_id: str,
    internal_project_id: str,
    client: WeaveClient | None = None,
) -> str:
    """Convert an external ``weave:///`` ref URI to ``weave-trace-internal:///`` format.

    Same-project refs use the pre-resolved *internal_project_id*.
    Cross-project refs are resolved lazily via
    ``client._resolve_ext_to_int_project_id``; when resolution is not
    possible the original URI is returned so the server can handle it.
    """
    prefix = f"{WEAVE_SCHEME}:///"
    if not ref_str.startswith(prefix):
        return ref_str
    rest = ref_str[len(prefix) :]
    parts = rest.split("/", 2)
    if len(parts) != 3:
        raise ValueError(f"Malformed ref URI, expected 3 path segments: {ref_str}")
    entity_project = f"{parts[0]}/{parts[1]}"
    if entity_project == project_id:
        return f"{WEAVE_INTERNAL_SCHEME}:///{internal_project_id}/{parts[2]}"
    # Cross-project: attempt lazy resolution, fall back to original URI.
    if client is None:
        return ref_str
    resolved = client._resolve_ext_to_int_project_id(entity_project)
    if resolved is None:
        return ref_str
    return f"{WEAVE_INTERNAL_SCHEME}:///{resolved}/{parts[2]}"


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


def to_json(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool = False
) -> Any:
    """Serialize *obj* to a JSON-compatible value.

    This is the public entry point.  Today it always takes the slow path
    (external ``weave:///`` refs, no ``expected_digest`` on file uploads).
    When the client-side-digests feature is wired up, the dispatcher here
    will call ``_to_json_fast`` instead.
    """
    return _to_json_slow(obj, project_id, client, use_dictify)


def _to_json_slow(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool = False
) -> Any:
    """Slow path: refs stay as ``weave:///`` URIs, no ``expected_digest``."""
    return _to_json_impl(obj, project_id, client, use_dictify, ref_converter=None)


def _to_json_fast(
    obj: Any,
    project_id: str,
    client: WeaveClient,
    use_dictify: bool = False,
    *,
    internal_project_id: str,
) -> Any:
    """Fast path: refs become ``weave-trace-internal:///`` URIs and file
    uploads include ``expected_digest``.

    *internal_project_id* is the server-side UUID for the current project.
    """

    def convert_ref(uri: str) -> str:
        return _convert_ext_ref_string(uri, project_id, internal_project_id, client)

    return _to_json_impl(obj, project_id, client, use_dictify, ref_converter=convert_ref)


# ── shared recursive implementation ──────────────────────────────────


def _to_json_impl(
    obj: Any,
    project_id: str,
    client: WeaveClient,
    use_dictify: bool,
    ref_converter: RefConverter | None,
) -> Any:
    recurse = _to_json_impl  # local alias for brevity

    if isinstance(obj, (TableRef, ObjectRef)):
        uri = obj.uri
        return ref_converter(uri) if ref_converter else uri
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            if k == "ref":
                # Refs are pointers to remote objects and should not be part of
                # the serialized payload. They are attached by the client after
                # the object is saved and returned from the server. If we encounter
                # a ref in the serialized payload, this would almost certainly be a
                # bug. However, we would prefer not to raise and error as that would
                # result in lost data. These refs should be removed before serialization.
                if v is not None:
                    logging.exception(f"Unexpected ref in object record: {obj}")
                else:
                    logging.warning(f"Unexpected null ref in object record: {obj}")
                    continue
            res[k] = recurse(v, project_id, client, use_dictify, ref_converter)
        return res
    elif isinstance_namedtuple(obj):
        return {
            k: recurse(v, project_id, client, use_dictify, ref_converter)
            for k, v in obj._asdict().items()
        }
    elif isinstance(obj, (list, tuple)):
        return [recurse(v, project_id, client, use_dictify, ref_converter) for v in obj]
    elif isinstance(obj, dict):
        return {
            k: recurse(v, project_id, client, use_dictify, ref_converter)
            for k, v in obj.items()
        }
    elif is_pydantic_model_class(obj):
        return obj.model_json_schema()

    if isinstance(obj, (int, float, str, bool)) or obj is None:
        # String values may contain embedded ref URIs (e.g. from prior
        # serialization).  On the fast path we convert them too.
        if (
            isinstance(obj, str)
            and ref_converter is not None
            and obj.startswith(f"{WEAVE_SCHEME}:///")
        ):
            return ref_converter(obj)
        return obj

    # Add explicit handling for WeaveScorerResult models
    from weave.flow.scorer import WeaveScorerResult

    if isinstance(obj, WeaveScorerResult):
        return {
            k: recurse(v, project_id, client, use_dictify, ref_converter)
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
                k: recurse(v, project_id, client, use_dictify, ref_converter)
                for k, v in as_dict.items()
            }
        return fallback_encode(obj)
    result = _build_result_from_encoded(
        encoded, project_id, client, include_expected_digest=ref_converter is not None
    )
    # Convert load_op URI on the fast path.
    if ref_converter is not None:
        load_op = result.get("load_op")
        if isinstance(load_op, str) and load_op.startswith(f"{WEAVE_SCHEME}:///"):
            result["load_op"] = ref_converter(load_op)
    return result


class EncodedCustomObjDictWithFilesAsDigests(TypedDict, total=False):
    _type: Literal["CustomWeaveType"]
    weave_type: custom_objs.WeaveTypeDict
    load_op: str | None
    val: Any
    files: Mapping[str, str]


def _build_result_from_encoded(
    encoded: custom_objs.EncodedCustomObjDict,
    project_id: str,
    client: WeaveClient,
    include_expected_digest: bool = False,
) -> EncodedCustomObjDictWithFilesAsDigests:
    file_digests = {}
    for name, val in encoded.get("files", {}).items():
        # Calculate the digest up-front so to_json is never blocked on
        # the network.  The file creation request is fired asynchronously.
        contents_as_bytes = val
        if isinstance(contents_as_bytes, str):
            contents_as_bytes = contents_as_bytes.encode("utf-8")
        digest = bytes_digest(contents_as_bytes)

        req = FileCreateReq(project_id=project_id, name=name, content=val)
        if include_expected_digest:
            req.expected_digest = digest
        client._send_file_create(req)
        file_digests[name] = digest

    result: EncodedCustomObjDictWithFilesAsDigests = {
        "_type": encoded["_type"],
        "weave_type": encoded["weave_type"],
    }
    if file_digests:
        result["files"] = file_digests
    if "val" in encoded:
        result["val"] = encoded["val"]
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
    if isinstance(rep, str) and len(rep) > limit:
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
            raise ValueError("to_dict failed") from None

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
    if isinstance(rep, str) and len(rep) > MAX_STR_LEN:
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
            encoded: custom_objs.EncodedCustomObjDict = {
                "_type": "CustomWeaveType",
                "weave_type": obj["weave_type"],
                "load_op": obj.get("load_op"),
            }
            if "val" in obj:
                encoded["val"] = obj["val"]
            if "files" in obj:
                file_spec = obj.get("files")
                if file_spec:
                    files = _load_custom_obj_files(project_id, server, file_spec)
                    encoded["files"] = files

            return custom_objs.decode_custom_obj(encoded)
        elif isinstance(val_type, str) and obj.get("_class_name") == val_type:
            from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
                BUILTIN_OBJECT_REGISTRY,
            )

            cls = BUILTIN_OBJECT_REGISTRY.get(val_type)
            if cls:
                # Filter out metadata fields before validation
                obj_data = {
                    k: v for k, v in obj.items() if k in cls.model_fields.keys()
                }
                return cls.model_validate(obj_data)

        return ObjectRecord(
            {k: from_json(v, project_id, server) for k, v in obj.items()}
        )
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return Ref.parse_uri(obj)

    return obj
