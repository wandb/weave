"""Tests for Scorer V2 API endpoints.

Tests verify that the Scorer V2 API correctly creates, reads, lists, and deletes scorer objects.
"""

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError


@pytest.mark.parametrize(
    ("object_id", "description", "op_source_code"),
    [
        (
            "exact_match",
            "A simple exact match scorer",
            'def score(output: str, target: str) -> dict:\n    return {"correct": output == target}',
        ),
        (
            "length_scorer",
            None,
            'def score(output: str) -> dict:\n    return {"length": len(output)}',
        ),
        (
            "json_similarity",
            "Complex JSON similarity scorer",
            "import json\nfrom typing import Any\n\n"
            "def score(output: str, target: str) -> dict:\n"
            "    '''Complex scoring function.'''\n"
            "    try:\n"
            "        output_data = json.loads(output)\n"
            "        target_data = json.loads(target)\n"
            "    except json.JSONDecodeError:\n"
            '        return {"error": "Invalid JSON", "score": 0.0}\n'
            "    matches = sum(1 for k, v in target_data.items() if output_data.get(k) == v)\n"
            "    total = len(target_data)\n"
            '    return {"score": matches / total if total else 0.0, "matches": matches, "total": total}',
        ),
    ],
    ids=["basic", "no_description", "complex_source_code"],
)
def test_scorer_create_and_read_round_trip(
    trace_server, object_id, description, op_source_code
):
    """Creating a scorer yields a v0 weave ref and reads back the same metadata."""
    project_id = f"{TEST_ENTITY}/test_scorer_create_{object_id}"
    create_res = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name=object_id,
            description=description,
            op_source_code=op_source_code,
        )
    )
    assert create_res.digest is not None
    assert create_res.object_id == object_id
    assert create_res.version_index == 0
    assert isinstance(create_res.scorer, str)
    assert create_res.scorer.startswith("weave:///")

    read_res = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id, object_id=object_id, digest=create_res.digest
        )
    )
    assert read_res.object_id == object_id
    assert read_res.digest == create_res.digest
    assert read_res.version_index == 0
    assert read_res.name == object_id
    assert read_res.description == description
    assert read_res.created_at is not None
    assert isinstance(read_res.score_op, str)
    assert read_res.score_op


@pytest.mark.parametrize(
    ("object_id", "description", "op_source_code", "expected_substring"),
    [
        (
            "special_chars",
            'Scorer with "special" characters',
            "def score(output: str) -> dict:\n"
            "    '''This scorer has \"quotes\" and 'apostrophes'.'''\n"
            '    return {"result": f"Output: {output} with special chars: \\n\\t"}',
            '"special"',
        ),
        (
            "unicode_scorer",
            "Unicode scorer 🌍",
            "def score(output: str) -> dict:\n"
            "    '''This scorer has unicode: 你好世界 🚀'''\n"
            '    return {"greeting": "你好世界"}',
            "🌍",
        ),
    ],
    ids=["special_characters", "unicode"],
)
def test_scorer_metadata_round_trip_with_exotic_text(
    trace_server, object_id, description, op_source_code, expected_substring
):
    """Special and unicode characters in code/description survive create + read."""
    project_id = f"{TEST_ENTITY}/test_scorer_{object_id}"
    create_res = trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name=object_id,
            description=description,
            op_source_code=op_source_code,
        )
    )
    read_res = trace_server.scorer_read(
        tsi.ScorerReadReq(
            project_id=project_id, object_id=object_id, digest=create_res.digest
        )
    )
    assert read_res.name == object_id
    assert read_res.description == description
    assert read_res.score_op
    assert expected_substring in read_res.description


def test_scorer_read_not_found(trace_server):
    """Reading a non-existent scorer raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_scorer_read_not_found"
    with pytest.raises(NotFoundError):
        trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=project_id,
                object_id="nonexistent_scorer",
                digest="fake_digest_1234567890",
            )
        )


def test_scorer_list_contents_and_pagination(trace_server):
    """List returns full metadata, respects limit/offset, paginates without overlap."""
    project_id = f"{TEST_ENTITY}/test_scorer_list"

    # Empty project lists nothing.
    assert (
        list(trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))) == []
    )

    for i in range(10):
        _create_scorer(trace_server, project_id, f"scorer_{i}")

    all_scorers = list(
        trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id))
    )
    assert len(all_scorers) == 10
    assert {s.name for s in all_scorers} == {f"scorer_{i}" for i in range(10)}
    for scorer in all_scorers:
        assert scorer.score_op
        assert scorer.created_at is not None

    assert (
        len(
            list(
                trace_server.scorer_list(
                    tsi.ScorerListReq(project_id=project_id, limit=3)
                )
            )
        )
        == 3
    )
    assert (
        len(
            list(
                trace_server.scorer_list(
                    tsi.ScorerListReq(project_id=project_id, offset=7)
                )
            )
        )
        == 3
    )

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
    assert {s.name for s in page1} & {s.name for s in page2} == set()


def test_scorer_list_excludes_deleted(trace_server):
    """Deleted scorers disappear from list results."""
    project_id = f"{TEST_ENTITY}/test_scorer_list_after_deletion"
    for name in ["keep_1", "delete_me", "keep_2"]:
        _create_scorer(trace_server, project_id, name)

    trace_server.scorer_delete(
        tsi.ScorerDeleteReq(project_id=project_id, object_id="delete_me", digests=None)
    )

    scorers = list(trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id)))
    assert {s.name for s in scorers} == {"keep_1", "keep_2"}


def test_scorer_delete_selective_and_all(trace_server):
    """Deleting specific digests removes only those; ``digests=None`` removes every version."""
    # Selective delete: first two of four versions go, last two remain readable.
    selective_proj = f"{TEST_ENTITY}/test_scorer_delete_multiple"
    digests = [
        _create_scorer(
            trace_server, selective_proj, "multi_version_scorer", f'{{"version": {i}}}'
        ).digest
        for i in range(4)
    ]
    del_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=selective_proj,
            object_id="multi_version_scorer",
            digests=digests[:2],
        )
    )
    assert del_res.num_deleted == 2
    for digest in digests[:2]:
        with pytest.raises(ObjectDeletedError):
            trace_server.scorer_read(
                tsi.ScorerReadReq(
                    project_id=selective_proj,
                    object_id="multi_version_scorer",
                    digest=digest,
                )
            )
    for digest in digests[2:]:
        read_res = trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=selective_proj,
                object_id="multi_version_scorer",
                digest=digest,
            )
        )
        assert read_res.digest == digest

    # Delete-all: a single version, then a multi-version object.
    single_proj = f"{TEST_ENTITY}/test_scorer_delete_single"
    single_digest = _create_scorer(trace_server, single_proj, "delete_test").digest
    single_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=single_proj, object_id="delete_test", digests=[single_digest]
        )
    )
    assert single_res.num_deleted == 1
    with pytest.raises(ObjectDeletedError):
        trace_server.scorer_read(
            tsi.ScorerReadReq(
                project_id=single_proj, object_id="delete_test", digest=single_digest
            )
        )

    all_proj = f"{TEST_ENTITY}/test_scorer_delete_all"
    for i in range(3):
        _create_scorer(
            trace_server, all_proj, "versioned_scorer", f'{{"version": {i}}}'
        )
    all_res = trace_server.scorer_delete(
        tsi.ScorerDeleteReq(
            project_id=all_proj, object_id="versioned_scorer", digests=None
        )
    )
    assert all_res.num_deleted == 3


def test_scorer_delete_not_found(trace_server):
    """Deleting a non-existent scorer raises NotFoundError."""
    project_id = f"{TEST_ENTITY}/test_scorer_delete_not_found"
    with pytest.raises(NotFoundError):
        trace_server.scorer_delete(
            tsi.ScorerDeleteReq(
                project_id=project_id,
                object_id="nonexistent_scorer",
                digests=["fake_digest"],
            )
        )


def test_scorer_versioning(trace_server):
    """Creating multiple versions of a scorer increments version_index with distinct digests."""
    project_id = f"{TEST_ENTITY}/test_scorer_versioning"
    versions = [
        _create_scorer(
            trace_server,
            project_id,
            "versioned_scorer",
            f'{{"version": {i}}}',
            f"Version {i}",
        )
        for i in range(3)
    ]
    assert [v.version_index for v in versions] == [0, 1, 2]
    assert len({v.digest for v in versions}) == 3


def test_scorer_list_with_missing_name_in_val(trace_server):
    """Regression test: scorer_list should not crash when val has no 'name' key.

    Previously, the ClickHouse implementation would pass name=None to
    ScorerReadRes, causing a pydantic ValidationError. It should fall
    back to using object_id as the name.
    """
    project_id = f"{TEST_ENTITY}/test_scorer_list_missing_name"
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
    scorers = list(trace_server.scorer_list(tsi.ScorerListReq(project_id=project_id)))
    assert len(scorers) == 1
    assert scorers[0].name == "nameless_scorer"
    assert scorers[0].object_id == "nameless_scorer"


def _create_scorer(
    trace_server,
    project_id: str,
    name: str,
    body: str = '{"score": 1}',
    description: str | None = None,
) -> tsi.ScorerCreateRes:
    """Create a minimal scorer whose `score` returns `body`; returns the create response."""
    return trace_server.scorer_create(
        tsi.ScorerCreateReq(
            project_id=project_id,
            name=name,
            description=description,
            op_source_code=f"def score():\n    return {body}",
        )
    )
