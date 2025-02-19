from typing import Optional


class Error(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message: Optional[str] = None, status_code: int = 500):
        self.message = message
        self.status_code = status_code


class RequestTooLarge(Error):
    """Raised when a request is too large."""

    def __init__(
        self, message: Optional[str] = "Request too large", status_code: int = 413
    ):
        super().__init__(message, status_code)


class InvalidRequest(Error):
    """Raised when a request is invalid."""

    def __init__(self, message: Optional[str] = None, status_code: int = 422):
        super().__init__(message, status_code)


class InsertTooLarge(Error):
    """Raised when a single insert is too large."""

    def __init__(self, message: Optional[str] = None, status_code: int = 413):
        super().__init__(message, status_code)


class InvalidFieldError(Error):
    """Raised when a field is invalid."""

    def __init__(self, message: Optional[str] = None, status_code: int = 403):
        super().__init__(message, status_code)


class MissingLLMApiKeyError(Error):
    """Raised when a LLM API key is missing for completion."""

    def __init__(self, message: str, api_key: str, status_code: int = 400):
        self.api_key = api_key
        super().__init__(message, status_code)


class NotFoundError(Error):
    """Raised when a general not found error occurs."""

    def __init__(self, message: Optional[str] = None, status_code: int = 404):
        super().__init__(message, status_code)


class ObjectDeletedError(Error):
    """Raised when an object has been deleted."""

    def __init__(self, message: str, deleted_at: str, status_code: int = 404):
        self.deleted_at = deleted_at
        super().__init__(message, status_code)


class ProjectNotFound(Error):
    """Raised when a project is not found."""

    def __init__(self, message: Optional[str] = None, status_code: int = 404):
        super().__init__(message, status_code)


class RunNotFound(Error):
    """Raised when a run is not found."""

    def __init__(self, message: Optional[str] = None, status_code: int = 404):
        super().__init__(message, status_code)


class InvalidIdFormat(Error):
    """Raised when an ID is not in the correct format."""

    def __init__(self, message: Optional[str] = None, status_code: int = 400):
        super().__init__(message, status_code)


class InvalidExternalRef(Error):
    """Raised when an external reference is invalid."""

    def __init__(self, message: Optional[str] = None, status_code: int = 400):
        super().__init__(message, status_code)


class InvalidInternalRef(Error):
    """Raised when an internal reference is invalid."""

    def __init__(self, message: Optional[str] = None, status_code: int = 400):
        super().__init__(message, status_code)
