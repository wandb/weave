"""Tests for Op V2 API endpoints.

Tests verify that the Op V2 API correctly creates, reads, lists, and deletes op objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_op_create_with_and_without_source_code(trace_server):
    """op_create returns a digest + object_id at version 0, whether or not
    source code is supplied (None falls back to a placeholder body).
    """
    project_id = f"{TEST_ENTITY}/test_op_create"

    with_source = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="my_function",
            description=None,
            source_code="def my_function(x: int) -> int:\n    return x * 2",
        )
    )
    assert with_source.digest is not None
    assert with_source.object_id == "my_function"
    assert with_source.version_index == 0

    without_source = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name="my_op_no_source",
            description=None,
            source_code=None,
        )
    )
    assert without_source.digest is not None
    assert without_source.object_id == "my_op_no_source"
    assert without_source.version_index == 0


@pytest.mark.parametrize(
    ("name", "source_code", "extra_substrings"),
    [
        (
            "read_test",
            "def read_test(x: int) -> int:\n    return x + 1",
            [],
        ),
        (
            "special_function",
            "def special_function(x: str) -> str:\n"
            "    '''This function has \"quotes\" and 'apostrophes'.'''\n"
            '    return f"Result: {x} with special chars: \n\t\r"\n',
            [],
        ),
        (
            "unicode_function",
            "def unicode_function():\n"
            "    '''This function has unicode: 你好世界 🚀 café'''\n"
            '    return "unicode test"\n',
            ["你好世界", "🚀", "café"],
        ),
    ],
    ids=["plain", "special_chars", "unicode"],
)
def test_op_read_roundtrip(trace_server, name, source_code, extra_substrings):
    """op_read returns the created op with its source code preserved verbatim,
    including special characters and unicode.
    """
    project_id = f"{TEST_ENTITY}/test_op_read_{name}"

    create_res = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=project_id,
            name=name,
            description=None,
            source_code=source_code,
        )
    )
    read_res = trace_server.op_read(
        tsi.OpReadReq(project_id=project_id, object_id=name, digest=create_res.digest)
    )

    assert read_res.object_id == name
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.code == source_code
    assert read_res.created_at is not None
    for substring in extra_substrings:
        assert substring in read_res.code


def test_op_read_not_found(trace_server):
    """Reading a non-existent op raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_op_read_not_found"
    with pytest.raises(NotFoundError):
        trace_server.op_read(
            tsi.OpReadReq(
                project_id=project_id,
                object_id="nonexistent_op",
                digest="fake_digest_1234567890",
            )
        )


def test_op_list_content_and_filtering(trace_server):
    """op_list returns every op with code + created_at loaded, an empty project
    yields nothing, and deleted ops drop out of subsequent listings.
    """
    # Empty project -> no ops.
    empty_project = f"{TEST_ENTITY}/test_op_list_empty"
    assert list(trace_server.op_list(tsi.OpListReq(project_id=empty_project))) == []

    # Three ops, all carry loaded code + created_at.
    project_id = f"{TEST_ENTITY}/test_op_list_basic"
    for name in ("op_a", "op_b", "op_c"):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name=name,
                description=None,
                source_code=f"def {name}():\n    pass",
            )
        )
    ops = list(trace_server.op_list(tsi.OpListReq(project_id=project_id)))
    assert {op.object_id for op in ops} == {"op_a", "op_b", "op_c"}
    for op in ops:
        assert op.code
        assert "def " in op.code
        assert op.created_at is not None

    # Deleting an op removes it from the listing.
    del_project = f"{TEST_ENTITY}/test_op_list_after_deletion"
    for name in ("op_keep_1", "op_delete", "op_keep_2"):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=del_project,
                name=name,
                description=None,
                source_code=f"def {name}():\n    pass",
            )
        )
    trace_server.op_delete(
        tsi.OpDeleteReq(project_id=del_project, object_id="op_delete", digests=None)
    )
    remaining = list(trace_server.op_list(tsi.OpListReq(project_id=del_project)))
    assert {op.object_id for op in remaining} == {"op_keep_1", "op_keep_2"}


@pytest.mark.parametrize(
    ("limit", "offset", "expected_count"),
    [(3, None, 3), (None, 2, 3)],
    ids=["limit", "offset"],
)
def test_op_list_pagination(trace_server, limit, offset, expected_count):
    """Limit and offset each slice the op listing over a 5-op project."""
    project_id = f"{TEST_ENTITY}/test_op_list_pagination"
    for i in range(5):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name=f"op_{i}",
                description=None,
                source_code=f"def op_{i}():\n    pass",
            )
        )
    req_kwargs = {"project_id": project_id}
    if limit is not None:
        req_kwargs["limit"] = limit
    if offset is not None:
        req_kwargs["offset"] = offset
    ops = list(trace_server.op_list(tsi.OpListReq(**req_kwargs)))
    assert len(ops) == expected_count


def test_op_list_pagination_pages_are_disjoint(trace_server):
    """Successive limit/offset pages over the same project never overlap."""
    project_id = f"{TEST_ENTITY}/test_op_list_pages_disjoint"
    for i in range(10):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name=f"op_{i}",
                description=None,
                source_code=f"def op_{i}():\n    pass",
            )
        )
    page1 = list(
        trace_server.op_list(tsi.OpListReq(project_id=project_id, limit=3, offset=0))
    )
    page2 = list(
        trace_server.op_list(tsi.OpListReq(project_id=project_id, limit=3, offset=3))
    )
    assert len(page1) == 3
    assert len(page2) == 3
    assert {op.object_id for op in page1} & {op.object_id for op in page2} == set()


def test_op_delete_versions(trace_server):
    """op_delete handles a single version, a specific subset (survivors remain),
    all versions (digests=None), and raises NotFoundError for a missing op.
    """
    # Single version: deleted op then reads as ObjectDeletedError.
    single_project = f"{TEST_ENTITY}/test_op_delete_single"
    single = trace_server.op_create(
        tsi.OpCreateReq(
            project_id=single_project,
            name="delete_test",
            description=None,
            source_code="def delete_test():\n    pass",
        )
    )
    single_del = trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=single_project,
            object_id="delete_test",
            digests=[single.digest],
        )
    )
    assert single_del.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.op_read(
            tsi.OpReadReq(
                project_id=single_project,
                object_id="delete_test",
                digest=single.digest,
            )
        )

    # Subset of versions: first two deleted, last two still readable.
    multi_project = f"{TEST_ENTITY}/test_op_delete_multiple"
    digests = [
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=multi_project,
                name="multi_version_op",
                description=None,
                source_code=f"def multi_version_op():\n    return {i}",
            )
        ).digest
        for i in range(4)
    ]
    multi_del = trace_server.op_delete(
        tsi.OpDeleteReq(
            project_id=multi_project,
            object_id="multi_version_op",
            digests=digests[:2],
        )
    )
    assert multi_del.num_deleted == 2
    for digest in digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.op_read(
                tsi.OpReadReq(
                    project_id=multi_project,
                    object_id="multi_version_op",
                    digest=digest,
                )
            )
    for digest in digests[2:]:
        read_res = trace_server.op_read(
            tsi.OpReadReq(
                project_id=multi_project,
                object_id="multi_version_op",
                digest=digest,
            )
        )
        assert read_res.digest == digest

    # All versions: digests=None deletes every version.
    all_project = f"{TEST_ENTITY}/test_op_delete_all"
    for i in range(3):
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=all_project,
                name="versioned_op",
                description=None,
                source_code=f"def versioned_op():\n    return {i}",
            )
        )
    all_del = trace_server.op_delete(
        tsi.OpDeleteReq(project_id=all_project, object_id="versioned_op", digests=None)
    )
    assert all_del.num_deleted == 3

    # Missing op raises NotFoundError.
    nf_project = f"{TEST_ENTITY}/test_op_delete_not_found"
    with pytest.raises(NotFoundError):
        trace_server.op_delete(
            tsi.OpDeleteReq(
                project_id=nf_project,
                object_id="nonexistent_op",
                digests=["fake_digest"],
            )
        )


def test_op_versioning(trace_server):
    """Creating multiple versions of an op increments version_index and yields
    distinct digests.
    """
    project_id = f"{TEST_ENTITY}/test_op_versioning"
    versions = [
        trace_server.op_create(
            tsi.OpCreateReq(
                project_id=project_id,
                name="versioned_function",
                description=None,
                source_code=f"def versioned_function():\n    return {i}",
            )
        )
        for i in range(3)
    ]

    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2
    assert len({v.digest for v in versions}) == 3
