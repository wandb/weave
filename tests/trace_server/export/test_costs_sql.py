"""Tier 2 cost-join SQL builder.

The output is one Parquet row per `(call, model)`; the GROUP BY from
`token_costs.py` is intentionally dropped. The ranking subquery must
prefer project-level over default pricing, prefer prices effective at or
before the call's started_at, and drop calls with no model key in
`summary.usage` (no `weave_dummy_llm_id` pollution).
"""

import uuid
from datetime import datetime, timezone
from typing import cast

import pytest

from weave.trace_server.export.costs_sql import (
    DUMMY_LLM_ID,
    LLM_TOKEN_PRICES_TABLE,
    build_cost_join_export_sql,
)
from weave.trace_server.export.schemas import ExportTable

JOB = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class TestCostJoinShape:
    def test_select_passes_through_all_call_columns(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        # `ranked.* EXCEPT (usage_raw, kv, rnk)` keeps every raw call column
        # plus the derived per-model columns and the joined price columns.
        assert "ranked.* EXCEPT (usage_raw, kv, rnk)" in prepared.sql

    def test_join_attaches_price_columns(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        for col in [
            "prompt_token_cost",
            "completion_token_cost",
            "cache_read_input_token_cost",
            "cache_creation_input_token_cost",
            "prompt_token_cost_unit",
            "completion_token_cost_unit",
            "effective_date",
            "pricing_level",
        ]:
            assert f"ltp.{col}" in prepared.sql

    def test_join_left_keeps_calls_without_price_rows(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert "LEFT JOIN" in prepared.sql

    def test_no_group_by_in_export_path(self) -> None:
        """v1 contract: one row per (call, model). GROUP BY is dropped."""
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert "GROUP BY" not in prepared.sql.upper()

    def test_filters_dummy_llm_id(self) -> None:
        """Calls with empty/malformed `summary.usage` must be dropped, not
        emitted with the `weave_dummy_llm_id` sentinel.
        """
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert f"ranked.llm_id != '{DUMMY_LLM_ID}'" in prepared.sql

    def test_pricing_rank_prefers_project_over_default(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        # Project override beats default beats nothing.
        assert "pricing_level = 'project'" in prepared.sql
        assert "pricing_level = 'default'" in prepared.sql
        # `rnk = 1` selects the best-matching row.
        assert "ranked.rnk = 1" in prepared.sql

    def test_rank_respects_started_at_versus_effective_date(self) -> None:
        """Mirror token_costs.py: prices live-at-call-time outrank later ones."""
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert "lu.started_at >= ltp.effective_date" in prepared.sql

    def test_rank_partition_is_per_call_per_model(self) -> None:
        """One row per (call, model) requires PARTITION BY (id, llm_id)."""
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert "PARTITION BY lu.id, lu.llm_id" in prepared.sql

    def test_only_project_id_is_parameterized(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="UHJvajEyMw=="
        )
        # `project_id` flows through CH parameter substitution.
        assert "{project_id:String}" in prepared.sql
        assert prepared.params["project_id"] == "UHJvajEyMw=="
        # The literal project_id must not appear inlined anywhere.
        assert "UHJvajEyMw==" not in prepared.sql

    def test_time_range_pushed_into_inner_subquery(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 2, 1, tzinfo=timezone.utc)
        prepared = build_cost_join_export_sql(
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


class TestSecurity:
    def test_no_credentials_in_sql(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        for forbidden in ("access_key_id", "secret_access_key", "session_token"):
            assert forbidden not in prepared.sql

    def test_references_nc_by_name(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert JOB.hex in prepared.sql  # NC name is built from job_id.hex

    @pytest.mark.parametrize("table", ["calls_complete", "calls_merged"])
    def test_tier_1_tables_supported(self, table: str) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB,
            table=cast(ExportTable, table),
            project_id="proj",
        )
        assert f"FROM {table}" in prepared.sql

    def test_references_canonical_prices_table(self) -> None:
        prepared = build_cost_join_export_sql(
            job_id=JOB, table="calls_complete", project_id="proj"
        )
        assert LLM_TOKEN_PRICES_TABLE in prepared.sql
