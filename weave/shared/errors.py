"""Exception types shared between the Weave client and trace server.

The server-side error registry (HTTP status mapping, response formatting)
lives in ``weave.trace_server.errors``; this module holds only the exception
classes themselves so client code can catch them without importing the server
package.
"""

import datetime

# =============================================================================
# Error Codes - Machine-readable codes for client-side error detection
# =============================================================================


class ErrorCode:
    """Machine-readable error codes for client detection.

    These codes are included in error responses to allow clients to programmatically
    identify specific error conditions without parsing human-readable messages.
    """

    CALLS_COMPLETE_MODE_REQUIRED = "CALLS_COMPLETE_MODE_REQUIRED"


# =============================================================================
# Exception Classes
# =============================================================================


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class RequestTooLarge(Error):
    """Raised when a request is too large."""

    pass


class InvalidRequest(Error):
    """Raised when a request is invalid."""

    pass


class ObjectNameTypeCollision(InvalidRequest):
    """Raised when obj_create targets an object_id already bound to a different base_object_class.

    Object names are bound to one type per project (WB-30574). Weave refs do not
    carry type, so allowing same-name different-type would make refs ambiguous.
    """

    def __init__(
        self,
        object_id: str,
        kind: str,
        new_base_object_class: str | None,
        existing_base_object_classes: list[str | None],
    ):
        self.object_id = object_id
        self.kind = kind
        self.new_base_object_class = new_base_object_class
        self.existing_base_object_classes = existing_base_object_classes
        existing_labels = [
            _describe_object_class(c) for c in existing_base_object_classes
        ]
        existing_desc = " or ".join(dict.fromkeys(existing_labels))
        super().__init__(
            f"Cannot publish {object_id!r} as {_describe_object_class(new_base_object_class)}: "
            f"that name is already used by {existing_desc} in this project. "
            f"Object versions cannot share types, publish this object under a different name."
        )


class CallsCompleteModeRequired(InvalidRequest):
    """Raised when project requires calls_complete mode but SDK is using legacy mode.

    This exception includes a machine-readable error_code that clients can use to
    detect this specific error condition and automatically switch modes.
    """

    error_code: str = ErrorCode.CALLS_COMPLETE_MODE_REQUIRED

    def __init__(self, project_id: str, min_sdk_version: str = "0.52.26"):
        """Initialize the exception.

        Args:
            project_id: The project ID that requires calls_complete mode.
            min_sdk_version: The minimum SDK version required.
        """
        self.project_id = project_id
        self.min_sdk_version = min_sdk_version
        super().__init__(
            f"The project '{project_id}' has been created in the more performant 'complete' mode. "
            f"Please upgrade your SDK to at least: {min_sdk_version} to write to this project."
        )


# Clickhouse errors
class QueryMemoryLimitExceededError(Error):
    """Raised when a query memory limit is exceeded."""

    pass


class QueryNoCommonTypeError(Error):
    """Raised when a query has no common type."""

    pass


class QueryIllegalTypeofArgumentError(Error):
    """Raised when a query has an illegal type of argument."""

    pass


class BadQueryParameterError(Error):
    """Raised when a query parameter is invalid."""

    pass


class QueryTimeoutExceededError(Error):
    """Raised when a query timeout is exceeded."""

    pass


class InsertTooLarge(Error):
    """Raised when a single insert is too large."""

    pass


class LightweightUpdateNotAllowedError(Error):
    """Raised when ClickHouse lightweight updates are not enabled."""

    pass


# User error
class InvalidFieldError(Error):
    """Raised when a field is invalid."""

    pass


class NotFoundError(Error):
    """Raised when a general not found error occurs."""

    pass


class MissingLLMApiKeyError(Error):
    """Raised when a LLM API key is missing for completion."""

    def __init__(self, message: str, api_key_name: str):
        self.api_key_name = api_key_name
        super().__init__(message)


class ObjectDeletedError(Error):
    """Raised when an object has been deleted."""

    def __init__(self, message: str, deleted_at: datetime.datetime):
        self.deleted_at = deleted_at
        super().__init__(message)


class InvalidExternalRef(Error):
    """Raised when an external reference is invalid."""

    pass


class DigestMismatchError(Error):
    """Raised when a client-provided digest does not match the server-computed digest."""

    pass


class ProjectNotFound(Error):
    """Raised when a project is not found."""

    pass


class InvalidIdFormat(Exception):
    pass


class RunNotFound(Exception):
    pass


def _describe_object_class(base_object_class: str | None) -> str:
    """Human-readable label for a base_object_class (None = an untyped object)."""
    if base_object_class is None:
        return "a generic (untyped) object"
    return f"a {base_object_class}"
