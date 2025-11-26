"""Utilities for handling base class names in serialization.

These are shared between the client (weave.trace) and server (weave.trace_server)
to ensure consistent handling of class hierarchies during serialization.
"""

# Classes that should be filtered out when computing _bases for backward compatibility.
# When classes inherit from Generic[T], Python's MRO includes Generic, but we exclude
# it to maintain consistent _bases serialization and digest computation.
IGNORED_BASE_CLASS_NAMES = frozenset({"Generic"})
