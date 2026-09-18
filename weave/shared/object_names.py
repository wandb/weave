"""Tag and alias validation shared by trace API contracts."""

import re

from weave.shared.errors import InvalidRequest

# --- Tag and Alias validation ---
# Follows W&B Models conventions:
#   - Tags: alphanumeric, hyphens, underscores, single spaces between words,
#     max 256 chars.  Matches W&B Models TAG_REGEX.
#   - Aliases: broad charset, disallow "/" and ":", length 1-128,
#     reserve "latest" and version patterns (v\d+), reject whitespace-only.

MAX_ALIAS_LENGTH = 128
MAX_TAG_LENGTH = 256
TAG_REGEX = re.compile(r"^[-\w]+( [-\w]+)*$")
_INVALID_ALIAS_CHARACTERS = frozenset("/:")
_VERSION_LIKE_PATTERN = re.compile(r"^v\d+$")
_RESERVED_ALIAS_NAMES = {"latest"}


def validate_tag_name(name: str) -> None:
    """Validate a tag name against W&B Models TAG_REGEX.

    Allowed: alphanumeric, hyphens, underscores, single spaces between words.
    Max length: 256 characters.
    """
    if not name:
        raise InvalidRequest("tag name must not be empty")
    if len(name) > MAX_TAG_LENGTH:
        raise InvalidRequest(f"tag name must be at most {MAX_TAG_LENGTH} characters")
    if not TAG_REGEX.match(name):
        raise InvalidRequest(
            f"tag name {name!r} is invalid: only alphanumeric characters, "
            "hyphens, underscores, and single spaces between words are allowed"
        )


def validate_alias_name(name: str) -> None:
    """Validate an alias name. Disallows '/' and ':', reserves 'latest' and version indices."""
    if not name:
        raise InvalidRequest("alias name must not be empty")
    if not name.strip():
        raise InvalidRequest("alias name must not be whitespace-only")
    if len(name) > MAX_ALIAS_LENGTH:
        raise InvalidRequest(
            f"alias name must be at most {MAX_ALIAS_LENGTH} characters"
        )
    for ch in name:
        if ch in _INVALID_ALIAS_CHARACTERS:
            raise InvalidRequest(f"alias name cannot contain character '{ch}'")
    if _VERSION_LIKE_PATTERN.match(name):
        raise InvalidRequest(
            f"alias name '{name}' is reserved (matches version pattern v<number>)"
        )
    if name in _RESERVED_ALIAS_NAMES:
        raise InvalidRequest(f"alias name '{name}' is reserved")
