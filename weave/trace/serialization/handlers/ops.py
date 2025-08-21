"""Serialization handler for Weave Ops."""

from __future__ import annotations

from typing import Any

from weave.trace.op import Op, is_op
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.op_type import save_instance, load_instance
from weave.trace.serialization.registry import SerializationContext, register


def serialize_op(obj: Op, context: SerializationContext) -> dict[str, Any]:
    """Serialize an Op using the existing op_type serialization."""
    # Create an artifact for file-based serialization
    artifact = MemTraceFilesArtifact()
    save_instance(obj, artifact, "op")
    
    # Get the encoded data
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "Op"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_op(data: dict[str, Any], context: SerializationContext) -> Op | None:
    """Deserialize an Op."""
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "Op":
        return None
    
    # Reconstruct the artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Use the existing load_instance function
    return load_instance(artifact, "op")


def register_op_handler():
    """Register the Op serialization handler."""
    register(
        Op,
        serialize_op,
        deserialize_op,
        priority=85,
        check_func=is_op
    )