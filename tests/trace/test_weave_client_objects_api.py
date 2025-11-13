"""Tests for WeaveClient Objects API mixin methods.

Tests verify that the mixin methods correctly delegate to the underlying server
and provide a convenient interface for users.
"""

from __future__ import annotations

from weave.trace.weave_client import WeaveClient


def test_dataset_create_via_client(client: WeaveClient):
    """Test creating a dataset through the WeaveClient mixin method."""
    # Create a dataset using the mixin method
    rows = [
        {"input": "hello", "output": "world"},
        {"input": "foo", "output": "bar"},
    ]
    result = client.create_dataset(
        name="test_dataset",
        rows=rows,
        description="Test dataset",
    )

    # Verify the response
    assert result.digest is not None
    assert result.object_id == "test_dataset"
    assert result.version_index == 0


def test_dataset_get_via_client(client: WeaveClient):
    """Test reading a dataset through the WeaveClient mixin method."""
    # Create a dataset first
    rows = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    create_result = client.create_dataset(
        name="test_get_dataset",
        rows=rows,
    )

    # Read it back using the mixin method
    dataset = client.get_dataset("test_get_dataset", digest="latest")

    # Verify the response
    assert dataset.object_id == "test_get_dataset"
    assert dataset.digest == create_result.digest
    assert dataset.version_index == 0
    assert isinstance(dataset.rows, str)
    assert dataset.rows.startswith("weave:///")


def test_dataset_list_via_client(client: WeaveClient):
    """Test listing datasets through the WeaveClient mixin method."""
    # Create a few datasets
    for i in range(3):
        client.create_dataset(
            name=f"test_list_dataset_{i}",
            rows=[{"index": i}],
        )

    # List them using the mixin method
    datasets = list(client.list_datasets())

    # Verify we got our datasets
    assert len(datasets) >= 3
    dataset_names = [d.name for d in datasets]
    for i in range(3):
        assert f"test_list_dataset_{i}" in dataset_names


def test_dataset_delete_via_client(client: WeaveClient):
    """Test deleting a dataset through the WeaveClient mixin method."""
    # Create a dataset
    client.create_dataset(
        name="test_delete_dataset",
        rows=[{"data": "to_delete"}],
    )

    # Delete it using the mixin method
    result = client.delete_dataset("test_delete_dataset")

    # Verify deletion
    assert result.num_deleted == 1


def test_op_create_via_client(client: WeaveClient):
    """Test creating an op through the WeaveClient mixin method."""
    source_code = """
def my_function(x: int) -> int:
    return x * 2
"""
    result = client.create_op(
        name="test_op",
        source_code=source_code,
    )

    # Verify the response
    assert result.digest is not None
    assert result.object_id == "test_op"
    assert result.version_index == 0


def test_op_get_via_client(client: WeaveClient):
    """Test reading an op through the WeaveClient mixin method."""
    # Create an op first
    source_code = "def func(): pass"
    create_result = client.create_op(
        name="test_get_op",
        source_code=source_code,
    )

    # Read it back using the mixin method
    op = client.get_op("test_get_op", digest="latest")

    # Verify the response
    assert op.object_id == "test_get_op"
    assert op.digest == create_result.digest
    assert op.version_index == 0
    assert isinstance(op.code, str)


def test_op_list_via_client(client: WeaveClient):
    """Test listing ops through the WeaveClient mixin method."""
    # Create a few ops
    for i in range(3):
        client.create_op(
            name=f"test_list_op_{i}",
            source_code=f"def op_{i}(): pass",
        )

    # List them using the mixin method
    ops = list(client.list_ops())

    # Verify we got our ops
    assert len(ops) >= 3


def test_op_delete_via_client(client: WeaveClient):
    """Test deleting an op through the WeaveClient mixin method."""
    # Create an op
    client.create_op(
        name="test_delete_op",
        source_code="def to_delete(): pass",
    )

    # Delete it using the mixin method
    result = client.delete_op("test_delete_op")

    # Verify deletion
    assert result.num_deleted == 1


def test_scorer_create_via_client(client: WeaveClient):
    """Test creating a scorer through the WeaveClient mixin method."""
    op_source_code = """
def score(output: str, target: str) -> dict:
    return {"exact_match": output == target}
"""
    result = client.create_scorer(
        name="test_scorer",
        op_source_code=op_source_code,
        description="Test scorer",
    )

    # Verify the response
    assert result.digest is not None
    assert result.object_id == "test_scorer"
    assert result.version_index == 0
    assert result.scorer is not None


def test_scorer_get_via_client(client: WeaveClient):
    """Test reading a scorer through the WeaveClient mixin method."""
    # Create a scorer first
    op_source_code = "def score(): pass"
    create_result = client.create_scorer(
        name="test_get_scorer",
        op_source_code=op_source_code,
    )

    # Read it back using the mixin method
    scorer = client.get_scorer("test_get_scorer", digest="latest")

    # Verify the response
    assert scorer.object_id == "test_get_scorer"
    assert scorer.digest == create_result.digest
    assert scorer.version_index == 0
    assert scorer.name == "test_get_scorer"


def test_scorer_list_via_client(client: WeaveClient):
    """Test listing scorers through the WeaveClient mixin method."""
    # Create a few scorers
    for i in range(3):
        client.create_scorer(
            name=f"test_list_scorer_{i}",
            op_source_code=f"def score_{i}(): pass",
        )

    # List them using the mixin method
    scorers = list(client.list_scorers())

    # Verify we got our scorers
    assert len(scorers) >= 3
    scorer_names = [s.name for s in scorers]
    for i in range(3):
        assert f"test_list_scorer_{i}" in scorer_names


def test_scorer_delete_via_client(client: WeaveClient):
    """Test deleting a scorer through the WeaveClient mixin method."""
    # Create a scorer
    client.create_scorer(
        name="test_delete_scorer",
        op_source_code="def score(): pass",
    )

    # Delete it using the mixin method
    result = client.delete_scorer("test_delete_scorer")

    # Verify deletion
    assert result.num_deleted == 1


def test_dataset_create_without_name(client: WeaveClient):
    """Test creating a dataset without a name."""
    rows = [{"a": 1}]
    result = client.create_dataset(rows=rows)

    # Should still work, even without a name
    assert result.digest is not None
    assert result.version_index == 0


def test_op_create_without_name(client: WeaveClient):
    """Test creating an op without a name."""
    source_code = "def anonymous(): pass"
    result = client.create_op(source_code=source_code)

    # Should still work, even without a name
    assert result.digest is not None
    assert result.version_index == 0
