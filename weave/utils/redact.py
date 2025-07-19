# always use lowercase keys for the redact keys
from typing import Any

REDACT_KEYS = (
    "api_key",
    "auth_headers",
    "authorization",
)
REDACTED_VALUE = "REDACTED"


def should_redact(key: str) -> bool:
    return key.lower() in REDACT_KEYS


def redact_sensitive_keys_recursively(obj: Any) -> Any:
    if isinstance(obj, dict):
        dict_res = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                dict_res[k] = REDACTED_VALUE
            else:
                dict_res[k] = redact_sensitive_keys_recursively(v)
        return dict_res

    elif isinstance(obj, list):
        list_res = []
        for v in obj:
            list_res.append(redact_sensitive_keys_recursively(v))
        return list_res

    elif isinstance(obj, tuple):
        tuple_res = []
        for v in obj:
            tuple_res.append(redact_sensitive_keys_recursively(v))
        return tuple(tuple_res)

    # Return the original object for non-container types
    return obj
