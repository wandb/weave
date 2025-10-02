"""Tests for base64 content conversion functionality (updated for new API)."""

import base64
import json
from unittest.mock import MagicMock

import pytest

from weave.trace_server.base64_content_conversion import (
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
        assert result["weave_type"]["type"] == "weave.type_wrappers.Content.content.Content"
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

        test_data = b"a" * 100
        b64_data = base64.b64encode(test_data).decode("ascii")

        input_data = {
            "field1": "normal string",
            "field2": b64_data,  # raw base64 should remain unchanged
            "nested": {"field3": f"data:image/png;base64,{b64_data}"},
        }

        result = replace_base64_with_content_objects(input_data, "test_project", trace_server)

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

        test_data = b"a" * 100
        b64_data = base64.b64encode(test_data).decode("ascii")

        input_data = [
            "normal string",
            b64_data,  # raw base64 should remain unchanged
            {"nested": f"data:text/plain;base64,{b64_data}"},
        ]

        result = replace_base64_with_content_objects(input_data, "test_project", trace_server)

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

        test_data = b"Test image data"
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

        # End request with standalone base64 in output should NOT be replaced
        long_bytes = b"b" * 100
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
