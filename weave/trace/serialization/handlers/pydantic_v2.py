"""Serialization handlers for Pydantic models using the new registration system."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from weave.trace.serialization.handlers.handler_registry import handler
from weave.trace.serialization.registry import SerializationContext


def is_pydantic_model_instance(obj: Any) -> bool:
    """Check if object is a Pydantic model instance."""
    return isinstance(obj, BaseModel)


def is_pydantic_model_class(obj: Any) -> bool:
    """Check if object is a Pydantic model class."""
    try:
        return (
            isinstance(obj, type) and
            issubclass(obj, BaseModel) and
            obj is not BaseModel
        )
    except TypeError:
        # Handle cases like Iterable[SomeModel]
        return False


def is_pydantic_special_type(obj: Any) -> bool:
    """Check if object is a special Pydantic type (not a BaseModel)."""
    if not hasattr(obj, "__class__"):
        return False
    
    module = getattr(obj.__class__, "__module__", "")
    if not module.startswith("pydantic"):
        return False
    
    # Check if it's not a BaseModel (those are handled separately)
    return not isinstance(obj, BaseModel)


@handler(is_pydantic_model_instance, priority=80, name="PydanticModel")
class PydanticModelHandler:
    """Handler for Pydantic model instances."""
    
    @staticmethod
    def serialize(obj: BaseModel, context: SerializationContext) -> dict[str, Any]:
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
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> BaseModel:
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
            # If we can't reconstruct the exact model, return the data dict
            # In production, we might want to raise or log this
            return deserialized_data


@handler(is_pydantic_model_class, priority=75, name="PydanticModelClass")
class PydanticModelClassHandler:
    """Handler for Pydantic model classes (not instances)."""
    
    @staticmethod
    def serialize(obj: Type[BaseModel], context: SerializationContext) -> dict[str, Any]:
        """Serialize a Pydantic model class."""
        # For model classes, we serialize the schema
        return {
            "_type": "PydanticModelClass",
            "_class": obj.__name__,
            "_module": obj.__module__,
            "schema": obj.model_json_schema()
        }
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> Type[BaseModel]:
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


@handler(is_pydantic_special_type, priority=70, name="PydanticSpecialType")
class PydanticSpecialTypeHandler:
    """Handler for special Pydantic types (SecretStr, HttpUrl, etc.)."""
    
    @staticmethod
    def serialize(obj: Any, context: SerializationContext) -> dict[str, Any]:
        """Serialize special Pydantic types."""
        class_name = obj.__class__.__name__
        result = {
            "_type": f"Pydantic{class_name}",
            "_class": class_name,
            "_module": obj.__class__.__module__,
        }
        
        # Handle different special types
        if "Secret" in class_name:
            if context.redact_pii:
                result["_value"] = "***REDACTED***"
            elif hasattr(obj, "get_secret_value"):
                result["_value"] = obj.get_secret_value()
            else:
                result["_value"] = str(obj)
        elif "Url" in class_name or "Path" in class_name or "UUID" in class_name:
            result["_value"] = str(obj)
        elif class_name == "EmailStr":
            if context.redact_pii:
                result["_value"] = "***REDACTED***"
            else:
                result["_value"] = str(obj)
        else:
            result["_value"] = str(obj)
        
        return result
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> Any:
        """Deserialize special Pydantic types."""
        # For now, just return the value
        # In a full implementation, we'd reconstruct the actual Pydantic type
        return data.get("_value")


def register_pydantic_handlers():
    """Register all Pydantic type handlers."""
    # The decorator-based handlers auto-register via handler_registry
    from weave.trace.serialization.handlers.handler_registry import register_pending_handlers
    register_pending_handlers()