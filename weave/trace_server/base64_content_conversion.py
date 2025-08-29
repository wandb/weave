"""Base64 content conversion utilities for trace server.

This module handles automatic detection and replacement of base64 encoded content
with content objects stored in bucket storage.
"""

import base64
import logging
import re
from typing import Any, Optional, Tuple, TypeVar

from weave.trace_server.trace_server_interface import (
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

# Maximum size for base64 content to be processed (to avoid memory issues)
MAX_BASE64_SIZE = 100 * 1024 * 1024  # 100 MB

# Minimum size for standalone base64 (to avoid false positives)
MIN_BASE64_SIZE = 100  # 100 bytes


def is_valid_base64(value: str) -> bool:
    """Check if a string is valid base64.

    Args:
        value: String to check

    Returns:
        True if the string is valid base64
    """
    if not isinstance(value, str):
        return False

    # Check minimum length to avoid false positives
    if len(value) < MIN_BASE64_SIZE:
        return False

    # Check if it matches base64 pattern
    if not BASE64_PATTERN.match(value):
        return False

    # Validate by trying to decode
    try:
        # Check that length is multiple of 4 (with padding)
        if len(value) % 4 != 0:
            return False

        base64.b64decode(value, validate=True)
        return True
    except Exception:
        return False


def extract_data_uri_content(data_uri: str) -> Optional[Tuple[str, bytes, str]]:
    """Extract content type and decoded bytes from a data URI.

    Args:
        data_uri: Data URI string in format data:[content-type];base64,[data]

    Returns:
        Tuple of (content_type, decoded_bytes, original_schema) or None if extraction fails
    """
    match = DATA_URI_PATTERN.match(data_uri)
    if not match:
        return None

    content_type = match.group(1)
    base64_data = match.group(2)

    try:
        # Check size before decoding to avoid memory issues
        estimated_size = len(base64_data) * 3 / 4
        if estimated_size > MAX_BASE64_SIZE:
            logger.warning(
                f"Base64 content too large ({estimated_size} bytes), skipping conversion"
            )
            return None

        decoded_bytes = base64.b64decode(base64_data, validate=True)
        original_schema = f"data:{content_type};base64,{{base64_content}}"
        return content_type, decoded_bytes, original_schema
    except Exception as e:
        logger.warning(f"Failed to decode base64 data from data URI: {e}")
        return None


def extract_standalone_base64(value: str) -> Optional[Tuple[bytes, str]]:
    """Extract decoded bytes from a standalone base64 string.

    Args:
        value: Standalone base64 string

    Returns:
        Tuple of (decoded_bytes, original_schema) or None if extraction fails
    """
    if not is_valid_base64(value):
        return None

    try:
        # Check size before decoding
        estimated_size = len(value) * 3 / 4
        if estimated_size > MAX_BASE64_SIZE:
            logger.warning(
                f"Base64 content too large ({estimated_size} bytes), skipping conversion"
            )
            return None

        decoded_bytes = base64.b64decode(value, validate=True)
        original_schema = "{base64_content}"
        return decoded_bytes, original_schema
    except Exception as e:
        logger.warning(f"Failed to decode standalone base64: {e}")
        return None


def create_content_object(
    data: bytes,
    original_schema: str,
    project_id: str,
    trace_server: TraceServerInterface,
    mimetype: Optional[str] = None,
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
    import json

    content_obj = Content.from_bytes(
        data, mimetype=mimetype, metadata={"_original_schema": original_schema}
    )

    content_data = content_obj.data
    metadata_data = json.dumps(content_obj.model_dump(exclude={"data"})).encode("utf-8")

    # Create files in storage
    # 1. Store the actual content
    content_req = FileCreateReq(
        project_id=project_id, name="content", content=content_data
    )
    content_res = trace_server.file_create(content_req)

    # 2. Store the metadata
    metadata_req = FileCreateReq(
        project_id=project_id, name="metadata.json", content=metadata_data
    )
    metadata_res = trace_server.file_create(metadata_req)

    # We exclude the load op because it isn't possible to get from the server side
    content_obj = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
        "files": {"content": content_res.digest, "metadata.json": metadata_res.digest},
    }

    return content_obj


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
        elif isinstance(val, str):
            # Check for data URI pattern first
            data_uri_content = extract_data_uri_content(val)
            if data_uri_content:
                content_type, decoded_bytes, original_schema = data_uri_content
                try:
                    # Create proper Content object structure
                    content_obj = create_content_object(
                        decoded_bytes,
                        original_schema,
                        project_id,
                        trace_server,
                        content_type,
                    )

                    logger.debug("Replaced data URI with Content object")
                    return content_obj
                except Exception as e:
                    logger.warning(f"Failed to create content from data URI: {e}")
                    return val

            # Check for standalone base64
            standalone_content = extract_standalone_base64(val)
            if standalone_content:
                decoded_bytes, original_schema = standalone_content
                try:
                    # Create proper Content object structure
                    content_obj = create_content_object(
                        decoded_bytes,
                        original_schema,
                        project_id,
                        trace_server,
                        None,  # No mimetype for standalone base64
                    )

                    logger.debug("Replaced standalone base64 with Content object")
                    return content_obj
                except Exception as e:
                    logger.warning(
                        f"Failed to create content from standalone base64: {e}"
                    )
                    return val

            return val
        else:
            return val

    return _visit(vals)


def process_call_inputs_outputs(
    data: T,
    project_id: str,
    trace_server: TraceServerInterface,
) -> T:
    """Process call inputs/outputs to replace base64 content.

    This is the main entry point for processing trace data before insertion.

    Args:
        data: Input or output data from a call
        project_id: Project ID for storage
        trace_server: Trace server instance

    Returns:
        Tuple of (processed_data, list_of_refs) with base64 content replaced by Content objects
    """
    processed_data = replace_base64_with_content_objects(data, project_id, trace_server)

    return processed_data


def reconstruct_base64_from_refs(
    vals: Any,
    project_id: str,
    trace_server: TraceServerInterface,
) -> Any:
    """Recursively reconstruct base64 content from content references.

    Only reconstructs content that has _original_schema metadata, indicating
    it was originally base64 that we converted. Native Content objects are not
    reconstructed.

    Args:
        vals: Value to process (can be dict, list, or primitive)
        project_id: Project ID for storage
        trace_server: Trace server instance for file retrieval

    Returns:
        Processed value with content references replaced by base64 where applicable
    """

    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            result = {}
            for k, v in val.items():
                result[k] = _visit(v)
            return result
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str) and val.startswith("weave-internal:///"):
            # Check if this is a content reference we created
            try:
                # Parse the reference to get the digest
                # Format: weave-internal:///{project_id}/file/{digest}
                parts = val.split("/")
                if len(parts) >= 5 and parts[3] == "file":
                    ref_project_id = parts[2]
                    digest = parts[4]

                    # Only process if it's from the same project
                    if ref_project_id != project_id:
                        return val

                    # Read the file content and metadata
                    from weave.trace_server.trace_server_interface import (
                        FileContentReadReq,
                    )

                    file_req = FileContentReadReq(
                        project_id=project_id,
                        digest=digest,
                    )

                    try:
                        file_res = trace_server.file_content_read(file_req)
                        content_bytes = file_res.content

                        # Try to read the metadata to check for _original_schema
                        # This would require reading the metadata.json if stored separately
                        # For now, we'll need to store this information differently
                        # or pass it through somehow. Let's check if we can detect
                        # by trying to read associated metadata

                        # Since we don't have direct access to metadata here,
                        # we'll need a different approach. For now, return as-is.
                        # This will be enhanced when we have metadata storage.
                        return val

                    except Exception:
                        # If we can't read the file, leave the reference as-is
                        return val

            except Exception:
                pass

            return val
        else:
            return val

    return _visit(vals)


def reconstruct_base64_from_refs_with_metadata(
    vals: Any,
    project_id: str,
    trace_server: TraceServerInterface,
    refs_metadata: dict[str, dict[str, Any]],
) -> Any:
    """Recursively reconstruct base64 content from content references using metadata.

    This version uses pre-fetched metadata to determine which refs should be
    reconstructed to their original base64 format.

    Args:
        vals: Value to process (can be dict, list, or primitive)
        project_id: Project ID for storage
        trace_server: Trace server instance for file retrieval
        refs_metadata: Dict mapping content refs to their metadata

    Returns:
        Processed value with content references replaced by base64 where applicable
    """

    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            result = {}
            for k, v in val.items():
                result[k] = _visit(v)
            return result
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str) and val.startswith("weave-internal:///"):
            # Check if we have metadata for this ref
            metadata = refs_metadata.get(val, {})
            original_schema = metadata.get("_original_schema")

            if not original_schema:
                # No original schema means this was not converted from base64
                return val

            try:
                # Parse the reference to get the digest
                parts = val.split("/")
                if len(parts) >= 5 and parts[3] == "file":
                    digest = parts[4]

                    # Read the file content
                    from weave.trace_server.trace_server_interface import (
                        FileContentReadReq,
                    )

                    file_req = FileContentReadReq(
                        project_id=project_id,
                        digest=digest,
                    )

                    file_res = trace_server.file_content_read(file_req)
                    content_bytes = file_res.content

                    # Reconstruct based on the original schema
                    if original_schema == "{base64_content}":
                        # Standalone base64
                        return base64.b64encode(content_bytes).decode("ascii")
                    elif (
                        original_schema.startswith("data:")
                        and "{base64_content}" in original_schema
                    ):
                        # Data URI format
                        b64_content = base64.b64encode(content_bytes).decode("ascii")
                        return original_schema.replace("{base64_content}", b64_content)

            except Exception as e:
                logger.warning(f"Failed to reconstruct base64 from ref {val}: {e}")

            return val
        else:
            return val

    return _visit(vals)
