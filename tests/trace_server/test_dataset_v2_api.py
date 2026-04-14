"""Tests for Dataset V2 API endpoints.

Tests verify that the Dataset V2 API correctly creates, reads, lists, and deletes dataset objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_dataset_create_and_read(trace_server):
    """Test creating datasets (with and without description) and reading them back."""
    project_id = f"{TEST_ENTITY}/test_dataset_create_and_read"

    # Create with description
    rows = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    create_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="people",
            description="A dataset of people",
            rows=rows,
        )
    )
    assert create_res.digest is not None
    assert create_res.object_id == "people"
    assert create_res.version_index == 0

    # Read it back
    read_res = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="people",
            digest=create_res.digest,
        )
    )
    assert read_res.object_id == "people"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == "people"
    assert read_res.description == "A dataset of people"
    assert read_res.created_at is not None
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")

    # Create without description
    create_res2 = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="dataset_no_desc",
            description=None,
            rows=[{"x": 1, "y": 2}],
        )
    )
    assert create_res2.digest is not None
    assert create_res2.object_id == "dataset_no_desc"
    assert create_res2.version_index == 0

    # Create with empty rows
    create_res3 = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="empty_dataset",
            description="A dataset with no rows",
            rows=[],
        )
    )
    assert create_res3.digest is not None
    read_res3 = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="empty_dataset",
            digest=create_res3.digest,
        )
    )
    assert read_res3.name == "empty_dataset"
    assert isinstance(read_res3.rows, str)

    # Create with many rows
    large_rows = [{"id": i, "value": f"value_{i}", "data": i * 2} for i in range(100)]
    create_res4 = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="large_dataset",
            description="A dataset with 100 rows",
            rows=large_rows,
        )
    )
    assert create_res4.digest is not None
    read_res4 = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="large_dataset",
            digest=create_res4.digest,
        )
    )
    assert read_res4.name == "large_dataset"
    assert isinstance(read_res4.rows, str)
    assert read_res4.rows.startswith("weave:///")

    # Read not found
    with pytest.raises(NotFoundError):
        trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id,
                object_id="nonexistent_dataset",
                digest="fake_digest_1234567890",
            )
        )


def test_dataset_list_and_pagination(trace_server):
    """Test listing datasets with limit, offset, and empty project."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_pagination"

    # Empty project
    datasets = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id))
    )
    assert len(datasets) == 0

    # Create 10 datasets
    for i in range(10):
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name=f"dataset_{i}",
                description=None,
                rows=[{"value": i}],
            )
        )

    # List all
    datasets = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id))
    )
    assert len(datasets) == 10
    for ds in datasets:
        assert isinstance(ds.rows, str)
        assert ds.rows.startswith("weave:///")
        assert ds.created_at is not None

    # Limit
    datasets = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id, limit=3))
    )
    assert len(datasets) == 3

    # Offset
    datasets = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id, offset=7))
    )
    assert len(datasets) == 3

    # Limit + offset pagination
    page1 = list(
        trace_server.dataset_list(
            tsi.DatasetListReq(project_id=project_id, limit=3, offset=0)
        )
    )
    page2 = list(
        trace_server.dataset_list(
            tsi.DatasetListReq(project_id=project_id, limit=3, offset=3)
        )
    )
    assert len(page1) == 3
    assert len(page2) == 3
    page1_names = {ds.name for ds in page1}
    page2_names = {ds.name for ds in page2}
    assert len(page1_names & page2_names) == 0


def test_dataset_versioning(trace_server):
    """Test version_index increments and all versions are distinct."""
    project_id = f"{TEST_ENTITY}/test_dataset_versioning"

    versions = []
    for i in range(3):
        create_res = trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="versioned_dataset",
                description=f"Version {i}",
                rows=[{"value": i}],
            )
        )
        versions.append(create_res)

    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2
    assert len({v.digest for v in versions}) == 3


def test_dataset_delete(trace_server):
    """Test deleting datasets: single version, all versions, multiple versions, not found."""
    project_id = f"{TEST_ENTITY}/test_dataset_delete"

    # Delete single version
    create_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="delete_single",
            description=None,
            rows=[{"id": 1}],
        )
    )
    delete_res = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id,
            object_id="delete_single",
            digests=[create_res.digest],
        )
    )
    assert delete_res.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id,
                object_id="delete_single",
                digest=create_res.digest,
            )
        )

    # Delete all versions
    digests = []
    for i in range(3):
        res = trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="delete_all",
                description=None,
                rows=[{"version": i}],
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id, object_id="delete_all", digests=None
        )
    )
    assert delete_res.num_deleted == 3

    # Delete multiple specific versions (keep some)
    digests = []
    for i in range(4):
        res = trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name="delete_multi",
                description=None,
                rows=[{"version": i}],
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.dataset_delete(
        tsi.DatasetDeleteReq(
            project_id=project_id,
            object_id="delete_multi",
            digests=digests[:2],
        )
    )
    assert delete_res.num_deleted == 2
    for digest in digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.dataset_read(
                tsi.DatasetReadReq(
                    project_id=project_id,
                    object_id="delete_multi",
                    digest=digest,
                )
            )
    for digest in digests[2:]:
        read_res = trace_server.dataset_read(
            tsi.DatasetReadReq(
                project_id=project_id,
                object_id="delete_multi",
                digest=digest,
            )
        )
        assert read_res.digest == digest

    # Delete not found
    with pytest.raises(NotFoundError):
        trace_server.dataset_delete(
            tsi.DatasetDeleteReq(
                project_id=project_id,
                object_id="nonexistent_dataset",
                digests=["fake_digest"],
            )
        )


def test_dataset_list_after_deletion(trace_server):
    """Test that deleted datasets don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_after_deletion"

    dataset_names = ["keep_1", "delete_me", "keep_2"]
    for name in dataset_names:
        trace_server.dataset_create(
            tsi.DatasetCreateReq(
                project_id=project_id,
                name=name,
                description=None,
                rows=[{"id": 1}],
            )
        )

    trace_server.dataset_delete(
        tsi.DatasetDeleteReq(project_id=project_id, object_id="delete_me", digests=None)
    )

    datasets = list(
        trace_server.dataset_list(tsi.DatasetListReq(project_id=project_id))
    )
    dataset_names_returned = {ds.name for ds in datasets}
    assert dataset_names_returned == {"keep_1", "keep_2"}


def test_dataset_special_characters_and_unicode(trace_server):
    """Test creating and reading datasets with special characters and unicode."""
    project_id = f"{TEST_ENTITY}/test_dataset_special_chars"

    # Special characters
    rows = [
        {"text": "This has \"quotes\" and 'apostrophes'"},
        {"text": "Line breaks:\n\tand tabs"},
        {"text": "Unicode: 你好世界 🚀"},
    ]
    create_res = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="special_chars",
            description='Dataset with "special" characters',
            rows=rows,
        )
    )
    read_res = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="special_chars",
            digest=create_res.digest,
        )
    )
    assert read_res.name == "special_chars"
    assert read_res.description == 'Dataset with "special" characters'
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")

    # Unicode
    unicode_rows = [
        {"language": "Chinese", "greeting": "你好世界"},
        {"language": "Japanese", "greeting": "こんにちは"},
        {"language": "Emoji", "greeting": "🚀 🌟 ✨"},
    ]
    create_res2 = trace_server.dataset_create(
        tsi.DatasetCreateReq(
            project_id=project_id,
            name="unicode_dataset",
            description="Unicode greetings 🌍",
            rows=unicode_rows,
        )
    )
    read_res2 = trace_server.dataset_read(
        tsi.DatasetReadReq(
            project_id=project_id,
            object_id="unicode_dataset",
            digest=create_res2.digest,
        )
    )
    assert read_res2.name == "unicode_dataset"
    assert read_res2.description == "Unicode greetings 🌍"
    assert "🌍" in read_res2.description
