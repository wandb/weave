from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

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


def encode_custom_obj(obj: Any) -> dict | None:
    serializer = get_serializer_for_obj(obj)
    if serializer is None:
        # We silently return None right now. We could warn here. This object
        # will not be recoverable with client.get
        return None
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
    return {
        "_type": "CustomWeaveType",
        "weave_type": {"type": serializer.id()},
        "files": encoded_path_contents,
        "load_op": load_op_uri,
    }


def _decode_custom_obj(
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op: Callable[..., Any],
) -> Any:
    # Disables tracing so that calls to loading data itself don't get traced
    load_instance_op._tracing_enabled = False  # type: ignore
    art = MemTraceFilesArtifact(encoded_path_contents, metadata={})
    res = load_instance_op(art, "obj")
    res.art = art
    return res


def decode_custom_obj(
    weave_type: dict,
    encoded_path_contents: Mapping[str, str | bytes],
    load_instance_op_uri: str | None = None,
) -> Any:
    _type = weave_type["type"]
    found_serializer = False

    # First, try to load the object using a known serializer
    if _type in KNOWN_TYPES:
        serializer = get_serializer_by_id(_type)
        if serializer is not None:
            found_serializer = True
            load_instance_op = serializer.load

            try:
                return _decode_custom_obj(encoded_path_contents, load_instance_op)
            except Exception as e:
                pass

    # Otherwise, fall back to load_instance_op
    if not found_serializer:
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
