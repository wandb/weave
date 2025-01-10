# always use lowercase keys for the redact keys
from collections.abc import Iterable

DEFAULT_REDACT_KEYS = {
    "api_key",
    "auth_headers",
    "authorization",
}
DEFAULT_REDACTED_VALUE = "REDACTED"

_redact_keys: set[str]
_redacted_value: str


def configure_redaction(
    keys: Iterable[str] = DEFAULT_REDACT_KEYS,
    redacted_value: str = DEFAULT_REDACTED_VALUE,
):
    # Should this be on the settings object?
    global _redact_keys, _redacted_value

    _redact_keys = set(keys)
    _redacted_value = redacted_value


def should_redact(key: str) -> bool:
    return key.lower() in _redact_keys
