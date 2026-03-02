import hashlib
import json

import pytest

from weave.shared import (
    compute_file_digest,
    compute_object_digest,
    compute_object_digest_result,
    compute_object_ref_uri,
    compute_row_digest,
    compute_table_digest,
    compute_table_ref_uri,
)
from weave.shared.digest import bytes_digest, str_digest
from weave.shared.object_class_util import process_incoming_object_val
from weave.shared.refs_internal import (
    WEAVE_INTERNAL_SCHEME,
    InvalidInternalRef,
    parse_internal_uri,
)

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


def test_compute_object_ref_uri() -> None:
    project_id = "internal-proj-abc"
    object_id = "gpt4o-judge"
    val = {
        "model": "gpt-4o",
        "temperature": 0.0,
        "system_prompt": "You are an expert evaluator.",
    }

    uri = compute_object_ref_uri(project_id, object_id, val)

    assert uri.startswith(f"{WEAVE_INTERNAL_SCHEME}:///")
    parsed = parse_internal_uri(uri)
    assert parsed.project_id == project_id
    assert parsed.name == object_id
    assert parsed.version == compute_object_digest(val)


def test_compute_table_ref_uri() -> None:
    project_id = "internal-proj-abc"
    rows = [
        {"input": "What is RAG?", "expected": "Retrieval-augmented generation"},
        {
            "input": "Explain RLHF",
            "expected": "Reinforcement learning from human feedback",
        },
    ]
    row_digests = [compute_row_digest(r) for r in rows]

    uri = compute_table_ref_uri(project_id, row_digests)

    assert uri.startswith(f"{WEAVE_INTERNAL_SCHEME}:///")
    parsed = parse_internal_uri(uri)
    assert parsed.project_id == project_id
    assert parsed.digest == compute_table_digest(row_digests)


def test_compute_object_ref_uri_with_external_to_internal_map() -> None:
    """Demonstrates the minimal contract: resolve external ID, then construct ref."""
    # Simulate the response from project_ids_external_to_internal
    project_id_map = {
        "acme/summarization-eval": "aW50ZXJuYWwtaWQ",  # opaque internal ID
    }

    external_id = "acme/summarization-eval"
    internal_id = project_id_map[external_id]

    val = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "system_prompt": "Summarize the following text concisely.",
    }
    object_id = "summarizer-v2"

    uri = compute_object_ref_uri(internal_id, object_id, val)

    expected_digest = compute_object_digest(val)
    assert (
        uri
        == f"{WEAVE_INTERNAL_SCHEME}:///{internal_id}/object/{object_id}:{expected_digest}"
    )


def test_compute_object_ref_uri_stable_across_key_order() -> None:
    """Dict insertion order must not affect the ref URI."""
    val_a = {"model": "gpt-4o", "temperature": 0.7, "top_p": 0.9}
    val_b = {"top_p": 0.9, "model": "gpt-4o", "temperature": 0.7}

    uri_a = compute_object_ref_uri("proj123", "chat-config", val_a)
    uri_b = compute_object_ref_uri("proj123", "chat-config", val_b)

    assert uri_a == uri_b


def test_compute_table_ref_uri_sensitive_to_row_order() -> None:
    """Reordering rows must produce a different table ref."""
    rows = [
        {"prompt": "Hello", "completion": "Hi there"},
        {"prompt": "Bye", "completion": "Goodbye"},
    ]
    digests_forward = [compute_row_digest(r) for r in rows]
    digests_reversed = [compute_row_digest(r) for r in reversed(rows)]

    uri_forward = compute_table_ref_uri("proj123", digests_forward)
    uri_reversed = compute_table_ref_uri("proj123", digests_reversed)

    assert uri_forward != uri_reversed


@pytest.mark.parametrize(
    ("project_id", "object_id", "match"),
    [
        ("entity/project", "my-scorer", "project_id.*cannot contain '/'"),
        ("proj123", "bad:name", "name.*cannot contain ':'"),
    ],
    ids=["slash-in-project-id", "colon-in-object-id"],
)
def test_compute_object_ref_uri_rejects_invalid_names(
    project_id: str, object_id: str, match: str
) -> None:
    with pytest.raises(InvalidInternalRef, match=match):
        compute_object_ref_uri(project_id, object_id, {"model": "gpt-4o"})
