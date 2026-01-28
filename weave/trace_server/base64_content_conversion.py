"""Base64 content conversion utilities for trace server.

This module handles automatic detection and replacement of base64 encoded content
with content objects stored in bucket storage.
"""

import json
import logging
import re
from typing import Any, TypeVar

import ddtrace

from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndV2Req,
    CallStartReq,
    CompletedCallSchemaForInsert,
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
    source: str = "unknown",
) -> dict[str, Any]:
    """Create a proper Content object structure and store its files.

    Args:
        content_obj: Content object to store.
        project_id: Project ID for storage.
        trace_server: Trace server instance for file storage.
        source: Source of content ("data_uri" or "base64").

    Returns:
        Dict representing the Content object in the proper format.
    """
    content_data = content_obj.data
    content_size = len(content_data)
    content_metadata = json.dumps(content_obj.model_dump(exclude={"data"})).encode(
        "utf-8"
    )

    set_current_span_dd_tags(
        {
            "content.source": source,
            "content.mimetype": content_obj.mimetype or "unknown",
            "content.size_bytes": content_size,
        }
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


@ddtrace.tracer.wrap(name="replace_base64_with_content_objects")
def replace_base64_with_content_objects(
    vals: T,
    project_id: str,
    trace_server: TraceServerInterface,
) -> tuple[T, dict[str, int]]:
    """Recursively replace base64 content with Content objects.

    Follows the same pattern as extract_refs_from_values, visiting all values
    and replacing base64 content where found.

    Args:
        vals: Value to process (can be dict, list, or primitive).
        project_id: Project ID for storage.
        trace_server: Trace server instance for file storage.

    Returns:
        Tuple of (processed_value, stats_dict).
    """
    stats = {
        "strings_checked": 0,
        "data_uri_converted": 0,
        "base64_converted": 0,
    }

    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            result = {}
            for k, v in val.items():
                result[k] = _visit(v)
            return result
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str) and len(val) > AUTO_CONVERSION_MIN_SIZE:
            stats["strings_checked"] += 1
            # Check for data URI pattern first
            if is_data_uri(val):
                try:
                    result = store_content_object(
                        Content.from_data_url(val),
                        project_id,
                        trace_server,
                        source="data_uri",
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to create and store content from data URI with error {e}"
                    )
                else:
                    stats["data_uri_converted"] += 1
                    return result

            if is_base64(val):
                try:
                    # All we care about here is if this is an object that we can handle in some way.
                    # 'aaaa' is valid base64 and will come out as text/plain
                    # More complicated false positives or failed detections will show 'application/octet-stream'
                    # The uncovered scenario is if a user has encoded a plaintext document as Base64
                    # We don't handle text content objects in a special way on the clients, so this is acceptable.
                    content: Content[Any] = Content.from_base64(val)
                except Exception as e:
                    logger.warning(
                        f"Failed to create content from standalone base64: {e}"
                    )
                else:
                    if content.mimetype not in (
                        "text/plain",
                        "application/octet-stream",
                    ):
                        result = store_content_object(
                            content,
                            project_id,
                            trace_server,
                            source="base64",
                        )
                        stats["base64_converted"] += 1
                        return result

            return val
        return val

    result = _visit(vals)
    set_current_span_dd_tags(
        {
            "traverse.strings_checked": stats["strings_checked"],
            "traverse.data_uri_converted": stats["data_uri_converted"],
            "traverse.base64_converted": stats["base64_converted"],
            "traverse.total_converted": stats["data_uri_converted"]
            + stats["base64_converted"],
        }
    )
    return result, stats


R = TypeVar("R", bound=CallStartReq | CallEndReq | CallEndV2Req)


@ddtrace.tracer.wrap(name="process_call_req_to_content")
def process_call_req_to_content(
    req: R,
    trace_server: TraceServerInterface,
) -> R:
    """Process call inputs/outputs to replace base64 content.

    This is the main entry point for processing trace data before insertion.

    Args:
        req: Call request (start, end, or end v2).
        trace_server: Trace server instance.

    Returns:
        Request with base64 content replaced by Content objects.
    """
    if isinstance(req, CallStartReq):
        set_current_span_dd_tags({"req_type": "call_start"})
        req.start.inputs, _ = replace_base64_with_content_objects(
            req.start.inputs, req.start.project_id, trace_server
        )
    elif isinstance(req, (CallEndReq, CallEndV2Req)):
        req_type = "call_end_v2" if isinstance(req, CallEndV2Req) else "call_end"
        set_current_span_dd_tags({"req_type": req_type})
        req.end.output, _ = replace_base64_with_content_objects(
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
    set_current_span_dd_tags({"req_type": "complete_call"})
    complete_call.inputs, input_stats = replace_base64_with_content_objects(
        complete_call.inputs, complete_call.project_id, trace_server
    )
    complete_call.output, output_stats = replace_base64_with_content_objects(
        complete_call.output, complete_call.project_id, trace_server
    )
    set_current_span_dd_tags(
        {
            "total.strings_checked": input_stats["strings_checked"]
            + output_stats["strings_checked"],
            "total.converted": (
                input_stats["data_uri_converted"]
                + input_stats["base64_converted"]
                + output_stats["data_uri_converted"]
                + output_stats["base64_converted"]
            ),
        }
    )
    return complete_call
