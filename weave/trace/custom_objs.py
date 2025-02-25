from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Literal, TypedDict, Union

from weave.trace import op_type  # noqa: F401, Must import this to register op save/load
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.mem_artifact import MemTraceFilesArtifact
from weave.trace.op import Op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.serializer import get_serializer_by_id, get_serializer_for_obj


class DecodeCustomObjectError(Exception):
    """An error that occurs while decoding a custom object."""


# in future, could generalize as
# {target_cls.__module__}.{target_cls.__qualname__}
KNOWN_TYPES = {
    "Op",
    "PIL.Image.Image",
    "wave.Wave_read",
    "datetime.datetime",
}


class WeaveTypeInfo(TypedDict):
    """Information about the Weave type being serialized."""

    type: str


class ArtifactBasedCustomObject(TypedDict):
    """A custom object serialized using artifact-based serialization."""

    _type: Literal["CustomWeaveType"]
    weave_type: WeaveTypeInfo
    files: dict[str, str | bytes]
    load_op: str | None


class InlineCustomObject(TypedDict):
    """A custom object serialized using inline serialization."""

    _type: Literal["CustomWeaveType"]
    weave_type: WeaveTypeInfo
    inline_data: Any


# Union type representing either serialization approach
SerializedCustomObject = Union[ArtifactBasedCustomObject, InlineCustomObject]


def encode_custom_obj(obj: Any) -> SerializedCustomObject | None:
    """Encode a custom object into a serialized representation.

    This function attempts to serialize an object using either inline serialization
    or artifact-based serialization, depending on the capabilities of the serializer.

    Args:
        obj: The object to serialize

    Returns:
        A serialized representation of the object, or None if no serializer is found
    """
    serializer = get_serializer_for_obj(obj)
    if serializer is None:
        # We silently return None right now. We could warn here. This object
        # will not be recoverable with client.get
        return None

    # Use inline serialization if available
    if serializer.inline_serialize is not None:
        inline_data = serializer.inline_serialize(obj)
        return InlineCustomObject(
            _type="CustomWeaveType",
            weave_type=WeaveTypeInfo(type=serializer.id()),
            inline_data=inline_data,
        )

    # Fall back to artifact-based serialization
    art = MemTraceFilesArtifact()
    serializer.save(obj, art, "obj")

    # Save the load_instance function as an op, and store a reference
    # to that op in the saved value record. We don't do this if what
    # we're saving is actually an op, since that would be self-referential
    # (the op loading code is always present, we don't need to save/load it).
    load_op_uri = None
    if serializer.id() != "Op":
        # Ensure load_instance is an op
        if not isinstance(serializer.load, Op):
            serializer.load = op(serializer.load)
        # Save the load_intance_op
        wc = require_weave_client()

        # TODO(PR): this can fail right? Or does it return None?
        # Calculating this URL is blocking, but we only have to pay it once per custom type
        load_instance_op_ref = wc._save_op(serializer.load, "load_" + serializer.id())  # type: ignore
        load_op_uri = load_instance_op_ref.uri()

    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)  # type: ignore
        for k, v in art.path_contents.items()
    }
    return ArtifactBasedCustomObject(
        _type="CustomWeaveType",
        weave_type=WeaveTypeInfo(type=serializer.id()),
        files=encoded_path_contents,
        load_op=load_op_uri,
    )


def _decode_custom_obj(
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op: Callable[..., Any],
) -> Any:
    # Disables tracing so that calls to loading data itself don't get traced
    load_instance_op._tracing_enabled = False  # type: ignore
    art = MemTraceFilesArtifact(encoded_path_contents, metadata={})
    res = load_instance_op(art, "obj")
    # Only set the art attribute if the object supports it
    if hasattr(res, "art"):
        res.art = art
    return res


def _decode_custom_obj_inline(
    weave_type: WeaveTypeInfo,
    inline_data: Any,
) -> Any:
    """Decode a custom object using inline serialization.

    Args:
        weave_type: Information about the Weave type being deserialized
        inline_data: The inline data to deserialize

    Returns:
        The deserialized object

    Raises:
        ValueError: If no inline deserializer is found for the type
    """
    _type = weave_type["type"]

    if _type not in KNOWN_TYPES:
        raise ValueError(f"No known serializer for type `{_type}`")

    serializer = get_serializer_by_id(_type)
    if serializer is None or serializer.inline_deserialize is None:
        raise ValueError(f"No inline deserializer found for `{_type}`")

    return serializer.inline_deserialize(inline_data)


def _decode_custom_obj_artifact(
    weave_type: WeaveTypeInfo,
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op_uri: str | None = None,
) -> Any:
    """Decode a custom object using artifact-based serialization.

    Args:
        weave_type: Information about the Weave type being deserialized
        encoded_path_contents: The encoded file contents
        load_instance_op_uri: The URI of the load operation, if needed

    Returns:
        The deserialized object

    Raises:
        ValueError: If no serializer is found for the type
        TypeError: If load_instance_op_uri is not an ObjectRef
        DecodeCustomObjectError: If decoding fails
    """
    _type = weave_type["type"]
    load_instance_op = None

    # First, try to use a known serializer
    if _type in KNOWN_TYPES:
        serializer = get_serializer_by_id(_type)
        if serializer is not None:
            load_instance_op = serializer.load

    # If no known serializer, try to load from the provided URI
    if load_instance_op is None:
        if load_instance_op_uri is None:
            raise ValueError(f"No serializer found for `{_type}`")

        ref = parse_uri(load_instance_op_uri)
        if not isinstance(ref, ObjectRef):
            raise TypeError(f"Expected ObjectRef, got `{type(ref)}`")

        wc = require_weave_client()
        load_instance_op = wc.get(ref)
        if load_instance_op is None:
            raise ValueError(
                f"Failed to load op needed to decode object of type `{_type}`. See logs above for more information."
            )

    try:
        return _decode_custom_obj(encoded_path_contents, load_instance_op)
    except Exception as e:
        raise DecodeCustomObjectError(
            f"Failed to decode object of type `{_type}`. See logs above for more information."
        ) from e


def decode_custom_obj(
    weave_type: WeaveTypeInfo,
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op_uri: str | None = None,
    inline_data: Any = None,
) -> Any:
    """Decode a custom object from its serialized representation.

    This function handles both artifact-based and inline serialization approaches.
    If inline_data is provided and a suitable inline deserializer exists, inline
    deserialization is used. Otherwise, artifact-based deserialization is used.

    Args:
        weave_type: Information about the Weave type being deserialized
        encoded_path_contents: The encoded file contents (required even for inline serialization)
        load_instance_op_uri: For artifact-based serialization, the URI of the load operation
        inline_data: For inline serialization, the inline data

    Returns:
        The deserialized object

    Raises:
        ValueError: If no serializer is found for the type
        TypeError: If load_instance_op_uri is not an ObjectRef
        DecodeCustomObjectError: If decoding fails
    """
    # Try inline deserialization first if inline_data is provided
    if inline_data is not None:
        try:
            return _decode_custom_obj_inline(weave_type, inline_data)
        except ValueError:
            # Fall back to artifact-based deserialization if inline fails
            pass

    # Use artifact-based deserialization
    return _decode_custom_obj_artifact(
        weave_type, encoded_path_contents, load_instance_op_uri
    )
