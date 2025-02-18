from weave.trace import settings

# always use lowercase keys for the redact keys
REDACT_KEYS = (
    "api_key",
    "auth_headers",
    "authorization",
)
REDACTED_VALUE = "REDACTED"


def should_redact(key: str) -> bool:
    return key.lower() in settings.redact_keys()


def get_redacted_value() -> str:
    return settings.redacted_value()
