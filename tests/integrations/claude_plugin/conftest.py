"""Pytest configuration for claude_plugin tests."""

import pytest


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio is not installed)."""
    return "asyncio"
