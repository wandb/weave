"""Tests for server-side digest validation.

Exercises validate_expected_digest and the expected_digest fields on requests
that support it: FileCreateReq, ObjCreateReq, and TableCreateReq.
"""

from __future__ import annotations

import json
from enum import IntEnum

import pytest

from weave.shared.digest import (
    canonical_json,
    compute_file_digest,
    compute_object_digest,
    compute_row_digest,
)
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import DigestMismatchError
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
)


@pytest.mark.parametrize(
    "val",
    [
        {"label_map": {1: "neg", 2: "neu", 10: "pos"}},
        {"cfg": {"thresholds": {10: 0.1, 2: 0.2, 30: 0.3}}},
        {"flags": {True: "on", False: "off"}},
    ],
    ids=["int_keys", "nested_int_keys", "bool_keys"],
)
def test_object_digest_stable_across_json_roundtrip(val: dict) -> None:
    """The client hashes the in-memory val; the server hashes it after it
    round-trips through JSON over the wire, which turns non-string dict keys
    into strings before sort_keys orders them. The digest must be identical
    both ways, otherwise the client-side fast path 409s.
    """
    wire_val = json.loads(json.dumps(val))
    assert compute_object_digest(val) == compute_object_digest(wire_val)


def test_row_digest_stable_across_json_roundtrip() -> None:
    """Same invariant for table row digests (non-string keys in a row)."""
    row = {"weights": {1: 0.5, 2: 0.3, 10: 0.2}}
    assert compute_row_digest(row) == compute_row_digest(json.loads(json.dumps(row)))


class _Label(IntEnum):
    NEG = 0
    POS = 1


@pytest.mark.parametrize(
    "val",
    [
        {"floats": {"a": 1.5, "b": float("nan"), "c": float("inf")}},
        {"unicode": {"emoji": "😀", "esc": 'a"b\\c'}},
        {"nested": [{"x": 1}, {"y": [{"z": 2}]}]},
        {"enum_val": {"score": _Label.POS}},
        {"label_map": {1: "neg", 2: "neu", 10: "pos"}},
        {"mixed": {1: "a", "b": 2}},
        {"collision": {1: "a", "1": "b"}},
        {"bools": {True: "on", False: "off"}},
    ],
    ids=[
        "floats",
        "unicode",
        "nested",
        "enum_value",
        "int_keys",
        "mixed_keys",
        "key_collision",
        "bool_keys",
    ],
)
def test_canonical_json_matches_full_roundtrip(val: dict) -> None:
    """The gated fast path must be byte-identical to the unconditional
    dumps->loads->dumps round-trip for every payload, whether or not it has
    non-string dict keys. Any divergence is a silent digest mismatch.
    """
    assert canonical_json(val) == json.dumps(
        json.loads(json.dumps(val)), sort_keys=True
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


@pytest.mark.trace_server
class TestFileCreateExpectedDigest:
    def test_no_expected_digest(self, client) -> None:
        """file_create without expected_digest succeeds (fallback path)."""
        req = FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=b"hello world",
        )
        res = client.server.file_create(req)
        assert res.digest is not None

    def test_correct_expected_digest(self, client) -> None:
        """file_create with correct expected_digest succeeds."""
        content = b"hello world"
        digest = compute_file_digest(content)
        req = FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=content,
            expected_digest=digest,
        )
        res = client.server.file_create(req)
        assert res.digest == digest

    def test_wrong_expected_digest(self, client) -> None:
        """file_create with wrong expected_digest raises DigestMismatchError."""
        req = FileCreateReq(
            project_id=client.project_id,
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
                project_id=client.project_id,
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
                project_id=client.project_id,
                object_id="test_obj",
                val={"key": "value"},
                expected_digest="wrong_digest",
            )
        )
        with pytest.raises(DigestMismatchError):
            client.server.obj_create(req)

    def test_client_digest_with_nonstring_keys(self, client) -> None:
        """A client computes expected_digest over native (int) dict keys; the
        server receives the JSON-serialized val (string keys) and must still
        accept it rather than raising a 409 DigestMismatchError.
        """
        val = {"label_map": {1: "neg", 2: "neu", 10: "pos"}}
        expected_digest = compute_object_digest(val)
        wire_val = json.loads(json.dumps(val))
        req = ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=client.project_id,
                object_id="scorer_obj",
                val=wire_val,
                expected_digest=expected_digest,
            )
        )
        res = client.server.obj_create(req)
        assert res.digest == expected_digest


@pytest.mark.trace_server
class TestTableCreateExpectedDigest:
    def test_no_expected_digest(self, client) -> None:
        """table_create without expected_digest succeeds (fallback path)."""
        req = TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client.project_id,
                rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
            )
        )
        res = client.server.table_create(req)
        assert res.digest is not None

    def test_wrong_expected_digest(self, client) -> None:
        """table_create with wrong expected_digest raises DigestMismatchError."""
        req = TableCreateReq(
            table=TableSchemaForInsert(
                project_id=client.project_id,
                rows=[{"val": {"a": 1}}, {"val": {"a": 2}}],
                expected_digest="wrong_digest",
            )
        )
        with pytest.raises(DigestMismatchError):
            client.server.table_create(req)
