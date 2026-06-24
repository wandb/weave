"""Tests for Op V2 API endpoints.

Tests verify that the Op V2 API correctly creates, reads, lists, and deletes op objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_op_create_basic(trace_server):
    """Test creating a basic op object."""
    project_id = f"{TEST_ENTITY}/test_op_create_basic"

    # Create an op
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="my_function",
        description=None,
        source_code="def my_function(x: int) -> int:\n    return x * 2",
    )
    create_res = trace_server.op_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "my_function"
    assert create_res.version_index == 0


def test_op_create_without_source_code(trace_server):
    """Test creating an op without providing source code (uses placeholder)."""
    project_id = f"{TEST_ENTITY}/test_op_create_no_source"

    # Create an op without source code
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="my_op_no_source",
        description=None,
        source_code=None,
    )
    create_res = trace_server.op_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "my_op_no_source"
    assert create_res.version_index == 0


def test_op_read_basic(trace_server):
    """Test reading a specific op object."""
    project_id = f"{TEST_ENTITY}/test_op_read_basic"

    # Create an op
    source_code = "def read_test(x: int) -> int:\n    return x + 1"
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="read_test",
        description=None,
        source_code=source_code,
    )
    create_res = trace_server.op_create(create_req)

    # Read the op back
    read_req = tsi.OpReadReq(
        project_id=project_id,
        object_id="read_test",
        digest=create_res.digest,
    )
    read_res = trace_server.op_read(read_req)

    assert read_res.object_id == "read_test"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.code == source_code
    assert read_res.created_at is not None


def test_op_read_not_found(trace_server):
    """Test reading a non-existent op raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_op_read_not_found"

    read_req = tsi.OpReadReq(
        project_id=project_id,
        object_id="nonexistent_op",
        digest="fake_digest_1234567890",
    )

    with pytest.raises(NotFoundError):
        trace_server.op_read(read_req)


def test_op_list_basic(trace_server):
    """Test listing all ops in a project."""
    project_id = f"{TEST_ENTITY}/test_op_list_basic"

    # Create multiple ops
    op_names = ["op_a", "op_b", "op_c"]
    for name in op_names:
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name=name,
            description=None,
            source_code=f"def {name}():\n    pass",
        )
        trace_server.op_create(create_req)

    # List all ops
    list_req = tsi.OpListReq(project_id=project_id)
    ops = list(trace_server.op_list(list_req))

    assert len(ops) == 3
    op_names_returned = {op.object_id for op in ops}
    assert op_names_returned == {"op_a", "op_b", "op_c"}

    # Verify all ops have code loaded
    for op in ops:
        assert op.code
        assert "def " in op.code
        assert op.created_at is not None


def test_op_list_with_limit(trace_server):
    """Test listing ops with a limit."""
    project_id = f"{TEST_ENTITY}/test_op_list_limit"

    # Create multiple ops
    for i in range(5):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name=f"op_{i}",
            description=None,
            source_code=f"def op_{i}():\n    pass",
        )
        trace_server.op_create(create_req)

    # List with a limit
    list_req = tsi.OpListReq(project_id=project_id, limit=3)
    ops = list(trace_server.op_list(list_req))

    assert len(ops) == 3


def test_op_list_with_offset(trace_server):
    """Test listing ops with an offset."""
    project_id = f"{TEST_ENTITY}/test_op_list_offset"

    # Create multiple ops
    for i in range(5):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name=f"op_{i}",
            description=None,
            source_code=f"def op_{i}():\n    pass",
        )
        trace_server.op_create(create_req)

    # List with an offset
    list_req = tsi.OpListReq(project_id=project_id, offset=2)
    ops = list(trace_server.op_list(list_req))

    assert len(ops) == 3


def test_op_list_with_limit_and_offset(trace_server):
    """Test listing ops with both limit and offset for pagination."""
    project_id = f"{TEST_ENTITY}/test_op_list_pagination"

    # Create multiple ops
    for i in range(10):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name=f"op_{i}",
            description=None,
            source_code=f"def op_{i}():\n    pass",
        )
        trace_server.op_create(create_req)

    # First page
    list_req1 = tsi.OpListReq(project_id=project_id, limit=3, offset=0)
    ops1 = list(trace_server.op_list(list_req1))
    assert len(ops1) == 3

    # Second page
    list_req2 = tsi.OpListReq(project_id=project_id, limit=3, offset=3)
    ops2 = list(trace_server.op_list(list_req2))
    assert len(ops2) == 3

    # Verify different ops on different pages
    ops1_ids = {op.object_id for op in ops1}
    ops2_ids = {op.object_id for op in ops2}
    assert len(ops1_ids & ops2_ids) == 0  # No overlap


def test_op_list_empty_project(trace_server):
    """Test listing ops in a project with no ops."""
    project_id = f"{TEST_ENTITY}/test_op_list_empty"

    list_req = tsi.OpListReq(project_id=project_id)
    ops = list(trace_server.op_list(list_req))

    assert len(ops) == 0


def test_op_delete_single_version(trace_server):
    """Test deleting a single version of an op."""
    project_id = f"{TEST_ENTITY}/test_op_delete_single"

    # Create an op
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="delete_test",
        description=None,
        source_code="def delete_test():\n    pass",
    )
    create_res = trace_server.op_create(create_req)

    # Delete the specific version
    delete_req = tsi.OpDeleteReq(
        project_id=project_id,
        object_id="delete_test",
        digests=[create_res.digest],
    )
    delete_res = trace_server.op_delete(delete_req)

    assert delete_res.num_deleted == 1

    # Verify the op is deleted (should raise ObjectDeletedError)
    read_req = tsi.OpReadReq(
        project_id=project_id,
        object_id="delete_test",
        digest=create_res.digest,
    )
    with pytest.raises(ObjectDeletedError):
        trace_server.op_read(read_req)


def test_op_delete_all_versions(trace_server):
    """Test deleting all versions of an op (no digests specified)."""
    project_id = f"{TEST_ENTITY}/test_op_delete_all"

    # Create multiple versions of the same op
    digests = []
    for i in range(3):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name="versioned_op",
            description=None,
            source_code=f"def versioned_op():\n    return {i}",
        )
        create_res = trace_server.op_create(create_req)
        digests.append(create_res.digest)

    # Delete all versions (no digests specified)
    delete_req = tsi.OpDeleteReq(
        project_id=project_id,
        object_id="versioned_op",
        digests=None,
    )
    delete_res = trace_server.op_delete(delete_req)

    assert delete_res.num_deleted == 3


def test_op_delete_multiple_versions(trace_server):
    """Test deleting multiple specific versions of an op."""
    project_id = f"{TEST_ENTITY}/test_op_delete_multiple"

    # Create multiple versions
    digests = []
    for i in range(4):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name="multi_version_op",
            description=None,
            source_code=f"def multi_version_op():\n    return {i}",
        )
        create_res = trace_server.op_create(create_req)
        digests.append(create_res.digest)

    # Delete the first two versions
    delete_req = tsi.OpDeleteReq(
        project_id=project_id,
        object_id="multi_version_op",
        digests=digests[:2],
    )
    delete_res = trace_server.op_delete(delete_req)

    assert delete_res.num_deleted == 2

    # Verify the first two are deleted
    for digest in digests[:2]:
        read_req = tsi.OpReadReq(
            project_id=project_id,
            object_id="multi_version_op",
            digest=digest,
        )
        with pytest.raises(ObjectDeletedError):
            trace_server.op_read(read_req)

    # Verify the last two still exist
    for digest in digests[2:]:
        read_req = tsi.OpReadReq(
            project_id=project_id,
            object_id="multi_version_op",
            digest=digest,
        )
        read_res = trace_server.op_read(read_req)
        assert read_res.digest == digest


def test_op_delete_not_found(trace_server):
    """Test deleting a non-existent op raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_op_delete_not_found"

    delete_req = tsi.OpDeleteReq(
        project_id=project_id,
        object_id="nonexistent_op",
        digests=["fake_digest"],
    )

    with pytest.raises(NotFoundError):
        trace_server.op_delete(delete_req)


def test_op_versioning(trace_server):
    """Test that creating multiple versions of an op increments version_index."""
    project_id = f"{TEST_ENTITY}/test_op_versioning"

    # Create multiple versions of the same op
    versions = []
    for i in range(3):
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name="versioned_function",
            description=None,
            source_code=f"def versioned_function():\n    return {i}",
        )
        create_res = trace_server.op_create(create_req)
        versions.append(create_res)

    # Verify version indices increment
    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2

    # Verify all versions are distinct
    assert len({v.digest for v in versions}) == 3


def test_op_code_with_special_characters(trace_server):
    """Test creating and reading an op with special characters in source code."""
    project_id = f"{TEST_ENTITY}/test_op_special_chars"

    # Create an op with special characters
    source_code = """def special_function(x: str) -> str:
    '''This function has "quotes" and 'apostrophes'.'''
    return f"Result: {x} with special chars: \n\t\r"
"""
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="special_function",
        description=None,
        source_code=source_code,
    )
    create_res = trace_server.op_create(create_req)

    # Read it back and verify the code is preserved
    read_req = tsi.OpReadReq(
        project_id=project_id,
        object_id="special_function",
        digest=create_res.digest,
    )
    read_res = trace_server.op_read(read_req)

    assert read_res.code == source_code


def test_op_code_with_unicode(trace_server):
    """Test creating and reading an op with unicode characters in source code."""
    project_id = f"{TEST_ENTITY}/test_op_unicode"

    # Create an op with unicode
    source_code = """def unicode_function():
    '''This function has unicode: 你好世界 🚀 café'''
    return "unicode test"
"""
    create_req = tsi.OpCreateReq(
        project_id=project_id,
        name="unicode_function",
        description=None,
        source_code=source_code,
    )
    create_res = trace_server.op_create(create_req)

    # Read it back and verify the unicode is preserved
    read_req = tsi.OpReadReq(
        project_id=project_id,
        object_id="unicode_function",
        digest=create_res.digest,
    )
    read_res = trace_server.op_read(read_req)

    assert read_res.code == source_code
    assert "你好世界" in read_res.code
    assert "🚀" in read_res.code
    assert "café" in read_res.code


def test_op_list_after_deletion(trace_server):
    """Test that deleted ops don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_op_list_after_deletion"

    # Create three ops
    op_names = ["op_keep_1", "op_delete", "op_keep_2"]
    digests = {}
    for name in op_names:
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name=name,
            description=None,
            source_code=f"def {name}():\n    pass",
        )
        create_res = trace_server.op_create(create_req)
        digests[name] = create_res.digest

    # Delete one op
    delete_req = tsi.OpDeleteReq(
        project_id=project_id,
        object_id="op_delete",
        digests=None,
    )
    trace_server.op_delete(delete_req)

    # List ops - should only see the two that weren't deleted
    list_req = tsi.OpListReq(project_id=project_id)
    ops = list(trace_server.op_list(list_req))

    op_names_returned = {op.object_id for op in ops}
    assert op_names_returned == {"op_keep_1", "op_keep_2"}
    assert "op_delete" not in op_names_returned
