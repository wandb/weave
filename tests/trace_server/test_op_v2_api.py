"""Tests for Op V2 API endpoints.

Tests verify that the Op V2 API correctly creates, reads, lists, and deletes op objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_op_create_and_read(trace_server):
    """Test creating ops (with and without source code) and reading them back."""
    project_id = f"{TEST_ENTITY}/test_op_create_and_read"

    # Create with source code
    source_code = "def my_function(x: int) -> int:\n    return x * 2"
    create_res = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="my_function",
            description=None,
            source_code=source_code,
        )
    )
    assert create_res.digest is not None
    assert create_res.object_id == "my_function"
    assert create_res.version_index == 0

    # Read it back
    read_res = trace_server.op_read(
        tsi.OpReadReq(
            project_id=project_id,
            object_id="my_function",
            digest=create_res.digest,
        )
    )
    assert read_res.object_id == "my_function"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.code == source_code
    assert read_res.created_at is not None

    # Create without source code
    create_res2 = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="my_op_no_source",
            description=None,
            source_code=None,
        )
    )
    assert create_res2.digest is not None
    assert create_res2.object_id == "my_op_no_source"
    assert create_res2.version_index == 0

    # Read not found
    with pytest.raises(NotFoundError):
        trace_server.op_read(
            tsi.OpReadReq(
                project_id=project_id,
                object_id="nonexistent_op",
                digest="fake_digest_1234567890",
            )
        )


def test_op_list_and_pagination(trace_server):
    """Test listing ops with limit, offset, and empty project."""
    project_id = f"{TEST_ENTITY}/test_op_list_pagination"

    # Empty project
    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id)))
    assert len(ops) == 0

    # Create 10 ops
    for i in range(10):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name=f"op_{i}",
                description=None,
                source_code=f"def op_{i}():\n    pass",
            )
        )

    # List all
    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id)))
    assert len(ops) == 10
    for op in ops:
        assert op.code
        assert "def " in op.code
        assert op.created_at is not None

    # Limit
    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id, limit=3)))
    assert len(ops) == 3

    # Offset
    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id, offset=7)))
    assert len(ops) == 3

    # Limit + offset pagination
    page1 = list(
        trace_server.op_list(
            tsi.OpListReq(project_id=project_id, limit=3, offset=0)
        )
    )
    page2 = list(
        trace_server.op_list(
            tsi.OpListReq(project_id=project_id, limit=3, offset=3)
        )
    )
    assert len(page1) == 3
    assert len(page2) == 3
    page1_ids = {op.object_id for op in page1}
    page2_ids = {op.object_id for op in page2}
    assert len(page1_ids & page2_ids) == 0


def test_op_versioning(trace_server):
    """Test version_index increments and all versions are distinct."""
    project_id = f"{TEST_ENTITY}/test_op_versioning"

    versions = []
    for i in range(3):
        create_res = trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name="versioned_function",
                description=None,
                source_code=f"def versioned_function():\n    return {i}",
            )
        )
        versions.append(create_res)

    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2
    assert len({v.digest for v in versions}) == 3


def test_op_delete(trace_server):
    """Test deleting ops: single version, all versions, multiple versions, not found."""
    project_id = f"{TEST_ENTITY}/test_op_delete"

    # Delete single version
    create_res = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="delete_single",
            description=None,
            source_code="def delete_single():\n    pass",
        )
    )
    delete_res = trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=project_id,
            object_id="delete_single",
            digests=[create_res.digest],
        )
    )
    assert delete_res.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.op_read(
            tsi.OpReadReq(
                project_id=project_id,
                object_id="delete_single",
                digest=create_res.digest,
            )
        )

    # Delete all versions
    digests = []
    for i in range(3):
        res = trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name="delete_all",
                description=None,
                source_code=f"def delete_all():\n    return {i}",
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=project_id, object_id="delete_all", digests=None
        )
    )
    assert delete_res.num_deleted == 3

    # Delete multiple specific versions (keep some)
    digests = []
    for i in range(4):
        res = trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name="delete_multi",
                description=None,
                source_code=f"def delete_multi():\n    return {i}",
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=project_id,
            object_id="delete_multi",
            digests=digests[:2],
        )
    )
    assert delete_res.num_deleted == 2
    for digest in digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.op_read(
                tsi.OpReadReq(
                    project_id=project_id,
                    object_id="delete_multi",
                    digest=digest,
                )
            )
    for digest in digests[2:]:
        read_res = trace_server.op_read(
            tsi.OpReadReq(
                project_id=project_id,
                object_id="delete_multi",
                digest=digest,
            )
        )
        assert read_res.digest == digest

    # Delete not found
    with pytest.raises(NotFoundError):
        trace_server.op_delete(
            tsi.OpDeleteReq(
                project_id=project_id,
                object_id="nonexistent_op",
                digests=["fake_digest"],
            )
        )


def test_op_list_after_deletion(trace_server):
    """Test that deleted ops don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_op_list_after_deletion"

    op_names = ["op_keep_1", "op_delete", "op_keep_2"]
    for name in op_names:
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name=name,
                description=None,
                source_code=f"def {name}():\n    pass",
            )
        )

    trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=project_id, object_id="op_delete", digests=None
        )
    )

    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id)))
    op_names_returned = {op.object_id for op in ops}
    assert op_names_returned == {"op_keep_1", "op_keep_2"}


def test_op_special_characters_and_unicode(trace_server):
    """Test creating and reading ops with special characters and unicode."""
    project_id = f"{TEST_ENTITY}/test_op_special_chars"

    # Special characters
    source_special = """def special_function(x: str) -> str:
    '''This function has "quotes" and 'apostrophes'.'''
    return f"Result: {x} with special chars: \n\t\r"
"""
    create_res = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="special_function",
            description=None,
            source_code=source_special,
        )
    )
    read_res = trace_server.op_read(
        tsi.OpReadReq(
            project_id=project_id,
            object_id="special_function",
            digest=create_res.digest,
        )
    )
    assert read_res.code == source_special

    # Unicode
    source_unicode = """def unicode_function():
    '''This function has unicode: 你好世界 🚀 café'''
    return "unicode test"
"""
    create_res = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="unicode_function",
            description=None,
            source_code=source_unicode,
        )
    )
    read_res = trace_server.op_read(
        tsi.OpReadReq(
            project_id=project_id,
            object_id="unicode_function",
            digest=create_res.digest,
        )
    )
    assert read_res.code == source_unicode
    assert "你好世界" in read_res.code
    assert "🚀" in read_res.code
    assert "café" in read_res.code
