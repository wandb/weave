"""Tests for Scorer V2 API endpoints.

Tests verify that the Scorer V2 API correctly creates, reads, lists, and deletes scorer objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


def test_scorer_create_and_read(trace_server):
    """Test creating scorers (with and without description) and reading them back."""
    project_id = f"{TEST_ENTITY}/test_scorer_create_and_read"

    # Create with description
    op_source_code = """
def score(output: str, target: str) -> dict:
    return {"correct": output.lower() == target.lower()}
"""
    create_res = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="case_insensitive_match",
            description="Case insensitive match scorer",
            op_source_code=op_source_code,
        )
    )
    assert create_res.digest is not None
    assert create_res.object_id == "case_insensitive_match"
    assert create_res.version_index == 0
    assert isinstance(create_res.scorer, str)
    assert create_res.scorer.startswith("weave:///")

    # Read it back
    read_res = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id,
            object_id="case_insensitive_match",
            digest=create_res.digest,
        )
    )
    assert read_res.object_id == "case_insensitive_match"
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == "case_insensitive_match"
    assert read_res.description == "Case insensitive match scorer"
    assert read_res.created_at is not None
    assert isinstance(read_res.score_op, str)
    assert read_res.score_op.startswith("weave:///") or len(read_res.score_op) > 0

    # Create without description
    create_res2 = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="length_scorer",
            description=None,
            op_source_code='def score(output: str) -> dict:\n    return {"length": len(output)}',
        )
    )
    assert create_res2.digest is not None
    assert create_res2.object_id == "length_scorer"
    assert isinstance(create_res2.scorer, str)

    # Read not found
    with pytest.raises(NotFoundError):
        trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=project_id,
                object_id="nonexistent_scorer",
                digest="fake_digest_1234567890",
            )
        )


def test_scorer_list_and_pagination(trace_server):
    """Test listing scorers with limit, offset, and empty project."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_pagination"

    # Empty project
    scorers = list(
        trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))
    )
    assert len(scorers) == 0

    # Create 10 scorers
    for i in range(10):
        trace_server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name=f"scorer_{i}",
                description=None,
                op_source_code=f'def score():\n    return {{"value": {i}}}',
            )
        )

    # List all
    scorers = list(
        trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))
    )
    assert len(scorers) == 10
    for scorer in scorers:
        assert scorer.score_op
        assert scorer.created_at is not None

    # Limit
    scorers = list(
        trace_server.scorer_list(
            tsi.ScorerListReq(project_id=project_id, limit=3)
        )
    )
    assert len(scorers) == 3

    # Offset
    scorers = list(
        trace_server.scorer_list(
            tsi.ScorerListReq(project_id=project_id, offset=7)
        )
    )
    assert len(scorers) == 3

    # Limit + offset pagination
    page1 = list(
        trace_server.scorer_list(
            tsi.ScorerListReq(project_id=project_id, limit=3, offset=0)
        )
    )
    page2 = list(
        trace_server.scorer_list(
            tsi.ScorerListReq(project_id=project_id, limit=3, offset=3)
        )
    )
    assert len(page1) == 3
    assert len(page2) == 3
    page1_names = {s.name for s in page1}
    page2_names = {s.name for s in page2}
    assert len(page1_names & page2_names) == 0


def test_scorer_versioning(trace_server):
    """Test version_index increments and all versions are distinct."""
    project_id = f"{TEST_ENTITY}/test_scorer_versioning"

    versions = []
    for i in range(3):
        create_res = trace_server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="versioned_scorer",
                description=f"Version {i}",
                op_source_code=f'def score():\n    return {{"version": {i}}}',
            )
        )
        versions.append(create_res)

    assert versions[0].version_index == 0
    assert versions[1].version_index == 1
    assert versions[2].version_index == 2
    assert len({v.digest for v in versions}) == 3


def test_scorer_delete(trace_server):
    """Test deleting scorers: single version, all versions, multiple versions, not found."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete"

    # Delete single version
    create_res = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="delete_single",
            description=None,
            op_source_code='def score():\n    return {"score": 1}',
        )
    )
    delete_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=project_id,
            object_id="delete_single",
            digests=[create_res.digest],
        )
    )
    assert delete_res.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=project_id,
                object_id="delete_single",
                digest=create_res.digest,
            )
        )

    # Delete all versions
    digests = []
    for i in range(3):
        res = trace_server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="delete_all",
                description=None,
                op_source_code=f'def score():\n    return {{"version": {i}}}',
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=project_id, object_id="delete_all", digests=None
        )
    )
    assert delete_res.num_deleted == 3

    # Delete multiple specific versions (keep some)
    digests = []
    for i in range(4):
        res = trace_server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="delete_multi",
                description=None,
                op_source_code=f'def score():\n    return {{"version": {i}}}',
            )
        )
        digests.append(res.digest)
    delete_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=project_id,
            object_id="delete_multi",
            digests=digests[:2],
        )
    )
    assert delete_res.num_deleted == 2
    for digest in digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.scorer_read(
                tsi.ScorerReadReq(
                    project_id=project_id,
                    object_id="delete_multi",
                    digest=digest,
                )
            )
    for digest in digests[2:]:
        read_res = trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=project_id,
                object_id="delete_multi",
                digest=digest,
            )
        )
        assert read_res.digest == digest

    # Delete not found
    with pytest.raises(NotFoundError):
        trace_server.scorer_delete(
            tsi.ScorerDeleteReq(
                project_id=project_id,
                object_id="nonexistent_scorer",
                digests=["fake_digest"],
            )
        )


def test_scorer_list_after_deletion(trace_server):
    """Test that deleted scorers don't appear in list results."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_after_deletion"

    scorer_names = ["keep_1", "delete_me", "keep_2"]
    for name in scorer_names:
        trace_server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name=name,
                description=None,
                op_source_code='def score():\n    return {"score": 1}',
            )
        )

    trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=project_id, object_id="delete_me", digests=None
        )
    )

    scorers = list(
        trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))
    )
    scorer_names_returned = {s.name for s in scorers}
    assert scorer_names_returned == {"keep_1", "keep_2"}


def test_scorer_special_characters_and_complex_code(trace_server):
    """Test scorers with special characters, unicode, and complex source code."""
    project_id = f"{TEST_ENTITY}/test_scorer_special_chars"

    # Special characters
    create_res = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="special_chars",
            description='Scorer with "special" characters',
            op_source_code="""
def score(output: str) -> dict:
    '''This scorer has "quotes" and 'apostrophes'.'''
    return {"result": f"Output: {output} with special chars: \\n\\t"}
""",
        )
    )
    read_res = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id,
            object_id="special_chars",
            digest=create_res.digest,
        )
    )
    assert read_res.name == "special_chars"
    assert read_res.description == 'Scorer with "special" characters'
    assert read_res.score_op

    # Unicode
    create_res2 = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="unicode_scorer",
            description="Unicode scorer 🌍",
            op_source_code="""
def score(output: str) -> dict:
    '''This scorer has unicode: 你好世界 🚀'''
    return {"greeting": "你好世界"}
""",
        )
    )
    read_res2 = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id,
            object_id="unicode_scorer",
            digest=create_res2.digest,
        )
    )
    assert read_res2.name == "unicode_scorer"
    assert "🌍" in read_res2.description

    # Complex multi-line code
    complex_code = """
import json
from typing import Any

def score(output: str, target: str) -> dict:
    '''
    Complex scoring function with multiple operations.
    '''
    try:
        output_data = json.loads(output)
        target_data = json.loads(target)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "score": 0.0}

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
    create_res3 = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name="json_similarity",
            description="Complex JSON similarity scorer",
            op_source_code=complex_code,
        )
    )
    assert create_res3.digest is not None
    read_res3 = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id,
            object_id="json_similarity",
            digest=create_res3.digest,
        )
    )
    assert read_res3.name == "json_similarity"
    assert read_res3.description == "Complex JSON similarity scorer"


def test_scorer_list_with_missing_name_in_val(trace_server):
    """Regression test: scorer_list should not crash when val has no 'name' key.

    Previously, the ClickHouse implementation would pass name=None to
    ScorerReadRes, causing a pydantic ValidationError. It should fall
    back to using object_id as the name.
    """
    project_id = f"{TEST_ENTITY}/test_scorer_list_missing_name"

    # Directly create a Scorer object whose val dict has no "name" key.
    trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="nameless_scorer",
                val={
                    "_type": "Scorer",
                    "_class_name": "Scorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                    "description": "A scorer with no name in val",
                    "score": "",
                },
                set_base_object_class="Scorer",
            )
        )
    )

    scorers = list(
        trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))
    )
    assert len(scorers) == 1
    assert scorers[0].name == "nameless_scorer"
    assert scorers[0].object_id == "nameless_scorer"
