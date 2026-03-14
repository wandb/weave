import hashlib
import json

import pytest

from weave.shared import (
    compute_file_content_ref_uri,
    compute_file_digest,
    compute_object_digest,
    compute_object_digest_result,
    compute_object_ref_uri,
    compute_op_ref_uri,
    compute_row_digest,
    compute_table_digest,
    compute_table_ref_uri,
)
from weave.shared.digest import bytes_digest, str_digest
from weave.shared.object_class_util import process_incoming_object_val
from weave.shared.refs_internal import (
    WEAVE_INTERNAL_SCHEME,
    InternalObjectRef,
    InternalOpRef,
    InternalTableRef,
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


# --- Object ref with extras ---


def test_compute_object_ref_uri_with_attr_extra() -> None:
    """Object ref with an attr extra path (e.g. accessing a nested field)."""
    val = {
        "model": "gpt-4o",
        "prompt_template": "Translate {text} to {lang}.",
    }
    uri = compute_object_ref_uri(
        "proj123", "translator", val, extra=["attr", "prompt_template"]
    )

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalObjectRef)
    assert parsed.extra == ["attr", "prompt_template"]
    assert "/attr/prompt_template" in uri


def test_compute_object_ref_uri_with_dataset_row_extra() -> None:
    """Dataset row ref: object ref + attr/rows/id/<row_digest>."""
    dataset_val = {"description": "QA pairs for eval"}
    row = {"input": "What is RLHF?", "expected": "Reinforcement learning from human feedback"}
    row_digest = compute_row_digest(row)

    uri = compute_object_ref_uri(
        "proj123",
        "qa-dataset",
        dataset_val,
        extra=["attr", "rows", "id", row_digest],
    )

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalObjectRef)
    assert parsed.extra == ["attr", "rows", "id", row_digest]
    assert f"/attr/rows/id/{row_digest}" in uri


def test_compute_object_ref_uri_with_list_index_extra() -> None:
    """Object ref drilling into a list element."""
    val = {"messages": [{"role": "system", "content": "You are helpful."}]}
    uri = compute_object_ref_uri(
        "proj123", "chat-history", val, extra=["attr", "messages", "index", "0"]
    )

    parsed = parse_internal_uri(uri)
    assert parsed.extra == ["attr", "messages", "index", "0"]


def test_compute_object_ref_uri_with_nested_dict_extra() -> None:
    """Object ref drilling into a nested dict key."""
    val = {"hyperparams": {"lr": 0.001, "epochs": 10}}
    uri = compute_object_ref_uri(
        "proj123", "training-config", val, extra=["attr", "hyperparams", "key", "lr"]
    )

    parsed = parse_internal_uri(uri)
    assert parsed.extra == ["attr", "hyperparams", "key", "lr"]


# --- Op refs ---


def test_compute_op_ref_uri() -> None:
    """Op refs use the /op/ kind instead of /object/."""
    op_val = {"source": "def predict(input): ..."}
    uri = compute_op_ref_uri("proj123", "predict", op_val)

    assert "/op/predict:" in uri
    assert "/object/" not in uri

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalOpRef)
    assert parsed.project_id == "proj123"
    assert parsed.name == "predict"
    assert parsed.version == compute_object_digest(op_val)


def test_compute_op_ref_uri_evaluation_run() -> None:
    """Matches the server pattern for evaluation run ops."""
    op_val = {"source": "def Evaluation.evaluate(): ..."}
    uri = compute_op_ref_uri("proj123", "Evaluation.evaluate", op_val)

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalOpRef)
    assert parsed.name == "Evaluation.evaluate"


def test_op_ref_and_object_ref_differ_for_same_val() -> None:
    """Same val produces different URIs for op vs object refs."""
    val = {"source": "def score(output): return output == expected"}
    obj_uri = compute_object_ref_uri("proj123", "score", val)
    op_uri = compute_op_ref_uri("proj123", "score", val)

    assert obj_uri != op_uri
    assert "/object/score:" in obj_uri
    assert "/op/score:" in op_uri
    # Digests themselves should be identical
    obj_parsed = parse_internal_uri(obj_uri)
    op_parsed = parse_internal_uri(op_uri)
    assert obj_parsed.version == op_parsed.version


# --- Table / row refs ---


def test_compute_table_ref_uri_single_row() -> None:
    row = {"prompt": "Explain transformers", "completion": "Transformers are..."}
    row_digests = [compute_row_digest(row)]
    uri = compute_table_ref_uri("proj123", row_digests)

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalTableRef)
    assert parsed.digest == compute_table_digest(row_digests)


def test_compute_table_ref_uri_empty_rows() -> None:
    """Empty row list produces a valid table ref (degenerate but legal)."""
    uri = compute_table_ref_uri("proj123", [])

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalTableRef)
    assert parsed.digest == compute_table_digest([])


def test_row_digest_stable_across_key_order() -> None:
    """Row digests are stable regardless of dict key order."""
    row_a = {"input": "Hello", "expected": "Hi", "score": 0.9}
    row_b = {"score": 0.9, "input": "Hello", "expected": "Hi"}
    assert compute_row_digest(row_a) == compute_row_digest(row_b)


def test_row_digests_unique_per_content() -> None:
    """Different row content produces different digests."""
    row_a = {"input": "What is RAG?", "expected": "Retrieval-augmented generation"}
    row_b = {"input": "What is RAG?", "expected": "A technique for grounding LLMs"}
    assert compute_row_digest(row_a) != compute_row_digest(row_b)


# --- Content / file refs ---


def test_compute_file_content_ref_uri() -> None:
    """File content ref is an object ref with an attr extra for the file field."""
    op_val = {"source": "weave-trace-internal:///proj123/file/abc123"}
    uri = compute_file_content_ref_uri("proj123", "predict", op_val, "source")

    parsed = parse_internal_uri(uri)
    assert isinstance(parsed, InternalObjectRef)
    assert parsed.extra == ["attr", "source"]
    assert parsed.name == "predict"
    assert "/attr/source" in uri


def test_file_digest_deterministic() -> None:
    """Same content always produces the same digest."""
    content = b'{"role": "system", "content": "You are a helpful assistant."}'
    assert compute_file_digest(content) == compute_file_digest(content)


def test_file_digest_unique_per_content() -> None:
    """Different content produces different digests."""
    content_a = b"def predict(input): return llm(input)"
    content_b = b"def predict(input): return llm(input, temperature=0)"
    assert compute_file_digest(content_a) != compute_file_digest(content_b)


def test_file_digest_matches_table_used_by_server() -> None:
    """file_create on the server calls compute_file_digest — verify the formula."""
    source_code = "def evaluate(output, expected): return output == expected"
    content = source_code.encode("utf-8")
    digest = compute_file_digest(content)
    # Must equal bytes_digest (the primitive the server uses)
    assert digest == bytes_digest(content)
