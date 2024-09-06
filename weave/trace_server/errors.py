class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class RequestTooLarge(Error):
    """Raised when a request is too large."""

    pass


class InvalidRequest(Error):
    """Raised when a request is invalid."""

    pass


class ObjectDeletedError(Error):
    """Raised when an object has been deleted."""

    pass


class NotFoundError(Error):
    """Raised when not found."""

    pass
