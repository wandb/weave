"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.ids import (
    _generate_uuidv7_bytes,
    generate_id,
    os,
    time,
)

__all__ = ["_generate_uuidv7_bytes", "generate_id", "os", "time"]
