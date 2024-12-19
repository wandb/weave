# always use lowercase keys for the redact keys
REDACT_KEYS = (
    "api_key",
    "auth_headers",
    "authorization",
)
REDACTED_VALUE = "REDACTED"


def should_redact(key: str) -> bool:
    return key.lower() in REDACT_KEYS
