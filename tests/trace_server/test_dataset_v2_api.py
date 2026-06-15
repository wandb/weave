"""Tests for Dataset V2 API endpoints.

Tests verify that the Dataset V2 API correctly creates, reads, lists, and deletes dataset objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_dataset_create_shapes(trace_server):
    """dataset_create across row shapes: with/without description, empty, large.

    Every create returns a digest, echoes object_id, and starts at version 0.
    """
    project_id = f"{TEST_ENTITY}/test_dataset_create_shapes"
    cases = [
        (
            "with_desc",
            "A test dataset",
            [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}],
        ),
        ("no_desc", None, [{"x": 1, "y": 2}]),
        ("empty_rows", "A dataset with no rows", []),
        (
            "large_rows",
            "100 rows",
            [{"id": i, "value": f"value_{i}"} for i in range(100)],
        ),
    ]
    for name, description, rows in cases:
        res = trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id, name=name, description=description, rows=rows
            )
        )
        assert res.digest is not None
        assert res.object_id == name
        assert res.version_index == 0


def test_dataset_read_round_trip_and_not_found(trace_server):
    """dataset_read returns full metadata and a `weave:///` rows reference (never
    inline data); reading a missing dataset raises NotFoundError.
    """
    project_id = f"{TEST_ENTITY}/test_dataset_read"
    create_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="people",
            description="A dataset of people",
            rows=[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
        )
    )

    read_res = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id, object_id="people", digest=create_res.digest
        )
    )
    assert read_res.object_id == "people"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == "people"
    assert read_res.description == "A dataset of people"
    assert read_res.created_at is not None
    # Rows are a reference, not the actual data.
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")

    # Version-like digest "v0" resolves to the same first version (int parse path);
    # a "v"-prefixed non-integer digest falls back to a digest lookup (NotFound).
    by_version = trace_server.dataset_read(
        tsi.DatasetReadReq(project_id=project_id, object_id="people", digest="v0")
    )
    assert by_version.digest == create_res.digest
    with pytest.raises(NotFoundError):
        trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id, object_id="people", digest="vnotanint"
            )
        )

    with pytest.raises(NotFoundError):
        trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id,
                object_id="nonexistent_dataset",
                digest="fake_digest_1234567890",
            )
        )


def test_dataset_metadata_preserves_special_and_unicode(trace_server):
    """Special characters and unicode in name/description survive the create ->
    read round-trip; rows remain a reference.
    """
    project_id = f"{TEST_ENTITY}/test_dataset_special_unicode"

    special_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="special_chars",
            description='Dataset with "special" characters',
            rows=[
                {"text": "This has \"quotes\" and 'apostrophes'"},
                {"text": "Line breaks:\n\tand tabs"},
                {"text": "Unicode: 你好世界 🚀"},
            ],
        )
    )
    special_read = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id, object_id="special_chars", digest=special_res.digest
        )
    )
    assert special_read.name == "special_chars"
    assert special_read.description == 'Dataset with "special" characters'
    assert isinstance(special_read.rows, str)
    assert special_read.rows.startswith("weave:///")

    unicode_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="unicode_dataset",
            description="Unicode greetings 🌍",
            rows=[
                {"language": "Chinese", "greeting": "你好世界"},
                {"language": "Japanese", "greeting": "こんにちは"},
                {"language": "Emoji", "greeting": "🚀 🌟 ✨"},
            ],
        )
    )
    unicode_read = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="unicode_dataset",
            digest=unicode_res.digest,
        )
    )
    assert unicode_read.name == "unicode_dataset"
    assert unicode_read.description == "Unicode greetings 🌍"
    assert "🌍" in unicode_read.description


def test_dataset_versioning_increments_and_distinct_digests(trace_server):
    """Re-creating the same dataset name increments version_index and yields a
    distinct digest per version.
    """
    project_id = f"{TEST_ENTITY}/test_dataset_versioning"
    versions = [
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="versioned_dataset",
                description=f"Version {i}",
                rows=[{"value": i}],
            )
        )
        for i in range(3)
    ]

    assert [v.version_index for v in versions] == [0, 1, 2]
    assert len({v.digest for v in versions}) == 3


def test_dataset_list_pagination_and_empty(trace_server):
    """dataset_list: empty project -> 0; basic list returns all names with rows
    references; limit, offset, and limit+offset paginate without overlap.
    """
    empty_project = f"{TEST_ENTITY}/test_dataset_list_empty"
    assert (
        list(trace_server.dataset_list(tsi.DatasetListReq(project_id=empty_project)))
        == []
    )

    # Basic list: three named datasets, each with a rows reference.
    basic_project = f"{TEST_ENTITY}/test_dataset_list_basic"
    for name in ("dataset_a", "dataset_b", "dataset_c"):
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=basic_project,
                name=name,
                description=f"Dataset {name}",
                rows=[{"id": 1, "name": name}],
            )
        )
    basic = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=basic_project))
    )
    assert len(basic) == 3
    assert {ds.name for ds in basic} == {"dataset_a", "dataset_b", "dataset_c"}
    for ds in basic:
        assert isinstance(ds.rows, str)
        assert ds.rows.startswith("weave:///")
        assert ds.created_at is not None

    # Pagination: 10 datasets, exercise limit, offset, and limit+offset.
    page_project = f"{TEST_ENTITY}/test_dataset_list_pagination"
    for i in range(10):
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=page_project,
                name=f"dataset_{i}",
                description=None,
                rows=[{"value": i}],
            )
        )
    assert (
        len(
            list(
                trace_server.dataset_list(
                    tsi.DatasetListReq(project_id=page_project, limit=3)
                )
            )
        )
        == 3
    )
    assert (
        len(
            list(
                trace_server.dataset_list(
                    tsi.DatasetListReq(project_id=page_project, offset=7)
                )
            )
        )
        == 3
    )
    page1 = list(
        trace_server.dataset_list(
            tsi.DatasetListReq(project_id=page_project, limit=3, offset=0)
        )
    )
    page2 = list(
        trace_server.dataset_list(
            tsi.DatasetListReq(project_id=page_project, limit=3, offset=3)
        )
    )
    assert len(page1) == 3
    assert len(page2) == 3
    assert {ds.name for ds in page1} & {ds.name for ds in page2} == set()


def test_dataset_delete_variants(trace_server):
    """dataset_delete: single version, all versions (digests=None), a specific
    subset, and a missing dataset (NotFoundError). Deleted versions raise
    ObjectDeletedError on read; surviving versions still read.
    """
    project_id = f"{TEST_ENTITY}/test_dataset_delete_variants"

    # Single version: delete then read raises ObjectDeletedError.
    single = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id, name="single", description=None, rows=[{"id": 1}]
        )
    )
    single_del = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id, object_id="single", digests=[single.digest]
        )
    )
    assert single_del.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id, object_id="single", digest=single.digest
            )
        )

    # All versions: digests=None deletes every version.
    for i in range(3):
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="all_versions",
                description=None,
                rows=[{"version": i}],
            )
        )
    all_del = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id, object_id="all_versions", digests=None
        )
    )
    assert all_del.num_deleted == 3

    # Subset: delete the first two of four; the last two still read.
    multi_digests = [
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="multi",
                description=None,
                rows=[{"version": i}],
            )
        ).digest
        for i in range(4)
    ]
    multi_del = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id, object_id="multi", digests=multi_digests[:2]
        )
    )
    assert multi_del.num_deleted == 2
    for digest in multi_digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.dataset_read(
                tsi.DatasetReadReq(
                    project_id=project_id, object_id="multi", digest=digest
                )
            )
    for digest in multi_digests[2:]:
        assert (
            trace_server.dataset_read(
                tsi.DatasetReadReq(
                    project_id=project_id, object_id="multi", digest=digest
                )
            ).digest
            == digest
        )

    # Missing dataset raises NotFoundError.
    with pytest.raises(NotFoundError):
        trace_server.dataset_delete(
            tsi.DatasetDeleteReq(
                project_id=project_id,
                object_id="nonexistent_dataset",
                digests=["fake_digest"],
            )
        )


def test_dataset_list_excludes_deleted(trace_server):
    """A deleted dataset disappears from dataset_list while siblings remain."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_after_deletion"
    for name in ("keep_1", "delete_me", "keep_2"):
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id, name=name, description=None, rows=[{"id": 1}]
            )
        )

    trace_server.dataset_delete(
        tsi.DatasetDeleteReq(project_id=project_id, object_id="delete_me", digests=None)
    )

    names = {
        ds.name
        for ds in trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id))
    }
    assert names == {"keep_1", "keep_2"}
    assert "delete_me" not in names
