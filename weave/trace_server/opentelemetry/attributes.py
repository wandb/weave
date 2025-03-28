from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Iterable
from uuid import UUID
from openinference.semconv import trace
from openinference.semconv.trace import DocumentAttributes, SpanAttributes
from opentelemetry.proto.common.v1.common_pb2 import (AnyValue, KeyValue)

DOCUMENT_METADATA = DocumentAttributes.DOCUMENT_METADATA
LLM_PROMPT_TEMPLATE_VARIABLES = SpanAttributes.LLM_PROMPT_TEMPLATE_VARIABLES
METADATA = SpanAttributes.METADATA
TOOL_PARAMETERS = SpanAttributes.TOOL_PARAMETERS

# Attributes interpreted as JSON strings during ingestion
# Currently only maps openinference attributes
JSON_ATTRIBUTES = (
    DOCUMENT_METADATA,
    LLM_PROMPT_TEMPLATE_VARIABLES,
    METADATA,
    TOOL_PARAMETERS,
)

def to_json_serializable(value: Any) -> Any:
    """
    Transform common data types into JSON-serializable values.

    Args:
        value: Any value that needs to be converted to JSON-serializable format

    Returns:
        A JSON-serializable version of the input value

    Raises:
        ValueError: If the value type is not supported for JSON serialization
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [to_json_serializable(item) for item in value]
    elif isinstance(value, dict):
        return {str(k): to_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, Enum):
        return value.value
    elif hasattr(value, '__dataclass_fields__'):  # Handle dataclasses
        return {k: to_json_serializable(getattr(value, k)) for k in value.__dataclass_fields__}
    else:
        raise ValueError(f"Unsupported type for JSON serialization: {type(value)}")


def resolve_pb_any_value(value: AnyValue) -> Any:
    """
    Resolve the value field of an AnyValue protobuf message.

    Args:
        value: An AnyValue protobuf message

    Returns:
        The resolved value as a Python type

    Raises:
        ValueError: If the AnyValue has no value set or has an unsupported type
    """
    if value.HasField('string_value'):
        return value.string_value
    elif value.HasField('bool_value'):
        return value.bool_value
    elif value.HasField('int_value'):
        return value.int_value
    elif value.HasField('double_value'):
        return value.double_value
    elif value.HasField('array_value'):
        return [resolve_pb_any_value(v) for v in value.array_value.values]
    elif value.HasField('kvlist_value'):
        return dict(resolve_pb_key_value(kv) for kv in value.kvlist_value.values)
    elif value.HasField('bytes_value'):
        return value.bytes_value
    else:
        raise ValueError("AnyValue has no value set")

def resolve_pb_key_value(key_value: KeyValue) -> tuple[str, Any]:
    """
    Resolve a KeyValue protobuf message into a tuple of key and value.

    Args:
        key_value: A KeyValue protobuf message

    Returns:
        A tuple containing the key and resolved value

    Raises:
        ValueError: If the KeyValue has no value set or has an unsupported type
    """
    return (key_value.key, resolve_pb_any_value(key_value.value))

def transform_key_values(key_values: Iterable[KeyValue], separator: str = '.') -> dict[str, Any]:
    """
    Transform a list of KeyValue pairs into a nested dictionary structure.
    
    Args:
        key_values: An iterable of KeyValue protobuf messages
        separator: The character used to separate nested keys (default: '.')
        
    Returns:
        A nested dictionary where keys are split by the separator and digit keys
        are treated as array indices.
        
    Example:
        Input: [("llm.token_count.completion", 123)]
        Output: {"llm": {"token_count": {"completion": 123}}}
        
        Input: [
            ("retrieval.documents.0.document.content", 'A'),
            ("retrieval.documents.1.document.content", 'B')
        ]
        Output: {
            "retrieval": {
                "documents": [
                    {"document": {"content": "A"}},
                    {"document": {"content": "B"}}
                ]
            }
        }
    """
    result: dict[str, Any] = {}
    
    for key_value in key_values:
        key, value = resolve_pb_key_value(key_value)
        parts = key.split(separator)
        
        # Handle the nested structure
        current = result
        for i, part in enumerate(parts[:-1]):
            # Check if the next part is a digit (array index)
            next_part = parts[i + 1]
            if next_part.isdigit():
                # Initialize list if needed
                if part not in current:
                    current[part] = []
                # Ensure list is long enough
                while len(current[part]) <= int(next_part):
                    current[part].append({})
                current = current[part][int(next_part)]
            else:
                # Initialize dict if needed
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        # Set the final value
        final_part = parts[-1]
        if final_part.isdigit():
            # Handle case where the final part is a digit
            parent_part = parts[-2]
            if parent_part not in current:
                current[parent_part] = []
            while len(current[parent_part]) <= int(final_part):
                current[parent_part].append(None)
            current[parent_part][int(final_part)] = value
        else:
            current[final_part] = value
            
    return result
