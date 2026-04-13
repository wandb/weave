"""Tests for server-side digest validation.

Exercises validate_expected_digest and the expected_digest fields on requests
that support it: FileCreateReq, ObjCreateReq, and TableCreateReq.
"""

from __future__ import annotations

import pytest

from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import DigestMismatchError
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
)


def test_validate_expected_digest_match() -> None:
    """No error when expected matches actual."""
    validate_expected_digest(expected="abc123", actual="abc123", label="test")


def test_validate_expected_digest_none_skips() -> None:
    """None expected (fallback path) never raises."""
    validate_expected_digest(expected=None, actual="abc123", label="test")


def test_validate_expected_digest_mismatch_raises() -> None:
    """Mismatched digests raise DigestMismatchError."""
    with pytest.raises(DigestMismatchError, match="(?i)client.*!=.*server"):
        validate_expected_digest(expected="wrong", actual="abc123", label="test")


def test_expected_digest_on_create_endpoints(client) -> None:
    """Test expected_digest validation on file_create, obj_create, and table_create."""
    from weave.trace_server.sqlite_trace_server import compute_file_digest

    # --- FileCreateReq ---
    # No expected_digest (fallback path)
    res = client.server.file_create(
        FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=b"hello world",
        )
    )
    assert res.digest is not None

    # Correct expected_digest
    content = b"hello world"
    digest = compute_file_digest(content)
    res = client.server.file_create(
        FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=content,
            expected_digest=digest,
        )
    )
    assert res.digest == digest

    # Wrong expected_digest
    with pytest.raises(DigestMismatchError):
        client.server.file_create(
            FileCreateReq(
                project_id=client.project_id,
                name="test.txt",
                content=b"hello world",
                expected_digest="wrong_digest",
            )
        )

    # --- ObjCreateReq ---
    # No expected_digest
    res = client.server.obj_create(
        ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=client.project_id,
                object_id="test_obj",
                val={"key": "value"},
            )
        )
    )
    assert res.digest is not None

    # Wrong expected_digest
    with pytest.raises(DigestMismatchError):
        client.server.obj_create(
            ObjCreateReq(
                obj=ObjSchemaForInsert(
                    project_id=client.project_id,
                    object_id="test_obj",
                    val={"key": "value"},
                    expected_digest="wrong_digest",
                )
            )
        )

    # --- TableCreateReq ---
    # No expected_digest
    res = client.server.table_create(
        TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client.project_id,
                rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
            )
        )
    )
    assert res.digest is not None

    # Wrong expected_digest
    with pytest.raises(DigestMismatchError):
        client.server.table_create(
            TableCreateReq(
                table=TableSchemaForInsert(
                    project_id=client.project_id,
                    rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
                    expected_digest="wrong_digest",
                )
            )
        )
