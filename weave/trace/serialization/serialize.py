from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from types import CoroutineType
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeAlias, TypedDict

from pydantic import BaseModel

from weave.shared.digest import bytes_digest
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, Ref, TableRef
from weave.trace.serialization import custom_objs
from weave.trace.serialization.dictifiable import try_to_dict
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    TraceServerInterface,
)
from weave.utils.sanitize import REDACTED_VALUE, should_redact

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


# A JSON-safe value — the target shape every encoder produces on match. The
# leaf types line up with what json.dumps accepts; the recursion covers nested
# containers. Some encoder outputs are typed ``Any`` in practice (e.g. dictify,
# or registry-produced CustomWeaveType payloads), but they still conform
# structurally via the ``Any``-inside-``dict``/``list`` branches.
JsonValue: TypeAlias = bool | int | float | str | list[Any] | dict[str, Any] | None


class _MissType:
    """Type of the ``_MISS`` sentinel — a distinct class so encoders can
    declare "I might decline" in their return type without collapsing to
    ``Any``. Exactly one instance exists (``_MISS``).
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<_MISS>"


# Sentinel returned by an encoder when the input is not its responsibility.
_MISS: _MissType = _MissType()


class Encoder(Protocol):
    """A single step in the ``to_json`` priority ladder.

    Called once per candidate value. The encoder either claims the value and
    returns its JSON-safe encoded form, or declines by returning the ``_MISS``
    sentinel — in which case ``to_json`` tries the next encoder in order.

    Contract:
        - Never mutate ``obj``.
        - Never raise for "not my type" — return ``_MISS``. Exceptions should
          be reserved for genuine encoding failures (bad state, I/O errors).
        - Recurse through ``to_json`` for nested values rather than calling
          other encoders directly, so the full ladder applies uniformly.
    """

    def __call__(
        self,
        obj: Any,
        project_id: str,
        client: WeaveClient,
        use_dictify: bool,
    ) -> JsonValue | _MissType: ...


def to_json(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool = False
) -> Any:
    """Encode an arbitrary Python value to a JSON-safe payload.

    Dispatch is a priority ladder. Each encoder below is asked in order;
    the first one to return a non-_MISS value wins. ``stringify`` is the
    terminal fallback and always succeeds.

    Order:
        1. _encode_ref                 Ref (TableRef, ObjectRef) -> URI string
        2. _encode_object_record       ObjectRecord wrapper
        3. _encode_container           namedtuple / list / tuple / dict
        4. _encode_pydantic_schema     pydantic class (not instance) -> schema
        5. _encode_primitive           int / float / str / bool / None
        6. _encode_weave_scorer_result WeaveScorerResult (special case)
        7. _encode_custom_obj          registered type serializers
        8. _encode_dictify             use_dictify fallback
        9. _encode_try_to_dict         duck-typed to_dict fallback
       10. stringify                   repr/str terminal fallback
    """
    for encoder in _ENCODERS:
        result = encoder(obj, project_id, client, use_dictify)
        if not isinstance(result, _MissType):
            return result
    return stringify(obj)


def _encode_ref(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if isinstance(obj, (TableRef, ObjectRef)):
        return obj.uri
    return _MISS


def _encode_object_record(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if not isinstance(obj, ObjectRecord):
        return _MISS
    res: dict[str, Any] = {"_type": obj._class_name}
    for k, v in obj.__dict__.items():
        if k == "ref":
            # Refs are pointers to remote objects and should not appear in a
            # serialized payload — the client attaches them after save. A ref
            # showing up here is almost certainly a bug, but we log rather
            # than raise to avoid dropping user data.
            if v is not None:
                logging.exception("Unexpected ref in object record: %s", obj)
            else:
                logging.warning("Unexpected null ref in object record: %s", obj)
                continue
        res[k] = to_json(v, project_id, client, use_dictify)
    return res


def _encode_container(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if isinstance_namedtuple(obj):
        return {
            k: to_json(v, project_id, client, use_dictify)
            for k, v in obj._asdict().items()
        }
    if isinstance(obj, (list, tuple)):
        return [to_json(v, project_id, client, use_dictify) for v in obj]
    if isinstance(obj, dict):
        return {k: to_json(v, project_id, client, use_dictify) for k, v in obj.items()}
    return _MISS


def _encode_pydantic_schema(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if is_pydantic_model_class(obj):
        return obj.model_json_schema()
    return _MISS


def _encode_primitive(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return _MISS


def _encode_weave_scorer_result(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    # Phase-3 target: replace with a registered serializer in weave/flow/scorer.py.
    from weave.flow.scorer import WeaveScorerResult

    if isinstance(obj, WeaveScorerResult):
        return {
            k: to_json(v, project_id, client, use_dictify)
            for k, v in obj.model_dump().items()
        }
    return _MISS


def _encode_custom_obj(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    # Can block on large-file I/O for file-backed serializers.
    encoded = custom_objs.encode_custom_obj(obj)
    if encoded is None:
        return _MISS
    return _build_result_from_encoded(encoded, project_id, client)


def _encode_dictify(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if (
        use_dictify
        and not isinstance(obj, ALWAYS_STRINGIFY)
        and not has_custom_repr(obj)
    ):
        return dictify(obj)
    return _MISS


def _encode_try_to_dict(
    obj: Any, project_id: str, client: WeaveClient, use_dictify: bool
) -> Any:
    if as_dict := try_to_dict(obj):
        return {
            k: to_json(v, project_id, client, use_dictify) for k, v in as_dict.items()
        }
    return _MISS


_ENCODERS: list[Encoder] = [
    _encode_ref,
    _encode_object_record,
    _encode_container,
    _encode_pydantic_schema,
    _encode_primitive,
    _encode_weave_scorer_result,
    _encode_custom_obj,
    _encode_dictify,
    _encode_try_to_dict,
]


class EncodedCustomObjDictWithFilesAsDigests(TypedDict, total=False):
    _type: Literal["CustomWeaveType"]
    weave_type: custom_objs.WeaveTypeDict
    load_op: str | None
    val: Any
    files: Mapping[str, str]


def _build_result_from_encoded(
    encoded: custom_objs.EncodedCustomObjDict, project_id: str, client: WeaveClient
) -> EncodedCustomObjDictWithFilesAsDigests:
    file_digests = {}
    for name, val in encoded.get("files", {}).items():
        # Instead of waiting for the file to be created, we
        # calculate the digest directly. This makes sure that the
        # to_json procedure is not blocked on network requests.
        # Technically it is possible that the file creation request
        # fails.
        contents_as_bytes = val
        if isinstance(contents_as_bytes, str):
            contents_as_bytes = contents_as_bytes.encode("utf-8")
        digest = bytes_digest(contents_as_bytes)
        client._send_file_create(
            FileCreateReq(
                project_id=project_id,
                name=name,
                content=val,
                expected_digest=digest,
            )
        )
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


def isinstance_namedtuple(obj: Any) -> bool:
    return (
        isinstance(obj, tuple) and hasattr(obj, "_asdict") and hasattr(obj, "_fields")
    )


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
                    files = custom_objs._load_custom_obj_files(
                        project_id, server, file_spec
                    )
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
