"""Tests for base64 content conversion functionality."""

import base64
import json
from unittest.mock import MagicMock

import pytest

from weave.trace_server.base64_content_conversion import (
    create_content_object,
    extract_data_uri_content,
    extract_standalone_base64,
    is_valid_base64,
    process_call_inputs_outputs,
    replace_base64_with_content_objects,
)
from weave.trace_server.trace_server_interface import FileCreateRes


class TestBase64Detection:
    """Test base64 detection functionality."""

    def test_is_valid_base64_valid(self):
        """Test valid base64 strings are detected."""
        valid_b64 = base64.b64encode(b"a" * 100).decode("ascii")
        assert is_valid_base64(valid_b64)

    def test_is_valid_base64_invalid(self):
        """Test invalid base64 strings are rejected."""
        assert not is_valid_base64("not base64")
        assert not is_valid_base64("abc")  # Too short
        assert not is_valid_base64("a" * 50)  # Too short
        assert not is_valid_base64("abc@#$%")  # Invalid chars

    def test_extract_data_uri_content(self):
        """Test extraction from data URI format."""
        test_data = b"Hello, World!"
        b64_data = base64.b64encode(test_data).decode("ascii")
        data_uri = f"data:text/plain;base64,{b64_data}"

        result = extract_data_uri_content(data_uri)
        assert result is not None
        content_type, decoded_bytes, original_schema = result
        assert content_type == "text/plain"
        assert decoded_bytes == test_data
        assert "text/plain" in original_schema

    def test_extract_data_uri_content_invalid(self):
        """Test invalid data URIs are rejected."""
        assert extract_data_uri_content("not a data uri") is None
        assert extract_data_uri_content("data:text/plain,not base64") is None

    def test_extract_standalone_base64(self):
        """Test extraction of standalone base64 strings."""
        test_data = b"a" * 100
        b64_data = base64.b64encode(test_data).decode("ascii")

        result = extract_standalone_base64(b64_data)
        assert result is not None
        decoded_bytes, original_schema = result
        assert decoded_bytes == test_data
        assert original_schema == "{base64_content}"

    def test_extract_standalone_base64_invalid(self):
        """Test invalid standalone base64 is rejected."""
        assert extract_standalone_base64("not base64") is None
        assert extract_standalone_base64("short") is None


class TestContentObjectCreation:
    """Test Content object creation."""

    def test_create_content_object(self):
        """Test creating a Content object from bytes."""
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )

        test_data = b"Test content"
        mimetype = "text/plain"
        project_id = "test_project"

        result = create_content_object(test_data, mimetype, project_id, trace_server)

        # Verify structure
        assert result["_type"] == "CustomWeaveType"
        assert (
            result["weave_type"]["type"]
            == "weave.type_wrappers.Content.content.Content"
        )
        assert "files" in result
        assert result["files"]["content"] == "content_digest"
        assert result["files"]["metadata.json"] == "metadata_digest"
        # Load op should be present for consistency
        assert "load_op" in result
        assert "weave-trace-internal:///" in result["load_op"]

        # Verify the exact load_op format
        expected_load_op = "weave-trace-internal:///UHJvamVjdEludGVybmFsSWQ6dGVzdF9wcm9qZWN0/op/load_weave.type_wrappers.Content.content.Content:pHK80K8ec7lRHbNwjR2LjWQXRxAV8n5BmkixcTamz2k"
        assert result["load_op"] == expected_load_op

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
        assert metadata["mimetype"] == mimetype
        assert metadata["size"] == len(test_data)


class TestBase64Replacement:
    """Test base64 replacement in data structures."""

    def test_replace_base64_in_dict(self):
        """Test replacing base64 in nested dict structures."""
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
            "field2": b64_data,
            "nested": {"field3": f"data:image/png;base64,{b64_data}"},
        }

        result, refs = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # Check normal string is unchanged
        assert result["field1"] == "normal string"

        # Check standalone base64 was replaced
        assert isinstance(result["field2"], dict)
        assert result["field2"]["_type"] == "CustomWeaveType"

        # Check data URI was replaced
        assert isinstance(result["nested"]["field3"], dict)
        assert result["nested"]["field3"]["_type"] == "CustomWeaveType"

        # Check refs were collected (load_op refs)
        assert len(refs) == 2  # One for each base64 replacement

    def test_replace_base64_in_list(self):
        """Test replacing base64 in list structures."""
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
            b64_data,
            {"nested": f"data:text/plain;base64,{b64_data}"},
        ]

        result, refs = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # Check list structure is preserved
        assert len(result) == 3
        assert result[0] == "normal string"
        assert isinstance(result[1], dict)
        assert result[1]["_type"] == "CustomWeaveType"
        assert isinstance(result[2]["nested"], dict)
        assert result[2]["nested"]["_type"] == "CustomWeaveType"

        # Check refs were collected
        assert len(refs) == 2  # One for each base64 replacement

    def test_process_call_inputs_outputs(self):
        """Test the main entry point for processing call data."""
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )

        test_data = b"Test image data"
        b64_data = base64.b64encode(test_data).decode("ascii")

        input_data = {
            "image": f"data:image/png;base64,{b64_data}",
            "text": "Some normal text",
        }

        result, refs = process_call_inputs_outputs(
            input_data, "test_project", trace_server
        )

        # Verify processing
        assert result["text"] == "Some normal text"
        assert isinstance(result["image"], dict)
        assert result["image"]["_type"] == "CustomWeaveType"
        assert len(refs) == 1  # One load_op ref


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
