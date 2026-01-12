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

        # Check data URI was replaced
        assert isinstance(result["nested"]["field3"], dict)
        assert result["nested"]["field3"]["_type"] == "CustomWeaveType"
        assert set(result["nested"]["field3"]["files"].keys()) == {
            "content",
            "metadata.json",
        }

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
        assert isinstance(result[2]["nested"], dict)
        assert result[2]["nested"]["_type"] == "CustomWeaveType"

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
        assert isinstance(processed_start.start.inputs["image"], dict)
        assert processed_start.start.inputs["image"]["_type"] == "CustomWeaveType"

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

        # The WAV file should be converted to Content object
        assert isinstance(result["audio_field"], dict)
        assert result["audio_field"]["_type"] == "CustomWeaveType"
        assert (
            result["audio_field"]["weave_type"]["type"]
            == "weave.type_wrappers.Content.content.Content"
        )
        assert "files" in result["audio_field"]
        assert "content" in result["audio_field"]["files"]
        assert "metadata.json" in result["audio_field"]["files"]

        # Normal string should be unchanged
        assert result["other_field"] == "normal string"

        # Verify file_create was called twice (content + metadata)
        assert trace_server.file_create.call_count == 2

        # Verify the content mimetype is audio/wav (not text/plain or application/octet-stream)
        metadata_call = trace_server.file_create.call_args_list[1][0][0]
        metadata = json.loads(metadata_call.content)
        assert metadata["mimetype"] in ["audio/wav", "audio/x-wav", "audio/wave"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
