"""Tests for Scorer V2 API endpoints.

Tests verify that the Scorer V2 API correctly creates, reads, lists, and deletes scorer objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_scorer_create_basic(trace_server):
    """Test creating a basic scorer object."""
    project_id = f"{TEST_ENTITY}/test_scorer_create_basic"

    # Create a scorer
    op_source_code = """
def score(output: str, target: str) -> dict:
    return {"correct": output == target}
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="exact_match",
        description="A simple exact match scorer",
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "exact_match"
    assert create_res.version_index == 0
    # Verify scorer returns a reference string
    assert isinstance(create_res.scorer, str)
    assert create_res.scorer.startswith("weave:///")


def test_scorer_create_without_description(trace_server):
    """Test creating a scorer without providing a description."""
    project_id = f"{TEST_ENTITY}/test_scorer_create_no_desc"

    # Create a scorer without description
    op_source_code = """
def score(output: str) -> dict:
    return {"length": len(output)}
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="length_scorer",
        description=None,
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "length_scorer"
    assert create_res.version_index == 0
    assert isinstance(create_res.scorer, str)


def test_scorer_read_basic(trace_server):
    """Test reading a specific scorer object."""
    project_id = f"{TEST_ENTITY}/test_scorer_read_basic"

    # Create a scorer
    op_source_code = """
def score(output: str, target: str) -> dict:
    return {"correct": output.lower() == target.lower()}
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="case_insensitive_match",
        description="Case insensitive match scorer",
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    # Read the scorer back
    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="case_insensitive_match",
        digest=create_res.digest,
    )
    read_res = trace_server.scorer_read(read_req)

    assert read_res.object_id == "case_insensitive_match"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == "case_insensitive_match"
    assert read_res.description == "Case insensitive match scorer"
    assert read_res.created_at is not None
    # Verify score_op is a reference string
    assert isinstance(read_res.score_op, str)
    assert read_res.score_op.startswith("weave:///") or len(read_res.score_op) > 0


def test_scorer_read_not_found(trace_server):
    """Test reading a non-existent scorer raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_scorer_read_not_found"

    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="nonexistent_scorer",
        digest="fake_digest_1234567890",
    )

    with pytest.raises(NotFoundError):
        trace_server.scorer_read(read_req)


def test_scorer_list_basic(trace_server):
    """Test listing all scorers in a project."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_basic"

    # Create multiple scorers
    scorer_names = ["scorer_a", "scorer_b", "scorer_c"]
    for name in scorer_names:
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name=name,
            description=f"Scorer {name}",
            op_source_code=f'def score():\n    return {{"score": "{name}"}}',
        )
        trace_server.scorer_create(create_req)

    # List all scorers
    list_req = tsi.ScorerListReq(project_id=project_id)
    scorers = list(trace_server.scorer_list(list_req))

    assert len(scorers) == 3
    scorer_names_returned = {s.name for s in scorers}
    assert scorer_names_returned == {"scorer_a", "scorer_b", "scorer_c"}

    # Verify all scorers have score_op references
    for scorer in scorers:
        assert scorer.score_op
        assert scorer.created_at is not None


def test_scorer_list_with_limit(trace_server):
    """Test listing scorers with a limit."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_limit"

    # Create multiple scorers
    for i in range(5):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name=f"scorer_{i}",
            description=None,
            op_source_code=f'def score():\n    return {{"value": {i}}}',
        )
        trace_server.scorer_create(create_req)

    # List with a limit
    list_req = tsi.ScorerListReq(project_id=project_id, limit=3)
    scorers = list(trace_server.scorer_list(list_req))

    assert len(scorers) == 3


def test_scorer_list_with_offset(trace_server):
    """Test listing scorers with an offset."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_offset"

    # Create multiple scorers
    for i in range(5):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name=f"scorer_{i}",
            description=None,
            op_source_code=f'def score():\n    return {{"value": {i}}}',
        )
        trace_server.scorer_create(create_req)

    # List with an offset
    list_req = tsi.ScorerListReq(project_id=project_id, offset=2)
    scorers = list(trace_server.scorer_list(list_req))

    assert len(scorers) == 3


def test_scorer_list_with_limit_and_offset(trace_server):
    """Test listing scorers with both limit and offset for pagination."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_pagination"

    # Create multiple scorers
    for i in range(10):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name=f"scorer_{i}",
            description=None,
            op_source_code=f'def score():\n    return {{"value": {i}}}',
        )
        trace_server.scorer_create(create_req)

    # First page
    list_req1 = tsi.ScorerListReq(project_id=project_id, limit=3, offset=0)
    scorers1 = list(trace_server.scorer_list(list_req1))
    assert len(scorers1) == 3

    # Second page
    list_req2 = tsi.ScorerListReq(project_id=project_id, limit=3, offset=3)
    scorers2 = list(trace_server.scorer_list(list_req2))
    assert len(scorers2) == 3

    # Verify different scorers on different pages
    scorers1_names = {s.name for s in scorers1}
    scorers2_names = {s.name for s in scorers2}
    assert len(scorers1_names & scorers2_names) == 0  # No overlap


def test_scorer_list_empty_project(trace_server):
    """Test listing scorers in a project with no scorers."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_empty"

    list_req = tsi.ScorerListReq(project_id=project_id)
    scorers = list(trace_server.scorer_list(list_req))

    assert len(scorers) == 0


def test_scorer_delete_single_version(trace_server):
    """Test deleting a single version of a scorer."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete_single"

    # Create a scorer
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="delete_test",
        description=None,
        op_source_code='def score():\n    return {"score": 1}',
    )
    create_res = trace_server.scorer_create(create_req)

    # Delete the specific version
    delete_req = tsi.ScorerDeleteReq(
        project_id=project_id,
        object_id="delete_test",
        digests=[create_res.digest],
    )
    delete_res = trace_server.scorer_delete(delete_req)

    assert delete_res.num_deleted == 1

    # Verify the scorer is deleted (should raise ObjectDeletedError)
    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="delete_test",
        digest=create_res.digest,
    )
    with pytest.raises(ObjectDeletedError):
        trace_server.scorer_read(read_req)


def test_scorer_delete_all_versions(trace_server):
    """Test deleting all versions of a scorer (no digests specified)."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete_all"

    # Create multiple versions of the same scorer
    digests = []
    for i in range(3):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="versioned_scorer",
            description=None,
            op_source_code=f'def score():\n    return {{"version": {i}}}',
        )
        create_res = trace_server.scorer_create(create_req)
        digests.append(create_res.digest)

    # Delete all versions (no digests specified)
    delete_req = tsi.ScorerDeleteReq(
        project_id=project_id,
        object_id="versioned_scorer",
        digests=None,
    )
    delete_res = trace_server.scorer_delete(delete_req)

    assert delete_res.num_deleted == 3


def test_scorer_delete_multiple_versions(trace_server):
    """Test deleting multiple specific versions of a scorer."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete_multiple"

    # Create multiple versions
    digests = []
    for i in range(4):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="multi_version_scorer",
            description=None,
            op_source_code=f'def score():\n    return {{"version": {i}}}',
        )
        create_res = trace_server.scorer_create(create_req)
        digests.append(create_res.digest)

    # Delete the first two versions
    delete_req = tsi.ScorerDeleteReq(
        project_id=project_id,
        object_id="multi_version_scorer",
        digests=digests[:2],
    )
    delete_res = trace_server.scorer_delete(delete_req)

    assert delete_res.num_deleted == 2

    # Verify the first two are deleted
    for digest in digests[:2]:
        read_req = tsi.ScorerReadReq(
            project_id=project_id,
            object_id="multi_version_scorer",
            digest=digest,
        )
        with pytest.raises(ObjectDeletedError):
            trace_server.scorer_read(read_req)

    # Verify the last two still exist
    for digest in digests[2:]:
        read_req = tsi.ScorerReadReq(
            project_id=project_id,
            object_id="multi_version_scorer",
            digest=digest,
        )
        read_res = trace_server.scorer_read(read_req)
        assert read_res.digest == digest


def test_scorer_delete_not_found(trace_server):
    """Test deleting a non-existent scorer raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete_not_found"

    delete_req = tsi.ScorerDeleteReq(
        project_id=project_id,
        object_id="nonexistent_scorer",
        digests=["fake_digest"],
    )

    with pytest.raises(NotFoundError):
        trace_server.scorer_delete(delete_req)


def test_scorer_versioning(trace_server):
    """Test that creating multiple versions of a scorer increments version_index."""
    project_id = f"{TEST_ENTITY}/test_scorer_versioning"

    # Create multiple versions of the same scorer
    versions = []
    for i in range(3):
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="versioned_scorer",
            description=f"Version {i}",
            op_source_code=f'def score():\n    return {{"version": {i}}}',
        )
        create_res = trace_server.scorer_create(create_req)
        versions.append(create_res)

    # Verify version indices increment
    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2

    # Verify all versions are distinct
    assert len({v.digest for v in versions}) == 3


def test_scorer_with_special_characters(trace_server):
    """Test creating and reading a scorer with special characters in code."""
    project_id = f"{TEST_ENTITY}/test_scorer_special_chars"

    # Create a scorer with special characters
    op_source_code = """
def score(output: str) -> dict:
    '''This scorer has "quotes" and 'apostrophes'.'''
    return {"result": f"Output: {output} with special chars: \\n\\t"}
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="special_chars",
        description='Scorer with "special" characters',
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    # Read it back and verify metadata is preserved
    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="special_chars",
        digest=create_res.digest,
    )
    read_res = trace_server.scorer_read(read_req)

    assert read_res.name == "special_chars"
    assert read_res.description == 'Scorer with "special" characters'
    assert read_res.score_op  # Should have a reference


def test_scorer_with_unicode(trace_server):
    """Test creating and reading a scorer with unicode characters."""
    project_id = f"{TEST_ENTITY}/test_scorer_unicode"

    # Create a scorer with unicode
    op_source_code = """
def score(output: str) -> dict:
    '''This scorer has unicode: 你好世界 🚀'''
    return {"greeting": "你好世界"}
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="unicode_scorer",
        description="Unicode scorer 🌍",
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    # Read it back and verify metadata is preserved
    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="unicode_scorer",
        digest=create_res.digest,
    )
    read_res = trace_server.scorer_read(read_req)

    assert read_res.name == "unicode_scorer"
    assert read_res.description == "Unicode scorer 🌍"
    assert "🌍" in read_res.description


def test_scorer_list_after_deletion(trace_server):
    """Test that deleted scorers don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_after_deletion"

    # Create three scorers
    scorer_names = ["keep_1", "delete_me", "keep_2"]
    digests = {}
    for name in scorer_names:
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name=name,
            description=None,
            op_source_code='def score():\n    return {"score": 1}',
        )
        create_res = trace_server.scorer_create(create_req)
        digests[name] = create_res.digest

    # Delete one scorer
    delete_req = tsi.ScorerDeleteReq(
        project_id=project_id,
        object_id="delete_me",
        digests=None,
    )
    trace_server.scorer_delete(delete_req)

    # List scorers - should only see the two that weren't deleted
    list_req = tsi.ScorerListReq(project_id=project_id)
    scorers = list(trace_server.scorer_list(list_req))

    scorer_names_returned = {s.name for s in scorers}
    assert scorer_names_returned == {"keep_1", "keep_2"}
    assert "delete_me" not in scorer_names_returned


def test_scorer_complex_source_code(trace_server):
    """Test creating a scorer with complex multi-line source code."""
    project_id = f"{TEST_ENTITY}/test_scorer_complex_code"

    # Create a scorer with complex code
    op_source_code = """
import json
from typing import Any

def score(output: str, target: str) -> dict:
    '''
    Complex scoring function with multiple operations.
    '''
    # Parse outputs
    try:
        output_data = json.loads(output)
        target_data = json.loads(target)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "score": 0.0}

    # Calculate similarity
    matches = 0
    total = len(target_data)

    for key, value in target_data.items():
        if key in output_data and output_data[key] == value:
            matches += 1

    score = matches / total if total > 0 else 0.0

    return {
        "score": score,
        "matches": matches,
        "total": total
    }
"""
    create_req = tsi.ScorerCreateReq(
        project_id=project_id,
        name="json_similarity",
        description="Complex JSON similarity scorer",
        op_source_code=op_source_code,
    )
    create_res = trace_server.scorer_create(create_req)

    assert create_res.digest is not None
    assert create_res.object_id == "json_similarity"

    # Read it back
    read_req = tsi.ScorerReadReq(
        project_id=project_id,
        object_id="json_similarity",
        digest=create_res.digest,
    )
    read_res = trace_server.scorer_read(read_req)

    assert read_res.name == "json_similarity"
    assert read_res.description == "Complex JSON similarity scorer"
