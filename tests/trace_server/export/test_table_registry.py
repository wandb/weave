"""Every `ExportTable` literal must have a registry row.

Adding a new literal without a registry row should fail at import time,
not return a 500 mid-request.
"""

from typing import get_args

from weave.trace_server.export.schemas import ExportTable
from weave.trace_server.export.table_registry import (
    TABLE_REGISTRY,
    assert_registry_covers_literal,
)


def test_registry_covers_every_literal() -> None:
    assert set(TABLE_REGISTRY.keys()) == set(get_args(ExportTable))
    # idempotent check passes
    assert_registry_covers_literal()


def test_calls_complete_uses_started_at() -> None:
    spec = TABLE_REGISTRY["calls_complete"]
    assert spec.ch_table == "calls_complete"
    assert spec.time_column == "started_at"
    assert spec.project_id_column == "project_id"


def test_calls_merged_uses_started_at() -> None:
    """`calls_merged` is supported at parity with `calls_complete` (spec §goal)."""
    spec = TABLE_REGISTRY["calls_merged"]
    assert spec.ch_table == "calls_merged"
    assert spec.time_column == "started_at"
    assert spec.project_id_column == "project_id"
