"""Utils for creating object payloads that are similar to what the SDK would create."""

from __future__ import annotations

from typing import Any

OP_SOURCE_FILE_NAME = "obj.py"
PLACEHOLDER_OP_SOURCE = """def func(*args, **kwargs):
    ... # Code-capture unavailable for this op
"""


def build_op_val(file_digest: str, load_op: str | None = None) -> dict[str, Any]:
    """Build the op value structure with a file digest (post-file-upload).

    This creates the structure that matches what the SDK produces after file upload,
    where the files dict contains digest strings rather than content bytes.

    Args:
        file_digest: The digest of the uploaded source file
        load_op: Optional URI of the load_op (for non-Op custom types)

    Returns:
        Dictionary with the complete structure for an Op object ready for storage

    Examples:
        >>> result = build_op_val_with_file_digest("abc123")
        >>> result["files"][OP_SOURCE_FILE_NAME]
        'abc123'
    """
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "Op"},
        "files": {OP_SOURCE_FILE_NAME: file_digest},
    }
    if load_op is not None:
        result["load_op"] = load_op
    return result
