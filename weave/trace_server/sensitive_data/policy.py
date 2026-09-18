"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.sensitive_data.policy import (
    Enum,
    SensitiveDataPolicy,
    pii_enabled,
)

__all__ = ["Enum", "SensitiveDataPolicy", "pii_enabled"]
