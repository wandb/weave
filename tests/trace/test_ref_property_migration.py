"""
Tests for the ref property migration to ensure .ref access is properly intercepted.
"""

from unittest.mock import MagicMock

import pytest

from weave.trace.context.isolated_execution import UserExecutor
from weave.trace.context.ref_property_handler import RefProperty, add_ref_property
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.ref_util import get_ref, set_ref
from weave.trace.refs import ObjectRef
from weave.trace.table import Table
from weave.trace.vals import Traceable


# Test class using the property
class ClassWithRefProperty:
    ref = RefProperty()

    def __init__(self):
        # No need to set self.ref = None
        pass


# Test class for decorator
@add_ref_property
class DecoratedTestClass:
    def __init__(self):
        pass


def test_ref_property_basic():
    """Test basic ref property functionality."""
    obj = ClassWithRefProperty()

    # Initially None
    assert obj.ref is None
    assert get_ref(obj) is None

    # Set via property
    ref = ObjectRef(entity="test", project="test", name="test", _digest="test")
    obj.ref = ref

    # Should be accessible both ways
    assert obj.ref == ref
    assert get_ref(obj) == ref

    # Clear via property
    obj.ref = None
    assert obj.ref is None
    assert get_ref(obj) is None


def test_ref_property_with_set_ref():
    """Test that set_ref works with ref property."""
    obj = ClassWithRefProperty()

    ref = ObjectRef(entity="test", project="test", name="test", _digest="test")

    # Set via set_ref
    set_ref(obj, ref)

    # Should be accessible via property
    assert obj.ref == ref
    assert get_ref(obj) == ref


def test_decorated_class():
    """Test the @add_ref_property decorator."""
    obj = DecoratedTestClass()

    # Should work the same as manual property
    assert obj.ref is None

    ref = ObjectRef(entity="test", project="test", name="test", _digest="test")
    obj.ref = ref
    assert obj.ref == ref
    assert get_ref(obj) == ref


def test_traceable_class():
    """Test that Traceable class works with ref property."""

    # Create a concrete subclass for testing
    class TestTraceable(Traceable):
        def __init__(self):
            self.mutations = None
            self.root = self
            self.parent = None
            self.server = MagicMock()
            self._is_dirty = False
            # Don't set self.ref - handled by property

    obj = TestTraceable()

    # Should work transparently
    assert obj.ref is None

    ref = ObjectRef(
        entity="test", project="test", name="test", _digest="test", _extra=()
    )
    obj.ref = ref
    assert obj.ref == ref

    # Test _mark_dirty
    obj._mark_dirty()
    assert obj._is_dirty
    assert obj.ref is None  # Should be cleared


def test_table_class():
    """Test that Table class works with ref property."""
    table = Table([{"a": 1}, {"a": 2}])

    # Initially None (no need to set in __init__)
    assert table.ref is None

    # Can set refs
    from weave.trace.refs import TableRef

    ref = TableRef(
        entity="test", project="test", _digest="test", _row_digests=["row1", "row2"]
    )
    table.ref = ref
    assert table.ref == ref


@pytest.mark.asyncio
async def test_ref_property_with_isolation():
    """Test that ref property works with context isolation."""
    # Mock server
    server = MagicMock()
    server.ensure_project_exists = MagicMock(return_value=True)
    server.obj_create = MagicMock(return_value=MagicMock(digest="test-digest"))

    executor = UserExecutor(server)

    # Shared object
    shared_obj = ClassWithRefProperty()

    async def user1_task():
        client = get_weave_client()
        assert client.entity == "user1"

        # Set ref
        ref = ObjectRef(
            entity="user1", project="project1", name="obj1", _digest="digest1"
        )
        shared_obj.ref = ref

        # Verify it's set
        assert shared_obj.ref == ref
        assert get_ref(shared_obj) == ref
        return "user1-done"

    async def user2_task():
        client = get_weave_client()
        assert client.entity == "user2"

        # Set different ref
        ref = ObjectRef(
            entity="user2", project="project2", name="obj2", _digest="digest2"
        )
        shared_obj.ref = ref

        # Verify it's set
        assert shared_obj.ref == ref
        assert get_ref(shared_obj) == ref
        return "user2-done"

    # Execute sequentially to show last-writer-wins behavior
    result1 = await executor.execute(user1_task, "user1", "project1")
    result2 = await executor.execute(user2_task, "user2", "project2")

    assert result1 == "user1-done"
    assert result2 == "user2-done"

    # Outside contexts, ref persists (backward compatibility)
    assert shared_obj.ref.entity == "user2"  # Last writer


def test_ref_property_delete():
    """Test deleting refs via property."""
    obj = ClassWithRefProperty()

    ref = ObjectRef(entity="test", project="test", name="test", _digest="test")
    obj.ref = ref
    assert obj.ref == ref

    # Delete via del
    del obj.ref
    assert obj.ref is None
    assert get_ref(obj) is None


def test_legacy_ref_migration():
    """Test that objects with existing refs still work."""

    # Simulate a class that had refs before migration
    class LegacyClass:
        def __init__(self):
            self._ref = None  # Old way

    # Add property after the fact
    LegacyClass.ref = RefProperty()

    obj = LegacyClass()

    # Should still work
    assert obj.ref is None

    ref = ObjectRef(entity="test", project="test", name="test", _digest="test")
    obj.ref = ref
    assert obj.ref == ref
