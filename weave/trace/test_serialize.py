"""Tests for the serialization system."""

import pytest
from unittest.mock import MagicMock

from weave.trace.refs import ObjectRef, TableRef
from weave.trace.serialize import to_json
from weave.trace.serialization.protocol import SerializationContext
from weave.trace.serialization.registry import REGISTRY
from weave.trace.weave_client import WeaveClient

def test_ref_serialization():
    """Test that refs are serialized correctly using the new serializers."""
    mock_client = MagicMock(spec=WeaveClient)
    
    # Test ObjectRef serialization
    obj_ref = ObjectRef("test-project", "test-table", "test-object", _digest="test-digest")
    result = to_json(obj_ref, "test-project", mock_client)
    assert result["_type"] == "object_ref"
    assert result["content"] == obj_ref.uri()
    
    # Test TableRef serialization
    table_ref = TableRef("test-project", "test-table", _digest="test-digest")
    result = to_json(table_ref, "test-project", mock_client)
    assert result["_type"] == "table_ref"
    assert result["content"] == table_ref.uri()

def test_primitive_serialization():
    """Test that primitive types are serialized correctly."""
    mock_client = MagicMock(spec=WeaveClient)
    
    # Test basic types
    assert to_json(42, "test-project", mock_client) == 42
    assert to_json(3.14, "test-project", mock_client) == 3.14
    assert to_json("hello", "test-project", mock_client) == "hello"
    assert to_json(True, "test-project", mock_client) is True
    assert to_json(None, "test-project", mock_client) is None

def test_collection_serialization():
    """Test that collections are serialized correctly."""
    mock_client = MagicMock(spec=WeaveClient)
    
    # Test list
    obj_ref = ObjectRef("test-project", "test-table", "test-object", _digest="test-digest")
    result = to_json([1, "two", obj_ref], "test-project", mock_client)
    assert result[0] == 1
    assert result[1] == "two"
    assert result[2]["_type"] == "object_ref"
    assert result[2]["content"] == obj_ref.uri()
    
    # Test dict
    result = to_json({"a": 1, "b": obj_ref}, "test-project", mock_client)
    assert result["a"] == 1
    assert result["b"]["_type"] == "object_ref"
    assert result["b"]["content"] == obj_ref.uri()

def test_dictifiable_fallback():
    """Test that objects can fall back to dictification."""
    mock_client = MagicMock(spec=WeaveClient)
    
    class DictifiableObject:
        def __init__(self):
            self.x = 42
            self.y = "hello"
            
        def to_dict(self):
            return {"x": self.x, "y": self.y}
    
    obj = DictifiableObject()
    result = to_json(obj, "test-project", mock_client, use_dictify=True)
    assert result == {"x": 42, "y": "hello"} 