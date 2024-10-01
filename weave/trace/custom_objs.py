from typing import Any, Dict, Mapping, Optional, Union

from weave.trace import op_type  # noqa: F401, Must import this to register op save/load
from weave.trace.client_context.weave_client import require_weave_client
from weave.trace.mem_artifact import MemTraceFilesArtifact
from weave.trace.op import Op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.serializer import get_serializer_by_id, get_serializer_for_obj


def encode_custom_obj(obj: Any) -> Optional[dict]:
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


def decode_custom_obj(
    weave_type: Dict,
    encoded_path_contents: Mapping[str, Union[str, bytes]],
    load_instance_op_uri: Optional[str],
) -> Any:
    load_instance_op = None
    if load_instance_op_uri is not None:
        ref = parse_uri(load_instance_op_uri)
        if not isinstance(ref, ObjectRef):
            raise ValueError(f"Expected ObjectRef, got {load_instance_op_uri}")
        wc = require_weave_client()
        load_instance_op = wc.get(ref)
        if load_instance_op is None:
            raise ValueError(
                f"Failed to load op needed to decode object of type {weave_type}. See logs above for more information."
            )

    if load_instance_op is None:
        serializer = get_serializer_by_id(weave_type["type"])
        if serializer is None:
            raise ValueError(f"No serializer found for {weave_type}")
        load_instance_op = serializer.load

    # Disables tracing so that calls to loading data itself don't get traced
    load_instance_op._tracing_enabled = False  # type: ignore

    art = MemTraceFilesArtifact(
        encoded_path_contents,
        metadata={},
    )
    res = load_instance_op(art, "obj")
    res.art = art
    return res
