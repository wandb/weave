"""Tests for server-side digest validation.

Exercises validate_expected_digest and the expected_digest fields on requests
that support it: FileCreateReq, ObjCreateReq, and TableCreateReq.
"""

from __future__ import annotations

import pytest

from weave.shared.digest import compute_file_digest
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import DigestMismatchError
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
)


def test_validate_expected_digest() -> None:
    """Matching/None digests pass; mismatches raise DigestMismatchError."""
    validate_expected_digest(expected="abc123", actual="abc123", label="test")
    validate_expected_digest(expected=None, actual="abc123", label="test")
    with pytest.raises(DigestMismatchError, match="(?i)client.*!=.*server"):
        validate_expected_digest(expected="wrong", actual="abc123", label="test")


@pytest.mark.trace_server
def test_file_create_expected_digest(client) -> None:
    """file_create: fallback (none) and correct digests succeed, wrong raises."""
    content = b"hello world"
    no_digest = client.server.file_create(
        FileCreateReq(project_id=client.project_id, name="test.txt", content=content)
    )
    assert no_digest.digest is not None

    digest = compute_file_digest(content)
    correct = client.server.file_create(
        FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=content,
            expected_digest=digest,
        )
    )
    assert correct.digest == digest

    with pytest.raises(DigestMismatchError):
        client.server.file_create(
            FileCreateReq(
                project_id=client.project_id,
                name="test.txt",
                content=content,
                expected_digest="wrong_digest",
            )
        )


@pytest.mark.trace_server
def test_obj_create_expected_digest(client) -> None:
    """obj_create: fallback (none) succeeds, wrong digest raises."""
    no_digest = client.server.obj_create(
        ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=client.project_id,
                object_id="test_obj",
                val={"key": "value"},
            )
        )
    )
    assert no_digest.digest is not None

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


@pytest.mark.trace_server
def test_table_create_expected_digest(client) -> None:
    """table_create: fallback (none) succeeds, wrong digest raises."""
    rows = [{"val": {"a": 1}}, {"val": {"a": 2}}]
    no_digest = client.server.table_create(
        TableCreateReq(
            table=TableSchemaForInsert(project_id=client.project_id, rows=rows)
        )
    )
    assert no_digest.digest is not None

    with pytest.raises(DigestMismatchError):
        client.server.table_create(
            TableCreateReq(
                table=TableSchemaForInsert(
                    project_id=client.project_id,
                    rows=rows,
                    expected_digest="wrong_digest",
                )
            )
        )
