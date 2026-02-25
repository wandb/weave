import hashlib
import json

import pytest

from weave.shared import (
    compute_file_digest,
    compute_object_digest,
    compute_object_digest_result,
    compute_row_digest,
    compute_table_digest,
)
from weave.shared.digest import bytes_digest, str_digest
from weave.shared.object_class_util import process_incoming_object_val

pytestmark = pytest.mark.trace_server


def test_compute_object_digest_matches_server_formula() -> None:
    val = {"a": 1, "nested": {"k": "v"}}
    processed = process_incoming_object_val(val)
    expected = str_digest(json.dumps(processed["val"], sort_keys=True))
    assert compute_object_digest(val) == expected


def test_compute_object_digest_result_has_expected_fields() -> None:
    val = {"a": 1}
    result = compute_object_digest_result(val)
    assert result.processed_val == val
    assert result.json_val == json.dumps(val, sort_keys=True)
    assert result.digest == str_digest(json.dumps(val, sort_keys=True))
    assert result.base_object_class is None
    assert result.leaf_object_class is None


def test_compute_table_digest_matches_server_formula() -> None:
    rows = [{"x": 1}, {"x": 2}]
    expected_row_digests = [str_digest(json.dumps(r, sort_keys=True)) for r in rows]
    table_hasher = hashlib.sha256()
    for row_digest in expected_row_digests:
        table_hasher.update(row_digest.encode())
    expected_table_digest = table_hasher.hexdigest()

    assert [compute_row_digest(r) for r in rows] == expected_row_digests
    assert compute_table_digest(expected_row_digests) == expected_table_digest


def test_compute_file_digest_matches_server_formula() -> None:
    content = b"hello-shared"
    assert compute_file_digest(content) == bytes_digest(content)
