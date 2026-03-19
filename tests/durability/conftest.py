from __future__ import annotations

import pytest

from weave.durability import wal_consumer


@pytest.fixture(autouse=True)
def _clear_active_consumers() -> None:
    """Reset the active-consumer tracking set between tests."""
    wal_consumer._active_consumers.clear()
