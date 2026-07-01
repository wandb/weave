"""Tests for base64 content conversion functionality (updated for new API)."""

import base64
import json
from unittest.mock import MagicMock

import pytest

from weave.trace_server.base64_content_conversion import (
    AUTO_CONVERSION_MIN_SIZE,
    is_base64,
    is_data_uri,
    process_call_req_to_content,
    replace_base64_in_raw_messages,
    replace_base64_with_content_objects,
    store_content_object,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    EndedCallSchemaForInsert,
    FileCreateRes,
    ObjCreateRes,
    StartedCallSchemaForInsert,
)
from weave.type_wrappers.Content.content import Content

# Test data size larger than AUTO_CONVERSION_MIN_SIZE to trigger conversion
LARGE_TEST_DATA_SIZE = AUTO_CONVERSION_MIN_SIZE + 10

# Object digest returned by the mocked ``obj_create`` when content is published.
_OBJ_DIGEST = "obj_digest"


def _mock_obj_create(trace_server: MagicMock) -> None:
    """Mock ``obj_create`` so auto-conversion can publish a Content object.

    ``replace_base64_with_content_objects`` publishes each converted blob as a
    weave object and embeds its ref, so any test that converts must stub this.
    """
    trace_server.obj_create = MagicMock(
        return_value=ObjCreateRes(digest=_OBJ_DIGEST)
    )


def _assert_content_ref(value: object, project_id: str) -> None:
    """Assert *value* is an internal weave object ref to a published Content."""
    assert isinstance(value, str)
    assert value.startswith(f"weave-trace-internal:///{project_id}/object/")
    assert value.endswith(f":{_OBJ_DIGEST}")


class TestBase64AndDataURIDetection:
    """Test detection heuristics for data URIs only (raw base64 no longer auto-encoded)."""

    def test_is_data_uri_valid(self):
        """Valid base64 data URIs are detected."""
        test_data = b"Hello, World!"
        b64_data = base64.b64encode(test_data).decode("ascii")
        data_uri = f"data:text/plain;base64,{b64_data}"
        assert is_data_uri(data_uri)

    def test_is_data_uri_invalid(self):
        """Invalid data URIs are rejected."""
        assert not is_data_uri("not a data uri")
        assert not is_data_uri("data:text/plain,not base64")


class TestContentObjectStorage:
    """Test Content object storage and structure."""

    def test_store_content_object(self):
        """Test storing a Content object persists content and metadata files."""
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )

        test_data = b"Test content"
        project_id = "test_project"

        content_obj = Content.from_bytes(test_data)
        result = store_content_object(content_obj, project_id, trace_server)

        # Verify structure
        assert result["_type"] == "CustomWeaveType"
        assert (
            result["weave_type"]["type"]
            == "weave.type_wrappers.Content.content.Content"
        )
        assert "files" in result
        assert result["files"]["content"] == "content_digest"
        assert result["files"]["metadata.json"] == "metadata_digest"

        # Verify file_create was called
        assert trace_server.file_create.call_count == 2
        calls = trace_server.file_create.call_args_list

        # First call for content
        content_call = calls[0][0][0]
        assert content_call.project_id == project_id
        assert content_call.name == "content"
        assert content_call.content == test_data

        # Second call for metadata
        metadata_call = calls[1][0][0]
        assert metadata_call.project_id == project_id
        assert metadata_call.name == "metadata.json"
        metadata = json.loads(metadata_call.content)
        # Ensure key metadata fields are present and correct
        assert metadata["mimetype"] == content_obj.mimetype
        assert metadata["size"] == content_obj.size
        assert metadata["filename"] == content_obj.filename


class TestBase64Replacement:
    """Test base64 replacement in data structures."""

    def test_replace_data_uri_in_dict_only(self):
        """Only base64 data URIs are replaced; raw base64 is left untouched."""
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest1"),
                FileCreateRes(digest="metadata_digest1"),
                FileCreateRes(digest="content_digest2"),
                FileCreateRes(digest="metadata_digest2"),
            ]
        )
        _mock_obj_create(trace_server)

        test_data = b"a" * LARGE_TEST_DATA_SIZE
        b64_data = base64.b64encode(test_data).decode("ascii")

        input_data = {
            "field1": "normal string",
            "field2": b64_data,  # raw base64 should remain unchanged
            "nested": {"field3": f"data:image/png;base64,{b64_data}"},
        }

        result = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # Check normal string is unchanged
        assert result["field1"] == "normal string"

        # Check standalone base64 is NOT replaced
        assert result["field2"] == b64_data

        # Check data URI was replaced with a published-object ref
        _assert_content_ref(result["nested"]["field3"], "test_project")

    def test_replace_data_uri_in_list_only(self):
        """Only base64 data URIs are replaced in lists; raw base64 is left untouched."""
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest1"),
                FileCreateRes(digest="metadata_digest1"),
                FileCreateRes(digest="content_digest2"),
                FileCreateRes(digest="metadata_digest2"),
            ]
        )
        _mock_obj_create(trace_server)

        test_data = b"a" * LARGE_TEST_DATA_SIZE
        b64_data = base64.b64encode(test_data).decode("ascii")

        input_data = [
            "normal string",
            b64_data,  # raw base64 should remain unchanged
            {"nested": f"data:text/plain;base64,{b64_data}"},
        ]

        result = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # Check list structure is preserved
        assert len(result) == 3
        assert result[0] == "normal string"
        # Raw base64 remains a string
        assert result[1] == b64_data
        _assert_content_ref(result[2]["nested"], "test_project")

    def test_process_call_req_to_content_start_and_end(self):
        """Test the main entry point for processing CallStartReq and CallEndReq."""
        # Mock trace server
        trace_server = MagicMock()
        # Two files for start (content + metadata), two for end
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest_start"),
                FileCreateRes(digest="metadata_digest_start"),
                FileCreateRes(digest="content_digest_end"),
                FileCreateRes(digest="metadata_digest_end"),
            ]
        )
        _mock_obj_create(trace_server)

        test_data = b"x" * LARGE_TEST_DATA_SIZE
        b64_data = base64.b64encode(test_data).decode("ascii")

        # Start request with data URI in inputs
        start_req = CallStartReq(
            start=StartedCallSchemaForInsert(
                project_id="proj",
                op_name="op",
                started_at=__import__("datetime").datetime.utcnow(),
                attributes={},
                inputs={
                    "image": f"data:image/png;base64,{b64_data}",
                    "text": "Some normal text",
                },
            )
        )

        processed_start = process_call_req_to_content(start_req, trace_server)
        assert processed_start.start.inputs["text"] == "Some normal text"
        _assert_content_ref(processed_start.start.inputs["image"], "proj")

        long_bytes = b"y" * LARGE_TEST_DATA_SIZE
        long_b64 = base64.b64encode(long_bytes).decode("ascii")
        end_req = CallEndReq(
            end=EndedCallSchemaForInsert(
                project_id="proj",
                id="call-id",
                ended_at=__import__("datetime").datetime.utcnow(),
                summary={"usage": {}, "status_counts": {}},
                output=long_b64,
            )
        )

        processed_end = process_call_req_to_content(end_req, trace_server)
        assert processed_end.end.output == long_b64


class TestStandaloneBase64Detection:
    """Test detection and conversion of standalone base64 strings (new functionality)."""

    def test_non_media_base64_strings_not_converted(self):
        """Test that various base64 strings of different lengths (mod 4) that decode to
        text/plain or application/octet-stream are NOT converted.
        """
        # Mock trace server
        trace_server = MagicMock()

        # Test strings of various lengths mod 4
        # These should all decode to text/plain or application/octet-stream
        test_cases = [
            # Length % 4 == 0: "aaaa" decodes to binary data
            "aaaa",
            # Length % 4 == 0: "hello" in base64
            "aGVsbG8=",
            # Length % 4 == 0: "test message"
            "dGVzdCBtZXNzYWdl",
            # Length % 4 == 0: longer text
            "VGhpcyBpcyBhIGxvbmdlciB0ZXN0IG1lc3NhZ2U=",
            # Short strings that are valid base64 but not media
            "YQ==",  # "a"
            "YWI=",  # "ab"
            "YWJj",  # "abc"
            # Random-looking base64 that's still text-like
            "SGVsbG8gV29ybGQh",  # "Hello World!"
        ]

        for test_str in test_cases:
            # First verify these match the base64 pattern
            assert is_base64(test_str), f"Expected {test_str} to match base64 pattern"

            input_data = {"field": test_str}
            result = replace_base64_with_content_objects(
                input_data, "test_project", trace_server
            )

            # These should NOT be converted because they decode to text/plain or application/octet-stream
            assert result["field"] == test_str, (
                f"Expected {test_str} to NOT be converted"
            )

        # Verify trace server was never called since nothing should be converted
        assert trace_server.file_create.call_count == 0

    def test_wav_file_base64_converted(self):
        """Test that a dict with a field containing raw base64 representing a WAV file
        is detected and converted to Content.
        """
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )
        _mock_obj_create(trace_server)

        # Create a minimal valid WAV file (larger than AUTO_CONVERSION_MIN_SIZE)
        # WAV format: RIFF header + fmt chunk + data chunk
        wav_data = bytearray()

        # RIFF header
        wav_data.extend(b"RIFF")
        # Placeholder for file size (will update later)
        file_size_pos = len(wav_data)
        wav_data.extend(b"\x00\x00\x00\x00")
        wav_data.extend(b"WAVE")

        # fmt chunk
        wav_data.extend(b"fmt ")
        wav_data.extend((16).to_bytes(4, "little"))  # chunk size
        wav_data.extend((1).to_bytes(2, "little"))  # audio format (PCM)
        wav_data.extend((1).to_bytes(2, "little"))  # num channels
        wav_data.extend((44100).to_bytes(4, "little"))  # sample rate
        wav_data.extend((88200).to_bytes(4, "little"))  # byte rate
        wav_data.extend((2).to_bytes(2, "little"))  # block align
        wav_data.extend((16).to_bytes(2, "little"))  # bits per sample

        # data chunk - make it large enough to exceed AUTO_CONVERSION_MIN_SIZE
        audio_data_size = LARGE_TEST_DATA_SIZE
        wav_data.extend(b"data")
        wav_data.extend(audio_data_size.to_bytes(4, "little"))
        # Add audio data (silence)
        wav_data.extend(b"\x00" * audio_data_size)

        # Update file size in RIFF header (total size - 8 bytes for RIFF header)
        file_size = len(wav_data) - 8
        wav_data[file_size_pos : file_size_pos + 4] = file_size.to_bytes(4, "little")

        # Encode as base64
        wav_base64 = base64.b64encode(bytes(wav_data)).decode("ascii")

        # Verify it matches base64 pattern
        assert is_base64(wav_base64)

        # Test that it gets converted
        input_data = {
            "audio_field": wav_base64,
            "other_field": "normal string",
        }

        result = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # The WAV file should be converted to a published-object ref
        _assert_content_ref(result["audio_field"], "test_project")

        # Normal string should be unchanged
        assert result["other_field"] == "normal string"

        # Verify file_create was called twice (content + metadata)
        assert trace_server.file_create.call_count == 2

        # Detected audio/x-wav is normalized to canonical audio/wav.
        metadata_call = trace_server.file_create.call_args_list[1][0][0]
        metadata = json.loads(metadata_call.content)
        assert metadata["mimetype"] == "audio/wav"


class TestThresholdAndStructuralIdentity:
    """Pins the auto-conversion threshold and the "don't copy unchanged subtrees" behaviour.

    These exist because both knobs are part of the hot path on every
    ``upsert_batch``: the threshold gates how much expensive regex / decode
    work runs on long-but-not-binary strings, and the in-place return path
    avoids allocating a fresh dict/list on each level of a no-binary payload.
    """

    def test_auto_conversion_threshold_is_eight_kib(self):
        """Regression guard: the threshold has a real cost when lowered."""
        # If someone drops this back to 1024, all the mid-sized LLM outputs in
        # production traces start hitting `is_data_uri` + `is_base64` again —
        # the very work the threshold bump was meant to skip.
        assert AUTO_CONVERSION_MIN_SIZE == 8192

    def test_string_below_threshold_does_not_invoke_storage(self):
        """A 1-8 KiB string must short-circuit on size; no regex, no storage."""
        trace_server = MagicMock()
        # 4 KiB string of valid-looking base64 alphabet — would have decoded
        # successfully under the old threshold and gone through the regex
        # path. Now it must be returned untouched.
        below_threshold = "A" * 4096
        result = replace_base64_with_content_objects(
            {"field": below_threshold}, "test_project", trace_server
        )
        assert result["field"] == below_threshold
        assert trace_server.file_create.call_count == 0

    def test_no_replacement_returns_same_object_identity(self):
        """If nothing changed, the caller gets back the original dict object.

        This is what makes the no-binary hot path cheap: every level whose
        children are all untouched returns the same reference instead of
        allocating a fresh copy. Identity matters here — checking equality
        wouldn't catch a regression to the always-allocate code path.
        """
        trace_server = MagicMock()
        original = {
            "messages": [
                {"role": "user", "content": "no binary here"},
                {"role": "assistant", "content": "still nothing"},
            ],
            "metadata": {"trace_id": "abc"},
        }
        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )
        # The outer dict, the messages list, every inner message dict, and
        # the metadata dict must all be the same object as the input — no
        # copies anywhere on a clean no-binary tree.
        assert result is original
        assert result["messages"] is original["messages"]
        assert result["messages"][0] is original["messages"][0]
        assert result["metadata"] is original["metadata"]

    def test_partial_replacement_copies_only_affected_subtrees(self):
        """A replacement on one branch must not allocate copies on the others."""
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )
        _mock_obj_create(trace_server)
        png_data_uri = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000
        ).decode("ascii")

        untouched_branch = {"role": "assistant", "content": "plain reply"}
        touched_branch = {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": png_data_uri}}],
        }
        original = {
            "messages": [untouched_branch, touched_branch],
            "model": "claude-sonnet-4-6",
        }

        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )

        # Branches with no replacement keep their identity.
        assert result["messages"][0] is untouched_branch
        # The branch that did get a replacement is a fresh object whose
        # rewritten subtree no longer matches the source.
        assert result["messages"][1] is not touched_branch
        # And critically: the input dict was not mutated.
        assert touched_branch["content"][0]["image_url"]["url"] == png_data_uri

    def test_partial_replacement_in_list_isolates_unchanged_indices(self):
        """List sibling of the dict-partial test: only the touched index is copied.

        Without this the list branch of ``_visit_children`` is only exercised
        in the all-changed and all-unchanged extremes, which leaves the
        "first-change triggers a copy of the whole list" path partially
        covered (codecov flagged this on the original PR).
        """
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )
        _mock_obj_create(trace_server)
        png_data_uri = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000
        ).decode("ascii")

        untouched_message = {"role": "user", "content": "plain text"}
        touched_message = {"role": "assistant", "content": png_data_uri}
        other_untouched_message = {"role": "tool", "content": "also plain"}
        original_messages = [
            untouched_message,
            touched_message,
            other_untouched_message,
        ]
        original = {"messages": original_messages, "model": "claude-sonnet-4-6"}

        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )

        # The list itself was copied (one of its entries changed), but the
        # unchanged dict entries keep their identity inside the new list.
        assert result["messages"] is not original_messages
        assert result["messages"][0] is untouched_message
        assert result["messages"][2] is other_untouched_message
        # The touched entry was replaced — different identity, and the
        # original dict is left intact.
        assert result["messages"][1] is not touched_message
        assert touched_message["content"] == png_data_uri

    def test_caller_overwrite_safe_after_in_place_return(self):
        """Caller pattern ``req.start.inputs = replace_base64(...)`` is safe.

        Confirms the no-copy path doesn't introduce a subtle aliasing bug:
        even though the result is the same object as the input, the
        ``CallStartReq`` machinery in ``process_call_req_to_content`` just
        rebinds the field, which is fine.
        """
        from datetime import datetime, timezone

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
        # Pydantic shallow-copies inputs at model construction, so we compare
        # by value rather than identity here — content must round-trip
        # unchanged regardless of the SDK copy.
        assert processed.start.inputs == inputs_before
        assert trace_server.file_create.call_count == 0


class TestReplaceBase64InRawMessages:
    """Test the OTel raw-message wrapper that mirrors the non-OTel calls path.

    GenAI OTel spans usually carry their message payload as a JSON-encoded
    string, so ``replace_base64_in_raw_messages`` must parse it into structured
    form before the shared walker can find inline base64 leaves.
    """

    @staticmethod
    def _trace_server() -> MagicMock:
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=lambda req: FileCreateRes(digest=f"digest_{req.name}")
        )
        _mock_obj_create(trace_server)
        return trace_server

    @staticmethod
    def _data_uri() -> str:
        b64 = base64.b64encode(b"a" * LARGE_TEST_DATA_SIZE).decode("ascii")
        return f"data:image/png;base64,{b64}"

    def test_json_string_messages_data_uri_converted(self):
        """A JSON-string payload is parsed and inline data-URIs are converted."""
        trace_server = self._trace_server()
        data_uri = self._data_uri()
        messages = json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {"type": "text", "content": "describe this"},
                        {"type": "image", "url": data_uri},
                    ],
                }
            ]
        )

        result = replace_base64_in_raw_messages(messages, "proj", trace_server)

        # Parsed into structured form (mirrors what _normalize_raw_messages sees).
        assert isinstance(result, list)
        parts = result[0]["parts"]
        assert parts[0] == {"type": "text", "content": "describe this"}
        # The data-URI field value (not the whole part) becomes a Content ref.
        assert parts[1]["type"] == "image"
        _assert_content_ref(parts[1]["url"], "proj")
        assert trace_server.file_create.call_count == 2

    def test_structured_list_messages_converted(self):
        """An already-parsed list is walked directly (no JSON string)."""
        trace_server = self._trace_server()
        messages = [{"role": "user", "parts": [{"type": "image", "url": self._data_uri()}]}]

        result = replace_base64_in_raw_messages(messages, "proj", trace_server)

        _assert_content_ref(result[0]["parts"][0]["url"], "proj")
        assert trace_server.file_create.call_count == 2

    def test_no_base64_is_noop(self):
        """A payload without base64 triggers no file storage."""
        trace_server = self._trace_server()
        messages = json.dumps(
            [{"role": "user", "parts": [{"type": "text", "content": "hello"}]}]
        )

        result = replace_base64_in_raw_messages(messages, "proj", trace_server)

        assert result == [
            {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
        ]
        assert trace_server.file_create.call_count == 0

    def test_non_json_string_returned_unchanged(self):
        """A plain (non-JSON) string is returned as-is, not stored."""
        trace_server = self._trace_server()

        result = replace_base64_in_raw_messages("just some text", "proj", trace_server)

        assert result == "just some text"
        assert trace_server.file_create.call_count == 0

    def test_none_and_non_container_returned_unchanged(self):
        """None and non-container inputs are passed through untouched."""
        trace_server = self._trace_server()

        assert replace_base64_in_raw_messages(None, "proj", trace_server) is None
        assert replace_base64_in_raw_messages(42, "proj", trace_server) == 42
        assert trace_server.file_create.call_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
