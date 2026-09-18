"""Closed deployment policy for trace-ingest sensitive-data handling."""

from enum import Enum


class SensitiveDataPolicy(str, Enum):
    OFF = "off"
    PII_V1 = "pii-v1"


def pii_enabled(policy: SensitiveDataPolicy) -> bool:
    if policy is SensitiveDataPolicy.OFF:
        return False
    if policy is SensitiveDataPolicy.PII_V1:
        return True
    raise ValueError(f"Unknown sensitive-data policy: {policy!r}")
