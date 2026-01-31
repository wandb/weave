"""Tests for Dataset V2 API endpoints.

Tests verify that the Dataset V2 API correctly creates, reads, lists, and deletes dataset objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_dataset_create_basic(trace_server):
    """Test creating a basic dataset object."""
    project_id = f"{TEST_ENTITY}/test_dataset_create_basic"

    # Create a dataset
    rows = [
        {"id": 1, "value": "a"},
        {"id": 2, "value": "b"},
        {"id": 3, "value": "c"},
    ]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="my_dataset",
        description="A test dataset",
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "my_dataset"
    assert create_res.version_index == 0


def test_dataset_create_without_description(trace_server):
    """Test creating a dataset without providing a description."""
    project_id = f"{TEST_ENTITY}/test_dataset_create_no_desc"

    # Create a dataset without description
    rows = [{"x": 1, "y": 2}]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="dataset_no_desc",
        description=None,
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "dataset_no_desc"
    assert create_res.version_index == 0


def test_dataset_read_basic(trace_server):
    """Test reading a specific dataset object."""
    project_id = f"{TEST_ENTITY}/test_dataset_read_basic"

    # Create a dataset
    rows = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="people",
        description="A dataset of people",
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    # Read the dataset back
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="people",
        digest=create_res.digest,
    )
    read_res = trace_server.dataset_read(read_req)

    assert read_res.object_id == "people"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == "people"
    assert read_res.description == "A dataset of people"
    assert read_res.created_at is not None
    # Verify rows is a string reference, not the actual data
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")


def test_dataset_read_not_found(trace_server):
    """Test reading a non-existent dataset raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_dataset_read_not_found"

    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="nonexistent_dataset",
        digest="fake_digest_1234567890",
    )

    with pytest.raises(NotFoundError):
        trace_server.dataset_read(read_req)


def test_dataset_list_basic(trace_server):
    """Test listing all datasets in a project."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_basic"

    # Create multiple datasets
    dataset_names = ["dataset_a", "dataset_b", "dataset_c"]
    for name in dataset_names:
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name=name,
            description=f"Dataset {name}",
            rows=[{"id": 1, "name": name}],
        )
        trace_server.dataset_create(create_req)

    # List all datasets
    list_req = tsi.DatasetListReq(project_id=project_id)
    datasets = list(trace_server.dataset_list(list_req))

    assert len(datasets) == 3
    dataset_names_returned = {ds.name for ds in datasets}
    assert dataset_names_returned == {"dataset_a", "dataset_b", "dataset_c"}

    # Verify all datasets have rows references (not actual data)
    for ds in datasets:
        assert isinstance(ds.rows, str)
        assert ds.rows.startswith("weave:///")
        assert ds.created_at is not None


def test_dataset_list_with_limit(trace_server):
    """Test listing datasets with a limit."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_limit"

    # Create multiple datasets
    for i in range(5):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name=f"dataset_{i}",
            description=None,
            rows=[{"value": i}],
        )
        trace_server.dataset_create(create_req)

    # List with a limit
    list_req = tsi.DatasetListReq(project_id=project_id, limit=3)
    datasets = list(trace_server.dataset_list(list_req))

    assert len(datasets) == 3


def test_dataset_list_with_offset(trace_server):
    """Test listing datasets with an offset."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_offset"

    # Create multiple datasets
    for i in range(5):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name=f"dataset_{i}",
            description=None,
            rows=[{"value": i}],
        )
        trace_server.dataset_create(create_req)

    # List with an offset
    list_req = tsi.DatasetListReq(project_id=project_id, offset=2)
    datasets = list(trace_server.dataset_list(list_req))

    assert len(datasets) == 3


def test_dataset_list_with_limit_and_offset(trace_server):
    """Test listing datasets with both limit and offset for pagination."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_pagination"

    # Create multiple datasets
    for i in range(10):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name=f"dataset_{i}",
            description=None,
            rows=[{"value": i}],
        )
        trace_server.dataset_create(create_req)

    # First page
    list_req1 = tsi.DatasetListReq(project_id=project_id, limit=3, offset=0)
    datasets1 = list(trace_server.dataset_list(list_req1))
    assert len(datasets1) == 3

    # Second page
    list_req2 = tsi.DatasetListReq(project_id=project_id, limit=3, offset=3)
    datasets2 = list(trace_server.dataset_list(list_req2))
    assert len(datasets2) == 3

    # Verify different datasets on different pages
    datasets1_names = {ds.name for ds in datasets1}
    datasets2_names = {ds.name for ds in datasets2}
    assert len(datasets1_names & datasets2_names) == 0  # No overlap


def test_dataset_list_empty_project(trace_server):
    """Test listing datasets in a project with no datasets."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_empty"

    list_req = tsi.DatasetListReq(project_id=project_id)
    datasets = list(trace_server.dataset_list(list_req))

    assert len(datasets) == 0


def test_dataset_delete_single_version(trace_server):
    """Test deleting a single version of a dataset."""
    project_id = f"{TEST_ENTITY}/test_dataset_delete_single"

    # Create a dataset
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="delete_test",
        description=None,
        rows=[{"id": 1}],
    )
    create_res = trace_server.dataset_create(create_req)

    # Delete the specific version
    delete_req = tsi.DatasetDeleteReq(
        project_id=project_id,
        object_id="delete_test",
        digests=[create_res.digest],
    )
    delete_res = trace_server.dataset_delete(delete_req)

    assert delete_res.num_deleted == 1

    # Verify the dataset is deleted (should raise ObjectDeletedError)
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="delete_test",
        digest=create_res.digest,
    )
    with pytest.raises(ObjectDeletedError):
        trace_server.dataset_read(read_req)


def test_dataset_delete_all_versions(trace_server):
    """Test deleting all versions of a dataset (no digests specified)."""
    project_id = f"{TEST_ENTITY}/test_dataset_delete_all"

    # Create multiple versions of the same dataset
    digests = []
    for i in range(3):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="versioned_dataset",
            description=None,
            rows=[{"version": i}],
        )
        create_res = trace_server.dataset_create(create_req)
        digests.append(create_res.digest)

    # Delete all versions (no digests specified)
    delete_req = tsi.DatasetDeleteReq(
        project_id=project_id,
        object_id="versioned_dataset",
        digests=None,
    )
    delete_res = trace_server.dataset_delete(delete_req)

    assert delete_res.num_deleted == 3


def test_dataset_delete_multiple_versions(trace_server):
    """Test deleting multiple specific versions of a dataset."""
    project_id = f"{TEST_ENTITY}/test_dataset_delete_multiple"

    # Create multiple versions
    digests = []
    for i in range(4):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="multi_version_dataset",
            description=None,
            rows=[{"version": i}],
        )
        create_res = trace_server.dataset_create(create_req)
        digests.append(create_res.digest)

    # Delete the first two versions
    delete_req = tsi.DatasetDeleteReq(
        project_id=project_id,
        object_id="multi_version_dataset",
        digests=digests[:2],
    )
    delete_res = trace_server.dataset_delete(delete_req)

    assert delete_res.num_deleted == 2

    # Verify the first two are deleted
    for digest in digests[:2]:
        read_req = tsi.DatasetReadReq(
            project_id=project_id,
            object_id="multi_version_dataset",
            digest=digest,
        )
        with pytest.raises(ObjectDeletedError):
            trace_server.dataset_read(read_req)

    # Verify the last two still exist
    for digest in digests[2:]:
        read_req = tsi.DatasetReadReq(
            project_id=project_id,
            object_id="multi_version_dataset",
            digest=digest,
        )
        read_res = trace_server.dataset_read(read_req)
        assert read_res.digest == digest


def test_dataset_delete_not_found(trace_server):
    """Test deleting a non-existent dataset raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_dataset_delete_not_found"

    delete_req = tsi.DatasetDeleteReq(
        project_id=project_id,
        object_id="nonexistent_dataset",
        digests=["fake_digest"],
    )

    with pytest.raises(NotFoundError):
        trace_server.dataset_delete(delete_req)


def test_dataset_versioning(trace_server):
    """Test that creating multiple versions of a dataset increments version_index."""
    project_id = f"{TEST_ENTITY}/test_dataset_versioning"

    # Create multiple versions of the same dataset
    versions = []
    for i in range(3):
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="versioned_dataset",
            description=f"Version {i}",
            rows=[{"value": i}],
        )
        create_res = trace_server.dataset_create(create_req)
        versions.append(create_res)

    # Verify version indices increment
    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2

    # Verify all versions are distinct
    assert len({v.digest for v in versions}) == 3


def test_dataset_with_special_characters(trace_server):
    """Test creating and reading a dataset with special characters in data."""
    project_id = f"{TEST_ENTITY}/test_dataset_special_chars"

    # Create a dataset with special characters
    rows = [
        {"text": "This has \"quotes\" and 'apostrophes'"},
        {"text": "Line breaks:\n\tand tabs"},
        {"text": "Unicode: 你好世界 🚀"},
    ]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="special_chars",
        description='Dataset with "special" characters',
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    # Read it back and verify metadata is preserved
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="special_chars",
        digest=create_res.digest,
    )
    read_res = trace_server.dataset_read(read_req)

    assert read_res.name == "special_chars"
    assert read_res.description == 'Dataset with "special" characters'
    # The rows should still be a reference
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")


def test_dataset_with_unicode(trace_server):
    """Test creating and reading a dataset with unicode characters."""
    project_id = f"{TEST_ENTITY}/test_dataset_unicode"

    # Create a dataset with unicode
    rows = [
        {"language": "Chinese", "greeting": "你好世界"},
        {"language": "Japanese", "greeting": "こんにちは"},
        {"language": "Emoji", "greeting": "🚀 🌟 ✨"},
    ]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="unicode_dataset",
        description="Unicode greetings 🌍",
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    # Read it back and verify metadata is preserved
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="unicode_dataset",
        digest=create_res.digest,
    )
    read_res = trace_server.dataset_read(read_req)

    assert read_res.name == "unicode_dataset"
    assert read_res.description == "Unicode greetings 🌍"
    assert "🌍" in read_res.description


def test_dataset_list_after_deletion(trace_server):
    """Test that deleted datasets don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_dataset_list_after_deletion"

    # Create three datasets
    dataset_names = ["keep_1", "delete_me", "keep_2"]
    digests = {}
    for name in dataset_names:
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name=name,
            description=None,
            rows=[{"id": 1}],
        )
        create_res = trace_server.dataset_create(create_req)
        digests[name] = create_res.digest

    # Delete one dataset
    delete_req = tsi.DatasetDeleteReq(
        project_id=project_id,
        object_id="delete_me",
        digests=None,
    )
    trace_server.dataset_delete(delete_req)

    # List datasets - should only see the two that weren't deleted
    list_req = tsi.DatasetListReq(project_id=project_id)
    datasets = list(trace_server.dataset_list(list_req))

    dataset_names_returned = {ds.name for ds in datasets}
    assert dataset_names_returned == {"keep_1", "keep_2"}
    assert "delete_me" not in dataset_names_returned


def test_dataset_empty_rows(trace_server):
    """Test creating a dataset with empty rows."""
    project_id = f"{TEST_ENTITY}/test_dataset_empty_rows"

    # Create a dataset with empty rows
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="empty_dataset",
        description="A dataset with no rows",
        rows=[],
    )
    create_res = trace_server.dataset_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "empty_dataset"

    # Read it back
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="empty_dataset",
        digest=create_res.digest,
    )
    read_res = trace_server.dataset_read(read_req)

    assert read_res.name == "empty_dataset"
    assert isinstance(read_res.rows, str)


def test_dataset_large_rows(trace_server):
    """Test creating a dataset with many rows."""
    project_id = f"{TEST_ENTITY}/test_dataset_large_rows"

    # Create a dataset with 100 rows
    rows = [{"id": i, "value": f"value_{i}", "data": i * 2} for i in range(100)]
    create_req = tsi.DatasetCreateReq(
        project_id=project_id,
        name="large_dataset",
        description="A dataset with 100 rows",
        rows=rows,
    )
    create_res = trace_server.dataset_create(create_req)

    assert create_res.digest is not None

    # Read it back
    read_req = tsi.DatasetReadReq(
        project_id=project_id,
        object_id="large_dataset",
        digest=create_res.digest,
    )
    read_res = trace_server.dataset_read(read_req)

    assert read_res.name == "large_dataset"
    # The rows should still be a reference (not the actual 100 rows)
    assert isinstance(read_res.rows, str)
    assert read_res.rows.startswith("weave:///")
