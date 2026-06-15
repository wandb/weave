"""Tests for base64 content conversion functionality (updated for new API)."""

import base64
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from weave.trace_server.base64_content_conversion import (
    AUTO_CONVERSION_MIN_SIZE,
    is_base64,
    is_data_uri,
    process_call_req_to_content,
    replace_base64_with_content_objects,
    store_content_object,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    EndedCallSchemaForInsert,
    FileCreateRes,
    StartedCallSchemaForInsert,
)
from weave.type_wrappers.Content.content import Content

# Test data size larger than AUTO_CONVERSION_MIN_SIZE to trigger conversion
LARGE_TEST_DATA_SIZE = AUTO_CONVERSION_MIN_SIZE + 10


def test_is_data_uri_detection():
    """Valid base64 data URIs are detected; non-data-URI strings are rejected."""
    b64_data = base64.b64encode(b"Hello, World!").decode("ascii")
    assert is_data_uri(f"data:text/plain;base64,{b64_data}")
    assert not is_data_uri("not a data uri")
    assert not is_data_uri("data:text/plain,not base64")


def test_store_content_object():
    """Storing a Content object persists content and metadata files."""
    trace_server = _mock_trace_server(2)
    test_data = b"Test content"
    project_id = "test_project"

    content_obj = Content.from_bytes(test_data)
    result = store_content_object(content_obj, project_id, trace_server)

    # Verify structure
    assert result["_type"] == "CustomWeaveType"
    assert result["weave_type"]["type"] == "weave.type_wrappers.Content.content.Content"
    assert "files" in result
    assert result["files"]["content"] == "content_0"
    assert result["files"]["metadata.json"] == "content_1"

    # Verify file_create was called for content then metadata.
    assert trace_server.file_create.call_count == 2
    calls = trace_server.file_create.call_args_list
    content_call = calls[0][0][0]
    assert content_call.project_id == project_id
    assert content_call.name == "content"
    assert content_call.content == test_data

    metadata_call = calls[1][0][0]
    assert metadata_call.project_id == project_id
    assert metadata_call.name == "metadata.json"
    metadata = json.loads(metadata_call.content)
    assert metadata["mimetype"] == content_obj.mimetype
    assert metadata["size"] == content_obj.size
    assert metadata["filename"] == content_obj.filename


def test_replace_data_uri_only_in_dict_and_list_containers():
    """Across both dict and list containers, only base64 data URIs are
    replaced; normal strings and raw (non-data-URI) base64 are left untouched.
    """
    test_data = b"a" * LARGE_TEST_DATA_SIZE
    b64_data = base64.b64encode(test_data).decode("ascii")

    dict_server = _mock_trace_server(4)
    dict_result = replace_base64_with_content_objects(
        {
            "field1": "normal string",
            "field2": b64_data,  # raw base64 should remain unchanged
            "nested": {"field3": f"data:image/png;base64,{b64_data}"},
        },
        "test_project",
        dict_server,
    )
    assert dict_result["field1"] == "normal string"
    assert dict_result["field2"] == b64_data
    assert isinstance(dict_result["nested"]["field3"], dict)
    assert dict_result["nested"]["field3"]["_type"] == "CustomWeaveType"
    assert set(dict_result["nested"]["field3"]["files"].keys()) == {
        "content",
        "metadata.json",
    }

    list_server = _mock_trace_server(4)
    list_result = replace_base64_with_content_objects(
        [
            "normal string",
            b64_data,  # raw base64 should remain unchanged
            {"nested": f"data:text/plain;base64,{b64_data}"},
        ],
        "test_project",
        list_server,
    )
    assert len(list_result) == 3
    assert list_result[0] == "normal string"
    assert list_result[1] == b64_data
    assert isinstance(list_result[2]["nested"], dict)
    assert list_result[2]["nested"]["_type"] == "CustomWeaveType"


def test_process_call_req_to_content_start_and_end():
    """The main entry point processes data URIs in CallStartReq inputs but
    leaves raw base64 in CallEndReq output untouched.
    """
    trace_server = _mock_trace_server(4)
    test_data = b"x" * LARGE_TEST_DATA_SIZE
    b64_data = base64.b64encode(test_data).decode("ascii")

    start_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id="proj",
            op_name="op",
            started_at=datetime.now(timezone.utc),
            attributes={},
            inputs={
                "image": f"data:image/png;base64,{b64_data}",
                "text": "Some normal text",
            },
        )
    )
    processed_start = process_call_req_to_content(start_req, trace_server)
    assert processed_start.start.inputs["text"] == "Some normal text"
    assert isinstance(processed_start.start.inputs["image"], dict)
    assert processed_start.start.inputs["image"]["_type"] == "CustomWeaveType"

    long_bytes = b"y" * LARGE_TEST_DATA_SIZE
    long_b64 = base64.b64encode(long_bytes).decode("ascii")
    end_req = CallEndReq(
        end=EndedCallSchemaForInsert(
            project_id="proj",
            id="call-id",
            ended_at=datetime.now(timezone.utc),
            summary={"usage": {}, "status_counts": {}},
            output=long_b64,
        )
    )
    processed_end = process_call_req_to_content(end_req, trace_server)
    assert processed_end.end.output == long_b64


def test_non_media_base64_strings_not_converted():
    """Base64 strings of various lengths (mod 4) that decode to text/plain or
    application/octet-stream are NOT converted.
    """
    trace_server = MagicMock()
    test_cases = [
        "aaaa",  # decodes to binary data
        "aGVsbG8=",  # "hello"
        "dGVzdCBtZXNzYWdl",  # "test message"
        "VGhpcyBpcyBhIGxvbmdlciB0ZXN0IG1lc3NhZ2U=",  # longer text
        "YQ==",  # "a"
        "YWI=",  # "ab"
        "YWJj",  # "abc"
        "SGVsbG8gV29ybGQh",  # "Hello World!"
    ]
    for test_str in test_cases:
        assert is_base64(test_str), f"Expected {test_str} to match base64 pattern"
        result = replace_base64_with_content_objects(
            {"field": test_str}, "test_project", trace_server
        )
        assert result["field"] == test_str, f"Expected {test_str} to NOT be converted"
    assert trace_server.file_create.call_count == 0


def test_wav_file_base64_converted():
    """A field containing raw base64 representing a WAV file is detected and
    converted to a Content object, with audio/x-wav normalized to audio/wav.
    """
    trace_server = _mock_trace_server(2)
    wav_base64 = base64.b64encode(_make_wav_bytes()).decode("ascii")
    assert is_base64(wav_base64)

    result = replace_base64_with_content_objects(
        {"audio_field": wav_base64, "other_field": "normal string"},
        "test_project",
        trace_server,
    )

    assert isinstance(result["audio_field"], dict)
    assert result["audio_field"]["_type"] == "CustomWeaveType"
    assert (
        result["audio_field"]["weave_type"]["type"]
        == "weave.type_wrappers.Content.content.Content"
    )
    assert "content" in result["audio_field"]["files"]
    assert "metadata.json" in result["audio_field"]["files"]
    assert result["other_field"] == "normal string"
    assert trace_server.file_create.call_count == 2

    metadata_call = trace_server.file_create.call_args_list[1][0][0]
    metadata = json.loads(metadata_call.content)
    assert metadata["mimetype"] == "audio/wav"


def test_auto_conversion_threshold_gates_storage():
    """The auto-conversion threshold is 8 KiB; a sub-threshold base64-looking
    string short-circuits on size with no regex and no storage call.
    """
    assert AUTO_CONVERSION_MIN_SIZE == 8192

    trace_server = MagicMock()
    # 4 KiB of valid-looking base64 alphabet would have decoded under the old
    # threshold and hit the regex path; now it must be returned untouched.
    below_threshold = "A" * 4096
    result = replace_base64_with_content_objects(
        {"field": below_threshold}, "test_project", trace_server
    )
    assert result["field"] == below_threshold
    assert trace_server.file_create.call_count == 0


def test_no_replacement_returns_same_object_identity():
    """A clean no-binary tree returns the original object at every level.

    Identity (not equality) matters: it's what makes the no-binary hot path
    cheap and would catch a regression to an always-allocate code path.
    """
    trace_server = MagicMock()
    original = {
        "messages": [
            {"role": "user", "content": "no binary here"},
            {"role": "assistant", "content": "still nothing"},
        ],
        "metadata": {"trace_id": "abc"},
    }
    result = replace_base64_with_content_objects(original, "test_project", trace_server)
    assert result is original
    assert result["messages"] is original["messages"]
    assert result["messages"][0] is original["messages"][0]
    assert result["metadata"] is original["metadata"]


def test_partial_replacement_isolates_unchanged_subtrees_in_dict_and_list():
    """A replacement copies only the affected subtree: untouched dict branches
    and untouched list indices keep their identity, the touched node is a fresh
    object, and the input payload is never mutated.
    """
    # Dict-partial: one message branch holds a data URI, the other is plain.
    dict_server = _mock_trace_server(2)
    png_data_uri = _png_data_uri()
    untouched_branch = {"role": "assistant", "content": "plain reply"}
    touched_branch = {
        "role": "user",
        "content": [{"type": "image_url", "image_url": {"url": png_data_uri}}],
    }
    dict_original = {
        "messages": [untouched_branch, touched_branch],
        "model": "claude-sonnet-4-6",
    }
    dict_result = replace_base64_with_content_objects(
        dict_original, "test_project", dict_server
    )
    assert dict_result["messages"][0] is untouched_branch
    assert dict_result["messages"][1] is not touched_branch
    assert touched_branch["content"][0]["image_url"]["url"] == png_data_uri

    # List-partial: the list is copied (one entry changed) but the unchanged
    # dict entries keep their identity inside the new list.
    list_server = _mock_trace_server(2)
    untouched_message = {"role": "user", "content": "plain text"}
    touched_message = {"role": "assistant", "content": png_data_uri}
    other_untouched_message = {"role": "tool", "content": "also plain"}
    list_messages = [untouched_message, touched_message, other_untouched_message]
    list_original = {"messages": list_messages, "model": "claude-sonnet-4-6"}
    list_result = replace_base64_with_content_objects(
        list_original, "test_project", list_server
    )
    assert list_result["messages"] is not list_messages
    assert list_result["messages"][0] is untouched_message
    assert list_result["messages"][2] is other_untouched_message
    assert list_result["messages"][1] is not touched_message
    assert touched_message["content"] == png_data_uri


def test_caller_overwrite_safe_after_in_place_return():
    """The ``req.start.inputs = replace_base64(...)`` caller pattern is safe:
    the no-copy path rebinds the field without introducing an aliasing bug.
    """
    trace_server = MagicMock()
    inputs_before = {"text": "no binary content here"}
    start_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id="proj",
            op_name="op",
            started_at=datetime.now(timezone.utc),
            attributes={},
            inputs=inputs_before,
        )
    )
    processed = process_call_req_to_content(start_req, trace_server)
    # Pydantic shallow-copies inputs at construction, so compare by value.
    assert processed.start.inputs == inputs_before
    assert trace_server.file_create.call_count == 0


def _mock_trace_server(num_files: int) -> MagicMock:
    """A trace server whose file_create returns deterministic digests."""
    trace_server = MagicMock()
    trace_server.file_create = MagicMock(
        side_effect=[FileCreateRes(digest=f"content_{i}") for i in range(num_files)]
    )
    return trace_server


def _png_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000
    ).decode("ascii")


def _make_wav_bytes() -> bytes:
    """A minimal valid WAV file larger than AUTO_CONVERSION_MIN_SIZE."""
    wav_data = bytearray()
    wav_data.extend(b"RIFF")
    file_size_pos = len(wav_data)
    wav_data.extend(b"\x00\x00\x00\x00")  # placeholder for file size
    wav_data.extend(b"WAVE")

    wav_data.extend(b"fmt ")
    wav_data.extend((16).to_bytes(4, "little"))  # chunk size
    wav_data.extend((1).to_bytes(2, "little"))  # audio format (PCM)
    wav_data.extend((1).to_bytes(2, "little"))  # num channels
    wav_data.extend((44100).to_bytes(4, "little"))  # sample rate
    wav_data.extend((88200).to_bytes(4, "little"))  # byte rate
    wav_data.extend((2).to_bytes(2, "little"))  # block align
    wav_data.extend((16).to_bytes(2, "little"))  # bits per sample

    audio_data_size = LARGE_TEST_DATA_SIZE
    wav_data.extend(b"data")
    wav_data.extend(audio_data_size.to_bytes(4, "little"))
    wav_data.extend(b"\x00" * audio_data_size)

    file_size = len(wav_data) - 8
    wav_data[file_size_pos : file_size_pos + 4] = file_size.to_bytes(4, "little")
    return bytes(wav_data)
