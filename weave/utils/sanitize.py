# always use lowercase keys for the redact keys
_REDACT_KEYS = {
    "api_key",
    "auth_headers",
    "authorization",
}
REDACTED_VALUE = "REDACTED"


def add_redact_key(key: str) -> None:
    """Add a key to the list of keys that should be redacted.

    Args:
        key: The key name to add to the redaction list.
             The key will be matched case-insensitively.

    Example:
        >>> import weave
        >>> from weave.utils import sanitize
        >>> weave.init("my-project", settings={"redact_pii": True})
        >>> sanitize.add_redact_key("token")
        >>> sanitize.add_redact_key("client_id")
    """
    _REDACT_KEYS.add(key.lower())


def remove_redact_key(key: str) -> None:
    """Remove a key from the list of keys that should be redacted.

    Args:
        key: The key name to remove from the redaction list.

    Note:
        This will not remove the default keys (api_key, auth_headers, authorization)
        unless explicitly called.
    """
    _REDACT_KEYS.discard(key.lower())


def get_redact_keys() -> set[str]:
    """Get a copy of the current set of keys that will be redacted.

    Returns:
        A copy of the set of keys that will be redacted.

    Examples:
        >>> from weave.utils import sanitize
        >>> keys = sanitize.get_redact_keys()
        >>> "api_key" in keys
        True
    """
    return _REDACT_KEYS.copy()


def should_redact(key: str) -> bool:
    """Return whether a given key should be redacted.

    Args:
        key: The key name to check.

    Returns:
        True if the key is configured to be redacted (case-insensitive), False otherwise.

    Examples:
        >>> from weave.utils import sanitize
        >>> sanitize.should_redact("API_KEY")
        True
        >>> sanitize.should_redact("random_key")
        False
    """
    return key.lower() in _REDACT_KEYS


# Note: No backward-compatibility alias is exposed; use add/remove/get helpers.
