"""Common exceptions used by both trace client and server.

This module contains exceptions that are shared between the client and server
to avoid circular dependencies and unnecessary requirements.
"""

import datetime


class ObjectDeletedError(Exception):
    """Raised when an object has been deleted."""

    def __init__(self, message: str, deleted_at: datetime.datetime):
        self.deleted_at = deleted_at
        super().__init__(message)
