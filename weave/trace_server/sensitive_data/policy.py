"""Closed deployment policy for trace-ingest sensitive-data handling."""

from enum import Enum


class SensitiveDataPolicy(str, Enum):
    OFF = "off"
    PII_V1 = "pii-v1"
