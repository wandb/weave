class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class RequestTooLarge(Error):
    """Raised when a request is too large."""

    pass


class InvalidRequest(Error):
    """Raised when a request is invalid."""

    pass


class InsertTooLarge(Error):
    """Raised when a single insert is too large."""

    pass


class InvalidFieldError(Error):
    """Raised when a field is invalid."""

    pass
