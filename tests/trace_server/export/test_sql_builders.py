"""SQL builders: parameter shape, identifier safety, settings inlining."""

import uuid
from datetime import datetime, timezone

import pytest

from weave.trace_server.export import sql
from weave.trace_server.export.constants import (
    MAX_EXPORT_QUERY_SECONDS,
    PARQUET_COMPRESSION,
)

JOB = uuid.UUID("11111111-2222-3333-4444-555555555555")


class TestInsertSql:
    def test_includes_project_id_param_only(self) -> None:
        prepared = sql.build_export_insert_sql(
            job_id=JOB, table="calls_complete", project_id="UHJvajEyMw=="
        )
        assert "{project_id:String}" in prepared.sql
        assert prepared.params == {"project_id": "UHJvajEyMw=="}

    def test_adds_time_predicates_when_range_present(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 2, 1, tzinfo=timezone.utc)
        prepared = sql.build_export_insert_sql(
            job_id=JOB,
            table="calls_complete",
            project_id="proj",
            time_start=start,
            time_end=end,
        )
        assert "{start_ts:DateTime64(3)}" in prepared.sql
        assert "{end_ts:DateTime64(3)}" in prepared.sql
        assert prepared.params["start_ts"] == start
        assert prepared.params["end_ts"] == end

    def test_uses_registry_identifiers_not_user_input(self) -> None:
        # Identifier-injection attempt: user supplies a table name with a
        # semicolon-suffix. The Literal[...] type constraint should already
        # have rejected this upstream, but the builder must not pass it
        # through either.
        with pytest.raises(KeyError):
            sql.build_export_insert_sql(
                job_id=JOB,
                table="calls_complete; DROP TABLE calls_complete; --",  # type: ignore[arg-type]
                project_id="proj",
            )

    def test_settings_clause_inlines_constants(self) -> None:
        prepared = sql.build_export_insert_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert f"max_execution_time = {MAX_EXPORT_QUERY_SECONDS}" in prepared.sql
        assert (
            f"output_format_parquet_compression_method = '{PARQUET_COMPRESSION}'"
            in prepared.sql
        )
        assert "s3_truncate_on_insert = 1" in prepared.sql

    def test_references_nc_by_name_not_credentials(self) -> None:
        prepared = sql.build_export_insert_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert "access_key_id" not in prepared.sql
        assert "secret_access_key" not in prepared.sql
        assert "session_token" not in prepared.sql
        assert JOB.hex in prepared.sql

    @pytest.mark.parametrize("table", ["calls_complete", "calls_merged"])
    def test_tier_1_tables_both_supported(self, table: str) -> None:
        prepared = sql.build_export_insert_sql(
            job_id=JOB,
            table=table,
            project_id="proj",  # type: ignore[arg-type]
        )
        assert f"FROM {table}" in prepared.sql


class TestPreflightCountSql:
    def test_count_returns_only_one_aggregation(self) -> None:
        prepared = sql.build_preflight_count_sql(
            table="calls_complete", project_id="proj"
        )
        assert "count()" in prepared.sql
        assert "FROM calls_complete" in prepared.sql
        assert prepared.params == {"project_id": "proj"}


class TestQueryLogLookup:
    def test_orders_by_event_time_descending(self) -> None:
        prepared = sql.build_query_log_lookup_sql()
        assert "ORDER BY event_time_microseconds DESC" in prepared.sql
        assert "LIMIT 1" in prepared.sql
        assert "{query_id:String}" in prepared.sql


class TestOrphanNcScan:
    def test_filters_to_export_prefix(self) -> None:
        prepared = sql.build_orphan_nc_scan_sql()
        assert "system.named_collections" in prepared.sql
        assert "'export\\_%'" in prepared.sql
        assert prepared.params == {}
