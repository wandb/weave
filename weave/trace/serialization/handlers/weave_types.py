"""Serialization handlers for Weave-specific types."""

from __future__ import annotations

from typing import Any

from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace.serialization import custom_objs
from weave.trace.serialization.registry import SerializationContext, register
from weave.trace_server.trace_server_interface_util import bytes_digest


def serialize_table_ref(obj: TableRef, context: SerializationContext) -> str:
    """Serialize a TableRef to its URI."""
    return obj.uri()


def deserialize_table_ref(data: str, context: SerializationContext) -> TableRef:
    """Deserialize a TableRef from its URI."""
    ref = parse_uri(data)
    if not isinstance(ref, TableRef):
        raise ValueError(f"Expected TableRef, got {type(ref)}")
    return ref


def serialize_object_ref(obj: ObjectRef, context: SerializationContext) -> str:
    """Serialize an ObjectRef to its URI."""
    return obj.uri()


def deserialize_object_ref(data: str, context: SerializationContext) -> ObjectRef:
    """Deserialize an ObjectRef from its URI."""
    ref = parse_uri(data)
    if not isinstance(ref, ObjectRef):
        raise ValueError(f"Expected ObjectRef, got {type(ref)}")
    return ref


def serialize_object_record(obj: ObjectRecord, context: SerializationContext) -> dict[str, Any]:
    """Serialize an ObjectRecord."""
    from weave.trace.serialization.registry import serialize
    
    res = {"_type": obj._class_name}
    new_context = context.increment_depth()
    
    for k, v in obj.__dict__.items():
        if k == "ref":
            # Refs are pointers to remote objects and should not be part of
            # the serialized payload
            if v is not None:
                import logging
                logging.warning(f"Unexpected ref in object record: {obj}")
            continue
        res[k] = serialize(v, new_context)
    
    return res


def deserialize_object_record(data: dict[str, Any], context: SerializationContext) -> ObjectRecord:
    """Deserialize an ObjectRecord."""
    from weave.trace.serialization.registry import deserialize
    
    new_context = context.increment_depth()
    deserialized_data = {
        k: deserialize(v, new_context) 
        for k, v in data.items() 
        if k != "_type"
    }
    return ObjectRecord(deserialized_data)


def serialize_table(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a Table object."""
    from weave.trace.serialization.registry import serialize
    from weave.trace.table import Table
    
    if not isinstance(obj, Table):
        raise TypeError(f"Expected Table, got {type(obj)}")
    
    new_context = context.increment_depth()
    
    result = {
        "_type": "Table",
        "rows": serialize(obj.rows, new_context)
    }
    
    # Include ref if present
    if hasattr(obj, "ref") and obj.ref is not None:
        result["ref"] = serialize(obj.ref, new_context)
    
    return result


def deserialize_table(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a Table object."""
    from weave.trace.serialization.registry import deserialize
    from weave.trace.table import Table
    
    new_context = context.increment_depth()
    rows = deserialize(data.get("rows", []), new_context)
    
    table = Table(rows)
    
    # Restore ref if present
    if "ref" in data:
        table.ref = deserialize(data["ref"], new_context)
    
    return table


def serialize_weave_table(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a WeaveTable object (from vals module)."""
    from weave.trace.serialization.registry import serialize
    
    # Get the table data
    if hasattr(obj, "rows"):
        rows = obj.rows
    elif hasattr(obj, "_rows"):
        rows = obj._rows
    else:
        rows = []
    
    new_context = context.increment_depth()
    
    result = {
        "_type": "WeaveTable", 
        "rows": serialize(rows, new_context)
    }
    
    return result


def serialize_dataset(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a Dataset object."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    
    result = {
        "_type": "Dataset",
        "_class": obj.__class__.__name__,
        "_module": obj.__class__.__module__,
    }
    
    # Serialize all fields
    for field_name in obj.__class__.__fields__:
        field_value = getattr(obj, field_name)
        result[field_name] = serialize(field_value, new_context)
    
    return result


def serialize_weave_scorer_result(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a WeaveScorerResult."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    model_data = obj.model_dump()
    
    return {
        "_type": "WeaveScorerResult",
        "data": serialize(model_data, new_context)
    }


def serialize_custom_weave_obj(obj: Any, context: SerializationContext) -> dict[str, Any] | None:
    """Serialize custom Weave objects using the existing custom_objs system."""
    encoded = custom_objs.encode_custom_obj(obj)
    
    if encoded is None:
        return None
    
    # Handle inline custom objects
    if "val" in encoded:
        return encoded
    
    # Handle file-based custom objects
    if "files" in encoded and context.client:
        file_digests = {}
        for name, val in encoded["files"].items():
            # Send file creation request
            from weave.trace_server.trace_server_interface import FileCreateReq
            
            context.client._send_file_create(
                FileCreateReq(project_id=context.project_id, name=name, content=val)
            )
            
            # Calculate digest
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
        
        if load_op_uri := encoded.get("load_op"):
            result["load_op"] = load_op_uri
        
        return result
    
    return encoded


def is_table(obj: Any) -> bool:
    """Check if object is a Table."""
    from weave.trace.table import Table
    return isinstance(obj, Table)


def is_weave_table(obj: Any) -> bool:
    """Check if object is a WeaveTable."""
    from weave.trace.vals import WeaveTable
    return isinstance(obj, WeaveTable)


def is_dataset(obj: Any) -> bool:
    """Check if object is a Dataset."""
    from weave.dataset.dataset import Dataset
    return isinstance(obj, Dataset)


def is_weave_scorer_result(obj: Any) -> bool:
    """Check if object is a WeaveScorerResult."""
    try:
        from weave.flow.scorer import WeaveScorerResult
        return isinstance(obj, WeaveScorerResult)
    except ImportError:
        return False


def register_weave_handlers():
    """Register all Weave-specific type handlers."""
    # Import types
    from weave.trace.refs import ObjectRef, TableRef
    from weave.trace.object_record import ObjectRecord
    
    # References (high priority)
    register(TableRef, serialize_table_ref, deserialize_table_ref, priority=90)
    register(ObjectRef, serialize_object_ref, deserialize_object_ref, priority=90)
    
    # ObjectRecord
    register(ObjectRecord, serialize_object_record, deserialize_object_record, priority=85)
    
    # Tables
    register(
        object,  # Base type, use check function
        serialize_table,
        deserialize_table,
        priority=80,
        check_func=is_table
    )
    
    register(
        object,
        serialize_weave_table,
        lambda data, ctx: data,  # Placeholder deserializer
        priority=80,
        check_func=is_weave_table
    )
    
    # Dataset
    register(
        object,
        serialize_dataset,
        lambda data, ctx: data,  # Placeholder deserializer
        priority=75,
        check_func=is_dataset
    )
    
    # WeaveScorerResult
    register(
        object,
        serialize_weave_scorer_result,
        lambda data, ctx: data,  # Placeholder deserializer
        priority=75,
        check_func=is_weave_scorer_result
    )
    
    # Custom Weave objects (lower priority, as fallback)
    # This will handle ops, images, etc. that use the custom_objs system
    register(
        object,
        serialize_custom_weave_obj,
        lambda data, ctx: custom_objs.decode_custom_inline_obj(data) if "_type" in data and data["_type"] == "CustomWeaveType" else data,
        priority=10,
        check_func=lambda obj: custom_objs.get_serializer_for_obj(obj) is not None
    )