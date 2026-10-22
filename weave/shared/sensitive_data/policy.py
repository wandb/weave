"""Closed deployment policy for trace-ingest sensitive-data handling."""

import warnings
from enum import Enum

# TODO: delete this module together with weave.shared.
warnings.warn(
    "weave.shared.sensitive_data.policy is deprecated and will be removed in a "
    "future release.",
    FutureWarning,
    stacklevel=2,
)


class SensitiveDataPolicy(str, Enum):
    OFF = "off"
    PII_V1 = "pii-v1"


def pii_enabled(policy: SensitiveDataPolicy) -> bool:
    if policy is SensitiveDataPolicy.OFF:
        return False
    if policy is SensitiveDataPolicy.PII_V1:
        return True
    raise ValueError(f"Unknown sensitive-data policy: {policy!r}")
