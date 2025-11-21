"""Base64 content conversion utilities for trace server.

This module handles automatic detection and replacement of base64 encoded content
with content objects stored in bucket storage.
"""

import json
import logging
import re
from typing import Any, TypeVar

from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    FileCreateReq,
    TraceServerInterface,
)
from weave.type_wrappers.Content.content import Content

logger = logging.getLogger(__name__)

# Pattern to match data URIs with base64 encoded content
# Format: data:[content-type];base64,[base64_data]
DATA_URI_PATTERN = re.compile(r"^data:([^;]+);base64,([A-Za-z0-9+/=]+)$", re.IGNORECASE)

# Minimum size to create a file (to avoid making more data than what the original is)
AUTO_CONVERSION_MIN_SIZE = 1024  # 1 KiB


def is_data_uri(data_uri: str) -> bool:
    """Extract content type and decoded bytes from a data URI.

    Args:
        data_uri: Data URI string in format data:[content-type];base64,[data]

    Returns:
        bool: True is match, else false
    """
    match = DATA_URI_PATTERN.match(data_uri)
    return bool(match)


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
                        f"Failed to create and store content from data URI with error {e}"
                    )

            return val
        return val

    return _visit(vals)


R = TypeVar("R", bound=CallStartReq | CallEndReq)


def process_call_req_to_content(
    req: R,
    trace_server: TraceServerInterface,
) -> R:
    """Process call inputs/outputs to replace base64 content.

    This is the main entry point for processing trace data before insertion.

    Args:
        data: Input or output data from a call
        project_id: Project ID for storage
        trace_server: Trace server instance

    Returns:
        Tuple of (processed_data, list_of_refs) with base64 content replaced by Content objects
    """
    if isinstance(req, CallStartReq):
        req.start.inputs = replace_base64_with_content_objects(
            req.start.inputs, req.start.project_id, trace_server
        )
    else:
        req.end.output = req.end.output = replace_base64_with_content_objects(
            req.end.output, req.end.project_id, trace_server
        )

    return req
