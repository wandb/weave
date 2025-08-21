"""Updated serialization module using the new unified registry.

This module provides the main serialization functions that integrate with
the new registry system while maintaining backward compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace.serialization import custom_objs
from weave.trace.serialization.registry import (
    SerializationContext,
    get_registry,
    serialize as registry_serialize,
)
from weave.trace.serialization.handlers import register_all_handlers
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.trace_server.trace_server_interface_util import bytes_digest

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

logger = logging.getLogger(__name__)

# Initialize the registry with all built-in handlers
_initialized = False


def _ensure_initialized():
    """Ensure the registry is initialized with handlers."""
    global _initialized
    if not _initialized:
        register_all_handlers()
        _register_weave_types()
        _initialized = True


def _register_weave_types():
    """Register Weave-specific type handlers."""
    from weave.trace.serialization.handlers.weave_types import register_weave_handlers
    register_weave_handlers()


def to_json(
    obj: Any, 
    project_id: str, 
    client: WeaveClient, 
    use_dictify: bool = False
) -> Any:
    """Serialize an object to JSON-compatible format using the new registry.
    
    This function maintains backward compatibility while using the new
    unified serialization registry internally.
    
    Args:
        obj: The object to serialize
        project_id: The project ID for the client
        client: The WeaveClient instance
        use_dictify: Whether to use dictify for unknown objects
        
    Returns:
        A JSON-compatible representation of the object
    """
    _ensure_initialized()
    
    # Create serialization context
    context = SerializationContext(
        project_id=project_id,
        client=client,
        use_refs=True,
        file_storage=True,
    )
    
    # Use the registry to serialize
    return registry_serialize(obj, context)


def from_json(obj: Any, project_id: str, server: TraceServerInterface) -> Any:
    """Deserialize an object from JSON format.
    
    Args:
        obj: The JSON data to deserialize
        project_id: The project ID
        server: The trace server interface
        
    Returns:
        The deserialized object
    """
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
        return parse_uri(obj)

    return obj


def _is_inline_custom_obj(encoded: dict) -> bool:
    """Check if a custom object is inline or file-backed."""
    return "val" in encoded


def _load_custom_obj_files(
    project_id: str, server: TraceServerInterface, file_digests: dict
) -> dict[str, bytes]:
    """Load custom object files from the server."""
    loaded_files: dict[str, bytes] = {}
    for name, digest in file_digests.items():
        file_response = server.file_content_read(
            FileContentReadReq(project_id=project_id, digest=digest)
        )
        loaded_files[name] = file_response.content
    return loaded_files


# Re-export some utilities for compatibility
from weave.trace.serialization.serialize import (
    fallback_encode,
    dictify,
    stringify,
    is_primitive,
    has_custom_repr,
    isinstance_namedtuple,
    ALWAYS_STRINGIFY,
    DEFAULT_MAX_DICTIFY_DEPTH,
    MAX_STR_LEN,
)