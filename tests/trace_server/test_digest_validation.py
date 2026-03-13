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
    with pytest.raises(DigestMismatchError, match="client.*!=.*server"):
        validate_expected_digest(expected="wrong", actual="abc123", label="test")


@pytest.mark.trace_server
class TestFileCreateExpectedDigest:
    def test_no_expected_digest(self, client) -> None:
        """file_create without expected_digest succeeds (fallback path)."""
        req = FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=b"hello world",
        )
        res = client.server.file_create(req)
        assert res.digest is not None

    def test_correct_expected_digest(self, client) -> None:
        """file_create with correct expected_digest succeeds."""
        from weave.trace_server.sqlite_trace_server import compute_file_digest

        content = b"hello world"
        digest = compute_file_digest(content)
        req = FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=content,
            expected_digest=digest,
        )
        res = client.server.file_create(req)
        assert res.digest == digest

    def test_wrong_expected_digest(self, client) -> None:
        """file_create with wrong expected_digest raises DigestMismatchError."""
        req = FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=b"hello world",
            expected_digest="wrong_digest",
        )
        with pytest.raises(DigestMismatchError):
            client.server.file_create(req)


@pytest.mark.trace_server
class TestObjCreateExpectedDigest:
    def test_no_expected_digest(self, client) -> None:
        """obj_create without expected_digest succeeds (fallback path)."""
        req = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=client._project_id(),
                object_id="test_obj",
                val={"key": "value"},
            )
        )
        res = client.server.obj_create(req)
        assert res.digest is not None

    def test_wrong_expected_digest(self, client) -> None:
        """obj_create with wrong expected_digest raises DigestMismatchError."""
        req = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=client._project_id(),
                object_id="test_obj",
                val={"key": "value"},
                expected_digest="wrong_digest",
            )
        )
        with pytest.raises(DigestMismatchError):
            client.server.obj_create(req)


@pytest.mark.trace_server
class TestTableCreateExpectedDigest:
    def test_no_expected_digest(self, client) -> None:
        """table_create without expected_digest succeeds (fallback path)."""
        req = TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client._project_id(),
                rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
            )
        )
        res = client.server.table_create(req)
        assert res.digest is not None

    def test_wrong_expected_digest(self, client) -> None:
        """table_create with wrong expected_digest raises DigestMismatchError."""
        req = TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client._project_id(),
                rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
                expected_digest="wrong_digest",
            )
        )
        with pytest.raises(DigestMismatchError):
            client.server.table_create(req)
