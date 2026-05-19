"""Tests for the dogstatsd-backed DB insert counter helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from weave.trace_server.datadog import (
    DB_INSERT_METRIC,
    DB_INSERT_PATH_UNKNOWN,
    db_insert_path,
    record_db_insert,
    tag_db_insert_path,
)


@pytest.fixture
def mock_statsd():
    with patch("weave.trace_server.datadog._dogstatsd_client") as m:
        yield m.return_value


def test_record_db_insert_emits_with_path_and_table_and_skips_zero(mock_statsd):
    # No path set -> "unknown"; explicit path overrides contextvar; nested
    # `db_insert_path` is a no-op (outermost wins) so the metric still
    # reflects the originating ingestion route.
    record_db_insert(table="calls_complete", count=3)

    with db_insert_path("otel_export"):
        record_db_insert(table="call_parts", count=10)
        with db_insert_path("ignored_inner"):
            record_db_insert(table="object_versions", count=2)

    # Explicit path arg wins over contextvar.
    with db_insert_path("call_start"):
        record_db_insert(table="call_parts", count=1, path="override")

    # Zero / negative counts are dropped; we don't want phantom emissions.
    record_db_insert(table="files", count=0)
    record_db_insert(table="files", count=-5)

    assert mock_statsd.increment.call_args_list == [
        (
            (DB_INSERT_METRIC,),
            {
                "value": 3,
                "tags": [
                    "table:calls_complete",
                    f"path:{DB_INSERT_PATH_UNKNOWN}",
                ],
            },
        ),
        (
            (DB_INSERT_METRIC,),
            {"value": 10, "tags": ["table:call_parts", "path:otel_export"]},
        ),
        (
            (DB_INSERT_METRIC,),
            {"value": 2, "tags": ["table:object_versions", "path:otel_export"]},
        ),
        (
            (DB_INSERT_METRIC,),
            {"value": 1, "tags": ["table:call_parts", "path:override"]},
        ),
    ]


def test_tag_db_insert_path_decorator_propagates(mock_statsd):
    @tag_db_insert_path("call_start_batch")
    def outer():
        record_db_insert(table="call_parts", count=1)
        inner()

    @tag_db_insert_path("call_start")
    def inner():
        # Decorator on inner is a no-op when outer already set the path.
        record_db_insert(table="call_parts", count=1)

    outer()

    paths = [
        kw["tags"][1] for _, kw in mock_statsd.increment.call_args_list
    ]
    assert paths == ["path:call_start_batch", "path:call_start_batch"]
