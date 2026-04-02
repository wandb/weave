"""Base64 content conversion utilities for trace server.

This module handles automatic detection and replacement of base64 encoded content
with content objects stored in bucket storage, and the reverse operation of
restoring content objects back to base64 for LLM API calls.
"""

import base64
import json
import logging
import re
from typing import Any, TypeVar

import ddtrace

from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndV2Req,
    CallStartReq,
    CompletedCallSchemaForInsert,
    FileContentReadReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.type_wrappers.Content.content import Content

logger = logging.getLogger(__name__)

# Pattern to match data URIs with base64 encoded content
# Format: data:[content-type];base64,[base64_data]
DATA_URI_PATTERN = re.compile(r"^data:([^;]+);base64,([A-Za-z0-9+/=]+)$", re.IGNORECASE)

# Pattern to match standalone base64 strings
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

# Minimum size to create a file (to avoid making more data than what the original is)
AUTO_CONVERSION_MIN_SIZE = 1024  # 1 KiB


def is_base64(value: str) -> bool:
    """Huerestic to quickly check if a string is likely base64.
    We do not decode here because Content already does decode based 'true' validation
    Args:
        value: String to check
    Returns:
        True if the string is possibly valid base64
    """
    return BASE64_PATTERN.match(value) is not None


def is_data_uri(data_uri: str) -> bool:
    """Extract content type and decoded bytes from a data URI.

    Args:
        data_uri: Data URI string in format data:[content-type];base64,[data]

    Returns:
        bool: True is match, else false
    """
    return DATA_URI_PATTERN.match(data_uri) is not None


@ddtrace.tracer.wrap(name="store_content_object")
def store_content_object(
    content_obj: Content,
    project_id: str,
    trace_server: TraceServerInterface,
) -> dict[str, Any]:
    """Create a proper Content object structure and store its files.

    Args:
        data: Raw byte content
        original_schema: The schema to restore the original base64 string
        mimetype: MIME type of the content
        project_id: Project ID for storage
        trace_server: Trace server instance for file storage

    Returns:
        Dict representing the Content object in the proper format
    """
    content_data = content_obj.data
    content_metadata = json.dumps(content_obj.model_dump(exclude={"data"})).encode(
        "utf-8"
    )

    # Create files in storage
    # 1. Store the actual content
    content_req = FileCreateReq(
        project_id=project_id, name="content", content=content_data
    )
    content_res = trace_server.file_create(content_req)

    # 2. Store the metadata
    metadata_req = FileCreateReq(
        project_id=project_id, name="metadata.json", content=content_metadata
    )
    metadata_res = trace_server.file_create(metadata_req)

    # We exclude the load op because it isn't possible to get from the server side
    return {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
        "files": {"content": content_res.digest, "metadata.json": metadata_res.digest},
    }


T = TypeVar("T")


def replace_base64_with_content_objects(
    vals: T,
    project_id: str,
    trace_server: TraceServerInterface,
) -> T:
    """Recursively replace base64 content with Content objects.

    Follows the same pattern as extract_refs_from_values, visiting all values
    and replacing base64 content where found.

    Args:
        vals: Value to process (can be dict, list, or primitive)
        project_id: Project ID for storage
        trace_server: Trace server instance for file storage

    Returns:
        Tuple of (processed_value, list_of_created_refs)
    """

    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            result = {}
            for k, v in val.items():
                result[k] = _visit(v)
            return result
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str) and len(val) > AUTO_CONVERSION_MIN_SIZE:
            # Check for data URI pattern first
            if is_data_uri(val):
                try:
                    # Create proper Content object structure
                    return store_content_object(
                        Content.from_data_url(val),
                        project_id,
                        trace_server,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create and store content from data URI with error %s",
                        e,
                    )

            if is_base64(val):
                try:
                    # All we care about here is if this is an object that we can handle in some way.
                    # 'aaaa' is valid base64 and will come out as text/plain
                    # More complicated false positives or failed detections will show 'application/octet-stream'
                    # The uncovered scenario is if a user has encoded a plaintext document as Base64
                    # We don't handle text content objects in a special way on the clients, so this is acceptable.
                    content: Content[Any] = Content.from_base64(val)
                    if content.mimetype not in {
                        "text/plain",
                        "application/octet-stream",
                    }:
                        return store_content_object(
                            content,
                            project_id,
                            trace_server,
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to create content from standalone base64: %s", e
                    )

            return val
        return val

    return _visit(vals)


R = TypeVar("R", bound=CallStartReq | CallEndReq | CallEndV2Req)


@ddtrace.tracer.wrap(name="process_call_req_to_content")
def process_call_req_to_content(
    req: R,
    trace_server: TraceServerInterface,
) -> R:
    """Process call inputs/outputs to replace base64 content.

    This is the main entry point for processing trace data before insertion.

    Args:
        req: Call request (start, end, or end v2)
        trace_server: Trace server instance

    Returns:
        Request with base64 content replaced by Content objects.
    """
    if isinstance(req, CallStartReq):
        req.start.inputs = replace_base64_with_content_objects(
            req.start.inputs, req.start.project_id, trace_server
        )
    elif isinstance(req, (CallEndReq, CallEndV2Req)):
        req.end.output = replace_base64_with_content_objects(
            req.end.output, req.end.project_id, trace_server
        )

    return req


@ddtrace.tracer.wrap(name="process_complete_call_to_content")
def process_complete_call_to_content(
    complete_call: CompletedCallSchemaForInsert,
    trace_server: TraceServerInterface,
) -> CompletedCallSchemaForInsert:
    """Process a complete call to replace base64 content in inputs and outputs.

    Args:
        complete_call: Complete call schema with both inputs and outputs.
        trace_server: Trace server instance for file storage.

    Returns:
        CompletedCallSchemaForInsert with base64 content replaced by Content objects.
    """
    complete_call.inputs = replace_base64_with_content_objects(
        complete_call.inputs, complete_call.project_id, trace_server
    )
    complete_call.output = replace_base64_with_content_objects(
        complete_call.output, complete_call.project_id, trace_server
    )
    return complete_call


_CONTENT_WEAVE_TYPE = "weave.type_wrappers.Content.content.Content"


def _is_content_object(val: Any) -> bool:
    """Check if a value is a CustomWeaveType Content object dict."""
    return (
        isinstance(val, dict)
        and val.get("_type") == "CustomWeaveType"
        and isinstance(val.get("weave_type"), dict)
        and val["weave_type"].get("type") == _CONTENT_WEAVE_TYPE
        and isinstance(val.get("files"), dict)
    )


@ddtrace.tracer.wrap(name="restore_content_objects_to_base64")
def restore_content_objects_to_base64(
    vals: T,
    project_id: str,
    trace_server: TraceServerInterface,
) -> T:
    """Restore CustomWeaveType Content objects back to data URL strings.

    This is the reverse of replace_base64_with_content_objects. It finds
    CustomWeaveType Content objects in the data structure and reads their stored
    file data, converting back to data URL strings suitable for sending to LLMs.

    Args:
        vals: Value to process (can be dict, list, or primitive)
        project_id: Project ID for file storage lookup
        trace_server: Trace server instance for file reading

    Returns:
        Processed value with Content objects replaced by data URL strings.
    """

    def _restore_one(val: dict) -> Any:
        files = val.get("files", {})
        metadata_digest = files.get("metadata.json")
        content_digest = files.get("content")

        if not metadata_digest or not content_digest:
            return val

        try:
            metadata_res = trace_server.file_content_read(
                FileContentReadReq(project_id=project_id, digest=metadata_digest)
            )
            metadata = json.loads(metadata_res.content)
            mimetype = metadata.get("mimetype", "application/octet-stream")

            content_res = trace_server.file_content_read(
                FileContentReadReq(project_id=project_id, digest=content_digest)
            )
            b64_data = base64.b64encode(content_res.content).decode("ascii")
            return f"data:{mimetype};base64,{b64_data}"
        except Exception as e:
            logger.warning("Failed to restore Content object to data URL: %s", e)
            return val

    def _visit(v: Any) -> Any:
        if _is_content_object(v):
            return _restore_one(v)
        if isinstance(v, dict):
            # Handle Weave's custom ContentMessage format: {type: "image", image: <content_object>}
            # The frontend stores images as {type: K, [K]: CustomWeaveTypePayload} where K is
            # the content type. Convert to the standard OpenAI image_url format so litellm
            # can forward it to any LLM provider.
            content_type = v.get("type")
            if content_type == "image" and _is_content_object(v.get("image")):
                data_url = _restore_one(v["image"])
                if isinstance(data_url, str):
                    return {"type": "image_url", "image_url": {"url": data_url}}
            return {k: _visit(item) for k, item in v.items()}
        if isinstance(v, list):
            return [_visit(item) for item in v]
        return v

    return _visit(vals)
