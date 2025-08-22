"""Tests for the new unified serialization system."""

from collections import namedtuple
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field

from weave.trace.serialization.handlers import register_all_handlers
from weave.trace.serialization.registry import (
    SerializationContext,
    get_registry,
    serialize,
)


# Test models
class SimpleModel(BaseModel):
    """A simple Pydantic model for testing."""

    name: str
    age: int
    tags: List[str] = Field(default_factory=list)


class NestedModel(BaseModel):
    """A nested Pydantic model for testing."""

    id: int
    simple: SimpleModel
    optional: Optional[str] = None


# Test namedtuple
Point = namedtuple("Point", ["x", "y"])


class TestPrimitiveTypes:
    """Test serialization of primitive Python types."""

    def setup_method(self):
        """Setup test registry."""
        get_registry().clear()
        register_all_handlers()

    def test_serialize_primitives(self):
        """Test serialization of primitive types."""
        context = SerializationContext()

        # Test basic types
        assert serialize(42, context) == 42
        assert serialize(3.14, context) == 3.14
        assert serialize("hello", context) == "hello"
        assert serialize(True, context) is True
        assert serialize(None, context) is None

    def test_serialize_bytes(self):
        """Test serialization of bytes."""
        context = SerializationContext()

        # UTF-8 bytes
        utf8_bytes = b"hello"
        result = serialize(utf8_bytes, context)
        assert result == {"_type": "bytes", "encoding": "utf-8", "value": "hello"}

        # Binary bytes
        binary_bytes = bytes([0, 1, 2, 255])
        result = serialize(binary_bytes, context)
        assert result["_type"] == "bytes"
        assert result["encoding"] == "base64"

    def test_serialize_collections(self):
        """Test serialization of collections."""
        context = SerializationContext()

        # List
        assert serialize([1, 2, 3], context) == [1, 2, 3]
        assert serialize(["a", "b"], context) == ["a", "b"]

        # Tuple
        result = serialize((1, 2), context)
        assert result == {"_type": "tuple", "values": [1, 2]}

        # Set
        result = serialize({1, 2, 3}, context)
        assert result["_type"] == "set"
        assert set(result["values"]) == {1, 2, 3}

        # Dict
        assert serialize({"a": 1, "b": 2}, context) == {"a": 1, "b": 2}

    def test_serialize_nested_collections(self):
        """Test serialization of nested collections."""
        context = SerializationContext()

        nested = {
            "list": [1, 2, [3, 4]],
            "tuple": (5, 6),
            "dict": {"inner": {"value": 7}},
        }

        result = serialize(nested, context)
        assert result["list"] == [1, 2, [3, 4]]
        assert result["tuple"]["_type"] == "tuple"
        assert result["dict"]["inner"]["value"] == 7

    def test_serialize_namedtuple(self):
        """Test serialization of namedtuples."""
        context = SerializationContext()

        point = Point(x=10, y=20)
        result = serialize(point, context)

        assert result["_type"] == "namedtuple"
        assert result["_class"] == "Point"
        assert result["values"] == {"x": 10, "y": 20}

    def test_circular_reference_detection(self):
        """Test that circular references are detected."""
        context = SerializationContext()

        # Create circular reference
        lst = [1, 2]
        lst.append(lst)

        result = serialize(lst, context)
        assert len(result) == 3
        assert result[0] == 1
        assert result[1] == 2
        assert result[2]["_type"] == "CircularRef"

    def test_depth_limit(self):
        """Test that depth limit is enforced."""
        context = SerializationContext(max_depth=2)

        deeply_nested = {"a": {"b": {"c": {"d": 1}}}}
        result = serialize(deeply_nested, context)

        # Should serialize up to depth 2, then hit limit
        assert "a" in result
        assert "b" in result["a"]
        assert "_type" in result["a"]["b"]["c"]
        assert result["a"]["b"]["c"]["_type"] == "DepthLimitExceeded"


class TestPydanticTypes:
    """Test serialization of Pydantic models."""

    def setup_method(self):
        """Setup test registry."""
        get_registry().clear()
        register_all_handlers()

    def test_serialize_simple_model(self):
        """Test serialization of a simple Pydantic model."""
        context = SerializationContext()

        model = SimpleModel(name="Alice", age=30, tags=["python", "ml"])
        result = serialize(model, context)

        assert result["_type"] == "PydanticModel"
        assert result["_class"] == "SimpleModel"
        assert result["_module"] == "test_new_serialization"
        assert result["data"]["name"] == "Alice"
        assert result["data"]["age"] == 30
        assert result["data"]["tags"] == ["python", "ml"]

    def test_serialize_nested_model(self):
        """Test serialization of nested Pydantic models."""
        context = SerializationContext()

        simple = SimpleModel(name="Bob", age=25)
        nested = NestedModel(id=1, simple=simple, optional="test")
        result = serialize(nested, context)

        assert result["_type"] == "PydanticModel"
        assert result["_class"] == "NestedModel"
        assert result["data"]["id"] == 1
        assert result["data"]["optional"] == "test"

        # Check nested model
        simple_data = result["data"]["simple"]
        assert simple_data["_type"] == "PydanticModel"
        assert simple_data["_class"] == "SimpleModel"
        assert simple_data["data"]["name"] == "Bob"

    def test_serialize_pydantic_class(self):
        """Test serialization of a Pydantic model class (not instance)."""
        context = SerializationContext()

        result = serialize(SimpleModel, context)

        assert result["_type"] == "PydanticModelClass"
        assert result["_class"] == "SimpleModel"
        assert "schema" in result
        assert "properties" in result["schema"]

    def test_pydantic_with_collections(self):
        """Test Pydantic models containing collections."""
        context = SerializationContext()

        model = SimpleModel(
            name="Charlie", age=35, tags=["data", "science", "engineering"]
        )

        result = serialize(model, context)
        assert result["data"]["tags"] == ["data", "science", "engineering"]

    def test_fallback_for_unknown_types(self):
        """Test fallback serialization for unknown types."""
        context = SerializationContext()

        class UnknownClass:
            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return f"UnknownClass({self.value})"

        obj = UnknownClass(42)
        result = serialize(obj, context)

        # Objects with __dict__ get serialized as "Object" type
        assert result["_type"] == "Object"
        assert result["_class"] == "UnknownClass"
        assert result["data"]["value"] == 42

        # Test true fallback with an object that has no __dict__
        class NoDict:
            __slots__ = ["value"]

            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return f"NoDict({self.value})"

        obj_no_dict = NoDict(42)
        result_no_dict = serialize(obj_no_dict, context)

        assert result_no_dict["_type"] == "FallbackString"
        assert "NoDict(42)" in result_no_dict["_value"]


class TestSerializationContext:
    """Test SerializationContext functionality."""

    def test_context_depth_tracking(self):
        """Test that context properly tracks depth."""
        context = SerializationContext(max_depth=5)

        assert context.depth == 0

        new_context = context.increment_depth()
        assert new_context.depth == 1
        assert context.depth == 0  # Original unchanged

        deep_context = new_context.increment_depth().increment_depth()
        assert deep_context.depth == 3

    def test_context_seen_tracking(self):
        """Test that context tracks seen objects."""
        context = SerializationContext()

        obj_id = 12345
        assert not context.has_seen(obj_id)

        context.mark_seen(obj_id)
        assert context.has_seen(obj_id)

        # Multiple marks should be idempotent
        context.mark_seen(obj_id)
        assert context.has_seen(obj_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
