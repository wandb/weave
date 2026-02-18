"""Shared test utilities for trace tests."""

from __future__ import annotations


class FailingSaveType:
    """A type whose serializer save function always raises an exception."""

    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:
        return f"FailingSaveType({self.value!r})"


def failing_save(obj, artifact, name):
    """A save function that always raises an exception."""
    raise RuntimeError("Intentional failure in save function")


def failing_load(artifact, name, val):
    """A load function (not used in these tests)."""
    return FailingSaveType(val)
