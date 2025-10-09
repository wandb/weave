from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Callable

from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import is_op, op
from weave.trace.op_protocol import Op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.serialization import (
    op_type,  # noqa: F401, Must import this to register op save/load
)
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.serializer import (
    get_serializer_by_id,
    get_serializer_for_obj,
    is_inline_save,
)


class DecodeCustomObjectError(Exception):
    """An error that occurs while decoding a custom object."""


# in future, could generalize as
# {target_cls.__module__}.{target_cls.__qualname__}
KNOWN_TYPES = {
    "Op",
    "PIL.Image.Image",
    "wave.Wave_read",
    "weave.type_handlers.Audio.audio.Audio",
    "datetime.datetime",
    "rich.markdown.Markdown",
    "moviepy.video.VideoClip.VideoClip",
    "weave.type_wrappers.Content.content.Content",
}


def encode_custom_obj(obj: Any) -> dict | None:
    serializer = get_serializer_for_obj(obj)
    if serializer is None:
        # We silently return None right now. We could warn here. This object
        # will not be recoverable with client.get
        return None

    # Save the load function as an op, and store a reference
    # to that op in the saved value record. We don't do this if what
    # we're saving is actually an op, since that would be self-referential
    # (the op loading code is always present, we don't need to save/load it).
    load_op_uri = None
    if serializer.id() != "Op":
        # Ensure load is an op
        if not isinstance(serializer.load, Op):
            serializer.load = op(serializer.load)
            # We don't want to actually trace the load_instance op,
            # just save it.
            serializer.load._tracing_enabled = False  # type: ignore
        # Save the load_instance_op
        wc = require_weave_client()

        # TODO(PR): this can fail right? Or does it return None?
        # Calculating this URL is blocking, but we only have to pay it once per custom type
        load_instance_op_ref = wc._save_op(serializer.load, "load_" + serializer.id())  # type: ignore
        load_op_uri = load_instance_op_ref.uri()

    encoded = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": serializer.id()},
        "load_op": load_op_uri,
    }

    # Dispatch based on signature
    if is_inline_save(serializer.save):
        # Inline: (obj) -> metadata
        encoded["val"] = serializer.save(obj)
    else:
        # File-based: (obj, artifact, name) -> metadata | None
        art = MemTraceFilesArtifact()
        metadata = serializer.save(obj, art, "obj")

        if art.path_contents:
            encoded["files"] = {
                k: (v.encode("utf-8") if isinstance(v, str) else v)  # type: ignore
                for k, v in art.path_contents.items()
            }

        if metadata is not None:
            encoded["val"] = metadata

    return encoded


def decode_custom_inline_obj(obj: dict) -> Any:
    type_ = obj["weave_type"]["type"]
    if type_ in KNOWN_TYPES:
        serializer = get_serializer_by_id(type_)
        if serializer is not None:
            # Use inspection to determine load signature
            # New API: load(artifact, name, metadata) - 3 params
            # Legacy inline: load(val) - 1 param
            sig = inspect.signature(serializer.load)
            param_count = len(sig.parameters)

            if param_count == 3:
                # New WeaveSerializer API
                art = MemTraceFilesArtifact()
                metadata = obj.get("val")
                return serializer.load(art, "obj", metadata)
            else:
                # Legacy inline API
                if is_op(serializer.load):
                    # We would expect this to be already set to False, but
                    # just in case.
                    serializer.load._tracing_enabled = False  # type: ignore
                return serializer.load(obj["val"])

    load_op_uri = obj.get("load_op")
    if load_op_uri is None:
        raise ValueError(f"No serializer found for `{type_}`")

    op_ref = OpRef.parse_uri(load_op_uri)
    wc = require_weave_client()
    load_instance_op = wc.get(op_ref)
    if load_instance_op is None:
        raise ValueError(
            f"Failed to load op needed to decode object of type `{type_}`. See logs above for more information."
        )

    load_instance_op._tracing_enabled = False  # type: ignore
    return load_instance_op(obj.get("val"))


def _decode_custom_files_obj(
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op: Callable[..., Any],
    metadata: Any | None = None,
) -> Any:
    art = MemTraceFilesArtifact(encoded_path_contents, metadata={})

    # Use inspection to determine the signature of the load function
    # WeaveSerializer.load has signature (artifact, name, metadata)
    # Legacy file-based has signature (artifact, name)
    sig = inspect.signature(load_instance_op)
    param_count = len(sig.parameters)

    if param_count == 3:
        # New API: load function takes (artifact, name, metadata)
        res = load_instance_op(art, "obj", metadata)
    elif param_count == 2:
        # Legacy API: load function takes (artifact, name)
        load_instance_op._tracing_enabled = False  # type: ignore
        res = load_instance_op(art, "obj")
    else:
        raise ValueError(
            f"Unexpected load function signature with {param_count} parameters. "
            f"Expected 2 (artifact, name) or 3 (artifact, name, metadata)"
        )

    res.art = art
    return res


def decode_custom_files_obj(
    weave_type: dict,
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op_uri: str | None = None,
    metadata: Any | None = None,
) -> Any:
    type_ = weave_type["type"]
    found_serializer = False

    # First, try to load the object using a known serializer
    if type_ in KNOWN_TYPES:
        serializer = get_serializer_by_id(type_)
        if serializer is not None:
            found_serializer = True
            load_instance_op = serializer.load

            try:
                return _decode_custom_files_obj(
                    encoded_path_contents, load_instance_op, metadata
                )
            except Exception as e:
                pass

    # Otherwise, fall back to load_instance_op from the saved op URI
    # This handles cases where the serializer isn't registered or is from a prior version
    if not found_serializer:
        if load_instance_op_uri is None:
            raise ValueError(f"No serializer found for `{type_}`")

        obj_ref = ObjectRef.parse_uri(load_instance_op_uri)
        wc = require_weave_client()
        load_instance_op = wc.get(obj_ref)
        if load_instance_op is None:
            raise ValueError(
                f"Failed to load op needed to decode object of type `{type_}`. See logs above for more information."
            )

    try:
        return _decode_custom_files_obj(encoded_path_contents, load_instance_op, metadata)
    except Exception as e:
        raise DecodeCustomObjectError(
            f"Failed to decode object of type `{type_}`. See logs above for more information."
        ) from e
