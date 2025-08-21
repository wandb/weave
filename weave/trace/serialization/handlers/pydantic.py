"""Serialization handlers for Pydantic models."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from weave.trace.serialization.registry import SerializationContext, register


def serialize_pydantic_model(obj: BaseModel, context: SerializationContext) -> dict[str, Any]:
    """Serialize a Pydantic model instance."""
    from weave.trace.serialization.registry import serialize
    
    # Serialize each field value recursively to preserve type information
    serialized_data = {}
    new_context = context.increment_depth()
    
    # Use model_fields to get the field names (Pydantic v2) or __fields__ (v1)
    if hasattr(obj, "model_fields"):
        # Pydantic v2
        for field_name in obj.model_fields:
            field_value = getattr(obj, field_name)
            serialized_data[field_name] = serialize(field_value, new_context)
    else:
        # Pydantic v1
        for field_name in obj.__fields__:
            field_value = getattr(obj, field_name)
            serialized_data[field_name] = serialize(field_value, new_context)
    
    # Add type information for deserialization
    result = {
        "_type": "PydanticModel",
        "_class": obj.__class__.__name__,
        "_module": obj.__class__.__module__,
        "data": serialized_data
    }
    
    return result


def deserialize_pydantic_model(data: dict[str, Any], context: SerializationContext) -> BaseModel:
    """Deserialize a Pydantic model instance."""
    from weave.trace.serialization.registry import deserialize
    
    # Extract type information
    class_name = data.get("_class")
    module_name = data.get("_module")
    model_data = data.get("data", {})
    
    # Deserialize the model data
    new_context = context.increment_depth()
    deserialized_data = deserialize(model_data, new_context)
    
    # Try to import and reconstruct the model
    try:
        import importlib
        module = importlib.import_module(module_name)
        model_class = getattr(module, class_name)
        
        if not issubclass(model_class, BaseModel):
            raise ValueError(f"{model_class} is not a Pydantic BaseModel")
        
        # Create the model instance
        return model_class.model_validate(deserialized_data)
    except (ImportError, AttributeError, ValueError) as e:
        # If we can't reconstruct the exact model, return a dict
        # In production, we might want to raise or log this
        return deserialized_data


def serialize_pydantic_class(obj: Type[BaseModel], context: SerializationContext) -> dict[str, Any]:
    """Serialize a Pydantic model class (not instance)."""
    # For model classes, we might want to serialize the schema
    return {
        "_type": "PydanticModelClass",
        "_class": obj.__name__,
        "_module": obj.__module__,
        "schema": obj.model_json_schema()
    }


def deserialize_pydantic_class(data: dict[str, Any], context: SerializationContext) -> Type[BaseModel]:
    """Deserialize a Pydantic model class."""
    class_name = data.get("_class")
    module_name = data.get("_module")
    
    try:
        import importlib
        module = importlib.import_module(module_name)
        model_class = getattr(module, class_name)
        
        if not issubclass(model_class, BaseModel):
            raise ValueError(f"{model_class} is not a Pydantic BaseModel")
        
        return model_class
    except (ImportError, AttributeError, ValueError):
        # Return the schema if we can't reconstruct the class
        return data.get("schema", {})


def is_pydantic_model_instance(obj: Any) -> bool:
    """Check if an object is a Pydantic model instance."""
    return isinstance(obj, BaseModel)


def is_pydantic_model_class(obj: Any) -> bool:
    """Check if an object is a Pydantic model class."""
    try:
        return (
            isinstance(obj, type) and
            issubclass(obj, BaseModel) and
            obj is not BaseModel
        )
    except TypeError:
        # Handle cases like Iterable[SomeModel]
        return False


def handle_special_pydantic_types(obj: Any, context: SerializationContext) -> Any | None:
    """Handle special Pydantic types like SecretStr, HttpUrl, etc."""
    # Check for Pydantic special types
    if hasattr(obj, "__class__") and obj.__class__.__module__.startswith("pydantic"):
        class_name = obj.__class__.__name__
        
        # Handle SecretStr, SecretBytes
        if "Secret" in class_name:
            if context.redact_pii:
                return {"_type": f"Pydantic{class_name}", "_value": "***REDACTED***"}
            else:
                # Get the actual secret value (be careful with this!)
                if hasattr(obj, "get_secret_value"):
                    return {
                        "_type": f"Pydantic{class_name}",
                        "_value": obj.get_secret_value()
                    }
        
        # Handle HttpUrl, AnyUrl, etc.
        if "Url" in class_name:
            return {
                "_type": f"Pydantic{class_name}",
                "_value": str(obj)
            }
        
        # Handle EmailStr
        if class_name == "EmailStr":
            if context.redact_pii:
                return {"_type": "PydanticEmailStr", "_value": "***REDACTED***"}
            return {"_type": "PydanticEmailStr", "_value": str(obj)}
        
        # Handle Path types
        if "Path" in class_name:
            return {
                "_type": f"Pydantic{class_name}",
                "_value": str(obj)
            }
        
        # Handle UUID types
        if "UUID" in class_name:
            return {
                "_type": f"Pydantic{class_name}",
                "_value": str(obj)
            }
    
    return None


def serialize_pydantic_special(obj: Any, context: SerializationContext) -> Any:
    """Serialize special Pydantic types."""
    result = handle_special_pydantic_types(obj, context)
    if result is not None:
        return result
    
    # Fallback to string representation
    return {"_type": "PydanticSpecial", "_class": obj.__class__.__name__, "_value": str(obj)}


def deserialize_pydantic_special(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize special Pydantic types."""
    type_name = data.get("_type", "")
    value = data.get("_value")
    
    # For now, just return the value
    # In a full implementation, we'd reconstruct the actual Pydantic type
    return value


def is_pydantic_special_type(obj: Any) -> bool:
    """Check if an object is a special Pydantic type."""
    if not hasattr(obj, "__class__"):
        return False
    
    module = getattr(obj.__class__, "__module__", "")
    if not module.startswith("pydantic"):
        return False
    
    # Check if it's not a BaseModel (those are handled separately)
    return not isinstance(obj, BaseModel)


def register_pydantic_handlers():
    """Register all Pydantic type handlers."""
    # Pydantic model instances (high priority)
    register(
        BaseModel,
        serialize_pydantic_model,
        deserialize_pydantic_model,
        priority=80,
        check_func=is_pydantic_model_instance
    )
    
    # Pydantic model classes
    register(
        type,
        serialize_pydantic_class,
        deserialize_pydantic_class,
        priority=75,
        check_func=is_pydantic_model_class
    )
    
    # Special Pydantic types (SecretStr, HttpUrl, etc.)
    register(
        object,  # Base type, will use check_func
        serialize_pydantic_special,
        deserialize_pydantic_special,
        priority=70,
        check_func=is_pydantic_special_type
    )