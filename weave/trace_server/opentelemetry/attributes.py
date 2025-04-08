import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any, Union
from uuid import UUID

import openinference.semconv.trace as oi
import opentelemetry.semconv_ai as ot
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from weave.trace_server.trace_server_interface import LLMUsageSchema


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
    elif hasattr(value, "__dataclass_fields__"):  # Handle dataclasses
        return {
            k: to_json_serializable(getattr(value, k))
            for k in value.__dataclass_fields__
        }
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
    if value.HasField("string_value"):
        return value.string_value
    elif value.HasField("bool_value"):
        return value.bool_value
    elif value.HasField("int_value"):
        return value.int_value
    elif value.HasField("double_value"):
        return value.double_value
    elif value.HasField("array_value"):
        return [resolve_pb_any_value(v) for v in value.array_value.values]
    elif value.HasField("kvlist_value"):
        return dict(resolve_pb_key_value(kv) for kv in value.kvlist_value.values)
    elif value.HasField("bytes_value"):
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


def _get_value_from_nested_dict(d: dict[str, Any], key: str) -> Any:
    """Get a value from a nested dictionary using a dot-separated key."""
    if "." not in key:
        return d.get(key)

    parts = key.split(".")
    current = d
    for part in parts:
        if part not in current or not isinstance(current, dict):
            return None
        current = current[part]
    return current


def _set_value_in_nested_dict(d: dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dictionary using a dot-separated key."""
    if "." not in key:
        d[key] = value
        return

    parts = key.split(".")
    current = d
    for _, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def convert_numeric_keys_to_list(
    obj: dict[str, Any],
) -> Union[dict[str, Any], list[Any]]:
    """
    Convert dictionaries with numeric-only keys to lists.

    If all keys in a dictionary are numeric strings (0, 1, 2, ...),
    convert it to a list. Recursively processes nested dictionaries.
    """
    # Process all nested dictionaries first
    for key, value in obj.items():
        if isinstance(value, dict):
            obj[key] = convert_numeric_keys_to_list(value)

    # Check if all keys are numeric strings and contiguous starting from 0
    try:
        keys = sorted(int(k) for k in obj.keys())
        if keys == list(range(len(keys))) and all(
            isinstance(k, str) and k.isdigit() for k in obj.keys()
        ):
            # Convert to list, preserving order
            return [obj[str(i)] for i in range(len(keys))]
    except (ValueError, TypeError):
        # Not all keys are numeric
        pass

    return obj


def expand_attributes(
    kv: Iterable[tuple[str, str]], json_attributes: list[str] = []
) -> dict[str, Any]:
    """
    Expand a flattened JSON attributes file into a nested Python dictionary.

    Args:
        file_path: Path to the JSON file with flattened attributes
        json_attributes: list of attributes to parse as JSON strings

    Returns:
        A nested Python dictionary
    """
    # Read the JSON file

    # Create the result dictionary
    result_dict: dict[str, Any] = {}

    # Process each key-value pair
    for flat_key, value in kv:
        # Check if the value should be parsed as JSON
        should_parse_as_json = any(
            flat_key.endswith(attr) or flat_key == attr for attr in json_attributes
        )

        if should_parse_as_json and isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # If JSON parsing fails, keep the original value
                pass

        # Add the nested key to the result
        _set_value_in_nested_dict(result_dict, flat_key, value)

    # Convert dictionaries with numeric keys to lists
    return result_dict


def flatten_attributes(
    data: dict[str, Any], json_attributes: list[str] = []
) -> dict[str, Any]:
    """
    Flatten a nested Python dictionary into a flat dictionary with dot-separated keys.

    Args:
        data: Nested Python dictionary to flatten
        json_attributes: list of attributes to stringify as JSON

    Returns:
        A flattened dictionary with dot-separated keys
    """
    result: dict[str, Any] = {}

    def _flatten(obj: Union[dict[str, Any], list[Any]], prefix: str = "") -> None:
        # Check if the entire object should be stringified as JSON
        should_stringify_entire_obj = any(
            prefix.rstrip(".") == attr for attr in json_attributes
        )

        if should_stringify_entire_obj:
            result[prefix.rstrip(".")] = json.dumps(obj)
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}{key}" if prefix else key

                # Check if this exact key's value should be stringified as JSON
                should_stringify_as_json = any(
                    new_key == attr for attr in json_attributes
                )

                if (
                    isinstance(value, dict) or isinstance(value, list)
                ) and not should_stringify_as_json:
                    # Recursively flatten nested dictionaries or lists
                    _flatten(value, f"{new_key}.")
                else:
                    # If the value matches a JSON attribute, stringify it
                    if should_stringify_as_json and not isinstance(value, str):
                        value = json.dumps(value)
                    result[new_key] = value
        elif isinstance(obj, list):
            # Handle lists by using numeric indices as keys
            for i, item in enumerate(obj):
                new_key = f"{prefix}{i}"

                # Check if this exact key's value should be stringified as JSON
                should_stringify_as_json = any(
                    new_key == attr for attr in json_attributes
                )

                if (
                    isinstance(item, dict) or isinstance(item, list)
                ) and not should_stringify_as_json:
                    # Recursively flatten nested dictionaries or lists
                    _flatten(item, f"{new_key}.")
                else:
                    # If the item matches a JSON attribute, stringify it
                    if should_stringify_as_json and not isinstance(item, str):
                        item = json.dumps(item)
                    result[new_key] = item

    _flatten(data)
    return result


def get_attribute(data: dict[str, Any], key: str) -> Any:
    """
    Get the value of a nested attribute from either a nested or flattened dictionary.

    Args:
        data: dictionary to get value from
        key: Dot-separated key to get

    Returns:
        The value at the specified key or None if not found
    """
    # Check if it's a flat dictionary
    if key in data:
        return data[key]

    # Try to get from nested structure
    return _get_value_from_nested_dict(data, key)


def pop_attribute(data: dict[str, Any], key: str) -> Any:
    """
    Pop the value of a nested attribute from either a nested or flattened dictionary.

    Args:
        data: dictionary to get value from
        key: Dot-separated key to get

    Returns:
        The value at the specified key or None if not found
    """
    # Check if it's a flat dictionary
    if key in data:
        return data.pop(key)

    # Try to get from nested structure
    return _get_value_from_nested_dict(data, key)


def unflatten_key_values(
    key_values: Iterable[KeyValue],
) -> dict[str, Any]:
    """
    Transform a list of KeyValue pairs into a nested dictionary structure.

    Args:
        key_values: An iterable of KeyValue protobuf messages
        separator: The character used to separate nested keys (default: '.')

    Returns:
        A nested dictionary where keys are split by the separator

    Example:
        Input: [("llm.token_count.completion", 123)]
        Output: {"llm": {"token_count": {"completion": 123}}}

        Input: [
            ("retrieval.documents.0.document.content", 'A'),
            ("retrieval.documents.1.document.content", 'B')
        ]
        Output: {
            "retrieval": {
                "documents": {
                    "0": {"document": {"content": "A"}},
                    "1": {"document": {"content": "B"}}
                }
            }
        }
    """
    iterator = ((kv.key, resolve_pb_any_value(kv.value)) for kv in key_values)
    return expand_attributes(iterator, json_attributes=[])


class ConventionType(Enum):
    OPENINFERENCE = "openinference"
    OPENTELEMETRY = "gen_ai"
    CUSTOM = "custom"


class AbstractAttributes(ABC):
    _attributes: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def __getitem__(self, key: str) -> Any: ...

    @abstractmethod
    def __setitem__(self, key: str, value: Any) -> None: ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def get_attribute_value(self, key: str) -> Any: ...

    @abstractmethod
    def get_weave_inputs(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_weave_outputs(self) -> Any: ...

    @abstractmethod
    def get_weave_usage(self) -> LLMUsageSchema: ...


class Attributes(AbstractAttributes):
    _attributes: dict[str, Any] = field(default_factory=dict)

    def __init__(self, attributes: dict[str, Any] = {}) -> None:
        self._attributes = attributes

    def __getitem__(self, key: str) -> Any:
        return self._attributes.__getitem__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        return self._attributes.__setitem__(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._attributes.get(key, default)

    def get_attribute_value(self, key: str) -> Any:
        return get_attribute(self._attributes, key)

    def get_weave_usage(self) -> LLMUsageSchema:
        raise NotImplementedError("get_weave_usage is not implemented")

    def get_weave_inputs(self) -> Any:
        raise NotImplementedError("get_weave_inputs is not implemented")

    def get_weave_outputs(self) -> Any:
        raise NotImplementedError("get_weave_outputs is not implemented")

    def get_weave_attributes(self) -> Any:
        raise NotImplementedError("get_weave_attributes is not implemented")


# If we don't have any conventions to follow, just dump everything to attributes
# Later we may add support for user defined conventions through headers
class GenericAttributes(Attributes):
    def get_weave_usage(self) -> LLMUsageSchema:
        return {}

    def get_weave_inputs(self) -> Any:
        return {}

    def get_weave_outputs(self) -> Any:
        return {}

    def get_weave_attributes(self) -> Any:
        return self._attributes


class OpenInferenceAttributes(Attributes):
    def get_weave_attributes(self) -> dict[str, Any]:
        system = self.get_attribute_value(oi.SpanAttributes.LLM_SYSTEM)
        provider = self.get_attribute_value(oi.SpanAttributes.LLM_PROVIDER)
        invocation_parameters = self.get_attribute_value(
            oi.SpanAttributes.LLM_INVOCATION_PARAMETERS
        )
        kind = self.get_attribute_value(oi.SpanAttributes.OPENINFERENCE_SPAN_KIND)
        model = self.get_attribute_value(oi.SpanAttributes.LLM_MODEL_NAME)
        attributes = {
            "system": str(system) if system else None,
            "provider": str(provider) if provider else None,
            "kind": str(kind) if kind else None,
            "model": str(model) if model else None,
        }
        if invocation_parameters:
            try:
                js = json.loads(invocation_parameters)
                for k, v in js.items():
                    attributes[k] = str(v)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON string: {invocation_parameters}")
        return attributes

    def get_weave_outputs(self) -> Any:
        outputs: dict[str, Any] = (
            self.get_attribute_value(oi.SpanAttributes.LLM_OUTPUT_MESSAGES) or {}
        )
        result = {}
        for k, v in outputs.items():
            if k.isdigit() and isinstance(v, dict):
                for key in v.keys():
                    result[key + f"_{k}"] = v[key]
        return result

    def get_weave_inputs(self) -> Any:
        inputs: dict[str, Any] = (
            self.get_attribute_value(oi.SpanAttributes.LLM_INPUT_MESSAGES) or {}
        )
        result = {}
        for k, v in inputs.items():
            if k.isdigit() and isinstance(v, dict):
                for key in v.keys():
                    result[key + f"_{k}"] = v[key]
        return result

    def get_weave_usage(self) -> LLMUsageSchema:
        prompt_tokens = self.get_attribute_value(
            oi.SpanAttributes.LLM_TOKEN_COUNT_PROMPT
        )
        completion_tokens = self.get_attribute_value(
            oi.SpanAttributes.LLM_TOKEN_COUNT_COMPLETION
        )
        total_tokens = self.get_attribute_value(oi.SpanAttributes.LLM_TOKEN_COUNT_TOTAL)
        return LLMUsageSchema(
            prompt_tokens=int(prompt_tokens) if prompt_tokens else None,
            completion_tokens=int(completion_tokens) if completion_tokens else None,
            total_tokens=int(total_tokens) if total_tokens else None,
        )


class OpenTelemetryAttributes(Attributes):
    def get_weave_attributes(self) -> dict[str, Any]:
        max_tokens = self.get_attribute_value(ot.SpanAttributes.LLM_REQUEST_MAX_TOKENS)
        system = self.get_attribute_value(ot.SpanAttributes.LLM_SYSTEM)
        kind = self.get_attribute_value(ot.SpanAttributes.TRACELOOP_SPAN_KIND)
        model = self.get_attribute_value(ot.SpanAttributes.LLM_RESPONSE_MODEL)

        attributes = {
            "system": str(system) if system else None,
            "max_tokens": int(max_tokens) if max_tokens else None,
            "kind": str(kind) if kind else None,
            "model": str(model) if model else None,
        }
        return attributes

    def get_weave_outputs(self) -> Any:
        outputs: dict[str, Any] | None = self.get_attribute_value(
            ot.SpanAttributes.LLM_COMPLETIONS
        )
        if isinstance(outputs, dict) and outputs.keys():
            return convert_numeric_keys_to_list(outputs)
        return outputs or {}

    def get_weave_inputs(self) -> Any:
        inputs: dict[str, Any] | None = self.get_attribute_value(
            ot.SpanAttributes.LLM_PROMPTS
        )
        if isinstance(inputs, dict) and inputs.keys():
            return convert_numeric_keys_to_list(inputs)
        return inputs or {}

    def get_weave_usage(self) -> LLMUsageSchema:
        prompt_tokens = self.get_attribute_value(
            ot.SpanAttributes.LLM_USAGE_PROMPT_TOKENS
        )
        completion_tokens = self.get_attribute_value(
            ot.SpanAttributes.LLM_USAGE_COMPLETION_TOKENS
        )
        total_tokens = self.get_attribute_value(
            ot.SpanAttributes.LLM_USAGE_TOTAL_TOKENS
        )
        return LLMUsageSchema(
            prompt_tokens=int(prompt_tokens) if prompt_tokens else None,
            completion_tokens=int(completion_tokens) if completion_tokens else None,
            total_tokens=int(total_tokens) if total_tokens else None,
        )


class AttributesFactory:
    def from_proto(self, key_values: Iterable[KeyValue]) -> "Attributes":
        expanded = unflatten_key_values(key_values)
        if get_attribute(expanded, ConventionType.OPENINFERENCE.value):
            return OpenInferenceAttributes(expanded)
        elif get_attribute(expanded, ConventionType.OPENTELEMETRY.value):
            return OpenTelemetryAttributes(expanded)
        return GenericAttributes(expanded)
