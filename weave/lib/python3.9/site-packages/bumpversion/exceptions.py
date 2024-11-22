"""Custom exceptions for BumpVersion."""

from typing import Optional

from click import Context, UsageError


class BumpVersionError(UsageError):
    """Custom base class for all BumpVersion exception types."""

    def __init__(self, message: str, ctx: Optional[Context] = None):
        self.message = message
        self.ctx = ctx


class FormattingError(BumpVersionError):
    """We are unable to represent a version required by a format."""

    pass


class MissingValueError(BumpVersionError):
    """A part required for a version format is empty."""

    pass


class DirtyWorkingDirectoryError(BumpVersionError):
    """The working directory is dirty, and it is not allowed."""

    pass


class SignedTagsError(BumpVersionError):
    """The VCS does not support signed tags."""

    pass


class VersionNotFoundError(BumpVersionError):
    """A version number was not found in a source file."""

    pass


class InvalidVersionPartError(BumpVersionError):
    """The specified part (e.g. 'bugfix') was not found."""

    pass


class ConfigurationError(BumpVersionError):
    """A configuration key-value is missing or in the wrong type."""

    pass


class BadInputError(BumpVersionError):
    """User input was bad."""

    pass


class HookError(BumpVersionError):
    """A hook failed."""

    pass
